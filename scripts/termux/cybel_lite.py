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
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

CYBEL_HOME = Path(os.environ.get("CYBEL_HOME", Path.home() / "cybel"))
ACTIONS_PATH = CYBEL_HOME / "scripts" / "termux" / "actions.json"
FAQ_PATH = CYBEL_HOME / "data" / "hestim_knowledge_base.json"
TOUR_PATH = CYBEL_HOME / "data" / "lab_tour.json"
POINTS_PATH = CYBEL_HOME / "data" / "points.json"
KIOSK_CONFIG_PATH = CYBEL_HOME / "data" / "kiosk_config.json"
KIOSK_DIST = CYBEL_HOME / "frontend-kiosk" / "dist"
LAB_TOUR_MODULE = CYBEL_HOME / "sdk" / "lab_tour.py"
SPEECH_TIMING_MODULE = CYBEL_HOME / "sdk" / "speech_timing.py"
TOUR_TRACE_MODULE = CYBEL_HOME / "sdk" / "tour_trace.py"
TOUR_NAVIGATION_MODULE = CYBEL_HOME / "sdk" / "tour_navigation.py"


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


def _load_tour_trace_module():
    return _load_module_from_file("cybel_tour_trace", TOUR_TRACE_MODULE)


def _load_tour_navigation_module():
    return _load_module_from_file("cybel_tour_navigation", TOUR_NAVIGATION_MODULE)


_lab_tour = _load_lab_tour_module()
_speech_timing = _load_speech_timing_module()
_tour_trace = _load_tour_trace_module()
_tour_navigation = _load_tour_navigation_module()
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
LOCALIZATION_MIN_PERCENT = float(
    os.environ.get(
        "LOCALIZATION_MIN_PERCENT",
        str(_tour_navigation.DEFAULT_LOCALIZATION_MIN_PERCENT),
    )
)

TTS_RECEIVER = "com.cybel.ttsbridge/.SpeakReceiver"
TTS_ACTION = "com.cybel.ttsbridge.SPEAK"

NAV_STATUS_LABELS = {
    600: "En initialisation",
    601: "Prêt",
    602: "En navigation",
    603: "Arrivé",
    604: "Erreur",
}

GLOBAL_LOCATE_SERVICE_CHAIN = ("/global_locate", "/global_localization")

_speech_state: dict = {"speaking": False, "last_text": ""}
_telemetry_sockets: set[WebSocket] = set()


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


def _service_succeeded(response: dict) -> bool:
    if not response:
        return False
    if response.get("result") is False:
        return False
    return True


async def ros_call_service_first(
    candidates: list[tuple[str, dict]],
    *,
    timeout: float = 8.0,
) -> tuple[str | None, dict]:
    """Essaie les services ROS dans l'ordre (aligné APK / sdk/ros_ops)."""
    last_response: dict = {}
    for service, args in candidates:
        try:
            response = await ros_call_service(service, args, timeout=timeout)
            last_response = response if isinstance(response, dict) else {}
            if _service_succeeded(last_response):
                return service, last_response
        except Exception:
            continue
    return None, last_response


async def cancel_navigation_full() -> None:
    """Annule navigation, POI et marqueurs (réinitialise un état 604)."""
    for service, args in (
        ("/path_follower/cancel", {}),
        ("/poi", {"command": "stop"}),
        ("/marker_manager/control", {"command": "stop"}),
    ):
        try:
            await ros_call_service(service, args)
        except Exception:
            pass
    try:
        uri = f"ws://{ROBOT_HOST}:{ROBOT_WS_PORT}"
        async with websockets.connect(uri, open_timeout=3) as ws:
            await ws.send(
                json.dumps({"op": "publish", "topic": "/path_follower/cancel", "msg": {}})
            )
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


async def ensure_auto_navigation() -> bool:
    """Annule la nav en cours et passe le châssis en mode automatique."""
    try:
        await cancel_navigation_full()
        await ros_call_service("/change_location_mode", {"mode": 1})
        await asyncio.sleep(0.5)
        return True
    except Exception:
        return False


