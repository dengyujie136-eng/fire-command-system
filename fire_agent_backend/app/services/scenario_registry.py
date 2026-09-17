from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.scenario import ScenarioDefinition


DEFAULT_SCENARIOS = [
    {
        "scenario_id": "dixie_fire_2021",
        "name": "Dixie Fire 2021 historical raster replay",
        "location_name": "Dixie Fire ignition area, California, USA",
        "longitude": -121.38241,
        "latitude": 39.87194,
        "coordinate_precision": "firms_candidate_exact",
        "duration_minutes": 72 * 60,
        "default_tick_interval_seconds": 2.0,
        "time_segments": [{"from_minute": 0, "to_minute": 72 * 60, "step_minutes": 60}],
        "profiles": {
            "region": "dixie_fire_2021",
            "weather": "nasa_power_hourly",
            "fuel": "esa_worldcover_2021",
            "terrain": "copernicus_dem_glo30",
            "data_source": "shared_handoff",
        },
    },
]


async def ensure_default_scenarios(db: AsyncSession) -> None:
    # Keep historical rows for referential integrity, but expose only the
    # active Dixie scenario to new events and the scenario selector.
    result = await db.execute(select(ScenarioDefinition))
    for existing in result.scalars().all():
        existing.enabled = existing.scenario_id == "dixie_fire_2021"
    for item in DEFAULT_SCENARIOS:
        result = await db.execute(select(ScenarioDefinition).where(ScenarioDefinition.scenario_id == item["scenario_id"]))
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in item.items():
                setattr(existing, key, value)
            existing.enabled = True
            continue
        db.add(ScenarioDefinition(**item))
    await db.commit()


async def list_scenarios(db: AsyncSession) -> list[ScenarioDefinition]:
    await ensure_default_scenarios(db)
    result = await db.execute(select(ScenarioDefinition).where(ScenarioDefinition.enabled.is_(True)).order_by(ScenarioDefinition.id))
    return list(result.scalars().all())


async def get_scenario_or_404(db: AsyncSession, scenario_id: str) -> ScenarioDefinition:
    await ensure_default_scenarios(db)
    result = await db.execute(
        select(ScenarioDefinition).where(
            ScenarioDefinition.scenario_id == scenario_id,
            ScenarioDefinition.enabled.is_(True),
        )
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise AppError(f"Scenario not found: {scenario_id}", code="scenario_not_found", status_code=404)
    return scenario
