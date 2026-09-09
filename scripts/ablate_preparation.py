#!/usr/bin/env python3
"""Ablation : la séquence de préparation est-elle nécessaire, ou seulement présente ?

L'article affirme que ce qui sépare une intégration qui fonctionne d'un script
rapportant un succès sans rien déplacer, c'est la séquence de préparation.
C'est une affirmation ; ceci la mesure.

  Bras A (préparé)    : annulation, attente d'un état prêt, puis le but
  Bras B (non préparé): le but, directement

Les deux bras émettent le même appel /poi vers la même cible, depuis la même
position de départ. Seule la préparation les sépare.

DEUX LEÇONS DE LA PREMIÈRE VERSION, qui déclarait tout en échec :

1. Le succès se juge sur la POSITION FINALE, pas sur un code d'état. La mesure
   du 2026-09-09 (scripts/probe_nav_states.py, 4 essais) montre que pendant une
   navigation par POI, nav_status peut rester à 601 du début à la fin sans
   jamais passer par 602 — rarement observable, donc, pas absente : la
   campagne d'ablation menée le même jour (10 essais par bras, ci-dessous) a
   vu 602 apparaître dans 19 des 20 trajets. Dans les deux cas, un critère
   fondé sur l'apparition de 602 est trop fragile pour juger un essai.

2. La position de départ est vérifiée avant chaque essai, elle n'est pas
   supposée. Un essai qui ne part pas du point de retrait est écarté plutôt que
   compté, car il ne mesure pas la même chose que les autres.

    python scripts/ablate_preparation.py --host 10.42.0.1 --trials 10
    python scripts/ablate_preparation.py --dry-run     # vérifie sans bouger

Le robot est arrêté en sortie, y compris sur Ctrl+C ou erreur.
Résultats écrits après chaque essai : data/ablation_preparation.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import websockets
except ImportError:
    sys.exit("Dépendance manquante : pip install websockets")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ablation_preparation.json"

TARGET_NAME = "CNC ROUTEUR"
START_NAME = "EXTRUSION-SOUFFLAGE"

NAV_TIMEOUT = 90.0          # s, un trajet de 9 m en prend ~40
ARRIVAL_RADIUS_M = 0.80     # rayon d'arrivée, verité terrain
START_RADIUS_M = 1.20       # tolérance sur la position de départ
SETTLE = 4.0

READY, ARRIVED, ERROR = 601, 603, 604


def load_point(name: str) -> dict:
    pts = json.loads((ROOT / "data" / "points.json").read_text(encoding="utf-8"))["points"]
    p = next((x for x in pts if x["name"] == name), None)
    if not p:
        sys.exit(f"POI inconnu : {name}")
    return p


class State:
    def __init__(self) -> None:
        self.nav = -1
        self.pose: dict | None = None
        self.seen_codes: set[int] = set()

    def update(self, msg: dict) -> None:
        if msg.get("topic") == "/robot_status":
            self.nav = msg["msg"].get("nav_status", self.nav)
            self.seen_codes.add(self.nav)
        elif msg.get("topic") == "/robot_pose":
            self.pose = msg["msg"]

    def dist(self, goal: dict) -> float | None:
        if not self.pose:
            return None
        return math.hypot(self.pose["x"] - goal["x"], self.pose["y"] - goal["y"])


async def send(ws, msg: dict) -> None:
    await ws.send(json.dumps(msg))


async def fire(ws, service: str, args: dict) -> None:
    await send(ws, {"op": "call_service", "id": f"f{int(time.time()*1000)}",
                    "service": service, "args": args})


async def pump(ws, st: State, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            st.update(json.loads(await asyncio.wait_for(ws.recv(), timeout=0.3)))
        except (asyncio.TimeoutError, TimeoutError):
            continue


async def cancel_all(ws) -> None:
    for svc in ("/move_base/cancel", "/path_follower/cancel"):
        try:
            await fire(ws, svc, {})
        except Exception:
            pass
    await asyncio.sleep(0.4)


async def prepare(ws, st: State) -> int:
    """Purge l'état bloquant et attend un état prêt. Retourne l'état atteint."""
    await cancel_all(ws)
    end = time.time() + 12
    while time.time() < end:
        await pump(ws, st, 0.5)
        if st.nav in (READY, ARRIVED):
            break
    return st.nav


async def travel(ws, st: State, goal: dict, timeout: float = NAV_TIMEOUT
                 ) -> tuple[bool, float, float, int]:
    """Attend l'arrivée à la POSITION du but. (arrivé, durée, distance, code)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            st.update(json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5)))
        except (asyncio.TimeoutError, TimeoutError):
            continue
        d = st.dist(goal)
        if d is not None and d <= ARRIVAL_RADIUS_M:
            return True, time.time() - t0, d, st.nav
        if st.nav == ERROR:
            break
    d = st.dist(goal)
    return False, time.time() - t0, (d if d is not None else -1.0), st.nav


