from __future__ import annotations

import heapq
import math
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.event import FireEvent
from app.models.observation import Observation
from app.models.spatial_analysis import EmergencyRoutePlan, SpatialAnalysisRun, SpatialImpactRecord
from app.models.spread import FireFrontStep, SimulationRun
from app.schemas.spatial_analysis import SpatialAnalysisRequest
from app.services.event_service import append_timeline, get_event_or_404
from app.services.websocket_manager import websocket_manager


KM_PER_DEGREE_LAT = 110.574
KM_PER_DEGREE_LON = 111.320


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _offset(lng: float, lat: float, east_km: float, north_km: float) -> list[float]:
    return [
        round(lng + east_km / max(1e-6, KM_PER_DEGREE_LON * math.cos(math.radians(lat))), 7),
        round(lat + north_km / KM_PER_DEGREE_LAT, 7),
    ]


def _distance_km(a: list[float], b: list[float]) -> float:
    mean_lat = math.radians((a[1] + b[1]) / 2)
    east = (b[0] - a[0]) * KM_PER_DEGREE_LON * math.cos(mean_lat)
    north = (b[1] - a[1]) * KM_PER_DEGREE_LAT
    return math.hypot(east, north)


def _point_in_ring(point: list[float], ring: list[list[float]]) -> bool:
    x, y = point
    inside = False
    for start, end in zip(ring, ring[1:] + ring[:1]):
        x1, y1 = start
        x2, y2 = end
        if (y1 > y) != (y2 > y):
            cross_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < cross_x:
                inside = not inside
    return inside


def _distance_point_segment_km(point: list[float], start: list[float], end: list[float]) -> float:
    ref_lat = math.radians(point[1])
    scale_x = KM_PER_DEGREE_LON * math.cos(ref_lat)
    px, py = point[0] * scale_x, point[1] * KM_PER_DEGREE_LAT
    ax, ay = start[0] * scale_x, start[1] * KM_PER_DEGREE_LAT
    bx, by = end[0] * scale_x, end[1] * KM_PER_DEGREE_LAT
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _distance_to_rings_km(point: list[float], rings: list[list[list[float]]]) -> float:
    if any(_point_in_ring(point, ring) for ring in rings):
        return 0.0
    distances = [
        _distance_point_segment_km(point, start, end)
        for ring in rings
        for start, end in zip(ring, ring[1:])
    ]
    return min(distances) if distances else 999.0


def _distance_to_ring_boundary_km(point: list[float], ring: list[list[float]]) -> float:
    distances = [
        _distance_point_segment_km(point, start, end)
        for start, end in zip(ring, ring[1:] + ring[:1])
    ]
    return min(distances) if distances else 999.0


