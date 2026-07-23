#!/usr/bin/env python3
"""Backend CYBEL léger pour Termux — sans FastAPI/pydantic (pas de compilation Rust)."""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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
VISITORS_PATH = CYBEL_HOME / "data" / "visitors.json"
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


def _ensure_sdk_package_stub() -> None:
    """Enregistre le package sdk sans exécuter sdk/__init__.py (pydantic absent sur Termux)."""
    import types

    existing = sys.modules.get("sdk")
    if existing is not None and getattr(existing, "__file__", None):
        return
    if existing is not None and hasattr(existing, "__path__"):
        return
    pkg = types.ModuleType("sdk")
    pkg.__path__ = [str(CYBEL_HOME / "sdk")]
    pkg.__package__ = "sdk"
    sys.modules["sdk"] = pkg


def _load_sdk_module_from_file(module_suffix: str):
    """Charge sdk/<suffix>.py en préservant les imports relatifs sdk.*."""
    import importlib.util

    full_name = f"sdk.{module_suffix}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    _ensure_sdk_package_stub()
    path = CYBEL_HOME / "sdk" / f"{module_suffix}.py"
    spec = importlib.util.spec_from_file_location(
        full_name,
        path,
        submodule_search_locations=[str(CYBEL_HOME / "sdk")],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Module sdk introuvable: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
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
filter_tour_by_poi = _lab_tour.filter_tour_by_poi
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

FACE_ENROLL_RECEIVER = "com.cybel.facebridge/.EnrollReceiver"
FACE_ENROLL_ACTION = "com.cybel.facebridge.ENROLL"

NAV_STATUS_LABELS = {
    600: "En initialisation",
    601: "Prêt",
    602: "En navigation",
    603: "Arrivé",
    604: "Erreur",
    605: "En recharge",
}

CHARGE_HOME_TOPIC = "/charge_server/home_pose"
START_RECHARGE_SERVICE = "/start_recharge"

GLOBAL_LOCATE_SERVICE_CHAIN = ("/global_locate", "/global_localization")
# yutong_assistance/GlobalLocate.cmd (via /rosapi/service_request_details) —
# /global_locate n'est PAS un service vide : sans "cmd" explicite le châssis ne
# répond jamais (observé : timeout, aucune rotation réelle malgré le faux
# "succès" du repli /global_localization, lui authentiquement std_srvs/Empty).
GLOBAL_LOCATE_ARGS = {
    "/global_locate": {
        "cmd": 0,  # GLOBAL
        "search_step_linear": 0.0,
        "search_step_angular": 0.0,
        "search_boundary": {},
    },
}

TELEOP_TOPIC = "/cmd_vel_mux/input/teleop"
TWIST_TYPE = "geometry_msgs/Twist"
POI_NAV_SERVICE_CHAIN = ("/tag_manager/navi", "/poi")
MARKER_SERVICE_CHAIN = (
    "/marker_manager/get_markers_details",
    "/marker_operation/get_markers",
)
MARKER_UTILS_MODULE = CYBEL_HOME / "sdk" / "marker_utils.py"
CANCEL_NAV_PUBLISH_TOPICS = ("/move_base/cancel", "/path_follower/cancel")
CANCEL_NAV_SERVICE_CHAIN = ("/move_base/cancel", "/path_follower/cancel")

_speech_state: dict = {"speaking": False, "last_text": ""}
_telemetry_sockets: set[WebSocket] = set()
PEOPLE_TOPIC = "/detected_people_array"
_detected_people: list[dict] = []
_people_utils_module = None
_visitor_utils_module = None
_voice_commands_module = None
_knowledge_engine = None
_voice_logger = None
_current_identified_visitor: dict | None = None
_current_identified_at: float = 0.0
VISITOR_IDENTITY_TTL_SECONDS = 120.0
DEFAULT_FACE_RECOGNITION_THRESHOLD = 0.82


def _get_people_utils():
    global _people_utils_module
    if _people_utils_module is None:
        _people_utils_module = _load_sdk_module_from_file("people_utils")
    return _people_utils_module


def _get_visitor_utils():
    global _visitor_utils_module
    if _visitor_utils_module is None:
        _visitor_utils_module = _load_sdk_module_from_file("visitor_utils")
    return _visitor_utils_module


def _get_voice_commands():
    global _voice_commands_module
    if _voice_commands_module is None:
        _voice_commands_module = _load_sdk_module_from_file("voice_commands")
    return _voice_commands_module


def _get_knowledge_engine():
    """KnowledgeEngine (FAQ HESTIM + lab) — modules sdk purs, chargés via le shim.

    knowledge_engine ne dépend que de json_store et voice_commands (tous deux sans
    pydantic depuis le refactor), donc importable tel quel sur Termux.
    """
    global _knowledge_engine
    if _knowledge_engine is None:
        # voice_commands doit être chargé d'abord (import interne de knowledge_engine).
        _get_voice_commands()
        module = _load_sdk_module_from_file("knowledge_engine")
        _knowledge_engine = module.KnowledgeEngine(CYBEL_HOME / "data")
    return _knowledge_engine


def _get_voice_logger():
    """Journal JSONL des échanges vocaux (latence, déclenchements mot d'éveil)
    — alimente scripts/measure_voice_latency.py (métriques papier ICRA 2027)."""
    global _voice_logger
    if _voice_logger is None:
        module = _load_sdk_module_from_file("voice_trace")
        _voice_logger = module.VoiceSessionLogger(log_dir=CYBEL_HOME / "data" / "logs" / "voice")
    return _voice_logger


def get_detected_people() -> list[dict]:
    return list(_detected_people)


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


_ALLCAPS_RUN = re.compile(r"\b[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ]{2,}\b")


def _tts_friendly(text: str) -> str:
    """Convertit les suites de 2+ majuscules (noms de POI 'PORTE-LABO', sigles
    comme 'HESTIM') en casse normale avant envoi au TTS.

    De nombreux moteurs TextToSpeech (dont celui utilisé ici) épellent lettre
    par lettre tout mot tout-en-majuscules qui n'est pas reconnu comme un mot
    du dictionnaire — constaté sur le robot réel : « HESTIM » lu « H-E-S-T-I-M »
    au lieu du mot. Les noms de POI (convention Deployment Tool : tout majuscule,
    voir sdk/poi_names.py) sont exactement dans ce cas et seraient tout autant
    affectés. On ne touche que le texte envoyé au TTS, jamais l'affichage écran.
    """

    def _title(match: "re.Match[str]") -> str:
        word = match.group(0)
        return word[0] + word[1:].lower()

    return _ALLCAPS_RUN.sub(_title, text)


def speak_local(text: str, lang: str = "fr") -> bool:
    text = _tts_friendly(text)
    escaped = text.replace("'", "'\\''")
    broadcast = (
        f"am broadcast -n {TTS_RECEIVER} -a {TTS_ACTION} "
        f"--es text '{escaped}' --es lang '{lang}'"
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


def trigger_face_enrollment(name: str, civility: str) -> bool:
    """Ouvre la fenêtre d'enrôlement CybelFaceBridge (15s) — équivalent
    programmatique de scripts/termux/enroll_visitor.sh. Permet un déclenchement
    distant (interface opérateur PC, via le backend PC qui relaie ici) plutôt
    qu'un accès direct ADB/Termux à la tablette."""
    escaped_name = name.replace("'", "'\\''")
    escaped_civility = civility.replace("'", "'\\''")
    broadcast = (
        f"am broadcast -n {FACE_ENROLL_RECEIVER} -a {FACE_ENROLL_ACTION} "
        f"--es name '{escaped_name}' --es civility '{escaped_civility}'"
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


# /velocity_control (constructeur, non documenté officiellement) — reverse-engineering
# terrain, voir docs/movement-audit/ROS_COMMUNICATION.md §4 : plages de cmd groupées
# par palier (0-2 sécurité, 3-5 équilibre, 6-8 efficacité). On utilise la première
# valeur de chaque plage comme commande canonique de réglage — confirmé en direct
# le 2026-07-17 : cmd 99 (GET) sur le robot au réglage par défaut usine ("équilibre")
# renvoie bien info="3", cohérent avec cette hypothèse.
VELOCITY_PROFILE_CMD = {"safety": 0, "balance": 3, "efficiency": 6}
VELOCITY_PROFILE_MPS = {"safety": 0.3, "balance": 0.5, "efficiency": 0.8}


def _velocity_level_from_cmd(cmd: int) -> str | None:
    if 0 <= cmd <= 2:
        return "safety"
    if 3 <= cmd <= 5:
        return "balance"
    if 6 <= cmd <= 8:
        return "efficiency"
    return None


async def get_velocity_profile() -> dict:
    """Lit le profil de vitesse actuel du châssis (cmd 99 = GET, sans effet)."""
    try:
        response = await ros_call_service("/velocity_control", {"cmd": 99})
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    raw = response.get("info") if isinstance(response, dict) else None
    try:
        raw_cmd = int(raw)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Réponse /velocity_control inattendue", "raw": response}
    level = _velocity_level_from_cmd(raw_cmd)
    return {
        "ok": True,
        "level": level,
        "raw_cmd": raw_cmd,
        "max_speed_mps": VELOCITY_PROFILE_MPS.get(level) if level else None,
    }


async def set_velocity_profile(level: str) -> dict:
    """Change le profil de vitesse max du châssis (service constructeur /velocity_control)."""
    cmd = VELOCITY_PROFILE_CMD.get(level)
    if cmd is None:
        return {"ok": False, "error": f"Niveau de vitesse inconnu : {level}"}
    try:
        response = await ros_call_service("/velocity_control", {"cmd": cmd})
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if not _service_succeeded(response):
        return {"ok": False, "error": "Service /velocity_control refusé", "raw": response}
    return {"ok": True, "level": level, "max_speed_mps": VELOCITY_PROFILE_MPS[level]}


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


def _poi_nav_chain(point_name: str) -> list[tuple[str, dict]]:
    tag_args = {"name": point_name, "tag_name": point_name}
    poi_args = {
        "name": point_name,
        "point_name": point_name,
        "command": "go",
    }
    return [
        (POI_NAV_SERVICE_CHAIN[0], tag_args),
        (POI_NAV_SERVICE_CHAIN[1], poi_args),
    ]


async def _ws_publish_teleop(
    ws,
    linear_x: float,
    angular_z: float,
    *,
    advertised: list[bool],
) -> None:
    if not advertised[0]:
        await ws.send(
            json.dumps(
                {
                    "op": "advertise",
                    "topic": TELEOP_TOPIC,
                    "type": TWIST_TYPE,
                }
            )
        )
        advertised[0] = True
    await ws.send(
        json.dumps(
            {
                "op": "publish",
                "topic": TELEOP_TOPIC,
                "msg": {
                    "linear": {"x": linear_x, "y": 0.0, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": angular_z},
                },
            }
        )
    )


async def cancel_navigation_full(*, point_name: str | None = None) -> None:
    """Annule navigation, POI et marqueurs (réinitialise un état 604/602 fantôme)."""
    poi_stops: list[dict] = [{"command": "stop"}]
    if point_name:
        poi_stops.insert(
            0,
            {"name": point_name, "point_name": point_name, "command": "stop"},
        )
    for service, args in (
        *[(service, {}) for service in CANCEL_NAV_SERVICE_CHAIN],
        *[(("/poi", args)) for args in poi_stops],
        ("/marker_manager/control", {"command": "stop"}),
    ):
        try:
            await ros_call_service(service, args)
        except Exception:
            pass
    try:
        uri = f"ws://{ROBOT_HOST}:{ROBOT_WS_PORT}"
        advertised = [False]
        async with websockets.connect(uri, open_timeout=3) as ws:
            for topic in CANCEL_NAV_PUBLISH_TOPICS:
                await ws.send(
                    json.dumps({"op": "publish", "topic": topic, "msg": {}})
                )
            await _ws_publish_teleop(ws, 0.0, 0.0, advertised=advertised)
    except Exception:
        pass


def _ghost_nav(snap: dict) -> bool:
    return _tour_navigation.is_ghost_navigation(
        int(snap.get("nav_status") or 0),
        velocity=snap.get("velocity"),
        navigating_to=snap.get("navigating_to"),
    )


async def ensure_auto_navigation() -> bool:
    """Annule la nav en cours, passe en mode auto et attend nav_status prêt (601/603)."""
    snap = await fetch_robot_snapshot(timeout=4.0)
    nav_status_now = int(snap.get("nav_status") or 0)
    # Court-circuit : robot déjà prêt et déjà en mode auto — annuler une nav
    # inexistante et re-demander le mode auto ne fait qu'ajouter deux
    # aller-retours ROS (et leur latence réseau) à chaque déplacement pour
    # rien. Sans danger : nav_mode reflète control_state (téléop/joystick),
    # pas seulement le champ brut nav_mode qui peut être en retard.
    if nav_status_now in (601, 603) and snap.get("nav_mode") == "auto_navi":
        return True
    try:
        await cancel_navigation_full(
            point_name=str(snap.get("navigating_to") or "") or None
        )
        await ros_call_service("/change_location_mode", {"mode": 1})
    except Exception:
        return False
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 8.0
    while loop.time() < deadline:
        snap = await fetch_robot_snapshot(timeout=4.0)
        nav_status = int(snap.get("nav_status") or 0)
        if nav_status in (601, 603):
            return True
        if nav_status in (600, 604):
            await asyncio.sleep(0.5)
            continue
        if nav_status == 602 and _ghost_nav(snap):
            await asyncio.sleep(0.4)
            continue
        await asyncio.sleep(0.4)
    snap = await fetch_robot_snapshot(timeout=4.0)
    nav_status = int(snap.get("nav_status") or 0)
    if nav_status in (601, 603):
        return True
    # 605 sans charge physique : objectif nav en attente, on peut relancer (CYB-061).
    return (
        (nav_status == 602 and _ghost_nav(snap))
        or (
            nav_status == _tour_navigation.CHARGING_NAV_STATUS
            and not _tour_navigation.parse_charger_flag(snap.get("charger"))
        )
    )


async def recover_navigation_state(timeout: float = 12.0) -> dict:
    """Annule nav/erreurs et attend un état prêt (601/603)."""
    bad_states = {600, 602, 604, _tour_navigation.CHARGING_NAV_STATUS}

    async def _cancel_and_mode(snap: dict) -> None:
        await cancel_navigation_full(
            point_name=str(snap.get("navigating_to") or "") or None
        )
        try:
            await ros_call_service("/change_location_mode", {"mode": 1})
        except Exception:
            pass
        await asyncio.sleep(0.5)

    snap = await fetch_robot_snapshot()
    nav_status = int(snap.get("nav_status") or 0)
    # Court-circuit : déjà prêt et déjà en mode auto, rien à récupérer —
    # l'appel précédent annulait/changeait de mode sans condition, ajoutant
    # annulation + changement de mode + 0,5 s à *chaque* déplacement, y
    # compris quand le robot n'en avait pas besoin (voir ensure_auto_navigation,
    # appelée juste après dans le même flux de navigation — même tax payée
    # deux fois de suite).
    if nav_status in (601, 603) and snap.get("nav_mode") == "auto_navi":
        return snap
    if (
        nav_status == _tour_navigation.CHARGING_NAV_STATUS
        and not _tour_navigation.parse_charger_flag(snap.get("charger"))
    ):
        try:
            await ros_call_service(START_RECHARGE_SERVICE, {"command": "stop"})
        except Exception:
            pass
    await _cancel_and_mode(snap)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline and int(snap.get("nav_status") or 0) in bad_states:
        await asyncio.sleep(0.5)
        snap = await fetch_robot_snapshot()
    if int(snap.get("nav_status") or 0) in bad_states:
        for _ in range(2):
            await _cancel_and_mode(snap)
            await asyncio.sleep(1.0)
            snap = await fetch_robot_snapshot()
            if int(snap.get("nav_status") or 0) not in bad_states:
                break
            if int(snap.get("nav_status") or 0) == 602 and _ghost_nav(snap):
                break
    return snap


def _readiness_kwargs(snap: dict, *, ghost_nav_recovered: bool = False) -> dict:
    charger = _tour_navigation.parse_charger_flag(snap.get("charger"))
    nav_status = int(snap.get("nav_status") or 0)
    return {
        "velocity": snap.get("velocity"),
        "navigating_to": snap.get("navigating_to"),
        "ghost_nav_recovered": ghost_nav_recovered,
        "charger": charger,
        "hard_estop": bool(snap.get("hard_estop")),
        "soft_estop": bool(snap.get("soft_estop")),
    }


async def _publish_charge_leave() -> None:
    """Tente de quitter la borne (aligné SelfChassis / charge_server)."""
    try:
        uri = f"ws://{ROBOT_HOST}:{ROBOT_WS_PORT}"
        async with websockets.connect(uri, open_timeout=4) as ws:
            await ws.send(
                json.dumps(
                    {
                        "op": "publish",
                        "topic": CHARGE_HOME_TOPIC,
                        "msg": {"data": False},
                    }
                )
            )
    except Exception:
        pass


async def ensure_leave_charge_if_needed(timeout: float = 15.0) -> dict:
    """Sortie de borne uniquement si le robot signale charger=1."""
    snap = await fetch_robot_snapshot(timeout=6.0)
    if not _tour_navigation.parse_charger_flag(snap.get("charger")):
        return snap

    await cancel_navigation_full(
        point_name=str(snap.get("navigating_to") or "") or None
    )
    await _publish_charge_leave()
    for service, args in (
        ("/marker_manager/control", {"command": "stop"}),
        ("/poi", {"command": "stop"}),
    ):
        try:
            await ros_call_service(service, args)
        except Exception:
            pass
    try:
        await ros_call_service(START_RECHARGE_SERVICE, {"command": "stop"})
    except Exception:
        pass
    try:
        await ros_call_service("/change_location_mode", {"mode": 1})
    except Exception:
        pass

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        await asyncio.sleep(0.6)
        snap = await fetch_robot_snapshot(timeout=6.0)
        nav_status = int(snap.get("nav_status") or 0)
        if nav_status in (601, 603) and not _tour_navigation.parse_charger_flag(
            snap.get("charger")
        ):
            return snap
        if nav_status not in (_tour_navigation.CHARGING_NAV_STATUS,) and not _tour_navigation.parse_charger_flag(
            snap.get("charger")
        ):
            return snap
    return snap


async def ensure_global_localization(
    min_percent: float | None = None,
    timeout: float = 45.0,
) -> tuple[bool, dict]:
    """Lance la relocalisation globale (chaîne APK) et attend le seuil de confiance."""
    target = min_percent if min_percent is not None else LOCALIZATION_MIN_PERCENT
    snap = await fetch_robot_snapshot(timeout=5.0)
    loc = snap.get("localization_percent")
    nav_status_now = int(snap.get("nav_status") or 0)
    # Court-circuit seulement si la loc est bonne ET le nav est déjà prêt (≠600).
    # Si nav_status=600, il faut appeler /global_locate même avec une bonne loc,
    # car c'est le service qui fait passer le châssis de 600→601.
    if loc is not None and loc >= target and nav_status_now != 600:
        return True, snap
    service, _ = await ros_call_service_first(
        [(name, GLOBAL_LOCATE_ARGS.get(name, {})) for name in GLOBAL_LOCATE_SERVICE_CHAIN],
        timeout=8.0,
    )
    if not service:
        return False, snap
    # Délai minimum pour laisser le châssis traiter /global_locate et mettre à jour nav_status
    await asyncio.sleep(3.0)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        await asyncio.sleep(1.0)
        snap = await fetch_robot_snapshot(timeout=5.0)
        loc = snap.get("localization_percent")
        nav = int(snap.get("nav_status") or 0)
        if loc is not None and loc >= target and nav != 600:
            return True, snap
    return False, snap


async def prepare_for_tour() -> tuple[bool, str, dict]:
    """Prérequis visite : récupération nav + localisation."""
    snap = await ensure_leave_charge_if_needed()
    snap = await recover_navigation_state()
    nav_status = int(snap.get("nav_status") or 0)
    loc = snap.get("localization_percent")
    ghost_recovered = nav_status == 602 and _ghost_nav(snap)

    if nav_status in (604,):
        _, reason = _tour_navigation.assess_tour_readiness(
            nav_status,
            loc,
            min_localization=LOCALIZATION_MIN_PERCENT,
            require_known_localization=True,
            **_readiness_kwargs(snap),
        )
        return False, reason, snap
    if nav_status == 600:
        loc_ok, snap = await ensure_global_localization()
        nav_status = int(snap.get("nav_status") or 0)
        loc = snap.get("localization_percent")
        if nav_status == 600 and loc is not None and loc >= LOCALIZATION_MIN_PERCENT:
            snap = await recover_navigation_state(timeout=15.0)
            nav_status = int(snap.get("nav_status") or 0)
            loc = snap.get("localization_percent")
        if nav_status == 600:
            _, reason = _tour_navigation.assess_tour_readiness(
                nav_status,
                loc,
                min_localization=LOCALIZATION_MIN_PERCENT,
                require_known_localization=True,
                **_readiness_kwargs(snap),
            )
            return False, reason, snap
    if (
        nav_status == _tour_navigation.CHARGING_NAV_STATUS
        and _tour_navigation.parse_charger_flag(snap.get("charger"))
    ):
        return False, _tour_navigation.charging_navigation_message(charger=True), snap
    if nav_status == 602 and not ghost_recovered:
        _, reason = _tour_navigation.assess_tour_readiness(
            nav_status,
            loc,
            min_localization=LOCALIZATION_MIN_PERCENT,
            require_known_localization=True,
            **_readiness_kwargs(snap),
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

    nav_status = int(snap.get("nav_status") or 0)
    ghost_recovered = nav_status == 602 and _ghost_nav(snap)
    stuck_605 = (
        nav_status == _tour_navigation.CHARGING_NAV_STATUS
        and not _tour_navigation.parse_charger_flag(snap.get("charger"))
    )
    ready, reason = _tour_navigation.assess_tour_readiness(
        nav_status,
        snap.get("localization_percent"),
        min_localization=LOCALIZATION_MIN_PERCENT,
        require_known_localization=True,
        **_readiness_kwargs(
            snap,
            ghost_nav_recovered=ghost_recovered or stuck_605,
        ),
    )
    if ready:
        return True, "", snap
    return False, reason, snap


async def prepare_for_nav_goal() -> dict:
    """Avant chaque objectif : récupération nav + relocalisation si besoin."""
    snap = await ensure_leave_charge_if_needed()
    snap = await recover_navigation_state(timeout=8.0)
    nav_status = int(snap.get("nav_status") or 0)
    loc = snap.get("localization_percent")
    ghost_recovered = nav_status == 602 and _ghost_nav(snap)

    if nav_status == _tour_navigation.CHARGING_NAV_STATUS and _tour_navigation.parse_charger_flag(
        snap.get("charger")
    ):
        raise RuntimeError(
            _tour_navigation.charging_navigation_message(charger=True)
        )

    if nav_status == 602 and not ghost_recovered:
        _, reason = _tour_navigation.assess_tour_readiness(
            nav_status,
            loc,
            min_localization=LOCALIZATION_MIN_PERCENT,
            require_known_localization=True,
            **_readiness_kwargs(snap),
        )
        raise RuntimeError(reason)

    if nav_status == 604:
        _, reason = _tour_navigation.assess_tour_readiness(
            nav_status,
            loc,
            min_localization=LOCALIZATION_MIN_PERCENT,
            require_known_localization=True,
        )
        raise RuntimeError(reason)

    needs_reloc = (
        nav_status == 600
        or loc is None
        or (loc is not None and loc < LOCALIZATION_MIN_PERCENT)
    )
    if needs_reloc:
        loc_ok, snap = await ensure_global_localization()
        nav_status = int(snap.get("nav_status") or 0)
        loc = snap.get("localization_percent")
        if not loc_ok:
            if nav_status == 600:
                raise RuntimeError(_tour_navigation.NAV_STATUS_HINTS[600])
            if loc is not None:
                raise RuntimeError(
                    f"Localisation insuffisante ({loc:.0f} % "
                    f"< {LOCALIZATION_MIN_PERCENT:.0f} %). Relocalisez le robot."
                )
            raise RuntimeError(
                "Localisation inconnue après relocalisation — vérifiez rosbridge "
                "et placez le robot sur une zone connue de la carte."
            )

    nav_status = int(snap.get("nav_status") or 0)
    stuck_605 = (
        nav_status == _tour_navigation.CHARGING_NAV_STATUS
        and not _tour_navigation.parse_charger_flag(snap.get("charger"))
    )
    ready, reason = _tour_navigation.assess_tour_readiness(
        nav_status,
        snap.get("localization_percent"),
        min_localization=LOCALIZATION_MIN_PERCENT,
        require_known_localization=True,
        **_readiness_kwargs(snap, ghost_nav_recovered=ghost_recovered or stuck_605),
    )
    if not ready:
        raise RuntimeError(reason)
    return snap


async def navigate_to_point(point_name: str) -> None:
    await prepare_for_nav_goal()
    if not await ensure_auto_navigation():
        raise RuntimeError("Impossible d'activer le mode navigation automatique")
    service, _ = await ros_call_service_first(_poi_nav_chain(point_name))
    if service:
        return
    point = find_point(point_name)
    if point:
        await navigate_to_coordinate(
            float(point["x"]),
            float(point["y"]),
            float(point.get("theta") or 0.0),
            skip_prepare=True,
        )
        return
    raise RuntimeError(f"Navigation POI échouée pour « {point_name} »")


async def navigate_to_coordinate(
    x: float,
    y: float,
    theta: float = 0.0,
    *,
    skip_prepare: bool = False,
) -> None:
    if not skip_prepare:
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


async def speak_local_and_wait(text: str, lang: str = "fr") -> None:
    """Envoie le TTS local et attend la fin réelle du service Android."""
    _speech_state["speaking"] = True
    _speech_state["last_text"] = text
    try:
        if not speak_local(text, lang):
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
    # control_state != 30 signale une prise de contrôle manuelle (joystick/téléop)
    # même quand le champ nav_mode brut n'a pas encore été remis à jour côté
    # châssis — même logique que sdk/real_robot.py._handle_status, nécessaire
    # pour pouvoir se fier à nav_mode et court-circuiter ensure_auto_navigation()
    # sans risquer de rater un passage en manuel.
    control_state = int(status_msg.get("control_state") or 30)
    nav_mode = str(status_msg.get("nav_mode") or "auto_navi")
    if control_state != 30:
        nav_mode = "manual"
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
        "charger": _tour_navigation.parse_charger_flag(status_msg.get("charger")),
        "connected": bool(pose_msg or status_msg),
        "nav_mode_label": "Manuel" if nav_mode == "manual" else "Automatique",
        "navigating_to": status_msg.get("navigating_to"),
        "soft_estop": bool(status_msg.get("soft_estop")),
        "hard_estop": bool(status_msg.get("hard_estop")),
        "nav_mode": nav_mode,
    }
    state["nav_status_label"] = NAV_STATUS_LABELS.get(state["nav_status"], "?")
    if state["x"] is not None:
        state["x"] = round(float(state["x"]), 3)
    if state["y"] is not None:
        state["y"] = round(float(state["y"]), 3)
    if state["theta"] is not None:
        state["theta"] = round(float(state["theta"]), 3)
    return state


async def fetch_robot_snapshot(timeout: float = 6.0) -> dict:
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
                    if pose_msg and status_msg and loc_msg:
                        break
                    if pose_msg and status_msg and loop.time() > deadline - 1.0:
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
    except Exception:
        pass
    return _merge_robot_state(pose_msg, status_msg, loc_msg or None)


def _stop_goal_xy(stop) -> tuple[float | None, float | None]:
    """Coordonnées cible d'un arrêt (coords directes ou POI dans points.json)."""
    if stop is None:
        return None, None
    if getattr(stop, "x", None) is not None and getattr(stop, "y", None) is not None:
        return float(stop.x), float(stop.y)
    target = getattr(stop, "target_point", None)
    if target:
        point = find_point(str(target))
        if point is not None:
            return float(point.get("x", 0.0)), float(point.get("y", 0.0))
    return None, None


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
    goal_x, goal_y = _stop_goal_xy(stop)

    def _robot_velocity(robot: dict) -> tuple[float, float]:
        velocity = robot.get("velocity") or [0.0, 0.0]
        if isinstance(velocity, (list, tuple)) and len(velocity) >= 2:
            return float(velocity[0]), float(velocity[1])
        return 0.0, 0.0

    def _arrived(robot: dict, nav_status: int) -> bool:
        return _tour_navigation.evaluate_navigation_arrival(
            nav_status=nav_status,
            saw_active=saw_active,
            pose_x=float(robot.get("x") or 0.0),
            pose_y=float(robot.get("y") or 0.0),
            goal_x=goal_x,
            goal_y=goal_y,
            velocity=_robot_velocity(robot),
        )

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
            elif goal_x is not None and goal_y is not None and robot.get("x") is not None:
                distance = _tour_trace.distance_xy(
                    float(robot["x"]),
                    float(robot["y"]),
                    goal_x,
                    goal_y,
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
                robot = _merge_robot_state(pose_msg, status_msg, loc_msg or None)
                nav_status = int(robot.get("nav_status") or 0)
                vx, vy = _robot_velocity(robot)
                if abs(vx) > 0.05 or abs(vy) > 0.05:
                    saw_active = True
                if not saw_active and loop.time() > activation_deadline:
                    if _arrived(robot, nav_status):
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
            vx, vy = _robot_velocity(robot)
            if abs(vx) > 0.05 or abs(vy) > 0.05:
                saw_active = True
            if _arrived(robot, nav_status):
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
            if not saw_active and loop.time() > activation_deadline:
                if _arrived(robot, nav_status):
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


async def go_home() -> bool:
    """Retour borne de recharge (SelfChassis.sendGoHome)."""
    snap = await ensure_leave_charge_if_needed(timeout=3.0)
    if int(snap.get("nav_status") or 0) == _tour_navigation.CHARGING_NAV_STATUS:
        return True
    await cancel_navigation_full(
        point_name=str(snap.get("navigating_to") or "") or None
    )
    try:
        await ros_call_service("/change_location_mode", {"mode": 1})
    except Exception:
        pass
    try:
        uri = f"ws://{ROBOT_HOST}:{ROBOT_WS_PORT}"
        async with websockets.connect(uri, open_timeout=4) as ws:
            await ws.send(
                json.dumps(
                    {
                        "op": "publish",
                        "topic": CHARGE_HOME_TOPIC,
                        "msg": {"data": True},
                    }
                )
            )
    except Exception:
        pass
    try:
        response = await ros_call_service(START_RECHARGE_SERVICE, {}, timeout=8.0)
        return response.get("result", True) is not False
    except Exception:
        return False


async def stop_robot() -> None:
    snap = await fetch_robot_snapshot(timeout=3.0)
    await cancel_navigation_full(
        point_name=str(snap.get("navigating_to") or "") or None
    )


async def execute_action(action_id: str, lang: str) -> dict:
    action = find_action(action_id)
    if not action:
        return {"ok": False, "error": f"Action '{action_id}' inconnue"}

    events: list[str] = []

    if action_id == "stop_all":
        await stop_robot()
        events.append("Action interrompue")
        return {"ok": True, "action": action_id, "events": events}

    if action_id == "return_charge":
        ok = await go_home()
        if not ok:
            return {"ok": False, "error": "Retour à la borne impossible"}
        events.append("Retour à la borne de recharge")
        return {"ok": True, "action": action_id, "events": events}

    if action_id == "guided_tour":
        return {"ok": False, "error": "use_tour_start", "action": action_id}

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
            point = find_point(str(target))
            if point:
                try:
                    await navigate_to_coordinate(
                        float(point["x"]),
                        float(point["y"]),
                        float(point.get("theta") or 0.0),
                    )
                    events.append(f"Navigation vers {target} (coordonnées)")
                except Exception as exc2:
                    return {"ok": False, "error": f"Navigation échouée : {exc2}"}
            else:
                return {"ok": False, "error": f"Navigation échouée : {exc}"}

    route = action.get("route_name")
    if route:
        events.append(f"Visite guidée — utilisez le bouton « Visite guidée »")

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


def build_tour_engine(tracer=None, available_poi: set[str] | None = None) -> TourEngine:
    tour = load_lab_tour(TOUR_PATH if TOUR_PATH.is_file() else None)
    if available_poi is not None:
        tour = filter_tour_by_poi(tour, available_poi)

    async def speak(text: str) -> None:
        await speak_local_and_wait(text)

    async def navigate(stop, index: int) -> None:
        snap_before = await fetch_robot_snapshot()
        if tracer:
            tracer.robot_snapshot("nav_before", snap_before, stop=stop)
        if stop.target_point:
            if tracer:
                tracer.nav_command(
                    stop,
                    index=index,
                    robot=snap_before,
                    nav_status=snap_before.get("nav_status"),
                    nav_status_label=str(snap_before.get("nav_status_label", "")),
                    detail=f"service /tag_manager/navi → {stop.target_point}",
                )
            await navigate_to_point(str(stop.target_point))
            arrived, err = await wait_for_navigation_arrival(
                tracer=tracer, stop=stop, stop_index=index
            )
            if not arrived:
                raise RuntimeError(err)
        elif stop.has_coordinates():
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
    sync_ok, _, sync_err = await sync_poi_from_ros_map()
    if not sync_ok:
        return JSONResponse(
            {"ok": False, "error": sync_err or "Synchronisation POI impossible"},
            status_code=503,
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
    available_poi = {str(p.get("name")) for p in load_points() if p.get("name")}
    _tour_engine = build_tour_engine(tracer=_active_tracer, available_poi=available_poi)
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
    if action_id == "guided_tour":
        return await tour_start(request)
    try:
        result = await execute_action(action_id, lang)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    if result.get("error") == "use_tour_start":
        return await tour_start(request)
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


def load_visitors() -> list[dict]:
    if not VISITORS_PATH.is_file():
        return []
    with open(VISITORS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("visitors", []))


def save_visitors(visitors: list[dict]) -> None:
    VISITORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "visitors": visitors,
    }
    with open(VISITORS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def find_visitor(visitor_id: str) -> dict | None:
    return next((v for v in load_visitors() if v.get("id") == visitor_id), None)


def visitor_public(visitor: dict) -> dict:
    """Retire l'embedding — ne jamais exposer les données biométriques au client."""
    return {k: v for k, v in visitor.items() if k != "embedding"}


def kiosk_destinations() -> list[dict]:
    tour = load_lab_tour(TOUR_PATH if TOUR_PATH.is_file() else None)
    tour_names = {
        stop.target_point
        for stop in tour.stops
        if getattr(stop, "target_point", None)
    }
    return [
        p
        for p in load_points()
        if p.get("kiosk_visible", True) and p.get("name") in tour_names
    ]


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
        "presence_welcome_enabled": True,
        "presence_max_distance_m": 3.0,
        "presence_cooldown_seconds": 90,
        "presence_speak_welcome": True,
        "face_recognition_enabled": False,
        "face_recognition_threshold": DEFAULT_FACE_RECOGNITION_THRESHOLD,
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
        "presence_welcome_enabled",
        "presence_max_distance_m",
        "presence_cooldown_seconds",
        "presence_speak_welcome",
        "face_recognition_enabled",
        "face_recognition_threshold",
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
    on_charger = _tour_navigation.parse_charger_flag(snap.get("charger"))
    return {
        "connected": bool(snap.get("connected")),
        "battery": int(snap.get("battery") or 0),
        "charger": on_charger,
        "soft_estop": bool(snap.get("soft_estop")),
        "hard_estop": bool(snap.get("hard_estop")),
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


async def navigation_cancel(_: Request) -> JSONResponse:
    snap = await ensure_leave_charge_if_needed()
    snap = await recover_navigation_state(timeout=15.0)
    nav_status = int(snap.get("nav_status") or 0)
    ghost = nav_status == 602 and _ghost_nav(snap)
    ok = nav_status in (601, 603) or ghost
    payload = {
        "ok": ok,
        **robot_status_payload(snap),
    }
    if not ok:
        payload["error"] = (
            f"État navigation {nav_status} non récupéré — relocalisez ou redémarrez "
            "la stack ROS du robot."
        )
        return JSONResponse(payload, status_code=409)
    return JSONResponse(payload)


async def charge_go_home(_: Request) -> JSONResponse:
    ok = await go_home()
    snap = await fetch_robot_snapshot()
    payload = {"ok": ok, **robot_status_payload(snap)}
    if not ok:
        payload["error"] = "Retour à la borne de recharge refusé"
        return JSONResponse(payload, status_code=409)
    return JSONResponse(payload)


async def kiosk_diagnostics(_: Request) -> JSONResponse:
    snap = await fetch_robot_snapshot(timeout=8.0)
    nav_status = int(snap.get("nav_status") or 0)
    loc = snap.get("localization_percent")
    ready, reason = _tour_navigation.assess_tour_readiness(
        nav_status,
        loc,
        min_localization=LOCALIZATION_MIN_PERCENT,
        require_known_localization=True,
        **_readiness_kwargs(snap, ghost_nav_recovered=_ghost_nav(snap)),
    )
    return JSONResponse(
        {
            "mode": "termux-lite",
            "robot_host": ROBOT_HOST,
            "overall_ok": ready,
            "blocking_reason": reason or None,
            "robot": robot_status_payload(snap),
        }
    )


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


def save_points(points: list[dict]) -> None:
    from datetime import datetime, timezone

    POINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "points": points,
    }
    with open(POINTS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


_MARKER_UTILS_MODULE = None


def _load_marker_utils():
    global _MARKER_UTILS_MODULE
    if _MARKER_UTILS_MODULE is not None:
        return _MARKER_UTILS_MODULE
    for dep in ("constants", "poi_names", "ros_ops"):
        _load_sdk_module_from_file(dep)
    _MARKER_UTILS_MODULE = _load_sdk_module_from_file("marker_utils")
    return _MARKER_UTILS_MODULE


async def fetch_raw_markers_from_ros() -> list[dict]:
    marker_utils = _load_marker_utils()
    for service in MARKER_SERVICE_CHAIN:
        response = await ros_call_service(service, {})
        raw = marker_utils.extract_raw_markers(response)
        if raw:
            return raw
    return []


async def sync_poi_from_ros_map() -> tuple[bool, dict | None, str | None]:
    """Lit les POI ROS (carte courante) et remplace points.json (supprime les absents)."""
    try:
        marker_utils = _load_marker_utils()
        raw_markers = await fetch_raw_markers_from_ros()
        if not raw_markers:
            return False, None, "Aucun marqueur ROS — créez les POI dans Deployment Tool."
        tour = load_lab_tour(TOUR_PATH if TOUR_PATH.is_file() else None)
        mark_kiosk = {
            stop.target_point
            for stop in tour.stops
            if getattr(stop, "target_point", None)
        }
        merged = marker_utils.merge_point_dicts(
            load_points(),
            raw_markers,
            mark_kiosk=mark_kiosk,
        )
        save_points(merged)
        summary = {
            "ros_count": len(raw_markers),
            "total_count": len(merged),
            "kiosk_visible_count": sum(1 for p in merged if p.get("kiosk_visible")),
        }
        return True, summary, None
    except Exception as exc:
        return False, None, f"Sync POI échouée : {exc}"


async def navigation_sync_points(_: Request) -> JSONResponse:
    """Synchronise POI ROS (Sentrymove) → data/points.json sur la tablette."""
    ok, summary, err = await sync_poi_from_ros_map()
    if not ok:
        return JSONResponse({"ok": False, "error": err}, status_code=503)
    return JSONResponse(
        {
            "ok": True,
            "summary": summary,
            "points": load_points(),
        }
    )


async def navigation_list_points(_: Request) -> JSONResponse:
    return JSONResponse(load_points())


async def list_destinations(_: Request) -> JSONResponse:
    sync_ok, _, sync_err = await sync_poi_from_ros_map()
    if not sync_ok:
        cached = kiosk_destinations()
        if cached:
            return JSONResponse(cached)
        return JSONResponse(
            {"ok": False, "error": sync_err or "Synchronisation POI impossible"},
            status_code=503,
        )
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

    ready, reason, _ = await prepare_for_tour()
    if not ready:
        return JSONResponse({"ok": False, "error": reason}, status_code=400)
    if not await ensure_auto_navigation():
        return JSONResponse(
            {
                "ok": False,
                "error": "Impossible d'activer le mode navigation automatique",
            },
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


async def _voice_navigate(point_name: str, lang: str) -> dict:
    """Prépare la navigation (localisation, mode auto), annonce et lance le trajet.
    Même chaîne que go_destination, réutilisée par les commandes vocales."""
    point = find_point(point_name)
    if not point:
        return {"ok": False, "error": f"Destination « {point_name} » inconnue"}
    ready, reason, _ = await prepare_for_tour()
    if not ready:
        return {"ok": False, "error": reason}
    if not await ensure_auto_navigation():
        return {"ok": False, "error": "Impossible d'activer le mode navigation automatique"}
    welcome = (
        f"I will take you to {point_name}. Please follow me."
        if lang == "en"
        else f"Je vous accompagne vers {point_name}. Suivez-moi."
    )
    speak_local(welcome)
    try:
        await navigate_to_point(point_name)
    except Exception as exc:
        return {"ok": False, "error": f"Navigation vers « {point_name} » impossible : {exc}"}
    return {"ok": True, "point": point_name, "reply": welcome}


async def handle_voice_command(text: str, lang: str) -> dict:
    """NLU minimal : commande vocale → action / navigation POI / réponse FAQ.

    Réutilise le moteur partagé (sdk.voice_commands, sdk.knowledge_engine) et les
    exécuteurs déjà présents dans ce backend (execute_action, navigate_to_point,
    speak_local). Renvoie un dict structuré (le champ `start_tour` signale au routeur
    d'enchaîner sur tour_start, qui a besoin de l'objet Request)."""
    voice = _get_voice_commands()
    cleaned = (text or "").strip()
    if not cleaned:
        return {"ok": False, "understood": False, "kind": "empty",
                "transcript": text, "reply": ""}

    # 1) Commande d'action (« visite guidée », « arrête », « accueil »…)
    action_id = voice.match_voice_command(cleaned)
    if action_id:
        if action_id == "guided_tour":
            return {"ok": True, "understood": True, "kind": "action",
                    "action": action_id, "transcript": cleaned,
                    "reply": "Je démarre la visite guidée." if lang == "fr"
                             else "Starting the guided tour.", "start_tour": True}
        result = await execute_action(action_id, lang)
        if result.get("error") == "use_tour_start":
            return {"ok": True, "understood": True, "kind": "action",
                    "action": action_id, "transcript": cleaned,
                    "reply": "Je démarre la visite guidée." if lang == "fr"
                             else "Starting the guided tour.", "start_tour": True}
        reply = "; ".join(result.get("events", [])) or result.get("error", "")
        return {"ok": bool(result.get("ok")), "understood": True, "kind": "action",
                "action": action_id, "transcript": cleaned,
                "reply": reply, "events": result.get("events", []),
                "error": result.get("error")}

    # 2) Navigation vers un POI nommé (« va à la porte labo »)
    point_names = [str(p.get("name", "")) for p in load_points() if p.get("name")]
    point_name = voice.match_point_navigation(cleaned, point_names)
    if point_name:
        nav = await _voice_navigate(point_name, lang)
        return {"ok": bool(nav.get("ok")), "understood": True, "kind": "navigation",
                "point": point_name, "transcript": cleaned,
                "reply": nav.get("reply") or nav.get("error", ""),
                "error": nav.get("error")}

    # 3) Question FAQ / connaissances (« qu'est-ce que HESTIM »)
    try:
        engine = _get_knowledge_engine()
        match = engine.match(cleaned, lang=lang, point_names=point_names)
    except Exception:
        match = None
    # Seuil aligné sur backend/services/knowledge_service.py : sous 2.0, un mot
    # générique (« est ») suffit à matcher n'importe quelle question — faux positifs.
    if match and getattr(match, "score", 0.0) < 2.0:
        match = None
    if match and getattr(match, "answer", ""):
        answer = str(match.answer)
        speak_local(answer)
        response = {"ok": True, "understood": True, "kind": "faq",
                    "transcript": cleaned, "reply": answer}
        # Si l'entrée pointe vers un lieu, on peut aussi y naviguer.
        target = getattr(match, "point_name", None)
        if target:
            nav = await _voice_navigate(str(target), lang)
            if nav.get("ok"):
                response["point"] = target
                response["kind"] = "faq+navigation"
        return response

    # 4) Non compris
    reply = ("Je n'ai pas compris votre demande. Vous pouvez me demander une "
             "destination, la visite guidée, ou une question sur HESTIM."
             if lang == "fr" else
             "I didn't understand. You can ask for a destination, the guided "
             "tour, or a question about HESTIM.")
    speak_local(reply)
    return {"ok": False, "understood": False, "kind": "unknown",
            "transcript": cleaned, "reply": reply}


async def voice_command(request: Request) -> JSONResponse:
    """POST /api/voice — reçoit un transcript (STT côté app native) et l'exécute."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "JSON invalide"}, status_code=400)
    text = str(body.get("text", "")).strip()
    lang = str(body.get("lang", "fr"))
    stt_end_ms = body.get("stt_end_ms")
    if not text:
        return JSONResponse({"ok": False, "error": "Texte vide"}, status_code=400)

    result = await handle_voice_command(text, lang)

    # Latence bout-en-bout (fin de parole détectée côté app native -> réponse
    # prête ici, TTS déjà déclenché par handle_voice_command/speak_local) —
    # même horloge système que le client puisque le kiosque et ce backend
    # tournent sur le même appareil (Termux). Métrique papier ICRA 2027.
    latency_ms: int | None = None
    if isinstance(stt_end_ms, (int, float)) and stt_end_ms > 0:
        latency_ms = round(time.time() * 1000 - stt_end_ms)

    try:
        _get_voice_logger().record(
            "voice_exchange",
            transcript=result.get("transcript", text),
            kind=result.get("kind", "unknown"),
            ok=bool(result.get("ok")),
            latency_ms=latency_ms,
        )
    except Exception:
        pass

    # Diffuse l'échange au kiosque (bulle transcript + réponse, TTS déjà déclenché).
    await _broadcast_to_telemetry({
        "type": "voice",
        "transcript": result.get("transcript", text),
        "reply": result.get("reply", ""),
        "kind": result.get("kind", "unknown"),
        "ok": bool(result.get("ok")),
        "latency_ms": latency_ms,
    })
    # La visite guidée a besoin de l'objet Request (tour_start) — enchaînement ici.
    if result.get("start_tour"):
        await tour_start(request)
    return JSONResponse(result)


async def voice_wake_event(request: Request) -> JSONResponse:
    """POST /api/voice/wake-event — journalise un déclenchement du mot d'éveil
    (confirmed=true si une commande a bien suivi, false si écoute restée
    silencieuse) pour mesurer le taux de faux déclenchements (métrique papier
    ICRA 2027, cf. scripts/measure_voice_latency.py)."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "JSON invalide"}, status_code=400)
    confirmed = bool(body.get("confirmed"))
    try:
        _get_voice_logger().record("wake_trigger", confirmed=confirmed)
    except Exception:
        pass
    return JSONResponse({"ok": True})


async def voice_vocabulary(_: Request) -> JSONResponse:
    """GET /api/voice/vocabulary — vocabulaire fermé pour contraindre le STT
    embarqué (grammaire Vosk) aux mots que ce backend comprend réellement :
    actions connues, POI actuellement déployés, questions/mots-clés FAQ.
    Calculé à la volée (pas de cache) pour rester en phase avec les POI et la
    base de connaissances actuels sans nécessiter de rebuild APK."""
    voice = _get_voice_commands()
    point_names = [str(p.get("name", "")) for p in load_points() if p.get("name")]
    extra_phrases = [str(entry.get("question_fr", "")) for entry in load_faq()]
    try:
        engine = _get_knowledge_engine()
        for lab_entry in engine.list_lab_entries():
            extra_phrases.extend(str(k) for k in lab_entry.get("keywords") or [])
    except Exception:
        pass
    words = voice.build_vocabulary(point_names=point_names, extra_phrases=extra_phrases)
    return JSONResponse({"words": words})


async def robot_status(_: Request) -> JSONResponse:
    snap = await fetch_robot_snapshot()
    return JSONResponse(robot_status_payload(snap))


async def robot_people(_: Request) -> JSONResponse:
    return JSONResponse({"people": get_detected_people()})


async def visitors_list(_: Request) -> JSONResponse:
    return JSONResponse([visitor_public(v) for v in load_visitors()])


async def visitors_current(_: Request) -> JSONResponse:
    if _current_identified_visitor is None or (time.time() - _current_identified_at) > VISITOR_IDENTITY_TTL_SECONDS:
        return JSONResponse({"visitor": None})
    return JSONResponse({"visitor": _current_identified_visitor})


async def visitors_identify(request: Request) -> JSONResponse:
    """Reçoit un embedding facial calculé par CybelFaceBridge (tablette) et le compare
    aux visiteurs enrôlés. Ne reçoit et n'expose jamais d'image — uniquement un vecteur."""
    global _current_identified_visitor, _current_identified_at
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "message": "JSON invalide"}, status_code=400)

    embedding = body.get("embedding")
    visitor_utils = _get_visitor_utils()
    if not visitor_utils.validate_embedding(embedding):
        return JSONResponse({"ok": False, "message": "Embedding invalide"}, status_code=400)

    visitors = load_visitors()
    candidates = [(v.get("id"), v.get("embedding") or []) for v in visitors]
    threshold = float(
        load_kiosk_config().get(
            "face_recognition_threshold", DEFAULT_FACE_RECOGNITION_THRESHOLD
        )
    )
    visitor_id, score = visitor_utils.find_best_match(embedding, candidates, threshold)
    if visitor_id is None:
        # Diffusé même sans correspondance : permet à l'interface opérateur de
        # confirmer en direct que la caméra voit bien un visage (« detected »),
        # utile pour calibrer le seuil ou vérifier la distinction entre plusieurs
        # visiteurs enrôlés, sans jamais transmettre d'image.
        await _broadcast_to_telemetry(
            {"type": "face_status", "detected": True, "matched": False, "confidence": score}
        )
        return JSONResponse({"ok": False, "confidence": score, "message": "Visiteur inconnu"})

    matched = next(v for v in visitors if v.get("id") == visitor_id)
    matched["last_identified_at"] = datetime.now(timezone.utc).isoformat()
    save_visitors(visitors)

    public = visitor_public(matched)
    _current_identified_visitor = public
    _current_identified_at = time.time()
    await _broadcast_to_telemetry({"type": "visitor", "visitor": public, "confidence": score})
    await _broadcast_to_telemetry(
        {"type": "face_status", "detected": True, "matched": True, "confidence": score, "visitor": public}
    )
    return JSONResponse({"ok": True, "visitor": public, "confidence": score})


async def visitors_enroll_trigger(request: Request) -> JSONResponse:
    """Déclenche à distance l'ouverture de la fenêtre d'enrôlement facial (15s) —
    permet à l'interface opérateur (frontend/, PC) de lancer un enrôlement sans
    accès direct (ADB/Termux) à la tablette. Le backend PC relaie ici via
    settings.kiosk_backend_url ; voir backend/services/visitor_service.py."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "JSON invalide"}, status_code=400)
    name = str(body.get("name", "")).strip()
    if not name:
        return JSONResponse({"ok": False, "error": "Nom requis"}, status_code=400)
    civility = str(body.get("civility", ""))
    if not trigger_face_enrollment(name, civility):
        return JSONResponse(
            {"ok": False, "error": "Déclenchement impossible (CybelFaceBridge indisponible ?)"},
            status_code=503,
        )
    return JSONResponse({"ok": True, "name": name, "window_seconds": 15})


async def visitors_enroll(request: Request) -> JSONResponse:
    """Enrôlement déclenché par le personnel (voir scripts/termux/enroll_visitor.sh) —
    jamais de capture automatique/silencieuse d'un visiteur non consentant."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "JSON invalide"}, status_code=400)

    name = str(body.get("name", "")).strip()
    civility = str(body.get("civility", ""))
    embedding = body.get("embedding")
    consent = bool(body.get("consent"))

    if not consent:
        return JSONResponse(
            {"ok": False, "error": "Le consentement du visiteur est requis"}, status_code=400
        )
    if not name:
        return JSONResponse({"ok": False, "error": "Nom requis"}, status_code=400)
    visitor_utils = _get_visitor_utils()
    if not visitor_utils.validate_embedding(embedding):
        return JSONResponse({"ok": False, "error": "Embedding invalide"}, status_code=400)

    visitor = {
        "id": str(uuid.uuid4()),
        "name": name,
        "civility": civility,
        "consent": consent,
        "enrolled_at": datetime.now(timezone.utc).isoformat(),
        "last_identified_at": None,
        "embedding": embedding,
    }
    visitors = load_visitors()
    visitors.append(visitor)
    save_visitors(visitors)
    return JSONResponse(visitor_public(visitor))


async def visitors_delete(request: Request) -> JSONResponse:
    global _current_identified_visitor
    visitor_id = request.path_params.get("visitor_id")
    visitors = load_visitors()
    remaining = [v for v in visitors if v.get("id") != visitor_id]
    if len(remaining) == len(visitors):
        return JSONResponse(
            {"ok": False, "error": f"Visiteur '{visitor_id}' introuvable"}, status_code=404
        )
    save_visitors(remaining)
    if _current_identified_visitor and _current_identified_visitor.get("id") == visitor_id:
        _current_identified_visitor = None
    return JSONResponse({"ok": True})


async def speech_status(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "speaking": bool(_speech_state.get("speaking")),
            "last_text": str(_speech_state.get("last_text") or ""),
            "mock": False,
        }
    )


async def velocity_profile_get(_: Request) -> JSONResponse:
    result = await get_velocity_profile()
    return JSONResponse(result, status_code=200 if result.get("ok") else 502)


async def velocity_profile_set(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "JSON invalide"}, status_code=400)
    level = str(body.get("level", "")).strip()
    if level not in VELOCITY_PROFILE_CMD:
        return JSONResponse(
            {"ok": False, "error": f"Niveau invalide (attendu : {', '.join(VELOCITY_PROFILE_CMD)})"},
            status_code=400,
        )
    result = await set_velocity_profile(level)
    return JSONResponse(result, status_code=200 if result.get("ok") else 502)


async def _people_listener_loop() -> None:
    """Écoute /detected_people_array (caméra robot) pour présence visiteur."""
    global _detected_people
    uri = f"ws://{ROBOT_HOST}:{ROBOT_WS_PORT}"
    people_utils = _get_people_utils()
    while True:
        try:
            async with websockets.connect(uri, open_timeout=5) as ws:
                await _subscribe_topics(ws, [PEOPLE_TOPIC])
                while True:
                    raw = await ws.recv()
                    data = json.loads(raw)
                    if data.get("topic") != PEOPLE_TOPIC:
                        continue
                    _detected_people = people_utils.parse_people_from_ros_message(
                        data.get("msg") or {}
                    )
        except Exception:
            await asyncio.sleep(2.0)


async def _broadcast_to_telemetry(message: dict) -> None:
    """Diffuse un événement ponctuel (pas rejoué en boucle, contrairement à status/people)."""
    payload = json.dumps(message)
    dead: list[WebSocket] = []
    for ws in list(_telemetry_sockets):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _telemetry_sockets.discard(ws)


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
        await websocket.send_text(
            json.dumps({"type": "people", "people": get_detected_people()})
        )
        if (
            _current_identified_visitor is not None
            and (time.time() - _current_identified_at) <= VISITOR_IDENTITY_TTL_SECONDS
        ):
            await websocket.send_text(
                json.dumps({"type": "visitor", "visitor": _current_identified_visitor})
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
                people_msg = json.dumps(
                    {"type": "people", "people": get_detected_people()}
                )
                dead: list[WebSocket] = []
                for ws in list(_telemetry_sockets):
                    try:
                        await ws.send_text(status_msg)
                        await ws.send_text(speech_msg)
                        await ws.send_text(tour_msg)
                        await ws.send_text(people_msg)
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
        Route("/api/navigation/points", navigation_list_points, methods=["GET"]),
        Route("/api/navigation/sync", navigation_sync_points, methods=["POST"]),
        Route("/api/reception/go", go_destination, methods=["POST"]),
        Route("/api/reception/actions", list_actions, methods=["GET"]),
        Route("/api/reception/actions/{action_id}/execute", run_action, methods=["POST"]),
        Route("/api/voice", voice_command, methods=["POST"]),
        Route("/api/voice/wake-event", voice_wake_event, methods=["POST"]),
        Route("/api/voice/vocabulary", voice_vocabulary, methods=["GET"]),
        Route("/api/reception/voice", voice_command, methods=["POST"]),
        Route("/api/robot/status", robot_status, methods=["GET"]),
        Route("/api/robot/people", robot_people, methods=["GET"]),
        Route("/api/visitors", visitors_list, methods=["GET"]),
        Route("/api/visitors/current", visitors_current, methods=["GET"]),
        Route("/api/visitors/identify", visitors_identify, methods=["POST"]),
        Route("/api/visitors/enroll", visitors_enroll, methods=["POST"]),
        Route("/api/visitors/enroll-trigger", visitors_enroll_trigger, methods=["POST"]),
        Route("/api/visitors/{visitor_id}", visitors_delete, methods=["DELETE"]),
        Route("/api/robot/relocalize", robot_relocalize, methods=["POST"]),
        Route("/api/navigation/cancel", navigation_cancel, methods=["POST"]),
        Route("/api/charge/go-home", charge_go_home, methods=["POST"]),
        Route("/api/diagnostics", kiosk_diagnostics, methods=["GET"]),
        Route("/api/speech/status", speech_status, methods=["GET"]),
        Route("/api/settings/velocity", velocity_profile_get, methods=["GET"]),
        Route("/api/settings/velocity", velocity_profile_set, methods=["POST"]),
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

    @asynccontextmanager
    async def _lifespan(_: Starlette):
        asyncio.create_task(_telemetry_broadcast_loop())
        asyncio.create_task(_people_listener_loop())
        yield

    return Starlette(routes=routes, lifespan=_lifespan)


app = build_app()


def main() -> None:
    print(f"CYBEL lite — http://0.0.0.0:{BACKEND_PORT} (robot {ROBOT_HOST}:{ROBOT_WS_PORT})")
    uvicorn.run(app, host="0.0.0.0", port=BACKEND_PORT, log_level="info")


if __name__ == "__main__":
    main()
