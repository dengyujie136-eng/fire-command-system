from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.route_search import plan_emergency_routes


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KM_PER_DEGREE_LAT = 110.57669
KM_PER_DEGREE_LON_EQUATOR = 111.320
DEFAULT_EVENT_ID = "muli-fire-demo-001"
DEFAULT_EVENT_NAME = "木里县森林火灾演示事件"


class ForeFireDataError(ValueError):
    """Raised when a ForeFire payload is missing required decision fields."""


def load_forefire_input(file_path: str | Path) -> tuple[dict[str, Any], Path]:
    path = _resolve_path(file_path)
    if path.is_dir():
        return _load_forefire_directory(path), path
    if not path.exists():
        raise FileNotFoundError(f"ForeFire input not found: {path}")
    with path.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ForeFireDataError("ForeFire input JSON must be an object.")
    if payload.get("type") in {"FeatureCollection", "Feature"}:
        payload = _wrap_geojson_payload(payload, path)
    return payload, path


def generate_forefire_decision(
    forefire_payload: dict[str, Any],
    *,
    source_path: str | Path | None = None,
    event_id: str | None = None,
    event_name: str | None = None,
    ignition_point: dict[str, Any] | list[float] | None = None,
    weather: dict[str, Any] | None = None,
    dem: dict[str, Any] | None = None,
    resources: dict[str, Any] | None = None,
    targets: list[dict[str, Any]] | None = None,
    resource_context: dict[str, Any] | None = None,
    environment_context: dict[str, Any] | None = None,
    extra_warnings: list[str] | None = None,
    include_coordinates: bool = True,
) -> dict[str, Any]:
    parsed = parse_forefire_payload(forefire_payload, source_path=source_path)
    event_id = event_id or DEFAULT_EVENT_ID
    event_name = event_name or DEFAULT_EVENT_NAME
    provided_ignition = _coerce_point(ignition_point)
    if provided_ignition:
        parsed["ignition_point"] = provided_ignition

    warnings = _build_input_warnings(
        weather=weather,
        dem=dem,
        resources=resources,
        targets=targets,
        environment_context=environment_context,
    )
    warnings.extend(extra_warnings or [])
    if environment_context:
        warnings.extend(str(item) for item in environment_context.get("warnings", []))

    resource_inventory, used_mock_resources = _normalize_resources(resources)
    if used_mock_resources:
        warnings.append("资源数据缺失，已使用本地默认资源库存兜底。")

    warnings = _dedupe_strings(warnings)

    environment = EnvironmentAssessmentAgent().run(
        parsed,
        weather=weather,
        dem=dem,
        targets=targets,
        environment_context=environment_context,
    )
    spread = FireSpreadAgent().run(parsed)
    command = CommandDecisionAgent().run(
        environment,
        spread,
        parsed,
        weather=weather,
        resources=resource_inventory,
        resource_data_missing=resources is None,
    )
    dispatch = ResourceDispatchAgent().run(
        command.get("recommended_plan") or {},
        resource_inventory,
        parsed,
        resource_context=resources,
    )

    input_summary = _build_input_summary(parsed)
    input_summary["event_id"] = event_id
    input_summary["event_name"] = event_name
    adapter_steps = deepcopy(parsed["steps"])
    if not include_coordinates:
        for step in adapter_steps:
            step.pop("coordinates", None)

    page_packages = _build_page_packages(
        parsed=parsed,
        forefire_payload=forefire_payload,
        input_summary=input_summary,
        environment=environment,
        spread=spread,
        command=command,
        dispatch=dispatch,
        warnings=warnings,
        weather=weather,
        dem=dem,
        resources=resources,
        resource_context=resource_context,
        environment_context=environment_context,
        event_id=event_id,
        event_name=event_name,
    )

    result = {
        "task_id": parsed["task_id"],
        "event_id": event_id,
        "event_name": event_name,
        "source": parsed["source"],
        "status": "decision_generated",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_summary": input_summary,
        "agent_outputs": {
            "forefire_adapter": {
                "validated": True,
                "time_steps": adapter_steps,
                "growth_metrics": parsed["metrics"],
            },
            "environment_assessment": environment,
            "fire_spread_analysis": spread,
            "command_decision": command,
            "resource_dispatch": dispatch,
            "uav_dispatch": page_packages["uav_package"],
            "route_planning": page_packages["route_package"],
            "damage_assessment": page_packages["assessment_package"],
            "command_summary": page_packages["command_package"],
            "fusion_diagnostics": page_packages["fusion_package"],
        },
        "packages": {
            "situation_package": _build_situation_package(parsed, environment),
            "risk_package": _build_risk_package(parsed, environment, spread, warnings),
            "plan_package": _build_plan_package(command),
            "task_package": _build_task_package(dispatch),
            "feedback_package": _build_feedback_package(parsed, warnings),
            **page_packages,
        },
        "candidate_plans": command["candidate_plans"],
        "recommended_plan": command.get("recommended_plan") or {},
        "blocked_or_downgraded_plans": command["blocked_or_downgraded_plans"],
        "warnings": warnings,
    }
    return result


