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
DEFAULT_ADB_SERIAL = "172.16.0.194:5555"

TELEOP_SPEED = 0.15           # m/s — vitesse forward (faible pour sécurité)
TELEOP_DURATION = 0.8         # s   — durée de l'impulsion
TELEOP_POSE_THRESHOLD = 0.04  # m   — déplacement minimal pour considérer succès
TELEOP_INTER_TRIAL = 4.0      # s   — pause entre essais (robot se stabilise)

NAV_TIMEOUT = 60              # s   — timeout max par essai de navigation
NAV_INTER_TRIAL = 6.0         # s   — pause entre essais (repositionnement)

TTS_TEXT = "Bonjour"          # texte court pour minimiser la durée du test
TTS_INTER_TRIAL = 2.5         # s   — laisser le TTS terminer avant mesure suivante

TOUR_POLL_INTERVAL = 20.0     # s   — intervalle de polling statut visite
TOUR_TIMEOUT = 3600.0         # s   — timeout max par essai de visite (60 min)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers WebSocket / rosbridge
# ══════════════════════════════════════════════════════════════════════════════

async def ws_send(ws, msg: dict) -> None:
    await ws.send(json.dumps(msg))


async def ws_call(ws, service: str, args: dict | None = None, timeout: float = 8.0) -> dict:
    """Appel call_service rosbridge — retourne la réponse ou {} si timeout."""
    if args is None:
        args = {}
    req_id = f"call_{service.replace('/', '_')}_{int(time.time() * 1000)}"
    await ws_send(ws, {"op": "call_service", "id": req_id, "service": service, "args": args})
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(2.0, deadline - time.time()))
        except asyncio.TimeoutError:
            break
        data = json.loads(raw)
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
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        return json.loads(raw)
    except (asyncio.TimeoutError, Exception):
        return {}


async def drain(ws, n: int = 10, timeout: float = 0.3) -> None:
    """Vider le buffer de réception."""
    for _ in range(n):
        try:
            await asyncio.wait_for(ws.recv(), timeout=timeout)
        except (asyncio.TimeoutError, Exception):
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

async def wait_nav_done(ws, timeout: float = NAV_TIMEOUT) -> tuple[int, float]:
    """Attend nav_status 603 (arrivé) ou 604 (erreur). Retourne (code, durée_s)."""
    t0 = time.time()
    deadline = t0 + timeout
    while time.time() < deadline:
        msg = await ws_recv(ws, timeout=min(1.5, deadline - time.time()))
        topic = msg.get("topic", "")
        data = msg.get("msg", {})

        if topic == "/navi_status":
            try:
                code = int(str(data.get("data", "-1")).strip())
            except ValueError:
                continue
            if code in (603, 604):
                return code, time.time() - t0

        elif topic == "/robot_status":
            nav = data.get("nav_status", -1)
            if nav in (603, 604):
                return nav, time.time() - t0

    return -1, time.time() - t0  # -1 = timeout


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
    await _nav_send_goal(ws, *away_coords)
    code, elapsed = await wait_nav_done(ws, timeout=60.0)
    print(f"{'OK' if code == 603 else '?'} ({elapsed:.1f}s)")
    await cancel_nav_full(ws)


async def nav_s1_trial(ws, x: float, y: float, theta: float, idx: int) -> dict:
    print(f"    S1 essai {idx}: /navi_goal ({x:.2f}, {y:.2f}, θ={theta:.2f}) ...", end=" ", flush=True)
    await _nav_send_goal(ws, x, y, theta)
    code, elapsed = await wait_nav_done(ws, timeout=NAV_TIMEOUT)
    success = code == 603
    print(f"{'✓' if success else '✗'}  nav_status={code} ({elapsed:.1f}s)")
    return {"trial": idx, "strategy": "S1", "success": success,
            "nav_status_final": code, "elapsed_s": round(elapsed, 1)}


