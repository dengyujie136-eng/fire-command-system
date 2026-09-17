"""Download three full-area Sentinel-2 composites for the Dixie Fire from GEE.

The output files are real georeferenced GeoTIFFs. The region is the complete
MTBS Dixie Fire bounding box, not an individual candidate hotspot.
"""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import ee
import requests


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw" / "sentinel2" / "dixie_fire_2021" / "gee"
MANIFEST_PATH = ROOT / "data" / "manifests" / "dixie_fire_2021_sentinel2_gee.json"

# WGS84 extent of the downloaded MTBS Dixie Fire perimeter. The rectangle
# guarantees complete spatial coverage; the original perimeter remains the
# validation geometry in data/processed/burned_area/.
AOI_BBOX = [-121.542701, 39.860961, -120.186653, 40.784350]

PHASES = {
    "pre": {
        "start": "2021-07-01",
        "end": "2021-07-13",
        "label": "灾前",
    },
    "during": {
        "start": "2021-07-13",
        "end": "2021-07-21",
        "label": "灾中",
    },
    "post": {
        "start": "2021-09-20",
        "end": "2021-09-24",
        "label": "灾后",
    },
}

BANDS = ["B2", "B3", "B4", "B8"]
MGRS_TILES = ["10TFK", "10TFL", "10TGK", "10TGL", "11TKE", "11TKF"]

# Four columns by three rows keeps each native GEE download small enough for
# the download endpoint while the union of all cells covers the complete AOI.
GRID_COLUMNS = 4
GRID_ROWS = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        default=os.environ.get("GEE_PROJECT_ID"),
        help="Google Earth Engine Cloud Project ID, or set GEE_PROJECT_ID",
    )
    parser.add_argument(
        "--max-cloud",
        type=float,
        default=40.0,
        help="Maximum scene cloud percentage used before compositing",
    )
    return parser.parse_args()


def initialize(project: str | None) -> None:
    if not project:
        raise SystemExit(
            "Missing GEE project ID. Use --project YOUR_PROJECT_ID or set GEE_PROJECT_ID."
        )
    try:
        ee.Initialize(project=project)
    except Exception as error:
        print("GEE authentication is required or expired.")
        print("Run: earthengine authenticate")
        raise SystemExit(f"GEE initialization failed: {error}") from error


def sentinel_collection(start: str, end: str, max_cloud: float) -> ee.ImageCollection:
    return (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start, end)
        .filterBounds(ee.Geometry.Rectangle(AOI_BBOX))
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
        .select(BANDS)
    )


def grid_regions() -> list[tuple[str, list[float]]]:
    west, south, east, north = AOI_BBOX
    regions = []
    for row in range(GRID_ROWS):
        cell_south = south + (north - south) * row / GRID_ROWS
        cell_north = south + (north - south) * (row + 1) / GRID_ROWS
        for column in range(GRID_COLUMNS):
            cell_west = west + (east - west) * column / GRID_COLUMNS
            cell_east = west + (east - west) * (column + 1) / GRID_COLUMNS
            regions.append(
                (
                    f"r{row + 1:02d}c{column + 1:02d}",
                    [cell_west, cell_south, cell_east, cell_north],
                )
            )
    return regions


def download_one_tile(
    phase: str,
    config: dict,
    image: ee.Image,
    tile_id: str,
    tile_bbox: list[float],
) -> dict:
    filename = OUT_DIR / (
        f"dixie_fire_2021_sentinel2_{phase}_{tile_id}_"
        f"{config['start'].replace('-', '')}_{config['end'].replace('-', '')}_20m.tif"
    )
    if filename.exists() and filename.stat().st_size >= 50_000:
        with filename.open("rb") as stream:
            if stream.read(4) in (b"II*\x00", b"MM\x00*"):
                return asset_record(phase, config, tile_id, tile_bbox, filename, None)

    region = ee.Geometry.Rectangle(tile_bbox)
    download_url = image.getDownloadURL(
        {
            "name": filename.stem,
            "region": region,
            "scale": 20,
            "crs": "EPSG:4326",
            "filePerBand": False,
            "format": "GEO_TIFF",
        }
    )
    response = requests.get(download_url, stream=True, timeout=900)
    response.raise_for_status()
    temporary = filename.with_suffix(".download")
    with temporary.open("wb") as output:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                output.write(chunk)
    content_type = response.headers.get("content-type", "").lower()
    if zipfile.is_zipfile(temporary) or "zip" in content_type:
        with zipfile.ZipFile(temporary) as archive:
            tif_names = [
                name for name in archive.namelist()
                if name.lower().endswith((".tif", ".tiff"))
            ]
            if len(tif_names) != 1:
                raise RuntimeError(f"Expected one GeoTIFF in GEE archive, found: {tif_names}")
            with archive.open(tif_names[0]) as source, filename.open("wb") as target:
                target.write(source.read())
        temporary.unlink()
    else:
        temporary.replace(filename)
    with filename.open("rb") as stream:
        if stream.read(4) not in (b"II*\x00", b"MM\x00*"):
            raise RuntimeError(f"GEE output is not a GeoTIFF: {filename}")
    return asset_record(phase, config, tile_id, tile_bbox, filename, None)


