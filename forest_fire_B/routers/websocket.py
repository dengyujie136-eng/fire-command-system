# routers/websocket.py
import asyncio
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(
    prefix="/ws",
    tags=["websocket"]
)


# --- 连接管理器 (简单版) ---
# 在实际生产中，建议使用更健壮的连接管理类来处理断开重连和房间概念
class ConnectionManager:
    def __init__(self):
        # 统一管理在线连接和无人机状态
        # 当前所有已经链接的WebSocket客户端
        self.active_connections: List[WebSocket] = []
        # 无人机位置缓存，用于模拟无人机飞行
        self.uav_cache: Dict[str, dict] = {}

    # 连接建立方法
    # “客户端接入管理”的方法
    async def connect(self, websocket: WebSocket):
        # 接受WebSocket连接
        await websocket.accept()
        self.active_connections.append(websocket)

    # 断开连接方法
    # 把断开的WebSocket连接从活动列表中移除，断开之后就不再推送消息
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    # 更新无人机位置缓存
    # 把无人机位置信息更新到内存缓存中
    # 无人机坐标、高度、当前进度、状态等信息
    def update_uav_cache(self, uav_id: str, data: dict):
        self.uav_cache[uav_id] = data

    # 获取无人机位置缓存
    # 从内存缓存中获取指定无人机ID的最新位置信息
    def get_uav_cache(self, uav_id: str):
        return self.uav_cache.get(uav_id)

    # 广播消息方法
    # 向所有连接的客户端广播消息
    # 消息格式：{ "type": "alert" | "uav_position" | "uav_status", "data": ... }   
    # 火灾警报广播、无人机轨迹同步、实时状态更新
    async def broadcast(self, message: dict):
        """向所有连接的客户端广播消息"""
        # 记录断开的连接，稍后清理
        disconnected_clients = []
        # 遍历所有连接的客户端
        for connection in self.active_connections:
            # 尝试发送消息
            try:
                await connection.send_json(message)
            except Exception:
                # 记录断开的连接，稍后清理
                disconnected_clients.append(connection)

        # 清理断开的连接
        for client in disconnected_clients:
            self.disconnect(client)

# 创建连接管理器实例
# 全局唯一的连接管理器，负责管理所有WebSocket连接和无人机状态
manager = ConnectionManager()

# 火灾警报广播接口
# 每 5 秒向所有客户端广播一次警报消息
@router.websocket("/alert")
async def websocket_alert(websocket: WebSocket):
    """
    火灾警报广播接口
    每 5 秒向所有客户端广播一次警报消息
    """
    await manager.connect(websocket)
    try:
        while True:
            # 1. 发送警报消息
            alert_data = {
                "type": "alert",
                "message": "火势扩大",
                "timestamp": asyncio.get_event_loop().time()
            }
            await manager.broadcast(alert_data)
            
            # 2. 等待 5 秒
            await asyncio.sleep(5)
            
            # 3. 检查连接是否依然活跃 (可选，防止空转)
            # 如果客户端断开，send_json 会抛出异常，被外层 catch 捕获
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        print(f"Alert WebSocket Error: {e}")


@router.websocket("/uav")
async def websocket_uav(websocket: WebSocket):
    """
    无人机实时位置模拟接口
    模拟无人机从 (114.3, 30.5, 100) 飞向 (114.4, 30.6, 150)
    每秒更新一次位置
    """
    await manager.connect(websocket)

    # 定义起点和终点
    start_pos = {"lng": 114.3, "lat": 30.5, "alt": 100}
    end_pos = {"lng": 114.4, "lat": 30.6, "alt": 150}

    # 模拟飞行参数
    duration_seconds = 10  # 总飞行时间 10 秒
    steps = duration_seconds * 1  # 每秒 1 步

    try:
        for i in range(steps + 1):
            # 计算当前进度比例 (0.0 到 1.0)
            progress = i / steps

            # 线性插值计算当前位置
            current_lng = start_pos["lng"] + (end_pos["lng"] - start_pos["lng"]) * progress
            current_lat = start_pos["lat"] + (end_pos["lat"] - start_pos["lat"]) * progress
            current_alt = start_pos["alt"] + (end_pos["alt"] - start_pos["alt"]) * progress

            # 构建消息
            uav_data = {
                "type": "uav_position",
                "uav_id": "mock-uav-001",
                "lng": round(current_lng, 6),
                "lat": round(current_lat, 6),
                "alt": round(current_alt, 2),
                "progress": round(progress * 100, 1)
            }

            # 同步内存缓存
            manager.update_uav_cache("mock-uav-001", uav_data)

            # 广播给所有客户端
            await manager.broadcast(uav_data)

            # 等待 1 秒
            await asyncio.sleep(1)

        # 飞行结束，发送完成信号
        completed_payload = {
            "type": "uav_status",
            "uav_id": "mock-uav-001",
            "status": "completed",
            "message": "无人机已到达目标位置"
        }
        manager.update_uav_cache("mock-uav-001", completed_payload)
        await manager.broadcast(completed_payload)

        # 保持连接一段时间或等待客户端断开
        await asyncio.sleep(5)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        print(f"UAV WebSocket Error: {e}")


@router.websocket("/forefire")
async def websocket_forefire(websocket: WebSocket):
    """
    ForeFire 智能体实时通道。
    后端在生成决策、更新调度库存、生成路线时，会向该通道广播 JSON 消息。
    """
    await manager.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "forefire_ws_connected",
                "message": "ForeFire realtime channel connected",
                "supported_events": [
                    "forefire_decision_generated",
                    "dispatch_state_updated",
                    "route_plan_generated",
                ],
            }
        )
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        print(f"ForeFire WebSocket Error: {e}")
