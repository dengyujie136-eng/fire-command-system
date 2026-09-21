from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.historical_event import HistoricalEventQuery, HistoricalEventRead
from app.services.historical_event_service import get_historical_event, query_historical_events
from app.services.realtime_service import list_regions


router = APIRouter(prefix="/data-agent", tags=["data-agent"])

DATASET_ALIASES: dict[str, list[str]] = {
    "hotspots": ["firms"],
    "burned_area": ["mtbs"],
    "weather": ["nasa_power_daily"],
    "weather_hourly": ["nasa_power_hourly"],
    "realtime_replay": ["firms"],
    "realtime_hotspots": ["realtime_firms"],
    "realtime_image_demo": [],
    "realtime_firms_archive": [],
    "forefire_input": ["forefire_input_manifest"],
    "terrain": ["copernicus_dem"],
    "slope": ["copernicus_dem"],
    "aspect": ["copernicus_dem"],
    "fuel": ["worldcover"],
    "land_cover": ["worldcover"],
}

DATASET_ENDPOINTS: dict[str, dict[str, Any]] = {
    "hotspots": {
        "role": "FIRMS candidate hotspots and ten-minute clusters",
        "endpoint": "/api/data/events/{event_id}/hotspots?aggregate=true",
        "consumer": ["member_a", "member_b", "member_c"],
    },
    "burned_area": {
        "role": "MTBS final burned perimeter for validation",
        "endpoint": "/api/data/events/{event_id}/burned-area?include_geometry=true",
        "consumer": ["member_a", "member_c", "member_d"],
    },
    "weather": {
        "role": "NASA POWER daily temperature, humidity, wind and precipitation",
        "endpoint": "/api/data/events/{event_id}/weather",
        "consumer": ["member_a", "member_c", "member_d"],
    },
    "weather_hourly": {
        "role": "NASA POWER hourly temperature, humidity and wind input; precipitation may be missing in the source",
        "endpoint": "/api/data/events/{event_id}/weather-hourly",
        "consumer": ["member_a", "member_c", "member_d"],
    },
    "realtime_replay": {
        "role": "Ten-minute historical replay products derived from FIRMS hotspot clusters",
        "endpoint": "/api/data/events/{event_id}/realtime-replay?start_at={start_at}&end_at={end_at}",
        "consumer": ["member_a", "member_d"],
    },
    "realtime_hotspots": {
        "role": "Latest FIRMS NRT/VIIRS realtime candidate hotspots for a supported region",
        "endpoint": "/api/realtime/hotspots?region_id={region_id}",
        "status_endpoint": "/api/realtime/status?region_id={region_id}",
        "catalog_endpoint": "/api/data-agent/realtime-catalog",
        "consumer": ["member_a", "member_b", "member_d"],
    },
    "realtime_image_demo": {
        "role": "Pre-downloaded GOES-18 C07/C14 imagery processed as simulated ten-minute reception, with FDCC validation",
        "endpoint": "/api/realtime-demo/manifest",
        "detect_endpoint": "/api/realtime-demo/detect?slot_index={slot_index}",
        "preview_endpoint": "/api/realtime-demo/preview/{slot_index}",
        "consumer": ["member_a", "member_b", "member_d"],
    },
    "realtime_firms_archive": {
        "role": "Three-month FIRMS VIIRS historical hotspot archive used as simulated near-realtime daily reception",
        "endpoint": "/api/realtime-demo/firms-archive/manifest",
        "hotspots_endpoint": "/api/realtime-demo/firms-archive/hotspots?observed_on={date}",
        "consumer": ["member_a", "member_b", "member_d"],
    },
    "forefire_input": {
        "role": "Dixie Fire ForeFire input preparation manifest with deterministic ignition rule, raster paths and hourly weather",
        "path_suffix": "data/processed/forefire_input/dixie_fire_2021_forefire_input_manifest.json",
        "consumer": ["member_c"],
    },
    "terrain": {
        "role": "Copernicus DEM GeoTIFF",
        "path_suffix": "data/processed/dem/dixie_fire_2021_copernicus_dem_30m_utm10.tif",
        "consumer": ["member_c", "member_d"],
    },
    "slope": {
        "role": "DEM-derived slope in degrees",
        "path_suffix": "data/processed/dem/dixie_fire_2021_slope_deg_30m_utm10.tif",
        "consumer": ["member_c", "member_d"],
    },
    "aspect": {
        "role": "DEM-derived aspect in degrees",
        "path_suffix": "data/processed/dem/dixie_fire_2021_aspect_deg_30m_utm10.tif",
        "consumer": ["member_c", "member_d"],
    },
    "fuel": {
        "role": "Simplified fuel-class GeoTIFF derived from ESA WorldCover",
        "path_suffix": "data/processed/fuel/dixie_fire_2021_fuel_class_30m_utm10.tif",
        "consumer": ["member_c"],
    },
    "land_cover": {
        "role": "ESA WorldCover 2021 land-cover GeoTIFF",
        "path_suffix": "data/processed/fuel/dixie_fire_2021_worldcover_30m_utm10.tif",
        "consumer": ["member_a", "member_c", "member_d"],
    },
}