def parse_forefire_payload(
    payload: dict[str, Any],
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ForeFireDataError("ForeFire payload must be a JSON object.")

    task_id = _require_string(payload, "task_id")
    status = _require_string(payload, "status")
    source = _require_string(payload, "source")
    if status.lower() != "done":
        raise ForeFireDataError(f"ForeFire task status must be 'done', got: {status}")
    if source.lower() != "forefire":
        raise ForeFireDataError(f"ForeFire source must be 'forefire', got: {source}")

    geojson = payload.get("geojson")
    if not isinstance(geojson, dict):
        raise ForeFireDataError("Missing required field: geojson")
    if geojson.get("type") != "FeatureCollection":
        raise ForeFireDataError("geojson.type must be FeatureCollection.")

    features = geojson.get("features")
    if not isinstance(features, list) or not features:
        raise ForeFireDataError("geojson.features must be a non-empty list.")

    steps = [_parse_feature(feature, index) for index, feature in enumerate(features, start=1)]
    steps.sort(key=lambda item: (item["elapsed_minutes"], item["step"]))
    metrics = _calculate_growth_metrics(steps)
    ignition_point = _find_ignition_point(payload, task_id=task_id, source_path=source_path)

    return {
        "task_id": task_id,
        "status": status,
        "source": source,
        "ignition_point": ignition_point,
        "steps": steps,
        "metrics": metrics,
        "raw_geojson_type": geojson.get("type"),
    }


def check_safety_rules(
    plan: dict[str, Any],
    fire_summary: dict[str, Any],
    weather: dict[str, Any] | None = None,
    resources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    risk_level = fire_summary.get("risk_level", "low")
    final_area = float(fire_summary.get("final_area_km2", 0.0) or 0.0)
    accelerated = bool(fire_summary.get("accelerated_spread"))
    priority_directions = fire_summary.get("priority_protection_directions", [])
    flags: list[str] = []
    warnings: list[str] = []
    reasons: list[str] = []
    downgraded = False
    blocked = False

    if final_area > 8.0 and risk_level not in {"high", "extreme"}:
        risk_level = "high"
        flags.append("risk_floor_high_by_area")

    if accelerated:
        flags.append("accelerated_spread")
        reasons.append("最近一个时间段的火场扩张明显加快。")

    if priority_directions:
        flags.append("priority_direction_protection")
        reasons.append(f"重点保护方向：{'、'.join(_direction_label(item) for item in priority_directions)}。")

    wind_speed = _as_float((weather or {}).get("wind_speed"))
    task_blob = json.dumps(plan.get("tasks", []), ensure_ascii=True).lower()
    if wind_speed is not None and wind_speed > 10.0 and "uav" in task_blob and "low" in task_blob:
        downgraded = True
        flags.append("uav_low_altitude_limited_by_wind")
        reasons.append("风速超过 10 m/s，低空无人机巡查任务需要降级或改为中高空航线。")

    if resources is not None and _resources_insufficient(resources, risk_level):
        downgraded = True
        flags.append("resource_insufficient")
        reasons.append("当前可用资源低于该风险等级的最低调度要求。")

    has_evacuation = "evac" in task_blob or "evacuation" in task_blob
    has_key_protection = "protect" in task_blob or "key_target" in task_blob or "priority_target" in task_blob
    if risk_level in {"high", "extreme"} and not (has_evacuation or has_key_protection):
        downgraded = True
        flags.append("missing_evacuation_or_key_target_protection")
        reasons.append("高风险火情方案必须包含疏散安排或重点目标保护。")

    if not weather:
        warnings.append("气象数据缺失，安全校核已使用 ForeFire 火线和默认规则兜底。")
    if resources is None:
        warnings.append("资源数据缺失，资源校核已使用本地默认库存兜底。")

    status_adjustment = "blocked" if blocked else "downgraded" if downgraded else "available"
    return {
        "risk_level": risk_level,
        "status_adjustment": status_adjustment,
        "flags": flags,
        "reasons": reasons,
        "warnings": warnings,
    }


class EnvironmentAssessmentAgent:
    def run(
        self,
        parsed: dict[str, Any],
        *,
        weather: dict[str, Any] | None = None,
        dem: dict[str, Any] | None = None,
        targets: list[dict[str, Any]] | None = None,
        environment_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metrics = parsed["metrics"]
        protection_focus = _protection_focus(metrics, targets)
        return {
            "agent": "EnvironmentAssessmentAgent",
            "current_fire_area_km2": metrics["final_area_km2"],
            "area_growth_km2": metrics["area_growth_km2"],
            "avg_growth_km2_per_hour": metrics["avg_growth_km2_per_hour"],
            "latest_growth_km2_per_hour": metrics["latest_growth_km2_per_hour"],
            "spread_direction": metrics["main_spread_direction"],
            "bbox_expansion": metrics["bbox_expansion_km"],
            "fire_risk_level": metrics["risk_level"],
            "environment_risk_summary": _risk_summary(metrics, weather, dem, environment_context),
            "protection_focus": protection_focus,
            "environment_context": environment_context,
        }


class FireSpreadAgent:
    def run(self, parsed: dict[str, Any]) -> dict[str, Any]:
        metrics = parsed["metrics"]
        return {
            "agent": "FireSpreadAgent",
            "future_6h_summary": (
                f"ForeFire 预测火场将在 {metrics['duration_hours']} 小时内从 "
                f"{metrics['initial_area_km2']} 平方公里扩张到 {metrics['final_area_km2']} 平方公里。"
            ),
            "area_growth_curve": [
                {"elapsed_minutes": step["elapsed_minutes"], "area_km2": step["area_km2"]}
                for step in parsed["steps"]
            ],
            "final_bbox": metrics["final_bbox"],
            "high_risk_periods": [
                {
                    **interval,
                    "start_minutes": interval["from_minutes"],
                    "end_minutes": interval["to_minutes"],
                    "reason": "该时段面积增长率超过高风险阈值。",
                }
                for interval in metrics["area_growth_intervals"]
                if interval["growth_rate_km2_per_hour"] >= 1.5
            ],
            "accelerated_spread": metrics["accelerated_spread"],
            "latest_spread_intensity": metrics["latest_spread_intensity"],
            "main_spread_direction": metrics["main_spread_direction"],
        }


class CommandDecisionAgent:
    def run(
        self,
        environment: dict[str, Any],
        spread: dict[str, Any],
        parsed: dict[str, Any],
        *,
        weather: dict[str, Any] | None = None,
        resources: dict[str, Any] | None = None,
        resource_data_missing: bool = False,
    ) -> dict[str, Any]:
        metrics = parsed["metrics"]
        fire_summary = {
            "risk_level": environment["fire_risk_level"],
            "final_area_km2": metrics["final_area_km2"],
            "accelerated_spread": spread["accelerated_spread"],
            "priority_protection_directions": metrics["priority_protection_directions"],
        }
        plans = _build_candidate_plans(metrics)
        for plan in plans:
            safety = check_safety_rules(plan, fire_summary, weather=weather, resources=resources)
            plan["risk_level"] = safety["risk_level"]
            plan["score"] = _score_plan(plan)
            plan["safety_rules"] = safety
            if safety["status_adjustment"] != "available":
                plan["status"] = safety["status_adjustment"]
                plan["reasons"].extend(safety["reasons"])

        available = [plan for plan in plans if plan["status"] == "available"]
        recommended = max(available, key=lambda item: item["score"], default=None)
        if recommended is not None:
            recommended["status"] = "recommended"
            recommended["reasons"].append("该方案在满足硬性安全规则的候选方案中综合评分最高。")

        blocked_or_downgraded = [
            plan for plan in plans if plan["status"] in {"blocked", "downgraded"}
        ]
        return {
            "agent": "CommandDecisionAgent",
            "scoring_formula": (
                "score = 0.30*safety_margin + 0.25*response_efficiency "
                "+ 0.20*resource_match + 0.20*expected_control_effect "
                "- 0.15*execution_difficulty"
            ),
            "resource_data_missing": resource_data_missing,
            "candidate_plans": plans,
            "recommended_plan": recommended,
            "blocked_or_downgraded_plans": blocked_or_downgraded,
        }


class ResourceDispatchAgent:
    def run(
        self,
        recommended_plan: dict[str, Any],
        resources: dict[str, Any],
        parsed: dict[str, Any],
        resource_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metrics = parsed["metrics"]
        plan_id = recommended_plan.get("plan_id", "NONE")
        direction = metrics["main_spread_direction"]
        bbox = metrics["final_bbox"]
        direction_name = _direction_label(direction)
        crew_owner = _preferred_personnel_name(resource_context, "fire") or "北线森林消防一队"
        logistics_owner = _preferred_personnel_name(resource_context, "logistics") or "后勤保障组"
        evac_owner = _preferred_personnel_name(resource_context, "evacuation") or "疏散与交通管制组"
        water_source = _preferred_named_item(resource_context, "water_sources") or "最近可达水源点"
        tasks = [
            {
                "task_id": "TASK-FIRE-001",
                "owner": crew_owner,
                "action": f"在{direction_name}建立分段压制线并保护重点目标",
                "target": f"{direction_name}火线外缘，最终 bbox {bbox}",
                "priority": "critical",
                "eta_minutes": 20,
                "status": "planned",
                "reason": "最新增长率处于高风险区间，最终过火面积已超过重点处置阈值。",
            },
            {
                "task_id": "TASK-UAV-001",
                "owner": "无人机侦查组",
                "action": "执行火线热成像巡查和边界复核",
                "target": f"{direction_name}扩张边界",
                "priority": "high",
                "eta_minutes": 10,
                "status": "planned",
                "reason": "地面队伍进入活动火翼前，需要先更新火线边界和安全通道。",
            },
            {
                "task_id": "TASK-WATER-001",
                "owner": logistics_owner,
                "action": "前置水车、水泵和补给接驳点",
                "target": water_source,
                "priority": "high",
                "eta_minutes": 25,
                "status": "planned",
                "reason": "压制线和重点目标保护需要持续水源保障。",
            },
            {
                "task_id": "TASK-EVAC-001",
                "owner": evac_owner,
                "action": "准备疏散通道和火场警戒隔离区",
                "target": f"{direction_name}风险影响区",
                "priority": "critical",
                "eta_minutes": 15,
                "status": "planned",
                "reason": "高风险火情必须同步建立疏散、警戒和重点目标保护安排。",
            },
            {
                "task_id": "TASK-CMD-001",
                "owner": "现场指挥部",
                "action": "复核方案并准备下一轮 ForeFire 预测",
                "target": plan_id,
                "priority": "medium",
                "eta_minutes": 30,
                "status": "planned",
                "reason": "下一次火线更新后需要重新校核路径、人员和无人机任务。",
            },
        ]
        return {
            "agent": "ResourceDispatchAgent",
            "resource_inventory": resources,
            "recommended_plan_id": plan_id,
            "tasks": tasks,
            "inventory_changes": _build_inventory_changes(resources, metrics),
            "personnel_assignments": _build_personnel_assignments(resource_context, tasks),
        }


def _resolve_path(file_path: str | Path) -> Path:
    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _load_forefire_directory(path: Path) -> dict[str, Any]:
    front_files = sorted(path.glob("front_t*.geojson"), key=_front_file_seconds)
    if not front_files:
        raise FileNotFoundError(f"No front_t*.geojson files found in: {path}")
    features: list[dict[str, Any]] = []
    for index, front_file in enumerate(front_files, start=1):
        with front_file.open("r", encoding="utf-8-sig") as f:
            geojson = json.load(f)
        file_features = _coerce_geojson_features(geojson, front_file)
        elapsed_seconds = _front_file_seconds(front_file)
        for feature in file_features:
            props = feature.setdefault("properties", {})
            props.setdefault("step", index)
            props.setdefault("elapsed_seconds", elapsed_seconds)
            props.setdefault("elapsed_minutes", round(elapsed_seconds / 60))
            props.setdefault("source", "forefire")
            props.setdefault("output_file", front_file.name)
            features.append(feature)
    return {
        "task_id": path.name,
        "status": "done",
        "source": "forefire",
        "geojson": {"type": "FeatureCollection", "features": features},
    }


def _wrap_geojson_payload(geojson: dict[str, Any], path: Path) -> dict[str, Any]:
    features = _coerce_geojson_features(geojson, path)
    elapsed_seconds = _front_file_seconds(path)
    for index, feature in enumerate(features, start=1):
        props = feature.setdefault("properties", {})
        props.setdefault("step", index)
        if elapsed_seconds:
            props.setdefault("elapsed_seconds", elapsed_seconds)
            props.setdefault("elapsed_minutes", round(elapsed_seconds / 60))
        props.setdefault("source", "forefire")
        props.setdefault("output_file", path.name)
    return {
        "task_id": path.parent.name,
        "status": "done",
        "source": "forefire",
        "geojson": {"type": "FeatureCollection", "features": features},
    }


def _coerce_geojson_features(geojson: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    if geojson.get("type") == "FeatureCollection":
        features = geojson.get("features")
        if not isinstance(features, list) or not features:
            raise ForeFireDataError(f"GeoJSON file has no features: {path}")
        return features
    if geojson.get("type") == "Feature":
        return [geojson]
    raise ForeFireDataError(f"Unsupported GeoJSON type in {path}: {geojson.get('type')}")


def _front_file_seconds(path: Path) -> int:
    match = re.search(r"front_t(\d+)", path.name)
    return int(match.group(1)) if match else 0


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ForeFireDataError(f"Missing required field: {key}")
    return value.strip()


def _parse_feature(feature: Any, index: int) -> dict[str, Any]:
    if not isinstance(feature, dict):
        raise ForeFireDataError(f"geojson.features[{index}] must be an object.")
    props = feature.get("properties")
    if not isinstance(props, dict):
        raise ForeFireDataError(f"geojson.features[{index}].properties is required.")
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict):
        raise ForeFireDataError(f"geojson.features[{index}].geometry is required.")
    geometry_type = geometry.get("type")
    if geometry_type not in {"MultiPolygon", "Polygon"}:
        raise ForeFireDataError(
            f"geojson.features[{index}].geometry.type must be Polygon or MultiPolygon."
        )
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise ForeFireDataError(f"geojson.features[{index}].geometry.coordinates is required.")

    elapsed_minutes = _elapsed_minutes(props)
    points = _flatten_points(coordinates)
    if not points:
        raise ForeFireDataError(f"geojson.features[{index}] has no coordinate points.")

    provided_area = _first_number(feature.get("area_km2"), props.get("area_km2"), props.get("area"))
    computed_area = _geometry_area_km2(geometry_type, coordinates)
    area_km2 = round(provided_area if provided_area is not None else computed_area, 6)

    return {
        "step": int(_first_number(props.get("step"), index) or index),
        "elapsed_seconds": int(_first_number(props.get("elapsed_seconds"), elapsed_minutes * 60) or 0),
        "elapsed_minutes": int(elapsed_minutes),
        "output_file": str(props.get("output_file") or ""),
        "geometry_type": str(geometry_type),
        "coordinates": coordinates,
        "bbox": _bbox(points),
        "area_km2": area_km2,
        "point_count": len(points),
    }


def _elapsed_minutes(props: dict[str, Any]) -> int:
    minutes = _first_number(props.get("elapsed_minutes"))
    if minutes is not None:
        return int(round(minutes))
    seconds = _first_number(props.get("elapsed_seconds"))
    if seconds is not None:
        return int(round(seconds / 60))
    output_file = str(props.get("output_file") or "")
    match = re.search(r"front_t(\d+)", output_file)
    if match:
        return int(round(int(match.group(1)) / 60))
    raise ForeFireDataError("Feature is missing elapsed_minutes, elapsed_seconds, and output_file time.")


def _first_number(*values: Any) -> float | None:
    for value in values:
        number = _as_float(value)
        if number is not None:
            return number
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _flatten_points(node: Any) -> list[list[float]]:
    points: list[list[float]] = []

    def walk(value: Any) -> None:
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            points.append([float(value[0]), float(value[1])])
            return
        if isinstance(value, list):
            for item in value:
                walk(item)

    walk(node)
    return points


def _bbox(points: list[list[float]]) -> list[float]:
    return [
        round(min(point[0] for point in points), 6),
        round(min(point[1] for point in points), 6),
        round(max(point[0] for point in points), 6),
        round(max(point[1] for point in points), 6),
    ]


def _geometry_area_km2(geometry_type: str, coordinates: list[Any]) -> float:
    if geometry_type == "Polygon":
        return _polygon_area_km2(coordinates)
    return sum(_polygon_area_km2(polygon) for polygon in coordinates)


def _polygon_area_km2(polygon: list[Any]) -> float:
    if not polygon:
        return 0.0
    outer = _ring_area_km2(polygon[0])
    holes = sum(_ring_area_km2(ring) for ring in polygon[1:])
    return max(outer - holes, 0.0)


def _ring_area_km2(ring: list[Any]) -> float:
    points = [[float(point[0]), float(point[1])] for point in ring if isinstance(point, list) and len(point) >= 2]
    if len(points) < 3:
        return 0.0
    mean_lat = math.radians(sum(point[1] for point in points) / len(points))
    km_per_degree_lon = KM_PER_DEGREE_LON_EQUATOR * math.cos(mean_lat)
    projected = [(point[0] * km_per_degree_lon, point[1] * KM_PER_DEGREE_LAT) for point in points]
    signed_area = 0.0
    for (x1, y1), (x2, y2) in zip(projected, projected[1:] + projected[:1]):
        signed_area += x1 * y2 - x2 * y1
    return abs(signed_area) / 2.0


def _calculate_growth_metrics(steps: list[dict[str, Any]]) -> dict[str, Any]:
    initial = steps[0]
    final = steps[-1]
    duration_hours = round(final["elapsed_minutes"] / 60.0, 6)
    area_growth = round(final["area_km2"] - initial["area_km2"], 6)
    intervals = _area_growth_intervals(steps)
    latest_rate = intervals[-1]["growth_rate_km2_per_hour"] if intervals else 0.0
    accelerated = _accelerated_spread(intervals)
    center_delta = _bbox_center_delta_km(initial["bbox"], final["bbox"])
    bbox_expansion = _bbox_expansion_km(initial["bbox"], final["bbox"])
    priority_directions = _priority_directions(bbox_expansion)
    direction = _direction_from_delta(center_delta)
    risk_level = _risk_level(final["area_km2"], latest_rate, accelerated)
    return {
        "duration_hours": duration_hours,
        "step_count": len(steps),
        "interval_minutes": _typical_interval_minutes(steps),
        "initial_area_km2": initial["area_km2"],
        "final_area_km2": final["area_km2"],
        "area_growth_km2": area_growth,
        "area_growth_intervals": intervals,
        "avg_growth_km2_per_hour": round(area_growth / duration_hours, 6) if duration_hours else 0.0,
        "latest_growth_km2_per_hour": latest_rate,
        "latest_spread_intensity": _spread_intensity(latest_rate),
        "accelerated_spread": accelerated,
        "main_spread_direction": direction,
        "center_delta_km": center_delta,
        "bbox_expansion_km": bbox_expansion,
        "priority_protection_directions": priority_directions,
        "final_bbox": final["bbox"],
        "risk_level": risk_level,
    }


def _area_growth_intervals(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    intervals: list[dict[str, Any]] = []
    previous_minutes = 0
    previous_area = 0.0
    for step in steps:
        minutes_delta = max(step["elapsed_minutes"] - previous_minutes, 1)
        area_delta = round(step["area_km2"] - previous_area, 6)
        hours_delta = minutes_delta / 60.0
        intervals.append(
            {
                "from_minutes": previous_minutes,
                "to_minutes": step["elapsed_minutes"],
                "area_growth_km2": area_delta,
                "growth_rate_km2_per_hour": round(area_delta / hours_delta, 6),
            }
        )
        previous_minutes = step["elapsed_minutes"]
        previous_area = step["area_km2"]
    return intervals


def _accelerated_spread(intervals: list[dict[str, Any]]) -> bool:
    if len(intervals) < 3:
        return False
    previous = intervals[-2]["area_growth_km2"]
    latest = intervals[-1]["area_growth_km2"]
    return latest > max(previous * 1.25, previous + 0.5)


def _typical_interval_minutes(steps: list[dict[str, Any]]) -> int:
    if not steps:
        return 0
    deltas = [steps[0]["elapsed_minutes"]]
    deltas.extend(
        steps[index]["elapsed_minutes"] - steps[index - 1]["elapsed_minutes"]
        for index in range(1, len(steps))
    )
    deltas = sorted(delta for delta in deltas if delta > 0)
    return int(deltas[len(deltas) // 2]) if deltas else 0


def _bbox_center_delta_km(first_bbox: list[float], final_bbox: list[float]) -> dict[str, float]:
    first_center = [(first_bbox[0] + first_bbox[2]) / 2.0, (first_bbox[1] + first_bbox[3]) / 2.0]
    final_center = [(final_bbox[0] + final_bbox[2]) / 2.0, (final_bbox[1] + final_bbox[3]) / 2.0]
    mean_lat = math.radians((first_center[1] + final_center[1]) / 2.0)
    east_km = (final_center[0] - first_center[0]) * KM_PER_DEGREE_LON_EQUATOR * math.cos(mean_lat)
    north_km = (final_center[1] - first_center[1]) * KM_PER_DEGREE_LAT
    return {"east_km": round(east_km, 6), "north_km": round(north_km, 6)}


def _bbox_expansion_km(first_bbox: list[float], final_bbox: list[float]) -> dict[str, float]:
    mean_lat = math.radians((first_bbox[1] + first_bbox[3] + final_bbox[1] + final_bbox[3]) / 4.0)
    km_per_degree_lon = KM_PER_DEGREE_LON_EQUATOR * math.cos(mean_lat)
    return {
        "west": round(max(first_bbox[0] - final_bbox[0], 0.0) * km_per_degree_lon, 6),
        "east": round(max(final_bbox[2] - first_bbox[2], 0.0) * km_per_degree_lon, 6),
        "south": round(max(first_bbox[1] - final_bbox[1], 0.0) * KM_PER_DEGREE_LAT, 6),
        "north": round(max(final_bbox[3] - first_bbox[3], 0.0) * KM_PER_DEGREE_LAT, 6),
    }


def _priority_directions(expansion: dict[str, float]) -> list[str]:
    if not expansion:
        return []
    max_value = max(expansion.values())
    if max_value <= 0:
        return []
    return [direction for direction, value in expansion.items() if value >= max_value * 0.75]


def _direction_from_delta(delta: dict[str, float]) -> str:
    east = delta.get("east_km", 0.0)
    north = delta.get("north_km", 0.0)
    if abs(east) < 0.05 and abs(north) < 0.05:
        return "stable"
    horizontal = "east" if east > 0 else "west"
    vertical = "north" if north > 0 else "south"
    if abs(east) >= abs(north) * 1.5:
        return horizontal
    if abs(north) >= abs(east) * 1.5:
        return vertical
    return f"{vertical}-{horizontal}"


def _risk_level(final_area: float, latest_rate: float, accelerated: bool) -> str:
    if final_area >= 15.0 or latest_rate >= 3.0:
        return "extreme"
    if final_area > 8.0 or latest_rate >= 1.5 or accelerated:
        return "high"
    if final_area >= 3.0 or latest_rate >= 0.8:
        return "moderate"
    return "low"


def _spread_intensity(growth_rate: float) -> str:
    if growth_rate >= 3.0:
        return "extreme"
    if growth_rate >= 1.5:
        return "high"
    if growth_rate >= 0.5:
        return "moderate"
    return "low"


def _find_ignition_point(
    payload: dict[str, Any],
    *,
    task_id: str,
    source_path: str | Path | None,
) -> list[float] | None:
    for key in ("ignition_point", "fire_point", "ignition"):
        point = _coerce_point(payload.get(key))
        if point:
            return point
    for path in _ignition_candidates(task_id, source_path):
        if path.exists():
            text = path.read_text(encoding="utf-8-sig").strip()
            numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
            if len(numbers) >= 2:
                return [round(float(numbers[0]), 6), round(float(numbers[1]), 6)]
    return None


def _coerce_point(value: Any) -> list[float] | None:
    if isinstance(value, list) and len(value) >= 2:
        lon = _as_float(value[0])
        lat = _as_float(value[1])
        if lon is not None and lat is not None:
            return [round(lon, 6), round(lat, 6)]
    if isinstance(value, dict):
        lon = _first_number(value.get("lon"), value.get("lng"), value.get("longitude"))
        lat = _first_number(value.get("lat"), value.get("latitude"))
        if lon is not None and lat is not None:
            return [round(lon, 6), round(lat, 6)]
    return None


def _ignition_candidates(task_id: str, source_path: str | Path | None) -> list[Path]:
    candidates: list[Path] = []
    if source_path is not None:
        path = _resolve_path(source_path)
        base = path if path.is_dir() else path.parent
        candidates.extend([base / "ignition.txt", base / task_id / "ignition.txt"])
    candidates.append(PROJECT_ROOT / "data" / "forefire-output" / task_id / "ignition.txt")
    return candidates


def _build_input_warnings(
    *,
    weather: dict[str, Any] | None,
    dem: dict[str, Any] | None,
    resources: dict[str, Any] | None,
    targets: list[dict[str, Any]] | None,
    environment_context: dict[str, Any] | None = None,
) -> list[str]:
    warnings: list[str] = []
    if weather is None:
        if environment_context and environment_context.get("weather", {}).get("available"):
            warnings.append("请求体未提供实时气象数值，已接入本地 weather_data.nc 文件级摘要。")
        else:
            warnings.append("气象数据缺失，决策已基于 ForeFire 火线和默认规则生成。")
    if dem is None and not (environment_context and environment_context.get("dem", {}).get("available")):
        warnings.append("DEM 数据缺失，暂未应用地形坡度约束。")
    if resources is None:
        warnings.append("资源数据缺失，已使用本地默认资源库存。")
    if targets is None:
        warnings.append("重点目标数据缺失，已根据火场 bbox 扩张方向推断优先保护区域。")
    return warnings


def _normalize_resources(resources: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    if not resources:
        return (
            {
                "fire_crews": 6,
                "uavs": 3,
                "water_tankers": 4,
                "evacuation_buses": 3,
                "command_staff": 2,
                "medical_teams": 2,
                "source": "mock",
            },
            True,
        )
    resource_inventory = _list_value(resources, "resource_inventory")
    personnel_units = _list_value(resources, "personnel_units")
    uav_assets = _list_value(resources, "uav_assets")
    vehicles = _list_value(resources, "vehicles")
    normalized = {
        "fire_crews": int(
            _resource_count(resources, "fire_crews", "firefighters", "crews")
            or _personnel_role_count(personnel_units, "fire_crew", "firefighter", "消防")
            or 0
        ),
        "uavs": int(
            _resource_count(resources, "uavs", "drones")
            or _available_item_count(uav_assets, total_key="uav_id")
            or 0
        ),
        "water_tankers": int(
            _resource_count(resources, "water_tankers", "tankers", "water")
            or _vehicle_type_count(vehicles, "water", "tanker", "水")
            or _inventory_category_count(resource_inventory, "water", "pump", "水")
            or 0
        ),
        "evacuation_buses": int(
            _resource_count(resources, "evacuation_buses", "buses")
            or _vehicle_type_count(vehicles, "bus", "evacuation", "客车", "疏散")
            or 0
        ),
        "command_staff": int(
            _resource_count(resources, "command_staff", "commanders")
            or _personnel_role_count(personnel_units, "command", "commander", "指挥")
            or 0
        ),
        "medical_teams": int(
            _resource_count(resources, "medical_teams", "medical")
            or _personnel_role_count(personnel_units, "medical", "medic", "医疗", "救护")
            or 0
        ),
        "source": "provided",
        "raw_context_counts": {
            "resource_inventory": len(resource_inventory),
            "personnel_units": len(personnel_units),
            "uav_assets": len(uav_assets),
            "vehicles": len(vehicles),
            "water_sources": len(_list_value(resources, "water_sources")),
            "shelters": len(_list_value(resources, "shelters")),
            "important_targets": len(_list_value(resources, "important_targets")),
            "road_segments": len(_list_value(resources, "road_segments")),
        },
    }
    return normalized, False


def _resource_count(resources: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = resources.get(key)
        number = _as_float(value)
        if number is not None:
            return number
    items = resources.get("items")
    if isinstance(items, list):
        total = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "").lower()
            if any(key.rstrip("s") in item_type for key in keys):
                total += int(_first_number(item.get("count"), 1) or 1)
        return float(total) if total else None
    return None


def _resources_insufficient(resources: dict[str, Any], risk_level: str) -> bool:
    if risk_level in {"high", "extreme"}:
        minimums = {"fire_crews": 4, "uavs": 1, "water_tankers": 2, "evacuation_buses": 1}
    else:
        minimums = {"fire_crews": 2, "uavs": 1, "water_tankers": 1}
    return any(float(resources.get(key, 0) or 0) < minimum for key, minimum in minimums.items())


def _build_input_summary(parsed: dict[str, Any]) -> dict[str, Any]:
    metrics = parsed["metrics"]
    return {
        "duration_hours": metrics["duration_hours"],
        "steps": metrics["step_count"],
        "interval_minutes": metrics["interval_minutes"],
        "ignition_point": parsed["ignition_point"],
        "initial_area_km2": metrics["initial_area_km2"],
        "final_area_km2": metrics["final_area_km2"],
        "area_growth_km2": metrics["area_growth_km2"],
        "avg_growth_km2_per_hour": metrics["avg_growth_km2_per_hour"],
        "latest_growth_km2_per_hour": metrics["latest_growth_km2_per_hour"],
        "final_bbox": metrics["final_bbox"],
        "risk_level": metrics["risk_level"],
        "time_steps": [
            {
                "step": step["step"],
                "elapsed_minutes": step["elapsed_minutes"],
                "output_file": step["output_file"],
                "geometry_type": step["geometry_type"],
                "point_count": step["point_count"],
                "bbox": step["bbox"],
                "area_km2": step["area_km2"],
            }
            for step in parsed["steps"]
        ],
    }


def _risk_summary(
    metrics: dict[str, Any],
    weather: dict[str, Any] | None,
    dem: dict[str, Any] | None,
    environment_context: dict[str, Any] | None = None,
) -> str:
    parts = [
        f"最终过火面积约 {metrics['final_area_km2']} 平方公里。",
        f"最新增长率约 {metrics['latest_growth_km2_per_hour']} 平方公里/小时。",
        f"主扩散方向为{_direction_label(metrics['main_spread_direction'])}。",
    ]
    if metrics["accelerated_spread"]:
        parts.append("最近时段火势呈加速扩张趋势。")
    if weather is None:
        if environment_context and environment_context.get("weather", {}).get("available"):
            parts.append("本地气象 NetCDF 已接入，但当前未解析具体风速风向，建议联调时继续传入实时 weather。")
        else:
            parts.append("缺少实时气象数据，风驱风险仍需现场复核。")
    if dem is None and not (environment_context and environment_context.get("dem", {}).get("available")):
        parts.append("缺少 DEM 地形数据，坡度和通行阻力尚未参与计算。")
    elif environment_context and environment_context.get("dem", {}).get("available"):
        parts.append("本地 DEM 数据已接入文件级摘要，路径规划已按火场 bbox 做绕行约束。")
    return " ".join(parts)


def _protection_focus(metrics: dict[str, Any], targets: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    focus = [
        {
            "direction": direction,
            "direction_name": _direction_label(direction),
            "priority": "critical",
            "reason": f"火场 bbox 在{_direction_label(direction)}扩张明显。",
        }
        for direction in metrics["priority_protection_directions"]
    ]
    if targets:
        focus.extend(
            {
                "target_id": str(target.get("target_id") or target.get("id") or "target"),
                "name": str(target.get("name") or "重点保护目标"),
                "direction": str(target.get("direction") or "unknown"),
                "priority": str(target.get("priority") or "high"),
                "reason": "前端或资源上下文提供的重点目标，需要纳入保护序列。",
            }
            for target in targets[:5]
        )
    return focus


def _build_candidate_plans(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    target_direction = metrics["main_spread_direction"]
    priority = "、".join(_direction_label(item) for item in metrics["priority_protection_directions"]) or _direction_label(target_direction)
    return [
        {
            "plan_id": "PLAN-A",
            "name": "下风向与重点目标优先保护方案",
            "strategy": "在最快扩张方向前方建立保护阵地，同步疏散受威胁区域。",
            "target_area": f"{priority}方向重点保护区，最终 bbox {metrics['final_bbox']}",
            "risk_level": metrics["risk_level"],
            "safety_margin": 82,
            "response_efficiency": 78,
            "resource_match": 74,
            "expected_control_effect": 80,
            "execution_difficulty": 52,
            "score": 0.0,
            "status": "available",
            "reasons": [
                "方案匹配 ForeFire 推断的主要扩散方向，并包含重点目标保护。",
            ],
            "tasks": [
                {"type": "protect_key_targets", "action": "向重点目标缓冲区部署消防力量"},
                {"type": "evacuation", "action": "在最终火场 bbox 外侧准备疏散通道"},
                {"type": "uav_recon", "action": "使用无人机中空巡查活动火线"},
                {"type": "water_supply", "action": "在安全接近点前置水车和水泵"},
            ],
        },
        {
            "plan_id": "PLAN-B",
            "name": "外围火线分段压制方案",
            "strategy": "把最终火线外围划分为若干压制段，从安全边界逐段推进。",
            "target_area": f"最终 bbox {metrics['final_bbox']} 外围火线",
            "risk_level": metrics["risk_level"],
            "safety_margin": 60,
            "response_efficiency": 70,
            "resource_match": 68,
            "expected_control_effect": 76,
            "execution_difficulty": 72,
            "score": 0.0,
            "status": "available",
            "reasons": [
                "可降低外围火线继续扩张概率，但必须补充疏散或重点目标保护安排。",
            ],
            "tasks": [
                {"type": "perimeter_suppression", "action": "按火线分段安排地面队伍压制"},
                {"type": "water_line", "action": "在可通行外围段布设水带线"},
            ],
        },
        {
            "plan_id": "PLAN-C",
            "name": "无人机侦查、疏散与水源保障方案",
            "strategy": "先刷新火线情报，再疏散暴露区域，并同步锁定水源补给。",
            "target_area": f"{_direction_label(target_direction)}扩散走廊与疏散出口",
            "risk_level": metrics["risk_level"],
            "safety_margin": 78,
            "response_efficiency": 72,
            "resource_match": 70,
            "expected_control_effect": 70,
            "execution_difficulty": 48,
            "score": 0.0,
            "status": "available",
            "reasons": [
                "在保持疏散和后勤覆盖的同时，优先提升火线态势感知。",
            ],
            "tasks": [
                {"type": "low_altitude_uav_recon", "action": "风速允许时对活动火翼做低空复核"},
                {"type": "evacuation", "action": "将暴露人员转移出扩散走廊"},
                {"type": "water_supply", "action": "确认水泵和水车往返补给路线"},
                {"type": "command_review", "action": "现场执行前复核路线安全"},
            ],
        },
    ]


def _score_plan(plan: dict[str, Any]) -> float:
    return round(
        0.30 * float(plan["safety_margin"])
        + 0.25 * float(plan["response_efficiency"])
        + 0.20 * float(plan["resource_match"])
        + 0.20 * float(plan["expected_control_effect"])
        - 0.15 * float(plan["execution_difficulty"]),
        2,
    )


def _build_situation_package(parsed: dict[str, Any], environment: dict[str, Any]) -> dict[str, Any]:
    metrics = parsed["metrics"]
    return {
        "task_id": parsed["task_id"],
        "source": parsed["source"],
        "current_area_km2": metrics["final_area_km2"],
        "duration_hours": metrics["duration_hours"],
        "spread_direction": environment["spread_direction"],
        "final_bbox": metrics["final_bbox"],
        "summary": environment["environment_risk_summary"],
    }


def _build_risk_package(
    parsed: dict[str, Any],
    environment: dict[str, Any],
    spread: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    metrics = parsed["metrics"]
    return {
        "risk_level": environment["fire_risk_level"],
        "accelerated_spread": spread["accelerated_spread"],
        "latest_spread_intensity": metrics["latest_spread_intensity"],
        "high_risk_periods": spread["high_risk_periods"],
        "priority_protection_directions": metrics["priority_protection_directions"],
        "warnings": warnings,
    }


def _build_plan_package(command: dict[str, Any]) -> dict[str, Any]:
    recommended = command.get("recommended_plan") or {}
    return {
        "plan_count": len(command.get("candidate_plans", [])),
        "recommended_plan_id": recommended.get("plan_id"),
        "recommended_score": recommended.get("score"),
        "blocked_or_downgraded_plan_ids": [
            plan["plan_id"] for plan in command.get("blocked_or_downgraded_plans", [])
        ],
    }


def _build_task_package(dispatch: dict[str, Any]) -> dict[str, Any]:
    tasks = dispatch.get("tasks", [])
    return {
        "task_count": len(tasks),
        "critical_tasks": [task for task in tasks if task.get("priority") == "critical"],
        "tasks": tasks,
    }


def _build_feedback_package(parsed: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    interval = parsed["metrics"]["interval_minutes"]
    return {
        "next_forefire_update_minutes": interval,
        "warnings": warnings,
        "recommended_feedback": [
            "执行无人机任务前刷新实时气象输入。",
            "补充 DEM、燃料和重点目标图层后复核保护区。",
            "下一次 ForeFire 火线输出后重新生成处置决策。",
        ],
    }


def _build_page_packages(
    *,
    parsed: dict[str, Any],
    forefire_payload: dict[str, Any],
    input_summary: dict[str, Any],
    environment: dict[str, Any],
    spread: dict[str, Any],
    command: dict[str, Any],
    dispatch: dict[str, Any],
    warnings: list[str],
    weather: dict[str, Any] | None,
    dem: dict[str, Any] | None,
    resources: dict[str, Any] | None,
    resource_context: dict[str, Any] | None,
    environment_context: dict[str, Any] | None,
    event_id: str | None,
    event_name: str | None,
) -> dict[str, Any]:
    metrics = parsed["metrics"]
    bbox = metrics["final_bbox"]
    ignition = parsed.get("ignition_point") or _bbox_center(bbox)
    uav_package = _build_uav_package(parsed, resources)
    route_package = _build_route_package(parsed, resources, environment_context=environment_context)
    resource_package = _build_resource_package(dispatch, resources)
    assessment_package = _build_assessment_package(parsed, resources)
    command_package = _build_command_package(
        input_summary,
        command,
        dispatch,
        uav_package,
        route_package,
        resource_package,
        assessment_package,
        resources,
        event_name=event_name,
    )
    fusion_package = _build_fusion_package(
        forefire_payload=forefire_payload,
        warnings=warnings,
        weather=weather,
        dem=dem,
        resources=resources,
        environment_context=environment_context,
    )
    map_package = _build_map_package(
        parsed=parsed,
        forefire_payload=forefire_payload,
        ignition=ignition,
        uav_package=uav_package,
        route_package=route_package,
    )
    environment_package = {
        "event_id": event_id,
        "event_name": event_name,
        "ignition_point": ignition,
        "weather": weather,
        "dem": dem,
        "local_environment": environment_context,
        "resource_context_loaded": bool(resource_context),
        "summary": environment.get("environment_risk_summary"),
    }
    return {
        "map_package": map_package,
        "uav_package": uav_package,
        "route_package": route_package,
        "resource_package": resource_package,
        "assessment_package": assessment_package,
        "command_package": command_package,
        "fusion_package": fusion_package,
        "environment_package": environment_package,
    }


def _build_map_package(
    *,
    parsed: dict[str, Any],
    forefire_payload: dict[str, Any],
    ignition: list[float] | None,
    uav_package: dict[str, Any],
    route_package: dict[str, Any],
) -> dict[str, Any]:
    metrics = parsed["metrics"]
    return {
        "hotspot": {
            "event_id": parsed["task_id"],
            "name": "木里县森林火灾高危火点",
            "longitude": ignition[0] if ignition else None,
            "latitude": ignition[1] if ignition else None,
            "risk_level": metrics["risk_level"],
            "status": "待处置",
            "reason": "ForeFire 已生成火线预测，需进入联动处置流程。",
        },
        "fire_front_geojson": forefire_payload.get("geojson") or {"type": "FeatureCollection", "features": []},
        "uav_routes": uav_package.get("patrol_routes", []),
        "resource_routes": route_package.get("rescue_routes", []),
        "evacuation_routes": route_package.get("evacuation_routes", []),
        "coverage_areas": uav_package.get("coverage_areas", []),
        "risk_zones": route_package.get("risk_zones", []),
    }


def _build_uav_package(parsed: dict[str, Any], resources: dict[str, Any] | None) -> dict[str, Any]:
    metrics = parsed["metrics"]
    bbox = metrics["final_bbox"]
    direction = metrics["main_spread_direction"]
    selected = _select_uav_assets(resources)
    thermal_ids = selected["thermal"] or selected["available"][:2] or ["UAV-MON-01"]
    visible_ids = selected["visible"] or selected["available"][:1] or ["UAV-REC-01"]
    relay_ids = selected["relay"] or selected["available"][-1:] or ["UAV-COM-01"]
    route = _uav_patrol_route(bbox, direction)
    coverage = _coverage_polygon(bbox, scale=1.2)
    return {
        "uav_tasks": [
            {
                "task_id": "uav-thermal-main",
                "uav_ids": thermal_ids[:2],
                "owner": "/".join(thermal_ids[:2]),
                "action": f"执行{_direction_label(direction)}火线热成像巡航",
                "target": f"{_direction_label(direction)}活动火线",
                "priority": "critical",
                "duration_minutes": 45,
                "status": "planned",
                "reason": "主扩散方向需要连续热成像复核，避免地面队伍误入活动火翼。",
            },
            {
                "task_id": "uav-visible-spotting",
                "uav_ids": visible_ids[:2],
                "owner": "/".join(visible_ids[:2]),
                "action": "巡查飞火点和烟羽影响边界",
                "target": "火场外围可疑热点",
                "priority": "high",
                "duration_minutes": 35,
                "status": "planned",
                "reason": "外围飞火点会影响疏散路线和隔离带布设。",
            },
            {
                "task_id": "uav-relay-command",
                "uav_ids": relay_ids[:1],
                "owner": "/".join(relay_ids[:1]),
                "action": "建立临时空中通信中继",
                "target": "现场指挥部与火线队伍通信扇区",
                "priority": "high",
                "duration_minutes": 60,
                "status": "planned",
                "reason": "山区火场通信易受地形遮挡，需要保持指挥链路稳定。",
            },
        ],
        "patrol_routes": [
            {
                "route_id": "uav-route-main",
                "uav_ids": thermal_ids[:2],
                "coordinates": route,
                "color": "#a78bfa",
                "name": f"{_direction_label(direction)}火线巡航线",
            }
        ],
        "coverage_areas": [
            {
                "area_id": "uav-coverage-main",
                "name": "无人机重点覆盖区",
                "type": "Polygon",
                "coordinates": coverage,
            }
        ],
    }


def _build_route_package(
    parsed: dict[str, Any],
    resources: dict[str, Any] | None,
    *,
    environment_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = parsed["metrics"]
    bbox = metrics["final_bbox"]
    direction = metrics["main_spread_direction"]
    ignition = parsed.get("ignition_point") or _bbox_center(bbox)
    shelters = _list_value(resources, "shelters")
    road_segments = _list_value(resources, "road_segments")
    important_targets = _list_value(resources, "important_targets")
    start = _route_start_from_targets(important_targets, bbox, ignition)
    shelter = _select_shelter(shelters, bbox)
    end = _point_from_item(shelter) or _default_assembly_point(ignition, bbox, direction)
    env_bounds = _environment_bounds(environment_context)
    end = _clamp_point_to_bounds(end, env_bounds)
    entry_point = {
        "id": "entry-point-001",
        "name": "高风险目标入口点",
        "type": "entry_point",
        "longitude": start[0],
        "latitude": start[1],
        "description": "靠近当前高危火点的救援/撤离入口。",
    }
    assembly_point = {
        "id": "assembly-point-south",
        "name": str((shelter or {}).get("name") or "南侧安全集结点"),
        "type": "assembly_point",
        "longitude": end[0],
        "latitude": end[1],
        "description": "位于火场南侧、避开主要下风向的安全集结区域。",
    }
    rescue_start = _nearest_resource_point(resources, bbox) or _safe_point_away_from_bbox(bbox, direction, bounds=env_bounds)
    rescue_start = _clamp_point_to_bounds(rescue_start, env_bounds)
    rescue_end = _bbox_edge_point(bbox, direction)
    rescue_end = _clamp_point_to_bounds(rescue_end, env_bounds)
    safe_end = _safe_point_away_from_bbox(bbox, direction, bounds=env_bounds)
    safe_end = _clamp_point_to_bounds(safe_end, env_bounds)
    route_search = plan_emergency_routes(
        start=start,
        assembly=end,
        rescue_start=rescue_start,
        rescue_end=rescue_end,
        safe_end=safe_end,
        fire_bbox=bbox,
        spread_direction=direction,
        fire_geometry=_final_fire_geometry(parsed),
        road_segments=road_segments,
        environment_dir=(environment_context or {}).get("environment_dir"),
    )
    searched_routes = route_search["routes"]
    main_route = searched_routes["main_evacuation"]
    rescue_route = searched_routes["fire_rescue_approach"]
    safe_route = searched_routes["safe_route"]
    route_options = [
        _route_option(
            route_id="main_evacuation",
            name="主疏散路线",
            route_type="evacuation",
            priority="recommended",
            risk=main_route["risk"],
            color="#22c55e",
            coordinates=main_route["coordinates"],
            distance_km=main_route["distance_km"],
            speed_kmh=28,
            reason=f"A* 已在 DEM、燃料、火场距离和下风向代价面上搜索，路线优先向火场{_direction_label(_opposite_direction(direction))}撤离，并避让最终火线高风险栅格。",
            risk_summary=_route_risk_summary(main_route, "疏散"),
            recommended=True,
            elevation_trend="down",
            elevation_profile=main_route["elevation_profile"],
            search_diagnostics=main_route["diagnostics"],
        ),
        _route_option(
            route_id="fire_rescue_approach",
            name="消防救援接近路线",
            route_type="rescue_approach",
            priority="secondary",
            risk=rescue_route["risk"],
            color="#f59e0b",
            coordinates=rescue_route["coordinates"],
            distance_km=rescue_route["distance_km"],
            speed_kmh=20,
            reason="A* 已按消防接近权重搜索，允许靠近火场外缘，但仍对最终火线、下风向烟羽和陡坡栅格施加惩罚。",
            risk_summary=_route_risk_summary(rescue_route, "救援接近"),
            recommended=False,
            elevation_trend="up",
            elevation_profile=rescue_route["elevation_profile"],
            search_diagnostics=rescue_route["diagnostics"],
        ),
        _route_option(
            route_id="safe_route",
            name="安全路径",
            route_type="safe",
            priority="fallback",
            risk=safe_route["risk"],
            color="#38bdf8",
            coordinates=safe_route["coordinates"],
            distance_km=safe_route["distance_km"],
            speed_kmh=18,
            reason="A* 已使用最高安全权重搜索，重点压低火场邻近、下风向、燃料和坡度代价，作为备用安全通道。",
            risk_summary=_route_risk_summary(safe_route, "备用安全"),
            recommended=False,
            elevation_trend="down",
            elevation_profile=safe_route["elevation_profile"],
            search_diagnostics=safe_route["diagnostics"],
        ),
    ]
    evacuation_routes = [_legacy_route_from_option(route_options[0], start_label="高风险目标入口点", end_label=assembly_point["name"])]
    rescue_routes = [_legacy_route_from_option(route_options[1], start_label="消防力量集结点", end_label=f"{_direction_label(direction)}火线外缘")]
    blocked_routes = [
        {
            "id": str(item.get("segment_id") or item.get("id") or f"road-{idx}"),
            "segment_id": str(item.get("segment_id") or item.get("id") or f"road-{idx}"),
            "name": str(item.get("name") or "高风险路段"),
            "risk": str(item.get("risk_level") or "high"),
            "risk_level": str(item.get("risk_level") or "high"),
            "status": str(item.get("status") or "restricted"),
            "reason": str(item.get("notes") or "该路段风险较高，建议限制社会车辆通行。"),
            "coordinates": _road_segment_coordinates(item),
        }
        for idx, item in enumerate(road_segments, start=1)
        if str(item.get("risk_level") or "").lower() in {"high", "critical"} or str(item.get("status") or "").lower() in {"restricted", "closed"}
    ][:5]
    if not blocked_routes:
        blocked_routes = [
            {
                "id": "north-risk-corridor",
                "segment_id": "risk-road-bbox",
                "name": f"{_direction_label(direction)}风险通道",
                "risk": "high",
                "risk_level": "high",
                "status": "restricted",
                "reason": "处于预测火势扩展方向和较强风场影响范围内，不建议通行。",
                "coordinates": [ignition, _offset_point(ignition, 0.0016, 0.0018), _offset_point(ignition, 0.0034, 0.0038)],
            }
        ]
    risk_zones = [
        {
            "id": "fire-spread-risk-zone",
            "zone_id": "risk-final-fire-bbox",
            "name": "预测火势影响区",
            "type": "fire_risk",
            "risk": metrics["risk_level"],
            "risk_level": metrics["risk_level"],
            "coordinates": _bbox_polygon(bbox),
            "reason": "ForeFire 最终火线范围及其近场缓冲区。",
        },
        {
            "id": "downwind-smoke-risk-zone",
            "zone_id": "risk-smoke-main",
            "name": f"{_direction_label(direction)}烟羽影响区",
            "type": "smoke_risk",
            "risk": "high",
            "risk_level": "high",
            "coordinates": _directional_risk_polygon(bbox, direction),
            "reason": "主扩散方向附近需要重点关注烟羽、飞火和通行安全。",
        },
    ]
    return {
        "entry_point": entry_point,
        "assembly_point": assembly_point,
        "route_options": route_options,
        "evacuation_routes": evacuation_routes,
        "rescue_routes": rescue_routes,
        "blocked_routes": blocked_routes,
        "risk_zones": risk_zones,
        "search_diagnostics": route_search["diagnostics"],
        "warnings": route_search.get("warnings", []),
        "summary": "已基于 A* 代价面搜索生成主疏散路线、消防救援接近路线和备用安全路径。推荐优先使用主疏散路线，并结合现场道路通行情况复核。",
    }


def _build_resource_package(dispatch: dict[str, Any], resources: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "dispatch_tasks": dispatch.get("tasks", []),
        "inventory_changes": dispatch.get("inventory_changes", _build_inventory_changes(resources, {})),
        "personnel_assignments": dispatch.get("personnel_assignments", _build_personnel_assignments(resources, dispatch.get("tasks", []))),
        "resource_summary": _resource_summary(resources),
    }


def _build_assessment_package(parsed: dict[str, Any], resources: dict[str, Any] | None) -> dict[str, Any]:
    metrics = parsed["metrics"]
    final_area = float(metrics["final_area_km2"])
    targets = _list_value(resources, "important_targets")
    shelters = _list_value(resources, "shelters")
    affected_people = _estimated_affected_people(targets, shelters, final_area)
    severity_score = round(min(10.0, final_area * 0.42 + metrics["latest_growth_km2_per_hour"] * 1.1 + affected_people / 4500), 1)
    return {
        "severity": _severity_label(severity_score),
        "severity_score": severity_score,
        "final_area_km2": final_area,
        "burned_hectares": round(final_area * 100, 1),
        "economic_loss_million_cny": round(final_area * 3.8 + len(targets) * 1.6, 1),
        "affected_people": affected_people,
        "ecological_impact": round(min(100, final_area * 7.5 + metrics["latest_growth_km2_per_hour"] * 8), 1),
        "recovery_months": "3-6" if severity_score < 7 else "6-12",
        "loss_breakdown": [
            {"name": "林木资源", "value_million_cny": round(final_area * 1.8, 1)},
            {"name": "灭火投入", "value_million_cny": round(final_area * 0.9 + 2.0, 1)},
            {"name": "交通与疏散保障", "value_million_cny": round(max(1.0, affected_people / 5000), 1)},
            {"name": "生态修复", "value_million_cny": round(final_area * 1.1, 1)},
        ],
    }


def _build_command_package(
    input_summary: dict[str, Any],
    command: dict[str, Any],
    dispatch: dict[str, Any],
    uav_package: dict[str, Any],
    route_package: dict[str, Any],
    resource_package: dict[str, Any],
    assessment_package: dict[str, Any],
    resources: dict[str, Any] | None,
    *,
    event_name: str | None,
) -> dict[str, Any]:
    tasks = dispatch.get("tasks", [])
    uav_tasks = [task for task in uav_package.get("uav_tasks", []) if task.get("status") == "planned"]
    personnel_total = _personnel_total(resources)
    personnel_deployed = sum(int(item.get("assigned_headcount", 0) or 0) for item in resource_package.get("personnel_assignments", []))
    recommended = command.get("recommended_plan") or {}
    command_summary = (
        f"{event_name or '当前火情'}建议执行{recommended.get('name') or '推荐处置方案'}，"
        f"优先控制{_risk_label(input_summary.get('risk_level', 'high'))}火线、组织无人机巡航和疏散路线管制。"
    )
    return {
        "kpis": {
            "fire_count": 1,
            "final_area_km2": input_summary.get("final_area_km2"),
            "uav_online": max(len(_list_value(resources, "uav_assets")), len(uav_tasks)),
            "uav_mission": len(uav_tasks),
            "resource_points": _resource_point_count(resources),
            "personnel_total": personnel_total,
            "personnel_deployed": personnel_deployed,
            "vehicles_dispatched": len(_list_value(resources, "vehicles")) or 3,
            "evacuated_people": min(assessment_package.get("affected_people", 0), 1680),
        },
        "active_tasks": [
            {
                "task_id": task.get("task_id"),
                "name": task.get("action"),
                "status": "计划中",
                "progress": 0,
                "location": task.get("target"),
            }
            for task in tasks
        ],
        "command_summary": command_summary,
        "communication_log": [
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "sender": "Agent",
                "message": f"推荐方案 {recommended.get('plan_id') or '未确定'} 已生成。",
                "level": "info",
            }
        ],
    }


def _build_fusion_package(
    *,
    forefire_payload: dict[str, Any],
    warnings: list[str],
    weather: dict[str, Any] | None,
    dem: dict[str, Any] | None,
    resources: dict[str, Any] | None,
    environment_context: dict[str, Any] | None,
) -> dict[str, Any]:
    source_states = [
        _source_state("高危火点监测", "ready"),
        _source_state("ForeFire 火线", "ready" if forefire_payload.get("geojson") else "missing"),
        _source_state("Agent 决策", "ready"),
        _source_state("气象风场", _fusion_input_status(weather, environment_context, "weather")),
        _source_state("DEM/Fuel", _fusion_input_status(dem, environment_context, "dem")),
        _source_state("资源数据库", "ready" if resources else "mock"),
    ]
    confidence = 92
    confidence -= 8 if not weather else 0
    confidence -= 6 if not dem and not (environment_context and environment_context.get("dem", {}).get("available")) else 0
    confidence -= 8 if not resources else 0
    confidence -= min(12, len(warnings) * 2)
    return {
        "confidence": max(55, confidence),
        "data_sources": source_states,
        "warnings": warnings,
        "recommendation": "建议补充实时气象、DEM/Fuel 栅格解析和重点目标数据后再次刷新决策。",
    }


def _fusion_input_status(
    provided: dict[str, Any] | None,
    environment_context: dict[str, Any] | None,
    key: str,
) -> str:
    if provided:
        status = str(provided.get("status") or "")
        if status == "file_ready_unparsed":
            return "partial"
        return "ready"
    if environment_context and environment_context.get(key, {}).get("available"):
        return "partial"
    return "missing"


def _source_state(name: str, status: str) -> dict[str, str]:
    return {
        "name": name,
        "status": status,
        "label": {
            "ready": "已接入",
            "partial": "部分接入",
            "missing": "缺失",
            "mock": "本地兜底",
        }.get(status, status),
    }


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _list_value(container: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(container, dict):
        return []
    value = container.get(key)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _available_item_count(items: list[dict[str, Any]], *, total_key: str | None = None) -> int:
    count = 0
    for item in items:
        status = str(item.get("status") or "available").lower()
        if status in {"available", "idle", "online", "ready", "standby", "可用", "待命"}:
            count += 1
    if count == 0 and total_key:
        count = sum(1 for item in items if item.get(total_key))
    return count


def _personnel_role_count(items: list[dict[str, Any]], *tokens: str) -> int:
    total = 0
    lowered = [token.lower() for token in tokens]
    for item in items:
        haystack = " ".join(
            str(item.get(key) or "")
            for key in ("unit_type", "type", "role", "name", "skill_tags_json")
        ).lower()
        if any(token in haystack for token in lowered):
            total += int(_first_number(item.get("available_headcount"), item.get("headcount"), item.get("count"), 1) or 0)
    return total


def _vehicle_type_count(items: list[dict[str, Any]], *tokens: str) -> int:
    total = 0
    lowered = [token.lower() for token in tokens]
    for item in items:
        haystack = " ".join(str(item.get(key) or "") for key in ("vehicle_type", "type", "name")).lower()
        if any(token in haystack for token in lowered):
            total += int(_first_number(item.get("capacity"), 1) or 1)
    return total


def _inventory_category_count(items: list[dict[str, Any]], *tokens: str) -> int:
    total = 0
    lowered = [token.lower() for token in tokens]
    for item in items:
        haystack = " ".join(str(item.get(key) or "") for key in ("category", "type", "name", "notes")).lower()
        if any(token in haystack for token in lowered):
            total += int(_first_number(item.get("available"), item.get("total"), item.get("count"), 1) or 0)
    return total


def _preferred_personnel_name(resources: dict[str, Any] | None, role_token: str) -> str | None:
    tokens = {
        "fire": ("fire", "fire_crew", "firefighter", "消防"),
        "logistics": ("logistics", "后勤", "保障"),
        "evacuation": ("evacuation", "疏散", "交通"),
    }.get(role_token, (role_token,))
    for item in _list_value(resources, "personnel_units"):
        haystack = " ".join(str(item.get(key) or "") for key in ("unit_type", "name", "skill_tags_json")).lower()
        if any(token.lower() in haystack for token in tokens):
            return str(item.get("name") or item.get("unit_id"))
    return None


def _preferred_named_item(resources: dict[str, Any] | None, key: str) -> str | None:
    for item in _list_value(resources, key):
        name = item.get("name") or item.get("source_id") or item.get("id")
        if name:
            return str(name)
    return None


def _build_inventory_changes(resources: dict[str, Any] | None, metrics: dict[str, Any]) -> list[dict[str, Any]]:
    final_area = float(metrics.get("final_area_km2", 8.0) or 8.0)
    source_items = _list_value(resources, "resource_inventory")
    if source_items:
        changes = []
        for item in source_items[:6]:
            available = _first_number(item.get("available"), item.get("total"), item.get("count"), 0) or 0
            change = -min(int(max(1, final_area)), int(available) if available else int(max(1, final_area)))
            changes.append(
                {
                    "resource_id": str(item.get("resource_id") or item.get("id") or item.get("name") or "resource"),
                    "name": str(item.get("name") or "应急物资"),
                    "change": change,
                    "unit": str(item.get("unit") or "件"),
                    "reason": "根据推荐方案预占前线处置物资。",
                }
            )
        return changes
    return [
        {"resource_id": "res-protective-suit", "name": "森林消防防护服", "change": -24, "unit": "套", "reason": "前线消防队伍部署。"},
        {"resource_id": "res-fire-hose", "name": "消防水管", "change": -18, "unit": "卷", "reason": "建立分段压制线。"},
        {"resource_id": "res-pump", "name": "便携水泵", "change": -2, "unit": "台", "reason": "水源接驳和连续供水。"},
    ]


def _build_personnel_assignments(resources: dict[str, Any] | None, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units = _list_value(resources, "personnel_units")
    if units:
        assignments = []
        for idx, unit in enumerate(units[:4]):
            headcount = int(_first_number(unit.get("available_headcount"), unit.get("headcount"), 6) or 6)
            task = tasks[min(idx, len(tasks) - 1)] if tasks else {}
            assignments.append(
                {
                    "unit_id": str(unit.get("unit_id") or unit.get("id") or f"unit-{idx + 1}"),
                    "name": str(unit.get("name") or "应急队伍"),
                    "assigned_headcount": min(headcount, max(2, headcount)),
                    "task_id": task.get("task_id") or "TASK-FIRE-001",
                    "status": "planned",
                }
            )
        return assignments
    return [
        {"unit_id": "unit-fire-north", "name": "北线森林消防一队", "assigned_headcount": 18, "task_id": "TASK-FIRE-001", "status": "planned"},
        {"unit_id": "unit-logistics", "name": "后勤保障组", "assigned_headcount": 6, "task_id": "TASK-WATER-001", "status": "planned"},
        {"unit_id": "unit-evac", "name": "疏散与交通管制组", "assigned_headcount": 8, "task_id": "TASK-EVAC-001", "status": "planned"},
    ]


def _resource_summary(resources: dict[str, Any] | None) -> dict[str, int]:
    return {
        "resource_inventory": len(_list_value(resources, "resource_inventory")),
        "personnel_units": len(_list_value(resources, "personnel_units")),
        "uav_assets": len(_list_value(resources, "uav_assets")),
        "vehicles": len(_list_value(resources, "vehicles")),
        "water_sources": len(_list_value(resources, "water_sources")),
        "shelters": len(_list_value(resources, "shelters")),
        "important_targets": len(_list_value(resources, "important_targets")),
        "road_segments": len(_list_value(resources, "road_segments")),
    }


def _select_uav_assets(resources: dict[str, Any] | None) -> dict[str, list[str]]:
    result = {"available": [], "thermal": [], "visible": [], "relay": []}
    for item in _list_value(resources, "uav_assets"):
        status = str(item.get("status") or "available").lower()
        if status not in {"available", "idle", "ready", "online", "standby", "可用", "待命"}:
            continue
        uav_id = str(item.get("uav_id") or item.get("id") or item.get("name") or f"UAV-{len(result['available']) + 1:02d}")
        result["available"].append(uav_id)
        payload_blob = json.dumps(item.get("payloads_json") or item.get("payloads") or item, ensure_ascii=False).lower()
        if any(token in payload_blob for token in ("thermal", "infrared", "热成像", "红外")):
            result["thermal"].append(uav_id)
        if any(token in payload_blob for token in ("visible", "camera", "multispectral", "可见光", "多光谱")):
            result["visible"].append(uav_id)
        if any(token in payload_blob for token in ("relay", "communication", "通信", "中继")):
            result["relay"].append(uav_id)
    return result


def _route_start_from_targets(
    targets: list[dict[str, Any]],
    bbox: list[float],
    ignition: list[float] | None = None,
) -> list[float]:
    for item in targets:
        point = _point_from_item(item)
        if point:
            return point
    if ignition:
        return ignition
    return _bbox_edge_point(bbox, "south")


def _select_shelter(shelters: list[dict[str, Any]], bbox: list[float]) -> dict[str, Any] | None:
    available = [
        item for item in shelters
        if str(item.get("status") or "available").lower() not in {"closed", "full", "停用", "已满"}
    ]
    if not available:
        return None
    center = _bbox_center(bbox)
    return max(
        available,
        key=lambda item: (
            _first_number(item.get("capacity_people"), 0) or 0,
            _distance_km(center, _point_from_item(item) or center),
        ),
    )


def _point_from_item(item: dict[str, Any] | None) -> list[float] | None:
    if not isinstance(item, dict):
        return None
    lon = _first_number(item.get("lng"), item.get("lon"), item.get("longitude"), item.get("start_lng"))
    lat = _first_number(item.get("lat"), item.get("latitude"), item.get("start_lat"))
    if lon is None or lat is None:
        return None
    return [round(lon, 6), round(lat, 6)]


def _nearest_resource_point(resources: dict[str, Any] | None, bbox: list[float]) -> list[float] | None:
    center = _bbox_center(bbox)
    points = []
    for key in ("personnel_units", "vehicles", "water_sources", "resource_inventory"):
        for item in _list_value(resources, key):
            point = _point_from_item(item)
            if point:
                points.append(point)
    if not points:
        return None
    return min(points, key=lambda point: _distance_km(point, center))


def _final_fire_geometry(parsed: dict[str, Any]) -> dict[str, Any] | None:
    steps = parsed.get("steps")
    if not isinstance(steps, list) or not steps:
        return None
    final = steps[-1]
    geometry_type = final.get("geometry_type")
    coordinates = final.get("coordinates")
    if geometry_type in {"Polygon", "MultiPolygon"} and isinstance(coordinates, list) and coordinates:
        return {"type": geometry_type, "coordinates": coordinates}
    return None


def _route_risk_summary(route: dict[str, Any], purpose: str) -> str:
    diagnostics = route.get("diagnostics") or {}
    avg = float(route.get("risk_score") or diagnostics.get("average_risk_score") or 0.0)
    max_risk = float(route.get("max_risk_score") or diagnostics.get("max_risk_score") or 0.0)
    high_share = float(route.get("high_risk_share") or diagnostics.get("high_risk_share") or 0.0)
    risk = route.get("risk") or _risk_label_from_score(avg, high_share)
    label = {"low": "低风险", "medium": "中风险", "high": "高风险"}.get(str(risk), str(risk))
    return (
        f"{purpose}路线为{label}，平均风险指数 {avg:.2f}，最高风险指数 {max_risk:.2f}，"
        f"高风险栅格占比 {high_share:.0%}；风险来自 ForeFire 火线距离、下风向烟羽、燃料和坡度综合代价。"
    )


def _risk_label_from_score(avg: float, high_share: float) -> str:
    if avg >= 0.5 or high_share >= 0.25:
        return "high"
    if avg >= 0.28 or high_share >= 0.08:
        return "medium"
    return "low"


def _estimated_affected_people(targets: list[dict[str, Any]], shelters: list[dict[str, Any]], final_area: float) -> int:
    population = sum(int(_first_number(item.get("population"), 0) or 0) for item in targets)
    shelter_people = sum(int(_first_number(item.get("current_people"), 0) or 0) for item in shelters)
    baseline = int(final_area * 320)
    return max(baseline, population + shelter_people)


def _personnel_total(resources: dict[str, Any] | None) -> int:
    total = 0
    for item in _list_value(resources, "personnel_units"):
        total += int(_first_number(item.get("headcount"), item.get("available_headcount"), item.get("count"), 0) or 0)
    return total or 40


def _resource_point_count(resources: dict[str, Any] | None) -> int:
    return sum(
        len(_list_value(resources, key))
        for key in ("resource_inventory", "personnel_units", "uav_assets", "vehicles", "water_sources", "shelters")
    ) or 12


def _bbox_center(bbox: list[float]) -> list[float]:
    return [round((bbox[0] + bbox[2]) / 2, 6), round((bbox[1] + bbox[3]) / 2, 6)]


def _environment_bounds(environment_context: dict[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(environment_context, dict):
        return None
    candidates = [
        ((environment_context.get("forefire_input") or {}).get("bounds")),
        ((environment_context.get("dem") or {}).get("bounds")),
        ((environment_context.get("fuel") or {}).get("bounds")),
    ]
    for item in candidates:
        if not isinstance(item, dict):
            continue
        west = _first_number(item.get("west"))
        south = _first_number(item.get("south"))
        east = _first_number(item.get("east"))
        north = _first_number(item.get("north"))
        if None not in (west, south, east, north) and west < east and south < north:
            return {"west": west, "south": south, "east": east, "north": north}
    return None


def _clamp_point_to_bounds(point: list[float], bounds: dict[str, float] | None) -> list[float]:
    if not bounds:
        return point
    lon_margin = max((bounds["east"] - bounds["west"]) * 0.01, 0.0003)
    lat_margin = max((bounds["north"] - bounds["south"]) * 0.01, 0.0003)
    return [
        round(min(max(point[0], bounds["west"] + lon_margin), bounds["east"] - lon_margin), 6),
        round(min(max(point[1], bounds["south"] + lat_margin), bounds["north"] - lat_margin), 6),
    ]


def _default_assembly_point(
    ignition: list[float],
    bbox: list[float],
    direction: str,
) -> list[float]:
    if "north" in direction:
        return [round(ignition[0] - 0.0062, 6), round(min(ignition[1], bbox[1]) - 0.0082, 6)]
    if "south" in direction:
        return [round(ignition[0] + 0.0062, 6), round(max(ignition[1], bbox[3]) + 0.0082, 6)]
    if "east" in direction:
        return [round(min(ignition[0], bbox[0]) - 0.010, 6), round(ignition[1] - 0.004, 6)]
    if "west" in direction:
        return [round(max(ignition[0], bbox[2]) + 0.010, 6), round(ignition[1] - 0.004, 6)]
    return [round(ignition[0] - 0.0062, 6), round(ignition[1] - 0.0082, 6)]


def _bbox_polygon(bbox: list[float]) -> list[list[float]]:
    return [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[1]],
        [bbox[2], bbox[3]],
        [bbox[0], bbox[3]],
        [bbox[0], bbox[1]],
    ]


def _coverage_polygon(bbox: list[float], *, scale: float) -> list[list[float]]:
    center = _bbox_center(bbox)
    half_lng = (bbox[2] - bbox[0]) * scale / 2
    half_lat = (bbox[3] - bbox[1]) * scale / 2
    expanded = [
        round(center[0] - half_lng, 6),
        round(center[1] - half_lat, 6),
        round(center[0] + half_lng, 6),
        round(center[1] + half_lat, 6),
    ]
    return _bbox_polygon(expanded)


def _directional_risk_polygon(bbox: list[float], direction: str) -> list[list[float]]:
    west, south, east, north = bbox
    dx = max((east - west) * 0.55, 0.006)
    dy = max((north - south) * 0.55, 0.006)
    if "north" in direction:
        return [[west, north], [east, north], [east + dx, north + dy], [west - dx, north + dy], [west, north]]
    if "south" in direction:
        return [[west, south], [east, south], [east + dx, south - dy], [west - dx, south - dy], [west, south]]
    if "east" in direction:
        return [[east, south], [east, north], [east + dx, north + dy], [east + dx, south - dy], [east, south]]
    if "west" in direction:
        return [[west, south], [west, north], [west - dx, north + dy], [west - dx, south - dy], [west, south]]
    return _coverage_polygon(bbox, scale=1.35)


def _bbox_edge_point(bbox: list[float], direction: str) -> list[float]:
    center = _bbox_center(bbox)
    if "north" in direction:
        return [center[0], round(bbox[3] + 0.006, 6)]
    if "south" in direction:
        return [center[0], round(bbox[1] - 0.006, 6)]
    if "east" in direction:
        return [round(bbox[2] + 0.006, 6), center[1]]
    if "west" in direction:
        return [round(bbox[0] - 0.006, 6), center[1]]
    return center


def _safe_point_away_from_bbox(
    bbox: list[float],
    direction: str,
    *,
    bounds: dict[str, float] | None = None,
) -> list[float]:
    center = _bbox_center(bbox)
    opposite = _opposite_direction(direction)
    lon_margin = max((bbox[2] - bbox[0]) * 0.18, 0.002)
    lat_margin = max((bbox[3] - bbox[1]) * 0.18, 0.002)
    if "north" in opposite:
        target = [center[0], round(bbox[3] + 0.025, 6)]
    elif "south" in opposite:
        target = [center[0], round(bbox[1] - 0.025, 6)]
    elif "east" in opposite:
        target = [round(bbox[2] + 0.025, 6), center[1]]
    elif "west" in opposite:
        target = [round(bbox[0] - 0.025, 6), center[1]]
    else:
        target = [round(center[0] - 0.02, 6), round(center[1] - 0.02, 6)]
    if not bounds:
        return target
    return [
        round(min(max(target[0], bounds["west"] + lon_margin), bounds["east"] - lon_margin), 6),
        round(min(max(target[1], bounds["south"] + lat_margin), bounds["north"] - lat_margin), 6),
    ]


def _offset_midpoint(start: list[float], end: list[float], offset: float) -> list[float]:
    return [round((start[0] + end[0]) / 2 + offset, 6), round((start[1] + end[1]) / 2 - offset, 6)]


def _offset_point(point: list[float], lng_offset: float, lat_offset: float) -> list[float]:
    return [round(point[0] + lng_offset, 6), round(point[1] + lat_offset, 6)]


def _route_polyline(start: list[float], end: list[float], offsets: list[float]) -> list[list[float]]:
    if not offsets:
        return [start, end]
    points = [start]
    for index, offset in enumerate(offsets, start=1):
        ratio = index / (len(offsets) + 1)
        lng = start[0] + (end[0] - start[0]) * ratio
        lat = start[1] + (end[1] - start[1]) * ratio
        lateral = offset if index % 2 else -offset * 0.65
        points.append([round(lng + lateral, 6), round(lat - lateral * 0.7, 6)])
    points.append(end)
    return points


def _route_option(
    *,
    route_id: str,
    name: str,
    route_type: str,
    priority: str,
    risk: str,
    color: str,
    coordinates: list[list[float]],
    speed_kmh: float,
    reason: str,
    risk_summary: str,
    recommended: bool,
    elevation_trend: str,
    distance_km: float | None = None,
    elevation_profile: list[dict[str, float]] | None = None,
    search_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    distance = round(float(distance_km), 3) if distance_km is not None else _polyline_distance_km(coordinates)
    eta = round(distance / max(speed_kmh, 1.0) * 60, 1)
    option = {
        "id": route_id,
        "route_id": route_id,
        "name": name,
        "type": route_type,
        "priority": priority,
        "risk": risk,
        "risk_level": risk,
        "distance_km": distance,
        "eta_min": eta,
        "eta_minutes": eta,
        "color": color,
        "reason": reason,
        "risk_summary": risk_summary,
        "recommended": recommended,
        "coordinates": coordinates,
        "elevation_profile": elevation_profile or _elevation_profile(coordinates, trend=elevation_trend),
    }
    if search_diagnostics:
        option["search_method"] = "astar_cost_surface"
        option["search_diagnostics"] = search_diagnostics
    return option


def _legacy_route_from_option(
    option: dict[str, Any],
    *,
    start_label: str,
    end_label: str,
) -> dict[str, Any]:
    return {
        "route_id": option["id"],
        "id": option["id"],
        "name": option["name"],
        "type": option["type"],
        "start": start_label,
        "end": end_label,
        "distance_km": option["distance_km"],
        "eta_minutes": option["eta_min"],
        "risk_level": option["risk"],
        "risk": option["risk"],
        "coordinates": option["coordinates"],
        "elevation_profile": option["elevation_profile"],
        "reason": option["reason"],
        "risk_summary": option["risk_summary"],
        "recommended": option["recommended"],
    }


def _polyline_distance_km(coordinates: list[list[float]]) -> float:
    if len(coordinates) < 2:
        return 0.0
    distance = 0.0
    for start, end in zip(coordinates, coordinates[1:]):
        distance += _distance_km(start, end)
    return round(distance, 3)


def _elevation_profile(
    coordinates: list[list[float]],
    *,
    trend: str,
) -> list[dict[str, float]]:
    if not coordinates:
        return []
    cumulative = [0.0]
    for start, end in zip(coordinates, coordinates[1:]):
        cumulative.append(cumulative[-1] + _distance_km(start, end))
    total = cumulative[-1] or 1.0
    base = 2860.0 if trend == "down" else 2688.0
    amplitude = 172.0 if trend == "down" else 172.0
    profile = []
    for index, distance in enumerate(cumulative):
        ratio = distance / total
        ripple = math.sin(index * math.pi / max(len(cumulative) - 1, 1)) * 14.0
        if trend == "up":
            elevation = base + amplitude * ratio + ripple
        elif trend == "flat":
            elevation = base - 20.0 * ratio + ripple
        else:
            elevation = base - amplitude * ratio + ripple
        profile.append(
            {
                "distance_km": round(distance, 3),
                "elevation_m": int(round(elevation)),
            }
        )
    profile[0]["distance_km"] = 0.0
    return profile


def _road_segment_coordinates(item: dict[str, Any]) -> list[list[float]]:
    start_lng = _first_number(item.get("start_lng"))
    start_lat = _first_number(item.get("start_lat"))
    end_lng = _first_number(item.get("end_lng"))
    end_lat = _first_number(item.get("end_lat"))
    if None not in (start_lng, start_lat, end_lng, end_lat):
        return [[round(start_lng, 6), round(start_lat, 6)], [round(end_lng, 6), round(end_lat, 6)]]
    coordinates = item.get("coordinates")
    if isinstance(coordinates, list):
        return [
            [round(float(point[0]), 6), round(float(point[1]), 6)]
            for point in coordinates
            if isinstance(point, list) and len(point) >= 2 and _as_float(point[0]) is not None and _as_float(point[1]) is not None
        ]
    return []


def _uav_patrol_route(bbox: list[float], direction: str) -> list[list[float]]:
    if "north" in direction:
        lat = round(bbox[3] + 0.006, 6)
        return [[bbox[0], lat], [_bbox_center(bbox)[0], round(lat + 0.004, 6)], [bbox[2], lat]]
    if "south" in direction:
        lat = round(bbox[1] - 0.006, 6)
        return [[bbox[0], lat], [_bbox_center(bbox)[0], round(lat - 0.004, 6)], [bbox[2], lat]]
    if "east" in direction:
        lng = round(bbox[2] + 0.006, 6)
        return [[lng, bbox[1]], [round(lng + 0.004, 6), _bbox_center(bbox)[1]], [lng, bbox[3]]]
    if "west" in direction:
        lng = round(bbox[0] - 0.006, 6)
        return [[lng, bbox[1]], [round(lng - 0.004, 6), _bbox_center(bbox)[1]], [lng, bbox[3]]]
    return _bbox_polygon(bbox)[:3]


def _distance_km(a: list[float], b: list[float]) -> float:
    mean_lat = math.radians((a[1] + b[1]) / 2)
    east = (b[0] - a[0]) * KM_PER_DEGREE_LON_EQUATOR * math.cos(mean_lat)
    north = (b[1] - a[1]) * KM_PER_DEGREE_LAT
    return math.sqrt(east * east + north * north)


def _opposite_direction(direction: str) -> str:
    tokens = {
        "north": "south",
        "south": "north",
        "east": "west",
        "west": "east",
    }
    parts = [tokens.get(part, part) for part in str(direction).split("-")]
    return "-".join(parts)


def _direction_label(direction: Any) -> str:
    labels = {
        "north": "北侧",
        "south": "南侧",
        "east": "东侧",
        "west": "西侧",
        "north-east": "东北侧",
        "north-west": "西北侧",
        "south-east": "东南侧",
        "south-west": "西南侧",
        "stable": "稳定区",
        "unknown": "未知方向",
    }
    return labels.get(str(direction), str(direction))


def _risk_label(risk: Any) -> str:
    labels = {
        "low": "低风险",
        "moderate": "中风险",
        "medium": "中风险",
        "high": "高风险",
        "extreme": "极高风险",
        "critical": "极高风险",
    }
    return labels.get(str(risk), str(risk))


def _severity_label(score: float) -> str:
    if score >= 8:
        return "特别严重"
    if score >= 6:
        return "严重"
    if score >= 4:
        return "较重"
    return "一般"
