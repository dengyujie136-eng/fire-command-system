from __future__ import annotations

import heapq
import math
from bisect import bisect_right
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_NAME = "run_raster_fire_spread"
TOOL_VERSION = "1.3.0"

RASTER_FIRE_SPREAD_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Run a projected-grid wildfire spread simulation from hourly weather, "
            "a DEM GeoTIFF, and an ESA WorldCover-compatible GeoTIFF."
        ),
        "parameters": {
            "type": "object",
            "required": [
                "ignition_longitude",
                "ignition_latitude",
                "environment_timeline",
                "dem_path",
                "landcover_path",
            ],
            "properties": {
                "ignition_longitude": {"type": "number"},
                "ignition_latitude": {"type": "number"},
                "environment_timeline": {"type": "array", "minItems": 2},
                "dem_path": {"type": "string"},
                "landcover_path": {"type": "string"},
                "raster_resolution_m": {"type": "integer", "minimum": 30, "maximum": 300},
                "simulation_buffer_km": {"type": "number", "minimum": 5, "maximum": 80},
                "initial_radius_m": {"type": "number", "minimum": 15, "maximum": 500},
                "suppression_factor": {"type": "number", "minimum": 0, "maximum": 0.95},
                "wind_direction_convention": {
                    "type": "string",
                    "enum": ["meteorological_from", "spread_toward"],
                },
                "initial_fireline_geojson": {"type": "object"},
                "spread_rate_multiplier": {"type": "number", "minimum": 0.6, "maximum": 1.6},
                "wind_influence_multiplier": {"type": "number", "minimum": 0.5, "maximum": 1.5},
                "terrain_influence_multiplier": {"type": "number", "minimum": 0.5, "maximum": 1.5},
                "checkpoint_minutes": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 1},
                    "description": "Extra output checkpoints that do not alter weather validity intervals.",
                },
            },
        },
    },
}

# Relative spread factors for ESA WorldCover classes. Water, snow, built-up,
# and bare ground are barriers; wetlands remain slowly burnable.
LANDCOVER_FACTORS = {
    10: 0.92,
    20: 1.08,
    30: 1.20,
    40: 0.72,
    50: 0.0,
    60: 0.0,
    70: 0.0,
    80: 0.0,
    90: 0.24,
    95: 0.55,
    100: 0.35,
}

# Representative available fuel loads (kg/m2) used by the Byram fireline
# intensity proxy. These are model assumptions, not WorldCover attributes.
LANDCOVER_FUEL_LOAD_KG_M2 = {
    10: 1.80,
    20: 1.35,
    30: 0.72,
    40: 0.58,
    90: 0.42,
    95: 0.95,
    100: 0.48,
}
FUEL_HEAT_CONTENT_KJ_KG = 18_000.0

