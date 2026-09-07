# routers/tasks.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, Optional
import uuid
from routers.auth import get_current_user # 导入认证依赖

# 建议：查看 routers/auth.py 中 get_current_user 的返回类型提示，通常是 User 模型
# from schemas.user import User 

router = APIRouter(
    prefix="/task",
    tags=["任务管理"]
)

# 模拟任务数据库: { task_id: { ...task_data... } }
tasks_db: Dict[str, Dict[str, Any]] = {}

# 定义请求模型，允许额外字段 (用于创建任务)
class TaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

@router.post("/create")
def create_task(
    request: TaskCreateRequest, 
    current_user = Depends(get_current_user)
):
    task_id = str(uuid.uuid4())
    task_data = request.model_dump()
    
    # 修复：使用 .username 而不是 ["username"]
    owner_name = current_user.username
    
    new_task = {
        "task_id": task_id,
        "status": "pending",
        "owner": owner_name,
        "params": task_data,
        "result": None
    }
    
    tasks_db[task_id] = new_task
    
    return {
        "task_id": task_id,
        "status": "pending"
    }

# --- 任务查询接口 ---
@router.get("/{task_id}")
def get_task(task_id: str, current_user = Depends(get_current_user)):
    """
    根据 task_id 查询任务详情
    """
    # 1. 从内存字典中查找
    task = tasks_db.get(task_id)
    
    # 2. 如果未找到，返回 404
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 【修复点 2】获取当前登录用户的用户名用于权限比对
    try:
        current_username = current_user.username
    except AttributeError:
        current_username = current_user.get("username") if isinstance(current_user, dict) else ""

    # 3. 权限检查：确保用户只能查看自己的任务
    if task.get("owner") != current_user.username:   # 也要用 .username
        raise HTTPException(status_code=403, detail="Not authorized")

    # 4. 返回任务详情
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "params": task["params"],
        "result": task["result"]
    }