import logging
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

# 按接口合同默认使用本地 C 服务地址，可通过环境变量覆盖
# 确认客户端默认去哪里找C服务，以及等待时间
C_API_BASE_URL = os.getenv("WILDFIRE_C_API_BASE_URL", "http://127.0.0.1:8888")
TIMEOUT_SECONDS = 60.0

# 辅助函数：发送 POST 请求并返回 JSON 响应
async def _post_json(client: httpx.AsyncClient, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{C_API_BASE_URL}{path}"
    resp = await client.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()

# 辅助函数：发送 GET 请求并返回 JSON 响应
async def _get_json(client: httpx.AsyncClient, path: str) -> Dict[str, Any]:
    url = f"{C_API_BASE_URL}{path}"
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()

# 辅助函数：构建默认边界框
# 如果调用方没有提供边界，就使用这个默认边界框（默认分析区域）
def _build_default_bbox(fire_point: List[float]) -> List[float]:
    lng, lat = fire_point
    delta = 0.2
    return [lng - delta, lat - delta, lng + delta, lat + delta]

# 创建事件接口
# 调用 C 服务的 /api/v1/incidents 接口，创建事件
# 是整个模拟流程的第一步
async def call_create_incident(payload: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, trust_env=False) as client:
        return await _post_json(client, "/api/v1/incidents", payload)

# 接入数据接口
# 调用 C 服务的 /api/v1/incidents/{incident_id}/ingest 接口，接入数据
# 是整个模拟流程的第二步：把外部环境和数据源信息灌入事故
# 向C服务补充事故相关环境数据的接口封装
async def call_ingest_incident(incident_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, trust_env=False) as client:
        return await _post_json(client, f"/api/v1/incidents/{incident_id}/ingest", payload)

# 启动模拟接口
# 调用 C 服务的 /api/v1/incidents/{incident_id}/simulations 接口，启动模拟
# 是整个模拟流程的第三步：真正开始模拟计算
# 给指定incident_id创建一个simulation，传入模型类型、步数、时间步长、随机种子等参数
async def call_start_simulation(incident_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, trust_env=False) as client:
        return await _post_json(client, f"/api/v1/incidents/{incident_id}/simulations", payload)

# 查询模拟状态接口
# 调用 C 服务的 /api/v1/simulations/{simulation_id} 接口，查询模拟状态
# 是整个模拟流程的第四步：查询模拟计算进度
# 获取指定simulation_id的模拟状态，可能返回running,completed,falied,queued
async def call_get_simulation_status(simulation_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, trust_env=False) as client:
        return await _get_json(client, f"/api/v1/simulations/{simulation_id}")

# 查询模拟结果接口
# 调用 C 服务的 /api/v1/simulations/{simulation_id}/result 接口，查询模拟结果
# 是整个模拟流程的第五步（也是最后一步）：获取模拟计算结果
# 获取指定simulation_id的模拟后的火线、结果状态、相关产物数据等
async def call_get_simulation_result(simulation_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, trust_env=False) as client:
        return await _get_json(client, f"/api/v1/simulations/{simulation_id}/result")

# 辅助函数：构建圆形火线
# 把火点周围一圈点连成LineString，用于可视化展示
# 如果模拟结果里没有真实火线或者接口返回不完整，就用这个假定火线兜底
def _build_circle_linestring(lng: float, lat: float, radius_deg: float = 0.002, points: int = 12) -> Dict[str, Any]:
    coordinates: List[List[float]] = []
    for i in range(points + 1):
        angle = (2 * math.pi * i) / points
        coordinates.append(
            [
                round(lng + radius_deg * math.cos(angle), 6),
                round(lat + radius_deg * math.sin(angle), 6),
            ]
        )
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": {"source": "fallback"},
    }


# 辅助函数：提取模拟结果中的第一条火线
# 如果模拟结果里没有真实火线或者接口返回不完整，就用这个假定火线兜底
def _extract_first_fire_line(sim_result: Dict[str, Any]) -> Dict[str, Any]:
    # 从模拟结果中提取火线列表
    fire_lines = sim_result.get("result", {}).get("fire_lines", [])
    if isinstance(fire_lines, list) and fire_lines:
        # 提取第一条火线
        first = fire_lines[0]
        if isinstance(first, dict) and "geometry" in first:
            return {
                "type": "Feature",
                "geometry": first["geometry"],
                "properties": {"source": "simulate_result"},
            }
    fire_point = sim_result.get("result", {}).get("fire_point", [114.3, 30.5])
    lng, lat = float(fire_point[0]), float(fire_point[1])
    return _build_circle_linestring(lng, lat)

