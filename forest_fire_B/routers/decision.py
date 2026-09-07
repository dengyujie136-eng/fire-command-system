# routers/decision.py
# 决策与路径规划模块
# 规划逃生路径、消防员前往火线的路线、根据火场面积做资源调度的建议、无人机航线巡检
# 包含简化版A*路径规划逻辑
# 偏向于应急决策类问题
import math
from typing import Dict, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import Task, get_db
import logging

# 创建日志记录器和路由器
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/b/decision", tags=["decision"])

# 请求体模型（逃生路径、消防员路径、无人机航线巡检）
# 定义前端调用接口时需要传入的数据格式
class EscapeRouteRequest(BaseModel):
    start_lng: float
    start_lat: float
    scene_id: str

class FirefighterRouteRequest(BaseModel):
    start_lng: float
    start_lat: float
    scene_id: str

class UAVScheduleRequest(BaseModel):
    scene_id: str

# 响应体格式（逃生路径、消防员路径、无人机航线巡检）
# 定义接口返回的数据格式
class EscapeRouteResponse(BaseModel):
    route: List[Dict[str, float]]
    distance: float
    estimated_time: float

class FirefighterRouteResponse(BaseModel):
    route: List[Dict[str, float]]
    distance: float
    estimated_time: float

class ResourceDispatchResponse(BaseModel):
    fire_trucks: int
    uavs: int
    firefighters: int
    message: str

class UAVScheduleResponse(BaseModel):
    waypoints: List[Dict[str, float]]
    total_distance: float
    estimated_time: float

# A*算法节点类
# 虽然这里定义了A*，但后面的a_star_algorithm函数并没有实现A*算法，而是实现了简化版的路径规划
class Node:
    """A*算法节点"""
    def __init__(self, x, y, cost=0, heuristic=0, parent=None):
        self.x = x
        self.y = y
        self.cost = cost
        self.heuristic = heuristic
        self.total = cost + heuristic
        self.parent = parent
    # 比较节点总代价
    # 用于在优先队列中排序
    def __lt__(self, other):
        return self.total < other.total

# A*算法实现路径规划
# 这个函数名字叫 A*，但实际上是一个简化版实现，不是完整 A* 搜索。
async def a_star_algorithm(
    start: tuple, 
    goal: tuple, 
    obstacles: List[List[float]],
    grid_size: float = 0.001
) -> List[Dict[str, float]]:
    """
    A*算法实现路径规划
    
    参数：
        start: 起点坐标 (lng, lat)
        goal: 终点坐标 (lng, lat)
        obstacles: 障碍物坐标列表
        grid_size: 网格大小
    
    返回：
        路径点列表
    """
    # 简化实现，实际项目中需要更复杂的算法
    # 这里返回一条直线路径
    route = []
    steps = 10
    for i in range(steps + 1):
        progress = i / steps
        lng = start[0] + (goal[0] - start[0]) * progress
        lat = start[1] + (goal[1] - start[1]) * progress
        route.append({"lng": lng, "lat": lat})
    return route

