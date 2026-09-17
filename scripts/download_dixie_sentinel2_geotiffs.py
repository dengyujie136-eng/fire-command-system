"""Download real Sentinel-2 L2A GeoTIFF composites for the Dixie Fire AOI.

The Planetary Computer Data API returns a georeferenced multi-band GeoTIFF.
This script deliberately stores the source STAC item metadata next to every
download and refuses to keep an HTML/JSON error response as an image.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from osgeo import gdal, osr


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw" / "sentinel2" / "dixie_fire_2021" / "geotiff"
MANIFEST_PATH = ROOT / "data" / "manifests" / "dixie_fire_2021_sentinel2_geotiff.json"

AOI_BBOX = [-121.542701, 39.860961, -120.186653, 40.784350]
STAC_ITEM_URL = (
    "https://planetarycomputer.microsoft.com/api/stac/v1/collections/"
    "sentinel-2-l2a/items/{item_id}"
)
CROP_URL = "https://planetarycomputer.microsoft.com/api/data/v1/item/crop.tif"
BANDS = ["B02", "B03", "B04", "B08"]

# The six tiles used for the active event provide overlap across the UTM-zone
# boundary and cover the full MTBS fire perimeter in every phase.
ITEMS = {
    "pre": [
        "S2A_MSIL2A_20210708T184921_R113_T10TFK_20210709T151429",
        "S2A_MSIL2A_20210708T184921_R113_T10TFL_20210709T141512",
        "S2A_MSIL2A_20210708T184921_R113_T10TGK_20210709T133000",
        "S2A_MSIL2A_20210708T184921_R113_T10TGL_20210709T143314",
        "S2A_MSIL2A_20210708T184921_R113_T11TKE_20210709T150330",
        "S2A_MSIL2A_20210708T184921_R113_T11TKF_20210709T140045",
    ],
    "during": [
        "S2A_MSIL2A_20210718T184921_R113_T10TFK_20210719T082337",
        "S2A_MSIL2A_20210718T184921_R113_T10TFL_20210719T064532",
        "S2A_MSIL2A_20210718T184921_R113_T10TGK_20210719T070850",
        "S2A_MSIL2A_20210718T184921_R113_T10TGL_20210719T072313",
        "S2A_MSIL2A_20210718T184921_R113_T11TKE_20210719T071413",
        "S2A_MSIL2A_20210718T184921_R113_T11TKF_20210719T062744",
    ],
    "post": [
        "S2B_MSIL2A_20210921T184959_R113_T10TFK_20210922T121437",
        "S2B_MSIL2A_20210921T184959_R113_T10TFL_20210922T100915",
        "S2B_MSIL2A_20210921T184959_R113_T10TGK_20210922T120952",
        "S2B_MSIL2A_20210921T184959_R113_T10TGL_20210922T120443",
        "S2B_MSIL2A_20210921T184959_R113_T11TKE_20210922T104233",
        "S2B_MSIL2A_20210921T184959_R113_T11TKF_20210922T112448",
    ],
}


def request_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def tile_from_item(item_id: str) -> str:
    for part in item_id.split("_"):
        if part.startswith("T") and len(part) == 6:
            return part
    raise ValueError(f"MGRS tile not found in {item_id}")


def sign_asset(href: str) -> str:
    sign_url = "https://planetarycomputer.microsoft.com/api/sas/v1/sign?href=" + href
    signed = request_json(sign_url)
    return signed["href"]


def projected_aoi_bounds(epsg: int) -> tuple[float, float, float, float]:
    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    target = osr.SpatialReference()
    target.ImportFromEPSG(epsg)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(source, target)
    points = [
        transform.TransformPoint(AOI_BBOX[0], AOI_BBOX[1]),
        transform.TransformPoint(AOI_BBOX[2], AOI_BBOX[1]),
        transform.TransformPoint(AOI_BBOX[2], AOI_BBOX[3]),
        transform.TransformPoint(AOI_BBOX[0], AOI_BBOX[3]),
    ]
    return (
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )


def download_item(phase: str, item_id: str, stac: dict) -> dict:
    tile = tile_from_item(item_id)
    zone = tile[1:3]
    dst_crs = f"EPSG:326{zone}"
    filename = f"dixie_fire_2021_sentinel2_{phase}_{tile}_{item_id}.tif"
    path = OUT_DIR / filename
    part_path = path.with_suffix(".tif.part")
    metadata_path = path.with_suffix(".stac.json")

    if path.exists() and path.stat().st_size > 1024:
        data = path.read_bytes()[:4]
        if data in (b"II*\x00", b"MM\x00*"):
            print(f"[skip] {path.name}")
            return build_record(phase, tile, item_id, stac, path, dst_crs, url)

    source_bbox = stac["assets"]["B02"]["proj:bbox"]
    aoi_bounds = projected_aoi_bounds(int(dst_crs.rsplit("EPSG:", 1)[1]))
    clip_bounds = (
        max(source_bbox[0], aoi_bounds[0]),
        max(source_bbox[1], aoi_bounds[1]),
        min(source_bbox[2], aoi_bounds[2]),
        min(source_bbox[3], aoi_bounds[3]),
    )
    if clip_bounds[0] >= clip_bounds[2] or clip_bounds[1] >= clip_bounds[3]:
        raise ValueError(f"No AOI intersection for {item_id}: {clip_bounds}")

    source_uris = {band: stac["assets"][band]["href"] for band in BANDS}
    signed_paths = ["/vsicurl/" + sign_asset(source_uris[band]) for band in BANDS]
    print(f"[download] {phase} {tile} {item_id} bounds={clip_bounds}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vrt_path = path.with_suffix(".vrt")
    vrt = gdal.BuildVRT(
        str(vrt_path),
        signed_paths,
        options=gdal.BuildVRTOptions(
            separate=True,
            outputBounds=clip_bounds,
            srcNodata=0,
            VRTNodata=0,
            resampleAlg="nearest",
        ),
    )
    if vrt is None:
        raise RuntimeError(f"GDAL could not build a VRT for {item_id}")
    vrt = None
    translated = gdal.Translate(
        str(part_path),
        str(vrt_path),
        format="GTiff",
        creationOptions=[
            "TILED=YES",
            "COMPRESS=DEFLATE",
            "PREDICTOR=2",
            "BIGTIFF=IF_SAFER",
        ],
        noData=0,
    )
    if translated is None:
        raise RuntimeError(f"GDAL could not write GeoTIFF for {item_id}")
    translated = None
    if not part_path.exists() or part_path.stat().st_size <= 1024:
        raise RuntimeError(f"Empty GeoTIFF output for {item_id}")
    with part_path.open("rb") as output:
        if output.read(4) not in (b"II*\x00", b"MM\x00*"):
            raise RuntimeError(f"Output is not a GeoTIFF for {item_id}")
    os.replace(part_path, path)
    if vrt_path.exists():
        vrt_path.unlink()
    metadata_path.write_text(json.dumps(stac, ensure_ascii=False, indent=2), encoding="utf-8")
    return build_record(phase, tile, item_id, stac, path, dst_crs, clip_bounds, source_uris)


def build_record(
    phase: str,
    tile: str,
    item_id: str,
    stac: dict,
    path: Path,
    dst_crs: str,
    clip_bounds: tuple[float, float, float, float],
    source_uris: dict[str, str],
) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "phase": phase,
        "asset_id": item_id,
        "tile": tile,
        "source": "Microsoft Planetary Computer / Sentinel-2 L2A",
        "acquired_at": stac.get("properties", {}).get("datetime"),
        "cloud_cover": stac.get("properties", {}).get("eo:cloud_cover"),
        "path": path.relative_to(ROOT).as_posix(),
        "mime_type": "image/tiff; application=geotiff",
        "crs": dst_crs,
        "source_crs": stac.get("properties", {}).get("proj:epsg"),
        "bbox": stac.get("bbox"),
        "resolution_m": 10,
        "bands": BANDS,
        "coverage_role": "full_dixie_fire_aoi_tile",
        "aoi_bbox": AOI_BBOX,
        "byte_size": path.stat().st_size,
        "sha256": digest,
        "source_item_uri": STAC_ITEM_URL.format(item_id=item_id),
        "source_asset_uris": source_uris,
        "clip_bounds_projected": list(clip_bounds),
        "stac_metadata_path": path.with_suffix(".stac.json").relative_to(ROOT).as_posix(),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for phase, item_ids in ITEMS.items():
        for item_id in item_ids:
            stac = request_json(STAC_ITEM_URL.format(item_id=item_id))
            records.append(download_item(phase, item_id, stac))
            time.sleep(0.25)
    manifest = {
        "schema_version": "fire.imagery.geotiff-manifest.v0.1",
        "event_id": "dixie_fire_2021",
        "source": "Microsoft Planetary Computer STAC Data API",
        "api_key_required": False,
        "aoi_bbox": AOI_BBOX,
        "aoi_crs": "EPSG:4326",
        "bands": BANDS,
        "description": (
            "Real georeferenced Sentinel-2 L2A GeoTIFF composites clipped to "
            "the Dixie Fire MTBS bounding box. Pre/during/post imagery is "
            "covered by multiple MGRS tiles; previews are not used as inputs. "
            "The original MTBS perimeter remains available for validation."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assets": records,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] {len(records)} GeoTIFF assets; manifest={MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
