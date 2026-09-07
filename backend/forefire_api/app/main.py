from __future__ import annotations

import json
import math
import os
import shutil
import sqlite3
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import netCDF4
import numpy as np
from pydantic import BaseModel, Field


ENVIRONMENT_DIR = Path(os.getenv("ENVIRONMENT_DIR", "/app/environment"))
OUTPUT_DIR = Path(os.getenv("FOREFIRE_OUTPUT_DIR", "/app/output"))
DATA_DIR = Path(os.getenv("FOREFIRE_DATA_DIR", "/app/data"))
ARCHIVE_DB = DATA_DIR / "fire_events.db"
INPUT_NC = ENVIRONMENT_DIR / "final_input.nc"
VISUAL_WIND_NC = ENVIRONMENT_DIR / "weather_wind_large.nc"
IGNITION_FILE = ENVIRONMENT_DIR / "ignition.txt"
SCENE_ENVIRONMENT_DIRS = {
    "muli_lier_village": ENVIRONMENT_DIR,
    "pingyao_liujian_gou_early_replay": ENVIRONMENT_DIR / "pingyao_20240613",
}
WIND_FIELD_LOCK = threading.Lock()
WIND_FIELD_CACHE: dict[tuple[int, float | None], dict[str, Any]] = {}
DEFAULT_LONGITUDE = 101.269444
DEFAULT_LATITUDE = 28.530278
DEFAULT_START_TIME = os.getenv("FOREFIRE_START_TIME", "2020-06-01T12:00:00Z")
FUELS_CSV = """Index;Rhod;Rhol;Md;Ml;sd;sl;e;Sigmad;Sigmal;stoch;RhoA;Ta;Tau0;Deltah;DeltaH;Cp;Cpa;Ti;X0;r00;Blai;me
0;563.0;522.0;0.1;1.0;6099.0;7273.0;0;0.764;0.352;8.3;1.0;300;70000;18169000.0;18167000.0;1800;1000;600;0.3;2.5e-05;4.0;0.3
1;563.0;522.0;0.1;1.0;6099.0;7273.0;0;0.764;0.352;8.3;1.0;300;70000;18169000.0;18167000.0;1800;1000;600;0.3;2.5e-05;4.0;0.3
2;614.0;613.0;0.1;1.0;4287.0;5738.0;0.4;1.378;0.174;8.3;1.0;300;70000;18727000.0;18727000.0;1800;1000;600;0.3;2.5e-05;4.0;0.3
3;613.0;538.0;0.1;1.0;4357.0;6524.0;0.19;1.286;0.085;8.3;1.0;300;70000;18677000.0;18677000.0;1800;1000;600;0.3;2.5e-05;4.0;0.3
4;626.0;600.0;0.1;1.0;4325.0;5844.0;0.6;1.393;0.201;8.3;1.0;300;70000;18802000.0;18802000.0;1800;1000;600;0.3;2.5e-05;4.0;0.3
"""


class SimulateRequest(BaseModel):
    model: str = "standard"
    time: str | None = None
    duration: float = Field(default=6, ge=0.1)
    scene_id: str = "scene-001"
    longitude: float = DEFAULT_LONGITUDE
    latitude: float = DEFAULT_LATITUDE


class ArchiveRequest(BaseModel):
    event_id: str | None = None
    event_name: str = "木里县森林火灾演示事件"
    ignition_point: dict[str, Any] | None = None
    forefire_result: dict[str, Any] | None = None
    agent_result: dict[str, Any] | None = None
    agent_decision: dict[str, Any] | None = None
    agent_messages: list[Any] = Field(default_factory=list)
    derived_state: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    archived_at: str | None = None


class DispatchTaskRequest(BaseModel):
    task_id: str | None = None
    event_id: str = "muli-fire-demo-001"
    owner: str
    action: str
    target: str
    priority: str = "medium"
    status: str = "planned"
    eta_minutes: float | None = None
    lng: float | None = None
    lat: float | None = None
    reason: str | None = None


