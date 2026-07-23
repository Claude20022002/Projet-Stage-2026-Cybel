#!/usr/bin/env python3
"""
measure_voice_latency.py — agrège les logs JSONL vocaux (sdk/voice_trace.py,
écrits par scripts/termux/cybel_lite.py sur le robot) : latence bout-en-bout
ET taux de faux déclenchements du mot d'éveil.

Les logs vivent sur la tablette (CYBEL_HOME/data/logs/voice/*.log). Récupérez-les
d'abord via adb, puis lancez ce script en local :

  adb pull /data/data/com.termux/files/home/cybel-test/data/logs/voice data/logs/voice
  python scripts/measure_voice_latency.py

Sortie : résumé console (latence min/moyenne/max, taux de faux déclenchements)
+ les lignes \\ph{} prêtes à copier dans paper/icra_2027/main.tex.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_DIR = ROOT / "data" / "logs" / "voice"


def load_entries(log_dir: Path) -> list[dict]:
    entries: list[dict] = []
    for path in sorted(log_dir.glob("voice_*.log")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def observed_hours(entries: list[dict]) -> float:
    timestamps = []
    for e in entries:
        try:
            timestamps.append(datetime.fromisoformat(e["ts"]))
        except (KeyError, ValueError):
            continue
    if len(timestamps) < 2:
        return 0.0
    span = max(timestamps) - min(timestamps)
    return span.total_seconds() / 3600


def report_latency(entries: list[dict]) -> None:
    voice_entries = [
        e for e in entries if e.get("event") == "voice_exchange" and e.get("latency_ms") is not None
    ]
    if not voice_entries:
        print("Aucun échange vocal avec latence mesurée.")
        return

    latencies = [e["latency_ms"] for e in voice_entries]
    n = len(latencies)
    avg = round(sum(latencies) / n)

    print(f"Échanges vocaux avec latence mesurée : {n}")
    print(f"  min = {min(latencies)} ms, moyenne = {avg} ms, max = {max(latencies)} ms")
    print()
    print("Détail par échange :")
    for e in voice_entries:
        print(f"  {e['ts']}  {e['latency_ms']:>5} ms  [{e.get('kind', '?')}] {e.get('transcript', '')!r}")

    print()
    print("  -> Dans main.tex, remplacez :")
    print("      Voice command round-trip (speech end to TTS start) & \\ph{XXX\\,ms} (\\ph{N} trials)")
    print(f"      par  {min(latencies)}--{max(latencies)}\\,ms (mean {avg}\\,ms)  ({n} trials)")


def report_wake_triggers(entries: list[dict], hours: float) -> None:
    wake_entries = [e for e in entries if e.get("event") == "wake_trigger"]
    if not wake_entries:
        print("Aucun déclenchement du mot d'éveil journalisé.")
        return

    n_total = len(wake_entries)
    n_false = sum(1 for e in wake_entries if not e.get("confirmed"))
    rate = round(100 * n_false / n_total, 1)

    print(f"Déclenchements du mot d'éveil : {n_total} ({n_false} faux, {rate}%)")
    print(f"  Fenêtre d'observation : {hours:.1f} h (écart premier/dernier événement journalisé)")

    print()
    print("  -> Dans main.tex, remplacez :")
    print("      \\ph{false-trigger rate, N hours}")
    print(f"      par  {rate}\\% ({n_false}/{n_total} déclenchements, {hours:.1f} h observées)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--log-dir", type=Path, default=DEFAULT_LOG_DIR,
        help=f"Dossier contenant voice_*.log (défaut : {DEFAULT_LOG_DIR})",
    )
    args = parser.parse_args()

    if not args.log_dir.exists():
        sys.exit(
            f"Dossier introuvable : {args.log_dir}\n"
            "Récupérez d'abord les logs depuis la tablette, par ex. :\n"
            "  adb pull /data/data/com.termux/files/home/cybel-test/data/logs/voice "
            f"{args.log_dir}"
        )

    entries = load_entries(args.log_dir)
    if not entries:
        sys.exit(f"Aucun événement trouvé dans {args.log_dir}")

    hours = observed_hours(entries)

    print("=" * 66)
    print("  LATENCE VOIX")
    print("=" * 66)
    report_latency(entries)

    print()
    print("=" * 66)
    print("  FAUX DÉCLENCHEMENTS MOT D'ÉVEIL")
    print("=" * 66)
    report_wake_triggers(entries, hours)
    print("=" * 66)


if __name__ == "__main__":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
