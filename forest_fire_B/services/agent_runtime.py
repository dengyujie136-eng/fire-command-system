import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.c_client import call_get_simulation_result, call_start_simulation
from database import AsyncSessionLocal, Task

AnalysisWorkerFn = Callable[[Dict[str, Any]], Awaitable[str]]
DispatchWorkerFn = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
DroneWorkerFn = Callable[[Dict[str, Any]], Awaitable[List[Dict[str, Any]]]]


def _first_coordinate(fire_geojson: Dict[str, Any]) -> List[float]:
    coordinates = fire_geojson.get("geometry", {}).get("coordinates", [])
    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError("invalid fire geojson coordinates")
    first = coordinates[0]
    if not isinstance(first, list) or len(first) < 2:
        raise ValueError("invalid fire coordinate point")
    return [float(first[0]), float(first[1])]


def _calc_fire_area(fire_geojson: Dict[str, Any]) -> float:
    coordinates = fire_geojson.get("geometry", {}).get("coordinates", [])
    if not isinstance(coordinates, list):
        return 0.0
    return round(len(coordinates) * 0.01, 4)


def _make_drone_route(fire_point: List[float], range_km: float) -> List[Dict[str, float]]:
    lon, lat = fire_point
    offset = range_km * 0.01
    return [
        {"lat": lat - offset, "lon": lon - offset, "alt": 100},
        {"lat": lat + offset, "lon": lon - offset, "alt": 120},
        {"lat": lat + offset, "lon": lon + offset, "alt": 150},
        {"lat": lat - offset, "lon": lon + offset, "alt": 120},
        {"lat": lat, "lon": lon, "alt": 200},
    ]


async def run_agent_cycle(
    db: AsyncSession,
    scene_id: str,
    analysis_worker_fn: Optional[AnalysisWorkerFn] = None,
    dispatch_worker_fn: Optional[DispatchWorkerFn] = None,
    drone_worker_fn: Optional[DroneWorkerFn] = None,
    override_wind_speed: Optional[float] = None,
    override_wind_dir: Optional[float] = None,
) -> Dict[str, Any]:
    stmt = select(Task).where(Task.scene_id == scene_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if task is None:
        raise ValueError(f"scene not found: {scene_id}")

    if not task.current_fire_geojson:
        raise ValueError("scene has no current fire geojson")

    # Supervisor + Perceive
    prev_params = task.params or {}
    prev_agent_state = prev_params.get("agent_state", {}) if isinstance(prev_params, dict) else {}
    prev_perception = prev_agent_state.get("perception", {}) if isinstance(prev_agent_state, dict) else {}
    prev_area = float(prev_perception.get("fire_area", 0.0) or 0.0)
    prev_wind_speed = float(prev_perception.get("wind_speed", task.wind_params.get("wind_speed", 5.0) if task.wind_params else 5.0))

    fire_point = _first_coordinate(task.current_fire_geojson)
    existing_wind = task.wind_params or {}
    wind_speed = float(
        override_wind_speed if override_wind_speed is not None else existing_wind.get("wind_speed", 5.0)
    )
    wind_dir = float(override_wind_dir if override_wind_dir is not None else existing_wind.get("wind_dir", 45.0))

    incident_id = (task.params or {}).get("incident_id")
    if not incident_id:
        raise ValueError("scene missing incident_id")
    sim_start = await call_start_simulation(
        incident_id,
        {
            "model": "ca_v1",
            "steps": 1,
            "time_step_minutes": 10,
            "seed": 42,
        },
    )
    simulation_id = sim_start.get("simulation_id")
    if not simulation_id:
        raise ValueError(f"start simulation failed: {sim_start}")
    sim_result = await call_get_simulation_result(simulation_id)
    fire_lines = sim_result.get("result", {}).get("fire_lines", [])
    if not isinstance(fire_lines, list) or not fire_lines:
        raise ValueError(f"simulation result has no fire_lines: {sim_result}")
    latest = fire_lines[-1]
    geometry = latest.get("geometry")
    if not isinstance(geometry, dict):
        raise ValueError(f"invalid geometry in simulation result: {latest}")
    next_fire_line = {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "timestamp": latest.get("timestamp"),
            "time_index": latest.get("time_index"),
            "simulation_id": simulation_id,
        },
    }
    task.current_fire_geojson = next_fire_line
    task.current_step = int(task.current_step or 0) + 1
    task.wind_params = {"wind_speed": wind_speed, "wind_dir": wind_dir}

    # Supervisor: detect event triggers for replanning
    area = _calc_fire_area(next_fire_line)
    area_delta = round(area - prev_area, 4)
    wind_delta = round(wind_speed - prev_wind_speed, 4)
    events: List[Dict[str, Any]] = []
    if area_delta >= 0.3:
        events.append({"type": "fire_growth_spike", "value": area_delta, "threshold": 0.3})
    if abs(wind_delta) >= 3.0:
        events.append({"type": "wind_shift", "value": wind_delta, "threshold": 3.0})
    if wind_speed >= 12:
        events.append({"type": "extreme_wind", "value": wind_speed, "threshold": 12.0})

    need_replan = bool(events) or wind_speed >= 12 or area >= 1.2

    # Worker: analysis
    worker_context = {
        "scene_id": scene_id,
        "fire_point": fire_point,
        "wind_speed": wind_speed,
        "wind_dir": wind_dir,
        "fire_area": area,
        "area_delta": area_delta,
        "wind_delta": wind_delta,
        "events": events,
        "need_replan": need_replan,
        "step": task.current_step,
    }
    if analysis_worker_fn:
        analysis = await analysis_worker_fn(worker_context)
    else:
        trend = "高风险快速蔓延" if need_replan else "中低速蔓延"
        analysis = (
            f"场景{scene_id}当前{trend}，估算火场面积{area}，面积变化{area_delta}。"
            "建议持续巡检下风向并按事件动态调整资源。"
        )

    # Worker: dispatch plan
    if dispatch_worker_fn:
        dispatch_plan = await dispatch_worker_fn(worker_context)
    else:
        fire_trucks = max(1, int(area / 2) + 1)
        uavs = max(1, int(area / 5) + 1)
        firefighters = fire_trucks * 3
        dispatch_plan = {
            "fire_trucks": fire_trucks,
            "uavs": uavs,
            "firefighters": firefighters,
            "dispatch_reason": "event_triggered_replan" if need_replan else "routine_cycle",
        }

    # Worker: drone action plan
    if drone_worker_fn:
        drone_route = await drone_worker_fn(worker_context)
    else:
        drone_route = _make_drone_route(fire_point, range_km=5.0 if need_replan else 3.0)

    action_plan = {
        **dispatch_plan,
        "drone_route": drone_route,
        "need_replan": need_replan,
    }

    params = task.params or {}
    history = params.get("agent_history", []) if isinstance(params.get("agent_history"), list) else []
    cycle_record = {
        "cycle": task.current_step,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "events": events,
        "need_replan": need_replan,
        "plan_digest": {
            "fire_trucks": action_plan.get("fire_trucks"),
            "uavs": action_plan.get("uavs"),
            "firefighters": action_plan.get("firefighters"),
        },
    }
    history.append(cycle_record)
    if len(history) > 30:
        history = history[-30:]

    params["agent_state"] = {
        "scene_id": scene_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "cycle": task.current_step,
        "supervisor": {
            "events": events,
            "need_replan": need_replan,
            "area_delta": area_delta,
            "wind_delta": wind_delta,
        },
        "perception": {
            "fire_area": area,
            "wind_speed": wind_speed,
            "wind_dir": wind_dir,
        },
        "workers": {
            "analysis": analysis,
            "dispatch": {
                "fire_trucks": action_plan.get("fire_trucks"),
                "uavs": action_plan.get("uavs"),
                "firefighters": action_plan.get("firefighters"),
                "dispatch_reason": action_plan.get("dispatch_reason"),
            },
            "drone": {
                "route_points": len(drone_route),
                "range_mode": "wide" if need_replan else "routine",
            },
        },
        "plan": action_plan,
    }
    params["agent_history"] = history
    task.params = params
    task.last_update = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return params["agent_state"]


