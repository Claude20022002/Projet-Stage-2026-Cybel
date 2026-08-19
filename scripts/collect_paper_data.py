#!/usr/bin/env python3
"""
collect_paper_data.py — collecte les métriques manquantes pour le papier ROSCon Korea 2027.

Phases :
  rosapi  — compte exact de topics et services ROS actifs (via /rosapi/topics et /rosapi/services)
  teleop  — N essais de téléopération (succès = /robot_pose change de > 4 cm)
  nav     — comparaison S1 (coords /navi_goal) vs S3 (POI /tag_manager/navi) sur M essais chacun
  tts     — mesure latence broadcast ADB → CybelTTSBridge

Usage :
  python scripts/collect_paper_data.py --host 10.42.0.1
  python scripts/collect_paper_data.py --host 192.168.20.22 --teleop-trials 10 --nav-trials 5
  python scripts/collect_paper_data.py --host 10.42.0.1 --phase rosapi
  python scripts/collect_paper_data.py --phase tts --adb-serial 172.16.0.194:5555

Sortie : data/paper_metrics.json + résumé console pour copier dans main.tex
"""

import argparse
import asyncio
import io
import json
import math
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Force UTF-8 sur stdout (evite UnicodeEncodeError sur Windows/cp1252)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import websockets
except ImportError:
    sys.exit("Dependance manquante : pip install websockets")

# ── Chemins ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "paper_metrics.json"
POINTS_FILE = DATA_DIR / "points.json"

# ── Paramètres ─────────────────────────────────────────────────────────────────
DEFAULT_HOST = "10.42.0.1"
DEFAULT_PORT = 9090
DEFAULT_BACKEND_PORT = 8000
DEFAULT_BACKEND_TEST_PORT = 8001
DEFAULT_ADB_SERIAL = "172.16.0.194:5555"
# IP eth0 interne du châssis ROS — rosbridge oui, backend HTTP Termux non
CHASSIS_IP_PREFIX = "192.168.20."
DEBUG_LOG_PATH = ROOT / "debug-952273.log"
DEBUG_SESSION_ID = "952273"

TELEOP_SPEED = 0.15           # m/s — vitesse forward (faible pour sécurité)
TELEOP_DURATION = 0.8         # s   — durée de l'impulsion
TELEOP_POSE_THRESHOLD = 0.04  # m   — déplacement minimal pour considérer succès
TELEOP_INTER_TRIAL = 4.0      # s   — pause entre essais (robot se stabilise)

NAV_TIMEOUT = 90              # s   — timeout max par essai de navigation
NAV_INTER_TRIAL = 6.0         # s   — pause entre essais (repositionnement)

TTS_TEXT = "Bonjour"          # texte court pour minimiser la durée du test
TTS_INTER_TRIAL = 2.5         # s   — laisser le TTS terminer avant mesure suivante

TOUR_POLL_INTERVAL = 20.0     # s   — intervalle de polling statut visite
TOUR_TIMEOUT = 3600.0         # s   — timeout max par essai de visite (60 min)
TOUR_MAX_UNREACHABLE = 9      # sondages consécutifs illisibles avant abandon
                              # (9 x 20 s = 3 min : tolère une coupure Wi-Fi
                              #  passagère, sans consommer les 60 min de timeout)

# URL rosbridge active — initialisée dans run_async, utilisée par wait_nav_done
_ROSBRIDGE_URL: str = ""


def _agent_debug_log(
    location: str,
    message: str,
    data: dict | None = None,
    *,
    hypothesis_id: str = "",
    run_id: str = "pre-fix",
) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": DEBUG_SESSION_ID,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
        }
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass
    # #endregion


# ══════════════════════════════════════════════════════════════════════════════
# Helpers WebSocket / rosbridge
# ══════════════════════════════════════════════════════════════════════════════

async def ainput(prompt: str = "") -> str:
    """input() qui ne gèle pas la boucle asyncio.

    Un input() classique dans du code async bloque la boucle d'événements :
    pendant que l'opérateur positionne le robot, plus personne ne répond aux
    pings du WebSocket, et rosbridge coupe la session au bout de ping_timeout.
    Le symptôme observé était « no close frame received or sent » juste après
    la reprise, avec une télémétrie vide (nav_status=-1). En déportant la
    lecture clavier dans un thread, la boucle continue de tourner.
    """
    return await asyncio.to_thread(input, prompt)


async def ws_send(ws, msg: dict) -> None:
    try:
        await ws.send(json.dumps(msg))
    except Exception:
        pass  # WebSocket morte — on ignore silencieusement


async def ws_call(ws, service: str, args: dict | None = None, timeout: float = 8.0) -> dict:
    """Appel call_service rosbridge — retourne la réponse ou {} si timeout."""
    if args is None:
        args = {}
    req_id = f"call_{service.replace('/', '_')}_{int(time.time() * 1000)}"
    await ws_send(ws, {"op": "call_service", "id": req_id, "service": service, "args": args})
    deadline = time.time() + timeout
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(2.0, max(0.05, remaining)))
        except (asyncio.TimeoutError, TimeoutError, asyncio.CancelledError, Exception):
            break
        try:
            data = json.loads(raw)
        except Exception:
            break
        if data.get("id") == req_id or (
            data.get("op") == "service_response" and data.get("service") == service
        ):
            return data
    return {}


async def ws_subscribe(ws, topic: str, msg_type: str = "", throttle_ms: int = 200) -> None:
    msg: dict = {"op": "subscribe", "topic": topic, "throttle_rate": throttle_ms}
    if msg_type:
        msg["type"] = msg_type
    await ws_send(ws, msg)


async def ws_advertise(ws, topic: str, msg_type: str) -> None:
    await ws_send(ws, {"op": "advertise", "topic": topic, "type": msg_type})


async def ws_publish(ws, topic: str, msg_type: str, msg: dict) -> None:
    await ws_send(ws, {"op": "publish", "topic": topic, "type": msg_type, "msg": msg})


async def ws_recv(ws, timeout: float = 2.0) -> dict:
    """Lit un message WebSocket avec timeout — retourne {} si timeout ou erreur."""
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=max(0.05, timeout))
        return json.loads(raw)
    except (asyncio.TimeoutError, TimeoutError, asyncio.CancelledError, Exception):
        return {}


async def drain(ws, n: int = 10, timeout: float = 0.3) -> None:
    """Vider le buffer de réception."""
    for _ in range(n):
        try:
            await asyncio.wait_for(ws.recv(), timeout=max(0.05, timeout))
        except (asyncio.TimeoutError, TimeoutError, asyncio.CancelledError, Exception):
            break


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1 — rosapi : inventaire topics et services
# ══════════════════════════════════════════════════════════════════════════════

