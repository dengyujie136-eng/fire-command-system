from __future__ import annotations

import math
from typing import Any


TOOL_NAME = "run_dynamic_fire_spread"
TOOL_VERSION = "2.2.0"
SECTOR_COUNT = 72

FUEL_RATE_FACTORS = {
    "grass": 1.22,
    "shrub": 1.12,
    "conifer": 1.04,
    "mixed_forest": 0.96,
    "broadleaf": 0.82,
    "agriculture": 0.76,
    "urban_edge": 0.48,
}

LANDCOVER_RATE_FACTORS = {
    0: 0.03,
    1: 0.96,
    2: 1.2,
    3: 1.06,
    4: 0.78,
    10: 1.0,
    20: 1.14,
    30: 1.26,
    40: 0.8,
    50: 0.06,
    60: 0.14,
    70: 0.02,
    80: 0.01,
    90: 0.32,
    95: 0.68,
    100: 0.42,
}

LANDCOVER_LABELS = {
    0: "non_burnable",
    1: "mixed_forest",
    2: "shrub_grass",
    3: "conifer_forest",
    4: "agriculture",
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse",
    70: "snow_ice",
    80: "water",
    90: "wetland",
    95: "mangrove",
    100: "moss_lichen",
}

DYNAMIC_FIRE_SPREAD_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Run a time-varying wildfire spread simulation with optional DEM and land-cover grids. "
            "The caller must provide an ignition point and chronological weather/fuel-moisture frames. "
            "Use this tool again whenever observations or forecasts change."
        ),
        "parameters": {
            "type": "object",
            "required": [
                "ignition_longitude",
                "ignition_latitude",
                "environment_timeline",
            ],
            "properties": {
                "ignition_longitude": {"type": "number"},
                "ignition_latitude": {"type": "number"},
                "horizon_minutes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 1440,
                    "description": (
                        "Optional compatibility limit. When omitted, the final weather frame "
                        "defines the forecast horizon."
                    ),
                },
                "step_minutes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 120,
                    "description": (
                        "Optional legacy cadence metadata. Fireline outputs are emitted at "
                        "weather-frame valid times, while numerical integration remains at "
                        "five minutes or less."
                    ),
                },
                "environment_timeline": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": [
                            "elapsed_minutes",
                            "temperature_c",
                            "humidity_percent",
                            "wind_speed_m_s",
                            "wind_direction_deg",
                            "fuel_moisture",
                            "fire_weather_index",
                        ],
                        "properties": {
                            "elapsed_minutes": {"type": "integer", "minimum": 0},
                            "temperature_c": {"type": "number", "minimum": -30, "maximum": 65},
                            "humidity_percent": {"type": "number", "minimum": 0, "maximum": 100},
                            "wind_speed_m_s": {"type": "number", "minimum": 0, "maximum": 60},
                            "wind_direction_deg": {"type": "number", "minimum": 0, "exclusiveMaximum": 360},
                            "fuel_moisture": {"type": "number", "minimum": 0.01, "maximum": 0.8},
                            "fire_weather_index": {"type": "number", "minimum": 0, "maximum": 100},
                            "precipitation_mm_h": {"type": "number", "minimum": 0, "maximum": 200},
                            "source": {"type": "string"},
                        },
                    },
                },
                "terrain": {
                    "type": "object",
                    "properties": {
                        "mean_slope_deg": {"type": "number", "minimum": 0, "maximum": 70},
                        "aspect_deg": {"type": "number", "minimum": 0, "exclusiveMaximum": 360},
                        "upslope_direction_deg": {"type": "number", "minimum": 0, "exclusiveMaximum": 360},
                        "fuel_model": {
                            "type": "string",
                            "enum": sorted(FUEL_RATE_FACTORS),
                        },
                        "fuel_load_kg_m2": {"type": "number", "minimum": 0.05, "maximum": 8},
                        "canopy_cover_percent": {"type": "number", "minimum": 0, "maximum": 100},
                        "suppression_factor": {"type": "number", "minimum": 0, "maximum": 0.95},
                    },
                },
                "landscape": {
                    "type": "object",
                    "description": (
                        "Optional regular longitude/latitude grid containing elevation and land-cover "
                        "classes. Matrix rows follow latitudes and columns follow longitudes."
                    ),
                    "required": [
                        "longitudes",
                        "latitudes",
                        "elevation_m",
                        "landcover_codes",
                    ],
                    "properties": {
                        "longitudes": {
                            "type": "array",
                            "minItems": 2,
                            "items": {"type": "number"},
                        },
                        "latitudes": {
                            "type": "array",
                            "minItems": 2,
                            "items": {"type": "number"},
                        },
                        "elevation_m": {
                            "type": "array",
                            "minItems": 2,
                            "items": {
                                "type": "array",
                                "minItems": 2,
                                "items": {"type": "number"},
                            },
                        },
                        "landcover_codes": {
                            "type": "array",
                            "minItems": 2,
                            "items": {
                                "type": "array",
                                "minItems": 2,
                                "items": {"type": "integer"},
                            },
                        },
                        "landcover_labels": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "source": {"type": "string"},
                        "scene_id": {"type": "string"},
                        "is_simulated": {"type": "boolean"},
                    },
                },
                "initial_radius_m": {"type": "number", "minimum": 5, "maximum": 500},
                "initial_fireline_geojson": {
                    "type": "object",
                    "description": (
                        "Optional Polygon Feature or geometry used as the starting perimeter. "
                        "Provide this when continuing or correcting an earlier simulation."
                    ),
                },
            },
        },
    },
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _circular_delta(start_deg: float, end_deg: float) -> float:
    return (end_deg - start_deg + 180.0) % 360.0 - 180.0