async def recover_navigation_state(timeout: float = 12.0) -> dict:
    """Annule nav/erreurs et attend un état prêt (601/603)."""
    bad_states = {600, 602, 604}

    async def _cancel_and_mode() -> None:
        await cancel_navigation_full()
        try:
            await ros_call_service("/change_location_mode", {"mode": 1})
        except Exception:
            pass
        await asyncio.sleep(0.5)

    await _cancel_and_mode()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    snap = await fetch_robot_snapshot()
    while loop.time() < deadline and int(snap.get("nav_status") or 0) in bad_states:
        await asyncio.sleep(0.5)
        snap = await fetch_robot_snapshot()
    if int(snap.get("nav_status") or 0) in bad_states:
        await _cancel_and_mode()
        await asyncio.sleep(1.0)
        snap = await fetch_robot_snapshot()
    return snap


async def ensure_global_localization(
    min_percent: float | None = None,
    timeout: float = 45.0,
) -> tuple[bool, dict]:
    """Lance la relocalisation globale (chaîne APK) et attend le seuil de confiance."""
    target = min_percent if min_percent is not None else LOCALIZATION_MIN_PERCENT
    snap = await fetch_robot_snapshot(timeout=5.0)
    loc = snap.get("localization_percent")
    if loc is not None and loc >= target:
        return True, snap
    service, _ = await ros_call_service_first(
        [(name, {}) for name in GLOBAL_LOCATE_SERVICE_CHAIN],
        timeout=8.0,
    )
    if not service:
        return False, snap
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        await asyncio.sleep(1.0)
        snap = await fetch_robot_snapshot(timeout=5.0)
        loc = snap.get("localization_percent")
        if loc is not None and loc >= target:
            return True, snap
    return False, snap


async def prepare_for_tour() -> tuple[bool, str, dict]:
    """Prérequis visite : récupération nav + localisation."""
    snap = await recover_navigation_state()
    nav_status = int(snap.get("nav_status") or 0)
    loc = snap.get("localization_percent")

    if nav_status in (604, 600, 602):
        _, reason = _tour_navigation.assess_tour_readiness(
            nav_status,
            loc,
            min_localization=LOCALIZATION_MIN_PERCENT,
            require_known_localization=True,
        )
        return False, reason, snap

    needs_reloc = loc is None or loc < LOCALIZATION_MIN_PERCENT
    if needs_reloc:
        loc_ok, snap = await ensure_global_localization()
        nav_status = int(snap.get("nav_status") or 0)
        loc = snap.get("localization_percent")
        if not loc_ok:
            if nav_status == 600:
                return False, _tour_navigation.NAV_STATUS_HINTS[600], snap
            if loc is not None:
                reason = (
                    f"Localisation insuffisante ({loc:.0f} % "
                    f"< {LOCALIZATION_MIN_PERCENT:.0f} %). Relocalisez le robot."
                )
            else:
                reason = (
                    "Localisation inconnue après relocalisation — vérifiez rosbridge "
                    "et placez le robot sur une zone connue de la carte."
                )
            return False, reason, snap

    ready, reason = _tour_navigation.assess_tour_readiness(
        nav_status,
        snap.get("localization_percent"),
        min_localization=LOCALIZATION_MIN_PERCENT,
        require_known_localization=True,
    )
    if ready:
        return True, "", snap
    return False, reason, snap


async def prepare_for_nav_goal() -> dict:
    """Avant chaque objectif : annuler erreurs résiduelles."""
    snap = await recover_navigation_state(timeout=5.0)
    nav_status = int(snap.get("nav_status") or 0)
    if nav_status in (604, 600, 602):
        raise RuntimeError(
            _tour_navigation.assess_tour_readiness(
                nav_status,
                snap.get("localization_percent"),
                min_localization=LOCALIZATION_MIN_PERCENT,
            )[1]
        )
    return snap


async def navigate_to_point(point_name: str) -> None:
    await prepare_for_nav_goal()
    if not await ensure_auto_navigation():
        raise RuntimeError("Impossible d'activer le mode navigation automatique")
    await ros_call_service(
        "/poi",
        {"name": point_name, "point_name": point_name, "command": "go"},
    )


