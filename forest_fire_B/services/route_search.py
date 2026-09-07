from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENVIRONMENT_DIR = PROJECT_ROOT / "data" / "environment"
KM_PER_DEGREE_LAT = 110.57669
KM_PER_DEGREE_LON_EQUATOR = 111.320


@dataclass(frozen=True)
class EnvironmentGrid:
    lons: np.ndarray
    lats: np.ndarray
    elevation: np.ndarray
    fuel: np.ndarray
    wind_u: float | None
    wind_v: float | None
    source: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchGrid:
    lons: np.ndarray
    lats: np.ndarray
    elevation: np.ndarray
    fuel_norm: np.ndarray
    slope_norm: np.ndarray
    road_bonus: np.ndarray
    environment_source: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CostSurface:
    fire: np.ndarray
    fire_core: np.ndarray
    downwind: np.ndarray
    fuel: np.ndarray
    slope: np.ndarray
    road: np.ndarray
    combined_risk: np.ndarray
    wind_vector: tuple[float, float]


@dataclass(frozen=True)
class RouteWeights:
    distance: float
    fire: float
    downwind: float
    fuel: float
    slope: float
    inside_fire: float
    road_bonus: float


ROUTE_WEIGHTS: dict[str, RouteWeights] = {
    "main_evacuation": RouteWeights(
        distance=1.0,
        fire=7.0,
        downwind=5.5,
        fuel=1.2,
        slope=2.7,
        inside_fire=14.0,
        road_bonus=0.22,
    ),
    "fire_rescue_approach": RouteWeights(
        distance=0.85,
        fire=3.3,
        downwind=3.8,
        fuel=0.8,
        slope=2.0,
        inside_fire=6.0,
        road_bonus=0.28,
    ),
    "safe_route": RouteWeights(
        distance=1.15,
        fire=12.5,
        downwind=9.0,
        fuel=1.9,
        slope=4.2,
        inside_fire=24.0,
        road_bonus=0.18,
    ),
    "safe": RouteWeights(
        distance=1.15,
        fire=12.0,
        downwind=8.0,
        fuel=1.7,
        slope=4.0,
        inside_fire=22.0,
        road_bonus=0.20,
    ),
    "medium": RouteWeights(
        distance=0.95,
        fire=6.0,
        downwind=4.8,
        fuel=1.1,
        slope=2.5,
        inside_fire=11.0,
        road_bonus=0.24,
    ),
    "danger": RouteWeights(
        distance=0.72,
        fire=1.9,
        downwind=1.8,
        fuel=0.5,
        slope=1.2,
        inside_fire=3.0,
        road_bonus=0.30,
    ),
}


def plan_emergency_routes(
    *,
    start: list[float],
    assembly: list[float],
    rescue_start: list[float],
    rescue_end: list[float],
    safe_end: list[float],
    fire_bbox: list[float],
    spread_direction: str,
    fire_geometry: dict[str, Any] | None = None,
    road_segments: list[dict[str, Any]] | None = None,
    environment_dir: str | Path | None = None,
) -> dict[str, Any]:
    env = load_environment_grid(environment_dir)
    points = [start, assembly, rescue_start, rescue_end, safe_end]
    grid = _build_search_grid(
        env=env,
        points=points,
        fire_bbox=fire_bbox,
        road_segments=road_segments or [],
    )
    surface = _build_cost_surface(
        grid=grid,
        env=env,
        fire_bbox=fire_bbox,
        spread_direction=spread_direction,
        fire_geometry=fire_geometry,
    )

    route_inputs = {
        "main_evacuation": (start, assembly),
        "fire_rescue_approach": (rescue_start, rescue_end),
        "safe_route": (start, safe_end),
    }
    routes = {
        route_id: _search_route(
            route_id=route_id,
            start=route_start,
            goal=route_goal,
            grid=grid,
            surface=surface,
            weights=ROUTE_WEIGHTS[route_id],
        )
        for route_id, (route_start, route_goal) in route_inputs.items()
    }

    return {
        "routes": routes,
        "diagnostics": _diagnostics(grid, surface, env),
        "warnings": list(grid.warnings),
    }


