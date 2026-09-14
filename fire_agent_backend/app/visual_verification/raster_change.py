import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from app.visual_verification.image_processing.errors import (
    InvalidRasterBandError,
    MissingRasterCrsError,
    RasterBackendUnavailableError,
    UnsupportedImageError,
    UnsupportedRasterCrsError,
)
from app.visual_verification.image_processing.paths import SafeImagePathResolver
from app.visual_verification.schemas import (
    RemoteSensingAnalysisType,
    RemoteSensingChangeResult,
)


def _rasterio_modules():
    try:
        import rasterio
        from rasterio import features
        from rasterio.vrt import WarpedVRT
        from rasterio.warp import Resampling, transform_geom
    except ImportError as exc:
        raise RasterBackendUnavailableError(
            "multi-temporal raster analysis requires rasterio"
        ) from exc
    return rasterio, features, WarpedVRT, Resampling, transform_geom


def _band_map(dataset) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, description in enumerate(dataset.descriptions, start=1):
        if description:
            result[description.strip().upper()] = index
    return result


def _require_bands(dataset, names: tuple[str, ...]) -> dict[str, int]:
    available = _band_map(dataset)
    missing = [name for name in names if name not in available]
    if missing:
        raise InvalidRasterBandError(
            f"{Path(dataset.name).name} is missing band descriptions: {', '.join(missing)}"
        )
    return available


def _index(nir: np.ma.MaskedArray, comparison: np.ma.MaskedArray) -> np.ndarray:
    nir_values = np.asarray(nir.astype(np.float32).filled(np.nan))
    comparison_values = np.asarray(comparison.astype(np.float32).filled(np.nan))
    denominator = nir_values + comparison_values
    with np.errstate(divide="ignore", invalid="ignore"):
        result = (nir_values - comparison_values) / denominator
    result[~np.isfinite(result)] = np.nan
    return result.astype(np.float32)


def _stretch_rgb(data: np.ma.MaskedArray) -> Image.Image:
    values = np.asarray(data.astype(np.float32).filled(np.nan))
    valid = np.all(np.isfinite(values), axis=0)
    output: list[np.ndarray] = []
    for band in values:
        sample = band[valid]
        if sample.size:
            low, high = np.percentile(sample, (2, 98))
        else:
            low, high = 0.0, 1.0
        if not math.isfinite(float(low)) or not math.isfinite(float(high)) or high <= low:
            scaled = np.zeros_like(band, dtype=np.uint8)
        else:
            scaled = np.clip((band - low) / (high - low), 0, 1)
            scaled = np.nan_to_num(scaled, nan=0.0)
            scaled = (scaled * 255).astype(np.uint8)
        scaled[~valid] = 0
        output.append(scaled)
    return Image.fromarray(np.stack(output, axis=2))


def _save_preview(image: Image.Image, path: Path, max_dimension: int = 2048) -> None:
    """Write a model-ready preview without expanding large source rasters in storage."""

    if max(image.size) > max_dimension:
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    image.save(path, format="JPEG", quality=90)


def _write_float_raster(path: Path, values: np.ndarray, profile: dict) -> None:
    rasterio, _features, _vrt, _resampling, _transform_geom = _rasterio_modules()
    output_profile = dict(profile)
    output_profile.update(
        driver="GTiff",
        count=1,
        dtype="float32",
        nodata=-9999.0,
        compress="deflate",
    )
    encoded = np.where(np.isfinite(values), values, -9999.0).astype(np.float32)
    with rasterio.open(path, "w", **output_profile) as output:
        output.write(encoded, 1)


def _write_mask_raster(path: Path, values: np.ndarray, profile: dict) -> None:
    rasterio, _features, _vrt, _resampling, _transform_geom = _rasterio_modules()
    output_profile = dict(profile)
    output_profile.update(
        driver="GTiff",
        count=1,
        dtype="uint8",
        nodata=0,
        compress="deflate",
    )
    with rasterio.open(path, "w", **output_profile) as output:
        output.write(values.astype(np.uint8), 1)


