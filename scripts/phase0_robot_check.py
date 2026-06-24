#!/usr/bin/env python3
"""Smoke test Phase 0 CYBEL — validation protocole ROS avant l'interface web.

Vérifie connexion rosbridge, télémétrie, services APK (fallbacks Phase 0),
téléop sécurisée, annulation, navigation POI optionnelle et TTS optionnel.

Usage (depuis la racine du dépôt) :
    python scripts/phase0_robot_check.py
    python scripts/phase0_robot_check.py --teleop --relocalize --nav-poi Accueil --tts

Voir docs/PHASE0_DEMARRAGE.md pour le mode d'emploi complet.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk.constants import (  # noqa: E402
    GLOBAL_LOCATE_SERVICE_CHAIN,
    POI_NAV_SERVICE_CHAIN,
    ROS_SERVICES,
    ROS_TOPICS,
)
from sdk.mock_robot import MockRobot  # noqa: E402
from sdk.real_robot import RealRobot  # noqa: E402
from sdk.ros_ops import build_poi_nav_chain, call_service_first  # noqa: E402


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass
class Check:
    name: str
    status: Status
    detail: str = ""


@dataclass
class TelemetrySink:
    pose_updates: int = 0
    status_updates: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    last_pose: dict[str, Any] = field(default_factory=dict)

    async def on_telemetry(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "pose":
            self.pose_updates += 1
            self.last_pose = payload
        elif event_type == "status":
            self.status_updates += 1
        elif event_type == "event":
            self.events.append(payload)


def _load_env_defaults() -> dict[str, str]:
    """Lit backend/.env si présent (ROBOT_HOST, SPEECH_ADB_SERIAL, etc.)."""
    env_path = ROOT / "backend" / ".env"
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _banner(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _log_check(check: Check) -> None:
    tag = f"[{check.status.value:4}]"
    line = f"{tag} {check.name}"
    if check.detail:
        line += f" — {check.detail}"
    print(line)


async def _wait_until(
    predicate,
    *,
    timeout: float,
    interval: float = 0.25,
    label: str = "",
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return False


async def _list_ros_services(client) -> set[str]:
    try:
        resp = await client.call_service("/rosapi/services", {}, timeout=5.0)
        return set((resp.get("values") or {}).get("services") or [])
    except Exception:
        return set()


def _build_robot(args: argparse.Namespace, env: dict[str, str]):
    if args.mock:
        return MockRobot()

    host = args.host or env.get("ROBOT_HOST", "10.42.0.1")
    port = args.port or int(env.get("ROBOT_WS_PORT", "9090"))
    adb = args.adb_serial or env.get("SPEECH_ADB_SERIAL", "")

    return RealRobot(
        host=host,
        ws_port=port,
        speech_adb_serial=adb,
        auto_relocalize_on_connect=False,
        connect_timeout=args.connect_timeout,
        connect_retries=2,
    )


async def run_checks(robot, args: argparse.Namespace) -> list[Check]:
    env = _load_env_defaults()
    sink = TelemetrySink()
    robot.on_telemetry(sink.on_telemetry)
    checks: list[Check] = []

    host = args.host or env.get("ROBOT_HOST", "10.42.0.1")
    port = args.port or int(env.get("ROBOT_WS_PORT", "9090"))
    mode = "MOCK" if args.mock else f"RÉEL ws://{host}:{port}"

    _banner(f"CYBEL Phase 0 — smoke test ({mode})")
    print("Démarrage… (Ctrl+C pour interrompre)\n")

    try:
        await robot.start()
    except Exception as exc:
        checks.append(Check("Connexion ROSBridge", Status.FAIL, str(exc)))
        return checks

    # 1 — Connexion
    if robot.get_status().connected:
        checks.append(Check("Connexion ROSBridge", Status.PASS, "WebSocket ouvert"))
    else:
        checks.append(
            Check(
                "Connexion ROSBridge",
                Status.FAIL,
                f"Impossible de joindre {host}:{port} — Wi-Fi robot ?",
            )
        )
        return checks

    # 2 — Pose
    pose_ok = await _wait_until(lambda: sink.pose_updates > 0, timeout=args.telemetry_timeout)
    if pose_ok:
        p = sink.last_pose
        checks.append(
            Check(
                "Télémétrie /robot_pose",
                Status.PASS,
                f"x={p.get('x', 0):.2f} y={p.get('y', 0):.2f}",
            )
        )
    else:
        checks.append(
            Check(
                "Télémétrie /robot_pose",
                Status.FAIL,
                f"Aucun message en {args.telemetry_timeout:.0f}s",
            )
        )

    # 3 — Statut robot
    status_ok = await _wait_until(lambda: sink.status_updates > 0, timeout=args.telemetry_timeout)
    st = robot.get_status()
    if status_ok:
        checks.append(
            Check(
                "Télémétrie /robot_status",
                Status.PASS,
                f"nav_status={st.nav_status} ({st.nav_status_label}), "
                f"loc={st.localization_percent:.0f}%",
            )
        )
    else:
        checks.append(Check("Télémétrie /robot_status", Status.FAIL, "Pas de statut reçu"))

    # 4 — /navi_status (CYB-006)
    await asyncio.sleep(2.0)
    st = robot.get_status()
    if st.nav_status in (600, 601, 602, 603, 604):
        checks.append(
            Check(
                "État navigation (navi_status)",
                Status.PASS,
                f"code {st.nav_status} ({st.nav_status_label})",
            )
        )
    else:
        checks.append(
            Check(
                "État navigation (navi_status)",
                Status.WARN,
                f"code inattendu : {st.nav_status}",
            )
        )

    # 5 — Services ROS Phase 0
    if args.mock:
        checks.append(Check("Services ROS Phase 0", Status.SKIP, "mode mock"))
    else:
        services = await _list_ros_services(robot._client)  # noqa: SLF001 — script diagnostic
        expected = set(POI_NAV_SERVICE_CHAIN + GLOBAL_LOCATE_SERVICE_CHAIN)
        found = sorted(s for s in expected if s in services)
        missing = sorted(s for s in expected if s not in services)
        if found:
            detail = "présents : " + ", ".join(found)
            if missing:
                detail += f" | absents (fallback) : {', '.join(missing)}"
            checks.append(
                Check(
                    "Services ROS Phase 0",
                    Status.PASS if found else Status.WARN,
                    detail,
                )
            )
        else:
            checks.append(
                Check(
                    "Services ROS Phase 0",
                    Status.WARN,
                    f"Aucun service APK listé — absents : {', '.join(missing)}",
                )
            )

    # 6 — Marqueurs / POI
    points = robot.get_points()
    if points:
        sample = ", ".join(p.name for p in points[:5])
        extra = f" (+{len(points) - 5})" if len(points) > 5 else ""
        checks.append(
            Check("Marqueurs chargés", Status.PASS, f"{len(points)} — ex. {sample}{extra}")
        )
    else:
        checks.append(
            Check(
                "Marqueurs chargés",
                Status.WARN,
                "Liste vide — navigation POI impossible sans --nav-poi connu",
            )
        )

    # 7 — Relocalisation (optionnel)
    if args.relocalize:
        ok = await robot.global_localization()
        method = next(
            (e.get("method") for e in reversed(sink.events) if e.get("method")),
            None,
        )
        if ok:
            checks.append(
                Check(
                    "Relocalisation globale",
                    Status.PASS,
                    f"service utilisé : {method or 'voir événements'}",
                )
            )
            if not args.mock:
                loc_ok = await robot.wait_for_localization(timeout=args.localize_timeout)
                pct = robot.get_status().localization_percent
                checks.append(
                    Check(
                        "Attente localisation",
                        Status.PASS if loc_ok else Status.WARN,
                        f"{pct:.0f}% après {args.localize_timeout:.0f}s",
                    )
                )
        else:
            checks.append(Check("Relocalisation globale", Status.FAIL, "Aucun service disponible"))
    else:
        checks.append(
            Check("Relocalisation globale", Status.SKIP, "ajouter --relocalize pour tester")
        )

    # 8 — Probe service nav POI (sans relocalisation — le robot tournerait)
    if not args.mock and args.probe_services:
        poi_service, poi_resp = await call_service_first(
            robot._client,  # noqa: SLF001 — script diagnostic
            build_poi_nav_chain("__cybel_probe__"),
            timeout=3.0,
        )
        detail = f"réponse nav={poi_service or 'aucune'}"
        if poi_service and not poi_resp.get("result", True):
            detail += " (service présent, rejet attendu pour marqueur fictif)"
        checks.append(
            Check(
                "Probe service navigation POI",
                Status.PASS if poi_service else Status.WARN,
                detail,
            )
        )

    # 9 — Téléop (publish 0 toujours ; pulse si --teleop)
    if not args.mock:
        try:
            await robot._publish_velocity(0.0, 0.0)  # noqa: SLF001
            teleop_detail = f"advertise {ROS_TOPICS['teleop']}"
            if args.teleop:
                await robot.set_manual_mode(True)
                await asyncio.sleep(0.5)
                await robot.move(0.08, 0.0)
                await asyncio.sleep(0.4)
                await robot.move(0.0, 0.0)
                await robot.stop()
                teleop_detail += " + pulse 0.08 m/s (mode manuel)"
            checks.append(Check("Téléop cmd_vel_mux", Status.PASS, teleop_detail))
        except Exception as exc:
            checks.append(Check("Téléop cmd_vel_mux", Status.FAIL, str(exc)))
    else:
        checks.append(Check("Téléop cmd_vel_mux", Status.SKIP, "mode mock"))

    # 10 — Annulation navigation
    try:
        await robot.stop()
        checks.append(
            Check(
                "Annulation multi-canal",
                Status.PASS,
                "stop() — move_base/cancel + fallbacks",
            )
        )
    except Exception as exc:
        checks.append(Check("Annulation multi-canal", Status.FAIL, str(exc)))

    # 11 — Navigation POI optionnelle
    if args.nav_poi:
        target = args.nav_poi
        if not any(p.name == target for p in points) and not args.mock:
            checks.append(
                Check(
                    f"Navigation POI « {target} »",
                    Status.WARN,
                    "Marqueur absent de la liste — tentative quand même",
                )
            )
        started = await robot.navigate_to_point(target)
        if started:
            method = next(
                (e.get("method") for e in reversed(sink.events) if "method" in e),
                ROS_SERVICES["tag_manager_navi"],
            )
            await asyncio.sleep(args.nav_seconds)
            await robot.stop()
            checks.append(
                Check(
                    f"Navigation POI « {target} »",
                    Status.PASS,
                    f"démarrée via {method}, arrêt après {args.nav_seconds}s",
                )
            )
        else:
            checks.append(
                Check(f"Navigation POI « {target} »", Status.FAIL, "navigate_to_point a échoué")
            )
    else:
        checks.append(
            Check("Navigation POI", Status.SKIP, "--nav-poi NomMarqueur pour tester")
        )

    # 12 — Carte
    map_data = robot.get_map()
    if map_data:
        m = map_data.metadata
        checks.append(
            Check(
                "Carte SLAM",
                Status.PASS,
                f"{m.width}x{m.height} px ({m.name})",
            )
        )
    else:
        checks.append(Check("Carte SLAM", Status.WARN, "Carte non reçue (service /static_map)"))

    # 13 — TTS optionnel
    if args.tts:
        try:
            result = await robot.speak("Test CYBEL phase zéro")
            method = result.get("method", "?")
            ok = result.get("ok", False)
            checks.append(
                Check(
                    "Synthèse vocale",
                    Status.PASS if ok else Status.WARN,
                    f"méthode : {method}",
                )
            )
        except Exception as exc:
            checks.append(Check("Synthèse vocale", Status.FAIL, str(exc)))
    else:
        checks.append(Check("Synthèse vocale", Status.SKIP, "--tts pour tester (ADB requis)"))

    return checks


def _print_summary(checks: list[Check]) -> int:
    _banner("Résumé")
    for check in checks:
        _log_check(check)

    passed = sum(1 for c in checks if c.status == Status.PASS)
    failed = sum(1 for c in checks if c.status == Status.FAIL)
    warned = sum(1 for c in checks if c.status == Status.WARN)
    skipped = sum(1 for c in checks if c.status == Status.SKIP)

    print(f"\n{passed} PASS | {failed} FAIL | {warned} WARN | {skipped} SKIP")

    if failed:
        print("\nÉchec — corriger avant l'interface web (voir docs/PHASE0_DEMARRAGE.md).")
        return 1
    if warned:
        print("\nAvertissements — l'interface peut fonctionner ; vérifier les points WARN.")
        return 0
    print("\nTout est vert — vous pouvez lancer l'interface web.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test Phase 0 CYBEL (protocole ROS aligné APK).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python scripts/phase0_robot_check.py
  python scripts/phase0_robot_check.py --relocalize --teleop
  python scripts/phase0_robot_check.py --nav-poi Accueil --nav-seconds 5 --tts
  python scripts/phase0_robot_check.py --mock
        """,
    )
    parser.add_argument("--host", default="", help="ROSBridge (défaut : backend/.env ou 10.42.0.1)")
    parser.add_argument("--port", type=int, default=0, help="Port WebSocket (défaut : 9090)")
    parser.add_argument("--adb-serial", default="", help="ADB tablette (ex. 172.16.0.194:5555)")
    parser.add_argument("--mock", action="store_true", help="Utiliser MockRobot (sans réseau)")
    parser.add_argument("--connect-timeout", type=float, default=20.0)
    parser.add_argument("--telemetry-timeout", type=float, default=12.0)
    parser.add_argument("--relocalize", action="store_true", help="Lancer relocalisation (robot peut tourner)")
    parser.add_argument("--localize-timeout", type=float, default=45.0)
    parser.add_argument("--probe-services", action="store_true", default=True)
    parser.add_argument("--no-probe-services", action="store_false", dest="probe_services")
    parser.add_argument("--teleop", action="store_true", help="Pulse avant court en mode manuel")
    parser.add_argument("--nav-poi", default="", metavar="NOM", help="Tester navigation vers un marqueur")
    parser.add_argument("--nav-seconds", type=float, default=4.0, help="Durée avant arrêt nav POI")
    parser.add_argument("--tts", action="store_true", help="Phrase TTS de test")
    return parser.parse_args(argv)


async def _main_async(args: argparse.Namespace) -> int:
    env = _load_env_defaults()
    robot = _build_robot(args, env)
    try:
        checks = await run_checks(robot, args)
        return _print_summary(checks)
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Arrêt utilisateur.")
        return 130
    finally:
        try:
            await robot.stop()
        except Exception:
            pass


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    raise SystemExit(asyncio.run(_main_async(args)))


if __name__ == "__main__":
    main()
