from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from netCDF4 import Dataset
from PIL import Image
from pyproj import CRS, Transformer

from app.core.config import get_settings


DEMO_RELATIVE_DIR = Path("raw/realtime_demo/goes18/park_fire_2024")
PROCESSED_RELATIVE_DIR = Path("processed/realtime_demo")


def _data_root() -> Path:
    return get_settings().resolved_data_dir


def _manifest_path() -> Path:
    return _data_root() / DEMO_RELATIVE_DIR / "manifest.json"


def _read_manifest() -> dict[str, Any]:
    path = _manifest_path()
    if not path.exists():
        raise FileNotFoundError("GOES-18演示数据清单不存在，请先运行下载脚本")
    return json.loads(path.read_text(encoding="utf-8"))


def _find_slot(manifest: dict[str, Any], slot_index: int) -> dict[str, Any]:
    slots = manifest.get("slots", [])
    if slot_index < 0 or slot_index >= len(slots):
        raise ValueError(f"slot_index must be between 0 and {max(0, len(slots) - 1)}")
    return slots[slot_index]


def _asset(slot: dict[str, Any], channel: str) -> dict[str, Any]:
    for item in slot.get("assets", []):
        if item.get("channel") == channel:
            return item
    raise FileNotFoundError(f"{channel} asset is missing from selected slot")


def _local_asset(asset: dict[str, Any]) -> Path:
    path = _data_root().parent / Path(asset["local_path"])
    if not path.exists():
        raise FileNotFoundError(f"演示影像文件不存在: {asset['local_path']}")
    return path


def _brightness_temperature(dataset: Dataset) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    radiance = np.asarray(dataset.variables["Rad"][:], dtype=np.float32)
    radiance = np.maximum(radiance, 1e-6)
    fk1 = float(dataset.variables["planck_fk1"][...])
    fk2 = float(dataset.variables["planck_fk2"][...])
    bc1 = float(dataset.variables["planck_bc1"][...])
    bc2 = float(dataset.variables["planck_bc2"][...])
    temperature = (fk2 / np.log((fk1 / radiance) + 1.0) - bc1) / bc2
    x = np.asarray(dataset.variables["x"][:], dtype=np.float64)
    y = np.asarray(dataset.variables["y"][:], dtype=np.float64)
    return temperature, x, y


def _latlon_grid(x: np.ndarray, y: np.ndarray, dataset: Dataset) -> tuple[np.ndarray, np.ndarray]:
    projection = dataset.variables["goes_imager_projection"]
    perspective_height = float(projection.perspective_point_height)
    longitude_origin = float(projection.longitude_of_projection_origin)
    sweep = getattr(projection, "sweep_angle_axis", "x")
    semi_major = float(projection.semi_major_axis)
    semi_minor = float(projection.semi_minor_axis)
    x_mesh, y_mesh = np.meshgrid(x, y)
    source = CRS.from_proj4(
        f"+proj=geos +h={perspective_height} +lon_0={longitude_origin} "
        f"+a={semi_major} +b={semi_minor} +sweep={sweep} +units=m +no_defs"
    )
    # GOES x/y are scan angles in radians; pyproj's geos CRS expects metres.
    transformer = Transformer.from_crs(source, "EPSG:4326", always_xy=True)
    longitude, latitude = transformer.transform(
        x_mesh * perspective_height,
        y_mesh * perspective_height,
    )
    return np.asarray(longitude), np.asarray(latitude)


def _dilate(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, constant_values=False)
    return np.logical_or.reduce(
        [padded[row : row + mask.shape[0], col : col + mask.shape[1]] for row in range(3) for col in range(3)]
    )