async def navigate_to_coordinate(x: float, y: float, theta: float = 0.0) -> None:
    await prepare_for_nav_goal()
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
    _speech_state["speaking"] = True
    _speech_state["last_text"] = text
    try:
        if not speak_local(text):
            raise RuntimeError("TTS échoué")
        await _speech_timing.wait_for_tts_completion(
            text,
            _speech_timing.is_local_tts_service_running,
        )
    finally:
        _speech_state["speaking"] = False


async def _subscribe_topics(ws, topics: list[str]) -> None:
    for topic in topics:
        await ws.send(
            json.dumps(
                {"op": "subscribe", "topic": topic, "throttle_rate": 500}
            )
        )


def _merge_robot_state(
    pose_msg: dict,
    status_msg: dict,
    loc_msg: dict | None = None,
) -> dict:
    localization = _tour_navigation.parse_localization_percent(status_msg, loc_msg)
    state = {
        "x": pose_msg.get("x"),
        "y": pose_msg.get("y"),
        "theta": pose_msg.get("theta"),
        "nav_status": int(
            status_msg.get("nav_status")
            or status_msg.get("nav_internal_status")
            or 0
        ),
        "nav_status_label": "",
        "localization_percent": localization,
        "velocity": status_msg.get("velocity") or [0.0, 0.0],
        "battery": int(status_msg.get("battery") or 0),
        "charger": bool(status_msg.get("charger")),
        "connected": bool(pose_msg or status_msg),
        "nav_mode_label": "Automatique",
        "navigating_to": status_msg.get("navigating_to"),
    }
    state["nav_status_label"] = NAV_STATUS_LABELS.get(state["nav_status"], "?")
    if state["x"] is not None:
        state["x"] = round(float(state["x"]), 3)
    if state["y"] is not None:
        state["y"] = round(float(state["y"]), 3)
    if state["theta"] is not None:
        state["theta"] = round(float(state["theta"]), 3)
    return state


async def fetch_robot_snapshot(timeout: float = 5.0) -> dict:
    """Pose, statut navigation et localisation via rosbridge."""
    uri = f"ws://{ROBOT_HOST}:{ROBOT_WS_PORT}"
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    pose_msg: dict = {}
    status_msg: dict = {}
    loc_msg: dict = {}
    topics = ["/robot_pose", "/robot_status", "/localization_confidence"]
    try:
        async with websockets.connect(uri, open_timeout=5) as ws:
            await _subscribe_topics(ws, topics)
            while loop.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    if pose_msg and status_msg:
                        break
                    continue
                data = json.loads(raw)
                topic = data.get("topic")
                msg = data.get("msg") or {}
                if topic == "/robot_pose":
                    pose_msg = msg
                elif topic == "/robot_status":
                    status_msg = msg
                elif topic == "/localization_confidence":
                    loc_msg = msg
                if pose_msg and status_msg:
                    if loc_msg or loop.time() > deadline - 0.5:
                        break
    except Exception:
        pass
    return _merge_robot_state(pose_msg, status_msg, loc_msg or None)


