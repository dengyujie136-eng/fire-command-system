"""Submit complete-area Dixie Fire Sentinel-2 GeoTIFF exports to Google Drive.

Run this in the gee_safe environment. GEE creates the real GeoTIFF files in
Google Drive; download them manually after the tasks become COMPLETED.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import ee


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "manifests" / "dixie_fire_2021_sentinel2_gee_drive_tasks_10m.json"

AOI_BBOX = [-121.542701, 39.860961, -120.186653, 40.784350]
BANDS = ["B2", "B3", "B4", "B8"]
MGRS_TILES = ["10TFK", "10TFL", "10TGK", "10TGL", "11TKE", "11TKF"]
GRID_COLUMNS = 3
GRID_ROWS = 2

PHASES = {
    "pre": ("2021-07-01", "2021-07-13", "灾前"),
    "during": ("2021-07-13", "2021-07-21", "灾中"),
    "post": ("2021-09-20", "2021-09-24", "灾后"),
}


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=os.environ.get("GEE_PROJECT_ID"), required=False)
    parser.add_argument("--folder", default="Dixie_Fire_2021_Sentinel2_10m")
    parser.add_argument("--max-cloud", type=float, default=40.0)
    return parser.parse_args()


def init(project: str | None) -> None:
    if not project:
        raise SystemExit("请使用 --project YOUR_GEE_PROJECT_ID")
    try:
        ee.Initialize(project=project)
    except Exception as error:
        raise SystemExit(
            f"GEE 初始化失败：{error}\n请先执行 earthengine authenticate"
        ) from error


def grid_regions() -> list[tuple[str, list[float]]]:
    west, south, east, north = AOI_BBOX
    result = []
    for row in range(GRID_ROWS):
        y0 = south + (north - south) * row / GRID_ROWS
        y1 = south + (north - south) * (row + 1) / GRID_ROWS
        for column in range(GRID_COLUMNS):
            x0 = west + (east - west) * column / GRID_COLUMNS
            x1 = west + (east - west) * (column + 1) / GRID_COLUMNS
            result.append((f"r{row + 1:02d}c{column + 1:02d}", [x0, y0, x1, y1]))
    return result


def phase_image(start: str, end: str, max_cloud: float) -> tuple[ee.Image, dict, dict]:
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start, end)
        .filterBounds(ee.Geometry.Rectangle(AOI_BBOX))
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
        .select(BANDS)
    )
    counts: dict[str, int] = {}
    selected: dict[str, str] = {}
    for tile in MGRS_TILES:
        tile_collection = collection.filter(ee.Filter.eq("MGRS_TILE", tile))
        count = int(tile_collection.size().getInfo())
        counts[tile] = count
        if count:
            selected[tile] = tile_collection.sort("CLOUDY_PIXEL_PERCENTAGE").aggregate_array(
                "system:id"
            ).getInfo()[0]
    missing = [tile for tile in MGRS_TILES if tile not in selected]
    if missing:
        raise RuntimeError(f"{start} 至 {end} 缺少瓦片覆盖：{missing}")
    # Resolve the selected scenes into a fixed image list before export. This
    # keeps each task expression small and avoids the direct-download URL limit.
    image = ee.ImageCollection.fromImages(
        [ee.Image(selected[tile]).select(BANDS) for tile in MGRS_TILES]
    ).mosaic().toInt16()
    return image, counts, selected


def submit_exports(project: str, folder: str, max_cloud: float) -> dict:
    records = []
    for phase, (start, end, label) in PHASES.items():
        image, counts, selected = phase_image(start, end, max_cloud)
        for tile_id, bbox in grid_regions():
            description = f"dixie_fire_2021_s2_10m_{phase}_{tile_id}"
            task = ee.batch.Export.image.toDrive(
                image=image,
                description=description,
                folder=folder,
                fileNamePrefix=description,
                region=ee.Geometry.Rectangle(bbox),
                scale=10,
                crs="EPSG:32610",
                maxPixels=1e13,
                fileFormat="GeoTIFF",
                formatOptions={"cloudOptimized": True, "noData": 0},
            )
            task.start()
            records.append(
                {
                    "task_id": task.id,
                    "task_description": description,
                    "phase": phase,
                    "phase_label": label,
                    "date_start": start,
                    "date_end_exclusive": end,
                    "drive_folder": folder,
                    "file_name_prefix": description,
                    "bands": BANDS,
                    "crs": "EPSG:32610",
                    "resolution_m": 10,
                    "bbox": bbox,
                    "source_scene_counts_by_mgrs_tile": counts,
                    "selected_scene_ids_by_mgrs_tile": selected,
                }
            )
            print(f"SUBMITTED {description} {task.id}")
    return {
        "schema_version": "fire.imagery.gee-drive-task-manifest.v0.1",
        "event_id": "dixie_fire_2021",
        "source": "Google Earth Engine / COPERNICUS/S2_SR_HARMONIZED",
        "project_id": project,
        "drive_folder": folder,
        "aoi_bbox": AOI_BBOX,
        "bands": BANDS,
        "grid_columns": GRID_COLUMNS,
        "grid_rows": GRID_ROWS,
        "assets": records,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "resolution_m": 10,
        "crs": "EPSG:32610",
        "download_note": "After tasks are COMPLETED, download all 10 m GeoTIFFs from Google Drive.",
    }


def main() -> int:
    cli = args()
    init(cli.project)
    manifest = submit_exports(cli.project, cli.folder, cli.max_cloud)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SUBMITTED_TASKS {len(manifest['assets'])}")
    print(f"MANIFEST {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
