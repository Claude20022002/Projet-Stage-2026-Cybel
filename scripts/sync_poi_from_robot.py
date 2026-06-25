#!/usr/bin/env python3
"""Synchronise les POI du robot (Sentrymove / marker_manager) vers data/points.json.

Usage (depuis la racine du dépôt, Wi-Fi robot) :

    python scripts/sync_poi_from_robot.py --host 192.168.20.22
    python scripts/sync_poi_from_robot.py --host 10.42.0.1 --dry-run
    python scripts/sync_poi_from_robot.py --host 192.168.20.22 \\
        --mark-kiosk "Routeur CNC,Station LG-10,Extraction et soufflage"

Voir docs/SENTRYMOVE_POI_SYNC.md pour la procédure complète.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk.poi_sync import sync_from_robot  # noqa: E402

DEFAULT_KIOSK_POIS = (
    "Routeur CNC",
    "Station LG-10",
    "Station LG-09",
    "Extraction et soufflage",
    "Poste remplissage et bouchonnage",
    "Thermoformage",
    "Imprimante DTF C31 XP600",
    "Sérigraphie",
)


def parse_mark_kiosk(raw: str | None) -> set[str] | None:
    if not raw:
        return set(DEFAULT_KIOSK_POIS)
    names = {part.strip() for part in raw.split(",") if part.strip()}
    return names or None


def print_summary(merged, summary: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"POI ROS lus        : {summary['ros_count']}")
    print(f"Total après fusion : {summary['total_count']}")
    print(f"Visibles kiosque   : {summary['kiosk_visible_count']}")
    if summary.get("dry_run"):
        print("Mode               : dry-run (fichier non modifié)")
    print(f"{'=' * 60}\n")
    for point in merged:
        flag = "kiosk" if point.kiosk_visible else "     "
        print(f"  [{flag}] {point.name:40} ({point.x:.2f}, {point.y:.2f})  [{point.source}]")


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync POI ROS → data/points.json (après création dans Sentrymove)"
    )
    parser.add_argument(
        "--host",
        default="192.168.20.22",
        help="IP rosbridge (192.168.20.22 depuis Termux/tablette, 10.42.0.1 depuis PC Wi-Fi robot)",
    )
    parser.add_argument("--port", type=int, default=9090, help="Port rosbridge")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data",
        help="Répertoire data/ contenant points.json",
    )
    parser.add_argument(
        "--mark-kiosk",
        default=",".join(DEFAULT_KIOSK_POIS),
        help="Noms POI à marquer kiosk_visible=true (séparés par des virgules). "
        "Utilisez --mark-kiosk '' pour ne pas modifier les flags.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche le résultat sans écrire points.json",
    )
    args = parser.parse_args()

    mark_kiosk = parse_mark_kiosk(args.mark_kiosk)

    try:
        merged, summary = await sync_from_robot(
            args.data_dir,
            args.host,
            ws_port=args.port,
            mark_kiosk=mark_kiosk,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1

    print_summary(merged, summary)
    if not args.dry_run:
        print(f"Écrit : {args.data_dir / 'points.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
