import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from routers import charge, diagnostics, history, knowledge, map, mqtt, navigation, patrol, reception, robot, settings as settings_router, speech, tour
from services.charge_service import charge_service
from services.mqtt_bridge_service import mqtt_bridge_service
from services.robot_service import robot_service
from websocket.manager import ws_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def on_telemetry(event_type: str, payload: dict) -> None:
        await ws_manager.broadcast(event_type, payload)

    async def adb_health_loop() -> None:
        while True:
            await asyncio.sleep(90)
            if settings.robot_mock:
                continue
            try:
                result = await robot_service.ensure_adb_tts()
                if not result.get("ok"):
                    logger.debug("Health ADB TTS : %s", result)
            except Exception as exc:
                logger.debug("Health ADB TTS échoué : %s", exc)

    # Télémétrie enregistrée avant connect pour être rattachée au backend.
    robot_service.on_telemetry(on_telemetry)
    charge_service.attach(robot_service)
    await robot_service.connect()
    await mqtt_bridge_service.start(on_telemetry)
    adb_health_task = asyncio.create_task(adb_health_loop())
    yield
    adb_health_task.cancel()
    try:
        await adb_health_task
    except asyncio.CancelledError:
        pass
    await mqtt_bridge_service.stop()
    await robot_service.disconnect()


app = FastAPI(
    title="CYBEL API",
    description="Plateforme de commande robot CIOT TY1251D",
    version="0.2.0",
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
app.include_router(charge.router)
app.include_router(mqtt.router)
app.include_router(history.router)
app.include_router(navigation.router)
app.include_router(map.router)
app.include_router(settings_router.router)
app.include_router(reception.router)
app.include_router(speech.router)
app.include_router(knowledge.router)
app.include_router(tour.router)
app.include_router(patrol.router)
app.include_router(diagnostics.router)


KIOSK_DIST = ROOT / "frontend-kiosk" / "dist"
if KIOSK_DIST.is_dir():
    app.mount("/kiosk", StaticFiles(directory=str(KIOSK_DIST), html=True), name="kiosk")


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "mock": robot_service.is_mock,
        "robot_host": settings.robot_host,
        "mqtt": mqtt_bridge_service.get_status(),
        "version": "0.2.0",
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