def _orientation(a: list[float], b: list[float], c: list[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a: list[float], b: list[float], c: list[float], d: list[float]) -> bool:
    return _orientation(a, b, c) * _orientation(a, b, d) <= 0 and _orientation(c, d, a) * _orientation(c, d, b) <= 0


def _line_intersects_rings(line: list[list[float]], rings: list[list[list[float]]]) -> bool:
    if any(_point_in_ring(point, ring) for point in line for ring in rings):
        return True
    return any(
        _segments_intersect(start, end, edge_start, edge_end)
        for start, end in zip(line, line[1:])
        for ring in rings
        for edge_start, edge_end in zip(ring, ring[1:])
    )


def _rings_from_feature(feature: dict[str, Any]) -> list[list[list[float]]]:
    geometry = feature.get("geometry") or {}
    if geometry.get("type") == "Polygon":
        return [geometry.get("coordinates", [[]])[0]]
    if geometry.get("type") == "MultiPolygon":
        return [polygon[0] for polygon in geometry.get("coordinates", []) if polygon]
    return []


def _scenario_assets(event: FireEvent) -> dict[str, list[dict[str, Any]]]:
    lng, lat = event.ignition_longitude, event.ignition_latitude
    return {
        "settlements": [
            {
                "object_id": "settlement_downwind",
                "name": "下风向林缘居民点",
                "object_type": "settlement",
                "population": 860,
                "point": _offset(lng, lat, 0.85, 0.55),
            },
            {
                "object_id": "settlement_west",
                "name": "西侧山谷村组",
                "object_type": "settlement",
                "population": 320,
                "point": _offset(lng, lat, -2.1, -0.25),
            },
            {
                "object_id": "forest_station",
                "name": "南侧森林管护站",
                "object_type": "facility",
                "population": 28,
                "point": _offset(lng, lat, -0.65, -2.4),
            },
        ],
        "targets": [
            {
                "object_id": "target_power",
                "name": "东侧输电设施",
                "object_type": "power",
                "population": 0,
                "point": _offset(lng, lat, 1.25, 0.25),
            },
            {
                "object_id": "target_watchtower",
                "name": "北侧瞭望塔",
                "object_type": "watchtower",
                "population": 4,
                "point": _offset(lng, lat, -0.35, 1.45),
            },
            {
                "object_id": "target_water",
                "name": "西南应急水源",
                "object_type": "water_source",
                "population": 0,
                "point": _offset(lng, lat, -1.75, -1.2),
            },
        ],
        "roads": [
            {
                "object_id": "road_forest_01",
                "name": "林区巡护道路",
                "object_type": "road",
                "population": 0,
                "line": [_offset(lng, lat, -2.6, 0.35), _offset(lng, lat, 2.5, 0.75)],
            },
            {
                "object_id": "road_county_02",
                "name": "南侧县乡道路",
                "object_type": "road",
                "population": 0,
                "line": [_offset(lng, lat, -3.5, -1.8), _offset(lng, lat, 3.2, -1.45)],
            },
            {
                "object_id": "road_access_03",
                "name": "东侧进场便道",
                "object_type": "road",
                "population": 0,
                "line": [_offset(lng, lat, 2.8, -2.2), _offset(lng, lat, 0.45, 0.2)],
            },
        ],
        "shelters": [
            {"object_id": "shelter_southwest", "name": "西南应急避难点", "point": _offset(lng, lat, -3.4, -2.7)},
            {"object_id": "shelter_northwest", "name": "西北备用避难点", "point": _offset(lng, lat, -3.6, 2.2)},
        ],
        "stations": [
            {"object_id": "rescue_station", "name": "森林消防前置站", "point": _offset(lng, lat, -3.1, -2.0)},
        ],
    }


def _severity(distance_km: float, affected: bool) -> str:
    if distance_km == 0:
        return "critical"
    if affected:
        return "high"
    if distance_km <= 1.2:
        return "medium"
    return "low"


def _impact_records(
    assets: dict[str, list[dict[str, Any]]],
    rings: list[list[list[float]]],
    threat_buffer_km: float,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    point_assets = [
        *assets["settlements"],
        *assets["targets"],
        *[
            {**item, "object_type": "resource_station", "resource_capacity": 24}
            for item in assets["stations"]
        ],
        *[
            {
                **item,
                "object_type": "shelter",
                "population": 0,
                "resource_capacity": 300,
            }
            for item in assets["shelters"]
        ],
    ]
    for item in point_assets:
        distance = _distance_to_rings_km(item["point"], rings)
        affected = distance <= threat_buffer_km
        proximity_score = max(0.0, 1.0 - distance / max(threat_buffer_km * 2.0, 0.1))
        exposure_score = proximity_score * (1.0 if affected else 0.6)
        records.append(
            {
                **item,
                "affected": affected,
                "severity": _severity(distance, affected),
                "risk_score": round(exposure_score * 100.0, 1),
                "distance_to_fire_km": round(distance, 3),
                "geometry": {"type": "Point", "coordinates": item["point"]},
                "risk_basis": "fireline_clearance_and_threat_buffer",
            }
        )
    for item in assets["roads"]:
        intersects = _line_intersects_rings(item["line"], rings)
        endpoint_distance = min(_distance_to_rings_km(point, rings) for point in item["line"])
        affected = intersects or endpoint_distance <= threat_buffer_km
        proximity_score = max(0.0, 1.0 - endpoint_distance / max(threat_buffer_km * 2.0, 0.1))
        exposure_score = 1.0 if intersects else proximity_score * 0.6
        records.append(
            {
                **item,
                "affected": affected,
                "severity": "critical" if intersects else _severity(endpoint_distance, affected),
                "risk_score": round(exposure_score * 100.0, 1),
                "distance_to_fire_km": 0.0 if intersects else round(endpoint_distance, 3),
                "geometry": {"type": "LineString", "coordinates": item["line"]},
                "risk_basis": "fireline_intersection_or_road_clearance",
            }
        )
    return records


def _remote_sensing_summary(observations: list[Observation]) -> dict[str, Any]:
    """Summarize remote observations without inventing imagery evidence."""
    remote = [
        item
        for item in observations
        if item.source_type in {"satellite", "uav", "watchtower", "video"}
    ]
    source_confidence: dict[str, float] = {}
    for item in remote:
        source_confidence[item.source_type] = max(
            source_confidence.get(item.source_type, 0.0),
            float(item.confidence or 0.0),
        )
    mean_confidence = (
        sum(float(item.confidence or 0.0) for item in remote) / len(remote)
        if remote
        else 0.0
    )
    return {
        "observation_count": len(remote),
        "source_types": sorted(source_confidence),
        "max_confidence_by_source": {
            key: round(value, 3) for key, value in sorted(source_confidence.items())
        },
        "mean_confidence": round(mean_confidence, 3),
        "used_as": "evidence_quality_and_traceability",
        "is_simulated": any(item.is_simulated for item in remote) if remote else True,
    }


def _landcover_impact_summary(
    final_feature: dict[str, Any],
    total_area_km2: float,
) -> list[dict[str, Any]]:
    """Estimate fuel-class exposure from fireline sector samples."""
    properties = final_feature.get("properties") or {}
    landscape = properties.get("landscape") or {}
    counts = landscape.get("landcover_sector_counts") or {}
    total = sum(int(value) for value in counts.values())
    if total <= 0:
        return []
    return [
        {
            "name": str(name),
            "sector_count": int(count),
            "share": round(int(count) / total, 3),
            "area_km2": round(total_area_km2 * int(count) / total, 3),
            "calculation": "fireline_sector_sampling",
            "is_simulated": bool(landscape.get("is_simulated", True)),
        }
        for name, count in sorted(counts.items(), key=lambda pair: str(pair[0]))
    ]


def _fire_intensity_zones(
    final_feature: dict[str, Any],
    center: list[float],
) -> list[dict[str, Any]]:
    """Partition the final fire area into interpretable radial intensity zones."""
    properties = final_feature.get("properties") or {}
    geometry = final_feature.get("geometry") or {}
    ring = (geometry.get("coordinates") or [[]])[0]
    radii = properties.get("sector_radii_km") or []
    if len(ring) < 3 or len(radii) < 2:
        return []
    values = sorted(float(value) for value in radii)
    low_cut = values[max(0, int(len(values) * 0.33) - 1)]
    high_cut = values[min(len(values) - 1, int(len(values) * 0.67))]
    landscape = properties.get("landscape") or {}
    labels = landscape.get("landcover_sector_labels") or []
    zones: list[dict[str, Any]] = []
    for index, radius in enumerate(radii):
        radius_value = float(radius)
        if radius_value >= high_cut:
            level, label, color = "high", "large_fire", "#ef4444"
        elif radius_value >= low_cut:
            level, label, color = "medium", "medium_fire", "#f59e0b"
        else:
            level, label, color = "low", "small_fire", "#38bdf8"
        next_index = (index + 1) % len(radii)
        first = ring[index]
        second = ring[next_index]
        zones.append(
            {
                "type": "Feature",
                "properties": {
                    "object_id": f"fire_zone_{index + 1:02d}",
                    "object_type": "fire_intensity_zone",
                    "intensity_level": level,
                    "intensity_label": label,
                    "risk_score": round(
                        {"high": 85, "medium": 58, "low": 30}[level]
                        + min(10.0, radius_value / max(values[-1], 0.001) * 10.0),
                        1,
                    ),
                    "landcover_label": labels[index] if index < len(labels) else "unknown",
                    "sector_index": index,
                    "radius_km": round(radius_value, 4),
                    "fill_color": color,
                    "is_simulated": True,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[center, first, second, center]],
                },
            }
        )
    return zones


def _risk_areas(
    final_feature: dict[str, Any],
    previous_feature: dict[str, Any] | None,
    center: list[float],
    assets: dict[str, list[dict[str, Any]]],
    threat_buffer_km: float,
) -> list[dict[str, Any]]:
    """Build multi-factor risk zones across the fire and its threat buffer."""
    properties = final_feature.get("properties") or {}
    rings = _rings_from_feature(final_feature)
    ring = max(rings, key=len, default=[])
    radii = [float(value) for value in properties.get("sector_radii_km") or []]
    fire_intensities = [
        max(0.0, float(value))
        for value in properties.get("sector_fire_intensity_kw_m") or []
    ]
    if len(ring) < 3 or len(radii) < 2:
        return []
    previous_radii = [
        float(value)
        for value in ((previous_feature or {}).get("properties") or {}).get("sector_radii_km") or []
    ]
    environment = properties.get("environment") or {}
    landscape = properties.get("landscape") or {}
    slope_factors = landscape.get("slope_sector_factors") or []
    landcover_labels = landscape.get("landcover_sector_labels") or []
    max_radius = max(radii) or 1.0
    max_growth = max(
        1e-6,
        max(
            [max(0.0, radius - previous_radii[index]) for index, radius in enumerate(radii) if index < len(previous_radii)]
            or [1.0]
        ),
    )
    point_assets = [*assets["settlements"], *assets["targets"], *assets["stations"]]
    risk_scores: list[float] = []
    component_rows: list[dict[str, float]] = []
    sector_intensity_values: list[float] = []
    for index, radius in enumerate(radii):
        direction = index * 360.0 / len(radii)
        point = _from_local(
            math.sin(math.radians(direction)) * radius,
            math.cos(math.radians(direction)) * radius,
            center,
        )
        spread_score = min(1.0, radius / max_radius)
        growth = max(0.0, radius - previous_radii[index]) if index < len(previous_radii) else radius
        growth_score = min(1.0, growth / max_growth)
        wind_score = 0.5 + 0.5 * math.cos(
            math.radians(direction - float(environment.get("wind_direction_deg", 0.0)))
        )
        terrain_factor = float(slope_factors[index]) if index < len(slope_factors) else 1.0
        terrain_score = _clamp((terrain_factor - 0.62) / 1.03, 0.0, 1.0)
        fuel_label = str(landcover_labels[index]).lower() if index < len(landcover_labels) else "unknown"
        fuel_score = 0.9 if any(token in fuel_label for token in ("grass", "shrub")) else 0.68 if "forest" in fuel_label else 0.25 if any(token in fuel_label for token in ("bare", "rock", "urban")) else 0.55
        asset_score = max(
            (max(0.0, 1.0 - _distance_km(point, item["point"]) / 2.0) for item in point_assets),
            default=0.0,
        )
        intensity_kw_m = fire_intensities[index] if index < len(fire_intensities) else 0.0
        if fire_intensities:
            intensity_score = (
                _clamp(intensity_kw_m / 1000.0, 0.0, 0.5)
                if intensity_kw_m < 500.0
                else _clamp(0.5 + (intensity_kw_m - 500.0) / 5000.0, 0.5, 1.0)
            )
        else:
            intensity_score = growth_score
        components = {
            "fire_intensity": intensity_score,
            "spread": spread_score,
            "growth": growth_score,
            "wind": wind_score,
            "terrain": terrain_score,
            "fuel": fuel_score,
            "asset_exposure": asset_score,
        }
        score = 100.0 * (
            # Fireline intensity is the primary hazard driver. The remaining
            # factors describe how quickly the hazard may grow and what it may
            # expose, without converting geometry alone into a risk category.
            0.45 * intensity_score
            + 0.12 * spread_score
            + 0.12 * growth_score
            + 0.08 * wind_score
            + 0.07 * terrain_score
            + 0.07 * fuel_score
            + 0.09 * asset_score
        )
        risk_scores.append(score)
        component_rows.append(components)
        sector_intensity_values.append(intensity_kw_m)

    # Classify a local grid instead of connecting the fireline vertices to the
    # ignition point. Use an adaptive resolution so a compact fire does not
    # collapse into only a handful of cells and one uniform risk polygon.
    # The requested threat buffer represents potential near-term spread beyond
    # the current perimeter. Keep it bounded for stable grid resolution.
    threat_buffer_km = _clamp(threat_buffer_km, 0.08, 1.0)
    extent = max_radius + threat_buffer_km
    grid_size = max(32, min(72, math.ceil((extent * 2.0) / 0.3)))
    cell_size = (extent * 2.0) / grid_size
    # ``active_front`` is retained as an explanatory spatial attribute, but it
    # must not impose a minimum risk level.  A fireline can have low modeled
    # intensity (for example after moisture or fuel changes), so its risk must
    # still come from the fire-behaviour factors below.
    active_front_width_km = max(0.12, cell_size * 1.1)

    sorted_intensities = sorted(sector_intensity_values)
    intensity_low = sorted_intensities[max(0, int(len(sorted_intensities) * 0.2) - 1)]
    intensity_high = sorted_intensities[min(len(sorted_intensities) - 1, int(len(sorted_intensities) * 0.8))]
    intensity_span = max(1.0, intensity_high - intensity_low)
    final_elapsed_minute = max(1.0, float(properties.get("elapsed_minutes") or 1.0))
    previous_elapsed_minute = max(
        0.0,
        float(((previous_feature or {}).get("properties") or {}).get("elapsed_minutes") or 0.0),
    )

    def classify_risk(score: float, intensity_kw_m: float) -> str:
        # Absolute Byram intensity protects genuinely severe fronts from being
        # diluted by relative normalization. The composite score supplies the
        # within-fire gradient for moderate and low-intensity incidents.
        if score >= 48.0 or (intensity_kw_m >= 2000.0 and score >= 40.0):
            return "high"
        if score >= 35.0:
            return "medium"
        return "low"

    cells: dict[tuple[int, int], dict[str, Any]] = {}
    for row in range(grid_size):
        for col in range(grid_size):
            x = -extent + (col + 0.5) * cell_size
            y = -extent + (row + 0.5) * cell_size
            distance = math.hypot(x, y)
            grid_point = _from_local(x, y, center)
            inside_fire = _point_in_ring(grid_point, ring)
            boundary_distance = _distance_to_ring_boundary_km(grid_point, ring)
            if not inside_fire and boundary_distance > threat_buffer_km:
                continue
            direction = math.degrees(math.atan2(x, y)) % 360.0
            sector = min(
                range(len(radii)),
                key=lambda index: abs(
                    (direction - index * 360.0 / len(radii) + 180.0) % 360.0 - 180.0
                ),
            )
            front_radius = max(0.05, radii[sector])
            previous_radius = (
                max(0.0, previous_radii[sector])
                if sector < len(previous_radii)
                else 0.0
            )
            front_proximity = _clamp(
                1.0 - boundary_distance / max(0.65, front_radius * 0.42),
                0.0,
                1.0,
            )
            base_score = risk_scores[sector]
            intensity_kw_m = sector_intensity_values[sector]
            relative_intensity = _clamp(
                (intensity_kw_m - intensity_low) / intensity_span,
                0.0,
                1.0,
            )
            absolute_intensity = _clamp(intensity_kw_m / 2000.0, 0.0, 1.0)
            if inside_fire:
                radial_progress = _clamp(distance / front_radius, 0.0, 1.0)
                if previous_radius > 0.0 and distance <= previous_radius:
                    estimated_arrival = previous_elapsed_minute * _clamp(
                        distance / previous_radius,
                        0.0,
                        1.0,
                    )
                else:
                    interval_progress = _clamp(
                        (distance - previous_radius) / max(0.05, front_radius - previous_radius),
                        0.0,
                        1.0,
                    )
                    estimated_arrival = previous_elapsed_minute + (
                        final_elapsed_minute - previous_elapsed_minute
                    ) * interval_progress
                arrival_urgency = max(radial_progress, estimated_arrival / final_elapsed_minute)
            else:
                estimated_arrival = final_elapsed_minute * (
                    1.0 + boundary_distance / max(0.05, threat_buffer_km)
                )
                arrival_urgency = _clamp(
                    1.0 - boundary_distance / max(0.05, threat_buffer_km),
                    0.0,
                    1.0,
                )
            # The local score combines the sector fire-behaviour score with
            # recency/arrival, relative intensity within this incident, and an
            # absolute Byram-intensity contribution.
            relative_intensity_exposure = relative_intensity * (
                0.35 + 0.65 * arrival_urgency
            )
            local_score = (
                0.30 * base_score
                + 25.0 * arrival_urgency
                + 15.0 * relative_intensity_exposure
                + 25.0 * absolute_intensity
            )
            local_score = _clamp(local_score, 0.0, 100.0)
            level = classify_risk(local_score, intensity_kw_m)
            cells[(row, col)] = {
                "score": local_score,
                "level": level,
                "sector": sector,
                "point": [x, y],
                "components": {
                    **component_rows[sector],
                    "arrival_urgency": arrival_urgency,
                    "relative_fire_intensity": relative_intensity_exposure,
                    "absolute_fire_intensity": absolute_intensity,
                },
                "fire_intensity_kw_m": intensity_kw_m,
                "estimated_arrival_minute": estimated_arrival,
                "minimum_score": 0.0,
                "inside_fire": inside_fire,
                "active_front": boundary_distance <= active_front_width_km,
            }

    # Smooth cell scores over their immediate neighborhood. This removes
    # isolated classification holes while retaining broad spatial gradients.
    smoothed_scores: dict[tuple[int, int], float] = {}
    for cell, data in cells.items():
        row, col = cell
        neighbor_scores = [
            cells[neighbor]["score"]
            for neighbor in (
                (row - 1, col - 1), (row - 1, col), (row - 1, col + 1),
                (row, col - 1), (row, col + 1),
                (row + 1, col - 1), (row + 1, col), (row + 1, col + 1),
            )
            if neighbor in cells
        ]
        neighborhood_mean = sum(neighbor_scores) / len(neighbor_scores) if neighbor_scores else data["score"]
        smoothed_scores[cell] = max(
            data["minimum_score"],
            0.6 * data["score"] + 0.4 * neighborhood_mean,
        )
    for cell, score in smoothed_scores.items():
        cells[cell]["score"] = score
        cells[cell]["level"] = classify_risk(score, cells[cell]["fire_intensity_kw_m"])

    # Remove isolated one-cell classifications that create visual gaps between
    # otherwise continuous risk bands. Two passes are enough at this grid size.
    for _ in range(2):
        level_updates: dict[tuple[int, int], str] = {}
        for cell, data in cells.items():
            if data["minimum_score"] > 0:
                continue
            row, col = cell
            neighbor_levels = [
                cells[neighbor]["level"]
                for neighbor in (
                    (row - 1, col - 1), (row - 1, col), (row - 1, col + 1),
                    (row, col - 1), (row, col + 1),
                    (row + 1, col - 1), (row + 1, col), (row + 1, col + 1),
                )
                if neighbor in cells
            ]
            counts = {level: neighbor_levels.count(level) for level in ("low", "medium", "high")}
            dominant_level = max(counts, key=counts.get)
            if counts[data["level"]] <= 1 and counts[dominant_level] >= 3:
                level_updates[cell] = dominant_level
        for cell, level in level_updates.items():
            cells[cell]["level"] = level

    visited: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for cell in cells:
        if cell in visited:
            continue
        visited.add(cell)
        level = cells[cell]["level"]
        stack = [cell]
        component: list[tuple[int, int]] = []
        while stack:
            current = stack.pop()
            component.append(current)
            row, col = current
            for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if neighbor in cells and neighbor not in visited and cells[neighbor]["level"] == level:
                    visited.add(neighbor)
                    stack.append(neighbor)
        components.append(component)

    def component_polygon(component: list[tuple[int, int]]) -> list[list[list[float]]]:
        import numpy as np
        from affine import Affine
        from rasterio.features import shapes

        mask = np.zeros((grid_size, grid_size), dtype="uint8")
        for row, col in component:
            mask[row, col] = 1
        transform = Affine(cell_size, 0.0, -extent, 0.0, cell_size, -extent)
        polygons: list[list[list[list[float]]]] = []
        for geometry, value in shapes(mask, mask=mask.astype(bool), transform=transform):
            if value != 1 or geometry.get("type") != "Polygon":
                continue
            polygons.append(
                [
                    [_from_local(float(point[0]), float(point[1]), center) for point in ring]
                    for ring in geometry.get("coordinates", [])
                ]
            )
        return polygons[0] if polygons else []

    result: list[dict[str, Any]] = []
    for group_index, component in enumerate(components, 1):
        score = sum(cells[cell]["score"] for cell in component) / len(component)
        factor_totals = {
            key: sum(cells[cell]["components"].get(key, 0.0) for cell in component)
            for key in cells[component[0]]["components"]
        }
        component_intensities = [cells[cell]["fire_intensity_kw_m"] for cell in component]
        component_arrivals = [cells[cell]["estimated_arrival_minute"] for cell in component]
        inside_cell_count = sum(bool(cells[cell]["inside_fire"]) for cell in component)
        active_front_cell_count = sum(bool(cells[cell]["active_front"]) for cell in component)
        # Components are assembled from cells of one class, so preserve that
        # class instead of averaging a local intensity peak back out of it.
        # Spatial relation remains explanatory and never forces the category.
        level = cells[component[0]]["level"]
        zone_relation = (
            "contains_active_fireline"
            if active_front_cell_count
            else "burned_footprint"
            if inside_cell_count
            else "external_threat_buffer"
        )
        mean_intensity = sum(component_intensities) / max(1, len(component_intensities))
        max_intensity = max(component_intensities, default=0.0)
        intensity_level = (
            "extreme" if mean_intensity >= 4000
            else "high" if mean_intensity >= 2000
            else "moderate" if mean_intensity >= 500
            else "low"
        )
        polygon_rings = component_polygon(component)
        if not polygon_rings or len(polygon_rings[0]) < 4:
            continue
        result.append(
            {
                "type": "Feature",
                "properties": {
                    "object_id": f"risk_area_{group_index:02d}",
                    "object_type": "risk_area",
                    "risk_level": level,
                    "risk_score": round(score, 1),
                    "mean_fire_intensity_kw_m": round(mean_intensity, 1),
                    "max_fire_intensity_kw_m": round(max_intensity, 1),
                    "mean_estimated_arrival_minute": round(
                        sum(component_arrivals) / max(1, len(component_arrivals)),
                        1,
                    ),
                    "fire_intensity_level": intensity_level,
                    "fire_intensity_method": "Byram_H_w_R_proxy_unvalidated",
                    "sector_count": len(component),
                    "dominant_factors": sorted(factor_totals, key=factor_totals.get, reverse=True)[:3],
                    "grid_cell_count": len(component),
                    "inside_fire_cell_count": inside_cell_count,
                    "active_front_cell_count": active_front_cell_count,
                    "zone_relation": zone_relation,
                    "grid_resolution": round(cell_size, 3),
                    "classification_method": "fire_intensity_arrival_growth_wind_terrain_fuel_exposure",
                    "threat_buffer_km": round(threat_buffer_km, 3),
                    "is_simulated": True,
                },
                "geometry": {"type": "Polygon", "coordinates": polygon_rings},
            }
        )
    return result


def _local_xy(point: list[float], origin: list[float]) -> tuple[float, float]:
    return (
        (point[0] - origin[0]) * KM_PER_DEGREE_LON * math.cos(math.radians(origin[1])),
        (point[1] - origin[1]) * KM_PER_DEGREE_LAT,
    )


def _from_local(x: float, y: float, origin: list[float]) -> list[float]:
    return _offset(origin[0], origin[1], x, y)


def _point_segment_distance_xy(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _route_path(
    *,
    start: list[float],
    end: list[float],
    origin: list[float],
    rings: list[list[list[float]]],
    roads: list[dict[str, Any]],
    blocked_road_ids: set[str],
    safety_weight: float,
) -> tuple[list[list[float]], dict[str, Any]]:
    start_xy = _local_xy(start, origin)
    end_xy = _local_xy(end, origin)
    fire_points = [_local_xy(point, origin) for ring in rings for point in ring]
    all_x = [start_xy[0], end_xy[0], *(point[0] for point in fire_points)]
    all_y = [start_xy[1], end_xy[1], *(point[1] for point in fire_points)]
    margin = 1.3
    min_x, max_x = min(all_x) - margin, max(all_x) + margin
    min_y, max_y = min(all_y) - margin, max(all_y) + margin
    size = 76
    step_x = (max_x - min_x) / (size - 1)
    step_y = (max_y - min_y) / (size - 1)
    local_rings = [[_local_xy(point, origin) for point in ring] for ring in rings]
    local_roads = [
        {
            **road,
            "line_xy": [_local_xy(point, origin) for point in road["line"]],
        }
        for road in roads
    ]

    def index_of(point: tuple[float, float]) -> tuple[int, int]:
        col = round((point[0] - min_x) / step_x)
        row = round((point[1] - min_y) / step_y)
        return max(0, min(size - 1, row)), max(0, min(size - 1, col))

    def xy_of(node: tuple[int, int]) -> tuple[float, float]:
        row, col = node
        return min_x + col * step_x, min_y + row * step_y

    def inside_fire(point: tuple[float, float]) -> bool:
        return any(_point_in_ring([point[0], point[1]], [[p[0], p[1]] for p in ring]) for ring in local_rings)

    def fire_distance(point: tuple[float, float]) -> float:
        if inside_fire(point):
            return 0.0
        return min(
            _point_segment_distance_xy(point, start_point, end_point)
            for ring in local_rings
            for start_point, end_point in zip(ring, ring[1:])
        )

    def road_cost_factor(point: tuple[float, float]) -> float:
        factor = 1.0
        for road in local_roads:
            distance = _point_segment_distance_xy(point, road["line_xy"][0], road["line_xy"][-1])
            if distance <= 0.18:
                factor = min(factor, 0.68)
                if road["object_id"] in blocked_road_ids:
                    factor = 8.0
        return factor

    start_node, end_node = index_of(start_xy), index_of(end_xy)
    queue: list[tuple[float, tuple[int, int]]] = [(0.0, start_node)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    scores = {start_node: 0.0}
    visited = 0
    while queue:
        _, current = heapq.heappop(queue)
        visited += 1
        if current == end_node:
            break
        row, col = current
        current_xy = xy_of(current)
        for dr, dc in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
            neighbor = (row + dr, col + dc)
            if not (0 <= neighbor[0] < size and 0 <= neighbor[1] < size):
                continue
            neighbor_xy = xy_of(neighbor)
            move = math.hypot(neighbor_xy[0] - current_xy[0], neighbor_xy[1] - current_xy[1])
            distance_fire = fire_distance(neighbor_xy)
            fire_penalty = 80.0 if distance_fire == 0 else math.exp(-distance_fire / 0.55) * safety_weight
            elevation = 2450 + neighbor_xy[1] * 38 + math.sin(neighbor_xy[0] * 1.4) * 55
            current_elevation = 2450 + current_xy[1] * 38 + math.sin(current_xy[0] * 1.4) * 55
            slope_penalty = min(2.5, abs(elevation - current_elevation) / max(move * 1000, 1) * 12)
            fuel_penalty = 0.35 + 0.25 * (1 + math.sin(neighbor_xy[0] * 1.8 + neighbor_xy[1])) / 2
            tentative = scores[current] + move * (1 + fire_penalty + slope_penalty + fuel_penalty) * road_cost_factor(neighbor_xy)
            if tentative >= scores.get(neighbor, float("inf")):
                continue
            came_from[neighbor] = current
            scores[neighbor] = tentative
            heuristic = math.hypot(neighbor_xy[0] - end_xy[0], neighbor_xy[1] - end_xy[1])
            heapq.heappush(queue, (tentative + heuristic, neighbor))

    node = end_node if end_node in scores else min(scores, key=lambda item: math.hypot(xy_of(item)[0] - end_xy[0], xy_of(item)[1] - end_xy[1]))
    nodes = [node]
    while node in came_from:
        node = came_from[node]
        nodes.append(node)
    nodes.reverse()
    coordinates = [_from_local(*xy_of(node), origin) for node in nodes]
    if coordinates:
        coordinates[0] = start
        coordinates[-1] = end
    compressed = [point for index, point in enumerate(coordinates) if index == 0 or index == len(coordinates) - 1 or index % 5 == 0]
    length = sum(_distance_km(a, b) for a, b in zip(coordinates, coordinates[1:]))
    min_fire_distance = min((_distance_to_rings_km(point, rings) for point in coordinates), default=999.0)
    return compressed, {
        "search_method": "astar_cost_surface",
        "visited_nodes": visited,
        "grid_size": [size, size],
        "distance_km": round(length, 3),
        "minimum_fire_distance_km": round(min_fire_distance, 3),
    }


def _route_specs(
    event: FireEvent,
    spread_direction_deg: float,
    assets: dict[str, list[dict[str, Any]]],
    impacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ignition = [event.ignition_longitude, event.ignition_latitude]
    threatened = next(
        (item for item in impacts if item["object_type"] == "settlement" and item["affected"]),
        assets["settlements"][0],
    )
    theta = math.radians(spread_direction_deg)
    staging = _offset(ignition[0], ignition[1], -math.sin(theta) * 1.25, -math.cos(theta) * 1.25)
    return [
        {
            "route_type": "rescue_approach",
            "name": "救援进入路线",
            "start": assets["stations"][0]["point"],
            "end": staging,
            "speed_kmh": 24,
            "safety_weight": 6.5,
        },
        {
            "route_type": "evacuation",
            "name": "人员疏散主路线",
            "start": threatened["point"],
            "end": assets["shelters"][0]["point"],
            "speed_kmh": 20,
            "safety_weight": 12.0,
        },
        {
            "route_type": "evacuation_backup",
            "name": "人员疏散备用路线",
            "start": threatened["point"],
            "end": assets["shelters"][1]["point"],
            "speed_kmh": 18,
            "safety_weight": 14.0,
        },
    ]


def _risk_from_clearance(clearance: float) -> str:
    if clearance < 0.2:
        return "high"
    if clearance < 0.65:
        return "medium"
    return "low"


async def _latest_spread(db: AsyncSession, event_id: str) -> SimulationRun | None:
    result = await db.execute(
        select(SimulationRun)
        .where(SimulationRun.event_id == event_id)
        .order_by(desc(SimulationRun.created_at), desc(SimulationRun.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _spread_steps(db: AsyncSession, run_id: str) -> list[FireFrontStep]:
    result = await db.execute(
        select(FireFrontStep).where(FireFrontStep.run_id == run_id).order_by(FireFrontStep.time_minute, FireFrontStep.id)
    )
    return list(result.scalars().all())


async def create_spatial_analysis(
    db: AsyncSession,
    event_id: str,
    request: SpatialAnalysisRequest,
) -> dict[str, Any]:
    event = await get_event_or_404(db, event_id)
    spread = await _latest_spread(db, event_id)
    if not spread:
        raise AppError("Spread prediction is required before spatial analysis.", code="spread_run_required", status_code=400)
    steps = await _spread_steps(db, spread.run_id)
    if not steps:
        raise AppError("Spread prediction has no fireline steps.", code="fireline_steps_required", status_code=400)
    final_feature = steps[-1].fireline_geojson
    rings = _rings_from_feature(final_feature)
    if not rings:
        raise AppError("Final fireline geometry is not a polygon.", code="invalid_fireline_geometry", status_code=400)

    assets = _scenario_assets(event)
    observation_result = await db.execute(
        select(Observation)
        .where(Observation.event_id == event_id)
        .order_by(desc(Observation.observed_at), desc(Observation.id))
    )
    remote_sensing = _remote_sensing_summary(list(observation_result.scalars().all()))
    impacts_data = _impact_records(assets, rings, request.threat_buffer_km)
    blocked = set(request.blocked_road_ids)
    routes_data: list[dict[str, Any]] = []
    if request.include_routes:
        for spec in _route_specs(event, spread.spread_direction_deg, assets, impacts_data):
            coordinates, diagnostics = _route_path(
                start=spec["start"],
                end=spec["end"],
                origin=[event.ignition_longitude, event.ignition_latitude],
                rings=rings,
                roads=assets["roads"],
                blocked_road_ids=blocked,
                safety_weight=spec["safety_weight"],
            )
            risk = _risk_from_clearance(diagnostics["minimum_fire_distance_km"])
            routes_data.append(
                {
                    **spec,
                    "coordinates": coordinates,
                    "distance_km": diagnostics["distance_km"],
                    "eta_minutes": round(diagnostics["distance_km"] / spec["speed_kmh"] * 60, 1),
                    "risk_level": risk,
                    "status": "replanned" if blocked else "available",
                    "diagnostics": diagnostics,
                }
            )

    analysis_id = f"spa_{uuid4().hex[:18]}"
    affected = [item for item in impacts_data if item["affected"]]
    affected_population = sum(item.get("population", 0) for item in affected)
    affected_roads = [item for item in affected if item["object_type"] == "road"]
    affected_resources = [
        item
        for item in affected
        if item["object_type"] in {"resource_station", "shelter", "water_source"}
    ]
    risk_areas = _risk_areas(
        final_feature,
        steps[-2].fireline_geojson if len(steps) > 1 else None,
        [event.ignition_longitude, event.ignition_latitude],
        assets,
        request.threat_buffer_km,
    )
    summary = {
        "final_fire_area_km2": spread.final_area_km2,
        "maximum_spread_distance_km": spread.max_radius_km,
        "spread_direction_deg": spread.spread_direction_deg,
        "risk_level": spread.risk_level,
        "affected_object_count": len(affected),
        "affected_settlement_count": sum(item["object_type"] == "settlement" for item in affected),
        "affected_population": affected_population,
        "interrupted_road_count": len(affected_roads),
        "affected_resource_count": len(affected_resources),
        "affected_resource_capacity": sum(
            int(item.get("resource_capacity", 0)) for item in affected_resources
        ),
        "threatened_target_count": sum(item["object_type"] not in {"settlement", "road"} for item in affected),
        "risk_areas": {
            "feature_count": len(risk_areas),
            "high_count": sum(item["properties"]["risk_level"] == "high" for item in risk_areas),
            "medium_count": sum(item["properties"]["risk_level"] == "medium" for item in risk_areas),
            "low_count": sum(item["properties"]["risk_level"] == "low" for item in risk_areas),
            "classification": "multi_factor_grid_connectivity",
            "model_reliability": {
                "level": "demonstration_only",
                "calibrated": False,
                "validated_against_historical_fires": False,
                "note": "Composite proxy index; not an official wildfire hazard rating.",
            },
        },
        "remote_sensing": remote_sensing,
        "risk_method": "fire_intensity_arrival_growth_wind_terrain_fuel_exposure_grid",
        "route_count": len(routes_data),
        "blocked_road_ids": sorted(blocked),
    }
    impact_features = [
        {
            "type": "Feature",
            "properties": {
                "object_id": item["object_id"],
                "name": item["name"],
                "object_type": item["object_type"],
                "affected": item["affected"],
                "severity": item["severity"],
                "distance_to_fire_km": item["distance_to_fire_km"],
                "population": item.get("population", 0),
                "risk_score": item.get("risk_score", 0),
                "risk_basis": item.get("risk_basis", "fireline_clearance"),
                "resource_capacity": item.get("resource_capacity", 0),
                "is_simulated": True,
            },
            "geometry": item["geometry"],
        }
        for item in impacts_data
    ]
    impact_features.extend(risk_areas)
    route_features = [
        {
            "type": "Feature",
            "properties": {
                "route_type": item["route_type"],
                "name": item["name"],
                "risk_level": item["risk_level"],
                "distance_km": item["distance_km"],
                "eta_minutes": item["eta_minutes"],
                "status": item["status"],
                "search_method": "astar_cost_surface",
                "is_simulated": True,
            },
            "geometry": {"type": "LineString", "coordinates": item["coordinates"]},
        }
        for item in routes_data
    ]
    warnings = ["上游真实火点尚未交付，本次空间分析使用明确标注的模拟输入。"] if request.input_source == "upstream_mock" else []
    if not remote_sensing["observation_count"]:
        warnings.append(
            "No remote-sensing observations are available; risk uses fireline and asset layers only."
        )
    run = SpatialAnalysisRun(
        analysis_id=analysis_id,
        event_id=event_id,
        spread_run_id=spread.run_id,
        status="completed",
        analysis_engine="python_geometry_astar",
        input_source=request.input_source,
        summary=summary,
        parameters={
            "threat_buffer_km": request.threat_buffer_km,
            "blocked_road_ids": sorted(blocked),
            "coordinate_reference": "EPSG:4326 API; local kilometer plane for A* cost calculation",
            "remote_sensing": remote_sensing,
            "risk_method": summary["risk_method"],
            "landcover_calculation": "fireline_sector_sampling",
        },
        impact_geojson={"type": "FeatureCollection", "features": impact_features},
        route_geojson={"type": "FeatureCollection", "features": route_features},
        warnings=warnings,
        is_simulated=request.input_source == "upstream_mock",
    )
    db.add(run)
    await db.flush()

    impact_models: list[SpatialImpactRecord] = []
    for item in impacts_data:
        model = SpatialImpactRecord(
            record_id=f"imp_{uuid4().hex}",
            analysis_id=analysis_id,
            event_id=event_id,
            object_id=item["object_id"],
            object_type=item["object_type"],
            name=item["name"],
            severity=item["severity"],
            affected=item["affected"],
            distance_to_fire_km=item["distance_to_fire_km"],
            population=item.get("population", 0),
            geometry=item["geometry"],
            attributes={
                "is_simulated": True,
                "risk_score": item.get("risk_score", 0),
                "risk_basis": item.get("risk_basis", "fireline_clearance"),
                "resource_capacity": item.get("resource_capacity", 0),
                "remote_sensing": remote_sensing,
            },
        )
        db.add(model)
        impact_models.append(model)

    route_models: list[EmergencyRoutePlan] = []
    for item in routes_data:
        model = EmergencyRoutePlan(
            route_id=f"ert_{uuid4().hex}",
            analysis_id=analysis_id,
            event_id=event_id,
            route_type=item["route_type"],
            name=item["name"],
            status=item["status"],
            risk_level=item["risk_level"],
            distance_km=item["distance_km"],
            eta_minutes=item["eta_minutes"],
            geometry={
                "points": [
                    {"longitude": point[0], "latitude": point[1]}
                    for point in item["coordinates"]
                ],
                "geojson": {"type": "LineString", "coordinates": item["coordinates"]},
            },
            attributes={
                "is_simulated": True,
                "start": item["start"],
                "end": item["end"],
                "diagnostics": item["diagnostics"],
            },
        )
        db.add(model)
        route_models.append(model)

    await append_timeline(
        db,
        event_id=event_id,
        event_type="spatial_analysis.completed",
        status="simulating",
        title="影响分析与路线规划完成",
        message="已根据最终火线完成受影响对象统计和 A* 应急路线规划。",
        payload={"analysis_id": analysis_id, **summary},
        broadcast=True,
    )
    await db.commit()
    await db.refresh(run)
    for item in [*impact_models, *route_models]:
        await db.refresh(item)
    await websocket_manager.broadcast_event(
        event_id,
        "spatial_analysis.completed",
        {"analysis_id": analysis_id, "summary": summary, "route_geojson": run.route_geojson},
    )
    return {"run": run, "impacts": impact_models, "routes": route_models}


async def latest_spatial_analysis(db: AsyncSession, event_id: str) -> dict[str, Any] | None:
    await get_event_or_404(db, event_id)
    result = await db.execute(
        select(SpatialAnalysisRun)
        .where(SpatialAnalysisRun.event_id == event_id)
        .order_by(desc(SpatialAnalysisRun.created_at), desc(SpatialAnalysisRun.id))
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        return None
    impacts = list(
        (
            await db.execute(
                select(SpatialImpactRecord)
                .where(SpatialImpactRecord.analysis_id == run.analysis_id)
                .order_by(SpatialImpactRecord.id)
            )
        )
        .scalars()
        .all()
    )
    routes = list(
        (
            await db.execute(
                select(EmergencyRoutePlan)
                .where(EmergencyRoutePlan.analysis_id == run.analysis_id)
                .order_by(EmergencyRoutePlan.id)
            )
        )
        .scalars()
        .all()
    )
    return {"run": run, "impacts": impacts, "routes": routes}