async def go_to_start(ws, st: State, start: dict) -> bool:
    """Ramène le robot au point de départ, toujours préparé. Vérifié par position."""
    d = st.dist(start)
    if d is not None and d <= START_RADIUS_M:
        return True
    await prepare(ws, st)
    await fire(ws, "/poi", {"poi": START_NAME})
    ok, _, _, _ = await travel(ws, st, start)
    return ok


async def trial(ws, st: State, arm: str, idx: int, target: dict, start: dict) -> dict | None:
    print(f"    {arm} essai {idx:2d} ... ", end="", flush=True)

    if not await go_to_start(ws, st, start):
        print("ECARTE (position de depart non atteinte)")
        return None

    st.seen_codes.clear()
    nav_before = st.nav
    d_before = st.dist(target)

    if arm == "A":
        await prepare(ws, st)
    nav_at_goal = st.nav

    await fire(ws, "/poi", {"poi": TARGET_NAME})
    arrived, dur, d_final, nav_final = await travel(ws, st, target)

    print(f"{'OK   ' if arrived else 'ECHEC'} {dur:5.1f}s  "
          f"dist {d_before:.1f} -> {d_final:.2f} m  "
          f"nav {nav_before}->{nav_final}  vus {sorted(st.seen_codes)}")
    return {"arm": arm, "trial": idx, "success": arrived,
            "elapsed_s": round(dur, 1),
            "distance_start_m": round(d_before, 2) if d_before is not None else None,
            "distance_final_m": round(d_final, 2),
            "nav_before": nav_before, "nav_at_goal": nav_at_goal,
            "nav_final": nav_final, "nav_codes_seen": sorted(st.seen_codes)}


def save(results: list[dict], planned: int) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "target": TARGET_NAME, "start": START_NAME,
        "arrival_radius_m": ARRIVAL_RADIUS_M,
        "criterion": "final pose within arrival_radius_m of the target coordinates",
        "trials_planned": planned, "trials_done": len(results),
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def report(results: list[dict]) -> None:
    print("\n" + "=" * 66)
    for arm, label in (("A", "avec preparation"), ("B", "sans preparation")):
        r = [x for x in results if x["arm"] == arm]
        if not r:
            continue
        ok = sum(1 for x in r if x["success"])
        times = [x["elapsed_s"] for x in r if x["success"]]
        med = sorted(times)[len(times) // 2] if times else float("nan")
        print(f"  Bras {arm} ({label}) : {ok}/{len(r)}   mediane {med:.1f}s")
    print("=" * 66)
    print(f"Resultats : {OUT}")


async def run(host: str, port: int, trials: int, dry: bool) -> int:
    target, start = load_point(TARGET_NAME), load_point(START_NAME)
    sep = math.hypot(target["x"] - start["x"], target["y"] - start["y"])
    url = f"ws://{host}:{port}"
    print(f"Connexion {url} ...")
    async with websockets.connect(url, open_timeout=12, ping_interval=None) as ws:
        st = State()
        for t in ("/robot_status", "/robot_pose"):
            await send(ws, {"op": "subscribe", "topic": t, "throttle_rate": 200})
        await pump(ws, st, 2.0)
        if st.nav == -1 or st.pose is None:
            print("Telemetrie absente. Abandon."); return 2
        print(f"[OK] nav_status {st.nav}, pose ({st.pose['x']:.2f}, {st.pose['y']:.2f})")
        print(f"     {START_NAME} -> {TARGET_NAME} : {sep:.2f} m")
        print(f"     succes = pose finale a moins de {ARRIVAL_RADIUS_M} m de la cible")

        if dry:
            print("\n--dry-run : conditions verifiees, aucun mouvement demande.")
            return 0

        results: list[dict] = []
        try:
            for i in range(1, trials + 1):
                for arm in ("A", "B"):
                    r = await trial(ws, st, arm, i, target, start)
                    if r:
                        results.append(r)
                        save(results, trials * 2)
                    await cancel_all(ws)
                    await asyncio.sleep(SETTLE)
        finally:
            await cancel_all(ws)
            print("\nAnnulation envoyee, robot arrete.")

        save(results, trials * 2)
        report(results)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="10.42.0.1")
    ap.add_argument("--port", type=int, default=9090)
    ap.add_argument("--trials", type=int, default=10, help="essais PAR BRAS")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    try:
        sys.exit(asyncio.run(run(a.host, a.port, a.trials, a.dry_run)))
    except KeyboardInterrupt:
        print("\nInterrompu — une annulation a ete envoyee au robot.")
        sys.exit(130)


if __name__ == "__main__":
    main()