async def wait_for_navigation_arrival(
    timeout: float = 300.0,
    *,
    tracer=None,
    stop=None,
    stop_index: int = -1,
) -> tuple[bool, str]:
    uri = f"ws://{ROBOT_HOST}:{ROBOT_WS_PORT}"
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    saw_active = False
    activation_deadline = loop.time() + 12.0
    nav_started = loop.time()
    last_log = nav_started
    pose_msg: dict = {}
    status_msg: dict = {}
    loc_msg: dict = {}

    def _failure_message(robot: dict, *, never_started: bool) -> str:
        dest = ""
        distance = None
        if stop is not None:
            dest = getattr(stop, "equipment_fr", "") or str(stop)
            if getattr(stop, "x", None) is not None and robot.get("x") is not None:
                distance = _tour_trace.distance_xy(
                    float(robot["x"]),
                    float(robot["y"]),
                    float(stop.x),
                    float(stop.y),
                )
        return _tour_navigation.navigation_wait_failure_message(
            int(robot.get("nav_status") or 0),
            destination=dest,
            never_started=never_started,
            distance_to_target_m=distance,
        )

    async with websockets.connect(uri, open_timeout=5) as ws:
        await _subscribe_topics(ws, ["/robot_pose", "/robot_status", "/localization_confidence"])
        while loop.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                if not saw_active and loop.time() > activation_deadline:
                    robot = _merge_robot_state(pose_msg, status_msg, loc_msg or None)
                    err = _failure_message(robot, never_started=True)
                    if tracer and stop is not None:
                        tracer.nav_result(
                            stop,
                            index=stop_index,
                            robot=robot,
                            success=False,
                            nav_status=robot.get("nav_status"),
                            nav_status_label=str(robot.get("nav_status_label", "")),
                            error=err,
                        )
                    return False, err
                continue
            data = json.loads(raw)
            topic = data.get("topic")
            msg = data.get("msg") or {}
            if topic == "/robot_pose":
                pose_msg = msg
            elif topic == "/robot_status":
                status_msg = msg
            elif topic == "/localization_confidence":
                loc_msg = msg
            else:
                continue

            robot = _merge_robot_state(pose_msg, status_msg, loc_msg or None)
            now = loop.time()
            if tracer and stop is not None and now - last_log >= 3.0:
                tracer.nav_progress(
                    stop,
                    index=stop_index,
                    robot=robot,
                    nav_status=robot.get("nav_status"),
                    nav_status_label=str(robot.get("nav_status_label", "")),
                    elapsed_s=now - nav_started,
                )
                last_log = now

            nav_status = int(robot.get("nav_status") or 0)
            if nav_status == 602:
                saw_active = True
            if nav_status == 604:
                err = _failure_message(robot, never_started=False)
                if tracer and stop is not None:
                    tracer.nav_result(
                        stop,
                        index=stop_index,
                        robot=robot,
                        success=False,
                        nav_status=nav_status,
                        nav_status_label=str(robot.get("nav_status_label", "")),
                        error=err,
                    )
                return False, err
            if saw_active and nav_status == 603:
                velocity = robot.get("velocity") or [0.0, 0.0]
                if abs(velocity[0]) < 0.05 and abs(velocity[1]) < 0.05:
                    if tracer and stop is not None:
                        tracer.nav_result(
                            stop,
                            index=stop_index,
                            robot=robot,
                            success=True,
                            nav_status=nav_status,
                            nav_status_label=str(robot.get("nav_status_label", "")),
                        )
                    return True, ""
            if not saw_active and loop.time() > activation_deadline:
                err = _failure_message(robot, never_started=True)
                if tracer and stop is not None:
                    tracer.nav_result(
                        stop,
                        index=stop_index,
                        robot=robot,
                        success=False,
                        nav_status=nav_status,
                        nav_status_label=str(robot.get("nav_status_label", "")),
                        error=err,
                    )
                return False, err
    return False, "Délai d'attente navigation dépassé"


async def stop_robot() -> None:
    await cancel_navigation_full()


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
_active_tracer = None


def reset_tour_engine() -> None:
    global _tour_engine
    _tour_engine = None