app = FastAPI(title="ForeFire API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def archive_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(ARCHIVE_DB)
    connection.row_factory = sqlite3.Row
    return connection


def init_archive_db() -> None:
    with archive_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fire_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_name TEXT NOT NULL,
                ignition_lng REAL NOT NULL,
                ignition_lat REAL NOT NULL,
                forefire_json TEXT,
                agent_json TEXT,
                agent_messages_json TEXT,
                derived_state_json TEXT,
                created_at TEXT NOT NULL,
                archived_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_fire_events_archived_at ON fire_events(archived_at)")


def init_demo_context_db() -> None:
    with archive_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS resource_inventory (
                resource_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit TEXT NOT NULL,
                total REAL NOT NULL,
                available REAL NOT NULL,
                reserved REAL NOT NULL DEFAULT 0,
                location_name TEXT NOT NULL,
                lng REAL NOT NULL,
                lat REAL NOT NULL,
                status TEXT NOT NULL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS personnel_units (
                unit_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                headcount INTEGER NOT NULL,
                available_headcount INTEGER NOT NULL,
                skill_tags_json TEXT NOT NULL,
                location_name TEXT NOT NULL,
                lng REAL NOT NULL,
                lat REAL NOT NULL,
                status TEXT NOT NULL,
                contact TEXT
            );

            CREATE TABLE IF NOT EXISTS uav_assets (
                uav_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                model TEXT NOT NULL,
                payloads_json TEXT NOT NULL,
                battery_percent REAL NOT NULL,
                endurance_minutes REAL NOT NULL,
                max_range_km REAL NOT NULL,
                lng REAL NOT NULL,
                lat REAL NOT NULL,
                status TEXT NOT NULL,
                current_task_id TEXT
            );

            CREATE TABLE IF NOT EXISTS vehicles (
                vehicle_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                capacity TEXT,
                lng REAL NOT NULL,
                lat REAL NOT NULL,
                status TEXT NOT NULL,
                assigned_unit_id TEXT
            );

            CREATE TABLE IF NOT EXISTS water_sources (
                source_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                capacity_tons REAL,
                refill_rate_tons_per_hour REAL,
                lng REAL NOT NULL,
                lat REAL NOT NULL,
                access_level TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS shelters (
                shelter_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                capacity_people INTEGER NOT NULL,
                current_people INTEGER NOT NULL,
                lng REAL NOT NULL,
                lat REAL NOT NULL,
                status TEXT NOT NULL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS important_targets (
                target_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                target_type TEXT NOT NULL,
                priority TEXT NOT NULL,
                population INTEGER,
                lng REAL NOT NULL,
                lat REAL NOT NULL,
                protection_note TEXT
            );

            CREATE TABLE IF NOT EXISTS road_segments (
                segment_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                start_lng REAL NOT NULL,
                start_lat REAL NOT NULL,
                end_lng REAL NOT NULL,
                end_lat REAL NOT NULL,
                distance_km REAL NOT NULL,
                travel_time_minutes REAL NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS dispatch_tasks (
                task_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                owner TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                eta_minutes REAL,
                lng REAL,
                lat REAL,
                reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS communication_logs (
                log_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                channel TEXT NOT NULL,
                message TEXT NOT NULL,
                level TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        seed_rows = {
            "resource_inventory": [
                ("res-suit", "森林消防防护服", "protective_equipment", "件", 1250, 980, 0, "木里县前置物资库", 101.245, 28.507, "available", "适合一线扑火队伍"),
                ("res-extinguisher", "背负式灭火器", "fire_suppression", "具", 420, 360, 0, "东侧物资集结点", 101.290, 28.524, "available", "适合山地近距离压制"),
                ("res-pump", "便携消防泵", "water_supply", "台", 36, 28, 0, "西侧水源补给点", 101.251, 28.535, "available", "配合水车和临时蓄水池使用"),
                ("res-radio", "数字通信电台", "communication", "部", 180, 145, 0, "南侧安全营地", 101.263, 28.508, "available", "用于跨队伍通信"),
                ("res-medical", "急救包", "medical", "套", 260, 220, 0, "南侧安全营地", 101.263, 28.508, "available", "用于疏散和临时救护"),
            ],
            "personnel_units": [
                ("unit-fire-north", "北线森林消防一队", "fire_crew", 80, 72, '["direct_attack","firebreak","mountain"]', "北侧隔离带入口", 101.273, 28.554, "available", "13800010001"),
                ("unit-fire-east", "东线森林消防二队", "fire_crew", 65, 58, '["indirect_attack","patrol","mountain"]', "东侧前线", 101.291, 28.532, "available", "13800010002"),
                ("unit-evac", "疏散指挥组", "evacuation", 34, 30, '["evacuation","traffic_control"]', "南侧安全营地", 101.263, 28.508, "available", "13800010003"),
                ("unit-medical", "医疗救护组", "medical", 18, 16, '["first_aid","triage"]', "南侧安全营地", 101.263, 28.508, "available", "13800010004"),
                ("unit-logistics", "物资保障组", "logistics", 42, 38, '["supply","transport","water"]', "木里县前置物资库", 101.245, 28.507, "available", "13800010005"),
            ],
            "uav_assets": [
                ("UAV-01", "UAV-01 热成像侦察机", "M350-thermal", '["thermal","visible"]', 86, 55, 18, 101.263, 28.548, "available", None),
                ("UAV-02", "UAV-02 热成像侦察机", "M350-thermal", '["thermal","visible"]', 82, 55, 18, 101.255, 28.542, "available", None),
                ("UAV-03", "UAV-03 可见光巡查机", "Mavic-visible", '["visible","zoom"]', 74, 42, 12, 101.288, 28.538, "available", None),
                ("UAV-04", "UAV-04 多光谱巡查机", "Mavic-multispectral", '["multispectral","visible"]', 68, 40, 10, 101.286, 28.520, "available", None),
                ("UAV-05", "UAV-05 通信中继机", "Relay-UAV", '["relay"]', 91, 70, 20, 101.269, 28.510, "available", None),
                ("UAV-06", "UAV-06 备勤机", "Mavic-visible", '["visible"]', 88, 42, 12, 101.246, 28.512, "standby", None),
            ],
            "vehicles": [
                ("veh-water-01", "水车 01", "water_tanker", "12吨", 101.251, 28.535, "available", "unit-logistics"),
                ("veh-water-02", "水车 02", "water_tanker", "12吨", 101.252, 28.536, "available", "unit-logistics"),
                ("veh-fire-01", "森林消防车 01", "fire_engine", "8人/2吨", 101.273, 28.554, "available", "unit-fire-north"),
                ("veh-command-01", "现场指挥车", "command", "通信指挥", 101.263, 28.508, "available", "unit-evac"),
                ("veh-ambulance-01", "救护车 01", "ambulance", "2床位", 101.263, 28.508, "available", "unit-medical"),
            ],
            "water_sources": [
                ("water-west-pond", "西侧临时蓄水点", "pond", 180, 35, 101.251, 28.535, "good"),
                ("water-south-river", "南侧河谷取水点", "river", 800, 120, 101.258, 28.503, "medium"),
                ("water-town-hydrant", "木里县城消防栓群", "hydrant", 240, 60, 101.245, 28.507, "good"),
            ],
            "shelters": [
                ("shelter-south-camp", "南侧安全营地", 1800, 120, 101.263, 28.508, "open", "适合作为主疏散集结点"),
                ("shelter-town-school", "木里县民族中学临时避难点", 1200, 0, 101.246, 28.510, "standby", "可接收转移群众"),
            ],
            "important_targets": [
                ("target-village-south", "下风向村落入口", "village", "critical", 850, 101.258, 28.501, "需优先保护疏散通道"),
                ("target-power-east", "东侧输电线路", "power_line", "high", 0, 101.296, 28.529, "防止火线逼近造成停电"),
                ("target-forest-north", "北侧重点林缘", "forest", "critical", 0, 101.273, 28.554, "建立隔离带并持续巡查"),
                ("target-reservoir-west", "西侧水源地", "water_source", "high", 0, 101.251, 28.535, "保护水源补给能力"),
            ],
            "road_segments": [
                ("road-safe-south-1", "火点至南侧安全营地", 101.269444, 28.530278, 101.263, 28.508, 12.3, 25, "low", "open", "主疏散路线"),
                ("road-east-front-1", "火点至东侧前线", 101.269444, 28.530278, 101.291, 28.532, 8.6, 18, "medium", "open", "物资前送路线"),
                ("road-north-firebreak-1", "火点至北侧隔离带入口", 101.269444, 28.530278, 101.273, 28.554, 7.8, 16, "high", "restricted", "需消防队伍通行"),
                ("road-west-water-1", "火点至西侧水源补给点", 101.269444, 28.530278, 101.251, 28.535, 6.4, 14, "medium", "open", "水车补给路线"),
            ],
        }

        for table, rows in seed_rows.items():
            placeholders = ",".join("?" for _ in rows[0])
            connection.executemany(
                f"INSERT OR IGNORE INTO {table} VALUES ({placeholders})",
                rows,
            )


@app.on_event("startup")
def startup() -> None:
    init_archive_db()
    init_demo_context_db()


def archive_row_to_dict(row: sqlite3.Row, include_payload: bool = False) -> dict[str, Any]:
    result = {
        "id": row["id"],
        "event_id": row["event_id"],
        "event_name": row["event_name"],
        "ignition_point": {
            "longitude": row["ignition_lng"],
            "latitude": row["ignition_lat"],
        },
        "created_at": row["created_at"],
        "archived_at": row["archived_at"],
    }
    if include_payload:
      result.update(
          {
              "forefire_result": json.loads(row["forefire_json"] or "null"),
              "agent_result": json.loads(row["agent_json"] or "null"),
              "agent_messages": json.loads(row["agent_messages_json"] or "[]"),
              "derived_state": json.loads(row["derived_state_json"] or "{}"),
          }
      )
    return result


def archive_ignition_point(request: ArchiveRequest) -> tuple[float, float]:
    point = request.ignition_point or {}
    longitude = point.get("longitude") or point.get("lng") or DEFAULT_LONGITUDE
    latitude = point.get("latitude") or point.get("lat") or DEFAULT_LATITUDE
    return float(longitude), float(latitude)


def build_event_id(request: ArchiveRequest) -> str:
    if request.event_id:
        return request.event_id
    forefire = request.forefire_result or {}
    task_id = forefire.get("task_id")
    if task_id:
        return f"muli-fire-{task_id}"
    return f"muli-fire-{uuid.uuid4()}"


def scene_environment_dir(scene_id: str | None = None) -> Path:
    return SCENE_ENVIRONMENT_DIRS.get(scene_id or "", ENVIRONMENT_DIR)


def scene_input_nc(scene_id: str | None = None) -> Path:
    return scene_environment_dir(scene_id) / "final_input.nc"


def scene_visual_wind_nc(scene_id: str | None = None) -> Path:
    return scene_environment_dir(scene_id) / "weather_wind_large.nc"


def scene_ignition_file(scene_id: str | None = None) -> Path:
    return scene_environment_dir(scene_id) / "ignition.txt"


def ensure_inputs(scene_id: str | None = None) -> None:
    ignition_file = scene_ignition_file(scene_id)
    input_nc = scene_input_nc(scene_id)
    if not ignition_file.exists():
        raise HTTPException(status_code=500, detail=f"Missing ignition file: {ignition_file}")
    if not input_nc.exists():
        raise HTTPException(status_code=500, detail=f"Missing ForeFire input NetCDF: {input_nc}")


def read_ignition_point(scene_id: str | None = None) -> tuple[float, float]:
    ignition_file = scene_ignition_file(scene_id)
    if ignition_file.exists():
        parts = ignition_file.read_text(encoding="utf-8").split()
        if len(parts) >= 2:
            return float(parts[0]), float(parts[1])
    return DEFAULT_LONGITUDE, DEFAULT_LATITUDE


def ignition_hotspot_geojson(scene_id: str | None = None) -> dict[str, Any]:
    longitude, latitude = read_ignition_point(scene_id)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "kind": "high_risk_hotspot",
                    "name": "High-risk fire hotspot",
                    "level": "high",
                    "source": "backend_monitoring_preset",
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                },
            }
        ],
    }


def read_wind_field_from_input(max_points: int = 140, scene_id: str | None = None) -> dict[str, Any]:
    ensure_inputs(scene_id)
    input_nc = scene_input_nc(scene_id)
    longitude, latitude = read_ignition_point(scene_id)
    with netCDF4.Dataset(input_nc) as src:
        lons = np.asarray(src.variables["lon"][:], dtype=np.float64)
        lats = np.asarray(src.variables["lat"][:], dtype=np.float64)
        wind_u = np.asarray(src.variables["windU"][:], dtype=np.float64)
        wind_v = np.asarray(src.variables["windV"][:], dtype=np.float64)

    if lons.ndim == 1 and lats.ndim == 1:
        lon_grid, lat_grid = np.meshgrid(lons, lats)
    else:
        lon_grid, lat_grid = lons, lats

    u_stack = np.squeeze(wind_u)
    v_stack = np.squeeze(wind_v)
    if u_stack.ndim == 2:
        u_stack = u_stack[np.newaxis, :, :]
    elif u_stack.ndim > 3:
        u_stack = u_stack.reshape((-1, *u_stack.shape[-2:]))
    if v_stack.ndim == 2:
        v_stack = v_stack[np.newaxis, :, :]
    elif v_stack.ndim > 3:
        v_stack = v_stack.reshape((-1, *v_stack.shape[-2:]))

    min_lng = longitude - 0.09
    max_lng = longitude + 0.09
    min_lat = latitude - 0.075
    max_lat = latitude + 0.075
    mask = (lon_grid >= min_lng) & (lon_grid <= max_lng) & (lat_grid >= min_lat) & (lat_grid <= max_lat)
    indices = np.argwhere(mask)
    if len(indices) == 0:
        indices = np.argwhere(np.ones_like(lon_grid, dtype=bool))

    selected_rows = sorted({int(y) for y, _ in indices})
    selected_cols = sorted({int(x) for _, x in indices})
    target_cols = max(4, int(math.sqrt(max_points * 1.25)))
    target_rows = max(4, math.ceil(max_points / target_cols))
    row_step = max(1, math.ceil(len(selected_rows) / target_rows))
    col_step = max(1, math.ceil(len(selected_cols) / target_cols))
    sampled_indices = [(y, x) for y in selected_rows[::row_step] for x in selected_cols[::col_step]][:max_points]

    def vectors_for_time_slice(time_index: int) -> list[dict[str, Any]]:
        u_grid = u_stack[min(time_index, u_stack.shape[0] - 1)]
        v_grid = v_stack[min(time_index, v_stack.shape[0] - 1)]
        vectors: list[dict[str, Any]] = []
        for y, x in sampled_indices:
            u = float(u_grid[y, x])
            v = float(v_grid[y, x])
            speed = math.hypot(u, v)
            vectors.append(
                {
                    "lng": round(float(lon_grid[y, x]), 6),
                    "lat": round(float(lat_grid[y, x]), 6),
                    "u": round(u, 4),
                    "v": round(v, 4),
                    "speed": round(speed, 4),
                    "direction_deg": round((math.degrees(math.atan2(u, v)) + 360) % 360, 2),
                }
            )
        return vectors

    time_count = max(1, min(int(u_stack.shape[0]), int(v_stack.shape[0])))
    elapsed_steps = [round(index * 360 / max(1, time_count - 1)) for index in range(time_count)]
    time_step_vectors = [vectors_for_time_slice(index) for index in range(time_count)]
    all_speeds = [vector["speed"] for vectors in time_step_vectors for vector in vectors]
    return {
        "event_id": f"{scene_id or 'muli'}-wind-field",
        "source": str(input_nc.name),
        "bounds": [
            round(float(np.min(lon_grid[mask])), 6) if np.any(mask) else round(float(np.min(lon_grid)), 6),
            round(float(np.min(lat_grid[mask])), 6) if np.any(mask) else round(float(np.min(lat_grid)), 6),
            round(float(np.max(lon_grid[mask])), 6) if np.any(mask) else round(float(np.max(lon_grid)), 6),
            round(float(np.max(lat_grid[mask])), 6) if np.any(mask) else round(float(np.max(lat_grid)), 6),
        ],
        "max_speed": round(max(all_speeds, default=0), 4),
        "time_steps": [
            {
                "step": index,
                "elapsed_minutes": elapsed_minutes,
                "vectors": time_step_vectors[index],
            }
            for index, elapsed_minutes in enumerate(elapsed_steps)
        ],
    }


def _coord_values(dataset: netCDF4.Dataset, *names: str) -> np.ndarray:
    for name in names:
        if name in dataset.variables:
            return np.asarray(dataset.variables[name][:], dtype=np.float64)
    raise HTTPException(status_code=500, detail=f"Missing coordinate variable: {', '.join(names)}")


def _var_values(dataset: netCDF4.Dataset, *names: str) -> np.ndarray:
    for name in names:
        if name in dataset.variables:
            return np.asarray(dataset.variables[name][:], dtype=np.float64)
    raise HTTPException(status_code=500, detail=f"Missing wind variable: {', '.join(names)}")


def _nearest_time_labels(dataset: netCDF4.Dataset, time_count: int) -> list[str]:
    for name in ("valid_time", "time"):
        if name not in dataset.variables:
            continue
        variable = dataset.variables[name]
        try:
            values = netCDF4.num2date(variable[:], variable.units)
            return [value.isoformat() for value in values]
        except Exception:
            return [str(value) for value in variable[:]]
    return [str(index) for index in range(time_count)]


def _bilinear(grid: np.ndarray, lons: np.ndarray, lats: np.ndarray, lng: float, lat: float) -> float:
    lon_ascending = lons[0] <= lons[-1]
    lat_ascending = lats[0] <= lats[-1]
    lon_axis = lons if lon_ascending else lons[::-1]
    lat_axis = lats if lat_ascending else lats[::-1]
    work_grid = grid
    if not lat_ascending:
        work_grid = work_grid[::-1, :]
    if not lon_ascending:
        work_grid = work_grid[:, ::-1]

    lon_index = int(np.clip(np.searchsorted(lon_axis, lng) - 1, 0, len(lon_axis) - 2))
    lat_index = int(np.clip(np.searchsorted(lat_axis, lat) - 1, 0, len(lat_axis) - 2))
    lon0, lon1 = lon_axis[lon_index], lon_axis[lon_index + 1]
    lat0, lat1 = lat_axis[lat_index], lat_axis[lat_index + 1]
    x_weight = 0 if lon1 == lon0 else (lng - lon0) / (lon1 - lon0)
    y_weight = 0 if lat1 == lat0 else (lat - lat0) / (lat1 - lat0)

    q11 = work_grid[lat_index, lon_index]
    q21 = work_grid[lat_index, lon_index + 1]
    q12 = work_grid[lat_index + 1, lon_index]
    q22 = work_grid[lat_index + 1, lon_index + 1]
    return float(
        q11 * (1 - x_weight) * (1 - y_weight)
        + q21 * x_weight * (1 - y_weight)
        + q12 * (1 - x_weight) * y_weight
        + q22 * x_weight * y_weight
    )


def build_visual_wind_field(max_points: int = 140, scene_id: str | None = None) -> dict[str, Any]:
    visual_wind_nc = scene_visual_wind_nc(scene_id)
    longitude, latitude = read_ignition_point(scene_id)
    if not visual_wind_nc.exists():
        return read_wind_field_from_input(max_points=max_points, scene_id=scene_id)

    with netCDF4.Dataset(visual_wind_nc) as src:
        lons = _coord_values(src, "longitude", "lon")
        lats = _coord_values(src, "latitude", "lat")
        wind_u = np.squeeze(_var_values(src, "u10", "windU"))
        wind_v = np.squeeze(_var_values(src, "v10", "windV"))
        if wind_u.ndim == 2:
            wind_u = wind_u[np.newaxis, :, :]
        if wind_v.ndim == 2:
            wind_v = wind_v[np.newaxis, :, :]
        time_count = max(1, min(int(wind_u.shape[0]), int(wind_v.shape[0])))
        time_labels = _nearest_time_labels(src, time_count)

    min_lng = max(float(np.min(lons)), longitude - 0.70)
    max_lng = min(float(np.max(lons)), longitude + 0.80)
    min_lat = max(float(np.min(lats)), latitude - 0.55)
    max_lat = min(float(np.max(lats)), latitude + 0.65)
    target_cols = max(5, int(math.sqrt(max_points * 1.45)))
    target_rows = max(5, math.ceil(max_points / target_cols))
    sample_lons = np.linspace(min_lng, max_lng, target_cols)
    sample_lats = np.linspace(min_lat, max_lat, target_rows)

    def vectors_for_time_slice(time_index: int) -> list[dict[str, Any]]:
        u_grid = wind_u[min(time_index, time_count - 1)]
        v_grid = wind_v[min(time_index, time_count - 1)]
        vectors: list[dict[str, Any]] = []
        for lat in sample_lats:
            for lng in sample_lons:
                u = _bilinear(u_grid, lons, lats, float(lng), float(lat))
                v = _bilinear(v_grid, lons, lats, float(lng), float(lat))
                speed = math.hypot(u, v)
                vectors.append(
                    {
                        "lng": round(float(lng), 6),
                        "lat": round(float(lat), 6),
                        "u": round(u, 4),
                        "v": round(v, 4),
                        "speed": round(speed, 4),
                        "direction_deg": round((math.degrees(math.atan2(u, v)) + 360) % 360, 2),
                    }
                )
        return vectors[:max_points]

    elapsed_steps = [round(index * 360 / max(1, time_count - 1)) for index in range(time_count)]
    time_step_vectors = [vectors_for_time_slice(index) for index in range(time_count)]
    all_speeds = [vector["speed"] for vectors in time_step_vectors for vector in vectors]
    return {
        "event_id": f"{scene_id or 'muli'}-wind-field",
        "source": visual_wind_nc.name,
        "bounds": [round(min_lng, 6), round(min_lat, 6), round(max_lng, 6), round(max_lat, 6)],
        "max_speed": round(max(all_speeds, default=0), 4),
        "time_steps": [
            {
                "step": index,
                "elapsed_minutes": elapsed_minutes,
                "time": time_labels[index] if index < len(time_labels) else str(index),
                "vectors": time_step_vectors[index],
            }
            for index, elapsed_minutes in enumerate(elapsed_steps)
        ],
    }


def read_visual_wind_field(max_points: int = 140, scene_id: str | None = None) -> dict[str, Any]:
    visual_wind_nc = scene_visual_wind_nc(scene_id)
    cache_key = (scene_id or "default", max_points, visual_wind_nc.stat().st_mtime if visual_wind_nc.exists() else None)
    with WIND_FIELD_LOCK:
        cached = WIND_FIELD_CACHE.get(cache_key)
        if cached is not None:
            return cached
        result = build_visual_wind_field(max_points=max_points, scene_id=scene_id)
        WIND_FIELD_CACHE.clear()
        WIND_FIELD_CACHE[cache_key] = result
        return result


def meters_per_degree(latitude: float) -> tuple[float, float]:
    meters_per_degree_lat = math.pi * 6371189 / 180.0
    meters_per_degree_lon = math.pi * 6342516 * math.cos(math.radians(latitude)) / 180.0
    return meters_per_degree_lon, meters_per_degree_lat


def convert_to_forefire_netcdf(source_nc: Path, target_nc: Path) -> None:
    with netCDF4.Dataset(source_nc) as src:
        lons = np.asarray(src.variables["lon"][:], dtype=np.float64)
        lats = np.asarray(src.variables["lat"][:], dtype=np.float64)
        fuel = np.asarray(src.variables["fuel_idx"][:], dtype=np.int32)
        altitude = np.asarray(src.variables["topography_z"][:], dtype=np.float64)
        wind_u = np.asarray(src.variables["windU"][:], dtype=np.float64)
        wind_v = np.asarray(src.variables["windV"][:], dtype=np.float64)

    west, east = float(np.min(lons)), float(np.max(lons))
    south, north = float(np.min(lats)), float(np.max(lats))
    meters_lon, meters_lat = meters_per_degree(south)
    lx = (east - west) * meters_lon
    ly = (north - south) * meters_lat

    with netCDF4.Dataset(target_nc, "w", format="NETCDF4") as dst:
        dst.createDimension("fuelNT", 1)
        dst.createDimension("fuelNZ", 1)
        dst.createDimension("fuelNY", fuel.shape[0])
        dst.createDimension("fuelNX", fuel.shape[1])
        dst.createDimension("altitudeNT", 1)
        dst.createDimension("altitudeNZ", 1)
        dst.createDimension("altitudeNY", altitude.shape[0])
        dst.createDimension("altitudeNX", altitude.shape[1])
        dst.createDimension("windUNT", 1)
        dst.createDimension("windUNZ", 1)
        dst.createDimension("windUNY", wind_u.shape[-2])
        dst.createDimension("windUNX", wind_u.shape[-1])
        dst.createDimension("windVNT", 1)
        dst.createDimension("windVNZ", 1)
        dst.createDimension("windVNY", wind_v.shape[-2])
        dst.createDimension("windVNX", wind_v.shape[-1])

        fuel_var = dst.createVariable("fuel", "i4", ("fuelNT", "fuelNZ", "fuelNY", "fuelNX"))
        fuel_var.type = "fuel"
        fuel_var[:] = np.clip(fuel, 0, 4)[np.newaxis, np.newaxis, :, :]

        altitude_var = dst.createVariable("altitude", "f8", ("altitudeNT", "altitudeNZ", "altitudeNY", "altitudeNX"))
        altitude_var.type = "data"
        altitude_var[:] = altitude[np.newaxis, np.newaxis, :, :]

        wind_u_var = dst.createVariable("windU", "f8", ("windUNT", "windUNZ", "windUNY", "windUNX"))
        wind_u_var.type = "data"
        wind_u_var[:] = wind_u[:1, np.newaxis, :, :]

        wind_v_var = dst.createVariable("windV", "f8", ("windVNT", "windVNZ", "windVNY", "windVNX"))
        wind_v_var.type = "data"
        wind_v_var[:] = wind_v[:1, np.newaxis, :, :]

        domain_var = dst.createVariable("domain", "S1")
        domain_var.type = "domain"
        domain_var.version = np.float64(1.0)
        domain_var.SWx = np.float64(0.0)
        domain_var.SWy = np.float64(0.0)
        domain_var.SWz = np.float64(0.0)
        domain_var.Lx = np.float64(lx)
        domain_var.Ly = np.float64(ly)
        domain_var.Lz = np.float64(0.0)
        domain_var.t0 = np.float64(0.0)
        domain_var.Lt = np.float64(10_000_000.0)
        domain_var.BBoxWSEN = f"{west},{south},{east},{north}"
        domain_var.SWLngLat = f"{west},{south}"

        dst.version = "FF.1.0"


def forefire_domain_geometry(source_nc: Path, longitude: float, latitude: float) -> dict[str, float]:
    with netCDF4.Dataset(source_nc) as src:
        lons = np.asarray(src.variables["lon"][:], dtype=np.float64)
        lats = np.asarray(src.variables["lat"][:], dtype=np.float64)

    west, east = float(np.min(lons)), float(np.max(lons))
    south, north = float(np.min(lats)), float(np.max(lats))
    meters_lon, meters_lat = meters_per_degree(south)
    return {
        "lx": (east - west) * meters_lon,
        "ly": (north - south) * meters_lat,
        "x": (longitude - west) * meters_lon,
        "y": (latitude - south) * meters_lat,
    }


def forefire_geo_transform(source_nc: Path) -> dict[str, float]:
    with netCDF4.Dataset(source_nc) as src:
        lons = np.asarray(src.variables["lon"][:], dtype=np.float64)
        lats = np.asarray(src.variables["lat"][:], dtype=np.float64)

    west, east = float(np.min(lons)), float(np.max(lons))
    south, north = float(np.min(lats)), float(np.max(lats))
    meters_lon, meters_lat = meters_per_degree(south)
    return {
        "west": west,
        "east": east,
        "south": south,
        "north": north,
        "meters_lon": meters_lon,
        "meters_lat": meters_lat,
        "lx": (east - west) * meters_lon,
        "ly": (north - south) * meters_lat,
    }


def resolve_forefire_command() -> str:
    configured = os.getenv("FOREFIRE_CMD")
    if configured:
        return configured

    if shutil.which("forefire"):
        return "forefire -i {case_file}"

    raise HTTPException(
        status_code=503,
        detail=(
            "ForeFire engine is not available. Install Docker/ForeFire or set FOREFIRE_CMD. "
            "No fallback geometry is returned in real-result mode."
        ),
    )


def write_case_file(run_dir: Path, request: SimulateRequest) -> Path:
    duration_seconds = max(60, int(request.duration * 3600))
    step_count = 5
    step_seconds = max(60, duration_seconds // step_count)
    input_nc = scene_input_nc(request.scene_id)
    domain = forefire_domain_geometry(input_nc, request.longitude, request.latitude)

    lines = [
        "setParameters[ForeFireDataDirectory=ForeFire;fireOutputDirectory=ForeFire/Outputs;fuelsTableFile=fuels.csv]",
        "setParameters[dumpMode=geojson;perimeterResolution=30;spatialIncrement=5;propagationModel=Rothermel]",
        "setParameters[relax=0.1;smoothing=5;minimalPropagativeFrontDepth=4;minSpeed=0.0007]",
        f"loadData[data.nc;{DEFAULT_START_TIME}]",
        f"FireDomain[sw=(0,0,0);ne=({domain['lx']:.3f},{domain['ly']:.3f},0);t=0]",
        f"startFire[loc=({domain['x']:.3f},{domain['y']:.3f},0);t=0]",
    ]

    elapsed = 0
    for step in range(1, step_count + 1):
        elapsed += step_seconds
        lines.append(f"step[dt={step_seconds}]")
        lines.append(f"print[front_t{elapsed}.geojson]")

    lines.append("save[filename=output.nc]")
    lines.append("quit[]")

    case_file = run_dir / "case.ff"
    case_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return case_file


def run_forefire(request: SimulateRequest, task_id: str) -> Path:
    command_template = resolve_forefire_command()
    input_nc = scene_input_nc(request.scene_id)
    ignition_file = scene_ignition_file(request.scene_id)

    run_dir = OUTPUT_DIR / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    forefire_dir = run_dir / "ForeFire"
    forefire_dir.mkdir(exist_ok=True)
    shutil.copy2(input_nc, run_dir / "final_input.nc")
    convert_to_forefire_netcdf(input_nc, run_dir / "data.nc")
    shutil.copy2(run_dir / "data.nc", forefire_dir / "data.nc")
    (forefire_dir / "fuels.csv").write_text(FUELS_CSV, encoding="utf-8")
    shutil.copy2(ignition_file, run_dir / "ignition.txt")
    shutil.copy2(ignition_file, forefire_dir / "ignition.txt")
    case_file = write_case_file(run_dir, request)

    command = command_template.format(
        case_file=case_file.name,
        case_path=str(case_file),
        run_dir=str(run_dir),
        output_nc=str(run_dir / "output.nc"),
        duration_seconds=max(60, int(request.duration * 3600)),
        longitude=request.longitude,
        latitude=request.latitude,
    )

    try:
        completed = subprocess.run(
            command,
            shell=True,
            check=True,
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            timeout=int(os.getenv("FOREFIRE_TIMEOUT_SECONDS", "300")),
        )
    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "ForeFire command failed.",
                "command": command,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            },
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail={
                "message": "ForeFire command timed out.",
                "command": command,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            },
        ) from exc

    (run_dir / "forefire.stdout.txt").write_text(completed.stdout or "", encoding="utf-8")
    (run_dir / "forefire.stderr.txt").write_text(completed.stderr or "", encoding="utf-8")
    return run_dir


def load_forefire_geojson(run_dir: Path, scene_id: str | None = None) -> dict[str, Any]:
    def elapsed_from_path(path: Path) -> int:
        try:
            return int(path.stem.replace("front_t", ""))
        except ValueError:
            return 0

    transform = forefire_geo_transform(scene_input_nc(scene_id))

    def maybe_lon_lat(point: list[Any]) -> list[float]:
        x = float(point[0])
        y = float(point[1])
        if transform["west"] - 1 <= x <= transform["east"] + 1 and transform["south"] - 1 <= y <= transform["north"] + 1:
            return [round(x, 7), round(y, 7)]
        lng = transform["west"] + x / max(1e-6, transform["meters_lon"])
        lat = transform["south"] + y / max(1e-6, transform["meters_lat"])
        return [round(lng, 7), round(lat, 7)]

    def convert_coordinates(coordinates: Any) -> Any:
        if (
            isinstance(coordinates, list)
            and len(coordinates) >= 2
            and all(isinstance(value, (int, float)) for value in coordinates[:2])
        ):
            return maybe_lon_lat(coordinates)
        if isinstance(coordinates, list):
            return [convert_coordinates(item) for item in coordinates]
        return coordinates

    def flatten_points(coordinates: Any) -> list[list[float]]:
        if (
            isinstance(coordinates, list)
            and len(coordinates) >= 2
            and all(isinstance(value, (int, float)) for value in coordinates[:2])
        ):
            return [[float(coordinates[0]), float(coordinates[1])]]
        if isinstance(coordinates, list):
            points: list[list[float]] = []
            for item in coordinates:
                points.extend(flatten_points(item))
            return points
        return []

    def polygon_area_km2(points: list[list[float]]) -> float:
        if len(points) < 3:
            return 0.0
        lat0 = sum(point[1] for point in points) / len(points)
        meters_lon, meters_lat = meters_per_degree(lat0)
        projected = [
            ((point[0] - points[0][0]) * meters_lon, (point[1] - points[0][1]) * meters_lat)
            for point in points
        ]
        area_m2 = 0.0
        for index, current in enumerate(projected):
            nxt = projected[(index + 1) % len(projected)]
            area_m2 += current[0] * nxt[1] - nxt[0] * current[1]
        return round(abs(area_m2) / 2_000_000, 4)

    def radius_km(points: list[list[float]]) -> float:
        if not points:
            return 0.0
        center_lng = sum(point[0] for point in points) / len(points)
        center_lat = sum(point[1] for point in points) / len(points)
        meters_lon, meters_lat = meters_per_degree(center_lat)
        return round(
            max(
                math.hypot((point[0] - center_lng) * meters_lon, (point[1] - center_lat) * meters_lat)
                for point in points
            )
            / 1000,
            4,
        )

    geojson_files = sorted(run_dir.glob("front_t*.geojson"), key=elapsed_from_path)
    if not geojson_files:
        raise HTTPException(
            status_code=500,
            detail=f"ForeFire completed but no front_t*.geojson output was produced in {run_dir}",
        )

    features: list[dict[str, Any]] = []
    for index, geojson_file in enumerate(geojson_files, start=1):
        elapsed_text = geojson_file.stem.replace("front_t", "")
        try:
            elapsed_seconds = int(elapsed_text)
        except ValueError:
            elapsed_seconds = index

        data = json.loads(geojson_file.read_text(encoding="utf-8"))
        for feature in data.get("features", []):
            properties = feature.setdefault("properties", {})
            geometry = feature.get("geometry") or {}
            geometry["coordinates"] = convert_coordinates(geometry.get("coordinates"))
            points = flatten_points(geometry.get("coordinates"))
            properties.update(
                {
                    "kind": "fire_front",
                    "step": index,
                    "elapsed_seconds": elapsed_seconds,
                    "elapsed_minutes": round(elapsed_seconds / 60),
                    "source": "forefire",
                    "output_file": geojson_file.name,
                    "area_km2": float(properties.get("area_km2") or polygon_area_km2(points)),
                    "radius_km": float(properties.get("radius_km") or radius_km(points)),
                }
            )
            features.append(feature)

    return {"type": "FeatureCollection", "features": features}


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "final_input_exists": INPUT_NC.exists(),
        "ignition_exists": IGNITION_FILE.exists(),
        "scenes": {
            scene_id: {
                "environment_dir": str(path),
                "final_input_exists": (path / "final_input.nc").exists(),
                "ignition_exists": (path / "ignition.txt").exists(),
                "wind_exists": (path / "weather_wind_large.nc").exists(),
            }
            for scene_id, path in SCENE_ENVIRONMENT_DIRS.items()
        },
        "environment_dir": str(ENVIRONMENT_DIR),
        "archive_db": str(ARCHIVE_DB),
        "archive_db_exists": ARCHIVE_DB.exists(),
        "forefire_cmd_configured": bool(os.getenv("FOREFIRE_CMD")),
        "forefire_executable_available": bool(shutil.which("forefire")),
        "real_result_mode": True,
    }


@app.get("/hotspot")
def hotspot(scene_id: str | None = None) -> dict[str, Any]:
    ensure_inputs(scene_id)
    return ignition_hotspot_geojson(scene_id)


@app.get("/api/hotspot")
def api_hotspot(scene_id: str | None = None) -> dict[str, Any]:
    return hotspot(scene_id=scene_id)


@app.get("/api/weather/wind-field")
def wind_field(max_points: int = 140, scene_id: str | None = None) -> dict[str, Any]:
    return read_visual_wind_field(max_points=max(20, min(max_points, 400)), scene_id=scene_id)


@app.get("/weather/wind-field")
def wind_field_short_path(max_points: int = 140, scene_id: str | None = None) -> dict[str, Any]:
    return wind_field(max_points=max_points, scene_id=scene_id)


@app.post("/api/simulate")
def simulate(request: SimulateRequest) -> dict[str, Any]:
    ensure_inputs(request.scene_id)
    task_id = str(uuid.uuid4())
    run_dir = run_forefire(request, task_id)
    geojson = load_forefire_geojson(run_dir, request.scene_id)

    return {
        "task_id": task_id,
        "scene_id": request.scene_id,
        "status": "done",
        "source": "forefire",
        "area": None,
        "radius": None,
        "speed": None,
        "direction": None,
        "risk": None,
        "output_nc": str(run_dir / "output.nc") if (run_dir / "output.nc").exists() else None,
        "run_dir": str(run_dir),
        "geojson": geojson,
    }


@app.post("/simulate")
def simulate_short_path(request: SimulateRequest) -> dict[str, Any]:
    return simulate(request)


@app.get("/api/simulate/result/{task_id}")
def get_result(task_id: str, scene_id: str | None = None) -> dict[str, Any]:
    run_dir = OUTPUT_DIR / task_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Simulation result not found: {task_id}")
    return {
        "task_id": task_id,
        "status": "done",
        "source": "forefire",
        "output_nc": str(run_dir / "output.nc") if (run_dir / "output.nc").exists() else None,
        "geojson": load_forefire_geojson(run_dir, scene_id),
    }


@app.get("/api/simulate/history")
def history() -> list[dict[str, Any]]:
    if not OUTPUT_DIR.exists():
        return []
    return [
        {
            "task_id": path.name,
            "output_nc": str(path / "output.nc") if (path / "output.nc").exists() else None,
            "geojson_count": len(list(path.glob("front_t*.geojson"))),
        }
        for path in sorted(OUTPUT_DIR.iterdir(), reverse=True)
        if path.is_dir()
    ]


def table_rows(table: str) -> list[dict[str, Any]]:
    init_demo_context_db()
    with archive_connection() as connection:
        rows = connection.execute(f"SELECT * FROM {table}").fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        for key, value in list(item.items()):
            if key.endswith("_json") and isinstance(value, str):
                item[key.removesuffix("_json")] = json.loads(value)
                del item[key]
        result.append(item)
    return result


@app.get("/api/context/fire-demo")
def fire_demo_context() -> dict[str, Any]:
    init_demo_context_db()
    return {
        "event_id": "muli-fire-demo-001",
        "event_name": "木里县森林火灾演示事件",
        "ignition_point": {
            "longitude": DEFAULT_LONGITUDE,
            "latitude": DEFAULT_LATITUDE,
        },
        "resource_inventory": table_rows("resource_inventory"),
        "personnel_units": table_rows("personnel_units"),
        "uav_assets": table_rows("uav_assets"),
        "vehicles": table_rows("vehicles"),
        "water_sources": table_rows("water_sources"),
        "shelters": table_rows("shelters"),
        "important_targets": table_rows("important_targets"),
        "road_segments": table_rows("road_segments"),
    }


@app.get("/api/resources/inventory")
def resource_inventory() -> list[dict[str, Any]]:
    return table_rows("resource_inventory")


@app.get("/api/resources/personnel")
def personnel_units() -> list[dict[str, Any]]:
    return table_rows("personnel_units")


@app.get("/api/uav/assets")
def uav_assets() -> list[dict[str, Any]]:
    return table_rows("uav_assets")


@app.get("/api/routes/network")
def route_network() -> dict[str, Any]:
    return {
        "road_segments": table_rows("road_segments"),
        "water_sources": table_rows("water_sources"),
        "shelters": table_rows("shelters"),
        "important_targets": table_rows("important_targets"),
    }


@app.post("/api/tasks/dispatch")
def create_dispatch_task(request: DispatchTaskRequest) -> dict[str, Any]:
    init_demo_context_db()
    task_id = request.task_id or f"task-{uuid.uuid4()}"
    now = utc_now_iso()
    with archive_connection() as connection:
        connection.execute(
            """
            INSERT INTO dispatch_tasks (
                task_id, event_id, owner, action, target, priority, status,
                eta_minutes, lng, lat, reason, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                event_id = excluded.event_id,
                owner = excluded.owner,
                action = excluded.action,
                target = excluded.target,
                priority = excluded.priority,
                status = excluded.status,
                eta_minutes = excluded.eta_minutes,
                lng = excluded.lng,
                lat = excluded.lat,
                reason = excluded.reason,
                updated_at = excluded.updated_at
            """,
            (
                task_id,
                request.event_id,
                request.owner,
                request.action,
                request.target,
                request.priority,
                request.status,
                request.eta_minutes,
                request.lng,
                request.lat,
                request.reason,
                now,
                now,
            ),
        )
    return {"ok": True, "task_id": task_id, "status": request.status}


@app.get("/api/tasks/dispatch")
def list_dispatch_tasks(event_id: str = "muli-fire-demo-001") -> list[dict[str, Any]]:
    init_demo_context_db()
    with archive_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM dispatch_tasks WHERE event_id = ? ORDER BY created_at DESC",
            (event_id,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/fire/archive")
def archive_fire_event(request: ArchiveRequest) -> dict[str, Any]:
    init_archive_db()
    event_id = build_event_id(request)
    archived_at = request.archived_at or utc_now_iso()
    created_at = request.created_at or archived_at
    ignition_lng, ignition_lat = archive_ignition_point(request)
    agent_payload = request.agent_result if request.agent_result is not None else request.agent_decision

    with archive_connection() as connection:
        connection.execute(
            """
            INSERT INTO fire_events (
                event_id,
                event_name,
                ignition_lng,
                ignition_lat,
                forefire_json,
                agent_json,
                agent_messages_json,
                derived_state_json,
                created_at,
                archived_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                event_name = excluded.event_name,
                ignition_lng = excluded.ignition_lng,
                ignition_lat = excluded.ignition_lat,
                forefire_json = excluded.forefire_json,
                agent_json = excluded.agent_json,
                agent_messages_json = excluded.agent_messages_json,
                derived_state_json = excluded.derived_state_json,
                created_at = excluded.created_at,
                archived_at = excluded.archived_at
            """,
            (
                event_id,
                request.event_name,
                ignition_lng,
                ignition_lat,
                json.dumps(request.forefire_result, ensure_ascii=False),
                json.dumps(agent_payload, ensure_ascii=False),
                json.dumps(request.agent_messages, ensure_ascii=False),
                json.dumps(request.derived_state, ensure_ascii=False),
                created_at,
                archived_at,
            ),
        )

    return {
        "ok": True,
        "status": "archived",
        "event_id": event_id,
        "event_name": request.event_name,
        "ignition_point": {
            "longitude": ignition_lng,
            "latitude": ignition_lat,
        },
        "created_at": created_at,
        "archived_at": archived_at,
    }


@app.get("/api/fire/archive")
def list_fire_archives() -> list[dict[str, Any]]:
    init_archive_db()
    with archive_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, event_id, event_name, ignition_lng, ignition_lat, created_at, archived_at
            FROM fire_events
            ORDER BY archived_at DESC
            """
        ).fetchall()
    return [archive_row_to_dict(row) for row in rows]


@app.get("/api/fire/archive/{event_id}")
def get_fire_archive(event_id: str) -> dict[str, Any]:
    init_archive_db()
    with archive_connection() as connection:
        row = connection.execute(
            "SELECT * FROM fire_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Fire archive not found: {event_id}")
    return archive_row_to_dict(row, include_payload=True)


@app.delete("/api/fire/archive/{event_id}")
def delete_fire_archive(event_id: str) -> dict[str, Any]:
    init_archive_db()
    with archive_connection() as connection:
        cursor = connection.execute("DELETE FROM fire_events WHERE event_id = ?", (event_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Fire archive not found: {event_id}")
    return {"ok": True, "status": "deleted", "event_id": event_id}
