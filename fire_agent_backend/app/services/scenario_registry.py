from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.scenario import ScenarioDefinition


DEFAULT_SCENARIOS = [
    {
        "scenario_id": "muli_lier_village",
        "name": "Muli Li'er Village early fire decision scenario",
        "location_name": "Near Li'er Village, Yalongjiang Town, Muli County, Sichuan",
        "longitude": 101.269444,
        "latitude": 28.530278,
        "coordinate_precision": "exact",
        "duration_minutes": 120,
        "default_tick_interval_seconds": 2.0,
        "time_segments": [{"from_minute": 0, "to_minute": 120, "step_minutes": 5}],
        "profiles": {
            "region": "mountain_forest",
            "weather": "dry_windy",
            "fuel": "coniferous_mixed_forest",
            "road": "mountain_roads",
            "resource": "county_level",
            "sensor": "standard_four_layer",
        },
    },
    {
        "scenario_id": "pingyao_liujian_gou_early_replay",
        "name": "Pingyao Yanzhi Gou 2024-06-13 early fire decision replay",
        "location_name": "Yanzhi Gou area, Fengsheng Village, Zhukeng Township, Pingyao County, Shanxi",
        # Approximate geocoded point selected from public place descriptions until an official coordinate is verified.
        "longitude": 112.3136,
        "latitude": 37.0468,
        "coordinate_precision": "approximate_geocoded",
        "duration_minutes": 720,
        "default_tick_interval_seconds": 1.0,
        "time_segments": [
            {"from_minute": 0, "to_minute": 120, "step_minutes": 5},
            {"from_minute": 120, "to_minute": 720, "step_minutes": 15},
        ],
        "profiles": {
            "region": "north_china_hilly_forest",
            "weather": "dry_gusty",
            "fuel": "pine_shrub_mixed",
            "road": "rural_mountain_roads",
            "resource": "multi_county_response",
            "sensor": "standard_four_layer",
        },
    },
]


async def ensure_default_scenarios(db: AsyncSession) -> None:
    for item in DEFAULT_SCENARIOS:
        result = await db.execute(select(ScenarioDefinition).where(ScenarioDefinition.scenario_id == item["scenario_id"]))
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in item.items():
                setattr(existing, key, value)
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
