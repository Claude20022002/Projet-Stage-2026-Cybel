#!/usr/bin/env python3
"""Capture et compare des inventaires rosapi, pour tester le critère d'arrêt de la phase 2.

L'article déclare aujourd'hui ne pas pouvoir vérifier ce critère : une session
antérieure avait compté 455 topics et 308 services, la session archivée en
compte 404 et 321, et faute d'inventaire archivé en juillet on ne peut pas dire
si le graphe varie réellement ou si le premier comptage était approximatif.

Deux comptes identiques ne prouveraient rien : 404 topics peuvent recouvrir des
ensembles différents. On compare donc les ENSEMBLES, et on rapporte ce qui
apparaît et disparaît entre deux captures.

    python scripts/inventory_stability.py --host 10.42.0.1 --label avant
    python scripts/inventory_stability.py --host 10.42.0.1 --label apres
    python scripts/inventory_stability.py --compare avant apres

Les captures vont dans data/inventories/<label>.json et sont conservées : ce
sont elles, et non un compte dans le texte, qui étayent l'affirmation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import websockets
except ImportError:
    sys.exit("Dépendance manquante : pip install websockets")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "inventories"


async def _call(ws, service: str, timeout: float = 10.0) -> dict:
    await ws.send(json.dumps({"op": "call_service", "id": service, "service": service}))
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        try:
            d = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
        except (asyncio.TimeoutError, TimeoutError):
            continue
        if d.get("op") == "service_response" and d.get("service") == service:
            return d.get("values", {})
    return {}


async def capture(host: str, port: int, label: str) -> dict:
    url = f"ws://{host}:{port}"
    print(f"Connexion {url} ...")
    async with websockets.connect(url, open_timeout=12, ping_interval=None) as ws:
        topics = sorted((await _call(ws, "/rosapi/topics")).get("topics", []))
        services = sorted((await _call(ws, "/rosapi/services")).get("services", []))
        nodes = sorted((await _call(ws, "/rosapi/nodes")).get("nodes", []))

    snap = {
        "label": label,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "robot_host": host,
        "topics_count": len(topics),
        "services_count": len(services),
        "nodes_count": len(nodes),
        "topics": topics,
        "services": services,
        "nodes": nodes,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{label}.json"
    path.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  topics {len(topics)}  services {len(services)}  nodes {len(nodes)}")
    print(f"  -> {path.relative_to(ROOT)}")
    return snap


def compare(label_a: str, label_b: str) -> int:
    pa, pb = OUT_DIR / f"{label_a}.json", OUT_DIR / f"{label_b}.json"
    for p in (pa, pb):
        if not p.exists():
            sys.exit(f"Capture absente : {p}")
    a = json.loads(pa.read_text(encoding="utf-8"))
    b = json.loads(pb.read_text(encoding="utf-8"))

    print(f"{'':22s} {label_a:>14s} {label_b:>14s}")
    for key in ("topics", "services", "nodes"):
        print(f"  {key:20s} {len(a[key]):>14d} {len(b[key]):>14d}")

    identical = True
    for key in ("topics", "services", "nodes"):
        sa, sb = set(a[key]), set(b[key])
        only_a, only_b = sorted(sa - sb), sorted(sb - sa)
        if not only_a and not only_b:
            print(f"\n{key}: ensembles IDENTIQUES ({len(sa)} entrées)")
            continue
        identical = False
        print(f"\n{key}: {len(sa & sb)} en commun, "
              f"{len(only_a)} seulement dans {label_a}, {len(only_b)} seulement dans {label_b}")
        for name in only_a[:12]:
            print(f"    - {name}")
        for name in only_b[:12]:
            print(f"    + {name}")

    print()
    if identical:
        print("VERDICT : inventaire stable entre les deux captures.")
        print("          Le critère d'arrêt de la phase 2 est vérifié sur cet intervalle.")
    else:
        print("VERDICT : l'inventaire varie. C'est un résultat, pas un échec —")
        print("          il faut alors dire dans l'article que le graphe dépend de l'état,")
        print("          et rapporter ce qui apparaît et disparaît.")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="10.42.0.1")
    ap.add_argument("--port", type=int, default=9090)
    ap.add_argument("--label", help="nom de la capture à enregistrer")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"), help="compare deux captures")
    a = ap.parse_args()

    if a.compare:
        sys.exit(compare(*a.compare))
    if not a.label:
        ap.error("indiquez --label pour capturer, ou --compare A B")
    asyncio.run(capture(a.host, a.port, a.label))


if __name__ == "__main__":
    main()
