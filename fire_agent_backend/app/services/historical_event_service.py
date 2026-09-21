from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.historical_event import HistoricalFireEvent


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


CALIFORNIA_EVENT_SEEDS: list[dict[str, Any]] = [
    {
        "event_id": "dixie_fire_2021",
        "name": "Dixie Fire",
        "country": "United States",
        "region": "California",
        "bbox": {"west": -122.08, "south": 39.36, "east": -120.08, "north": 40.46, "crs": "EPSG:4326"},
        "centroid_longitude": -121.39,
        "centroid_latitude": 40.12,
        "started_at": _dt("2021-07-13T00:00:00"),
        "ended_at": _dt("2021-10-25T00:00:00"),
        "burned_area_km2": 3898.0,
        "duration_days": 104,
        "max_impact_area_km2": 3898.0,
        "losses": {"structures_destroyed": 1329, "fatalities": 1, "injuries": 3, "loss_source": "public incident summaries"},
        "data_availability": {
            "firms": True,
            "weather": True,
            "dem": True,
            "fuel": True,
            "burned_area": True,
            "goes_demo": False,
            "local_event_id": "dixie_fire_2021",
        },
        "environmental_data": {
            "firms": {"mode": "real_data", "endpoint": "/api/data/events/dixie_fire_2021/hotspots?aggregate=true"},
            "weather": {"mode": "real_data", "source": "NASA POWER", "endpoint": "/api/data/events/dixie_fire_2021/weather-hourly"},
            "dem": {"mode": "real_data", "source": "Copernicus DEM"},
            "land_cover": {"mode": "real_data", "source": "ESA WorldCover"},
            "fuel": {"mode": "model_derived", "source": "WorldCover simplified fuel mapping"},
            "burned_area": {"mode": "real_data", "source": "MTBS", "endpoint": "/api/data/events/dixie_fire_2021/burned-area?include_geometry=true"},
        },
        "model_data": {
            "spread": {"available": True, "mode": "model_result", "endpoint": "/api/events/{event_id}/spread-runs"},
            "risk": {"available": True, "mode": "model_result"},
            "route": {"available": True, "mode": "model_result"},
            "decision_report": {"available": True, "mode": "model_result"},
        },
        "source_url": "https://www.fire.ca.gov/incidents/2021/7/13/dixie-fire",
        "source_citation": "CAL FIRE incident summary, MTBS burned area products, FIRMS observations, NASA POWER weather.",
        "notes": "Primary supported historical event with local FIRMS, weather, DEM, fuel and burned-area products.",
    },
    {
        "event_id": "park_fire_2024",
        "name": "Park Fire",
        "country": "United States",
        "region": "California",
        "bbox": {"west": -122.25, "south": 39.65, "east": -120.65, "north": 40.65, "crs": "EPSG:4326"},
        "centroid_longitude": -121.52,
        "centroid_latitude": 40.02,
        "started_at": _dt("2024-07-24T00:00:00"),
        "ended_at": _dt("2024-09-26T00:00:00"),
        "burned_area_km2": 1738.6,
        "duration_days": 64,
        "max_impact_area_km2": 1738.6,
        "losses": {"structures_destroyed": 709, "fatalities": 0, "loss_source": "public incident summaries"},
        "data_availability": {"firms": False, "weather": False, "dem": False, "fuel": False, "burned_area": False, "local_event_id": None},
        "environmental_data": {},
        "model_data": {},
        "source_url": "https://www.fire.ca.gov/incidents/2024/7/24/park-fire",
        "source_citation": "CAL FIRE public incident summary. Local analytical products are not registered in this repository yet.",
        "notes": "Catalog metadata only; do not use as a local analysis source until data packages are registered.",
    },
    {
        "event_id": "caldor_fire_2021",
        "name": "Caldor Fire",
        "country": "United States",
        "region": "California",
        "bbox": {"west": -121.25, "south": 38.55, "east": -119.85, "north": 39.08, "crs": "EPSG:4326"},
        "centroid_longitude": -120.42,
        "centroid_latitude": 38.79,
        "started_at": _dt("2021-08-14T00:00:00"),
        "ended_at": _dt("2021-10-21T00:00:00"),
        "burned_area_km2": 897.7,
        "duration_days": 68,
        "max_impact_area_km2": 897.7,
        "losses": {"structures_destroyed": 1005, "fatalities": 0, "loss_source": "public incident summaries"},
        "data_availability": {"firms": False, "weather": False, "dem": False, "fuel": False, "burned_area": False, "local_event_id": None},
        "environmental_data": {},
        "model_data": {},
        "source_url": "https://www.fire.ca.gov/incidents/2021/8/14/caldor-fire",
        "source_citation": "CAL FIRE public incident summary. Local analytical products are not registered in this repository yet.",
        "notes": "Catalog metadata only.",
    },
    {
        "event_id": "mosquito_fire_2022",
        "name": "Mosquito Fire",
        "country": "United States",
        "region": "California",
        "bbox": {"west": -121.22, "south": 38.87, "east": -120.42, "north": 39.25, "crs": "EPSG:4326"},
        "centroid_longitude": -120.78,
        "centroid_latitude": 39.02,
        "started_at": _dt("2022-09-06T00:00:00"),
        "ended_at": _dt("2022-10-27T00:00:00"),
        "burned_area_km2": 310.8,
        "duration_days": 51,
        "max_impact_area_km2": 310.8,
        "losses": {"structures_destroyed": 78, "fatalities": 0, "loss_source": "public incident summaries"},
        "data_availability": {"firms": False, "weather": False, "dem": False, "fuel": False, "burned_area": False, "local_event_id": None},
        "environmental_data": {},
        "model_data": {},
        "source_url": "https://www.fire.ca.gov/incidents/2022/9/6/mosquito-fire",
        "source_citation": "CAL FIRE public incident summary. Local analytical products are not registered in this repository yet.",
        "notes": "Catalog metadata only.",
    },
]