async def nav_s3_trial(ws, poi_name: str, poi_id: str, idx: int) -> dict:
    print(f"    S3 essai {idx}: /tag_manager/navi '{poi_name}' ...", end=" ", flush=True)

    # Ne PAS utiliser ws_call : il monopolise ws.recv() et jette les messages
    # /navi_status qui arrivent pendant l'attente du service_response.
    # On envoie en fire-and-forget, puis on écoute nav_status immédiatement.
    async def _fire(service: str, args: dict) -> None:
        req_id = f"call_{service.replace('/', '_')}_{int(time.time() * 1000)}"
        await ws_send(ws, {"op": "call_service", "id": req_id, "service": service, "args": args})
        await asyncio.sleep(0.3)
        await drain(ws, n=5, timeout=0.2)

    # Tentative 1 : nom lisible ("CNC ROUTEUR")
    await _fire("/tag_manager/navi", {"name": poi_name, "tag_name": poi_name})
    code, elapsed = await wait_nav_done(ws, timeout=NAV_TIMEOUT)

    if code == -1:
        # Tentative 2 : ID interne du marqueur ("m1")
        await cancel_nav_full(ws)
        await _fire("/tag_manager/navi", {"name": poi_id, "tag_name": poi_id})
        code2, elapsed2 = await wait_nav_done(ws, timeout=30.0)
        elapsed += elapsed2
        if code2 != -1:
            code = code2
        else:
            # Tentative 3 : fallback /poi
            await cancel_nav_full(ws)
            await _fire("/poi", {"name": "navi", "point_name": poi_name, "command": "go"})
            code3, elapsed3 = await wait_nav_done(ws, timeout=30.0)
            elapsed += elapsed3
            code = code3

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

    # Activer mode automatique + subscribe nav_status
    print("  Activation mode auto (/change_location_mode mode=1)...")
    await ws_call(ws, "/change_location_mode", {"mode": 1}, timeout=5.0)
    await ws_subscribe(ws, "/navi_status", throttle_ms=300)
    await ws_subscribe(ws, "/robot_status", throttle_ms=500)
    await drain(ws)
    await asyncio.sleep(1.5)

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
        r = await nav_s3_trial(ws, poi_name, poi_id or poi_name, idx=i + 1)
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


async def phase_tour(host: str, backend_port: int, n_trials: int) -> dict:
    base = f"http://{host}:{backend_port}"
    print(f"\n[Phase tour] Visite guidée complète — {n_trials} essai(s) via {base}")

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
        else:
            print(f"\n  Essai 1/{n_trials} — démarrage de la visite...")

        t0 = time.time()
        start_resp = _http_post(f"{base}/api/tour/start?lang=fr")

        if start_resp.get("error") or not start_resp.get("ok"):
            err = start_resp.get("error", "démarrage refusé")
            print(f"  [ÉCHEC] Impossible de démarrer : {err}")
            results.append({"success": False, "error": err, "elapsed_s": 0.0})
            continue

        print(f"  [OK] Visite démarrée. Polling toutes les {TOUR_POLL_INTERVAL:.0f} s...")
        success = False
        error_msg = None

        while True:
            await asyncio.sleep(TOUR_POLL_INTERVAL)
            elapsed = time.time() - t0

            if elapsed > TOUR_TIMEOUT:
                error_msg = f"timeout {TOUR_TIMEOUT/60:.0f} min"
                print(f"  [TIMEOUT] {error_msg}")
                break

            st = _http_get(f"{base}/api/tour/status")
            if "error" in st:
                print(f"  [WARN] Impossible de lire le statut : {st['error']}")
                continue

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

        elapsed_total = time.time() - t0
        results.append({
            "success": success,
            "elapsed_s": round(elapsed_total, 1),
            "error": error_msg,
        })
        outcome = "SUCCÈS" if success else f"ÉCHEC ({error_msg})"
        print(f"  → Essai {trial_i + 1} : {outcome} en {elapsed_total / 60:.1f} min")

    session_h = (time.time() - session_start) / 3600
    n_ok = sum(1 for r in results if r["success"])
    rate_pct = round(100 * n_ok / max(n_trials, 1), 1)

    print(f"\n  Taux de complétion : {rate_pct}%  ({n_ok}/{n_trials})")
    print(f"  Durée session visite : {session_h:.2f} h")

    return {
        "tour_trials": n_trials,
        "tour_successes": n_ok,
        "tour_completion_rate_pct": rate_pct,
        "tour_results": results,
        "tour_session_duration_h": round(session_h, 2),
    }


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
    url = f"ws://{args.host}:{args.port}"
    phases = set(args.phase) if args.phase else {"rosapi", "teleop", "nav", "tts"}

    metrics: dict = {
        "collected_at": datetime.now().isoformat(),
        "robot_host": args.host,
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
            "       1. Le backend CYBEL tourne sur Termux (port 8000)\n"
            "       2. Le robot est localisé et la carte est chargée\n"
            "       3. Le robot est libre de ses mouvements dans le labo\n"
            "     Appuyez sur ENTRÉE pour lancer la visite complète ... "
        )
        metrics.update(
            await phase_tour(args.host, args.backend_port, n_trials=args.tour_trials)
        )

    # Sauvegarde
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✓  Résultats sauvegardés → {OUTPUT}")

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
  python scripts/collect_paper_data.py --phase tour --host 192.168.20.22 --tour-trials 3
        """,
    )
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"IP rosbridge et backend (défaut: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT,
                        help=f"Port HTTP du backend CYBEL (défaut: {DEFAULT_BACKEND_PORT})")
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