async def phase_rosapi(ws) -> dict:
    print("\n[Phase 1/4] Introspection rosapi — topics et services actifs...")

    resp_topics = await ws_call(ws, "/rosapi/topics", {}, timeout=10.0)
    topics: list[str] = (
        resp_topics.get("values", {}).get("topics", [])
        or resp_topics.get("topics", [])
    )

    resp_services = await ws_call(ws, "/rosapi/services", {}, timeout=10.0)
    services: list[str] = (
        resp_services.get("values", {}).get("services", [])
        or resp_services.get("services", [])
    )

    # Filtrer les topics rosapi internes (non pertinents pour le compte papier)
    ROSAPI_PREFIX = "/rosapi"
    user_topics = [t for t in topics if not t.startswith(ROSAPI_PREFIX)]
    user_services = [s for s in services if not s.startswith(ROSAPI_PREFIX)]

    print(f"  Topics totaux : {len(topics)}  (hors rosapi : {len(user_topics)})")
    print(f"  Services totaux : {len(services)}  (hors rosapi : {len(user_services)})")

    if user_topics:
        print("  Topics (5 premiers) :", user_topics[:5])
    if user_services:
        print("  Services (5 premiers) :", user_services[:5])

    return {
        "ros_topics_total": len(topics),
        "ros_topics_user": len(user_topics),
        "ros_topics_list": sorted(topics),
        "ros_services_total": len(services),
        "ros_services_user": len(user_services),
        "ros_services_list": sorted(services),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 — Téléopération
# ══════════════════════════════════════════════════════════════════════════════

async def read_latest_pose(ws, wait_s: float = 1.5) -> dict | None:
    """
    Lit la pose la plus recente en drainant tous les messages bufferises.
    Attend d'abord wait_s secondes que les messages s'accumulent,
    puis vide le buffer et retourne la derniere pose recue.
    """
    await asyncio.sleep(wait_s)
    latest: dict | None = None
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=0.25)
            msg = json.loads(raw)
            if msg.get("topic") == "/robot_pose":
                latest = msg.get("msg", {})
        except asyncio.TimeoutError:
            break
    return latest