async def ensure_historical_event_seeds(db: AsyncSession) -> None:
    for item in CALIFORNIA_EVENT_SEEDS:
        result = await db.execute(select(HistoricalFireEvent).where(HistoricalFireEvent.event_id == item["event_id"]))
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in item.items():
                setattr(existing, key, value)
        else:
            db.add(HistoricalFireEvent(**item))
    await db.commit()


async def get_historical_event(db: AsyncSession, event_id: str) -> HistoricalFireEvent:
    await ensure_historical_event_seeds(db)
    result = await db.execute(select(HistoricalFireEvent).where(HistoricalFireEvent.event_id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise AppError(f"Historical fire event not found: {event_id}", code="historical_event_not_found", status_code=404)
    return event


async def query_historical_events(
    db: AsyncSession,
    *,
    country: str = "United States",
    region: str = "California",
    last_years: int = 5,
    sort_by: str = "burned_area_km2",
    limit: int = 5,
    now: datetime | None = None,
) -> dict[str, Any]:
    await ensure_historical_event_seeds(db)
    current = now or datetime.now(timezone.utc)
    start_year = current.year - last_years
    sort_column = {
        "burned_area": HistoricalFireEvent.burned_area_km2,
        "burned_area_km2": HistoricalFireEvent.burned_area_km2,
        "duration": HistoricalFireEvent.duration_days,
        "duration_days": HistoricalFireEvent.duration_days,
        "max_impact": HistoricalFireEvent.max_impact_area_km2,
        "max_impact_area_km2": HistoricalFireEvent.max_impact_area_km2,
    }.get(sort_by, HistoricalFireEvent.burned_area_km2)
    stmt = (
        select(HistoricalFireEvent)
        .where(func.lower(HistoricalFireEvent.country) == country.lower())
        .where(func.lower(HistoricalFireEvent.region) == region.lower())
        .where(func.extract("year", HistoricalFireEvent.started_at) >= start_year)
        .order_by(sort_column.desc().nullslast(), HistoricalFireEvent.started_at.desc())
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return {
        "query": {
            "country": country,
            "region": region,
            "last_years": last_years,
            "start_year_inclusive": start_year,
            "sort_by": sort_by,
            "limit": limit,
        },
        "retrieval_mode": "deterministic_historical_event_database",
        "llm_required": False,
        "catalog_scope": "California historical wildfire seeds; only Dixie Fire currently has local analysis data packages.",
        "events": rows,
    }