def asset_record(
    phase: str,
    config: dict,
    tile_id: str,
    tile_bbox: list[float],
    filename: Path,
    scene_count: int | None,
) -> dict:
    return {
        "phase": phase,
        "phase_label": config["label"],
        "tile_id": tile_id,
        "path": filename.relative_to(ROOT).as_posix(),
        "source": "Google Earth Engine / COPERNICUS/S2_SR_HARMONIZED",
        "date_start": config["start"],
        "date_end_exclusive": config["end"],
        "scene_count_before_composite": scene_count,
        "bands": BANDS,
        "resolution_m": 20,
        "crs": "EPSG:4326",
        "bbox": tile_bbox,
        "coverage_role": "complete_dixie_fire_mtbs_bbox_grid_tile",
        "byte_size": filename.stat().st_size,
    }


def download_phase_image(
    phase: str, config: dict, max_cloud: float
) -> tuple[ee.Image, dict, dict]:
    collection = sentinel_collection(config["start"], config["end"], max_cloud)
    tile_counts = {}
    selected_ids = {}
    for tile in MGRS_TILES:
        tile_collection = collection.filter(ee.Filter.eq("MGRS_TILE", tile))
        count = tile_collection.size().getInfo()
        tile_counts[tile] = count
        if count:
            ids = tile_collection.sort("CLOUDY_PIXEL_PERCENTAGE").aggregate_array(
                "system:id"
            ).getInfo()
            selected_ids[tile] = ids[0]
    if len(selected_ids) != len(MGRS_TILES):
        missing = [tile for tile in MGRS_TILES if not tile_counts[tile]]
        raise RuntimeError(f"Missing Sentinel-2 coverage for {phase}: {missing}")

    # Resolve IDs first, then build a small fixed-image mosaic. This avoids
    # sending the full filtered/mapped collection expression to GEE.
    image = ee.ImageCollection.fromImages(
        [ee.Image(selected_ids[tile]).select(BANDS) for tile in MGRS_TILES]
    ).mosaic().toInt16()
    return image, tile_counts, selected_ids


def download_phase(phase: str, config: dict, max_cloud: float) -> list[dict]:
    image, tile_counts, selected_ids = download_phase_image(phase, config, max_cloud)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for tile_id, tile_bbox in grid_regions():
        record = download_one_tile(phase, config, image, tile_id, tile_bbox)
        record["source_scene_counts_by_mgrs_tile"] = tile_counts
        record["selected_scene_ids_by_mgrs_tile"] = selected_ids
        records.append(record)
    return records


def main() -> int:
    args = parse_args()
    initialize(args.project)
    assets = []
    for phase, config in PHASES.items():
        assets.extend(download_phase(phase, config, args.max_cloud))
    manifest = {
        "schema_version": "fire.imagery.gee-geotiff-manifest.v0.1",
        "event_id": "dixie_fire_2021",
        "source": "Google Earth Engine",
        "collection": "COPERNICUS/S2_SR_HARMONIZED",
        "api_key_required": False,
        "project_id_configured_at_runtime": True,
        "aoi_bbox": AOI_BBOX,
        "aoi_crs": "EPSG:4326",
        "bands": BANDS,
        "composite_method": "median per phase after scene cloud filter, downloaded as a 4x3 grid",
        "grid_columns": GRID_COLUMNS,
        "grid_rows": GRID_ROWS,
        "mgrs_tiles": MGRS_TILES,
        "max_cloud_percentage": args.max_cloud,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assets": assets,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Downloaded {len(assets)} real GeoTIFF phase composites.")
    print(f"Manifest: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