def _tour_log_dir() -> Path:
    path = CYBEL_HOME / "data" / "logs" / "tour"
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_tour_engine(tracer=None) -> TourEngine:
    tour = load_lab_tour(TOUR_PATH if TOUR_PATH.is_file() else None)

    async def speak(text: str) -> None:
        await speak_local_and_wait(text)

    async def navigate(stop, index: int) -> None:
        snap_before = await fetch_robot_snapshot()
        if tracer:
            tracer.robot_snapshot("nav_before", snap_before, stop=stop)
        if stop.has_coordinates():
            if tracer:
                tracer.nav_command(
                    stop,
                    index=index,
                    robot=snap_before,
                    nav_status=snap_before.get("nav_status"),
                    nav_status_label=str(snap_before.get("nav_status_label", "")),
                    detail=f"publish /navi_goal ({stop.x}, {stop.y}, {stop.theta or 0})",
                )
            await navigate_to_coordinate(stop.x, stop.y, stop.theta or 0.0)
            arrived, err = await wait_for_navigation_arrival(
                tracer=tracer, stop=stop, stop_index=index
            )
            if not arrived:
                raise RuntimeError(err)
        elif stop.target_point:
            if tracer:
                tracer.nav_command(
                    stop,
                    index=index,
                    robot=snap_before,
                    nav_status=snap_before.get("nav_status"),
                    nav_status_label=str(snap_before.get("nav_status_label", "")),
                    detail=f"service /poi go → {stop.target_point}",
                )
            await navigate_to_point(str(stop.target_point))
            arrived, err = await wait_for_navigation_arrival(
                tracer=tracer, stop=stop, stop_index=index
            )
            if not arrived:
                raise RuntimeError(err)
        else:
            raise RuntimeError(f"Arrêt '{stop.id}' sans destination")

    async def stop_motion() -> None:
        await stop_robot()

    return TourEngine(tour, speak, navigate, stop_motion, tracer=tracer)


def get_tour_engine() -> TourEngine:
    global _tour_engine
    if _tour_engine is None:
        _tour_engine = build_tour_engine(tracer=None)
    return _tour_engine


async def tour_info(_: Request) -> JSONResponse:
    tour = load_lab_tour(TOUR_PATH if TOUR_PATH.is_file() else None)
    return JSONResponse(tour_public_payload(tour))


async def tour_status(_: Request) -> JSONResponse:
    return JSONResponse(get_tour_engine().get_status().to_dict())


async def tour_start(request: Request) -> JSONResponse:
    global _tour_engine, _active_tracer
    lang = request.query_params.get("lang", "fr")
    engine = get_tour_engine()
    if engine.is_running():
        return JSONResponse(
            {"ok": False, "error": "Une visite est déjà en cours"},
            status_code=409,
        )
    reset_tour_engine()
    ready, reason, prereq_snap = await prepare_for_tour()
    if not ready:
        return JSONResponse({"ok": False, "error": reason}, status_code=409)
    if not await ensure_auto_navigation():
        return JSONResponse(
            {"ok": False, "error": "Impossible d'activer le mode navigation automatique"},
            status_code=409,
        )
    tour = load_lab_tour(TOUR_PATH if TOUR_PATH.is_file() else None)
    _active_tracer = _tour_trace.TourSessionLogger(
        tour_id=tour.id,
        log_dir=_tour_log_dir(),
    )
    _active_tracer.robot_snapshot("tour_start_pose", prereq_snap)
    _tour_engine = build_tour_engine(tracer=_active_tracer)
    try:
        result = await _tour_engine.start(lang)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    if not result.get("ok"):
        return JSONResponse(result, status_code=409)
    payload = {**result, "trace_session": _active_tracer.session_id}
    if _active_tracer.log_file:
        payload["trace_log"] = str(_active_tracer.log_file)
    return JSONResponse(payload)


async def tour_trace(_: Request) -> JSONResponse:
    if _active_tracer is None:
        return JSONResponse({"session_id": None, "log_file": None, "entries": []})
    return JSONResponse(_active_tracer.status_payload())


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


def load_points() -> list[dict]:
    if not POINTS_PATH.is_file():
        return []
    with open(POINTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("points", []))


def find_point(point_name: str) -> dict | None:
    return next((p for p in load_points() if p.get("name") == point_name), None)


def kiosk_destinations() -> list[dict]:
    return [p for p in load_points() if p.get("kiosk_visible", True)]