NEIGHBORS = (
    (-1, -1, math.sqrt(2.0), 315.0),
    (-1, 0, 1.0, 0.0),
    (-1, 1, math.sqrt(2.0), 45.0),
    (0, -1, 1.0, 270.0),
    (0, 1, 1.0, 90.0),
    (1, -1, math.sqrt(2.0), 225.0),
    (1, 0, 1.0, 180.0),
    (1, 1, math.sqrt(2.0), 135.0),
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _safe_data_path(value: str) -> Path:
    from app.core.config import get_settings

    root = get_settings().resolved_data_dir.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Raster path must be inside the configured data directory: {value}")
    if not path.is_file():
        raise ValueError(f"Raster file does not exist: {value}")
    return path


def _normalized_frames(
    frames: list[dict[str, Any]],
    convention: str,
) -> list[dict[str, Any]]:
    if len(frames) < 2:
        raise ValueError("environment_timeline requires at least two frames")
    normalized = []
    for frame in frames:
        direction = float(frame["wind_direction_deg"]) % 360.0
        if convention == "meteorological_from":
            direction = (direction + 180.0) % 360.0
        normalized.append(
            {
                "elapsed_minutes": int(frame["elapsed_minutes"]),
                "valid_at": frame.get("valid_at"),
                "temperature_c": float(frame["temperature_c"]),
                "humidity_percent": _clamp(frame["humidity_percent"], 0, 100),
                "wind_speed_m_s": _clamp(frame["wind_speed_m_s"], 0, 60),
                "wind_direction_deg": direction,
                "source_wind_direction_deg": float(frame["wind_direction_deg"]) % 360.0,
                "fuel_moisture": _clamp(frame["fuel_moisture"], 0.01, 0.8),
                "fire_weather_index": _clamp(frame["fire_weather_index"], 0, 100),
                "precipitation_mm_h": _clamp(frame.get("precipitation_mm_h", 0), 0, 200),
                "source": str(frame.get("source") or "agent_environment"),
            }
        )
    normalized.sort(key=lambda item: item["elapsed_minutes"])
    if normalized[0]["elapsed_minutes"] != 0:
        raise ValueError("the first environment frame must start at elapsed minute 0")
    if any(a["elapsed_minutes"] >= b["elapsed_minutes"] for a, b in zip(normalized, normalized[1:])):
        raise ValueError("environment frame elapsed minutes must be strictly increasing")
    return normalized


def _base_rate_m_min(
    frame: dict[str, Any],
    suppression_factor: float,
    spread_rate_multiplier: float = 1.0,
) -> float:
    humidity = _clamp((72.0 - frame["humidity_percent"]) / 55.0, 0.08, 1.2)
    moisture = _clamp((0.32 - frame["fuel_moisture"]) / 0.24, 0.08, 1.25)
    fwi = _clamp(frame["fire_weather_index"] / 20.0, 0.12, 1.8)
    temperature = _clamp((frame["temperature_c"] - 5.0) / 25.0, 0.35, 1.4)
    dryness = 0.28 * humidity + 0.31 * moisture + 0.29 * fwi + 0.12 * temperature
    rain = math.exp(-0.7 * frame["precipitation_mm_h"])
    return max(
        0.03,
        (0.28 + 1.35 * dryness)
        * rain
        * (1.0 - suppression_factor)
        * _clamp(spread_rate_multiplier, 0.6, 1.6),
    )


def _wind_factor(
    direction_deg: float,
    frame: dict[str, Any],
    wind_influence_multiplier: float = 1.0,
) -> float:
    ratio = _clamp(
        frame["wind_speed_m_s"] / 8.0 * _clamp(wind_influence_multiplier, 0.5, 1.5),
        0.0,
        2.0,
    )
    head = _clamp(1.0 + 0.58 * ratio, 1.0, 2.15)
    backing = _clamp(1.0 / (1.0 + 0.55 * ratio), 0.48, 1.0)
    major = (head + backing) / 2.0
    focus = (head - backing) / 2.0
    minor_sq = max(1e-6, major * major - focus * focus)
    relative = math.radians(direction_deg - frame["wind_direction_deg"])
    return _clamp(minor_sq / max(1e-6, major - focus * math.cos(relative)), 0.48, 2.15)


def _load_grid(
    dem_path: Path,
    landcover_path: Path,
    longitude: float,
    latitude: float,
    buffer_km: float,
    resolution_m: int,
) -> dict[str, Any]:
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds
    from rasterio.warp import transform
    from rasterio.windows import from_bounds as window_from_bounds

    with rasterio.open(dem_path) as dem_source:
        center_x, center_y = transform("EPSG:4326", dem_source.crs, [longitude], [latitude])
        radius = buffer_km * 1000.0
        bounds = (
            center_x[0] - radius,
            center_y[0] - radius,
            center_x[0] + radius,
            center_y[0] + radius,
        )
        clipped = (
            max(bounds[0], dem_source.bounds.left),
            max(bounds[1], dem_source.bounds.bottom),
            min(bounds[2], dem_source.bounds.right),
            min(bounds[3], dem_source.bounds.top),
        )
        width = max(2, int(math.ceil((clipped[2] - clipped[0]) / resolution_m)))
        height = max(2, int(math.ceil((clipped[3] - clipped[1]) / resolution_m)))
        window = window_from_bounds(*clipped, transform=dem_source.transform)
        elevation = dem_source.read(
            1,
            window=window,
            out_shape=(height, width),
            resampling=Resampling.bilinear,
            masked=True,
        ).astype("float64")
        crs = dem_source.crs
    target_transform = from_bounds(*clipped, width, height)
    with rasterio.open(landcover_path) as landcover_source:
        if landcover_source.crs != crs:
            raise ValueError("DEM and land-cover rasters must use the same CRS")
        landcover_window = window_from_bounds(*clipped, transform=landcover_source.transform)
        landcover = landcover_source.read(
            1,
            window=landcover_window,
            out_shape=(height, width),
            resampling=Resampling.nearest,
            masked=True,
        )
    elevation = np.ma.filled(elevation, np.nan)
    valid_elevation = np.isfinite(elevation)
    if not valid_elevation.any():
        raise ValueError("DEM window contains no valid cells")
    elevation[~valid_elevation] = float(np.nanmedian(elevation))
    landcover = np.ma.filled(landcover, 0).astype("int16")
    ignition_x, ignition_y = center_x[0], center_y[0]
    col = int((ignition_x - clipped[0]) / (clipped[2] - clipped[0]) * width)
    row = int((clipped[3] - ignition_y) / (clipped[3] - clipped[1]) * height)
    return {
        "elevation": elevation,
        "landcover": landcover,
        "transform": target_transform,
        "crs": crs,
        "resolution_m": abs(float(target_transform.a)),
        "ignition_row": max(0, min(height - 1, row)),
        "ignition_col": max(0, min(width - 1, col)),
        "bounds": clipped,
    }


def _initial_mask(grid: dict[str, Any], radius_m: float, initial_geojson: dict[str, Any] | None):
    import numpy as np

    elevation = grid["elevation"]
    if initial_geojson:
        from rasterio.features import rasterize
        from rasterio.warp import transform_geom

        geometry = initial_geojson.get("geometry", initial_geojson)
        projected = transform_geom("EPSG:4326", grid["crs"], geometry)
        return rasterize(
            [(projected, 1)],
            out_shape=elevation.shape,
            transform=grid["transform"],
            fill=0,
            dtype="uint8",
        ).astype(bool)
    rows, cols = np.indices(elevation.shape)
    distance = np.hypot(
        rows - grid["ignition_row"],
        cols - grid["ignition_col"],
    ) * grid["resolution_m"]
    return distance <= radius_m


def _boundary_cells(burned):
    import numpy as np

    interior = burned.copy()
    interior[0, :] = False
    interior[-1, :] = False
    interior[:, 0] = False
    interior[:, -1] = False
    interior[1:-1, 1:-1] &= (
        burned[:-2, 1:-1]
        & burned[2:, 1:-1]
        & burned[1:-1, :-2]
        & burned[1:-1, 2:]
    )
    return np.argwhere(burned & ~interior)


def _advance_interval(
    burned,
    grid: dict[str, Any],
    frame: dict[str, Any],
    duration_minutes: float,
    suppression_factor: float,
    spread_rate_multiplier: float = 1.0,
    wind_influence_multiplier: float = 1.0,
    terrain_influence_multiplier: float = 1.0,
):
    import numpy as np

    height, width = burned.shape
    arrival = np.full((height, width), np.inf, dtype="float64")
    heap: list[tuple[float, int, int]] = []
    for row, col in _boundary_cells(burned):
        arrival[row, col] = 0.0
        heapq.heappush(heap, (0.0, int(row), int(col)))
    base_rate = _base_rate_m_min(frame, suppression_factor, spread_rate_multiplier)
    elevation = grid["elevation"]
    landcover = grid["landcover"]
    resolution = grid["resolution_m"]
    while heap:
        elapsed, row, col = heapq.heappop(heap)
        if elapsed != arrival[row, col] or elapsed > duration_minutes:
            continue
        for row_delta, col_delta, distance_factor, direction in NEIGHBORS:
            target_row, target_col = row + row_delta, col + col_delta
            if not (0 <= target_row < height and 0 <= target_col < width):
                continue
            fuel_factor = LANDCOVER_FACTORS.get(int(landcover[target_row, target_col]), 0.0)
            if fuel_factor <= 0:
                continue
            distance_m = resolution * distance_factor
            slope_ratio = _clamp(
                (elevation[target_row, target_col] - elevation[row, col]) / distance_m,
                -0.5,
                0.5,
            )
            # Terrain is a bounded correction to the wind/fuel rate. A steep
            # local DEM step must not erase lateral or downhill propagation.
            slope_factor = _clamp(
                math.exp(0.35 * terrain_influence_multiplier * slope_ratio),
                0.78,
                1.28,
            )
            rate = base_rate * _wind_factor(direction, frame, wind_influence_multiplier) * slope_factor * fuel_factor
            candidate = elapsed + distance_m / max(0.03, rate)
            if candidate < arrival[target_row, target_col] and candidate <= duration_minutes:
                arrival[target_row, target_col] = candidate
                heapq.heappush(heap, (candidate, target_row, target_col))
    return burned | np.isfinite(arrival)


def _edge_arrival_minute(
    departure_minute: float,
    distance_m: float,
    direction: float,
    slope_factor: float,
    fuel_factor: float,
    frames: list[dict[str, Any]],
    frame_minutes: list[int],
    horizon_minute: float,
    suppression_factor: float,
    spread_rate_multiplier: float,
    wind_influence_multiplier: float,
) -> float:
    current = departure_minute
    remaining = distance_m
    while current < horizon_minute:
        frame_index = max(0, bisect_right(frame_minutes, current + 1e-9) - 1)
        frame = frames[frame_index]
        interval_end = (
            frame_minutes[frame_index + 1]
            if frame_index + 1 < len(frame_minutes)
            else horizon_minute
        )
        interval_end = min(float(interval_end), horizon_minute)
        rate = (
            _base_rate_m_min(frame, suppression_factor, spread_rate_multiplier)
            * _wind_factor(direction, frame, wind_influence_multiplier)
            * slope_factor
            * fuel_factor
        )
        available_minutes = max(0.0, interval_end - current)
        available_distance = rate * available_minutes
        if remaining <= available_distance:
            return current + remaining / max(rate, 0.03)
        remaining -= available_distance
        if interval_end <= current:
            break
        current = interval_end
    return math.inf


def _arrival_times(
    initial_burned,
    grid: dict[str, Any],
    frames: list[dict[str, Any]],
    suppression_factor: float,
    spread_rate_multiplier: float = 1.0,
    wind_influence_multiplier: float = 1.0,
    terrain_influence_multiplier: float = 1.0,
):
    """Calculate cumulative arrival times while switching weather at every frame."""
    import numpy as np

    height, width = initial_burned.shape
    arrival = np.full((height, width), np.inf, dtype="float64")
    heap: list[tuple[float, int, int]] = []
    for row, col in _boundary_cells(initial_burned):
        arrival[row, col] = 0.0
        heapq.heappush(heap, (0.0, int(row), int(col)))
    elevation = grid["elevation"]
    landcover = grid["landcover"]
    resolution = grid["resolution_m"]
    frame_minutes = [int(frame["elapsed_minutes"]) for frame in frames]
    horizon = float(frame_minutes[-1])
    while heap:
        elapsed, row, col = heapq.heappop(heap)
        if elapsed != arrival[row, col] or elapsed > horizon:
            continue
        for row_delta, col_delta, distance_factor, direction in NEIGHBORS:
            target_row, target_col = row + row_delta, col + col_delta
            if not (0 <= target_row < height and 0 <= target_col < width):
                continue
            fuel_factor = LANDCOVER_FACTORS.get(int(landcover[target_row, target_col]), 0.0)
            if fuel_factor <= 0:
                continue
            distance_m = resolution * distance_factor
            slope_ratio = _clamp(
                (elevation[target_row, target_col] - elevation[row, col]) / distance_m,
                -0.5,
                0.5,
            )
            slope_factor = _clamp(
                math.exp(0.35 * terrain_influence_multiplier * slope_ratio),
                0.78,
                1.28,
            )
            candidate = _edge_arrival_minute(
                elapsed,
                distance_m,
                direction,
                slope_factor,
                fuel_factor,
                frames,
                frame_minutes,
                horizon,
                suppression_factor,
                spread_rate_multiplier,
                wind_influence_multiplier,
            )
            if candidate < arrival[target_row, target_col]:
                arrival[target_row, target_col] = candidate
                heapq.heappush(heap, (candidate, target_row, target_col))
    arrival[initial_burned] = 0.0
    return arrival


def _sector_radii(grid: dict[str, Any], burned) -> list[float]:
    import numpy as np

    rows, cols = np.nonzero(burned)
    east = (cols - grid["ignition_col"]) * grid["resolution_m"] / 1000.0
    north = (grid["ignition_row"] - rows) * grid["resolution_m"] / 1000.0
    distance = np.hypot(east, north)
    direction = np.degrees(np.arctan2(east, north)) % 360.0
    radii = [0.005] * 72
    for angle, radius in zip(direction.tolist(), distance.tolist()):
        index = round(angle / 5.0) % 72
        radii[index] = max(radii[index], radius)
    for index in range(72):
        if radii[index] > 0.005:
            continue
        neighbors = [radii[(index + offset) % 72] for offset in (-2, -1, 1, 2) if radii[(index + offset) % 72] > 0.005]
        if neighbors:
            radii[index] = sum(neighbors) / len(neighbors)
    return radii


def _sector_front_metrics(
    grid: dict[str, Any],
    burned,
    frame: dict[str, Any],
    suppression_factor: float,
    spread_rate_multiplier: float = 1.0,
    wind_influence_multiplier: float = 1.0,
    terrain_influence_multiplier: float = 1.0,
) -> tuple[list[float], list[float]]:
    import numpy as np

    radii = [0.005] * 72
    intensities = [0.0] * 72
    elevation = grid["elevation"]
    landcover = grid["landcover"]
    resolution = grid["resolution_m"]
    base_rate = _base_rate_m_min(frame, suppression_factor, spread_rate_multiplier)
    available_fraction = _clamp(1.0 - 1.4 * frame["fuel_moisture"], 0.2, 0.95)
    for row_value, col_value in _boundary_cells(burned):
        row, col = int(row_value), int(col_value)
        east_km = (col - grid["ignition_col"]) * resolution / 1000.0
        north_km = (grid["ignition_row"] - row) * resolution / 1000.0
        radius = math.hypot(east_km, north_km)
        direction = math.degrees(math.atan2(east_km, north_km)) % 360.0
        sector = round(direction / 5.0) % 72
        inward_row = row + int(np.sign(grid["ignition_row"] - row))
        inward_col = col + int(np.sign(grid["ignition_col"] - col))
        inward_row = max(0, min(elevation.shape[0] - 1, inward_row))
        inward_col = max(0, min(elevation.shape[1] - 1, inward_col))
        inward_distance = resolution * max(1.0, math.hypot(inward_row - row, inward_col - col))
        slope_ratio = _clamp(
            (elevation[row, col] - elevation[inward_row, inward_col]) / inward_distance,
            -0.5,
            0.5,
        )
        slope_factor = _clamp(
            math.exp(0.35 * terrain_influence_multiplier * slope_ratio),
            0.78,
            1.28,
        )
        cover_code = int(landcover[row, col])
        fuel_factor = LANDCOVER_FACTORS.get(cover_code, 0.0)
        rate_m_min = base_rate * _wind_factor(direction, frame, wind_influence_multiplier) * slope_factor * fuel_factor
        fuel_load = LANDCOVER_FUEL_LOAD_KG_M2.get(cover_code, 0.0) * available_fraction
        intensity_kw_m = FUEL_HEAT_CONTENT_KJ_KG * fuel_load * max(0.0, rate_m_min) / 60.0
        if radius >= radii[sector]:
            radii[sector] = radius
            intensities[sector] = intensity_kw_m
    for index in range(72):
        if radii[index] > 0.005:
            continue
        neighbors = [
            candidate
            for offset in (-2, -1, 1, 2)
            if (candidate := radii[(index + offset) % 72]) > 0.005
        ]
        intensity_neighbors = [
            intensities[(index + offset) % 72]
            for offset in (-2, -1, 1, 2)
            if radii[(index + offset) % 72] > 0.005
        ]
        if neighbors:
            radii[index] = sum(neighbors) / len(neighbors)
            intensities[index] = sum(intensity_neighbors) / len(intensity_neighbors)
    return radii, intensities


def _geometry(grid: dict[str, Any], burned) -> dict[str, Any]:
    from rasterio.features import shapes
    from rasterio.warp import transform_geom

    polygons = []
    for geometry, value in shapes(
        burned.astype("uint8"),
        mask=burned,
        transform=grid["transform"],
    ):
        if value == 1:
            transformed = transform_geom(grid["crs"], "EPSG:4326", geometry, precision=7)
            polygons.append(transformed["coordinates"])
    if not polygons:
        raise ValueError("the raster spread produced no burned geometry")
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def _direction_and_radius(grid: dict[str, Any], burned) -> tuple[float, float]:
    import numpy as np

    rows, cols = np.nonzero(burned)
    east = (cols - grid["ignition_col"]) * grid["resolution_m"] / 1000.0
    north = (grid["ignition_row"] - rows) * grid["resolution_m"] / 1000.0
    distance = np.hypot(east, north)
    farthest = int(np.argmax(distance))
    return float(np.degrees(np.arctan2(east[farthest], north[farthest])) % 360.0), float(distance[farthest])


def run_raster_fire_spread(
    ignition_longitude: float,
    ignition_latitude: float,
    environment_timeline: list[dict[str, Any]],
    dem_path: str,
    landcover_path: str,
    raster_resolution_m: int = 90,
    simulation_buffer_km: float = 25,
    initial_radius_m: float = 187.5,
    suppression_factor: float = 0,
    wind_direction_convention: str = "meteorological_from",
    initial_fireline_geojson: dict[str, Any] | None = None,
    spread_rate_multiplier: float = 1.0,
    wind_influence_multiplier: float = 1.0,
    terrain_influence_multiplier: float = 1.0,
    checkpoint_minutes: list[int] | None = None,
) -> dict[str, Any]:
    if wind_direction_convention not in {"meteorological_from", "spread_toward"}:
        raise ValueError("unsupported wind direction convention")
    frames = _normalized_frames(environment_timeline, wind_direction_convention)
    grid = _load_grid(
        _safe_data_path(dem_path),
        _safe_data_path(landcover_path),
        ignition_longitude,
        ignition_latitude,
        _clamp(simulation_buffer_km, 5, 80),
        int(_clamp(raster_resolution_m, 30, 300)),
    )
    initial_burned = _initial_mask(grid, _clamp(initial_radius_m, 15, 500), initial_fireline_geojson)
    arrival = _arrival_times(
        initial_burned,
        grid,
        frames,
        _clamp(suppression_factor, 0, 0.95),
        _clamp(spread_rate_multiplier, 0.6, 1.6),
        _clamp(wind_influence_multiplier, 0.5, 1.5),
        _clamp(terrain_influence_multiplier, 0.5, 1.5),
    )
    steps = []
    frame_minutes = [int(frame["elapsed_minutes"]) for frame in frames]
    horizon_minute = frame_minutes[-1]
    output_minutes = sorted(
        set(frame_minutes)
        | {
            int(minute)
            for minute in (checkpoint_minutes or [])
            if 0 < int(minute) <= horizon_minute
        }
    )
    for index, output_minute in enumerate(output_minutes):
        frame_index = max(0, bisect_right(frame_minutes, output_minute + 1e-9) - 1)
        frame = frames[frame_index]
        burned = initial_burned | (arrival <= output_minute)
        propagation_weather = None
        propagation_interval = None
        if index:
            previous_minute = output_minutes[index - 1]
            previous_frame_index = max(0, bisect_right(frame_minutes, previous_minute + 1e-9) - 1)
            propagation_weather = frames[previous_frame_index]
            duration = output_minute - previous_minute
            propagation_interval = {
                "from_minute": previous_minute,
                "to_minute": output_minute,
                "duration_minutes": duration,
            }
        direction, radius = _direction_and_radius(grid, burned)
        sector_radii, sector_intensities = _sector_front_metrics(
            grid,
            burned,
            frame,
            _clamp(suppression_factor, 0, 0.95),
            _clamp(spread_rate_multiplier, 0.6, 1.6),
            _clamp(wind_influence_multiplier, 0.5, 1.5),
            _clamp(terrain_influence_multiplier, 0.5, 1.5),
        )
        active_intensities = [value for value in sector_intensities if value > 0]
        area_km2 = float(burned.sum()) * grid["resolution_m"] ** 2 / 1_000_000.0
        properties = {
            "elapsed_minutes": output_minute,
            "elapsed_seconds": output_minute * 60,
            "area_km2": round(area_km2, 4),
            "radius_km": round(radius, 4),
            "spread_direction_deg": round(direction, 1),
            "engine": "raster_agent_tool",
            "dynamic_environment": True,
            "terrain_aware": True,
            "landcover_aware": True,
            "initial_state": "fireline" if initial_fireline_geojson else "ignition",
            "sector_radii_km": [round(value, 4) for value in sector_radii],
            "sector_fire_intensity_kw_m": [round(value, 1) for value in sector_intensities],
            "fire_intensity": {
                "mean_kw_m": round(sum(active_intensities) / max(1, len(active_intensities)), 1),
                "max_kw_m": round(max(active_intensities, default=0.0), 1),
                "method": "Byram_H_w_R_proxy",
                "heat_content_kj_kg": FUEL_HEAT_CONTENT_KJ_KG,
                "calibrated": any(
                    abs(value - 1.0) > 1e-9
                    for value in (
                        spread_rate_multiplier,
                        wind_influence_multiplier,
                        terrain_influence_multiplier,
                    )
                ),
            },
            "environment": frame,
            "weather_used_for_previous_interval": propagation_weather,
            "propagation_interval": propagation_interval,
            "landscape": {
                "source": "Copernicus DEM + ESA WorldCover",
                "is_simulated": False,
                "crs": str(grid["crs"]),
                "resolution_m": round(grid["resolution_m"], 2),
                "grid_shape": list(burned.shape),
                "burned_cell_count": int(burned.sum()),
            },
        }
        steps.append(
            {
                "elapsed_minutes": output_minute,
                "elapsed_seconds": output_minute * 60,
                "area_km2": round(area_km2, 4),
                "radius_km": round(radius, 4),
                "spread_direction_deg": round(direction, 1),
                "fireline_geojson": {
                    "type": "Feature",
                    "properties": properties,
                    "geometry": _geometry(grid, burned),
                },
            }
        )
    final = steps[-1]
    return {
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "engine": "raster_agent_tool",
        "input": {
            "ignition_point": {"longitude": ignition_longitude, "latitude": ignition_latitude},
            "environment_timeline": frames,
            "horizon_minutes": frames[-1]["elapsed_minutes"],
            "step_minutes": min(
                b["elapsed_minutes"] - a["elapsed_minutes"] for a, b in zip(frames, frames[1:])
            ),
            "timing_mode": "weather_updates",
            "weather_update_minutes": [frame["elapsed_minutes"] for frame in frames],
            "extra_checkpoint_minutes": sorted(
                minute for minute in output_minutes if minute not in set(frame_minutes)
            ),
            "terrain": {"suppression_factor": suppression_factor},
            "landscape": {
                "enabled": True,
                "terrain_aware": True,
                "landcover_aware": True,
                "source": "Copernicus DEM + ESA WorldCover",
                "crs": str(grid["crs"]),
                "resolution_m": grid["resolution_m"],
            },
            "wind_direction_convention": wind_direction_convention,
            "model_parameters": {
                "spread_rate_multiplier": round(_clamp(spread_rate_multiplier, 0.6, 1.6), 3),
                "wind_influence_multiplier": round(_clamp(wind_influence_multiplier, 0.5, 1.5), 3),
                "terrain_influence_multiplier": round(_clamp(terrain_influence_multiplier, 0.5, 1.5), 3),
            },
        },
        "steps": steps,
        "summary": {
            "final_area_km2": final["area_km2"],
            "max_radius_km": max(step["radius_km"] for step in steps),
            "spread_direction_deg": final["spread_direction_deg"],
            "environment_frame_count": len(frames),
            "weather_update_minutes": [frame["elapsed_minutes"] for frame in frames],
            "forecast_valid_until_minute": frames[-1]["elapsed_minutes"],
            "representative_update_interval_minutes": min(
                b["elapsed_minutes"] - a["elapsed_minutes"] for a, b in zip(frames, frames[1:])
            ),
            "timing_mode": "weather_updates",
            "initial_state": "fireline" if initial_fireline_geojson else "ignition",
            "terrain_aware": True,
            "landcover_aware": True,
            "landscape": {
                "source": "Copernicus DEM + ESA WorldCover",
                "is_simulated": False,
                "crs": str(grid["crs"]),
                "resolution_m": round(grid["resolution_m"], 2),
                "grid_shape": list(burned.shape),
            },
            "model": {
                "spread_model": "projected_grid_travel_time",
                "wind_model": "elliptical_directional_rate",
                "terrain_model": "bounded_signed_neighbor_slope_v2",
                "terrain_slope_factor_range": "0.78-1.28",
                "fuel_model": "ESA_WorldCover_barrier_and_rate_mapping",
                "front_update_model": "multi_source_dijkstra_per_weather_interval",
                "arrival_time_model": "continuous_edge_progress_across_weather_updates",
                "fire_intensity_model": "Byram_H_w_R_landcover_fuel_load_proxy",
                "wind_direction_contract": "normalized_to_direction_fire_is_pushed_toward",
                "calibration_parameters": "explicit_bounded_run_inputs",
            },
        },
    }
