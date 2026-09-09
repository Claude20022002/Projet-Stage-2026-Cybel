#!/usr/bin/env python3
"""Ablation : la séquence de préparation est-elle nécessaire, ou seulement présente ?

L'article affirme que ce qui sépare une intégration qui fonctionne d'un script
qui rapporte un succès sans rien déplacer, c'est la séquence de préparation :
vérifier l'état de contrôle, purger les états bloquants, relocaliser si besoin.
C'est une affirmation, pas encore une mesure.

CONCEPTION. Comparer « avec » et « sans » préparation sur un robot déjà dans un
bon état ne montrerait rien : la préparation ne sert que lorsque l'état est
défavorable. On induit donc un état défavorable identique dans les deux bras,
puis on mesure si la préparation le rattrape.

L'état défavorable choisi est « navigation déjà en cours » (nav_status 602),
obtenu en lançant un premier but vers le point de retrait puis en émettant
immédiatement le but mesuré. C'est l'un des quatre cas que la séquence de
préparation traite, et il s'obtient sans deviner aucun argument : tous les
appels utilisés ici ont été validés par introspection.

  Bras A (préparé)   : perturbation -> annulation + attente d'un état prêt -> but
  Bras B (non préparé): perturbation -> but directement

Un échec du bras B avec nav_status figé à 601/602 démontre la nécessité.

    python scripts/ablate_preparation.py --host 10.42.0.1 --trials 10
    python scripts/ablate_preparation.py --dry-run      # verifie sans bouger

Le robot est arrêté en sortie, y compris sur Ctrl+C ou erreur.
Résultats : data/ablation_preparation.json
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

TARGET = "CNC ROUTEUR"
WITHDRAW = "EXTRUSION-SOUFFLAGE"
NAV_TIMEOUT = 90.0
SETTLE = 5.0

READY, MOVING, ARRIVED, ERROR = 601, 602, 603, 604


async def send(ws, msg: dict) -> None:
    await ws.send(json.dumps(msg))


async def fire(ws, service: str, args: dict) -> None:
    """Appel sans attendre la réponse : la télémétrie doit rester lisible."""
    await send(ws, {"op": "call_service", "id": f"f{int(time.time()*1000)}",
                    "service": service, "args": args})


async def drain(ws, seconds: float = 0.4) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            await asyncio.wait_for(ws.recv(), timeout=0.15)
        except (asyncio.TimeoutError, TimeoutError):
            return


class State:
    """Dernier état connu, alimenté par /robot_status et /robot_pose."""

    def __init__(self) -> None:
        self.nav = -1
        self.pose = None

    def update(self, msg: dict) -> None:
        if msg.get("topic") == "/robot_status":
            self.nav = msg["msg"].get("nav_status", self.nav)
        elif msg.get("topic") == "/robot_pose":
            self.pose = msg["msg"]


async def pump(ws, st: State, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            st.update(json.loads(await asyncio.wait_for(ws.recv(), timeout=0.3)))
        except (asyncio.TimeoutError, TimeoutError):
            continue


async def wait_nav(ws, st: State, timeout: float) -> tuple[int, bool, float]:
    """Attend l'arrivée. Retourne (code final, transition 602 vue, durée)."""
    t0 = time.time()
    saw_moving = False
    while time.time() - t0 < timeout:
        try:
            st.update(json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5)))
        except (asyncio.TimeoutError, TimeoutError):
            continue
        if st.nav == MOVING:
            saw_moving = True
        if st.nav == ARRIVED and saw_moving:
            return st.nav, saw_moving, time.time() - t0
        if st.nav == ERROR:
            return st.nav, saw_moving, time.time() - t0
    return st.nav, saw_moving, time.time() - t0


async def cancel_all(ws) -> None:
    for svc in ("/move_base/cancel", "/path_follower/cancel"):
        try:
            await fire(ws, svc, {})
        except Exception:
            pass
    await asyncio.sleep(0.4)