class AgentLoopManager:
    def __init__(self) -> None:
        self._loops: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def status(self, scene_id: str) -> Dict[str, Any]:
        info = self._loops.get(scene_id)
        if not info:
            return {"scene_id": scene_id, "running": False}
        return {
            "scene_id": scene_id,
            "running": not info["task"].done(),
            "interval_seconds": info["interval_seconds"],
            "max_cycles": info["max_cycles"],
            "completed_cycles": info["completed_cycles"],
            "last_state": info.get("last_state"),
            "started_at": info["started_at"],
        }

    async def stop(self, scene_id: str) -> bool:
        info = self._loops.get(scene_id)
        if not info:
            return False
        task = info["task"]
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self._loops.pop(scene_id, None)
        return True

    async def start(
        self,
        scene_id: str,
        interval_seconds: int,
        max_cycles: int,
        analysis_worker_fn: Optional[AnalysisWorkerFn] = None,
        dispatch_worker_fn: Optional[DispatchWorkerFn] = None,
        drone_worker_fn: Optional[DroneWorkerFn] = None,
    ) -> Dict[str, Any]:
        existing = self._loops.get(scene_id)
        if existing and not existing["task"].done():
            raise ValueError(f"loop already running for scene: {scene_id}")
        lock = self._locks.setdefault(scene_id, asyncio.Lock())

        async def _runner() -> None:
            cycles = 0
            while True:
                if max_cycles > 0 and cycles >= max_cycles:
                    break
                async with lock:
                    async with AsyncSessionLocal() as db:
                        state = await run_agent_cycle(
                            db=db,
                            scene_id=scene_id,
                            analysis_worker_fn=analysis_worker_fn,
                            dispatch_worker_fn=dispatch_worker_fn,
                            drone_worker_fn=drone_worker_fn,
                        )
                    info = self._loops.get(scene_id)
                    if info:
                        info["last_state"] = state
                        info["completed_cycles"] = cycles + 1
                cycles += 1
                await asyncio.sleep(interval_seconds)

        task = asyncio.create_task(_runner())
        self._loops[scene_id] = {
            "task": task,
            "interval_seconds": interval_seconds,
            "max_cycles": max_cycles,
            "completed_cycles": 0,
            "last_state": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.status(scene_id)