def load_kiosk_config() -> dict:
    default = {
        "organization_name_fr": "CYBEL",
        "organization_name_en": "CYBEL",
        "welcome_message_fr": "Bienvenue ! Touchez l'écran pour commencer.",
        "welcome_message_en": "Welcome! Touch the screen to begin.",
        "logo_url": "/kiosk/logo.svg",
        "standby_timeout_seconds": 90,
        "featured_destinations": [],
        "reception_actions": ["welcome_guest", "go_meeting_room", "wait_mode"],
    }
    if not KIOSK_CONFIG_PATH.is_file():
        return default
    try:
        with open(KIOSK_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {**default, **data}
    except (OSError, json.JSONDecodeError):
        return default


async def kiosk_config_get(_: Request) -> JSONResponse:
    return JSONResponse(load_kiosk_config())


async def kiosk_config_put(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "JSON invalide"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "Corps invalide"}, status_code=400)
    allowed = {
        "organization_name_fr",
        "organization_name_en",
        "welcome_message_fr",
        "welcome_message_en",
        "logo_url",
        "standby_timeout_seconds",
        "featured_destinations",
        "reception_actions",
    }
    current = load_kiosk_config()
    for key, value in body.items():
        if key in allowed:
            current[key] = value
    KIOSK_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(KIOSK_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return JSONResponse({"ok": True, "config": current})


def robot_status_payload(snap: dict) -> dict:
    loc = snap.get("localization_percent")
    return {
        "connected": bool(snap.get("connected")),
        "battery": int(snap.get("battery") or 0),
        "charger": bool(snap.get("charger")),
        "soft_estop": False,
        "nav_status": int(snap.get("nav_status") or 600),
        "nav_status_label": str(snap.get("nav_status_label") or "Inconnu"),
        "nav_mode_label": str(snap.get("nav_mode_label") or "Automatique"),
        "localization_percent": float(loc) if loc is not None else 0.0,
        "localization_label": (
            "Bonne"
            if loc is not None and loc >= LOCALIZATION_MIN_PERCENT
            else "Faible"
        ),
        "navigating_to": snap.get("navigating_to"),
    }


async def robot_relocalize(_: Request) -> JSONResponse:
    ok, snap = await ensure_global_localization()
    payload = {"ok": ok, **robot_status_payload(snap)}
    if not ok:
        loc = snap.get("localization_percent")
        if loc is not None:
            payload["error"] = (
                f"Localisation insuffisante ({loc:.0f} % "
                f"< {LOCALIZATION_MIN_PERCENT:.0f} %)"
            )
        else:
            payload["error"] = "Relocalisation échouée ou localisation inconnue"
        return JSONResponse(payload, status_code=409)
    return JSONResponse(payload)


async def list_destinations(_: Request) -> JSONResponse:
    return JSONResponse(kiosk_destinations())


async def go_destination(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "JSON invalide"}, status_code=400)
    point_name = str(body.get("point_name", "")).strip()
    lang = str(body.get("lang", "fr"))
    if not point_name:
        return JSONResponse({"ok": False, "error": "point_name requis"}, status_code=400)
    point = find_point(point_name)
    if not point:
        return JSONResponse(
            {"ok": False, "error": f"Destination « {point_name} » inconnue"},
            status_code=400,
        )
    welcome = (
        f"Welcome! I will take you to {point_name}. Please follow me."
        if lang == "en"
        else f"Bienvenue ! Je vous accompagne vers {point_name}. Suivez-moi."
    )
    events = [f"Accueil : {welcome}"]
    if speak_local(welcome):
        events.append("TTS local OK")
    else:
        events.append("TTS échoué")
    try:
        await navigate_to_point(point_name)
    except Exception:
        try:
            await navigate_to_coordinate(
                float(point["x"]),
                float(point["y"]),
                float(point.get("theta") or 0.0),
            )
        except Exception as exc:
            return JSONResponse(
                {
                    "ok": False,
                    "error": f"Impossible de naviguer vers « {point_name} » : {exc}",
                    "events": events,
                },
                status_code=400,
            )
    events.append(f"Navigation vers {point_name}")
    return JSONResponse({"ok": True, "point": point_name, "events": events})


async def robot_status(_: Request) -> JSONResponse:
    snap = await fetch_robot_snapshot()
    return JSONResponse(robot_status_payload(snap))


async def speech_status(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "speaking": bool(_speech_state.get("speaking")),
            "last_text": str(_speech_state.get("last_text") or ""),
            "mock": False,
        }
    )