# 逃生路径规划接口
# 根据起点和场景ID，规划逃生路径
# 使用A*算法简化版实现路径规划
@router.post("/escape-route", response_model=EscapeRouteResponse)
async def get_escape_route(
    request: EscapeRouteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    逃生路径规划
    """
    try:
        # 1. 从数据库读取场景信息
        stmt = select(Task).where(Task.scene_id == request.scene_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        # 2. 获取当前火线
        current_fire_line = task.current_fire_geojson
        if not current_fire_line or "geometry" not in current_fire_line:
            raise HTTPException(status_code=400, detail="No fire line found in scene")
        
        # 3. 提取火线坐标作为障碍物
        obstacles = current_fire_line["geometry"].get("coordinates", [])
        
        # 4. 计算逃生目标点（远离火线）
        # 简单实现：计算火线的中心点，然后向反方向移动一定距离
        if obstacles:
            # 计算火线中心点
            avg_lng = sum(coord[0] for coord in obstacles) / len(obstacles)
            avg_lat = sum(coord[1] for coord in obstacles) / len(obstacles)
            
            # 计算远离方向（简单实现：向正北方向移动）
            goal_lng = request.start_lng
            goal_lat = request.start_lat + 0.05  # 向北移动约5公里
        else:
            # 如果没有火线，默认向正北方向移动
            goal_lng = request.start_lng
            goal_lat = request.start_lat + 0.05
        
        # 5. 使用A*算法规划路径
        route = await a_star_algorithm(
            (request.start_lng, request.start_lat),
            (goal_lng, goal_lat),
            obstacles
        )
        
        # 6. 计算距离和估计时间
        distance = 5.0  # 简化估算
        estimated_time = distance / 5.0  # 假设步行速度5km/h
        
        return EscapeRouteResponse(
            route=route,
            distance=distance,
            estimated_time=estimated_time
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get escape route error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get escape route: {str(e)}")

# 消防员路径规划接口
# 根据起点和场景ID，规划消防员前往火线的路线
# 使用A*算法简化版实现路径规划
@router.post("/firefighter-route", response_model=FirefighterRouteResponse)
async def get_firefighter_route(
    request: FirefighterRouteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    消防员路径规划
    """
    try:
        # 1. 从数据库读取场景信息
        stmt = select(Task).where(Task.scene_id == request.scene_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        # 2. 获取当前火线
        current_fire_line = task.current_fire_geojson
        if not current_fire_line or "geometry" not in current_fire_line:
            raise HTTPException(status_code=400, detail="No fire line found in scene")
        
        # 3. 提取火线坐标
        fire_line_coords = current_fire_line["geometry"].get("coordinates", [])
        
        # 4. 计算目标点（火线前沿）
        if fire_line_coords:
            # 简单实现：选择火线的第一个点作为目标
            goal_lng, goal_lat = fire_line_coords[0]
        else:
            raise HTTPException(status_code=400, detail="No coordinates found in fire line")
        
        # 5. 使用A*算法规划路径
        route = await a_star_algorithm(
            (request.start_lng, request.start_lat),
            (goal_lng, goal_lat),
            []  # 消防员需要接近火线，所以不将火线视为障碍物
        )
        
        # 6. 计算距离和估计时间
        distance = 2.0  # 简化估算
        estimated_time = distance / 10.0  # 假设车辆速度10km/h
        
        return FirefighterRouteResponse(
            route=route,
            distance=distance,
            estimated_time=estimated_time
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get firefighter route error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get firefighter route: {str(e)}")

# 资源调度接口
# 根据场景ID，根据火场面积计算所需资源
# 简单规则引擎实现
@router.get("/resource-dispatch/{scene_id}", response_model=ResourceDispatchResponse)
async def get_resource_dispatch(
    scene_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    资源调度
    """
    try:
        # 1. 从数据库读取场景信息
        stmt = select(Task).where(Task.scene_id == scene_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        # 2. 计算火场面积（简单估算）
        fire_area = 0.0
        if task.current_fire_geojson and "geometry" in task.current_fire_geojson:
            coordinates = task.current_fire_geojson["geometry"].get("coordinates", [])
            if coordinates:
                fire_area = len(coordinates) * 0.01  # 简化估算
        
        # 3. 根据火场面积和蔓延速度计算所需资源
        # 简单规则引擎
        fire_trucks = max(1, int(fire_area / 2))  # 每2单位面积需要1辆消防车
        uavs = max(1, int(fire_area / 5))  # 每5单位面积需要1架无人机
        firefighters = fire_trucks * 3  # 每辆消防车配备3名消防员
        
        message = f"根据火场面积 {fire_area:.2f} 单位，建议调度 {fire_trucks} 辆消防车，{uavs} 架无人机，{firefighters} 名消防员"
        
        return ResourceDispatchResponse(
            fire_trucks=fire_trucks,
            uavs=uavs,
            firefighters=firefighters,
            message=message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get resource dispatch error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get resource dispatch: {str(e)}")

# 无人机航线巡检路径规划接口
# 根据场景ID，规划无人机航线巡检路径
# 使用简化版实现路径规划
@router.post("/uav/schedule", response_model=UAVScheduleResponse)
async def schedule_uav(
    request: UAVScheduleRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    无人机巡检路径规划
    """
    try:
        # 1. 从数据库读取场景信息
        stmt = select(Task).where(Task.scene_id == request.scene_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Scene not found")
        
        # 2. 获取当前火线
        current_fire_line = task.current_fire_geojson
        if not current_fire_line or "geometry" not in current_fire_line:
            raise HTTPException(status_code=400, detail="No fire line found in scene")
        
        # 3. 提取火线坐标
        fire_line_coords = current_fire_line["geometry"].get("coordinates", [])
        
        # 4. 生成绕火线的巡检路径
        waypoints = []
        if fire_line_coords:
            # 简单实现：在火线外围生成一个环形路径
            for coord in fire_line_coords:
                # 向外偏移0.002度（约200米）
                waypoints.append({
                    "lng": coord[0] + 0.002,
                    "lat": coord[1] + 0.002,
                    "alt": 100.0  # 飞行高度100米
                })
            # 闭合路径
            if waypoints:
                waypoints.append(waypoints[0])
        else:
            # 如果没有火线，生成一个默认的圆形路径
            center_lng, center_lat = 114.3, 30.5
            for i in range(8):
                angle = (i / 8) * 2 * 3.14159
                waypoints.append({
                    "lng": center_lng + 0.005 * math.cos(angle),
                    "lat": center_lat + 0.005 * math.sin(angle),
                    "alt": 100.0
                })
            waypoints.append(waypoints[0])
        
        # 5. 计算总距离和估计时间
        total_distance = 5.0  # 简化估算
        estimated_time = total_distance / 50.0  # 假设无人机速度50km/h
        
        return UAVScheduleResponse(
            waypoints=waypoints,
            total_distance=total_distance,
            estimated_time=estimated_time
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Schedule UAV error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule UAV: {str(e)}")