async def prepare(ws, st: State) -> None:
    """Séquence de préparation : purge l'état bloquant, attend un état prêt."""
    await cancel_all(ws)
    end = time.time() + 12
    while time.time() < end:
        await pump(ws, st, 0.5)
        if st.nav in (READY, ARRIVED):
            return
    # on n'attend pas indéfiniment : l'état est rapporté tel quel dans le résultat


async def goto(ws, st: State, poi: str, timeout: float = NAV_TIMEOUT) -> bool:
    """Déplacement utilitaire (retrait), toujours préparé."""
    await prepare(ws, st)
    await fire(ws, "/poi", {"poi": poi})
    code, moving, _ = await wait_nav(ws, st, timeout)
    return code == ARRIVED and moving


async def trial(ws, st: State, arm: str, idx: int) -> dict:
    """Un essai : perturbation identique, puis but avec ou sans préparation."""
    print(f"    {arm} essai {idx:2d} ... ", end="", flush=True)
    p0 = dict(st.pose) if st.pose else None

    # --- perturbation commune : une navigation est lancée puis on enchaîne ---
    await drain(ws)
    await fire(ws, "/poi", {"poi": WITHDRAW})
    await pump(ws, st, 4.0)            # laisse le robot passer en 602
    perturbed = st.nav

    # --- le bras diffère ici, et seulement ici ------------------------------
    if arm == "A":
        await prepare(ws, st)
    nav_before = st.nav
    await fire(ws, "/poi", {"poi": TARGET})
    code, moving, dur = await wait_nav(ws, st, NAV_TIMEOUT)

    dist = 0.0
    if p0 and st.pose:
        dist = math.hypot(st.pose["x"] - p0["x"], st.pose["y"] - p0["y"])
    ok = code == ARRIVED and moving

    print(f"{'OK ' if ok else 'ECHEC'}  nav={code} 602vu={'oui' if moving else 'NON'} "
          f"{dur:5.1f}s  {dist:.2f} m")
    return {"arm": arm, "trial": idx, "success": ok, "nav_final": code,
            "saw_moving": moving, "elapsed_s": round(dur, 1),
            "distance_m": round(dist, 2), "nav_perturbed": perturbed,
            "nav_before_goal": nav_before}


async def run(host: str, port: int, trials: int, dry: bool) -> int:
    url = f"ws://{host}:{port}"
    print(f"Connexion {url} ...")
    async with websockets.connect(url, open_timeout=12, ping_interval=None) as ws:
        st = State()
        for t in ("/robot_status", "/robot_pose"):
            await send(ws, {"op": "subscribe", "topic": t, "throttle_rate": 250})
        await pump(ws, st, 2.0)
        print(f"[OK] connecté — nav_status {st.nav}, pose {st.pose}")

        if st.nav == -1:
            print("Aucune télémétrie reçue. Abandon."); return 2
        if dry:
            print("\n--dry-run : conditions vérifiées, aucun mouvement demandé.")
            return 0

        results: list[dict] = []
        try:
            for i in range(1, trials + 1):
                for arm in ("A", "B"):
                    results.append(await trial(ws, st, arm, i))
                    await cancel_all(ws)
                    await asyncio.sleep(SETTLE)
                    # remise en position de départ, toujours préparée
                    await goto(ws, st, WITHDRAW)
                    save(results, trials)
        finally:
            await cancel_all(ws)
            print("\nAnnulation envoyée, robot arrêté.")

        save(results, trials)
        report(results)
    return 0


def save(results: list[dict], trials: int) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "target": TARGET, "withdraw": WITHDRAW,
        "trials_planned": trials, "trials_done": len(results),
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def report(results: list[dict]) -> None:
    print("\n" + "=" * 62)
    for arm, label in (("A", "avec préparation"), ("B", "sans préparation")):
        r = [x for x in results if x["arm"] == arm]
        if not r:
            continue
        ok = sum(1 for x in r if x["success"])
        codes = sorted({x["nav_final"] for x in r})
        print(f"  Bras {arm} ({label:17s}) : {ok}/{len(r)}  codes finaux {codes}")
    print("=" * 62)
    print(f"Résultats : {OUT}")


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
        print("\nInterrompu — une annulation a été envoyée au robot.")
        sys.exit(130)


if __name__ == "__main__":
    main()
