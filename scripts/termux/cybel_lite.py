#!/usr/bin/env python3
"""Backend CYBEL léger pour Termux — sans FastAPI/pydantic (pas de compilation Rust)."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import uvicorn
import websockets
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

CYBEL_HOME = Path(os.environ.get("CYBEL_HOME", Path.home() / "cybel"))
ACTIONS_PATH = CYBEL_HOME / "scripts" / "termux" / "actions.json"
FAQ_PATH = CYBEL_HOME / "data" / "hestim_knowledge_base.json"
TOUR_PATH = CYBEL_HOME / "data" / "lab_tour.json"
KIOSK_DIST = CYBEL_HOME / "frontend-kiosk" / "dist"

if str(CYBEL_HOME) not in sys.path:
    sys.path.insert(0, str(CYBEL_HOME))

from sdk.lab_tour import TourEngine, load_lab_tour, tour_public_payload

ROBOT_HOST = os.environ.get("ROBOT_HOST", "192.168.20.22")
ROBOT_WS_PORT = int(os.environ.get("ROBOT_WS_PORT", "9090"))
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8000"))

TTS_RECEIVER = "com.cybel.ttsbridge/.SpeakReceiver"
TTS_ACTION = "com.cybel.ttsbridge.SPEAK"


def load_actions() -> list[dict]:
    with open(ACTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_faq() -> list[dict]:
    if not FAQ_PATH.is_file():
        return []
    with open(FAQ_PATH, encoding="utf-8") as f:
        return json.load(f).get("faq", [])


def find_action(action_id: str) -> dict | None:
    return next((a for a in load_actions() if a["id"] == action_id), None)


def pick_speech(action: dict, lang: str) -> str | None:
    if lang == "en":
        return action.get("speech_en") or action.get("speech")
    return action.get("speech")


def speak_local(text: str) -> bool:
    escaped = text.replace("'", "'\\''")
    broadcast = (
        f"am broadcast -n {TTS_RECEIVER} -a {TTS_ACTION} --es text '{escaped}'"
    )
    for cmd in (broadcast, f"su -c '{broadcast}'"):
        try:
            result = subprocess.run(
                ["sh", "-c", cmd],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
    return False


async def ros_call_service(service: str, args: dict, timeout: float = 5.0) -> dict:
    uri = f"ws://{ROBOT_HOST}:{ROBOT_WS_PORT}"
    async with websockets.connect(uri, open_timeout=timeout) as ws:
        await ws.send(
            json.dumps({"op": "call_service", "service": service, "args": args})
        )
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            data = json.loads(raw)
            if data.get("op") == "service_response" and data.get("service") == service:
                return data.get("values") or data
            if data.get("op") == "status" and data.get("level") == "error":
                raise RuntimeError(data.get("msg", "rosbridge error"))


async def navigate_to_point(point_name: str) -> None:
    await ros_call_service(
        "/poi",
        {"name": point_name, "point_name": point_name, "command": "go"},
    )


async def stop_robot() -> None:
    try:
        await ros_call_service("/path_follower/cancel", {})
    except Exception:
        pass
    try:
        uri = f"ws://{ROBOT_HOST}:{ROBOT_WS_PORT}"
        async with websockets.connect(uri, open_timeout=3) as ws:
            await ws.send(
                json.dumps(
                    {
                        "op": "publish",
                        "topic": "/mobile_base/commands/velocity",
                        "msg": {
                            "linear": {"x": 0, "y": 0, "z": 0},
                            "angular": {"x": 0, "y": 0, "z": 0},
                        },
                    }
                )
            )
    except Exception:
        pass


async def execute_action(action_id: str, lang: str) -> dict:
    action = find_action(action_id)
    if not action:
        return {"ok": False, "error": f"Action '{action_id}' inconnue"}

    events: list[str] = []

    if action_id == "stop_all":
        await stop_robot()
        events.append("Action interrompue")
        return {"ok": True, "action": action_id, "events": events}

    speech = pick_speech(action, lang)
    if speech:
        if speak_local(speech):
            events.append(f"Annonce : {speech} (local-broadcast)")
        else:
            events.append("TTS échoué")

    target = action.get("target_point")
    if target:
        try:
            await navigate_to_point(str(target))
            events.append(f"Navigation vers {target}")
        except Exception as exc:
            return {"ok": False, "error": f"Navigation échouée : {exc}"}

    route = action.get("route_name")
    if route:
        events.append(f"Visite guidée '{route}' — sync GUIDED à brancher")

    if not events:
        events.append(f"Action '{action.get('label', action_id)}' exécutée")

    return {"ok": True, "action": action_id, "events": events}


_tour_engine: TourEngine | None = None


def get_tour_engine() -> TourEngine:
    global _tour_engine
    if _tour_engine is None:
        tour = load_lab_tour(TOUR_PATH if TOUR_PATH.is_file() else None)

        async def speak(text: str) -> None:
            if not speak_local(text):
                raise RuntimeError("TTS échoué")
            await asyncio.sleep(0.3)

        async def navigate(point: str) -> None:
            await navigate_to_point(point)

        async def stop_motion() -> None:
            await stop_robot()

        _tour_engine = TourEngine(tour, speak, navigate, stop_motion)
    return _tour_engine


async def tour_info(_: Request) -> JSONResponse:
    tour = load_lab_tour(TOUR_PATH if TOUR_PATH.is_file() else None)
    return JSONResponse(tour_public_payload(tour))


async def tour_status(_: Request) -> JSONResponse:
    return JSONResponse(get_tour_engine().get_status().to_dict())


async def tour_start(request: Request) -> JSONResponse:
    lang = request.query_params.get("lang", "fr")
    try:
        result = await get_tour_engine().start(lang)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    if not result.get("ok"):
        return JSONResponse(result, status_code=409)
    return JSONResponse(result)


async def tour_stop(_: Request) -> JSONResponse:
    result = await get_tour_engine().stop()
    return JSONResponse(result)


async def health(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "mock": False,
            "robot_host": ROBOT_HOST,
            "version": "0.2.0-lite",
            "mode": "termux-lite",
        }
    )


async def list_actions(_: Request) -> JSONResponse:
    return JSONResponse(load_actions())


async def run_action(request: Request) -> JSONResponse:
    action_id = request.path_params["action_id"]
    lang = request.query_params.get("lang", "fr")
    try:
        result = await execute_action(action_id, lang)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)


async def get_faq(_: Request) -> JSONResponse:
    return JSONResponse(load_faq())


async def say(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "JSON invalide"}, status_code=400)
    text = str(body.get("text", "")).strip()
    if not text:
        return JSONResponse({"ok": False, "error": "Texte vide"}, status_code=400)
    if speak_local(text):
        return JSONResponse({"ok": True, "method": "local-broadcast", "text": text})
    return JSONResponse({"ok": False, "error": "TTS échoué"}, status_code=400)


async def stop_speech(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


def build_app() -> Starlette:
    routes: list = [
        Route("/api/health", health, methods=["GET"]),
        Route("/api/reception/actions", list_actions, methods=["GET"]),
        Route("/api/reception/actions/{action_id}/execute", run_action, methods=["POST"]),
        Route("/api/knowledge/faq", get_faq, methods=["GET"]),
        Route("/api/tour", tour_info, methods=["GET"]),
        Route("/api/tour/status", tour_status, methods=["GET"]),
        Route("/api/tour/start", tour_start, methods=["POST"]),
        Route("/api/tour/stop", tour_stop, methods=["POST"]),
        Route("/api/speech/say", say, methods=["POST"]),
        Route("/api/speech/stop", stop_speech, methods=["POST"]),
    ]
    if KIOSK_DIST.is_dir():
        routes.append(
            Mount("/kiosk", app=StaticFiles(directory=str(KIOSK_DIST), html=True), name="kiosk")
        )
    return Starlette(routes=routes)


app = build_app()


def main() -> None:
    print(f"CYBEL lite — http://0.0.0.0:{BACKEND_PORT} (robot {ROBOT_HOST}:{ROBOT_WS_PORT})")
    uvicorn.run(app, host="0.0.0.0", port=BACKEND_PORT, log_level="info")


if __name__ == "__main__":
    main()
