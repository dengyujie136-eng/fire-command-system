import asyncio
import websockets
import json

async def test_alert():
    uri = "ws://localhost:8100/ws/alert"
    async with websockets.connect(uri) as websocket:
        print("Connected to Alert WS")
        for _ in range(3): # 接收 3 次消息
            msg = await websocket.recv()
            print(f"Alert Received: {msg}")

async def test_uav():
    uri = "ws://localhost:8100/ws/uav"
    async with websockets.connect(uri) as websocket:
        print("Connected to UAV WS")
        while True:
            msg = await websocket.recv()
            data = json.loads(msg)
            print(f"UAV Received: {data}")
            if data.get("type") == "uav_status" and data.get("status") == "completed":
                break

# 运行测试
# asyncio.run(test_alert())
asyncio.run(test_uav())