def _normalize_environment_frame(frame: dict[str, Any]) -> dict[str, Any]:
    return {
        "elapsed_minutes": max(0, int(frame.get("elapsed_minutes", 0))),
        "temperature_c": _clamp(frame.get("temperature_c", 30.0), -30.0, 65.0),
        "humidity_percent": _clamp(frame.get("humidity_percent", 35.0), 0.0, 100.0),
        "wind_speed_m_s": _clamp(frame.get("wind_speed_m_s", 3.0), 0.0, 60.0),
        "wind_direction_deg": float(frame.get("wind_direction_deg", 0.0)) % 360.0,
        "fuel_moisture": _clamp(frame.get("fuel_moisture", 0.16), 0.01, 0.8),
        "fire_weather_index": _clamp(frame.get("fire_weather_index", 12.0), 0.0, 100.0),
        "precipitation_mm_h": _clamp(frame.get("precipitation_mm_h", 0.0), 0.0, 200.0),
        "source": str(frame.get("source") or "agent_environment"),
    }


def _prepare_timeline(
    environment_timeline: list[dict[str, Any]],
    horizon_minutes: int | None,
) -> tuple[list[dict[str, Any]], int, str]:
    if not environment_timeline:
        raise ValueError("environment_timeline must contain at least one environment frame")
    frames_by_minute = {
        normalized["elapsed_minutes"]: normalized
        for normalized in (_normalize_environment_frame(item) for item in environment_timeline)
    }
    frames = [frames_by_minute[key] for key in sorted(frames_by_minute)]
    if frames[0]["elapsed_minutes"] > 0:
        frames.insert(0, {**frames[0], "elapsed_minutes": 0})

    final_weather_minute = int(frames[-1]["elapsed_minutes"])
    if horizon_minutes is None:
        if final_weather_minute < 1:
            raise ValueError(
                "environment_timeline must include a future weather valid time "
                "when horizon_minutes is omitted"
            )
        horizon = final_weather_minute
        timing_mode = "weather_updates"
    else:
        requested_horizon = int(horizon_minutes)
        if not 1 <= requested_horizon <= 1440:
            raise ValueError("horizon_minutes must be between 1 and 1440")
        if final_weather_minute > requested_horizon:
            horizon = final_weather_minute
            timing_mode = "weather_updates_extended_horizon"
        else:
            horizon = requested_horizon
            timing_mode = (
                "weather_updates"
                if final_weather_minute == requested_horizon
                else "legacy_horizon"
            )
            if final_weather_minute < horizon:
                frames.append({**frames[-1], "elapsed_minutes": horizon})
    return frames, horizon, timing_mode


def _weather_update_times(
    frames: list[dict[str, Any]],
    horizon_minutes: int,
) -> list[int]:
    return sorted(
        {
            0,
            horizon_minutes,
            *(
                int(frame["elapsed_minutes"])
                for frame in frames
                if 0 <= int(frame["elapsed_minutes"]) <= horizon_minutes
            ),
        }
    )


def _representative_update_interval(
    weather_update_minutes: list[int],
    compatibility_step_minutes: int | None,
) -> int:
    if compatibility_step_minutes is not None:
        step = int(compatibility_step_minutes)
        if not 1 <= step <= 120:
            raise ValueError("step_minutes must be between 1 and 120")
    intervals = [
        following - current
        for current, following in zip(
            weather_update_minutes,
            weather_update_minutes[1:],
        )
        if following > current
    ]
    if intervals:
        return min(intervals)
    return int(compatibility_step_minutes or 1)