async def telemetry_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    _telemetry_sockets.add(websocket)
    try:
        snap = await fetch_robot_snapshot()
        await websocket.send_text(
            json.dumps({"type": "status", **robot_status_payload(snap)})
        )
        await websocket.send_text(
            json.dumps({"type": "speech", **_speech_state, "mock": False})
        )
        await websocket.send_text(
            json.dumps(
                {"type": "tour", **get_tour_engine().get_status().to_dict()}
            )
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _telemetry_sockets.discard(websocket)


async def _telemetry_broadcast_loop() -> None:
    while True:
        if _telemetry_sockets:
            try:
                snap = await fetch_robot_snapshot(timeout=4.0)
                status_msg = json.dumps(
                    {"type": "status", **robot_status_payload(snap)}
                )
                speech_msg = json.dumps(
                    {"type": "speech", **_speech_state, "mock": False}
                )
                tour_msg = json.dumps(
                    {"type": "tour", **get_tour_engine().get_status().to_dict()}
                )
                dead: list[WebSocket] = []
                for ws in list(_telemetry_sockets):
                    try:
                        await ws.send_text(status_msg)
                        await ws.send_text(speech_msg)
                        await ws.send_text(tour_msg)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    _telemetry_sockets.discard(ws)
            except Exception:
                pass
        await asyncio.sleep(1.5)


def build_app() -> Starlette:
    routes: list = [
        Route("/api/health", health, methods=["GET"]),
        Route("/api/kiosk/config", kiosk_config_get, methods=["GET"]),
        Route("/api/kiosk/config", kiosk_config_put, methods=["PUT"]),
        Route("/api/reception/destinations", list_destinations, methods=["GET"]),
        Route("/api/reception/go", go_destination, methods=["POST"]),
        Route("/api/reception/actions", list_actions, methods=["GET"]),
        Route("/api/reception/actions/{action_id}/execute", run_action, methods=["POST"]),
        Route("/api/robot/status", robot_status, methods=["GET"]),
        Route("/api/robot/relocalize", robot_relocalize, methods=["POST"]),
        Route("/api/speech/status", speech_status, methods=["GET"]),
        Route("/api/knowledge/faq", get_faq, methods=["GET"]),
        Route("/api/tour", tour_info, methods=["GET"]),
        Route("/api/tour/full", tour_full, methods=["GET"]),
        Route("/api/tour/reload", tour_reload, methods=["POST"]),
        Route("/api/tour/full", tour_save_full, methods=["PUT"]),
        Route("/api/tour/status", tour_status, methods=["GET"]),
        Route("/api/tour/trace", tour_trace, methods=["GET"]),
        Route("/api/tour/start", tour_start, methods=["POST"]),
        Route("/api/tour/stop", tour_stop, methods=["POST"]),
        Route("/api/tour/halt", tour_halt, methods=["POST"]),
        Route("/api/tour/stops", tour_add_stop, methods=["POST"]),
        Route("/api/tour/stops/{stop_id}", tour_update_stop, methods=["PUT"]),
        Route("/api/tour/stops/{stop_id}", tour_delete_stop, methods=["DELETE"]),
        Route("/api/speech/say", say, methods=["POST"]),
        Route("/api/speech/stop", stop_speech, methods=["POST"]),
        WebSocketRoute("/ws/telemetry", telemetry_ws),
    ]
    if KIOSK_DIST.is_dir():
        routes.append(
            Mount("/kiosk", app=StaticFiles(directory=str(KIOSK_DIST), html=True), name="kiosk")
        )
    app = Starlette(routes=routes)

    @app.on_event("startup")
    async def _start_telemetry() -> None:
        asyncio.create_task(_telemetry_broadcast_loop())

    return app


app = build_app()


def main() -> None:
    print(f"CYBEL lite — http://0.0.0.0:{BACKEND_PORT} (robot {ROBOT_HOST}:{ROBOT_WS_PORT})")
    uvicorn.run(app, host="0.0.0.0", port=BACKEND_PORT, log_level="info")


if __name__ == "__main__":
    main()