async def read_robot_status(ws, timeout: float = 3.0) -> dict:
    """Lit le premier message /robot_status disponible."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = await ws_recv(ws, timeout=min(1.0, deadline - time.time()))
        if msg.get("topic") == "/robot_status":
            return msg.get("msg", {})
    return {}


async def phase_teleop(ws, n_trials: int = 10) -> dict:
    print(f"\n[Phase 2/4] Teleop — {n_trials} essais...")

    # Abonnements en premier (avant tout service call qui drainerait le buffer)
    await ws_advertise(ws, "/cmd_vel_mux/input/teleop", "geometry_msgs/Twist")
    await ws_subscribe(ws, "/robot_pose", "geometry_msgs/Pose2D", throttle_ms=100)
    await ws_subscribe(ws, "/robot_status", throttle_ms=300)
    await asyncio.sleep(1.0)

    # Diagnostic : lire l'etat du robot avant de commencer
    status = await read_robot_status(ws, timeout=4.0)
    nav_st = status.get("nav_status", -1)
    ctrl_st = status.get("control_state", -1)
    loc_pct = status.get("matching_degree", -1)
    print(f"  Statut robot : nav_status={nav_st}, control_state={ctrl_st}, localisation={loc_pct}%")

    if nav_st == 605:
        print("  AVERTISSEMENT: robot en charge (nav_status=605). Decrochez-le de la borne.")
        return {
            "teleop_trials": 0,
            "teleop_successes": 0,
            "teleop_success_rate_pct": 0.0,
            "teleop_skipped": True,
            "reason": "nav_status_605_charging",
        }

    # Approche Deployment Tool : publier cmd_vel SANS changer le mode
    # (SentryMove ne requiert pas /change_location_mode avant le joystick)
    print("  Publication cmd_vel directe (approche Deployment Tool, sans change_location_mode)...")

    TWIST_FWD = {"linear": {"x": TELEOP_SPEED, "y": 0.0, "z": 0.0},
                 "angular": {"x": 0.0, "y": 0.0, "z": 0.0}}
    TWIST_STOP = {"linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                  "angular": {"x": 0.0, "y": 0.0, "z": 0.0}}

    results = []

    for i in range(n_trials):
        print(f"  Essai {i + 1}/{n_trials}...", end=" ", flush=True)

        # Pose initiale : drainer le buffer puis lire la plus recente
        initial = await read_latest_pose(ws, wait_s=0.5)
        if not initial:
            print("(pas de pose — verifie la connexion rosbridge)")
            results.append({"trial": i + 1, "success": False, "reason": "no_initial_pose"})
            continue

        x0, y0 = initial.get("x", 0.0), initial.get("y", 0.0)

        # Impulsion forward pendant TELEOP_DURATION a ~10 Hz
        t_end = time.time() + TELEOP_DURATION
        while time.time() < t_end:
            await ws_publish(ws, "/cmd_vel_mux/input/teleop", "geometry_msgs/Twist", TWIST_FWD)
            await asyncio.sleep(0.1)

        # Stop
        await ws_publish(ws, "/cmd_vel_mux/input/teleop", "geometry_msgs/Twist", TWIST_STOP)

        # Pose finale : attendre stabilisation puis lire la plus recente
        final = await read_latest_pose(ws, wait_s=2.0)
        if not final:
            print("(pas de pose finale)")
            results.append({"trial": i + 1, "success": False, "reason": "no_final_pose"})
            await asyncio.sleep(TELEOP_INTER_TRIAL)
            continue

        x1, y1 = final.get("x", 0.0), final.get("y", 0.0)
        delta = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
        success = delta >= TELEOP_POSE_THRESHOLD

        print(f"{'OK' if success else 'ECHEC'}  delta={delta * 100:.1f}cm "
              f"({x0:.3f},{y0:.3f}) -> ({x1:.3f},{y1:.3f})")
        results.append({
            "trial": i + 1, "success": success,
            "delta_m": round(delta, 4),
            "pose_initial": {"x": x0, "y": y0},
            "pose_final": {"x": x1, "y": y1},
        })

        await asyncio.sleep(TELEOP_INTER_TRIAL)

    n_ok = sum(1 for r in results if r["success"])
    rate = n_ok / len(results) * 100 if results else 0
    print(f"  Teleop : {n_ok}/{len(results)} succes ({rate:.0f}%)")

    return {
        "teleop_trials": len(results),
        "teleop_successes": n_ok,
        "teleop_success_rate_pct": round(rate, 1),
        "teleop_results": results,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Phase 3 — Navigation S1 (coords) vs S3 (POI)
# ══════════════════════════════════════════════════════════════════════════════

async def wait_nav_done(
    ws,
    timeout: float = NAV_TIMEOUT,
    goal_xy: tuple[float, float] | None = None,
    arrive_radius_m: float = 0.8,
) -> tuple[int, float]:
    """Attend nav_status 603/604 ou détecte l'arrivée via vitesse+proximité cible.

    Utilise la connexion partagée `ws` (déjà souscrite aux topics nav dans phase_nav).
    ws_recv utilise asyncio.wait_for — CancelledError et TimeoutError sont capturées.
    """
    t0 = time.time()
    deadline = t0 + timeout
    saw_navigating = False
    pose_x: float | None = None
    pose_y: float | None = None
    last_vx = last_vy = 0.0
    stopped_since: float | None = None
    last_msg_time = time.time()
    silence_start: float | None = None

    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        msg = await ws_recv(ws, timeout=min(1.5, max(0.05, remaining)))
        topic = msg.get("topic", "")
        data = msg.get("msg", {})

        if topic:
            last_msg_time = time.time()
            silence_start = None
        else:
            if silence_start is None:
                silence_start = time.time()
            elif (time.time() - silence_start) >= 5.0:
                break

        if topic == "/navi_status":
            try:
                code = int(str(data.get("data", "-1")).strip())
            except ValueError:
                pass
            else:
                if code == 602:
                    saw_navigating = True
                    stopped_since = None
                if code in (603, 604):
                    if code == 603 and not saw_navigating:
                        pass
                    else:
                        return code, time.time() - t0

        elif topic == "/robot_status":
            nav = data.get("nav_status", -1)
            vel = data.get("velocity") or [0.0, 0.0]
            if isinstance(vel, (list, tuple)) and len(vel) >= 2:
                last_vx, last_vy = float(vel[0]), float(vel[1])
            if abs(last_vx) > 0.05 or abs(last_vy) > 0.05:
                saw_navigating = True
                stopped_since = None
            elif saw_navigating and stopped_since is None:
                stopped_since = time.time()
            if nav == 602:
                saw_navigating = True
                stopped_since = None
            if nav in (603, 604):
                if nav == 603 and not saw_navigating:
                    pass
                else:
                    return nav, time.time() - t0

        elif topic == "/robot_pose":
            new_x = data.get("x")
            new_y = data.get("y")
            if new_x is not None and new_y is not None and pose_x is not None and pose_y is not None:
                dx = abs(new_x - pose_x)
                dy = abs(new_y - pose_y)
                if dx > 0.02 or dy > 0.02:
                    saw_navigating = True
                    stopped_since = None
                elif saw_navigating and stopped_since is None and dx < 0.005 and dy < 0.005:
                    stopped_since = time.time()
            pose_x = new_x
            pose_y = new_y

        if goal_xy is not None and saw_navigating and pose_x is not None and pose_y is not None:
            dist = math.sqrt((pose_x - goal_xy[0]) ** 2 + (pose_y - goal_xy[1]) ** 2)
            if (
                stopped_since is not None
                and (time.time() - stopped_since) >= 1.0
                and dist < arrive_radius_m
            ):
                return 603, time.time() - t0
            if (time.time() - last_msg_time) >= 4.0 and dist < arrive_radius_m:
                return 603, time.time() - t0

    if saw_navigating and goal_xy is not None and pose_x is not None and pose_y is not None:
        dist = math.sqrt((pose_x - goal_xy[0]) ** 2 + (pose_y - goal_xy[1]) ** 2)
        if dist < arrive_radius_m:
            return 603, time.time() - t0

    return -1, time.time() - t0


async def cancel_nav_full(ws) -> None:
    """Annulation complète entre essais de navigation."""
    CANCEL_ID = {"id": "", "stamp": {"secs": 0, "nsecs": 0}}
    await ws_publish(ws, "/move_base/cancel", "actionlib_msgs/GoalID", CANCEL_ID)
    await ws_publish(ws, "/path_follower/cancel", "actionlib_msgs/GoalID", CANCEL_ID)
    await ws_call(ws, "/poi", {"name": "navi", "point_name": "", "command": "stop"}, timeout=3.0)
    STOP = {"linear": {"x": 0.0, "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": 0.0}}
    await ws_publish(ws, "/cmd_vel_mux/input/teleop", "geometry_msgs/Twist", STOP)
    await asyncio.sleep(1.5)


def _make_pose_msg(x: float, y: float, theta: float) -> dict:
    return {
        "header": {"frame_id": "map", "seq": 0, "stamp": {"secs": 0, "nsecs": 0}},
        "pose": {
            "position": {"x": x, "y": y, "z": 0.0},
            "orientation": {
                "x": 0.0, "y": 0.0,
                "z": round(math.sin(theta / 2), 6),
                "w": round(math.cos(theta / 2), 6),
            },
        },
    }


async def _nav_send_goal(ws, x: float, y: float, theta: float) -> None:
    await ws_advertise(ws, "/navi_goal", "geometry_msgs/PoseStamped")
    await ws_publish(ws, "/navi_goal", "geometry_msgs/PoseStamped", _make_pose_msg(x, y, theta))


async def nav_reset_to_away(ws, away_coords: tuple, away_name: str) -> None:
    """Navigate vers une position 'loin' non comptée pour repositionner le robot avant chaque essai."""
    print(f"    [reset→{away_name}] ...", end=" ", flush=True)
    await drain(ws, n=20, timeout=0.15)
    await _nav_send_goal(ws, *away_coords)
    code, elapsed = await wait_nav_done(ws, timeout=90.0, goal_xy=(away_coords[0], away_coords[1]))
    print(f"{'OK' if code == 603 else '?'} ({elapsed:.1f}s)")
    await cancel_nav_full(ws)


async def nav_s1_trial(ws, x: float, y: float, theta: float, idx: int) -> dict:
    print(f"    S1 essai {idx}: /navi_goal ({x:.2f}, {y:.2f}, θ={theta:.2f}) ...", end=" ", flush=True)
    await drain(ws, n=20, timeout=0.15)
    await _nav_send_goal(ws, x, y, theta)
    code, elapsed = await wait_nav_done(ws, timeout=NAV_TIMEOUT, goal_xy=(x, y))
    success = code == 603
    print(f"{'✓' if success else '✗'}  nav_status={code} ({elapsed:.1f}s)")
    return {"trial": idx, "strategy": "S1", "success": success,
            "nav_status_final": code, "elapsed_s": round(elapsed, 1)}


async def nav_s3_trial(
    ws,
    poi_name: str,
    poi_id: str,
    idx: int,
    goal_xy: tuple[float, float] | None = None,
) -> dict:
    print(f"    S3 essai {idx}: /poi '{poi_name}' ...", end=" ", flush=True)

    # Signature établie par introspection le 2026-08-19 :
    #   /rosapi/service_type("/poi")            -> yutong_assistance/poi
    #   /rosapi/service_request_details(...)    -> un seul champ : poi (string)
    # et /marker_manager/get_markers_brief renvoie les POI par NOM LISIBLE.
    #
    # Les versions antérieures appelaient /tag_manager/navi, qui n'existe pas
    # sur ce firmware (absent des 321 services introspectés, type vide), puis
    # /poi avec {name, point_name, command} — trois champs dont aucun n'est
    # celui attendu. Les deux campagnes précédentes ont donc mesuré un appel
    # malformé, pas la réutilisation des annotations.
    #
    # Ne PAS utiliser ws_call : il monopolise ws.recv() et jette les messages
    # /navi_status qui arrivent pendant l'attente du service_response.
    async def _fire(service: str, args: dict) -> None:
        req_id = f"call_{service.replace('/', '_')}_{int(time.time() * 1000)}"
        await ws_send(ws, {"op": "call_service", "id": req_id, "service": service, "args": args})
        await asyncio.sleep(0.3)
        await drain(ws, n=5, timeout=0.2)

    await drain(ws, n=20, timeout=0.15)
    await _fire("/poi", {"poi": poi_name})
    code, elapsed = await wait_nav_done(ws, timeout=NAV_TIMEOUT, goal_xy=goal_xy)

    success = code == 603
    print(f"{'✓' if success else '✗'}  nav_status={code} ({elapsed:.1f}s)")
    return {"trial": idx, "strategy": "S3", "success": success,
            "nav_status_final": code, "elapsed_s": round(elapsed, 1)}


async def phase_nav(ws, n_trials: int = 5) -> dict:
    print(f"\n[Phase 3/4] Navigation — {n_trials} essais S1 + {n_trials} essais S3...")

    # Charger les POI depuis data/points.json
    poi_name: str | None = None
    poi_id: str | None = None
    s1_coords: tuple[float, float, float] | None = None
    away_name: str | None = None
    away_coords: tuple[float, float, float] | None = None

    if POINTS_FILE.exists():
        raw = json.loads(POINTS_FILE.read_text(encoding="utf-8"))
        points_list: list = raw.get("points", [])
        eligible = [
            pt for pt in points_list
            if pt.get("name")
            and "RECHARGE" not in pt.get("name", "").upper()
            and pt.get("type", "common") != "charging"
            and pt.get("kiosk_visible", True)
        ]
        if eligible:
            pt0 = eligible[0]
            poi_name = pt0.get("name")
            poi_id = pt0.get("id", poi_name)
            s1_coords = (
                float(pt0.get("x", 0.0)),
                float(pt0.get("y", 0.0)),
                float(pt0.get("theta", 0.0)),
            )
        if len(eligible) > 1:
            pt1 = eligible[1]
            away_name = pt1.get("name")
            away_coords = (
                float(pt1.get("x", 0.0)),
                float(pt1.get("y", 0.0)),
                float(pt1.get("theta", 0.0)),
            )

    if not poi_name or not s1_coords:
        print("  ⚠ Aucun POI trouvé dans data/points.json — synchronisez d'abord les POI.")
        print("    Commande : python scripts/sync_poi_from_robot.py --host <IP>")
        return {"nav_skipped": True, "reason": "no_poi_in_points_json"}

    print(f"  POI cible : '{poi_name}' (id={poi_id})  coords S1 : ({s1_coords[0]:.2f}, {s1_coords[1]:.2f})")
    if away_coords:
        print(f"  POI reset  : '{away_name}'  coords : ({away_coords[0]:.2f}, {away_coords[1]:.2f})")

    # Activer mode automatique + subscribe nav_status + pose (pour détection arrivée)
    print("  Activation mode auto (/change_location_mode mode=1)...")
    await ws_call(ws, "/change_location_mode", {"mode": 1}, timeout=5.0)
    await ws_subscribe(ws, "/navi_status", throttle_ms=300)
    await ws_subscribe(ws, "/robot_status", throttle_ms=300)
    await ws_subscribe(ws, "/robot_pose", throttle_ms=300)
    await drain(ws)
    await asyncio.sleep(1.5)

    poi_goal_xy = (s1_coords[0], s1_coords[1])

    # ── S1 ──
    print(f"\n  — Stratégie S1 : coordonnées /navi_goal —")
    s1_results = []
    for i in range(n_trials):
        if away_coords:
            await nav_reset_to_away(ws, away_coords, away_name)
        r = await nav_s1_trial(ws, *s1_coords, idx=i + 1)
        s1_results.append(r)
        await cancel_nav_full(ws)
        await asyncio.sleep(NAV_INTER_TRIAL)

    # ── S3 ──
    print(f"\n  — Stratégie S3 : POI /tag_manager/navi —")
    s3_results = []
    for i in range(n_trials):
        if away_coords:
            await nav_reset_to_away(ws, away_coords, away_name)
        r = await nav_s3_trial(ws, poi_name, poi_id or poi_name, idx=i + 1, goal_xy=poi_goal_xy)
        s3_results.append(r)
        await cancel_nav_full(ws)
        await asyncio.sleep(NAV_INTER_TRIAL)

    def summarize(results: list[dict], label: str) -> dict:
        n = len(results)
        n_ok = sum(1 for r in results if r["success"])
        rate = n_ok / n * 100 if n else 0
        times_ok = [r["elapsed_s"] for r in results if r["success"]]
        avg_time = round(sum(times_ok) / len(times_ok), 1) if times_ok else None
        times_fail = [r["elapsed_s"] for r in results if not r["success"]]
        avg_recovery = round(sum(times_fail) / len(times_fail), 1) if times_fail else None
        print(f"  {label} : {n_ok}/{n} ({rate:.0f}%), moy={avg_time}s, récup={avg_recovery}s")
        return {
            "trials": n,
            "successes": n_ok,
            "success_rate_pct": round(rate, 1),
            "avg_time_s": avg_time,
            "avg_recovery_s": avg_recovery,
            "results": results,
        }

    return {
        "nav_poi_target": poi_name,
        "nav_s1": summarize(s1_results, "S1 (coords)"),
        "nav_s3": summarize(s3_results, "S3 (POI)  "),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Phase 4 — Latence TTS (ADB)
# ══════════════════════════════════════════════════════════════════════════════

def phase_tts(adb_serial: str, n_trials: int = 5) -> dict:
    print(f"\n[Phase 4/4] Latence TTS — {n_trials} mesures (adb -s {adb_serial})...")

    cmd = [
        "adb", "-s", adb_serial, "shell",
        (
            f"am broadcast -n com.cybel.ttsbridge/.SpeakReceiver "
            f"-a com.cybel.ttsbridge.SPEAK --es text '{TTS_TEXT}'"
        ),
    ]

    latencies_ms = []
    for i in range(n_trials):
        t0 = time.perf_counter()
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=10.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            # result=-1 means broadcast received (Android convention)
            success = res.returncode == 0 and b"Broadcast completed" in res.stdout
            if success:
                latencies_ms.append(elapsed_ms)
                print(f"  {i + 1}: {elapsed_ms:.0f} ms ✓")
            else:
                stdout = res.stdout.decode(errors="ignore")[:120]
                print(f"  {i + 1}: ✗ ({stdout})")
        except subprocess.TimeoutExpired:
            print(f"  {i + 1}: timeout ADB")
        except FileNotFoundError:
            print("  ⚠ 'adb' introuvable — vérifiez que Android SDK est sur le PATH")
            return {"tts_skipped": True, "reason": "adb_not_found"}

        time.sleep(TTS_INTER_TRIAL)

    if not latencies_ms:
        print("  ⚠ CybelTTSBridge absent ou adb non connecté.")
        print("  → Vérifiez : adb devices  et  adb install android/CybelTTSBridge/out/CybelTTSBridge.apk")
        return {"tts_skipped": True, "reason": "no_successful_broadcast"}

    avg = sum(latencies_ms) / len(latencies_ms)
    print(
        f"  Latence ADB → broadcast : min={min(latencies_ms):.0f} ms, "
        f"moy={avg:.0f} ms, max={max(latencies_ms):.0f} ms"
    )
    print(f"  Latence perçue (+ init TTS ~300 ms) : ~{avg + 300:.0f} ms")

    return {
        "tts_trials": len(latencies_ms),
        "tts_latency_adb_min_ms": round(min(latencies_ms)),
        "tts_latency_adb_avg_ms": round(avg),
        "tts_latency_adb_max_ms": round(max(latencies_ms)),
        "tts_latency_perceived_ms": round(avg + 300),
        "tts_note": "Latence ADB = commande→ack broadcast. Latence audio réelle ≈ +300 ms (init TextToSpeech Google).",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Phase 5 — tour : visite guidée complète (API REST backend)
# ══════════════════════════════════════════════════════════════════════════════

def _tour_metrics(results: list[dict], n_trials: int, session_start: float, base: str) -> dict:
    """Forme du bloc de résultats visite — partagée par la sauvegarde
    incrémentale et par le retour final, pour qu'elles ne divergent pas."""
    n_ok = sum(1 for r in results if r["success"])
    return {
        "tour_trials": n_trials,
        "tour_trials_done": len(results),
        "tour_successes": n_ok,
        "tour_completion_rate_pct": round(100 * n_ok / max(n_trials, 1), 1),
        "tour_results": results,
        "tour_session_duration_h": round((time.time() - session_start) / 3600, 2),
        "tour_backend_url": base,
    }


