import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import map, navigation, robot
from services.robot_service import robot_service
from websocket.manager import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def on_telemetry(event_type: str, payload: dict) -> None:
        await ws_manager.broadcast(event_type, payload)

    await robot_service.connect()
    robot_service.on_telemetry(on_telemetry)
    yield
    await robot_service.disconnect()


app = FastAPI(
    title="CYBEL API",
    description="Plateforme de commande robot CIOT TY1251D",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(robot.router)
app.include_router(navigation.router)
app.include_router(map.router)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "mock": robot_service.is_mock,
        "robot_host": settings.robot_host,
    }


@app.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        await websocket.send_text(
            json.dumps({"type": "status", **robot_service.get_status().model_dump()})
        )
        await websocket.send_text(
            json.dumps({"type": "pose", **robot_service.get_pose().model_dump()})
        )
        map_data = robot_service.get_map()
        if map_data:
            await websocket.send_text(
                json.dumps({"type": "map", **map_data.model_dump()})
            )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
