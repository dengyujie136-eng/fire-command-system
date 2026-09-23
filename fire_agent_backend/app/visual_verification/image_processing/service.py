import hashlib
import json
import math
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.visual_verification.image_processing.errors import (
    CandidateOutsideRasterError,
    DerivativeConflictError,
    EmptyRasterCropError,
    InvalidRasterBandError,
    MissingRasterCrsError,
    RasterBackendUnavailableError,
    UnsupportedImageError,
    UnsupportedRasterCrsError,
)
from app.visual_verification.image_processing.paths import SafeImagePathResolver
from app.visual_verification.image_processing.schemas import (
    ImageCropRequest,
    ImageProcessingResult,
    ImageSize,
    PixelWindow,
)


_PLAIN_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_GEOTIFF_SUFFIXES = {".tif", ".tiff"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _polygon(bounds: tuple[float, float, float, float]) -> dict[str, object]:
    west, south, east, north = bounds
    return {
        "type": "Polygon",
        "coordinates": [[
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
        ]],
    }


def _resize_down(image: Image.Image, max_dimension: int) -> Image.Image:
    output = image.copy()
    output.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    return output


def _atomic_save_image(
    image: Image.Image,
    destination: Path,
    *,
    image_format: str,
    jpeg_quality: int,
) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".image-", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        parameters: dict[str, Any] = {"format": image_format}
        if image_format == "JPEG":
            parameters.update(quality=jpeg_quality, optimize=True, progressive=True)
        image.save(temporary, **parameters)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_save_json(value: dict[str, Any], destination: Path) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".metadata-", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(
            json.dumps(value, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _detect_source_kind(path: Path, requested_kind: str) -> str:
    if requested_kind != "auto":
        return requested_kind
    suffix = path.suffix.lower()
    if suffix in _GEOTIFF_SUFFIXES:
        return "geotiff"
    if suffix in _PLAIN_IMAGE_SUFFIXES:
        return "plain_image"
    raise UnsupportedImageError(f"unsupported source image extension: {suffix or '<none>'}")


def _plain_image(path: Path, max_dimension: int) -> tuple[Image.Image, dict[str, Any]]:
    try:
        with Image.open(path) as opened:
            transposed = ImageOps.exif_transpose(opened)
            source_size = ImageSize(width=transposed.width, height=transposed.height)
            normalized = transposed.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise UnsupportedImageError(f"cannot decode source image: {path.name}") from exc

    output = _resize_down(normalized, max_dimension)
    return output, {
        "source_size": source_size,
        "crs": None,
        "requested_extent_geojson": None,
        "actual_extent_geojson": None,
        "pixel_window": None,
        "band_indexes": None,
        "nodata_ratio": None,
        "warnings": [
            "plain_image_has_no_georeferencing; source is treated as an existing candidate view"
        ],
    }


def _select_band_indexes(count: int, requested: list[int] | None, descriptions: tuple[str | None, ...] = ()) -> list[int]:
    if requested is not None:
        if any(index > count for index in requested):
            raise InvalidRasterBandError(
                f"requested raster bands {requested} exceed available band count {count}"
            )
        return requested
    names = {name.strip().upper(): index for index, name in enumerate(descriptions, start=1) if name}
    red = names.get("B4") or names.get("B04")
    green = names.get("B3") or names.get("B03")
    blue = names.get("B2") or names.get("B02")
    if red and green and blue:
        return [red, green, blue]
    if count == 1:
        return [1]
    if count in (3, 4):
        return [1, 2, 3]
    raise InvalidRasterBandError(
        "multiband rasters with other than 3 or 4 bands require explicit band_indexes"
    )


def _stretch_to_uint8(
    data: np.ma.MaskedArray,
    percentiles: tuple[float, float],
) -> tuple[np.ndarray, float]:
    mask = np.ma.getmaskarray(data)
    if mask.ndim == 0:
        mask = np.zeros(data.shape, dtype=bool)
    valid_pixels = ~np.any(mask, axis=0)
    nodata_ratio = float(1.0 - valid_pixels.mean())
    if not valid_pixels.any():
        raise EmptyRasterCropError("raster crop contains no valid pixels")

    output_bands: list[np.ndarray] = []
    low_percentile, high_percentile = percentiles
    for band_index in range(data.shape[0]):
        band = np.asarray(
            data[band_index].astype(np.float64).filled(np.nan),
            dtype=np.float64,
        )
        values = band[valid_pixels]
        values = values[np.isfinite(values)]
        if values.size == 0:
            raise EmptyRasterCropError("selected raster band contains no finite pixels")
        low, high = np.percentile(values, [low_percentile, high_percentile])
        if not np.isfinite(low) or not np.isfinite(high):
            raise EmptyRasterCropError("cannot calculate raster display stretch")
        if high <= low:
            scaled = np.zeros(band.shape, dtype=np.uint8)
        else:
            scaled = np.clip((band - low) / (high - low), 0, 1)
            scaled = np.nan_to_num(scaled, nan=0.0)
            scaled = (scaled * 255).astype(np.uint8)
        scaled[~valid_pixels] = 0
        output_bands.append(scaled)

    if len(output_bands) == 1:
        rgb = np.repeat(output_bands[0][..., np.newaxis], 3, axis=2)
    else:
        rgb = np.stack(output_bands, axis=2)
    return rgb, nodata_ratio


def _geotiff_image(
    path: Path,
    request: ImageCropRequest,
) -> tuple[Image.Image, dict[str, Any]]:
    try:
        import rasterio
        from rasterio.warp import transform, transform_bounds
        from rasterio.windows import Window, from_bounds
    except ImportError as exc:
        raise RasterBackendUnavailableError(
            "GeoTIFF processing requires the rasterio dependency"
        ) from exc

    try:
        dataset = rasterio.open(path)
    except Exception as exc:
        raise UnsupportedImageError(f"cannot open GeoTIFF: {path.name}") from exc

    with dataset:
        if dataset.crs is None:
            raise MissingRasterCrsError("GeoTIFF has no coordinate reference system")
        if not dataset.crs.is_projected:
            raise UnsupportedRasterCrsError(
                "candidate radius cropping requires a projected raster CRS with metre units"
            )
        try:
            unit_factor = float(dataset.crs.linear_units_factor[1])
        except Exception as exc:
            raise UnsupportedRasterCrsError("cannot determine raster linear units") from exc
        if not math.isclose(unit_factor, 1.0, rel_tol=0, abs_tol=1e-9):
            raise UnsupportedRasterCrsError("raster CRS linear unit must be metre")

        center_x, center_y = transform(
            "EPSG:4326",
            dataset.crs,
            [request.longitude],
            [request.latitude],
        )
        radius = request.crop_radius_m
        requested_bounds = (
            center_x[0] - radius,
            center_y[0] - radius,
            center_x[0] + radius,
            center_y[0] + radius,
        )
        floating_window = from_bounds(*requested_bounds, transform=dataset.transform)
        column_start = max(0, math.floor(floating_window.col_off))
        row_start = max(0, math.floor(floating_window.row_off))
        column_stop = min(dataset.width, math.ceil(floating_window.col_off + floating_window.width))
        row_stop = min(dataset.height, math.ceil(floating_window.row_off + floating_window.height))
        if column_stop <= column_start or row_stop <= row_start:
            raise CandidateOutsideRasterError("candidate crop does not intersect the raster")

        window = Window(
            column_start,
            row_start,
            column_stop - column_start,
            row_stop - row_start,
        )
        band_indexes = _select_band_indexes(dataset.count, request.band_indexes, dataset.descriptions)
        raster_data = dataset.read(band_indexes, window=window, masked=True)
        rgb, nodata_ratio = _stretch_to_uint8(
            raster_data,
            request.stretch_percentiles,
        )
        image = Image.fromarray(rgb)
        source_size = ImageSize(width=dataset.width, height=dataset.height)
        output = _resize_down(image, request.max_dimension)

        requested_wgs84 = transform_bounds(
            dataset.crs,
            "EPSG:4326",
            *requested_bounds,
            densify_pts=21,
        )
        actual_raster_bounds = dataset.window_bounds(window)
        actual_wgs84 = transform_bounds(
            dataset.crs,
            "EPSG:4326",
            *actual_raster_bounds,
            densify_pts=21,
        )
        warnings: list[str] = []
        if (
            column_start != math.floor(floating_window.col_off)
            or row_start != math.floor(floating_window.row_off)
            or column_stop != math.ceil(floating_window.col_off + floating_window.width)
            or row_stop != math.ceil(floating_window.row_off + floating_window.height)
        ):
            warnings.append("requested crop was clipped to raster bounds")
        if request.processing_purpose == "pipeline_test":
            warnings.append("pipeline_test output is not eligible as visual fire evidence")

        return output, {
            "source_size": source_size,
            "crs": dataset.crs.to_string(),
            "requested_extent_geojson": _polygon(requested_wgs84),
            "actual_extent_geojson": _polygon(actual_wgs84),
            "pixel_window": PixelWindow(
                column_offset=column_start,
                row_offset=row_start,
                width=column_stop - column_start,
                height=row_stop - row_start,
            ),
            "band_indexes": band_indexes,
            "nodata_ratio": nodata_ratio,
            "warnings": warnings,
        }


class ImageProcessingService:
    def __init__(self, source_root: Path, output_root: Path | None = None) -> None:
        self.paths = SafeImagePathResolver(source_root, output_root)

    def process(self, request: ImageCropRequest) -> ImageProcessingResult:
        source = self.paths.resolve_source(request.source_uri)
        source_kind = _detect_source_kind(source, request.source_kind)
        source_sha256 = _sha256(source)
        parameters = request.model_dump(mode="json", exclude={"source_uri"})
        parameter_sha256 = _canonical_hash(parameters)
        identity = _canonical_hash({
            "visual_case_id": request.visual_case_id,
            "source_asset_id": request.source_asset_id,
            "source_sha256": source_sha256,
            "parameter_sha256": parameter_sha256,
        })
        derivative_id = f"img-{identity[:32]}"
        output_directory = self.paths.output_directory(
            request.visual_case_id,
            request.source_asset_id,
        )
        extension = ".jpg" if request.output_format == "jpeg" else ".png"
        output_path = output_directory / f"{derivative_id}{extension}"
        preview_path = output_directory / f"{derivative_id}-preview.jpg"
        metadata_path = output_directory / f"{derivative_id}.json"

        if metadata_path.exists():
            try:
                cached = ImageProcessingResult.model_validate_json(
                    metadata_path.read_text(encoding="utf-8")
                )
            except Exception as exc:
                raise DerivativeConflictError(
                    "existing derivative metadata is invalid"
                ) from exc
            if (
                cached.source_sha256 != source_sha256
                or cached.parameter_sha256 != parameter_sha256
                or not output_path.exists()
                or not preview_path.exists()
                or _sha256(output_path) != cached.output_sha256
                or _sha256(preview_path) != cached.preview_sha256
            ):
                raise DerivativeConflictError(
                    "existing deterministic derivative does not match its metadata"
                )
            return cached.model_copy(update={"cache_hit": True})

        if source_kind == "plain_image":
            output_image, details = _plain_image(source, request.max_dimension)
        else:
            output_image, details = _geotiff_image(source, request)

        preview_image = _resize_down(output_image, request.thumbnail_dimension)
        output_format = "JPEG" if request.output_format == "jpeg" else "PNG"
        _atomic_save_image(
            output_image,
            output_path,
            image_format=output_format,
            jpeg_quality=request.jpeg_quality,
        )
        _atomic_save_image(
            preview_image,
            preview_path,
            image_format="JPEG",
            jpeg_quality=min(request.jpeg_quality, 88),
        )

        completed_at = datetime.now(UTC)
        result = ImageProcessingResult(
            derivative_id=derivative_id,
            visual_case_id=request.visual_case_id,
            source_asset_id=request.source_asset_id,
            source_uri=request.source_uri,
            source_kind=source_kind,
            source_sha256=source_sha256,
            parameter_sha256=parameter_sha256,
            output_uri=self.paths.output_uri(output_path),
            preview_uri=self.paths.output_uri(preview_path),
            metadata_uri=self.paths.output_uri(metadata_path),
            output_sha256=_sha256(output_path),
            preview_sha256=_sha256(preview_path),
            source_size=details["source_size"],
            output_size=ImageSize(width=output_image.width, height=output_image.height),
            preview_size=ImageSize(width=preview_image.width, height=preview_image.height),
            output_format=request.output_format,
            crs=details["crs"],
            requested_extent_geojson=details["requested_extent_geojson"],
            actual_extent_geojson=details["actual_extent_geojson"],
            pixel_window=details["pixel_window"],
            band_indexes=details["band_indexes"],
            nodata_ratio=details["nodata_ratio"],
            processing_parameters=parameters,
            processing_purpose=request.processing_purpose,
            is_simulated=request.is_simulated,
            warnings=details["warnings"],
            completed_at=completed_at,
        )
        _atomic_save_json(result.model_dump(mode="json"), metadata_path)
        return result
