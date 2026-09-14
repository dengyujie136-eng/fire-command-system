from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db


router = APIRouter(prefix="/data-agent", tags=["data-agent"])

DATASET_ALIASES: dict[str, list[str]] = {
    "hotspots": ["firms"],
    "burned_area": ["mtbs"],
    "weather": ["nasa_power_daily"],
    "weather_hourly": ["nasa_power_hourly"],
    "realtime_replay": ["firms"],
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


@router.get("/catalog/{event_id}")
async def data_catalog(event_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    manifests = await _manifest_rows(db, event_id)
    if not manifests:
        raise HTTPException(status_code=404, detail=f"No data manifest found: {event_id}")
    return {
        "schema_version": "fire.data-agent.catalog.v0.1",
        "event_id": event_id,
        "retrieval_mode": "deterministic_manifest_and_sql",
        "llm_required": False,
        "supported_needs": sorted(DATASET_ENDPOINTS),
        "manifests": manifests,
        "note": "Use POST /api/data-agent/resolve to select a task-specific data package.",
    }


@router.post("/resolve")
async def resolve_data_requirements(
    request: DataResolveRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    manifests = await _manifest_rows(db, request.event_id)
    if not manifests:
        raise HTTPException(status_code=404, detail=f"No data manifest found: {request.event_id}")

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

    selected = []
    for need in normalized_needs:
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