def _interpolate_environment(frames: list[dict[str, Any]], elapsed_minutes: float) -> dict[str, Any]:
    if elapsed_minutes <= frames[0]["elapsed_minutes"]:
        return dict(frames[0])
    if elapsed_minutes >= frames[-1]["elapsed_minutes"]:
        return dict(frames[-1])
    for start, end in zip(frames, frames[1:]):
        if start["elapsed_minutes"] <= elapsed_minutes <= end["elapsed_minutes"]:
            span = max(1.0, end["elapsed_minutes"] - start["elapsed_minutes"])
            ratio = (elapsed_minutes - start["elapsed_minutes"]) / span
            interpolated = {
                key: start[key] + (end[key] - start[key]) * ratio
                for key in (
                    "temperature_c",
                    "humidity_percent",
                    "wind_speed_m_s",
                    "fuel_moisture",
                    "fire_weather_index",
                    "precipitation_mm_h",
                )
            }
            interpolated["wind_direction_deg"] = (
                start["wind_direction_deg"]
                + _circular_delta(start["wind_direction_deg"], end["wind_direction_deg"]) * ratio
            ) % 360.0
            interpolated["elapsed_minutes"] = elapsed_minutes
            interpolated["source"] = (
                start["source"] if start["source"] == end["source"] else f"{start['source']}+{end['source']}"
            )
            return interpolated
    return dict(frames[-1])


def _fuel_rate_factor(fuel_model: str, fuel_load_kg_m2: float, canopy_cover_percent: float) -> float:
    """Return a bounded relative surface-fuel spread factor.

    This is deliberately a compact Rothermel-style surrogate.  The absolute
    rate is computed separately from weather; this function only describes
    how fuel continuity and loading change that rate.
    """
    model_factor = FUEL_RATE_FACTORS.get(fuel_model, FUEL_RATE_FACTORS["mixed_forest"])
    load_factor = _clamp(0.78 + fuel_load_kg_m2 * 0.14, 0.72, 1.32)
    canopy_factor = _clamp(0.94 + canopy_cover_percent / 700.0, 0.94, 1.08)
    return _clamp(model_factor * load_factor * canopy_factor, 0.35, 1.35)


def _normalize_landscape(landscape: dict[str, Any] | None) -> dict[str, Any] | None:
    if not landscape:
        return None

    longitudes = [float(value) for value in landscape.get("longitudes") or []]
    latitudes = [float(value) for value in landscape.get("latitudes") or []]
    if len(longitudes) < 2 or len(latitudes) < 2:
        raise ValueError("landscape must contain at least two longitudes and latitudes")
    if longitudes != sorted(longitudes) or latitudes != sorted(latitudes):
        raise ValueError("landscape longitude and latitude axes must be ascending")

    elevation_rows = landscape.get("elevation_m") or []
    landcover_rows = landscape.get("landcover_codes") or []
    if len(elevation_rows) != len(latitudes) or len(landcover_rows) != len(latitudes):
        raise ValueError("landscape matrix row count must match latitudes")

    elevation: list[list[float]] = []
    landcover: list[list[int]] = []
    for elevation_row, landcover_row in zip(elevation_rows, landcover_rows):
        if len(elevation_row) != len(longitudes) or len(landcover_row) != len(longitudes):
            raise ValueError("landscape matrix column count must match longitudes")
        normalized_elevation = [float(value) for value in elevation_row]
        if not all(math.isfinite(value) for value in normalized_elevation):
            raise ValueError("landscape elevation contains non-finite values")
        elevation.append(normalized_elevation)
        landcover.append([int(value) for value in landcover_row])

    longitude_step_m = abs(longitudes[1] - longitudes[0]) * 111_000.0 * math.cos(
        math.radians(sum(latitudes) / len(latitudes))
    )
    latitude_step_m = abs(latitudes[1] - latitudes[0]) * 111_000.0
    labels = {
        int(key): str(value)
        for key, value in (landscape.get("landcover_labels") or {}).items()
    }
    return {
        "longitudes": longitudes,
        "latitudes": latitudes,
        "elevation_m": elevation,
        "landcover_codes": landcover,
        "landcover_labels": labels,
        "source": str(landscape.get("source") or "agent_landscape_grid"),
        "original_source": landscape.get("original_source"),
        "classification_method": landscape.get("classification_method"),
        "scene_id": landscape.get("scene_id"),
        "is_simulated": bool(landscape.get("is_simulated", False)),
        "probe_distance_m": _clamp(
            min(longitude_step_m, latitude_step_m) * 0.75,
            30.0,
            250.0,
        ),
    }


