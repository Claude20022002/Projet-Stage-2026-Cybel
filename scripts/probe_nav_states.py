#!/usr/bin/env python3
"""Observe la machine à états pendant UNE navigation par POI.

Écrit avant de corriger l'ablation, parce que la première version supposait que
nav_status passe par 602 pendant un déplacement. Cette valeur n'a été lue dans
aucun des quatre essais d'origine — rarement observable, donc, pas absente :
la campagne d'ablation du 2026-09-09 (10 essais par bras) l'a vue passer par
602 dans la quasi-totalité des trajets. Plutôt que de redessiner la
perturbation sur une seconde hypothèse, on mesure ce que la machine fait
vraiment.

Journalise chaque changement d'état sur /robot_status et /navi_status, avec la
pose et la distance à la cible, pendant un aller simple.

    python scripts/probe_nav_states.py --poi "CNC ROUTEUR"

Le robot est arrêté en sortie, y compris sur Ctrl+C.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from pathlib import Path

try:
    import websockets
except ImportError:
    sys.exit("Dépendance manquante : pip install websockets")

ROOT = Path(__file__).resolve().parent.parent


def load_point(name: str) -> dict | None:
    pts = json.loads((ROOT / "data" / "points.json").read_text(encoding="utf-8"))["points"]
    return next((p for p in pts if p["name"] == name), None)


async def main_async(host: str, port: int, poi: str, seconds: float) -> int:
    target = load_point(poi)
    if not target:
        sys.exit(f"POI inconnu : {poi}")

    url = f"ws://{host}:{port}"
    print(f"Connexion {url} ...")
    async with websockets.connect(url, open_timeout=12, ping_interval=None) as ws:
        for t, rate in (("/robot_status", 100), ("/robot_pose", 100), ("/navi_status", 100)):
            await ws.send(json.dumps({"op": "subscribe", "topic": t, "throttle_rate": rate}))
        await asyncio.sleep(1.0)

        pose = None
        last = {}
        t0 = time.time()
        print(f"\nCible {poi} ({target['x']:.2f}, {target['y']:.2f})")
        print("Émission du but, puis journal des changements d'état.\n")
        print(f"  {'t+':>6s}  {'topic':16s} {'champ':12s} {'valeur':>8s}  {'dist':>6s}")

        await ws.send(json.dumps({"op": "call_service", "id": "go",
                                  "service": "/poi", "args": {"poi": poi}}))
        try:
            while time.time() - t0 < seconds:
                try:
                    d = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
                except (asyncio.TimeoutError, TimeoutError):
                    continue
                if d.get("op") != "publish":
                    continue
                topic, msg = d["topic"], d.get("msg", {})
                if topic == "/robot_pose":
                    pose = msg
                    continue
                dist = (math.hypot(pose["x"] - target["x"], pose["y"] - target["y"])
                        if pose else float("nan"))
                # on ne journalise que les CHANGEMENTS, sinon le flux est illisible
                for field in ("nav_status", "status", "nav_internal_status", "control_state"):
                    if field not in msg:
                        continue
                    key = f"{topic}.{field}"
                    if last.get(key) != msg[field]:
                        last[key] = msg[field]
                        print(f"  {time.time()-t0:6.1f}  {topic:16s} {field:12s} "
                              f"{str(msg[field]):>8s}  {dist:6.2f}")
                if pose and dist < 0.5:
                    print(f"\n  -> à moins de 0.5 m de la cible à t+{time.time()-t0:.1f}s")
                    break
        finally:
            for svc in ("/move_base/cancel", "/path_follower/cancel"):
                await ws.send(json.dumps({"op": "call_service", "id": "c",
                                          "service": svc, "args": {}}))
            await asyncio.sleep(0.3)
            print("\nAnnulation envoyée.")

        if pose:
            print(f"pose finale ({pose['x']:.2f}, {pose['y']:.2f})  "
                  f"distance à la cible {math.hypot(pose['x']-target['x'], pose['y']-target['y']):.2f} m")
        print("\nÉtats distincts observés :")
        for k, v in sorted(last.items()):
            print(f"  {k:34s} dernier = {v}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="10.42.0.1")
    ap.add_argument("--port", type=int, default=9090)
    ap.add_argument("--poi", default="CNC ROUTEUR")
    ap.add_argument("--seconds", type=float, default=90.0)
    a = ap.parse_args()
    try:
        sys.exit(asyncio.run(main_async(a.host, a.port, a.poi, a.seconds)))
    except KeyboardInterrupt:
        print("\nInterrompu."); sys.exit(130)


if __name__ == "__main__":
    main()
