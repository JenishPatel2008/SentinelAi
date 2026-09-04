import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["WebSocket"])

class ConnectionManager:
    def __init__(self):
        self.connections: list[tuple[WebSocket, asyncio.AbstractEventLoop]] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append((websocket, asyncio.get_running_loop()))

    def disconnect(self, websocket: WebSocket):
        self.connections = [(item, loop) for item, loop in self.connections if item is not websocket]

    async def broadcast(self, payload: dict):
        for websocket, _ in self.connections[:]:
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(websocket)

    def broadcast_from_sync(self, payload: dict):
        for websocket, loop in self.connections[:]:
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(websocket.send_json(payload), loop)

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
