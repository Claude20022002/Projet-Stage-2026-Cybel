#!/usr/bin/env python3
"""Backend CYBEL léger pour Termux — sans FastAPI/pydantic (pas de compilation Rust)."""
from __future__ import annotations

import asyncio
import json
import math
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
LAB_TOUR_MODULE = CYBEL_HOME / "sdk" / "lab_tour.py"
SPEECH_TIMING_MODULE = CYBEL_HOME / "sdk" / "speech_timing.py"


def _load_module_from_file(module_name: str, path: Path):
    """Charge un module sdk sans importer sdk/__init__.py (évite pydantic sur Termux)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Module introuvable: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_lab_tour_module():
    return _load_module_from_file("cybel_lab_tour", LAB_TOUR_MODULE)


def _load_speech_timing_module():
    return _load_module_from_file("cybel_speech_timing", SPEECH_TIMING_MODULE)


_lab_tour = _load_lab_tour_module()
_speech_timing = _load_speech_timing_module()
TourEngine = _lab_tour.TourEngine
load_lab_tour = _lab_tour.load_lab_tour
load_tour_data = _lab_tour.load_tour_data
save_tour_data = _lab_tour.save_tour_data
validate_stop_dict = _lab_tour.validate_stop_dict
slugify = _lab_tour.slugify
tour_public_payload = _lab_tour.tour_public_payload

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


async def ensure_auto_navigation() -> bool:
    """Annule la nav en cours et passe le châssis en mode automatique."""
    try:
        await stop_robot()
        await ros_call_service("/change_location_mode", {"mode": 1})
        await asyncio.sleep(0.5)
        return True
    except Exception:
        return False


async def navigate_to_point(point_name: str) -> None:
    if not await ensure_auto_navigation():
        raise RuntimeError("Impossible d'activer le mode navigation automatique")
    await ros_call_service(
        "/poi",
        {"name": point_name, "point_name": point_name, "command": "go"},
    )


async def navigate_to_coordinate(x: float, y: float, theta: float = 0.0) -> None:
    if not await ensure_auto_navigation():
        raise RuntimeError("Impossible d'activer le mode navigation automatique")
    uri = f"ws://{ROBOT_HOST}:{ROBOT_WS_PORT}"
    async with websockets.connect(uri, open_timeout=5) as ws:
        await ws.send(
            json.dumps(
                {
                    "op": "publish",
                    "topic": "/navi_goal",
                    "msg": {
                        "header": {"frame_id": "map"},
                        "pose": {
                            "position": {"x": x, "y": y, "z": 0.0},
                            "orientation": {
                                "x": 0.0,
                                "y": 0.0,
                                "z": math.sin(theta / 2),
                                "w": math.cos(theta / 2),
                            },
                        },
                    },
                }
            )
        )


def estimate_speech_seconds(text: str) -> float:
    return _speech_timing.estimate_speech_seconds(text)


async def speak_local_and_wait(text: str) -> None:
    """Envoie le TTS local et attend la fin réelle du service Android."""
    if not speak_local(text):
        raise RuntimeError("TTS échoué")
    await _speech_timing.wait_for_tts_completion(
        text,
        _speech_timing.is_local_tts_service_running,
    )


async def wait_for_navigation_arrival(timeout: float = 300.0) -> bool:
    uri = f"ws://{ROBOT_HOST}:{ROBOT_WS_PORT}"
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    saw_active = False
    activation_deadline = loop.time() + 12.0

    async with websockets.connect(uri, open_timeout=5) as ws:
        await ws.send(
            json.dumps(
                {
                    "op": "subscribe",
                    "topic": "/robot_status",
                    "throttle_rate": 500,
                }
            )
        )
        while loop.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                if not saw_active and loop.time() > activation_deadline:
                    return False
                continue
            data = json.loads(raw)
            if data.get("topic") != "/robot_status":
                continue
            msg = data.get("msg") or {}
            nav_status = int(msg.get("nav_status") or msg.get("nav_internal_status") or 0)
            if nav_status == 602:
                saw_active = True
            if nav_status == 604:
                return False
            if saw_active and nav_status == 603:
                velocity = msg.get("velocity") or [0.0, 0.0]
                if abs(velocity[0]) < 0.05 and abs(velocity[1]) < 0.05:
                    return True
            if not saw_active and loop.time() > activation_deadline:
                return False
    return False


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


def reset_tour_engine() -> None:
    global _tour_engine
    _tour_engine = None


def get_tour_engine() -> TourEngine:
    global _tour_engine
    if _tour_engine is None:
        tour = load_lab_tour(TOUR_PATH if TOUR_PATH.is_file() else None)

        async def speak(text: str) -> None:
            await speak_local_and_wait(text)

        async def navigate(stop) -> None:
            if stop.has_coordinates():
                await navigate_to_coordinate(stop.x, stop.y, stop.theta or 0.0)
                if not await wait_for_navigation_arrival():
                    raise RuntimeError(
                        f"Échec de navigation (604) vers {stop.equipment_fr} — "
                        "obstacle ou destination inaccessible"
                    )
            elif stop.target_point:
                await navigate_to_point(str(stop.target_point))
                if not await wait_for_navigation_arrival():
                    raise RuntimeError(
                        f"Échec de navigation (604) vers le point « {stop.target_point} » — "
                        "obstacle ou destination inaccessible"
                    )
            else:
                raise RuntimeError(f"Arrêt '{stop.id}' sans destination")

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
    engine = get_tour_engine()
    if engine.is_running():
        return JSONResponse(
            {"ok": False, "error": "Une visite est déjà en cours"},
            status_code=409,
        )
    # Recharge lab_tour.json à chaque démarrage (édition manuelle du fichier).
    reset_tour_engine()
    if not await ensure_auto_navigation():
        return JSONResponse(
            {"ok": False, "error": "Impossible d'activer le mode navigation automatique"},
            status_code=409,
        )
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


async def tour_halt(_: Request) -> JSONResponse:
    await get_tour_engine().stop()
    await stop_robot()
    return JSONResponse({"ok": True, "message": "Arrêt total effectué"})


async def tour_reload(_: Request) -> JSONResponse:
    reset_tour_engine()
    data = load_tour_data(TOUR_PATH)
    return JSONResponse({"ok": True, "stops": len(data.get("stops", [])), "tour": data})


async def tour_full(_: Request) -> JSONResponse:
    return JSONResponse(load_tour_data(TOUR_PATH))


async def tour_save_full(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "JSON invalide"}, status_code=400)
    try:
        stops = [validate_stop_dict(s) for s in body.get("stops", [])]
        payload = {**body, "stops": stops}
        save_tour_data(payload, TOUR_PATH)
        reset_tour_engine()
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "tour": payload})


async def tour_add_stop(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        data = load_tour_data(TOUR_PATH)
        validated = validate_stop_dict(body)
        if any(s.get("id") == validated["id"] for s in data.get("stops", [])):
            return JSONResponse(
                {"ok": False, "error": f"id '{validated['id']}' déjà utilisé"},
                status_code=400,
            )
        data.setdefault("stops", []).append(validated)
        save_tour_data(data, TOUR_PATH)
        reset_tour_engine()
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "tour": data})


async def tour_update_stop(request: Request) -> JSONResponse:
    stop_id = request.path_params["stop_id"]
    try:
        body = await request.json()
        data = load_tour_data(TOUR_PATH)
        stops = data.get("stops", [])
        index = next((i for i, s in enumerate(stops) if s.get("id") == stop_id), None)
        if index is None:
            return JSONResponse({"ok": False, "error": "Arrêt introuvable"}, status_code=404)
        stops[index] = validate_stop_dict({**stops[index], **body, "id": stop_id})
        data["stops"] = stops
        save_tour_data(data, TOUR_PATH)
        reset_tour_engine()
    except (json.JSONDecodeError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "tour": data})


async def tour_delete_stop(request: Request) -> JSONResponse:
    stop_id = request.path_params["stop_id"]
    data = load_tour_data(TOUR_PATH)
    stops = data.get("stops", [])
    filtered = [s for s in stops if s.get("id") != stop_id]
    if len(filtered) == len(stops):
        return JSONResponse({"ok": False, "error": "Arrêt introuvable"}, status_code=404)
    data["stops"] = filtered
    save_tour_data(data, TOUR_PATH)
    reset_tour_engine()
    return JSONResponse({"ok": True, "tour": data})


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
        Route("/api/tour/full", tour_full, methods=["GET"]),
        Route("/api/tour/reload", tour_reload, methods=["POST"]),
        Route("/api/tour/full", tour_save_full, methods=["PUT"]),
        Route("/api/tour/status", tour_status, methods=["GET"]),
        Route("/api/tour/start", tour_start, methods=["POST"]),
        Route("/api/tour/stop", tour_stop, methods=["POST"]),
        Route("/api/tour/halt", tour_halt, methods=["POST"]),
        Route("/api/tour/stops", tour_add_stop, methods=["POST"]),
        Route("/api/tour/stops/{stop_id}", tour_update_stop, methods=["PUT"]),
        Route("/api/tour/stops/{stop_id}", tour_delete_stop, methods=["DELETE"]),
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