def _axis_bracket(axis: list[float], value: float) -> tuple[int, int, float]:
    if value <= axis[0]:
        return 0, 0, 0.0
    if value >= axis[-1]:
        last = len(axis) - 1
        return last, last, 0.0
    low = 0
    high = len(axis) - 1
    while high - low > 1:
        middle = (low + high) // 2
        if axis[middle] <= value:
            low = middle
        else:
            high = middle
    span = max(1e-12, axis[high] - axis[low])
    return low, high, (value - axis[low]) / span


def _bilinear_sample(
    grid: list[list[float]],
    longitude_axis: list[float],
    latitude_axis: list[float],
    longitude: float,
    latitude: float,
) -> float:
    x0, x1, x_ratio = _axis_bracket(longitude_axis, longitude)
    y0, y1, y_ratio = _axis_bracket(latitude_axis, latitude)
    top = grid[y0][x0] + (grid[y0][x1] - grid[y0][x0]) * x_ratio
    bottom = grid[y1][x0] + (grid[y1][x1] - grid[y1][x0]) * x_ratio
    return top + (bottom - top) * y_ratio


def _nearest_sample(
    grid: list[list[int]],
    longitude_axis: list[float],
    latitude_axis: list[float],
    longitude: float,
    latitude: float,
) -> int:
    x0, x1, x_ratio = _axis_bracket(longitude_axis, longitude)
    y0, y1, y_ratio = _axis_bracket(latitude_axis, latitude)
    return int(grid[y1 if y_ratio >= 0.5 else y0][x1 if x_ratio >= 0.5 else x0])


def _offset_lon_lat(
    longitude: float,
    latitude: float,
    direction_deg: float,
    distance_m: float,
) -> tuple[float, float]:
    direction = math.radians(direction_deg)
    meters_per_degree_lat = 111_000.0
    meters_per_degree_lon = max(
        1.0,
        meters_per_degree_lat * math.cos(math.radians(latitude)),
    )
    return (
        longitude + math.sin(direction) * distance_m / meters_per_degree_lon,
        latitude + math.cos(direction) * distance_m / meters_per_degree_lat,
    )


def _landscape_context(
    ignition_longitude: float,
    ignition_latitude: float,
    direction_deg: float,
    radius_km: float,
    landscape: dict[str, Any],
) -> dict[str, Any]:
    front_longitude, front_latitude = _offset_lon_lat(
        ignition_longitude,
        ignition_latitude,
        direction_deg,
        radius_km * 1000.0,
    )
    probe_distance_m = float(landscape["probe_distance_m"])
    ahead_longitude, ahead_latitude = _offset_lon_lat(
        front_longitude,
        front_latitude,
        direction_deg,
        probe_distance_m,
    )
    axes = (landscape["longitudes"], landscape["latitudes"])
    front_elevation = _bilinear_sample(
        landscape["elevation_m"],
        *axes,
        front_longitude,
        front_latitude,
    )
    ahead_elevation = _bilinear_sample(
        landscape["elevation_m"],
        *axes,
        ahead_longitude,
        ahead_latitude,
    )
    slope_ratio = _clamp(
        (ahead_elevation - front_elevation) / probe_distance_m,
        -0.7,
        0.7,
    )
    slope_deg = math.degrees(math.atan(slope_ratio))
    landcover_code = _nearest_sample(
        landscape["landcover_codes"],
        *axes,
        ahead_longitude,
        ahead_latitude,
    )
    label = landscape["landcover_labels"].get(
        landcover_code,
        LANDCOVER_LABELS.get(landcover_code, f"class_{landcover_code}"),
    )
    return {
        "elevation_m": front_elevation,
        "ahead_elevation_m": ahead_elevation,
        "slope_ratio": slope_ratio,
        "slope_deg": slope_deg,
        # A signed slope correction is bounded so a DEM cannot dominate wind
        # and fuel effects.  At 20 degrees this is roughly 0.72 downhill to
        # 1.39 uphill, rather than the former 0.3 to 2.8 range.
        "slope_factor": _clamp(math.exp(0.9 * slope_ratio), 0.62, 1.65),
        "landcover_code": landcover_code,
        "landcover_label": label,
        "landcover_factor": LANDCOVER_RATE_FACTORS.get(landcover_code, 0.82),
    }


