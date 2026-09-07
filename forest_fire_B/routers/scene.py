# routers/scene.py
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import Task, get_db
from clients.c_client import (
    call_create_incident,
    call_ingest_incident,
    call_start_simulation,
    call_get_simulation_result,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/b/scene", tags=["scene"])

# 场景创建请求模型
# 定义了创建场景时需要传入的参数
class SceneCreateRequest(BaseModel):
    fire_point: list[float] = [114.3, 30.5]
    wind_speed: float
    wind_dir: float
    terrain: str = "mountain"
    area_bbox: Optional[list[float]] = None
    source: str = "manual"

# 场景步进请求模型
# 定义了步进场景时需要传入的参数（风速、风向可选）
class SceneStepRequest(BaseModel):
    wind_speed: Optional[float] = None
    wind_dir: Optional[float] = None

# 创建一个新的火场场景，并初始化对应的数据库任务和初始火线
# 把新场景注册到C端模拟系统里，并返回场景ID和任务ID
@router.post("/create")
async def create_scene(
    request: SceneCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    创建新场景
    1. 按 C v1 合同创建 incident + ingest
    2. 生成初始火线（小圆圈）
    3. 存入数据库并保存 incident_id
    """
    try:
        # 1. 生成场景ID
        scene_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        
        # 2. 创建事件并接入数据（严格走 C v1 主链路前两步）
        now = datetime.now(timezone.utc).replace(microsecond=0)
        start = (now - timedelta(hours=12)).replace(microsecond=0)
        fire_point = request.fire_point
        if not isinstance(fire_point, list) or len(fire_point) < 2:
            raise HTTPException(status_code=400, detail="fire_point must be [lng, lat]")
        lng, lat = float(fire_point[0]), float(fire_point[1])

        area_bbox = request.area_bbox or [lng - 0.2, lat - 0.2, lng + 0.2, lat + 0.2]
        incident_payload = {
            "name": f"scene_{scene_id}",
            "source": request.source,
            "fire_point": [lng, lat],
            "area_bbox": area_bbox,
            "start_time": now.isoformat(),
        }
        incident_res = await call_create_incident(incident_payload)
        incident_id = incident_res.get("incident_id")
        if not incident_id:
            raise HTTPException(status_code=500, detail=f"C create incident failed: {incident_res}")

        ingest_payload = {
            "time_range": {"start": start.isoformat(), "end": now.isoformat()},
            "sources": {
                "satellite": "sentinel_hub",
                "weather": "open_meteo",
                "terrain": request.terrain,
                "landcover": "worldcover",
            },
        }
        ingest_res = await call_ingest_incident(incident_id, ingest_payload)
        
        # 3. 生成初始火线（小圆圈）
        initial_fire_line = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [lng - 0.001, lat],
                    [lng, lat + 0.001],
                    [lng + 0.001, lat],
                    [lng, lat - 0.001],
                    [lng - 0.001, lat]
                ]
            },
            "properties": {
                "timestamp": asyncio.get_event_loop().time(),
                "step": 0
            }
        }
        
        # 4. 存储到数据库
        new_task = Task(
            task_id=task_id,
            scene_id=scene_id,
            owner="system",
            status="running",
            params=request.dict(),
            wind_params={
                "wind_speed": request.wind_speed,
                "wind_dir": request.wind_dir
            },
            current_fire_geojson=initial_fire_line,
            current_step=0
        )
        new_task.params = {
            **(new_task.params or {}),
            "incident_id": incident_id,
            "ingest": ingest_res,
        }
        
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)
        
        return {
            "scene_id": scene_id,
            "task_id": task_id,
            "status": "created",
            "incident_id": incident_id,
            "initial_fire_line": initial_fire_line
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create scene error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create scene: {str(e)}")

@router.post("/{scene_id}/step")
async def step_scene(
    scene_id: str,
    request: SceneStepRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    场景步进模拟
    1. 从数据库读取当前火线
    2. 提取起点
    3. 调用 C v1 simulations/result 得到新火线
    4. 更新数据库
    5. 返回新火线
    """
    try:
        # 1. 从数据库读取场景信息
        stmt = select(Task).where(Task.scene_id == scene_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        # 2. 提取当前火线的起点
        current_fire_line = task.current_fire_geojson
        if not current_fire_line or "geometry" not in current_fire_line:
            raise HTTPException(status_code=400, detail="No fire line found in scene")
        
        # 提取起点（使用第一个坐标点）
        coordinates = current_fire_line["geometry"].get("coordinates", [])
        if not coordinates:
            raise HTTPException(status_code=400, detail="No coordinates found in fire line")
        
        start_lng, start_lat = coordinates[0]
        
        # 3. 获取风速风向参数
        wind_speed = request.wind_speed or task.wind_params.get("wind_speed", 5.0)
        wind_dir = request.wind_dir or task.wind_params.get("wind_dir", 45.0)

        incident_id = (task.params or {}).get("incident_id")
        if not incident_id:
            raise HTTPException(status_code=400, detail="Scene missing incident_id, recreate scene")

        # 4. 启动模拟并读取结果（严格按合同）
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
            raise HTTPException(status_code=500, detail=f"Start simulation failed: {sim_start}")

        sim_result = await call_get_simulation_result(simulation_id)
        fire_lines = sim_result.get("result", {}).get("fire_lines", [])
        if not isinstance(fire_lines, list) or not fire_lines:
            raise HTTPException(status_code=500, detail=f"No fire_lines in simulation result: {sim_result}")
        last_line = fire_lines[-1]
        geometry = last_line.get("geometry")
        if not isinstance(geometry, dict):
            raise HTTPException(status_code=500, detail=f"Invalid geometry in simulation result: {last_line}")
        new_fire_line = {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "timestamp": last_line.get("timestamp"),
                "time_index": last_line.get("time_index"),
                "simulation_id": simulation_id,
            },
        }
        
        # 5. 更新数据库
        task.current_fire_geojson = new_fire_line
        task.current_step += 1
        task.wind_params = {
            "wind_speed": wind_speed,
            "wind_dir": wind_dir
        }
        
        await db.commit()
        await db.refresh(task)
        
        return {
            "scene_id": scene_id,
            "step": task.current_step,
            "simulation_id": simulation_id,
            "fire_line": new_fire_line
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Step scene error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to step scene: {str(e)}")

@router.get("/{scene_id}/fire-line")
async def get_scene_fire_line(
    scene_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    返回当前火线的GeoJSON
    """
    try:
        # 从数据库读取场景信息
        stmt = select(Task).where(Task.scene_id == scene_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        return {
            "scene_id": scene_id,
            "fire_line": task.current_fire_geojson
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get fire line error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get fire line: {str(e)}")

@router.get("/{scene_id}/status")
async def get_scene_status(
    scene_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    返回当前火场状态
    """
    try:
        # 从数据库读取场景信息
        stmt = select(Task).where(Task.scene_id == scene_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        # 计算火场面积（简单估算）
        fire_area = 0.0
        if task.current_fire_geojson and "geometry" in task.current_fire_geojson:
            # 简单估算：基于坐标点数量
            coordinates = task.current_fire_geojson["geometry"].get("coordinates", [])
            if coordinates:
                fire_area = len(coordinates) * 0.01  # 简化估算
        
        # 计算蔓延速度（简单估算）
        spread_speed = 0.0
        if task.current_step > 0:
            # 简化估算：假设每步蔓延1单位距离
            spread_speed = 1.0
        
        return {
            "scene_id": scene_id,
            "status": task.status,
            "current_step": task.current_step,
            "fire_area": fire_area,
            "spread_speed": spread_speed,
            "last_update": task.last_update.isoformat() if task.last_update else None,
            "wind_params": task.wind_params
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get scene status error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scene status: {str(e)}")