def plan_point_to_point_route_options(
    *,
    start: list[float],
    end: list[float],
    fire_bbox: list[float] | None = None,
    spread_direction: str = "north",
    fire_geometry: dict[str, Any] | None = None,
    environment_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    if fire_bbox is None:
        center = [(start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0]
        fire_bbox = [
            round(center[0] - 0.004, 6),
            round(center[1] - 0.004, 6),
            round(center[0] + 0.004, 6),
            round(center[1] + 0.004, 6),
        ]

    env = load_environment_grid(environment_dir)
    grid = _build_search_grid(env=env, points=[start, end], fire_bbox=fire_bbox, road_segments=[])
    surface = _build_cost_surface(
        grid=grid,
        env=env,
        fire_bbox=fire_bbox,
        spread_direction=spread_direction,
        fire_geometry=fire_geometry,
    )
    specs = [
        ("safe", "安全路径", "low", 18.0, "优先避开预测火场、下风向和陡坡区，适合作为稳妥通道。"),
        ("medium", "中等路径", "medium", 22.0, "在风险避让和行进距离之间折中，适合常规应急通行。"),
        ("danger", "危险路径", "high", 30.0, "以时间最短为主，可能贴近火场边缘，仅限紧急情况下复核使用。"),
    ]
    options = []
    for route_type, name, fallback_risk, speed_kmh, reason in specs:
        route = _search_route(
            route_id=route_type,
            start=start,
            goal=end,
            grid=grid,
            surface=surface,
            weights=ROUTE_WEIGHTS[route_type],
        )
        risk = route.get("risk") or fallback_risk
        if route_type == "danger":
            risk = "high"
        options.append(
            {
                "route_id": f"ROUTE-{route_type.upper()}",
                "id": f"ROUTE-{route_type.upper()}",
                "type": route_type,
                "name": name,
                "start": start,
                "end": end,
                "waypoints": route["coordinates"],
                "coordinates": route["coordinates"],
                "estimated_length_km": route["distance_km"],
                "distance_km": route["distance_km"],
                "estimated_time_minutes": round(route["distance_km"] / speed_kmh * 60, 1),
                "eta_min": round(route["distance_km"] / speed_kmh * 60, 1),
                "risk_level": risk,
                "risk": risk,
                "status": "planned",
                "reason": reason,
                "elevation_profile": route["elevation_profile"],
                "search_method": "astar_cost_surface",
                "diagnostics": route["diagnostics"],
            }
        )
    return options


def load_environment_grid(environment_dir: str | Path | None = None) -> EnvironmentGrid | None:
    base = _resolve_environment_dir(environment_dir)
    path = base / "final_input.nc"
    if not path.exists():
        return None
    try:
        import h5py
    except ImportError:
        return None

    try:
        with h5py.File(path, "r") as f:
            lats = np.asarray(f["lat"][()], dtype=float)
            lons = np.asarray(f["lon"][()], dtype=float)
            elevation = np.asarray(f["topography_z"][()], dtype=float)
            fuel = np.asarray(f["fuel_idx"][()], dtype=float)
            wind_u = _dataset_mean(f.get("windU"))
            wind_v = _dataset_mean(f.get("windV"))
    except Exception:
        return None

    if elevation.shape != (len(lats), len(lons)):
        return None
    if fuel.shape != (len(lats), len(lons)):
        fuel = np.zeros_like(elevation)

    if len(lats) > 1 and lats[0] > lats[-1]:
        lats = lats[::-1]
        elevation = elevation[::-1, :]
        fuel = fuel[::-1, :]
    if len(lons) > 1 and lons[0] > lons[-1]:
        lons = lons[::-1]
        elevation = elevation[:, ::-1]
        fuel = fuel[:, ::-1]

    elevation = _fill_invalid(elevation, fallback=0.0)
    fuel = _fill_invalid(fuel, fallback=0.0)
    return EnvironmentGrid(
        lons=lons,
        lats=lats,
        elevation=elevation,
        fuel=fuel,
        wind_u=wind_u,
        wind_v=wind_v,
        source=str(path),
    )


def _search_route(
    *,
    route_id: str,
    start: list[float],
    goal: list[float],
    grid: SearchGrid,
    surface: CostSurface,
    weights: RouteWeights,
) -> dict[str, Any]:
    start_idx = _point_to_index(start, grid)
    goal_idx = _point_to_index(goal, grid)
    path_indices, search_cost, visited = _astar(start_idx, goal_idx, grid, surface, weights)
    raw_coords = _indices_to_coordinates(path_indices, grid)
    if raw_coords:
        raw_coords[0] = _round_point(start)
        raw_coords[-1] = _round_point(goal)

    raw_elevations = [float(grid.elevation[row, col]) for row, col in path_indices]
    raw_distance = _polyline_distance_km(raw_coords)
    coordinates = _compress_path(raw_coords, path_indices)
    if coordinates:
        coordinates[0] = _round_point(start)
        coordinates[-1] = _round_point(goal)
    profile = _elevation_profile(raw_coords, raw_elevations)
    route_risks = [float(surface.combined_risk[row, col]) for row, col in path_indices]
    risk_stats = _risk_stats(route_risks)

    return {
        "id": route_id,
        "coordinates": coordinates,
        "distance_km": round(raw_distance, 3),
        "elevation_profile": profile,
        "risk": _risk_label_from_stats(risk_stats),
        "risk_score": risk_stats["average"],
        "max_risk_score": risk_stats["maximum"],
        "high_risk_share": risk_stats["high_share"],
        "diagnostics": {
            "search_method": "astar_cost_surface",
            "search_cost": round(search_cost, 3),
            "visited_nodes": int(visited),
            "raw_point_count": len(raw_coords),
            "display_point_count": len(coordinates),
            "average_risk_score": risk_stats["average"],
            "max_risk_score": risk_stats["maximum"],
            "high_risk_share": risk_stats["high_share"],
        },
    }


def _astar(
    start_idx: tuple[int, int],
    goal_idx: tuple[int, int],
    grid: SearchGrid,
    surface: CostSurface,
    weights: RouteWeights,
) -> tuple[list[tuple[int, int]], float, int]:
    rows, cols = grid.elevation.shape
    g_score = np.full((rows, cols), np.inf, dtype=float)
    closed = np.zeros((rows, cols), dtype=bool)
    came_from = np.full((rows, cols, 2), -1, dtype=np.int32)
    g_score[start_idx] = 0.0

    counter = 0
    open_heap: list[tuple[float, int, tuple[int, int]]] = [
        (_heuristic(start_idx, goal_idx, grid) * weights.distance, counter, start_idx)
    ]
    best_idx = start_idx
    best_h = _heuristic(start_idx, goal_idx, grid)
    visited = 0

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if closed[current]:
            continue
        closed[current] = True
        visited += 1

        h = _heuristic(current, goal_idx, grid)
        if h < best_h:
            best_h = h
            best_idx = current
        if current == goal_idx:
            return _reconstruct_path(came_from, current), float(g_score[current]), visited

        row, col = current
        for d_row, d_col in _neighbors():
            n_row = row + d_row
            n_col = col + d_col
            if n_row < 0 or n_col < 0 or n_row >= rows or n_col >= cols or closed[n_row, n_col]:
                continue
            neighbor = (n_row, n_col)
            step = _step_cost(current, neighbor, grid, surface, weights)
            tentative = g_score[current] + step
            if tentative < g_score[neighbor]:
                came_from[n_row, n_col] = [row, col]
                g_score[neighbor] = tentative
                counter += 1
                priority = tentative + _heuristic(neighbor, goal_idx, grid) * weights.distance
                heapq.heappush(open_heap, (float(priority), counter, neighbor))

    return _reconstruct_path(came_from, best_idx), float(g_score[best_idx]), visited


def _step_cost(
    current: tuple[int, int],
    neighbor: tuple[int, int],
    grid: SearchGrid,
    surface: CostSurface,
    weights: RouteWeights,
) -> float:
    row, col = current
    n_row, n_col = neighbor
    distance = _cell_distance_km(row, col, n_row, n_col, grid)
    if distance <= 0:
        return 0.0

    elevation_delta = abs(float(grid.elevation[n_row, n_col]) - float(grid.elevation[row, col]))
    move_slope = min(elevation_delta / max(distance * 1000.0, 1.0), 2.5)
    fire = (float(surface.fire[row, col]) + float(surface.fire[n_row, n_col])) / 2.0
    downwind = (float(surface.downwind[row, col]) + float(surface.downwind[n_row, n_col])) / 2.0
    fuel = (float(surface.fuel[row, col]) + float(surface.fuel[n_row, n_col])) / 2.0
    slope = max(
        move_slope,
        (float(surface.slope[row, col]) + float(surface.slope[n_row, n_col])) / 2.0,
    )
    inside = (float(surface.fire_core[row, col]) + float(surface.fire_core[n_row, n_col])) / 2.0
    road = (float(surface.road[row, col]) + float(surface.road[n_row, n_col])) / 2.0

    multiplier = (
        weights.distance
        + weights.fire * fire
        + weights.downwind * downwind
        + weights.fuel * fuel
        + weights.slope * slope
        + weights.inside_fire * inside
    )
    road_factor = max(0.62, 1.0 - weights.road_bonus * road)
    return max(distance * multiplier * road_factor, distance * 0.05)


def _build_search_grid(
    *,
    env: EnvironmentGrid | None,
    points: list[list[float]],
    fire_bbox: list[float],
    road_segments: list[dict[str, Any]],
) -> SearchGrid:
    west, south, east, north = fire_bbox
    lons = [point[0] for point in points] + [west, east]
    lats = [point[1] for point in points] + [south, north]
    bbox_width = max(east - west, 0.002)
    bbox_height = max(north - south, 0.002)
    min_lon = min(lons) - max(0.004, bbox_width * 0.18)
    max_lon = max(lons) + max(0.004, bbox_width * 0.18)
    min_lat = min(lats) - max(0.004, bbox_height * 0.18)
    max_lat = max(lats) + max(0.004, bbox_height * 0.18)

    if env is not None:
        lon_step = _median_step(env.lons)
        lat_step = _median_step(env.lats)
        if (
            min(lons) >= env.lons[0]
            and max(lons) <= env.lons[-1]
            and min(lats) >= env.lats[0]
            and max(lats) <= env.lats[-1]
        ):
            min_lon = max(min_lon, float(env.lons[0]))
            max_lon = min(max_lon, float(env.lons[-1]))
            min_lat = max(min_lat, float(env.lats[0]))
            max_lat = min(max_lat, float(env.lats[-1]))
    else:
        lon_step = max((max_lon - min_lon) / 180.0, 0.00028)
        lat_step = max((max_lat - min_lat) / 180.0, 0.00028)

    grid_lons = _make_axis(min_lon, max_lon, lon_step, max_count=280)
    grid_lats = _make_axis(min_lat, max_lat, lat_step, max_count=280)

    warnings: list[str] = []
    if env is None:
        elevation = _synthetic_elevation(grid_lats, grid_lons, fire_bbox)
        fuel_norm = _synthetic_fuel(grid_lats, grid_lons, fire_bbox)
        source = "synthetic_cost_surface"
        warnings.append("未能读取 final_input.nc，路径搜索已使用几何兜底代价面。")
    else:
        elevation, fuel_norm, outside_fraction = _sample_environment(env, grid_lats, grid_lons)
        source = env.source
        warnings.extend(env.warnings)
        if outside_fraction > 0.02:
            warnings.append(
                f"搜索范围有 {outside_fraction:.0%} 栅格超出 final_input.nc 覆盖范围，已使用边界栅格外推。"
            )

    slope_norm = _slope_surface(elevation, grid_lats, grid_lons)
    road_bonus = _road_bonus_surface(grid_lats, grid_lons, road_segments)
    return SearchGrid(
        lons=grid_lons,
        lats=grid_lats,
        elevation=elevation,
        fuel_norm=fuel_norm,
        slope_norm=slope_norm,
        road_bonus=road_bonus,
        environment_source=source,
        warnings=tuple(warnings),
    )


def _build_cost_surface(
    *,
    grid: SearchGrid,
    env: EnvironmentGrid | None,
    fire_bbox: list[float],
    spread_direction: str,
    fire_geometry: dict[str, Any] | None,
) -> CostSurface:
    lon_grid, lat_grid = np.meshgrid(grid.lons, grid.lats)
    fire, core = _fire_risk_surface(lon_grid, lat_grid, fire_bbox, fire_geometry)
    wind_vector = _combined_wind_vector(spread_direction, env)
    downwind = _downwind_surface(lon_grid, lat_grid, fire_bbox, wind_vector)
    combined = np.clip(
        0.52 * fire
        + 0.24 * downwind
        + 0.14 * grid.fuel_norm
        + 0.10 * np.clip(grid.slope_norm, 0.0, 1.0)
        - 0.06 * grid.road_bonus,
        0.0,
        1.0,
    )
    return CostSurface(
        fire=fire,
        fire_core=core.astype(float),
        downwind=downwind,
        fuel=grid.fuel_norm,
        slope=grid.slope_norm,
        road=grid.road_bonus,
        combined_risk=combined,
        wind_vector=wind_vector,
    )


def _fire_risk_surface(
    lon_grid: np.ndarray,
    lat_grid: np.ndarray,
    fire_bbox: list[float],
    fire_geometry: dict[str, Any] | None,
) -> tuple[np.ndarray, np.ndarray]:
    mean_lat = float(np.nanmean(lat_grid))
    if fire_geometry:
        try:
            from shapely import contains_xy, distance, points
            from shapely.geometry import shape

            geometry = shape(fire_geometry)
            core = contains_xy(geometry, lon_grid, lat_grid)
            degree_distance = np.asarray(distance(points(lon_grid, lat_grid), geometry), dtype=float)
            km_per_degree = _km_per_degree_mean(mean_lat)
            distance_km = degree_distance * km_per_degree
            risk = np.where(core, 1.0, np.exp(-distance_km / 0.7))
            return np.clip(risk, 0.0, 1.0), core
        except Exception:
            pass

    west, south, east, north = fire_bbox
    lon_factor = KM_PER_DEGREE_LON_EQUATOR * math.cos(math.radians(mean_lat))
    dx = np.maximum(np.maximum(west - lon_grid, 0.0), lon_grid - east) * lon_factor
    dy = np.maximum(np.maximum(south - lat_grid, 0.0), lat_grid - north) * KM_PER_DEGREE_LAT
    distance_km = np.sqrt(dx * dx + dy * dy)
    core = (lon_grid >= west) & (lon_grid <= east) & (lat_grid >= south) & (lat_grid <= north)
    risk = np.where(core, 1.0, np.exp(-distance_km / 0.7))
    return np.clip(risk, 0.0, 1.0), core


def _downwind_surface(
    lon_grid: np.ndarray,
    lat_grid: np.ndarray,
    fire_bbox: list[float],
    wind_vector: tuple[float, float],
) -> np.ndarray:
    west, south, east, north = fire_bbox
    center = [(west + east) / 2.0, (south + north) / 2.0]
    mean_lat = math.radians(center[1])
    x = (lon_grid - center[0]) * KM_PER_DEGREE_LON_EQUATOR * math.cos(mean_lat)
    y = (lat_grid - center[1]) * KM_PER_DEGREE_LAT
    vx, vy = wind_vector
    norm = math.hypot(vx, vy) or 1.0
    ux, uy = vx / norm, vy / norm
    along = x * ux + y * uy
    perp = np.abs(-uy * x + ux * y)

    width = max(
        min((east - west) * KM_PER_DEGREE_LON_EQUATOR * math.cos(mean_lat), (north - south) * KM_PER_DEGREE_LAT)
        * 0.75,
        0.55,
    )
    length = max(
        max((east - west) * KM_PER_DEGREE_LON_EQUATOR * math.cos(mean_lat), (north - south) * KM_PER_DEGREE_LAT)
        * 1.35,
        1.6,
    )
    plume = np.exp(-perp / width) * np.exp(-np.maximum(along, 0.0) / length)
    return np.clip(np.where(along > 0.0, plume, plume * 0.22), 0.0, 1.0)


def _sample_environment(
    env: EnvironmentGrid,
    grid_lats: np.ndarray,
    grid_lons: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    lat_idx = _nearest_indices(env.lats, grid_lats)
    lon_idx = _nearest_indices(env.lons, grid_lons)
    elevation = env.elevation[np.ix_(lat_idx, lon_idx)]
    fuel = env.fuel[np.ix_(lat_idx, lon_idx)]

    outside_lats = (grid_lats < env.lats[0]) | (grid_lats > env.lats[-1])
    outside_lons = (grid_lons < env.lons[0]) | (grid_lons > env.lons[-1])
    outside_fraction = float(
        (
            outside_lats[:, None]
            | outside_lons[None, :]
        ).sum()
        / max(len(grid_lats) * len(grid_lons), 1)
    )

    max_fuel = float(np.nanmax(fuel)) if np.isfinite(fuel).any() else 1.0
    if max_fuel <= 0:
        fuel_norm = np.zeros_like(fuel, dtype=float)
    else:
        fuel_norm = np.clip(fuel / max_fuel, 0.0, 1.0)
    return elevation.astype(float), fuel_norm.astype(float), outside_fraction


def _slope_surface(elevation: np.ndarray, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    dy_m = max(_median_step(lats) * KM_PER_DEGREE_LAT * 1000.0, 1.0)
    mean_lat = math.radians(float(np.nanmean(lats)))
    dx_m = max(_median_step(lons) * KM_PER_DEGREE_LON_EQUATOR * math.cos(mean_lat) * 1000.0, 1.0)
    grad_y, grad_x = np.gradient(elevation, dy_m, dx_m)
    grade = np.sqrt(grad_x * grad_x + grad_y * grad_y)
    return np.clip(grade / 0.75, 0.0, 2.0)


def _road_bonus_surface(
    lats: np.ndarray,
    lons: np.ndarray,
    road_segments: list[dict[str, Any]],
) -> np.ndarray:
    segments = [_segment_from_item(item) for item in road_segments]
    segments = [segment for segment in segments if segment is not None][:24]
    if not segments:
        return np.zeros((len(lats), len(lons)), dtype=float)

    lon_grid, lat_grid = np.meshgrid(lons, lats)
    center_lat = math.radians(float(np.nanmean(lats)))
    ref_lon = float(np.nanmean(lons))
    ref_lat = float(np.nanmean(lats))
    x = (lon_grid - ref_lon) * KM_PER_DEGREE_LON_EQUATOR * math.cos(center_lat)
    y = (lat_grid - ref_lat) * KM_PER_DEGREE_LAT
    bonus = np.zeros_like(x, dtype=float)

    for start, end in segments:
        ax = (start[0] - ref_lon) * KM_PER_DEGREE_LON_EQUATOR * math.cos(center_lat)
        ay = (start[1] - ref_lat) * KM_PER_DEGREE_LAT
        bx = (end[0] - ref_lon) * KM_PER_DEGREE_LON_EQUATOR * math.cos(center_lat)
        by = (end[1] - ref_lat) * KM_PER_DEGREE_LAT
        abx, aby = bx - ax, by - ay
        denom = abx * abx + aby * aby
        if denom <= 0:
            continue
        t = np.clip(((x - ax) * abx + (y - ay) * aby) / denom, 0.0, 1.0)
        px = ax + t * abx
        py = ay + t * aby
        distance = np.sqrt((x - px) ** 2 + (y - py) ** 2)
        bonus = np.maximum(bonus, np.exp(-((distance / 0.09) ** 2)))
    return np.clip(bonus, 0.0, 1.0)


def _segment_from_item(item: dict[str, Any]) -> tuple[list[float], list[float]] | None:
    start_lng = _as_float(item.get("start_lng"))
    start_lat = _as_float(item.get("start_lat"))
    end_lng = _as_float(item.get("end_lng"))
    end_lat = _as_float(item.get("end_lat"))
    if None not in (start_lng, start_lat, end_lng, end_lat):
        return [start_lng, start_lat], [end_lng, end_lat]
    coordinates = item.get("coordinates")
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        start = _coerce_point(coordinates[0])
        end = _coerce_point(coordinates[-1])
        if start and end:
            return start, end
    return None


def _synthetic_elevation(lats: np.ndarray, lons: np.ndarray, fire_bbox: list[float]) -> np.ndarray:
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    center_lon = (fire_bbox[0] + fire_bbox[2]) / 2.0
    center_lat = (fire_bbox[1] + fire_bbox[3]) / 2.0
    return (
        2850.0
        + (lat_grid - center_lat) * 16000.0
        - (lon_grid - center_lon) * 6000.0
        + np.sin((lon_grid - center_lon) * 400.0) * 45.0
        + np.cos((lat_grid - center_lat) * 360.0) * 35.0
    )


def _synthetic_fuel(lats: np.ndarray, lons: np.ndarray, fire_bbox: list[float]) -> np.ndarray:
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    center_lon = (fire_bbox[0] + fire_bbox[2]) / 2.0
    center_lat = (fire_bbox[1] + fire_bbox[3]) / 2.0
    pattern = 0.48 + 0.22 * np.sin((lon_grid - center_lon) * 520.0) + 0.18 * np.cos((lat_grid - center_lat) * 480.0)
    return np.clip(pattern, 0.05, 1.0)


def _combined_wind_vector(spread_direction: str, env: EnvironmentGrid | None) -> tuple[float, float]:
    sx, sy = _direction_vector(spread_direction)
    if env is None or env.wind_u is None or env.wind_v is None:
        return sx, sy
    wx, wy = float(env.wind_u), float(env.wind_v)
    wind_norm = math.hypot(wx, wy)
    if wind_norm < 0.05:
        return sx, sy
    wx, wy = wx / wind_norm, wy / wind_norm
    vx, vy = sx * 0.68 + wx * 0.32, sy * 0.68 + wy * 0.32
    norm = math.hypot(vx, vy) or 1.0
    return vx / norm, vy / norm


def _direction_vector(direction: str) -> tuple[float, float]:
    text = str(direction or "").lower()
    x = 0.0
    y = 0.0
    if "east" in text:
        x += 1.0
    if "west" in text:
        x -= 1.0
    if "north" in text:
        y += 1.0
    if "south" in text:
        y -= 1.0
    norm = math.hypot(x, y)
    if norm == 0:
        return 0.0, 1.0
    return x / norm, y / norm


def _point_to_index(point: list[float], grid: SearchGrid) -> tuple[int, int]:
    col = int(np.argmin(np.abs(grid.lons - float(point[0]))))
    row = int(np.argmin(np.abs(grid.lats - float(point[1]))))
    return row, col


def _indices_to_coordinates(path_indices: list[tuple[int, int]], grid: SearchGrid) -> list[list[float]]:
    return [[round(float(grid.lons[col]), 6), round(float(grid.lats[row]), 6)] for row, col in path_indices]


def _compress_path(raw_coords: list[list[float]], path_indices: list[tuple[int, int]]) -> list[list[float]]:
    if len(raw_coords) <= 2:
        return raw_coords
    keep = {0, len(raw_coords) - 1}
    last_kept = 0
    previous_direction: tuple[int, int] | None = None
    for index in range(1, len(path_indices)):
        prev = path_indices[index - 1]
        curr = path_indices[index]
        direction = (curr[0] - prev[0], curr[1] - prev[1])
        if previous_direction is not None and direction != previous_direction:
            keep.add(index - 1)
            last_kept = index - 1
        if index - last_kept >= 6:
            keep.add(index)
            last_kept = index
        previous_direction = direction
    return [raw_coords[index] for index in sorted(keep)]


def _elevation_profile(raw_coords: list[list[float]], raw_elevations: list[float]) -> list[dict[str, float]]:
    if not raw_coords:
        return []
    if len(raw_coords) == 1:
        return [{"distance_km": 0.0, "elevation_m": int(round(raw_elevations[0]))}]

    cumulative = [0.0]
    for start, end in zip(raw_coords, raw_coords[1:]):
        cumulative.append(cumulative[-1] + _distance_km(start, end))
    total = cumulative[-1]
    if total <= 0:
        return [{"distance_km": 0.0, "elevation_m": int(round(raw_elevations[0]))}]

    sample_count = min(28, max(7, int(math.ceil(total / 0.25)) + 1))
    targets = np.linspace(0.0, total, sample_count)
    elevations = np.interp(targets, cumulative, raw_elevations)
    profile = [
        {"distance_km": round(float(distance), 3), "elevation_m": int(round(float(elevation)))}
        for distance, elevation in zip(targets, elevations)
    ]
    profile[0]["distance_km"] = 0.0
    return profile


def _risk_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"average": 0.0, "maximum": 0.0, "high_share": 0.0}
    arr = np.asarray(values, dtype=float)
    return {
        "average": round(float(np.nanmean(arr)), 3),
        "maximum": round(float(np.nanmax(arr)), 3),
        "high_share": round(float((arr >= 0.7).sum() / max(arr.size, 1)), 3),
    }


def _risk_label_from_stats(stats: dict[str, float]) -> str:
    avg = stats["average"]
    high_share = stats["high_share"]
    if avg >= 0.5 or high_share >= 0.25:
        return "high"
    if avg >= 0.28 or high_share >= 0.08:
        return "medium"
    return "low"


def _reconstruct_path(came_from: np.ndarray, current: tuple[int, int]) -> list[tuple[int, int]]:
    path = [current]
    row, col = current
    while came_from[row, col, 0] >= 0:
        prev_row = int(came_from[row, col, 0])
        prev_col = int(came_from[row, col, 1])
        path.append((prev_row, prev_col))
        row, col = prev_row, prev_col
    path.reverse()
    return path


def _neighbors() -> tuple[tuple[int, int], ...]:
    return (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    )


def _heuristic(a: tuple[int, int], b: tuple[int, int], grid: SearchGrid) -> float:
    return _distance_km(
        [float(grid.lons[a[1]]), float(grid.lats[a[0]])],
        [float(grid.lons[b[1]]), float(grid.lats[b[0]])],
    )


def _cell_distance_km(row: int, col: int, n_row: int, n_col: int, grid: SearchGrid) -> float:
    return _distance_km(
        [float(grid.lons[col]), float(grid.lats[row])],
        [float(grid.lons[n_col]), float(grid.lats[n_row])],
    )


def _distance_km(a: list[float], b: list[float]) -> float:
    mean_lat = math.radians((a[1] + b[1]) / 2.0)
    east = (b[0] - a[0]) * KM_PER_DEGREE_LON_EQUATOR * math.cos(mean_lat)
    north = (b[1] - a[1]) * KM_PER_DEGREE_LAT
    return math.hypot(east, north)


def _polyline_distance_km(coordinates: list[list[float]]) -> float:
    if len(coordinates) < 2:
        return 0.0
    return sum(_distance_km(a, b) for a, b in zip(coordinates, coordinates[1:]))


def _diagnostics(grid: SearchGrid, surface: CostSurface, env: EnvironmentGrid | None) -> dict[str, Any]:
    lat_step = _median_step(grid.lats) * KM_PER_DEGREE_LAT * 1000.0
    mean_lat = math.radians(float(np.nanmean(grid.lats)))
    lon_step = _median_step(grid.lons) * KM_PER_DEGREE_LON_EQUATOR * math.cos(mean_lat) * 1000.0
    wind_speed = None
    if env is not None and env.wind_u is not None and env.wind_v is not None:
        wind_speed = round(math.hypot(env.wind_u, env.wind_v), 3)
    return {
        "search_method": "astar_cost_surface",
        "environment_source": grid.environment_source,
        "grid": {
            "rows": int(len(grid.lats)),
            "cols": int(len(grid.lons)),
            "lat_resolution_m": round(lat_step, 1),
            "lon_resolution_m": round(lon_step, 1),
        },
        "cost_layers": [
            "forefire_fire_geometry_distance",
            "downwind_plume_risk",
            "dem_slope",
            "fuel_index",
            "road_segment_attraction",
        ],
        "wind": {
            "east_component_mps": round(env.wind_u, 3) if env and env.wind_u is not None else None,
            "north_component_mps": round(env.wind_v, 3) if env and env.wind_v is not None else None,
            "speed_mps": wind_speed,
            "cost_vector": {
                "east": round(surface.wind_vector[0], 3),
                "north": round(surface.wind_vector[1], 3),
            },
        },
    }


def _make_axis(min_value: float, max_value: float, preferred_step: float, *, max_count: int) -> np.ndarray:
    if max_value <= min_value:
        max_value = min_value + preferred_step
    count = int(math.ceil((max_value - min_value) / max(preferred_step, 1e-6))) + 1
    count = max(3, min(max_count, count))
    return np.linspace(min_value, max_value, count, dtype=float)


def _nearest_indices(source_axis: np.ndarray, target_axis: np.ndarray) -> np.ndarray:
    positions = np.searchsorted(source_axis, target_axis)
    positions = np.clip(positions, 1, len(source_axis) - 1)
    left = positions - 1
    right = positions
    choose_right = np.abs(source_axis[right] - target_axis) < np.abs(source_axis[left] - target_axis)
    return np.where(choose_right, right, left).astype(int)


def _fill_invalid(values: np.ndarray, *, fallback: float) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if np.isfinite(arr).all():
        return arr
    fill = float(np.nanmedian(arr)) if np.isfinite(arr).any() else fallback
    return np.where(np.isfinite(arr), arr, fill)


def _dataset_mean(dataset: Any) -> float | None:
    if dataset is None:
        return None
    try:
        values = np.asarray(dataset[()], dtype=float)
    except Exception:
        return None
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return None
    return float(finite.mean())


def _median_step(axis: np.ndarray) -> float:
    if len(axis) < 2:
        return 0.00028
    diffs = np.abs(np.diff(axis.astype(float)))
    diffs = diffs[diffs > 0]
    if diffs.size == 0:
        return 0.00028
    return float(np.median(diffs))


def _km_per_degree_mean(lat: float) -> float:
    return (KM_PER_DEGREE_LAT + KM_PER_DEGREE_LON_EQUATOR * math.cos(math.radians(lat))) / 2.0


def _resolve_environment_dir(environment_dir: str | Path | None) -> Path:
    if environment_dir is None:
        return DEFAULT_ENVIRONMENT_DIR.resolve()
    path = Path(environment_dir)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _round_point(point: list[float]) -> list[float]:
    return [round(float(point[0]), 6), round(float(point[1]), 6)]


def _coerce_point(value: Any) -> list[float] | None:
    if isinstance(value, list) and len(value) >= 2:
        lon = _as_float(value[0])
        lat = _as_float(value[1])
        if lon is not None and lat is not None:
            return [lon, lat]
    return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
