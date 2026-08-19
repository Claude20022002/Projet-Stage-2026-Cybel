#!/usr/bin/env python3
"""Test unitaire : une seule navigation par annotation (POI), avec preuve de mouvement.

À lancer AVANT toute campagne longue, pour vérifier que le service répond et
que le robot bouge réellement. Un essai coûte une minute ; une campagne de
vingt essais en coûte quarante.

Contexte. Les campagnes de juillet et du 19 août ont mesuré 0 succès en S3.
L'introspection a montré pourquoi :

  /rosapi/service_type("/tag_manager/navi")  -> type vide, service inexistant
  /rosapi/service_type("/poi")               -> yutong_assistance/poi
  /rosapi/service_request_details(...)       -> un seul champ : poi (string)

Le script de collecte appelait un service absent, puis /poi avec trois champs
dont aucun n'était `poi`. Il ne mesurait donc pas la réutilisation des
annotations, mais un appel malformé.

Usage :
    python scripts/test_poi_nav.py                       # cible CNC ROUTEUR
    python scripts/test_poi_nav.py --poi "PORTE-LABO"
    python scripts/test_poi_nav.py --list                # liste les POI du châssis
    python scripts/test_poi_nav.py --dry-run             # vérifie sans bouger

Le robot est TOUJOURS arrêté en sortie, y compris sur Ctrl+C ou erreur.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time

try:
    import websockets
except ImportError:
    sys.exit("Dépendance manquante : pip install websockets")

DEFAULT_HOST = "10.42.0.1"
DEFAULT_PORT = 9090
DEFAULT_POI = "CNC ROUTEUR"

NAV_TIMEOUT = 90.0          # s, abandon si le robot n'arrive pas
ARRIVED, READY, MOVING = 603, 601, 602
MOVE_THRESHOLD_M = 0.10     # déplacement minimal pour parler de mouvement réel

CANCEL_SERVICES = ["/move_base/cancel", "/path_follower/cancel"]


async def call(ws, service: str, args: dict | None = None, timeout: float = 10.0) -> dict:
    """Appel de service qui attend sa réponse, en ignorant la télémétrie."""
    rid = f"t_{int(time.time() * 1000)}"
    await ws.send(json.dumps({"op": "call_service", "id": rid,
                              "service": service, "args": args or {}}))
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        try:
            d = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
        except (asyncio.TimeoutError, TimeoutError):
            continue
        if d.get("op") == "service_response" and d.get("service") == service:
            return d
    return {}


async def fire(ws, service: str, args: dict) -> None:
    """Envoi sans attendre la réponse : la télémétrie doit rester lisible."""
    await ws.send(json.dumps({"op": "call_service",
                              "id": f"f_{int(time.time() * 1000)}",
                              "service": service, "args": args}))


async def stop_everything(ws) -> None:
    """Annulation inconditionnelle. Appelée dans tous les cas de sortie."""
    for svc in CANCEL_SERVICES:
        try:
            await fire(ws, svc, {})
        except Exception:
            pass
    await asyncio.sleep(0.3)


async def list_pois(ws) -> list[str]:
    r = await call(ws, "/marker_manager/get_markers_brief")
    return [m.get("name", "") for m in r.get("values", {}).get("markers_brief", [])]


async def check_service(ws) -> tuple[bool, str]:
    r = await call(ws, "/rosapi/service_type", {"service": "/poi"})
    stype = r.get("values", {}).get("type", "")
    if not stype:
        return False, "/poi : type vide — le service n'existe pas sur ce firmware"
    d = await call(ws, "/rosapi/service_request_details", {"type": stype})
    fields: list[str] = []
    for td in d.get("values", {}).get("typedefs", []):
        if td.get("type", "").endswith("Request"):
            fields = td.get("fieldnames", [])
    if fields != ["poi"]:
        return False, f"/poi attend {fields}, or nous envoyons {{'poi': ...}}"
    return True, f"/poi : {stype}, champ unique 'poi' — conforme"


async def run(host: str, port: int, poi: str, dry_run: bool, do_list: bool) -> int:
    url = f"ws://{host}:{port}"
    print(f"Connexion {url} ...")
    async with websockets.connect(url, open_timeout=12, ping_interval=None) as ws:
        print("[OK] connecté\n")

        names = await list_pois(ws)
        if do_list:
            print(f"POI déclarés sur le châssis ({len(names)}) :")
            for n in names:
                print(f"  - {n}")
            return 0

        ok, msg = await check_service(ws)
        print(f"1. Signature du service\n   {msg}")
        if not ok:
            return 2

        print(f"\n2. Annotation cible\n   « {poi} » "
              f"{'trouvée' if poi in names else 'ABSENTE du châssis'}")
        if poi not in names:
            print(f"   POI disponibles : {', '.join(names)}")
            return 2

        # On suit /robot_status, pas /navi_status. Les deux topics existent et
        # ne parlent PAS le même langage : /navi_status porte les codes
        # actionlib de move_base (1 = ACTIVE, 3 = SUCCEEDED), alors que les
        # codes 601/602/603 du constructeur vivent dans le champ nav_status de
        # /robot_status. Confondre les deux fait manquer l'arrivée.
        await ws.send(json.dumps({"op": "subscribe", "topic": "/robot_pose",
                                  "type": "geometry_msgs/Pose2D", "throttle_rate": 200}))
        await ws.send(json.dumps({"op": "subscribe", "topic": "/robot_status",
                                  "throttle_rate": 300}))
        await asyncio.sleep(1.0)

        pose0, status0 = None, None
        end = time.time() + 4
        while time.time() < end and (pose0 is None or status0 is None):
            try:
                d = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            except (asyncio.TimeoutError, TimeoutError):
                continue
            if d.get("topic") == "/robot_pose":
                pose0 = d["msg"]
            elif d.get("topic") == "/robot_status":
                status0 = d["msg"]

        nav0 = (status0 or {}).get("nav_status")
        print(f"\n3. État initial\n   pose {pose0}\n   nav_status {nav0}"
              f"   (but courant : {(status0 or {}).get('current_goal_name')})")

        if dry_run:
            print("\n--dry-run : aucun mouvement demandé. Tout est conforme.")
            return 0

        print(f"\n4. Appel  /poi  {{'poi': '{poi}'}}")
        t0 = time.time()
        await fire(ws, "/poi", {"poi": poi})

        seen_moving = False
        code = -1
        last_pose = pose0
        try:
            while time.time() - t0 < NAV_TIMEOUT:
                try:
                    d = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
                except (asyncio.TimeoutError, TimeoutError):
                    continue
                if d.get("topic") == "/robot_pose":
                    last_pose = d["msg"]
                elif d.get("topic") == "/robot_status":
                    new = d["msg"].get("nav_status", -1)
                    if new != code:
                        code = new
                        print(f"   t+{time.time()-t0:5.1f}s  nav_status -> {code}")
                    if code == MOVING:
                        seen_moving = True
                    # Le robot peut déjà être à destination : on n'exige la
                    # transition 602 que si un déplacement reste à faire.
                    if code == ARRIVED and (seen_moving or time.time() - t0 > 8):
                        break
        finally:
            await stop_everything(ws)

        elapsed = time.time() - t0
        dist = 0.0
        if pose0 and last_pose:
            dist = math.hypot(last_pose["x"] - pose0["x"], last_pose["y"] - pose0["y"])

        print(f"\n5. Résultat")
        print(f"   durée            {elapsed:.1f} s")
        print(f"   navi_status final {code}")
        print(f"   transition 602 vue {'oui' if seen_moving else 'NON'}")
        print(f"   déplacement       {dist:.2f} m")

        moved = dist > MOVE_THRESHOLD_M
        if code == ARRIVED and moved:
            print("\n   >> SUCCÈS : le service répond ET le robot s'est déplacé.")
            print("      La campagne peut être relancée.")
            return 0
        if moved and not seen_moving:
            print("\n   >> Le robot a bougé mais aucune transition 602 n'a été vue.")
            print("      Probable artefact de mesure, pas un échec de navigation.")
            return 1
        print("\n   >> ÉCHEC : aucun mouvement. Ne pas lancer la campagne.")
        print("      Vérifier localisation ≥ 60 %, mode automatique, arrêt d'urgence.")
        return 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--poi", default=DEFAULT_POI)
    ap.add_argument("--list", action="store_true", help="lister les POI et sortir")
    ap.add_argument("--dry-run", action="store_true",
                    help="tout vérifier sans déplacer le robot")
    a = ap.parse_args()
    try:
        sys.exit(asyncio.run(run(a.host, a.port, a.poi, a.dry_run, a.list)))
    except KeyboardInterrupt:
        print("\nInterrompu — le robot a reçu l'ordre d'annulation.")
        sys.exit(130)


if __name__ == "__main__":
    main()