def _multi_polygon_wgs84(mask: np.ndarray, transform, crs) -> dict[str, object]:
    _rasterio, features, _vrt, _resampling, transform_geom = _rasterio_modules()
    polygons: list[object] = []
    for geometry, value in features.shapes(
        mask.astype(np.uint8),
        mask=mask.astype(bool),
        transform=transform,
    ):
        if int(value) != 1:
            continue
        projected = transform_geom(crs, "EPSG:4326", geometry, precision=7)
        if projected["type"] == "Polygon":
            polygons.append(projected["coordinates"])
        elif projected["type"] == "MultiPolygon":
            polygons.extend(projected["coordinates"])
    return {"type": "MultiPolygon", "coordinates": polygons}


class RasterChangeAnalyzer:
    """Compute a small, reproducible before/after wildfire change product."""

    def __init__(self, source_root: Path, output_root: Path) -> None:
        self.paths = SafeImagePathResolver(source_root, output_root)

    def analyze(
        self,
        *,
        event_id: str,
        analysis_type: RemoteSensingAnalysisType,
        before_asset_id: str,
        before_uri: str,
        after_asset_id: str,
        after_uri: str,
        threshold: float | None,
        minimum_region_pixels: int,
        is_simulated: bool,
        target_geometry_wgs84: dict[str, object] | None = None,
        analysis_id: str | None = None,
    ) -> RemoteSensingChangeResult:
        rasterio, features, WarpedVRT, Resampling, transform_geom = _rasterio_modules()
        before_path = self.paths.resolve_source(before_uri)
        after_path = self.paths.resolve_source(after_uri)
        identity = {
            "event_id": event_id,
            "analysis_type": analysis_type.value,
            "before_asset_id": before_asset_id,
            "after_asset_id": after_asset_id,
            "before_size": before_path.stat().st_size,
            "after_size": after_path.stat().st_size,
            "before_modified_ns": before_path.stat().st_mtime_ns,
            "after_modified_ns": after_path.stat().st_mtime_ns,
            "threshold": threshold,
            "minimum_region_pixels": minimum_region_pixels,
            "target_geometry_wgs84": target_geometry_wgs84,
        }
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True).encode("utf-8")
        ).hexdigest()
        result_analysis_id = analysis_id or f"raster-change-{digest[:24]}"

        try:
            before_dataset = rasterio.open(before_path)
            after_dataset = rasterio.open(after_path)
        except Exception as exc:
            raise UnsupportedImageError("cannot open the before/after GeoTIFF pair") from exc

        with before_dataset as before, after_dataset as after:
            if before.crs is None or after.crs is None:
                raise MissingRasterCrsError("before and after rasters must define a CRS")
            if not before.crs.is_projected:
                raise UnsupportedRasterCrsError(
                    "area calculation requires a projected reference raster"
                )
            unit_factor = float(before.crs.linear_units_factor[1])
            if not math.isclose(unit_factor, 1.0, rel_tol=0, abs_tol=1e-9):
                raise UnsupportedRasterCrsError("reference raster units must be metres")

            before_bands = _require_bands(before, ("B2", "B3", "B4", "B8"))
            after_bands = _require_bands(after, ("B2", "B3", "B4", "B8"))
            use_nbr = "B12" in before_bands and "B12" in after_bands
            comparison_band = "B12" if use_nbr else "B4"
            method = "dnbr_threshold_v1" if use_nbr else "dndvi_threshold_v1"
            actual_threshold = threshold if threshold is not None else (0.10 if use_nbr else 0.20)
            warnings: list[str] = []
            if not use_nbr:
                warnings.append(
                    "B12 is unavailable; dNDVI is used as a vegetation-change proxy instead of dNBR"
                )

            before_nir = before.read(before_bands["B8"], masked=True)
            before_comparison = before.read(before_bands[comparison_band], masked=True)
            before_index = _index(before_nir, before_comparison)

            with WarpedVRT(
                after,
                crs=before.crs,
                transform=before.transform,
                width=before.width,
                height=before.height,
                resampling=Resampling.bilinear,
                nodata=after.nodata,
            ) as aligned_after:
                after_nir = aligned_after.read(after_bands["B8"], masked=True)
                after_comparison = aligned_after.read(
                    after_bands[comparison_band], masked=True
                )
                after_index = _index(after_nir, after_comparison)
                after_rgb = aligned_after.read(
                    [after_bands["B4"], after_bands["B3"], after_bands["B2"]],
                    masked=True,
                )
                after_nir_composite = aligned_after.read(
                    [after_bands["B8"], after_bands["B4"], after_bands["B3"]],
                    masked=True,
                )

            valid = np.isfinite(before_index) & np.isfinite(after_index)
            if target_geometry_wgs84 is not None:
                try:
                    projected_geometry = transform_geom(
                        "EPSG:4326",
                        before.crs,
                        target_geometry_wgs84,
                        precision=3,
                    )
                except Exception as exc:
                    raise UnsupportedImageError(
                        "target_geometry cannot be transformed to the raster CRS"
                    ) from exc
                target_mask = features.geometry_mask(
                    [projected_geometry],
                    out_shape=(before.height, before.width),
                    transform=before.transform,
                    invert=True,
                )
                valid &= target_mask
            change = np.where(valid, before_index - after_index, np.nan).astype(np.float32)
            raw_mask = valid & (change >= actual_threshold)
            cleaned_mask = features.sieve(
                raw_mask.astype(np.uint8),
                size=minimum_region_pixels,
                mask=valid,
                connectivity=8,
            ).astype(bool)
            changed_pixel_count = int(cleaned_mask.sum())
            valid_pixel_count = int(valid.sum())
            pixel_area_m2 = abs(
                before.transform.a * before.transform.e
                - before.transform.b * before.transform.d
            )
            area_hectares = changed_pixel_count * pixel_area_m2 / 10_000
            area_geometry = _multi_polygon_wgs84(
                cleaned_mask,
                before.transform,
                before.crs,
            )

            output_directory = self.paths.output_directory(
                f"remote-sensing-{event_id}", result_analysis_id
            )
            before_index_path = output_directory / "before-index.tif"
            after_index_path = output_directory / "after-index.tif"
            change_path = output_directory / "change-index.tif"
            mask_path = output_directory / "changed-area-mask.tif"
            geometry_path = output_directory / "changed-area-wgs84.geojson"
            before_rgb_path = output_directory / "before-rgb.jpg"
            after_rgb_path = output_directory / "after-rgb.jpg"
            before_nir_path = output_directory / "before-nir.jpg"
            after_nir_path = output_directory / "after-nir.jpg"

            profile = before.profile
            _write_float_raster(before_index_path, before_index, profile)
            _write_float_raster(after_index_path, after_index, profile)
            _write_float_raster(change_path, change, profile)
            _write_mask_raster(mask_path, cleaned_mask, profile)
            geometry_path.write_text(
                json.dumps(area_geometry, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            _save_preview(
                _stretch_rgb(
                    before.read(
                        [before_bands["B4"], before_bands["B3"], before_bands["B2"]],
                        masked=True,
                    )
                ),
                before_rgb_path,
            )
            _save_preview(_stretch_rgb(after_rgb), after_rgb_path)
            _save_preview(
                _stretch_rgb(
                    before.read(
                        [before_bands["B8"], before_bands["B4"], before_bands["B3"]],
                        masked=True,
                    )
                ),
                before_nir_path,
            )
            _save_preview(_stretch_rgb(after_nir_composite), after_nir_path)

            return RemoteSensingChangeResult(
                analysis_id=result_analysis_id,
                event_id=event_id,
                analysis_type=analysis_type,
                before_asset_id=before_asset_id,
                after_asset_id=after_asset_id,
                method=method,
                threshold=actual_threshold,
                minimum_region_pixels=minimum_region_pixels,
                changed_pixel_count=changed_pixel_count,
                valid_pixel_count=valid_pixel_count,
                area_hectares=round(area_hectares, 6),
                area_geometry_wgs84=area_geometry,
                source_crs=before.crs.to_string(),
                resolution_m=(abs(before.res[0]), abs(before.res[1])),
                output_uris={
                    "before_rgb": self.paths.output_uri(before_rgb_path),
                    "after_rgb": self.paths.output_uri(after_rgb_path),
                    "before_nir": self.paths.output_uri(before_nir_path),
                    "after_nir": self.paths.output_uri(after_nir_path),
                    "before_index": self.paths.output_uri(before_index_path),
                    "after_index": self.paths.output_uri(after_index_path),
                    "change_index": self.paths.output_uri(change_path),
                    "changed_area_mask": self.paths.output_uri(mask_path),
                    "area_geojson": self.paths.output_uri(geometry_path),
                },
                warnings=warnings,
                is_simulated=is_simulated,
            )