def save_partial(fragment: dict) -> None:
    """Écrit un résultat intermédiaire sur le disque, immédiatement.

    Une campagne de dix visites dure plus de deux heures. Sans cela, une
    coupure réseau ou un Ctrl-C au huitième essai emporte les sept précédents.
    On fusionne dans le fichier existant plutôt que de l'écraser, pour que les
    phases lancées séparément se cumulent.
    """
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        current: dict = {}
        if OUTPUT.exists():
            try:
                current = json.loads(OUTPUT.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                current = {}
        current.update(fragment)
        current["partial_saved_at"] = datetime.now().isoformat()
        OUTPUT.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        print(f"  [WARN] Sauvegarde intermédiaire impossible : {exc}")


def _http_get(url: str, timeout: float = 10.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def _http_post(url: str, timeout: float = 15.0) -> dict:
    try:
        req = urllib.request.Request(url, data=b"", method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except Exception:
            detail = body
        return {"error": detail, "ok": False}
    except Exception as exc:
        return {"error": str(exc), "ok": False}


def _backend_health_ok(host: str, port: int, timeout: float = 3.0) -> bool:
    resp = _http_get(f"http://{host}:{port}/api/health", timeout=timeout)
    ok = "error" not in resp and resp.get("status") == "ok"
    _agent_debug_log(
        "collect_paper_data.py:_backend_health_ok",
        "backend health probe",
        {"host": host, "port": port, "ok": ok, "resp_keys": list(resp.keys())[:6]},
        hypothesis_id="H1",
    )
    return ok


def resolve_backend_base(
    backend_host: str | None,
    backend_port: int | None,
    robot_host: str,
) -> tuple[str, str, int, str]:
    """Retourne (base_url, host, port, note) pour l'API REST Termux (pas le châssis ROS)."""
    candidates: list[tuple[str, int, str]] = []

    if backend_host:
        port = backend_port or DEFAULT_BACKEND_PORT
        candidates.append((backend_host, port, "argument --backend-host"))
    else:
        if not robot_host.startswith(CHASSIS_IP_PREFIX):
            for port in filter(None, (backend_port, DEFAULT_BACKEND_TEST_PORT, DEFAULT_BACKEND_PORT)):
                candidates.append((robot_host, port, f"--host {robot_host}"))
        else:
            _agent_debug_log(
                "collect_paper_data.py:resolve_backend_base",
                "robot host looks like chassis IP — skipping for HTTP",
                {"robot_host": robot_host},
                hypothesis_id="H1",
            )
        candidates.extend([
            ("127.0.0.1", DEFAULT_BACKEND_TEST_PORT, "ADB forward test (127.0.0.1:8001)"),
            ("127.0.0.1", DEFAULT_BACKEND_PORT, "ADB forward principal (127.0.0.1:8000)"),
            ("localhost", DEFAULT_BACKEND_TEST_PORT, "ADB forward test (localhost:8001)"),
            ("localhost", DEFAULT_BACKEND_PORT, "ADB forward principal (localhost:8000)"),
        ])

    seen: set[tuple[str, int]] = set()
    for host, port, note in candidates:
        key = (host, port)
        if key in seen:
            continue
        seen.add(key)
        if _backend_health_ok(host, port):
            base = f"http://{host}:{port}"
            _agent_debug_log(
                "collect_paper_data.py:resolve_backend_base",
                "backend resolved",
                {"base": base, "via": note, "robot_host": robot_host},
                hypothesis_id="H1",
            )
            return base, host, port, note

    if backend_host:
        host = backend_host
        port = backend_port or DEFAULT_BACKEND_PORT
        note = "fallback explicite --backend-host"
    elif robot_host.startswith(CHASSIS_IP_PREFIX):
        host = "127.0.0.1"
        port = backend_port or DEFAULT_BACKEND_TEST_PORT
        note = "fallback localhost (châssis ROS en --host)"
    else:
        host = robot_host
        port = backend_port or DEFAULT_BACKEND_PORT
        note = "fallback --host"

    base = f"http://{host}:{port}"
    _agent_debug_log(
        "collect_paper_data.py:resolve_backend_base",
        "no healthy backend found",
        {"fallback": base, "robot_host": robot_host, "backend_host": backend_host},
        hypothesis_id="H1",
    )
    return base, host, port, note


def _try_relocalize(base: str) -> bool:
    resp = _http_post(f"{base}/api/robot/relocalize", timeout=20.0)
    ok = bool(resp.get("ok"))
    _agent_debug_log(
        "collect_paper_data.py:_try_relocalize",
        "relocalize API",
        {"ok": ok, "error": resp.get("error"), "message": resp.get("message")},
        hypothesis_id="H5",
    )
    if ok:
        print("  [INFO] Relocalisation automatique lancée via API...")
        return True
    err = resp.get("error", "échec inconnu")
    print(f"  [WARN] Relocalisation API refusée : {err}")
    return False


def _tour_stop(base: str) -> None:
    """Stop any running tour (best-effort, non-fatal)."""
    _http_post(f"{base}/api/tour/stop", timeout=10.0)
    time.sleep(2)


def _tour_is_running(base: str) -> bool:
    st = _http_get(f"{base}/api/tour/status")
    return st.get("state") in ("running", "navigating", "speaking", "returning")


async def _wait_for_localization(
    base: str,
    min_pct: float = 60.0,
    auto_wait: float = 60.0,
    *,
    try_relocalize: bool = True,
) -> bool:
    """Poll /api/robot/status jusqu'à ce que loc >= min_pct ET nav_status != 600.

    nav_status=600 signifie "châssis non prêt à naviguer" côté firmware.
    Un loc% élevé ne suffit pas : il faut que /global_locate ait été appelé
    pour que le châssis passe de 600 → 601 (prêt).
    Cette situation se produit systématiquement après un redémarrage du backend.
    """
    relocalize_done = False
    deadline = time.time() + auto_wait
    while time.time() < deadline:
        st = _http_get(f"{base}/api/robot/status", timeout=8.0)
        loc = float(st.get("localization_percent") or 0.0)
        nav = int(st.get("nav_status") or 0)
        connected = bool(st.get("connected"))

        # nav_status 600 = châssis non localisé (firmware), même si AMCL loc% est ok.
        # 601 = prêt, 602 = en navigation, 603 = arrivé, 605 = en charge
        nav_ready = nav not in (600, 0)

        remaining = int(deadline - time.time())
        print(
            f"  [attente] loc={loc:.0f}% nav={nav} {'OK' if nav_ready and loc>=min_pct else '...'}"
            f" — encore {remaining}s",
            end="\r",
        )

        if loc >= min_pct and nav_ready:
            print(f"  [OK] Localisation {loc:.0f}%  nav_status={nav} (prêt)          ")
            return True

        # loc ok mais nav=600 → le /global_locate n'a pas été appelé.
        # Appeler /api/robot/relocalize (qui appelle ensure_global_localization côté serveur).
        if try_relocalize and not relocalize_done and connected:
            if loc >= min_pct and nav == 600:
                print(f"\n  [INFO] loc={loc:.0f}% ok mais nav_status=600 — relocalisation API...")
                _try_relocalize(base)
                relocalize_done = True
                deadline = time.time() + auto_wait  # reset le timer
            elif loc < min_pct and not relocalize_done:
                print(f"\n  [INFO] loc={loc:.0f}% insuffisante — relocalisation API...")
                _try_relocalize(base)
                relocalize_done = True
                deadline = time.time() + auto_wait

        await asyncio.sleep(3.0)

    print()
    return False


async def phase_tour(
    backend_host: str | None,
    backend_port: int | None,
    robot_host: str,
    n_trials: int,
) -> dict:
    base, bh, bport, via = resolve_backend_base(backend_host, backend_port, robot_host)
    print(f"\n[Phase tour] Visite guidée complète — {n_trials} essai(s) via {base}")
    if robot_host.startswith(CHASSIS_IP_PREFIX) and not backend_host:
        print(
            "  [INFO] --host pointe le châssis ROS (192.168.20.x) — "
            "le backend HTTP est sur la tablette Termux, pas sur le robot."
        )
    print(f"  [INFO] Backend résolu via : {via}")

    if not _backend_health_ok(bh, bport):
        print("  [ERREUR] Backend CYBEL injoignable.")
        print("  >> Sur le PC : .\\scripts\\kiosk_test.ps1 reparer")
        print("  >> Ou : python scripts/collect_paper_data.py --phase tour \\")
        print("         --host 192.168.20.22 --backend-host localhost --backend-port 8001")
        return {
            "tour_skipped": True,
            "reason": "backend_unreachable",
            "tour_backend_url": base,
        }

    # Recharger le tour depuis le disque (prend en compte return_point = POINT-RECHARGE)
    reload_resp = _http_post(f"{base}/api/tour/reload")
    if "error" in reload_resp:
        print(f"  [ATTENTION] Rechargement tour échoué : {reload_resp['error']}")
        print("  >> Le backend est-il démarré sur Termux ?")
    else:
        n_stops = reload_resp.get("stops", "?")
        print(f"  [OK] Tour rechargé — {n_stops} arrêt(s) + retour POINT-RECHARGE")

    results = []
    session_start = time.time()

    for trial_i in range(n_trials):
        if trial_i > 0:
            input(
                f"\n  ⚠  Replacez le robot si nécessaire, puis appuyez sur ENTRÉE "
                f"pour l'essai {trial_i + 1}/{n_trials} ... "
            )
            # Stopper la visite précédente si toujours en cours
            if _tour_is_running(base):
                print("  [INFO] Visite précédente encore active — arrêt forcé...")
                _tour_stop(base)
        else:
            print(f"\n  Essai 1/{n_trials} — démarrage de la visite...")

        # --- Vérification localisation avant chaque essai ---
        print(f"  Vérification localisation (45s max)...")
        loc_ok = await _wait_for_localization(base)
        if not loc_ok:
            print("  [!!] Robot non localisé après 45s d'attente automatique.")
            print("       Cause probable : le robot a dérivé ou la carte est perdue.")
            print("       → Sur la tablette CYBEL : appuyez sur 'Relocaliser', attendez ≥60%.")
            input("       → Puis appuyez sur ENTRÉE une fois relocalisé ... ")
            loc_ok = await _wait_for_localization(base, auto_wait=30.0)
            if not loc_ok:
                st = _http_get(f"{base}/api/robot/status")
                loc_val = float(st.get("localization_percent") or 0.0)
                err = f"localisation insuffisante ({loc_val:.0f}%)"
                print(f"  [ÉCHEC] {err} — essai annulé")
                results.append({"success": False, "error": err, "elapsed_s": 0.0})
                continue

        t0 = time.time()

        # Le backend bloque ~15-30s sur sync_poi + prepare_for_tour + ensure_auto_navigation
        # → timeout genereux de 90s pour le start
        start_resp = _http_post(f"{base}/api/tour/start?lang=fr", timeout=90.0)

        poll_only = False  # basculer en mode polling si le start semble avoir fonctionné
        start_err = str(start_resp.get("error", ""))

        if "timed out" in start_err or "timeout" in start_err.lower():
            # Le client a coupé mais le serveur a probablement lancé la visite
            print("  [INFO] Délai dépassé côté client — le serveur a peut-être lancé la visite, polling...")
            poll_only = True
        elif "déjà en cours" in start_err or "already" in start_err.lower():
            print("  [INFO] Visite déjà en cours (essai précédent non terminé) — polling...")
            poll_only = True
        elif start_resp.get("error") or not start_resp.get("ok"):
            err = start_resp.get("error", "démarrage refusé")
            print(f"  [ÉCHEC] Impossible de démarrer : {err}")
            results.append({"success": False, "error": str(err), "elapsed_s": 0.0})
            continue

        if not poll_only:
            print(f"  [OK] Visite démarrée. Polling toutes les {TOUR_POLL_INTERVAL:.0f} s...")

        success = False
        error_msg = None
        unreachable_polls = 0

        while True:
            await asyncio.sleep(TOUR_POLL_INTERVAL)
            elapsed = time.time() - t0

            if elapsed > TOUR_TIMEOUT:
                error_msg = f"timeout {TOUR_TIMEOUT/60:.0f} min"
                print(f"  [TIMEOUT] {error_msg}")
                break

            st = _http_get(f"{base}/api/tour/status")
            if st.get("error"):
                unreachable_polls += 1
                print(f"  [WARN] Statut illisible ({unreachable_polls}/{TOUR_MAX_UNREACHABLE}) "
                      f": {st['error']}")
                # Un backend définitivement mort sinon consommerait le timeout
                # complet, soit une heure perdue par essai.
                if unreachable_polls >= TOUR_MAX_UNREACHABLE:
                    error_msg = (f"backend injoignable sur {unreachable_polls} sondages "
                                 f"consécutifs")
                    print(f"  [ABANDON] {error_msg}")
                    print("       → Termux a-t-il été suspendu ? Vérifiez le wake lock :")
                    print("         termux-wake-lock  (paquet termux-api)")
                    break
                continue
            unreachable_polls = 0

            state = st.get("state", "unknown")
            phase = st.get("phase", "")
            idx = st.get("current_index", -1)
            total = st.get("total_stops", "?")
            name = st.get("current_stop_name", "")
            label = f"arrêt {idx + 1}/{total} {name}" if idx >= 0 else phase

            print(f"    t+{elapsed:5.0f}s | {state:10s} | {label}")

            if state == "completed":
                success = True
                break
            if state in ("stopped", "error"):
                error_msg = st.get("error") or state
                break
            if poll_only and state in ("idle", "unknown"):
                # Tour déjà finie avant qu'on commence à poller (cas rare)
                print("  [INFO] Aucune visite active détectée au premier polling")
                error_msg = "aucune visite active"
                break

        elapsed_total = time.time() - t0
        results.append({
            "success": success,
            "elapsed_s": round(elapsed_total, 1),
            "error": error_msg,
        })
        outcome = "SUCCÈS" if success else f"ÉCHEC ({error_msg})"
        print(f"  → Essai {trial_i + 1} : {outcome} en {elapsed_total / 60:.1f} min")

        # Sauvegarde après CHAQUE essai : une interruption au huitième ne doit
        # pas emporter les sept précédents.
        save_partial(_tour_metrics(results, n_trials, session_start, base))
        print(f"     (résultats intermédiaires écrits → {OUTPUT.name})")

    metrics = _tour_metrics(results, n_trials, session_start, base)
    print(f"\n  Taux de complétion : {metrics['tour_completion_rate_pct']}%  "
          f"({metrics['tour_successes']}/{n_trials})")
    print(f"  Durée session visite : {metrics['tour_session_duration_h']:.2f} h")
    return metrics


# ══════════════════════════════════════════════════════════════════════════════
# Rapport final
# ══════════════════════════════════════════════════════════════════════════════

SEPARATOR = "=" * 66

def print_paper_summary(m: dict) -> None:
    print(f"\n{SEPARATOR}")
    print("  VALEURS POUR LE PAPIER  —  copier dans main.tex")
    print(SEPARATOR)

    if "ros_topics_user" in m:
        print(f"\n  [tab:re-effort]")
        print(f"    Topics ROS découverts (hors rosapi)  : {m['ros_topics_user']}")
        print(f"    Services ROS découverts (hors rosapi): {m['ros_services_user']}")
        print(f"    (total brut : {m['ros_topics_total']} topics, {m['ros_services_total']} services)")

    if "teleop_success_rate_pct" in m:
        t = m
        print(f"\n  [tab:metrics]")
        print(f"    Téléopération : {t['teleop_success_rate_pct']}%  ({t['teleop_successes']}/{t['teleop_trials']} essais)")

    if "nav_s1" in m and "nav_s3" in m:
        s1, s3 = m["nav_s1"], m["nav_s3"]
        mf1 = f"{s1.get('avg_recovery_s', 'N/A')}s" if s1.get("avg_recovery_s") else "N/A"
        mf3 = f"{s3.get('avg_recovery_s', 'N/A')}s" if s3.get("avg_recovery_s") else "N/A"
        print(f"\n  [tab:navcompare]")
        print(f"    S1 (coords) : {s1['success_rate_pct']}%  moy {s1['avg_time_s']}s  récup {mf1}")
        print(f"    S3 (POI)    : {s3['success_rate_pct']}%  moy {s3['avg_time_s']}s  récup {mf3}")

    if "tts_latency_perceived_ms" in m:
        print(f"\n  [tab:metrics]")
        print(f"    Latence voix (ADB + init TTS) : ~{m['tts_latency_perceived_ms']} ms")

    if "tour_completion_rate_pct" in m:
        tr = m["tour_completion_rate_pct"]
        tn = m["tour_trials"]
        ts = m["tour_successes"]
        dur = m.get("tour_session_duration_h", 0)
        print(f"\n  [tab:metrics — visite guidée]")
        print(f"    Taux de complétion visite : {tr}%  ({ts}/{tn} essais)")
        print(f"    Durée session kiosque     : {dur:.2f} h  (→ uptime Termux)")
        print(f"\n  → Dans main.tex, remplacez :")
        print(f"      \\ph{{XX\\%}} (\\ph{{N}} trials)  par  {tr}\\%  ({tn} essais)")
        print(f"      \\ph{{X hours}}               par  {dur:.1f} heures")

    print(f"\n  Fichier complet : {OUTPUT}")
    print(SEPARATOR)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

async def run_async(args) -> dict:
    global _ROSBRIDGE_URL
    url = f"ws://{args.host}:{args.port}"
    _ROSBRIDGE_URL = url
    phases = set(args.phase) if args.phase else {"rosapi", "teleop", "nav", "tts"}

    metrics: dict = {
        "collected_at": datetime.now().isoformat(),
        "robot_host": args.host,
        "backend_host": args.backend_host or "(auto)",
        "backend_port": args.backend_port,
        "phases_run": sorted(phases),
    }

    # Phases qui nécessitent rosbridge
    ws_phases = {"rosapi", "teleop", "nav"} & phases
    if ws_phases:
        print(f"Connexion rosbridge {url} ...")
        try:
            async with websockets.connect(  # type: ignore[arg-type]
                url, open_timeout=12, ping_interval=15, ping_timeout=30
            ) as ws:
                print(f"[OK] Connecté\n")

                if "rosapi" in phases:
                    metrics.update(await phase_rosapi(ws))

                if "teleop" in phases:
                    input(
                        "\n  ⚠  Phase téléop : placez le robot dans une zone dégagée (≥ 50 cm).\n"
                        "     Appuyez sur ENTRÉE quand c'est prêt ... "
                    )
                    metrics.update(await phase_teleop(ws, n_trials=args.teleop_trials))

                if "nav" in phases:
                    input(
                        "\n  ⚠  Phase navigation : vérifiez que les POI Sentrymove sont créés\n"
                        "     et que le robot est bien localisé (localisation ≥ 60 %).\n"
                        "     Appuyez sur ENTRÉE quand c'est prêt ... "
                    )
                    metrics.update(await phase_nav(ws, n_trials=args.nav_trials))

        except (OSError, TimeoutError) as e:
            print(f"[ERREUR] Impossible de se connecter a {url} : {e}")
            print("  >> Verifiez que le robot est allume et que le PC est sur son Wi-Fi.")
            print(f"  >> Essayez aussi --host 192.168.20.22 (lien eth0 interne)")
            if ws_phases == phases:
                sys.exit(1)
            metrics["rosbridge_error"] = str(e)

        except websockets.exceptions.WebSocketException as e:
            print(f"[ERREUR] WebSocket : {e}")
            metrics["rosbridge_error"] = str(e)

    # Phase TTS (indépendante de rosbridge)
    if "tts" in phases:
        metrics.update(phase_tts(args.adb_serial, n_trials=args.tts_trials))

    # Phase tour (HTTP REST — indépendante de rosbridge)
    if "tour" in phases:
        input(
            "\n  ⚠  Phase visite guidée : assurez-vous que :\n"
            "       1. Le backend CYBEL tourne sur Termux (port 8000 ou 8001)\n"
            "       2. Le robot est localisé et la carte est chargée\n"
            "       3. Le robot est libre de ses mouvements dans le labo\n"
            "     Si USB branché : .\\scripts\\kiosk_test.ps1 reparer avant de continuer.\n"
            "     Appuyez sur ENTRÉE pour lancer la visite complète ... "
        )
        metrics.update(
            await phase_tour(
                args.backend_host,
                args.backend_port,
                args.host,
                n_trials=args.tour_trials,
            )
        )

    # Sauvegarde — on FUSIONNE avec le fichier existant au lieu de l'écraser.
    # Les phases se lancent une par une sur plusieurs heures : une écriture
    # brutale ici effacerait les phases précédentes de la même campagne.
    save_partial(metrics)
    print(f"\n✓  Résultats sauvegardés → {OUTPUT}")
    merged = json.loads(OUTPUT.read_text(encoding="utf-8"))
    known = [p for p in ("rosapi", "teleop", "nav", "tts", "tour")
             if any(k.startswith(p if p != "rosapi" else "ros_") for k in merged)]
    print(f"   Phases présentes dans le fichier : {', '.join(known) or '(aucune)'}")

    print_paper_summary(metrics)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collecte des métriques manquantes — papier ROSCon Korea 2027",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python scripts/collect_paper_data.py --host 10.42.0.1
  python scripts/collect_paper_data.py --host 192.168.20.22 --teleop-trials 10 --nav-trials 5
  python scripts/collect_paper_data.py --phase rosapi --host 10.42.0.1
  python scripts/collect_paper_data.py --phase tts --adb-serial 172.16.0.194:5555
  python scripts/collect_paper_data.py --phase tour --host 192.168.20.22 --backend-host localhost --backend-port 8001 --tour-trials 3
        """,
    )
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"IP rosbridge robot (défaut: {DEFAULT_HOST}). "
                             f"Ne pas utiliser {CHASSIS_IP_PREFIX}x pour le backend HTTP.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--backend-host", default=None,
                        help="IP du backend Termux (tablette). Défaut : auto (localhost:8001/8000 via ADB)")
    parser.add_argument("--backend-port", type=int, default=None,
                        help=f"Port HTTP backend (défaut : auto — test {DEFAULT_BACKEND_TEST_PORT}, "
                             f"principal {DEFAULT_BACKEND_PORT})")
    parser.add_argument("--teleop-trials", type=int, default=10, metavar="N",
                        help="Nombre d'essais téléopération (défaut: 10)")
    parser.add_argument("--nav-trials", type=int, default=5, metavar="N",
                        help="Nombre d'essais navigation S1+S3 chacun (défaut: 5)")
    parser.add_argument("--tts-trials", type=int, default=5, metavar="N",
                        help="Nombre de mesures TTS (défaut: 5)")
    parser.add_argument("--tour-trials", type=int, default=3, metavar="N",
                        help="Nombre d'essais visite guidée (défaut: 3)")
    parser.add_argument("--adb-serial", default=DEFAULT_ADB_SERIAL,
                        help=f"Identifiant ADB de la tête Android (défaut: {DEFAULT_ADB_SERIAL})")
    parser.add_argument(
        "--phase", nargs="+", choices=["rosapi", "teleop", "nav", "tts", "tour"],
        help="Phases à exécuter (défaut: toutes sauf tour). Ex: --phase tour",
    )
    args = parser.parse_args()
    asyncio.run(run_async(args))


if __name__ == "__main__":
    main()
