#!/usr/bin/env python3
"""Circulation en boucle entre POI (journée d'intégration, bâtiment Ghandi).

Pilotée depuis le PC, sans câble : rosbridge du châssis (10.42.0.1:9090) pour le
mouvement, backend de la tête (Wi-Fi, port 8001) pour l'état, les coordonnées des
POI et les annonces vocales. Même chaîne de navigation que la campagne
d'ablation (scripts/ablate_preparation.py, 20/20 le 2026-09-09) : annulation,
attente d'un état prêt, appel /poi, et succès jugé sur la POSITION FINALE —
jamais sur l'acquittement (H4).

Garde-fous, vérifiés avant chaque trajet :
  - arrêt d'urgence (physique ou logiciel) enclenché  -> fin de la circulation ;
  - localisation sous le seuil                         -> fin (relocaliser avec
    Deployment Tool, pas d'ici : la relocalisation fait tourner le robot) ;
  - batterie sous le seuil                             -> retour au point de
    charge, puis fin ;
  - robot qui ne progresse pas (but acquitté, robot immobile) -> une nouvelle
    tentative, puis échec du trajet ; deux trajets ratés d'affilée -> fin.

Arrêt propre : Ctrl+C, ou créer le fichier d'arrêt (--stop-file) depuis un autre
terminal. Dans tous les cas le robot reçoit une annulation en sortie. Si le
Wi-Fi tombe, le robot finit au plus son trajet en cours puis s'arrête : aucun
nouveau but ne lui est envoyé.

    python scripts/circulation.py --dry-run                        # vérifie, ne bouge pas
    python scripts/circulation.py --cycles 1                       # un aller-retour
    python scripts/circulation.py --stops POINT-ECRAN,POINT-HALL --announce
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    import websockets
except ImportError:
    sys.exit("Dépendance manquante : pip install websockets")

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "data" / "logs"
DEFAULT_STOP_FILE = LOG_DIR / "circulation.stop"

READY, ARRIVED, ERROR = 601, 603, 604
ARRIVAL_RADIUS_M = 0.80     # même critère que la campagne d'ablation
LEG_TIMEOUT_S = 180.0       # ~16 m entre les deux POI actuels ; 9 m prenaient ~40 s
PROGRESS_WINDOW_S = 20.0    # but acquitté mais robot immobile depuis 20 s -> non exécuté
PROGRESS_MIN_M = 0.30
MAX_FAILED_LEGS = 2


class Telemetry:
    """État châssis, lu en continu sur rosbridge."""

    def __init__(self) -> None:
        self.nav = -1
        self.pose: dict | None = None

    def update(self, msg: dict) -> None:
        if msg.get("topic") == "/robot_status":
            self.nav = msg["msg"].get("nav_status", self.nav)
        elif msg.get("topic") == "/robot_pose":
            self.pose = msg["msg"]

    def dist(self, point: dict) -> float | None:
        if not self.pose:
            return None
        return math.hypot(self.pose["x"] - point["x"], self.pose["y"] - point["y"])


class Circulation:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.tel = Telemetry()
        self.ws = None
        self.points: dict[str, dict] = {}
        self.log_path = LOG_DIR / f"circulation_{datetime.now():%Y%m%d}.jsonl"
        self.stop_file = Path(args.stop_file)

    # ---- journal ---------------------------------------------------------
    def log(self, event: str, **data) -> None:
        line = {"at": datetime.now().isoformat(timespec="seconds"), "event": event, **data}
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        details = " ".join(f"{k}={v}" for k, v in data.items())
        print(f"[{line['at'][11:]}] {event} {details}", flush=True)

    # ---- backend tête (HTTP Wi-Fi) ----------------------------------------
    def http(self, path: str, body: dict | None = None, timeout: float = 10.0) -> dict:
        url = self.args.backend.rstrip("/") + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data, method="POST" if body is not None else "GET",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def robot_status(self) -> dict:
        return self.http("/api/robot/status")

    def load_points(self) -> None:
        """Coordonnées des POI de la carte active, synchronisées par la tête."""
        sync = self.http("/api/navigation/sync", body={}, timeout=20)
        if not sync.get("ok"):
            raise RuntimeError(f"Sync POI échouée : {sync.get('error')}")
        self.points = {p["name"]: p for p in sync["points"]}

    def announce(self) -> None:
        if not self.args.announce:
            return
        try:
            result = self.http("/api/event/announce/say", body={}, timeout=60)
            self.log("annonce", texte=result.get("text", result.get("error")))
        except Exception as exc:  # une annonce ratée n'arrête pas la circulation
            self.log("annonce_echec", erreur=exc)

    # ---- rosbridge ---------------------------------------------------------
    async def send(self, msg: dict) -> None:
        await self.ws.send(json.dumps(msg))

    async def fire(self, service: str, args: dict) -> None:
        await self.send({"op": "call_service", "id": f"c{int(time.time() * 1000)}",
                         "service": service, "args": args})

    async def pump(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            try:
                self.tel.update(json.loads(await asyncio.wait_for(self.ws.recv(), timeout=0.3)))
            except (asyncio.TimeoutError, TimeoutError):
                continue

    async def cancel_all(self) -> None:
        for svc in ("/move_base/cancel", "/path_follower/cancel"):
            try:
                await self.fire(svc, {})
            except Exception:
                pass
        await asyncio.sleep(0.4)

    async def prepare(self) -> int:
        """Purge l'état bloquant et attend un état prêt (séquence de l'ablation)."""
        await self.cancel_all()
        end = time.time() + 12
        while time.time() < end:
            await self.pump(0.5)
            if self.tel.nav in (READY, ARRIVED):
                break
        return self.tel.nav

    async def travel(self, point: dict) -> tuple[bool, str, float]:
        """Attend l'arrivée à la POSITION du POI. (arrivé, raison, durée)."""
        t0 = time.time()
        best = self.tel.dist(point)
        best_at = t0
        while time.time() - t0 < LEG_TIMEOUT_S:
            if self.stop_requested():
                return False, "arret_demande", time.time() - t0
            try:
                self.tel.update(json.loads(await asyncio.wait_for(self.ws.recv(), timeout=0.5)))
            except (asyncio.TimeoutError, TimeoutError):
                pass
            d = self.tel.dist(point)
            if d is None:
                continue
            if d <= ARRIVAL_RADIUS_M:
                return True, "arrive", time.time() - t0
            if self.tel.nav == ERROR:
                return False, "nav_status_604", time.time() - t0
            if best is None or d < best - PROGRESS_MIN_M:
                best, best_at = d, time.time()
            elif time.time() - best_at > PROGRESS_WINDOW_S:
                # Le piège H4 : but acquitté, robot immobile.
                return False, "aucune_progression", time.time() - t0
        return False, "delai_depasse", time.time() - t0

    # ---- garde-fous ---------------------------------------------------------
    def stop_requested(self) -> bool:
        return self.stop_file.exists()

    def check_safety(self) -> str | None:
        """Raison d'arrêter la circulation, ou None si le trajet suivant peut partir."""
        st = self.robot_status()
        if not st.get("connected"):
            return "châssis non connecté"
        if st.get("hard_estop") or st.get("soft_estop"):
            return "arrêt d'urgence enclenché"
        if st.get("localization_percent", 0) < self.args.min_localization:
            return (f"localisation {st.get('localization_percent')} % "
                    f"< {self.args.min_localization} % — relocaliser avec Deployment Tool")
        return None

    def battery_low(self) -> bool:
        return self.robot_status().get("battery", 100) < self.args.battery_min

    # ---- trajets --------------------------------------------------------------
    async def leg(self, name: str) -> bool:
        point = self.points[name]
        for attempt in (1, 2):
            nav_before = await self.prepare()
            d0 = self.tel.dist(point)
            self.log("depart", vers=name, tentative=attempt, nav=nav_before,
                     distance_m=round(d0, 2) if d0 is not None else None)
            await self.fire("/poi", {"poi": name})
            ok, reason, dur = await self.travel(point)
            d1 = self.tel.dist(point)
            self.log("arrivee" if ok else "echec_trajet", vers=name, raison=reason,
                     duree_s=round(dur, 1), nav=self.tel.nav,
                     distance_m=round(d1, 2) if d1 is not None else None)
            if ok or reason == "arret_demande":
                return ok
            await self.cancel_all()
        return False

    async def dwell(self) -> None:
        end = time.time() + self.args.dwell
        while time.time() < end and not self.stop_requested():
            await self.pump(1.0)

    async def run(self) -> int:
        self.load_points()
        missing = [s for s in self.args.stops if s not in self.points]
        if missing or self.args.return_point not in self.points:
            print(f"POI absents de la carte active : {missing or [self.args.return_point]}")
            print(f"POI disponibles : {sorted(self.points)}")
            return 2
        if self.stop_file.exists():
            self.stop_file.unlink()

        url = f"ws://{self.args.host}:{self.args.port}"
        async with websockets.connect(url, open_timeout=12, ping_interval=None) as ws:
            self.ws = ws
            for topic in ("/robot_status", "/robot_pose"):
                await self.send({"op": "subscribe", "topic": topic, "throttle_rate": 200})
            await self.pump(2.0)
            if self.tel.nav == -1 or self.tel.pose is None:
                print("Télémétrie châssis absente. Abandon.")
                return 2

            st = self.robot_status()
            self.log("demarrage", arrets=",".join(self.args.stops), nav=self.tel.nav,
                     batterie=st.get("battery"), localisation=st.get("localization_percent"),
                     pose=f"({self.tel.pose['x']:.2f},{self.tel.pose['y']:.2f})")
            reason = self.check_safety()
            if reason:
                self.log("refus", raison=reason)
                return 1
            if self.args.dry_run:
                print("--dry-run : conditions vérifiées, aucun mouvement demandé.")
                return 0

            failed = 0
            cycle = 0
            try:
                while not self.args.cycles or cycle < self.args.cycles:
                    cycle += 1
                    self.log("cycle", numero=cycle)
                    for name in self.args.stops:
                        if self.stop_requested():
                            self.log("fin", raison="arrêt demandé")
                            return 0
                        reason = self.check_safety()
                        if reason:
                            self.log("fin", raison=reason)
                            return 1
                        if self.battery_low():
                            self.log("batterie_basse", retour=self.args.return_point)
                            await self.leg(self.args.return_point)
                            self.log("fin", raison="batterie basse")
                            return 0
                        if await self.leg(name):
                            failed = 0
                            self.announce()
                            await self.dwell()
                        else:
                            failed += 1
                            if failed >= MAX_FAILED_LEGS:
                                self.log("fin", raison=f"{failed} trajets ratés d'affilée")
                                return 1
                self.log("fin", raison=f"{cycle} cycle(s) terminés")
                return 0
            finally:
                await self.cancel_all()
                print("Annulation envoyée, robot arrêté.", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="10.42.0.1", help="rosbridge du châssis")
    ap.add_argument("--port", type=int, default=9090)
    ap.add_argument("--backend", default="http://172.16.2.138:8001",
                    help="backend Termux de la tête (adresse Wi-Fi, peut changer : DHCP)")
    ap.add_argument("--stops", default="POINT-CHARGE,POINT-ECRAN",
                    help="POI visités dans l'ordre, séparés par des virgules")
    ap.add_argument("--return-point", default="POINT-CHARGE")
    ap.add_argument("--dwell", type=float, default=20.0, help="pause à chaque arrêt (s)")
    ap.add_argument("--cycles", type=int, default=0, help="0 = jusqu'à l'arrêt")
    ap.add_argument("--battery-min", type=int, default=25)
    ap.add_argument("--min-localization", type=float, default=60.0)
    ap.add_argument("--announce", action="store_true",
                    help="annonce vocale (mode événement) à chaque arrivée")
    ap.add_argument("--stop-file", default=str(DEFAULT_STOP_FILE))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.stops = [s.strip() for s in args.stops.split(",") if s.strip()]

    try:
        code = asyncio.run(Circulation(args).run())
    except KeyboardInterrupt:
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()
