from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SpreadIgnitionPoint(BaseModel):
    longitude: float
    latitude: float
    confidence: float = Field(default=0.95, ge=0, le=1)


class SpreadEnvironmentFrame(BaseModel):
    elapsed_minutes: int = Field(default=0, ge=0, le=1440)
    temperature_c: float = Field(ge=-30, le=65)
    humidity_percent: float = Field(ge=0, le=100)
    wind_speed_m_s: float = Field(ge=0, le=60)
    wind_direction_deg: float = Field(ge=0, lt=360)
    fuel_moisture: float = Field(ge=0.01, le=0.8)
    fire_weather_index: float = Field(ge=0, le=100)
    precipitation_mm_h: float = Field(default=0, ge=0, le=200)
    source: str = "agent_environment"


class SpreadTerrainContext(BaseModel):
    mean_slope_deg: float = Field(default=12, ge=0, le=70)
    aspect_deg: float = Field(default=0, ge=0, lt=360)
    upslope_direction_deg: float | None = Field(default=None, ge=0, lt=360)
    fuel_model: str = "mixed_forest"
    fuel_load_kg_m2: float = Field(default=1.4, ge=0.05, le=8)
    canopy_cover_percent: float = Field(default=55, ge=0, le=100)
    suppression_factor: float = Field(default=0, ge=0, le=0.95)


class SpreadLandscapeGrid(BaseModel):
    longitudes: list[float]
    latitudes: list[float]
    elevation_m: list[list[float]]
    landcover_codes: list[list[int]]
    landcover_labels: dict[str, str] = Field(default_factory=dict)
    source: str = "agent_landscape_grid"
    original_source: str | None = None
    classification_method: str | None = None
    scene_id: str | None = None
    is_simulated: bool = False


class SpreadRunRequest(BaseModel):
    horizon_minutes: int | None = Field(
        default=None,
        ge=1,
        le=1440,
        description=(
            "Optional legacy limit. The final environment frame or the next "
            "scenario weather update defines the normal forecast horizon."
        ),
    )
    step_minutes: int | None = Field(
        default=None,
        ge=1,
        le=120,
        description=(
            "Optional compatibility cadence. Fireline checkpoints follow "
            "environment-frame valid times."
        ),
    )
    prefer_forefire: bool = Field(
        default=False,
        description="Legacy compatibility field. The backend now uses the dynamic agent tool directly.",
    )
    ignition_point: SpreadIgnitionPoint | None = None
    input_source: str = "confirmed_fire_point"
    environment_timeline: list[SpreadEnvironmentFrame] = Field(default_factory=list)
    terrain: SpreadTerrainContext = Field(default_factory=SpreadTerrainContext)
    landscape: SpreadLandscapeGrid | None = None
    initial_radius_m: float = Field(default=30, ge=5, le=500)
    initial_fireline_geojson: dict[str, Any] | None = None
    continue_from_run_id: str | None = None
    run_mode: Literal[
        "initial_forecast",
        "rolling_forecast",
        "observation_corrected",
        "what_if",
    ] = "initial_forecast"
    initial_fireline_source: str = "ignition"
    raster_resolution_m: int = Field(default=90, ge=30, le=300)
    simulation_buffer_km: float = Field(default=25, ge=5, le=80)
    wind_direction_convention: Literal[
        "meteorological_from",
        "spread_toward",
    ] = "spread_toward"


class HistoricalSpreadRunRequest(BaseModel):
    start_at: datetime | None = None
    horizon_hours: int = Field(default=24, ge=1, le=168)
    raster_resolution_m: int = Field(default=90, ge=30, le=300)
    simulation_buffer_km: float = Field(default=25, ge=5, le=80)
    initial_radius_m: float = Field(default=187.5, ge=15, le=500)
    suppression_factor: float = Field(default=0, ge=0, le=0.95)
    hotspot_comparison_radius_km: float = Field(default=20, ge=1, le=100)
    spread_rate_multiplier: float = Field(default=1, ge=0.6, le=1.6)
    wind_influence_multiplier: float = Field(default=1, ge=0.5, le=1.5)
    terrain_influence_multiplier: float = Field(default=1, ge=0.5, le=1.5)
    wind_direction_convention: Literal[
        "meteorological_from",
        "spread_toward",
    ] = "meteorological_from"


class HistoricalCalibrationRequest(HistoricalSpreadRunRequest):
    horizon_hours: int = Field(
        default=24,
        ge=24,
        le=24,
        description="Fixed horizon providing 6, 12, and 24 hour FIRMS calibration checkpoints.",
    )


class SimulationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    event_id: str
    scenario_id: str
    status: str
    engine: str
    forefire_attempted: bool
    forefire_available: bool
    fallback_used: bool
    start_minute: int
    horizon_minutes: int
    step_minutes: int
    ignition_longitude: float
    ignition_latitude: float
    final_area_km2: float
    max_radius_km: float
    spread_direction_deg: float
    risk_level: str
    input_snapshot: dict[str, Any]
    result_summary: dict[str, Any]
    error_message: str
    created_at: datetime


class FireFrontStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_id: str
    run_id: str
    event_id: str
    time_minute: int
    elapsed_seconds: int
    area_km2: float
    radius_km: float
    spread_direction_deg: float
    fireline_geojson: dict[str, Any]
    created_at: datetime


class SpreadRunPayload(BaseModel):
    run: SimulationRunRead
    steps: list[FireFrontStepRead]
    geojson: dict[str, Any]


class SpreadEnvelope(BaseModel):
    ok: bool = True
    data: Any