def _landscape_summary(landscape: dict[str, Any] | None) -> dict[str, Any]:
    if not landscape:
        return {
            "enabled": False,
            "terrain_aware": False,
            "landcover_aware": False,
            "source": "uniform_terrain_fallback",
        }
    codes = [
        value
        for row in landscape["landcover_codes"]
        for value in row
    ]
    code_counts = {
        str(code): codes.count(code)
        for code in sorted(set(codes))
    }
    elevations = [
        value
        for row in landscape["elevation_m"]
        for value in row
    ]
    return {
        "enabled": True,
        "terrain_aware": True,
        "landcover_aware": True,
        "source": landscape["source"],
        "original_source": landscape["original_source"],
        "classification_method": landscape["classification_method"],
        "scene_id": landscape["scene_id"],
        "is_simulated": landscape["is_simulated"],
        "grid_shape": [
            len(landscape["latitudes"]),
            len(landscape["longitudes"]),
        ],
        "bounds": {
            "west": landscape["longitudes"][0],
            "south": landscape["latitudes"][0],
            "east": landscape["longitudes"][-1],
            "north": landscape["latitudes"][-1],
        },
        "elevation_min_m": _round(min(elevations), 1),
        "elevation_max_m": _round(max(elevations), 1),
        "landcover_cell_counts": code_counts,
    }


