from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.websocket_manager import websocket_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/system")
async def system_websocket(websocket: WebSocket) -> None:
    channel = "system"
    await websocket_manager.connect(channel, websocket)
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket_manager.send_personal(
                    websocket,
                    {
                        "type": "pong",
                        "channel": channel,
                        "payload": message.get("payload") or {},
                    },
                )
            else:
                await websocket_manager.send_personal(
                    websocket,
                    {
                        "type": "echo",
                        "channel": channel,
                        "payload": message,
                    },
                )
    except WebSocketDisconnect:
        await websocket_manager.disconnect(channel, websocket)


@router.websocket("/ws/events/{event_id}")
async def event_websocket(websocket: WebSocket, event_id: str) -> None:
    channel = f"event:{event_id}"
    await websocket_manager.connect(channel, websocket)
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket_manager.send_personal(
                    websocket,
                    {
                        "type": "pong",
                        "event_id": event_id,
                        "channel": channel,
                        "payload": message.get("payload") or {},
                    },
                )
            else:
                await websocket_manager.send_personal(
                    websocket,
                    {
                        "type": "echo",
                        "event_id": event_id,
                        "channel": channel,
                        "payload": message,
                    },
                )
    except WebSocketDisconnect:
        await websocket_manager.disconnect(channel, websocket)
