import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[channel].add(websocket)
        await self.send_personal(
            websocket,
            {
                "type": "connection_ack",
                "channel": channel,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def disconnect(self, channel: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[channel].discard(websocket)
            if not self._connections[channel]:
                self._connections.pop(channel, None)

    async def send_personal(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        await websocket.send_text(json.dumps(message, ensure_ascii=False))

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections.get(channel, set()))
        stale: list[WebSocket] = []
        for websocket in targets:
            try:
                await self.send_personal(websocket, message)
            except Exception:
                stale.append(websocket)
        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections[channel].discard(websocket)

    async def broadcast_system_event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        await self.broadcast(
            "system",
            {
                "type": event_type,
                "payload": payload or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def broadcast_event(self, event_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        await self.broadcast(
            f"event:{event_id}",
            {
                "type": event_type,
                "event_id": event_id,
                "payload": payload or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def connection_count(self, channel: str | None = None) -> int:
        if channel:
            return len(self._connections.get(channel, set()))
        return sum(len(items) for items in self._connections.values())


websocket_manager = WebSocketManager()
