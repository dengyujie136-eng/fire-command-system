# routers/simulate.py
# 火灾模拟接口
# 前端提交模拟参数
# start_simulation()创建任务并返回task_id
# 后台run_simulation_task()调外部服务执行模拟
# 结果写入simulation_store
# 前端通过get_simulation_result()轮询查询结果
import uuid
from typing import Dict, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

# 引入新创建的客户端函数
from clients.c_client import call_c_simulate

# 这个文件专门负责“火灾模拟”相关接口
router = APIRouter(
    prefix="/simulate",
    tags=["simulation"]
)

# 简单的内存存储，用于保存模拟任务的状态和结果
# 结构: { task_id: { "status": str, "result": Optional[dict], "error": Optional[str] } }
simulation_store: Dict[str, Dict[str, Any]] = {}

# 定义请求体模型，前端调用模拟接口要传什么参数
class SimulationRequest(BaseModel):
    """
    请求体模型
    """
    fire_point: list[float]
    wind_speed: float
    wind_dir: float
    terrain: str
    steps: int = 10  # 添加 steps 字段，可选，默认 10
    
    class Config:
        extra = "allow"

# 后台任务：调用 C 同学的真实模拟 API 并格式化结果
# 这是真正执行模拟的后台逻辑
async def run_simulation_task(task_id: str, params: dict):
    """
    后台任务：调用 C 同学的真实模拟 API 并格式化结果
    """
    try:
        # 1. 调用真实 API (内部已包含 detect 和 spread 两步)
        c_response = await call_c_simulate(params)
        
        # 2. 数据格式转换: 与 clients.c_client.call_c_simulate 返回保持一致
        fire_lines = c_response.get("result", {}).get("fire_lines", [])
        if not isinstance(fire_lines, list):
            raise Exception("Invalid response from simulate API: missing fire_lines")

        formatted_result = {
            "incident_id": c_response.get("incident_id"),
            "simulation_id": c_response.get("simulation_id"),
            "fire_lines": fire_lines,
        }
        
        # 3. 保存成功结果
        simulation_store[task_id] = {
            "status": "completed",
            "result": formatted_result
        }
                
    except Exception as e:
        # 4. 保存失败状态和错误信息
        simulation_store[task_id] = {
            "status": "failed",
            "error": str(e)
        }


# 启动模拟接口
# 这个接口是前端调用的入口，负责接收请求并启动后台任务
@router.post("/", response_model=dict)
async def start_simulation(
    background_tasks: BackgroundTasks,
    request: SimulationRequest
):
    """
    启动火灾蔓延模拟
    """
    task_id = str(uuid.uuid4())
    
    # 初始化任务状态为 pending
    simulation_store[task_id] = {
        "status": "pending",
        "result": None
    }
    
    # 添加后台任务
    # 将 Pydantic 模型转换为字典以便传递
    background_tasks.add_task(run_simulation_task, task_id, request.model_dump())
    
    return {
        "task_id": task_id,
        "status": "pending"
    }

# 查询模拟结果接口
# 这个接口是前端轮询查询结果的入口，负责接收任务 ID 并返回结果
@router.get("/result/{task_id}", response_model=dict)
async def get_simulation_result(task_id: str):
    """
    查询模拟结果
    """
    if task_id not in simulation_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = simulation_store[task_id]
    
    response = {
        "task_id": task_id,
        "status": task_data["status"]
    }
    
    # 如果已完成，附加结果
    if task_data["status"] == "completed":
        response["result"] = task_data["result"]
    elif task_data["status"] == "failed":
        response["error"] = task_data.get("error")
        
    return response