def _front_landscape_summary(
    ignition_longitude: float,
    ignition_latitude: float,
    radii_km: list[float],
    landscape: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not landscape:
        return None
    samples = [
        _landscape_context(
            ignition_longitude,
            ignition_latitude,
            index * 360.0 / len(radii_km),
            radius,
            landscape,
        )
        for index, radius in enumerate(radii_km)
    ]
    counts: dict[str, int] = {}
    for sample in samples:
        label = str(sample["landcover_label"])
        counts[label] = counts.get(label, 0) + 1
    dominant_landcover = max(counts, key=counts.get)
    return {
        "mean_front_elevation_m": _round(
            sum(sample["elevation_m"] for sample in samples) / len(samples),
            1,
        ),
        "min_front_elevation_m": _round(
            min(sample["elevation_m"] for sample in samples),
            1,
        ),
        "max_front_elevation_m": _round(
            max(sample["elevation_m"] for sample in samples),
            1,
        ),
        "mean_forward_slope_deg": _round(
            sum(sample["slope_deg"] for sample in samples) / len(samples),
            2,
        ),
        "max_uphill_slope_deg": _round(
            max(sample["slope_deg"] for sample in samples),
            2,
        ),
        "max_downhill_slope_deg": _round(
            min(sample["slope_deg"] for sample in samples),
            2,
        ),
        "dominant_landcover": dominant_landcover,
        "landcover_sector_counts": counts,
        "landcover_sector_labels": [
            str(sample["landcover_label"]) for sample in samples
        ],
        "slope_sector_factors": [
            _round(sample["slope_factor"], 3) for sample in samples
        ],
    }


def _base_rate_m_min(environment: dict[str, Any], terrain: dict[str, Any]) -> float:
    humidity_dryness = _clamp((72.0 - environment["humidity_percent"]) / 55.0, 0.08, 1.2)
    moisture_dryness = _clamp((0.32 - environment["fuel_moisture"]) / 0.24, 0.08, 1.25)
    fwi_dryness = _clamp(environment["fire_weather_index"] / 20.0, 0.12, 1.8)
    temperature_factor = _clamp((environment["temperature_c"] - 5.0) / 25.0, 0.35, 1.4)
    dryness = (
        0.28 * humidity_dryness
        + 0.31 * moisture_dryness
        + 0.29 * fwi_dryness
        + 0.12 * temperature_factor
    )
    fuel_factor = _fuel_rate_factor(
        str(terrain.get("fuel_model") or "mixed_forest"),
        float(terrain.get("fuel_load_kg_m2", 1.4)),
        float(terrain.get("canopy_cover_percent", 55.0)),
    )
    rain_factor = math.exp(-0.7 * environment["precipitation_mm_h"])
    suppression_factor = 1.0 - _clamp(terrain.get("suppression_factor", 0.0), 0.0, 0.95)
    return max(
        0.08,
        # Typical surface-fire spread is expressed in metres/minute.  Wind
        # is handled by the ellipse below, so it is not counted a second time
        # in the base rate.
        (0.28 + 1.35 * dryness)
        * fuel_factor
        * rain_factor
        * suppression_factor,
    )


def _smooth_front_increment(
    previous: list[float],
    proposed: list[float],
) -> list[float]:
    """Diffuse only the new advance, preserving a monotonic perimeter."""
    count = len(previous)
    increments = [max(0.0, proposed[index] - previous[index]) for index in range(count)]
    return [
        previous[index]
        + 0.70 * increments[index]
        + 0.15 * increments[(index - 1) % count]
        + 0.15 * increments[(index + 1) % count]
        for index in range(count)
    ]


def _elliptical_wind_factor(
    direction_deg: float,
    wind_direction_deg: float,
    wind_speed_m_s: float,
) -> float:
    """Return a focus-based elliptical head/flank/backing wind multiplier.

    ``wind_direction_deg`` is the direction the wind pushes the fire toward,
    matching the existing project contract.  The ratio is intentionally
    capped because this tool models surface fire, not crown-fire spotting.
    """
    wind_ratio = _clamp(wind_speed_m_s / 8.0, 0.0, 2.0)
    head_factor = _clamp(1.0 + 0.58 * wind_ratio, 1.0, 2.15)
    backing_factor = _clamp(1.0 / (1.0 + 0.55 * wind_ratio), 0.48, 1.0)
    semi_major = (head_factor + backing_factor) / 2.0
    focal_offset = (head_factor - backing_factor) / 2.0
    semi_minor_squared = max(1e-6, semi_major * semi_major - focal_offset * focal_offset)
    relative = math.radians(direction_deg - wind_direction_deg)
    denominator = semi_major - focal_offset * math.cos(relative)
    return _clamp(semi_minor_squared / max(1e-6, denominator), 0.48, 2.15)


def _advance_front(
    radii_km: list[float],
    environment: dict[str, Any],
    terrain: dict[str, Any],
    delta_minutes: float,
    ignition_longitude: float,
    ignition_latitude: float,
    landscape: dict[str, Any] | None,
) -> list[float]:
    base_rate = _base_rate_m_min(environment, terrain)
    slope_deg = _clamp(terrain.get("mean_slope_deg", 12.0), 0.0, 70.0)
    aspect_deg = float(terrain.get("upslope_direction_deg", terrain.get("aspect_deg", 0.0))) % 360.0
    next_radii: list[float] = []
    for index, radius in enumerate(radii_km):
        direction_deg = index * 360.0 / len(radii_km)
        wind_factor = _elliptical_wind_factor(
            direction_deg,
            environment["wind_direction_deg"],
            environment["wind_speed_m_s"],
        )
        if landscape:
            local = _landscape_context(
                ignition_longitude,
                ignition_latitude,
                direction_deg,
                radius,
                landscape,
            )
            slope_factor = local["slope_factor"]
            landcover_factor = local["landcover_factor"]
        else:
            slope_alignment = math.cos(math.radians(direction_deg - aspect_deg))
            signed_slope_ratio = math.tan(math.radians(slope_deg)) * slope_alignment
            slope_factor = _clamp(math.exp(0.9 * signed_slope_ratio), 0.62, 1.65)
            landcover_factor = 1.0
        rate_m_min = base_rate * wind_factor * slope_factor * landcover_factor
        next_radii.append(radius + rate_m_min * delta_minutes / 1000.0)
    return _smooth_front_increment(radii_km, next_radii)


def _ring_from_radii(longitude: float, latitude: float, radii_km: list[float]) -> list[list[float]]:
    ring: list[list[float]] = []
    meters_per_degree_lat = 111_000.0
    meters_per_degree_lon = max(1.0, meters_per_degree_lat * math.cos(math.radians(latitude)))
    for index, radius_km in enumerate(radii_km):
        direction = math.radians(index * 360.0 / len(radii_km))
        east_m = math.sin(direction) * radius_km * 1000.0
        north_m = math.cos(direction) * radius_km * 1000.0
        ring.append(
            [
                _round(longitude + east_m / meters_per_degree_lon, 7),
                _round(latitude + north_m / meters_per_degree_lat, 7),
            ]
        )
    ring.append(ring[0])
    return ring


def _geometry_from_geojson(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("type") == "Feature":
        return value.get("geometry") or {}
    return value


def _radii_from_fireline(
    longitude: float,
    latitude: float,
    initial_fireline_geojson: dict[str, Any],
) -> list[float]:
    if initial_fireline_geojson.get("type") == "Feature":
        stored_radii = (initial_fireline_geojson.get("properties") or {}).get("sector_radii_km")
        if isinstance(stored_radii, list) and len(stored_radii) == SECTOR_COUNT:
            return [max(0.005, float(value)) for value in stored_radii]

    geometry = _geometry_from_geojson(initial_fireline_geojson)
    if geometry.get("type") != "Polygon":
        raise ValueError("initial_fireline_geojson must contain a Polygon geometry")
    coordinates = geometry.get("coordinates") or []
    if not coordinates or len(coordinates[0]) < 4:
        raise ValueError("initial_fireline_geojson polygon has no valid exterior ring")

    meters_per_degree_lat = 111_000.0
    meters_per_degree_lon = max(1.0, meters_per_degree_lat * math.cos(math.radians(latitude)))
    radii: list[float | None] = [None] * SECTOR_COUNT
    for point in coordinates[0]:
        if not isinstance(point, list) or len(point) < 2:
            continue
        east_km = (float(point[0]) - longitude) * meters_per_degree_lon / 1000.0
        north_km = (float(point[1]) - latitude) * meters_per_degree_lat / 1000.0
        radius = math.hypot(east_km, north_km)
        direction = math.degrees(math.atan2(east_km, north_km)) % 360.0
        index = round(direction / (360.0 / SECTOR_COUNT)) % SECTOR_COUNT
        radii[index] = max(radius, radii[index] or 0.0)

    known = [index for index, radius in enumerate(radii) if radius is not None]
    if len(known) < 3:
        raise ValueError("initial_fireline_geojson could not be converted into a radial fire front")
    for index, radius in enumerate(radii):
        if radius is not None:
            continue
        left = next(
            (offset for offset in range(1, SECTOR_COUNT) if radii[(index - offset) % SECTOR_COUNT] is not None),
            None,
        )
        right = next(
            (offset for offset in range(1, SECTOR_COUNT) if radii[(index + offset) % SECTOR_COUNT] is not None),
            None,
        )
        if left is None or right is None:
            radii[index] = 0.005
            continue
        left_radius = float(radii[(index - left) % SECTOR_COUNT])
        right_radius = float(radii[(index + right) % SECTOR_COUNT])
        radii[index] = left_radius + (right_radius - left_radius) * left / (left + right)
    return [max(0.005, float(radius)) for radius in radii]


def _area_km2(radii_km: list[float]) -> float:
    points = [
        (
            math.sin(math.radians(index * 360.0 / len(radii_km))) * radius,
            math.cos(math.radians(index * 360.0 / len(radii_km))) * radius,
        )
        for index, radius in enumerate(radii_km)
    ]
    area = 0.0
    for current, following in zip(points, points[1:] + points[:1]):
        area += current[0] * following[1] - following[0] * current[1]
    return abs(area) / 2.0


def _dominant_direction(radii_km: list[float], fallback_deg: float) -> float:
    baseline = min(radii_km)
    east = 0.0
    north = 0.0
    for index, radius in enumerate(radii_km):
        weight = max(0.0, radius - baseline)
        direction = math.radians(index * 360.0 / len(radii_km))
        east += math.sin(direction) * weight
        north += math.cos(direction) * weight
    if math.hypot(east, north) < 1e-8:
        return fallback_deg % 360.0
    return math.degrees(math.atan2(east, north)) % 360.0


def run_dynamic_fire_spread(
    ignition_longitude: float,
    ignition_latitude: float,
    environment_timeline: list[dict[str, Any]],
    horizon_minutes: int | None = None,
    step_minutes: int | None = None,
    terrain: dict[str, Any] | None = None,
    landscape: dict[str, Any] | None = None,
    initial_radius_m: float = 30.0,
    initial_fireline_geojson: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run dynamic fire spread for an agent without calling an external simulation API."""
    normalized_terrain = {
        "mean_slope_deg": _clamp((terrain or {}).get("mean_slope_deg", 12.0), 0.0, 70.0),
        "aspect_deg": float((terrain or {}).get("aspect_deg", 0.0)) % 360.0,
        "upslope_direction_deg": float(
            (terrain or {}).get("upslope_direction_deg", (terrain or {}).get("aspect_deg", 0.0))
        )
        % 360.0,
        "fuel_model": str((terrain or {}).get("fuel_model") or "mixed_forest"),
        "fuel_load_kg_m2": _clamp((terrain or {}).get("fuel_load_kg_m2", 1.4), 0.05, 8.0),
        "canopy_cover_percent": _clamp((terrain or {}).get("canopy_cover_percent", 55.0), 0.0, 100.0),
        "suppression_factor": _clamp((terrain or {}).get("suppression_factor", 0.0), 0.0, 0.95),
    }
    normalized_landscape = _normalize_landscape(landscape)
    landscape_input_summary = _landscape_summary(normalized_landscape)
    frames, horizon, timing_mode = _prepare_timeline(
        environment_timeline,
        horizon_minutes,
    )
    output_times = _weather_update_times(frames, horizon)
    representative_step = _representative_update_interval(
        output_times,
        step_minutes,
    )
    if initial_fireline_geojson:
        radii_km = _radii_from_fireline(
            ignition_longitude,
            ignition_latitude,
            initial_fireline_geojson,
        )
        initial_state = "fireline"
    else:
        radii_km = [max(0.005, float(initial_radius_m) / 1000.0)] * SECTOR_COUNT
        initial_state = "ignition"
    steps: list[dict[str, Any]] = []
    current_minute = 0.0
    integration_minutes = 5.0
    for output_minute in output_times:
        while current_minute < output_minute:
            delta = min(integration_minutes, output_minute - current_minute)
            environment = _interpolate_environment(frames, current_minute + delta / 2.0)
            radii_km = _advance_front(
                radii_km,
                environment,
                normalized_terrain,
                delta,
                ignition_longitude,
                ignition_latitude,
                normalized_landscape,
            )
            current_minute += delta

        environment = _interpolate_environment(frames, output_minute)
        area = _area_km2(radii_km)
        max_radius = max(radii_km)
        direction = _dominant_direction(radii_km, environment["wind_direction_deg"])
        ring = _ring_from_radii(ignition_longitude, ignition_latitude, radii_km)
        environment_payload = {
            key: _round(environment[key], 3)
            for key in (
                "temperature_c",
                "humidity_percent",
                "wind_speed_m_s",
                "wind_direction_deg",
                "fuel_moisture",
                "fire_weather_index",
                "precipitation_mm_h",
            )
        }
        environment_payload["source"] = environment["source"]
        front_landscape = _front_landscape_summary(
            ignition_longitude,
            ignition_latitude,
            radii_km,
            normalized_landscape,
        )
        steps.append(
            {
                "elapsed_minutes": output_minute,
                "elapsed_seconds": output_minute * 60,
                "area_km2": _round(area, 4),
                "radius_km": _round(max_radius, 4),
                "spread_direction_deg": _round(direction, 1),
                "environment": environment_payload,
                "fireline_geojson": {
                    "type": "Feature",
                    "properties": {
                        "elapsed_minutes": output_minute,
                        "elapsed_seconds": output_minute * 60,
                        "area_km2": _round(area, 4),
                        "radius_km": _round(max_radius, 4),
                        "spread_direction_deg": _round(direction, 1),
                        "engine": "dynamic_agent_tool",
                        "dynamic_environment": True,
                        "terrain_aware": bool(normalized_landscape),
                        "landcover_aware": bool(normalized_landscape),
                        "initial_state": initial_state,
                        "sector_radii_km": [_round(radius, 6) for radius in radii_km],
                        "environment": environment_payload,
                        "landscape": front_landscape,
                    },
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                },
            }
        )

    final = steps[-1]
    return {
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "engine": "dynamic_agent_tool",
        "dynamic_environment": True,
        "steps": steps,
        "summary": {
            "step_count": len(steps),
            "final_area_km2": final["area_km2"],
            "max_radius_km": max(item["radius_km"] for item in steps),
            "spread_direction_deg": final["spread_direction_deg"],
            "environment_frame_count": len(frames),
            "environment_sources": sorted({item["source"] for item in frames}),
            "integration_minutes": integration_minutes,
            "timing_mode": timing_mode,
            "weather_update_minutes": output_times,
            "forecast_valid_until_minute": horizon,
            "representative_update_interval_minutes": representative_step,
            "legacy_step_minutes_requested": step_minutes,
            "initial_state": initial_state,
            "terrain_aware": bool(normalized_landscape),
            "landcover_aware": bool(normalized_landscape),
            "landscape": landscape_input_summary,
            "model": {
                "spread_model": "rothermel_style_surface_rate",
                "wind_model": "focus_based_elliptical_head_flank_backing",
                "terrain_model": "bounded_signed_slope_correction",
                "fuel_model": "weather_moisture_fuel_load_landcover_factor",
                "front_update_model": "monotonic_increment_diffusion",
                "wind_direction_contract": "direction_fire_is_pushed_toward",
            },
        },
        "input": {
            "ignition_point": {
                "longitude": ignition_longitude,
                "latitude": ignition_latitude,
            },
            "horizon_minutes": horizon,
            "step_minutes": representative_step,
            "legacy_step_minutes_requested": step_minutes,
            "timing_mode": timing_mode,
            "weather_update_minutes": output_times,
            "environment_timeline": frames,
            "terrain": normalized_terrain,
            "landscape": landscape_input_summary,
            "initial_radius_m": float(initial_radius_m),
            "initial_fireline_geojson": initial_fireline_geojson,
        },
    }