def _fdcc_validation(
    fdcc_path: Path,
    detected_mask: np.ndarray,
    spatial_mask: np.ndarray,
    longitude: np.ndarray,
    latitude: np.ndarray,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with Dataset(fdcc_path) as dataset:
        official_values = np.asarray(dataset.variables["Mask"][:])
    official_mask = spatial_mask & np.isin(official_values, [10, 11, 12, 13, 14, 15, 30, 31, 32, 33, 34, 35])
    detected_count = int(np.count_nonzero(detected_mask))
    official_count = int(np.count_nonzero(official_mask))
    matched_detected = int(np.count_nonzero(detected_mask & _dilate(official_mask)))
    matched_official = int(np.count_nonzero(official_mask & _dilate(detected_mask)))
    precision = matched_detected / detected_count if detected_count else 0.0
    recall = matched_official / official_count if official_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    rows, cols = np.where(official_mask)
    reference_hotspots = [
        {
            "reference_id": f"fdcc-{int(row)}-{int(col)}",
            "longitude": round(float(longitude[row, col]), 5),
            "latitude": round(float(latitude[row, col]), 5),
            "mask_code": int(official_values[row, col]),
            "source": "GOES-18 ABI-L2-FDCC",
        }
        for row, col in zip(rows[:500], cols[:500], strict=False)
    ]
    return (
        {
            "reference_product": "GOES-18 ABI-L2-FDCC",
            "matching_tolerance_pixels": 1,
            "detected_pixel_count": detected_count,
            "reference_fire_pixel_count": official_count,
            "matched_detected_pixel_count": matched_detected,
            "matched_reference_pixel_count": matched_official,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
        reference_hotspots,
    )


def _write_preview(
    bt07: np.ndarray,
    bt14: np.ndarray,
    spatial_mask: np.ndarray,
    detected_mask: np.ndarray,
    official_mask: np.ndarray,
    slot_index: int,
) -> str:
    rows, cols = np.where(spatial_mask)
    if not rows.size:
        raise ValueError("Park Fire bbox does not intersect the GOES grid")
    row_slice = slice(int(rows.min()), int(rows.max()) + 1)
    col_slice = slice(int(cols.min()), int(cols.max()) + 1)
    c07 = bt07[row_slice, col_slice]
    delta = (bt07 - bt14)[row_slice, col_slice]
    valid = spatial_mask[row_slice, col_slice] & np.isfinite(c07)

    thermal = np.clip((c07 - 285.0) / 85.0, 0.0, 1.0)
    contrast = np.clip((delta + 8.0) / 32.0, 0.0, 1.0)
    red = np.clip(thermal * 1.8, 0.0, 1.0)
    green = np.clip((thermal - 0.18) * 1.35, 0.0, 1.0)
    blue = np.clip((0.58 - thermal) * 1.25 + contrast * 0.18, 0.0, 1.0)
    rgb = np.stack([red, green, blue], axis=-1)
    rgb[~valid] = 0.0

    official = official_mask[row_slice, col_slice]
    detected = detected_mask[row_slice, col_slice]
    rgb[official] = [0.10, 0.88, 0.95]
    rgb[detected] = [1.00, 0.16, 0.05]
    rgb[official & detected] = [1.00, 0.88, 0.05]

    image = Image.fromarray((rgb * 255).astype(np.uint8), mode="RGB")
    if image.width < 900:
        scale = min(6, max(1, 900 // max(1, image.width)))
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    output_dir = _data_root() / PROCESSED_RELATIVE_DIR / "previews"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"slot_{slot_index:02d}.png"
    image.save(output_path, format="PNG", optimize=True)
    return str(output_path.relative_to(_data_root())).replace("\\", "/")


def _detect_hotspots(c07_path: Path, c14_path: Path, fdcc_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    with Dataset(c07_path) as c07, Dataset(c14_path) as c14:
        bt07, x, y = _brightness_temperature(c07)
        bt14, _, _ = _brightness_temperature(c14)
        # The two CONUS files have the same ABI grid. Resize only if an
        # upstream product changes its raster shape.
        if bt07.shape != bt14.shape:
            raise ValueError(f"C07/C14 grid mismatch: {bt07.shape} vs {bt14.shape}")
        longitude, latitude = _latlon_grid(x, y, c07)

    park_bbox = (-122.0, 39.5, -120.5, 40.5)
    spatial = (
        (longitude >= park_bbox[0])
        & (longitude <= park_bbox[2])
        & (latitude >= park_bbox[1])
        & (latitude <= park_bbox[3])
    )
    difference = bt07 - bt14
    mask = spatial & (bt07 >= 330.0) & (difference >= 8.0)
    evaluation, reference_hotspots = _fdcc_validation(fdcc_path, mask, spatial, longitude, latitude)
    with Dataset(fdcc_path) as dataset:
        official_values = np.asarray(dataset.variables["Mask"][:])
    official_mask = spatial & np.isin(official_values, [10, 11, 12, 13, 14, 15, 30, 31, 32, 33, 34, 35])
    rows, cols = np.where(mask)
    # Keep the full pixel mask for validation, but use non-maximum suppression
    # for map display so a raster fire patch is not mistaken for many fires.
    scores = bt07[rows, cols] + difference[rows, cols]
    order = np.argsort(scores)[::-1][:500]
    hotspots = []
    selected_pixels: list[tuple[int, int]] = []
    minimum_separation_pixels = 4
    for index in order:
        row, col = int(rows[index]), int(cols[index])
        if any((row - old_row) ** 2 + (col - old_col) ** 2 < minimum_separation_pixels ** 2 for old_row, old_col in selected_pixels):
            continue
        selected_pixels.append((row, col))
        rank = len(selected_pixels)
        hotspots.append(
            {
                "detection_id": f"goes-demo-{rank:04d}-{row}-{col}",
                "longitude": round(float(longitude[row, col]), 5),
                "latitude": round(float(latitude[row, col]), 5),
                "brightness_temperature_c07_k": round(float(bt07[row, col]), 2),
                "brightness_temperature_c14_k": round(float(bt14[row, col]), 2),
                "brightness_difference_k": round(float(difference[row, col]), 2),
                "confidence": round(min(0.99, max(0.0, 0.5 + float(difference[row, col]) / 40.0)), 3),
                "status": "candidate",
                "algorithm": "goes_abi_bt_threshold_nms_v0.2",
                "source_pixel_count": int(np.count_nonzero(mask)),
            }
        )
        if len(hotspots) >= 30:
            break
    return {
        "schema_version": "fire.realtime.demo.hotspots.v0.1",
        "event_id": manifest["event_id"],
        "display_name": manifest["display_name"],
        "data_source_mode": manifest["data_source_mode"],
        "observed_at": None,
        "source": "GOES-18 ABI C07/C14",
        "algorithm": {
            "name": "goes_abi_bt_threshold_nms_v0.2",
            "c07_threshold_k": 330.0,
            "c07_minus_c14_threshold_k": 8.0,
            "display_strategy": "local_peak_non_maximum_suppression",
            "minimum_separation_pixels": 4,
            "pixel_resolution_note": "GOES ABI CONUS imagery is a coarse raster; displayed points are representative peaks, not independent fire pixels.",
            "bbox_wgs84": list(park_bbox),
        },
        "hotspots": hotspots,
        "total": len(hotspots),
        "reference_hotspots": reference_hotspots,
        "evaluation": evaluation,
        "preview_legend": {
            "red": "threshold candidate",
            "cyan": "GOES FDCC reference",
            "yellow": "matched candidate and reference",
        },
    }


def demo_manifest() -> dict[str, Any]:
    manifest = _read_manifest()
    for slot in manifest.get("slots", []):
        slot["downloaded"] = all((_data_root().parent / Path(asset["local_path"])).exists() for asset in slot.get("assets", []))
    return manifest


def run_detection(slot_index: int) -> dict[str, Any]:
    manifest = _read_manifest()
    slot = _find_slot(manifest, slot_index)
    c07 = _local_asset(_asset(slot, "C07"))
    c14 = _local_asset(_asset(slot, "C14"))
    fdcc = _local_asset(_asset(slot, "FDCC"))
    result = _detect_hotspots(c07, c14, fdcc, manifest)
    result["observed_at"] = slot["observed_at"]
    result["slot_index"] = slot_index
    result["assets"] = {channel: _asset(slot, channel) for channel in ("C07", "C14", "FDCC") if any(item.get("channel") == channel for item in slot.get("assets", []))}
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0)
    result["processed_at"] = fetched_at.isoformat().replace("+00:00", "Z")
    result["preview_file"] = _write_preview(
        *_preview_inputs(c07, c14, fdcc, manifest),
        slot_index,
    )
    output_dir = _data_root() / PROCESSED_RELATIVE_DIR / "hotspots"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"slot_{slot_index:02d}.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["result_file"] = str(output_path.relative_to(_data_root())).replace("\\", "/")
    return result


def _preview_inputs(
    c07_path: Path,
    c14_path: Path,
    fdcc_path: Path,
    manifest: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with Dataset(c07_path) as c07, Dataset(c14_path) as c14:
        bt07, x, y = _brightness_temperature(c07)
        bt14, _, _ = _brightness_temperature(c14)
        longitude, latitude = _latlon_grid(x, y, c07)
    bbox = (-122.0, 39.5, -120.5, 40.5)
    spatial = (
        (longitude >= bbox[0]) & (longitude <= bbox[2])
        & (latitude >= bbox[1]) & (latitude <= bbox[3])
    )
    detected = spatial & (bt07 >= 330.0) & ((bt07 - bt14) >= 8.0)
    with Dataset(fdcc_path) as dataset:
        values = np.asarray(dataset.variables["Mask"][:])
    official = spatial & np.isin(values, [10, 11, 12, 13, 14, 15, 30, 31, 32, 33, 34, 35])
    return bt07, bt14, spatial, detected, official


def preview_path(slot_index: int) -> Path:
    path = _data_root() / PROCESSED_RELATIVE_DIR / "previews" / f"slot_{slot_index:02d}.png"
    if not path.exists():
        run_detection(slot_index)
    return path