class DataResolveRequest(BaseModel):
    event_id: str = Field(default="dixie_fire_2021", min_length=1, max_length=80)
    region_id: str | None = Field(default=None, min_length=1, max_length=80)
    needs: list[str] = Field(default_factory=lambda: ["hotspots", "burned_area", "weather", "terrain", "fuel"])


def _aliases_for_need(need: str) -> list[str]:
    return DATASET_ALIASES.get(need, [])


async def _manifest_rows(db: AsyncSession, event_id: str) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            SELECT dataset_id, name, source_url, license, acquired_at,
                   spatial_extent, temporal_extent, source_crs, target_crs,
                   processing_steps, local_path
            FROM fire_data_manifests
            WHERE event_id = :event_id
            ORDER BY dataset_id
            """
        ),
        {"event_id": event_id},
    )
    return [dict(row) for row in result.mappings().all()]


async def _event_statistics(db: AsyncSession, event_id: str) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            SELECT
              (SELECT COUNT(*) FROM firms_hotspot_observations WHERE event_id = :event_id) AS firms_raw,
              (SELECT MIN(observed_at) FROM firms_hotspot_observations WHERE event_id = :event_id) AS firms_start,
              (SELECT MAX(observed_at) FROM firms_hotspot_observations WHERE event_id = :event_id) AS firms_end,
              (SELECT COUNT(*) FROM fire_hotspots WHERE event_id = :event_id) AS candidate_hotspots,
              (SELECT MIN(observed_at) FROM fire_hotspots WHERE event_id = :event_id) AS hotspots_start,
              (SELECT MAX(observed_at) FROM fire_hotspots WHERE event_id = :event_id) AS hotspots_end,
              (SELECT COUNT(*) FROM fire_hotspot_clusters WHERE event_id = :event_id) AS hotspot_clusters,
              (SELECT MIN(observed_at) FROM fire_hotspot_clusters WHERE event_id = :event_id) AS clusters_start,
              (SELECT MAX(observed_at) FROM fire_hotspot_clusters WHERE event_id = :event_id) AS clusters_end,
              (SELECT COUNT(*) FROM burned_areas WHERE event_id = :event_id) AS burned_areas,
              (SELECT MIN(assessment_date) FROM burned_areas WHERE event_id = :event_id) AS burned_area_start,
              (SELECT MAX(assessment_date) FROM burned_areas WHERE event_id = :event_id) AS burned_area_end,
              (SELECT COUNT(*) FROM weather_observations WHERE event_id = :event_id) AS weather_daily,
              (SELECT MIN(observed_on) FROM weather_observations WHERE event_id = :event_id) AS weather_daily_start,
              (SELECT MAX(observed_on) FROM weather_observations WHERE event_id = :event_id) AS weather_daily_end,
              (SELECT COUNT(*) FROM weather_hourly_observations WHERE event_id = :event_id) AS weather_hourly,
              (SELECT MIN(observed_at) FROM weather_hourly_observations WHERE event_id = :event_id) AS weather_hourly_start,
              (SELECT MAX(observed_at) FROM weather_hourly_observations WHERE event_id = :event_id) AS weather_hourly_end
            """
        ),
        {"event_id": event_id},
    )
    return dict(result.mappings().one())


def _file_status(path: Path) -> dict[str, Any]:
    available = path.is_file() and path.stat().st_size > 0
    return {
        "available": available,
        "file_count": 1 if available else 0,
        "size_bytes": path.stat().st_size if path.is_file() else 0,
    }