# 核心模拟链路
# 串联C服务：创建事故-灌入数据-启动模拟-获取结果
async def call_c_simulate(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    统一走 C 的 V1 主链路：
    1) POST /api/v1/incidents
    2) POST /api/v1/incidents/{incident_id}/ingest
    3) POST /api/v1/incidents/{incident_id}/simulations
    4) GET  /api/v1/simulations/{simulation_id}/result
    """
    # 提取火点参数
    fire_point = params.get("fire_point")
    if not isinstance(fire_point, list) or len(fire_point) < 2:
        raise ValueError("Missing required parameter: fire_point [lng, lat]")
    # 提取模拟参数
    steps = int(params.get("steps", 12))
    time_step_minutes = int(params.get("time_step_minutes", 10))
    terrain = params.get("terrain", "local_dem")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = (now - timedelta(hours=12)).replace(microsecond=0)

    # 构建事故创建请求体
    incident_payload = {
        "name": params.get("incident_name", f"incident_{now.strftime('%Y%m%d_%H%M%S')}"),
        "source": params.get("source", "manual"),
        "fire_point": [float(fire_point[0]), float(fire_point[1])],
        "area_bbox": params.get("area_bbox", _build_default_bbox(fire_point)),
        "start_time": params.get("start_time", now.isoformat()),
    }

    # 构建数据接入请求体
    ingest_payload = {
        "time_range": {
            "start": params.get("ingest_start", start.isoformat()),
            "end": params.get("ingest_end", now.isoformat()),
        },
        "sources": {
            "satellite": params.get("satellite_source", "sentinel_hub"),
            "weather": params.get("weather_source", "open_meteo"),
            "terrain": terrain,
            "landcover": params.get("landcover_source", "worldcover"),
        },
        "sentinel_client_id": params.get("sentinel_client_id"),
        "sentinel_client_secret": params.get("sentinel_client_secret"),
    }

    # 构建模拟启动请求体
    simulation_payload = {
        "model": params.get("model", "ca_v1"),
        "steps": steps,
        "time_step_minutes": time_step_minutes,
        "seed": int(params.get("seed", 42)),
    }

    # 执行完整链路
    try:
        created = await call_create_incident(incident_payload)
        incident_id = created.get("incident_id")
        if not incident_id:
            raise Exception(f"Create incident missing incident_id: {created}")

        ingest_result = await call_ingest_incident(incident_id, ingest_payload)

        sim_created = await call_start_simulation(incident_id, simulation_payload)
        simulation_id = sim_created.get("simulation_id")
        if not simulation_id:
            raise Exception(f"Start simulation missing simulation_id: {sim_created}")

        result = await call_get_simulation_result(simulation_id)
        return {
            "incident_id": incident_id,
            "ingest": ingest_result,
            "simulation_id": simulation_id,
            "status": result.get("status", "completed"),
            "result": result.get("result", {}),
        }
    except httpx.HTTPStatusError as e:
        error_msg = (
            f"API Error. Status: {e.response.status_code}, "
            f"URL: {e.request.url}, Response: {e.response.text}"
        )
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Failed calling C V1 flow: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


async def call_fire_detect() -> List[Dict[str, float]]:
    """
    兼容旧逻辑：当前合同不提供 detect 接口，因此只返回默认火点。
    """
    logger.warning("fire-detect is not part of C v1 contract, using fallback fire point")
    return [{"lng": 114.3, "lat": 30.5}]


async def call_predict_spread(
    start_lng: float,
    start_lat: float,
    wind_dir: float,
    wind_speed: float,
    steps: int = 1,
) -> Dict[str, Any]:
    """
    兼容旧逻辑：当前合同不提供 predict/spread 接口。
    这里通过主链路做一次 steps=1 模拟并返回最新火线。
    """
    flow_result = await call_c_simulate(
        {
            "fire_point": [start_lng, start_lat],
            "wind_dir": wind_dir,
            "wind_speed": wind_speed,
            "steps": steps,
            "time_step_minutes": 10,
            "terrain": "local_dem",
        }
    )
    fire_lines = flow_result.get("result", {}).get("fire_lines", [])
    if isinstance(fire_lines, list) and fire_lines:
        last = fire_lines[-1]
        if isinstance(last, dict) and "geometry" in last:
            return {
                "type": "Feature",
                "geometry": last["geometry"],
                "properties": {"source": "simulation_result"},
            }
    direction_rad = math.radians(wind_dir)
    shift = max(0.0003, min(0.003, wind_speed * 0.00008))
    next_lng = start_lng + shift * math.cos(direction_rad)
    next_lat = start_lat + shift * math.sin(direction_rad)
    return _build_circle_linestring(next_lng, next_lat, radius_deg=0.002)


async def call_fire_intensity(scene_id: str) -> Dict[str, Any]:
    """
    合同中无该接口，保留兼容返回。
    """
    logger.warning("fire-intensity is not part of C v1 contract, using fallback intensity")
    return {
        "scene_id": scene_id,
        "intensity_level": "medium",
        "score": 0.6,
        "source": "fallback",
    }
