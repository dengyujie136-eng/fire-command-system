from datetime import datetime
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.schemas import TrustedIgnition
from app.schemas.spread import (
    SpreadEnvironmentFrame,
    SpreadIgnitionPoint,
    SpreadRunPayload,
    SpreadRunRequest,
)
from app.services.spread_service import create_spread_run


def _fuel_moisture(humidity: float, attributes: dict[str, Any]) -> float:
    value = attributes.get("fuel_moisture")
    if value is not None:
        return min(0.8, max(0.01, float(value)))
    return min(0.35, max(0.06, 0.07 + humidity / 650.0))


def _fire_weather_index(
    temperature: float,
    humidity: float,
    wind_speed: float,
    attributes: dict[str, Any],
) -> float:
    value = attributes.get("fire_weather_index")
    if value is not None:
        return min(100.0, max(0.0, float(value)))
    return min(
        100.0,
        max(0.0, temperature * 0.55 + wind_speed * 1.7 + (100 - humidity) * 0.18),
    )


async def load_hourly_weather(
    db: AsyncSession,
    *,
    event_id: str,
    observed_at: datetime,
    horizon_minutes: int,
) -> list[SpreadEnvironmentFrame]:
    limit = max(2, min(25, horizon_minutes // 60 + 1))
    result = await db.execute(
        text(
            """
            SELECT observed_at, temperature_c, relative_humidity_percent,
                   wind_speed_m_s, wind_direction_deg, precipitation_mm, attributes
            FROM weather_hourly_observations
            WHERE event_id = :event_id AND observed_at >= :observed_at
            ORDER BY observed_at
            LIMIT :limit
            """
        ),
        {"event_id": event_id, "observed_at": observed_at, "limit": limit},
    )
    rows = list(result.mappings().all())
    if not rows:
        result = await db.execute(
            text(
                """
                SELECT observed_at, temperature_c, relative_humidity_percent,
                       wind_speed_m_s, wind_direction_deg, precipitation_mm, attributes
                FROM weather_hourly_observations
                WHERE event_id = :event_id
                ORDER BY observed_at DESC
                LIMIT :limit
                """
            ),
            {"event_id": event_id, "limit": limit},
        )
        rows = list(reversed(result.mappings().all()))
    frames: list[SpreadEnvironmentFrame] = []
    for index, row in enumerate(rows):
        attributes = dict(row.get("attributes") or {})
        temperature = float(row["temperature_c"])
        humidity = float(row["relative_humidity_percent"])
        wind_speed = float(row["wind_speed_m_s"])
        frames.append(
            SpreadEnvironmentFrame(
                elapsed_minutes=min(horizon_minutes, index * 60),
                temperature_c=temperature,
                humidity_percent=humidity,
                wind_speed_m_s=wind_speed,
                wind_direction_deg=float(row["wind_direction_deg"]) % 360,
                fuel_moisture=_fuel_moisture(humidity, attributes),
                fire_weather_index=_fire_weather_index(
                    temperature, humidity, wind_speed, attributes
                ),
                precipitation_mm_h=max(0.0, float(row.get("precipitation_mm") or 0)),
                source="member_a_hourly_weather",
            )
        )
    if frames and frames[-1].elapsed_minutes < horizon_minutes:
        frames.append(
            frames[-1].model_copy(update={"elapsed_minutes": horizon_minutes})
        )
    return frames


class SpreadAdapter:
    """Translate a trusted visual ignition into member C's spread request."""

    async def run(
        self,
        db: AsyncSession,
        *,
        event_id: str,
        ignition: TrustedIgnition,
        horizon_minutes: int,
        weather_update_interval_minutes: int = 60,
        environment_overrides: Mapping[str, Any] | None = None,
        input_source: str | None = None,
        run_mode: str = "initial_forecast",
    ) -> tuple[SpreadRunPayload, list[SpreadEnvironmentFrame]]:
        weather = await load_hourly_weather(
            db,
            event_id=event_id,
            observed_at=ignition.observed_at,
            horizon_minutes=horizon_minutes,
        )
        if environment_overrides:
            source = str(
                environment_overrides.get("source")
                or "command_center_parameter_adjustment"
            )
            weather = [
                frame.model_copy(
                    update={
                        "temperature_c": float(environment_overrides.get("temperature_c", frame.temperature_c)),
                        "humidity_percent": float(environment_overrides.get("humidity_percent", frame.humidity_percent)),
                        "wind_speed_m_s": float(environment_overrides.get("wind_speed_m_s", frame.wind_speed_m_s)),
                        "wind_direction_deg": float(environment_overrides.get("wind_direction_deg", frame.wind_direction_deg)) % 360,
                        "fuel_moisture": float(environment_overrides.get("fuel_moisture", frame.fuel_moisture)),
                        "fire_weather_index": float(environment_overrides.get("fire_weather_index", frame.fire_weather_index)),
                        "precipitation_mm_h": float(environment_overrides.get("precipitation_mm_h", frame.precipitation_mm_h)),
                        "source": source,
                    }
                )
                for frame in weather
            ]
        interval = max(1, min(horizon_minutes, int(weather_update_interval_minutes)))
        update_times = list(range(0, horizon_minutes + 1, interval))
        if update_times[-1] != horizon_minutes:
            update_times.append(horizon_minutes)
        weather = [
            max(
                (frame for frame in weather if frame.elapsed_minutes <= elapsed_minutes),
                key=lambda frame: frame.elapsed_minutes,
                default=weather[0],
            ).model_copy(update={"elapsed_minutes": elapsed_minutes})
            for elapsed_minutes in update_times
        ]
        request = SpreadRunRequest(
            horizon_minutes=horizon_minutes,
            ignition_point=SpreadIgnitionPoint(
                longitude=ignition.longitude,
                latitude=ignition.latitude,
                confidence=ignition.confidence,
            ),
            input_source=input_source or f"visual_confirmation:{ignition.confirmation_id}",
            environment_timeline=weather,
            run_mode=run_mode,
        )
        data = await create_spread_run(db, event_id, request)
        return (
            SpreadRunPayload(
                run=data["run"],
                steps=data["steps"],
                geojson=data["geojson"],
            ),
            weather,
        )