def _directory_status(path: Path) -> dict[str, Any]:
    files = [
        item
        for item in path.rglob("*")
        if item.is_file() and not item.name.startswith(".") and item.stat().st_size > 0
    ] if path.is_dir() else []
    return {
        "available": bool(files),
        "file_count": len(files),
        "size_bytes": sum(item.stat().st_size for item in files),
    }


def _repository_path_status(repository_path: str) -> dict[str, Any]:
    normalized = repository_path.replace("\\", "/")
    if normalized.startswith("data/"):
        normalized = normalized[5:]
    path = get_settings().resolved_data_dir / normalized
    return _directory_status(path) if path.is_dir() else _file_status(path)


def _local_asset_catalog() -> dict[str, dict[str, Any]]:
    data_dir = get_settings().resolved_data_dir
    assets = {
        "dem": ("data/processed/dem/dixie_fire_2021_copernicus_dem_30m_utm10.tif", _file_status(data_dir / "processed/dem/dixie_fire_2021_copernicus_dem_30m_utm10.tif")),
        "fuel": ("data/processed/fuel/dixie_fire_2021_fuel_class_30m_utm10.tif", _file_status(data_dir / "processed/fuel/dixie_fire_2021_fuel_class_30m_utm10.tif")),
        "worldcover": ("data/processed/fuel/dixie_fire_2021_worldcover_30m_utm10.tif", _file_status(data_dir / "processed/fuel/dixie_fire_2021_worldcover_30m_utm10.tif")),
        "forefire_input": ("data/processed/forefire_input/dixie_fire_2021_forefire_input_manifest.json", _file_status(data_dir / "processed/forefire_input/dixie_fire_2021_forefire_input_manifest.json")),
        "sentinel2": ("data/raw/sentinel2", _directory_status(data_dir / "raw/sentinel2")),
    }
    return {
        key: {"repository_path": repository_path, **status}
        for key, (repository_path, status) in assets.items()
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


async def _realtime_statistics(db: AsyncSession) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            SELECT
              (SELECT COUNT(*) FROM realtime_observations) AS observations,
              (SELECT MIN(observed_at) FROM realtime_observations) AS observations_start,
              (SELECT MAX(observed_at) FROM realtime_observations) AS observations_end,
              (SELECT COUNT(*) FROM realtime_hotspots) AS candidate_hotspots,
              (SELECT MIN(observed_at) FROM realtime_hotspots) AS hotspots_start,
              (SELECT MAX(observed_at) FROM realtime_hotspots) AS hotspots_end
            """
        )
    )
    return dict(result.mappings().one())


async def _latest_realtime_row(db: AsyncSession, region_id: str) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT ro.observation_id, ro.region_id, ro.source, ro.product,
                   ro.observed_at, ro.fetched_at, ro.source_file,
                   ro.metadata_json, COUNT(rh.id) AS hotspot_count
            FROM realtime_observations ro
            LEFT JOIN realtime_hotspots rh ON rh.observation_id = ro.observation_id
            WHERE ro.region_id = :region_id
            GROUP BY ro.id
            ORDER BY ro.fetched_at DESC
            LIMIT 1
            """
        ),
        {"region_id": region_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None



@router.get("/historical-events")
async def historical_events(
    country: str = "United States",
    region: str = "California",
    last_years: int = 5,
    sort_by: str = "burned_area_km2",
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Query the Historical Fire Event Database for supported California events."""
    result = await query_historical_events(
        db,
        country=country,
        region=region,
        last_years=last_years,
        sort_by=sort_by,
        limit=limit,
    )
    return {
        "schema_version": "fire.data-agent.historical-events.v0.1",
        **{key: value for key, value in result.items() if key != "events"},
        "events": [HistoricalEventRead.model_validate(item).model_dump(mode="json") for item in result["events"]],
    }


@router.post("/historical-events/query")
async def query_historical_events_from_text(
    request: HistoricalEventQuery,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await query_historical_events(
        db,
        country=request.country,
        region=request.region,
        last_years=request.last_years,
        sort_by=request.sort_by,
        limit=request.limit,
    )
    return {
        "schema_version": "fire.data-agent.historical-events.v0.1",
        "input_text": request.text,
        **{key: value for key, value in result.items() if key != "events"},
        "events": [HistoricalEventRead.model_validate(item).model_dump(mode="json") for item in result["events"]],
    }


@router.get("/historical-events/{event_id}")
async def historical_event_detail(event_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    event = await get_historical_event(db, event_id)
    return {
        "schema_version": "fire.data-agent.historical-event.v0.1",
        "retrieval_mode": "deterministic_historical_event_database",
        "llm_required": False,
        "data": HistoricalEventRead.model_validate(event).model_dump(mode="json"),
    }
@router.get("/catalog/{event_id}")
async def data_catalog(event_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    manifests = await _manifest_rows(db, event_id)
    if not manifests:
        raise HTTPException(status_code=404, detail=f"No data manifest found: {event_id}")
    manifests = [
        {
            **manifest,
            "local_file": _repository_path_status(manifest["local_path"])["available"],
            "local_file_status": _repository_path_status(manifest["local_path"]),
        }
        for manifest in manifests
    ]
    statistics = await _event_statistics(db, event_id)
    return {
        "schema_version": "fire.data-agent.catalog.v0.1",
        "event_id": event_id,
        "retrieval_mode": "deterministic_manifest_and_sql",
        "llm_required": False,
        "supported_needs": sorted(DATASET_ENDPOINTS),
        "manifests": manifests,
        "statistics": statistics,
        "local_assets": _local_asset_catalog(),
        "note": "Use POST /api/data-agent/resolve to select a task-specific data package.",
    }


@router.get("/realtime-catalog")
async def realtime_data_catalog(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Expose realtime regions and the latest locally persisted observation batch."""
    data_dir = get_settings().resolved_data_dir
    goes_manifest = _read_json(data_dir / "raw/realtime_demo/goes18/park_fire_2024/manifest.json")
    archive_manifest = _read_json(data_dir / "raw/realtime_demo/firms_archive/california_nevada_2025/manifest.json")
    items = []
    for region in list_regions():
        latest = await _latest_realtime_row(db, region["id"])
        items.append(
            {
                **region,
                "available": latest is not None,
                "latest_observation": latest,
                "hotspots_endpoint": f"/api/realtime/hotspots?region_id={region['id']}",
                "status_endpoint": f"/api/realtime/status?region_id={region['id']}",
                "sync_endpoint": "/api/realtime/sync",
            }
        )
    items.extend(
        [
            {
                "id": "park_fire_2024_goes18_demo",
                "label": "Park Fire 2024 GOES-18 影像检测演示",
                "source": "GOES-18 ABI C07/C14 + FDCC",
                "source_mode": "pre_downloaded_real_satellite_simulated_reception",
                "available": goes_manifest is not None,
                "local_file": goes_manifest is not None,
                "record_count": len(goes_manifest.get("slots", [])) if goes_manifest else 0,
                "time_range": [
                    goes_manifest["slots"][0]["observed_at"],
                    goes_manifest["slots"][-1]["observed_at"],
                ] if goes_manifest and goes_manifest.get("slots") else None,
                "manifest_endpoint": "/api/realtime-demo/manifest",
                "detect_endpoint": "/api/realtime-demo/detect?slot_index={slot_index}",
                "preview_endpoint": "/api/realtime-demo/preview/{slot_index}",
                "consumer": ["member_a", "member_b", "member_d"],
            },
            {
                "id": "firms_archive_california_nevada_2025",
                "label": "加州北部及内华达西部 FIRMS 三个月演示",
                "source": "FIRMS VIIRS_SNPP_SP",
                "source_mode": "pre_downloaded_historical_simulated_reception",
                "available": archive_manifest is not None,
                "local_file": archive_manifest is not None,
                "record_count": archive_manifest.get("unique_rows", 0) if archive_manifest else 0,
                "time_range": [
                    archive_manifest.get("start_date"),
                    archive_manifest.get("end_date"),
                ] if archive_manifest else None,
                "manifest_endpoint": "/api/realtime-demo/firms-archive/manifest",
                "hotspots_endpoint": "/api/realtime-demo/firms-archive/hotspots?observed_on={date}",
                "consumer": ["member_a", "member_b", "member_d"],
            },
        ]
    )
    return {
        "schema_version": "fire.data-agent.realtime-catalog.v0.1",
        "retrieval_mode": "deterministic_local_observation",
        "llm_required": False,
        "items": items,
        "statistics": await _realtime_statistics(db),
        "note": "The realtime catalog describes locally persisted FIRMS NRT/VIIRS candidate observations; it does not mark candidates as confirmed fires.",
    }


@router.post("/resolve")
async def resolve_data_requirements(
    request: DataResolveRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    manifests = await _manifest_rows(db, request.event_id)

    normalized_needs = []
    unknown_needs = []
    for raw_need in request.needs:
        need = raw_need.strip().lower().replace("-", "_")
        if need in DATASET_ENDPOINTS and need not in normalized_needs:
            normalized_needs.append(need)
        elif need:
            unknown_needs.append(raw_need)
    if unknown_needs:
        raise HTTPException(
            status_code=422,
            detail={"unknown_needs": unknown_needs, "supported_needs": sorted(DATASET_ENDPOINTS)},
        )
    if not manifests and any(need not in {"realtime_hotspots", "realtime_image_demo", "realtime_firms_archive"} for need in normalized_needs):
        raise HTTPException(status_code=404, detail=f"No data manifest found: {request.event_id}")

    selected = []
    for need in normalized_needs:
        if need == "realtime_image_demo":
            descriptor = dict(DATASET_ENDPOINTS[need])
            descriptor.update(
                {
                    "need": need,
                    "available": True,
                    "event_id": "park_fire_2024_demo",
                    "data_source_mode": "pre_downloaded_real_satellite_simulated_reception",
                    "manifests": [],
                }
            )
            selected.append(descriptor)
            continue
        if need == "realtime_firms_archive":
            descriptor = dict(DATASET_ENDPOINTS[need])
            descriptor.update({"need": need, "available": True, "manifests": []})
            selected.append(descriptor)
            continue
        if need == "realtime_hotspots":
            if not request.region_id:
                raise HTTPException(
                    status_code=422,
                    detail="region_id is required when needs contains realtime_hotspots",
                )
            try:
                region = next(item for item in list_regions() if item["id"] == request.region_id)
            except StopIteration as exc:
                raise HTTPException(status_code=422, detail=f"Unsupported realtime region: {request.region_id}") from exc
            latest = await _latest_realtime_row(db, request.region_id)
            descriptor = dict(DATASET_ENDPOINTS[need])
            descriptor.update(
                {
                    "need": need,
                    "region_id": request.region_id,
                    "region": region,
                    "available": latest is not None,
                    "latest_observation": latest,
                    "manifests": [],
                    "endpoint": descriptor["endpoint"].format(region_id=request.region_id),
                    "status_endpoint": descriptor["status_endpoint"].format(region_id=request.region_id),
                }
            )
            selected.append(descriptor)
            continue
        aliases = _aliases_for_need(need)
        matched = [
            manifest
            for manifest in manifests
            if any(alias in manifest["dataset_id"] for alias in aliases)
        ]
        descriptor = dict(DATASET_ENDPOINTS[need])
        descriptor["need"] = need
        descriptor["available"] = bool(matched) or "path_suffix" in descriptor
        descriptor["manifests"] = matched
        if "path_suffix" in descriptor:
            descriptor["repository_path"] = descriptor["path_suffix"]
            descriptor["container_path"] = f"/app/{descriptor['path_suffix']}"
        if "endpoint" in descriptor:
            descriptor["endpoint"] = descriptor["endpoint"].format(event_id=request.event_id)
        selected.append(descriptor)

    return {
        "schema_version": "fire.data-agent.resolve.v0.1",
        "event_id": request.event_id,
        "retrieval_mode": "deterministic_manifest_and_sql",
        "llm_required": False,
        "selected_needs": normalized_needs,
        "selected_datasets": selected,
        "handoff": {
            "member_b": "Use hotspots endpoint and imagery_refs for visual verification.",
            "member_c": "Use the forefire_input manifest, terrain, slope, aspect, fuel GeoTIFF paths and weather_hourly endpoint for ForeFire input preparation.",
            "member_d": "Use burned-area geometry, hotspots, weather and downstream spread outputs for impact and decision analysis.",
        },
        "limitations": [
            "WorldCover-derived fuel classes are a course-demo proxy, not a calibrated LANDFIRE fuel model.",
            "Raster files are local read-only artifacts; the returned paths are valid inside the fire-agent container and the shared repository.",
        ],
    }
