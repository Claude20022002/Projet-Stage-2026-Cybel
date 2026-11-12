#!/usr/bin/env python3
"""Mesure la latence et la stabilité du lien rosbridge (phase P1 du Pi compagnon).

LECTURE SEULE : appelle un service d'information de rosapi et écoute /robot_status ;
n'envoie aucune commande au châssis. Même script sur le Pi et sur le PC, pour comparer.

    python scripts/measure_rosbridge_latency.py --calls 100 --listen 60
    python scripts/measure_rosbridge_latency.py --label pi --json data/logs/latence_pi.json

Mesures :
  - aller-retour d'un appel de service rosapi (p50 / p95 / max, en ms) ;
  - écoute de /robot_status : messages reçus, plus long silence (gel Wi-Fi),
    nombre de silences de plus de 2 s, reconnexions nécessaires.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
import statistics
import time
from datetime import datetime
from pathlib import Path

try:
    import websockets
except ImportError:
    raise SystemExit("Dépendance manquante : pip install websockets")

# Services d'information de rosapi, sans effet sur le robot ; le premier qui répond sert.
PROBE_SERVICES = ("/rosapi/get_time", "/rosapi/topics")
FREEZE_S = 2.0


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


async def call(ws, service: str, call_id: str, timeout: float) -> dict:
    await ws.send(json.dumps({"op": "call_service", "id": call_id, "service": service, "args": {}}))
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise asyncio.TimeoutError
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
        if msg.get("op") == "service_response" and msg.get("id") == call_id:
            return msg


async def measure_calls(url: str, n: int, timeout: float) -> dict:
    async with websockets.connect(url, open_timeout=10, ping_interval=None, max_size=None) as ws:
        service = None
        for candidate in PROBE_SERVICES:
            try:
                if (await call(ws, candidate, "probe", timeout)).get("result", True):
                    service = candidate
                    break
            except asyncio.TimeoutError:
                continue
        if service is None:
            raise SystemExit(f"Aucun service de sonde ne répond : {PROBE_SERVICES}")
        rtts, timeouts = [], 0
        for i in range(n):
            t0 = time.perf_counter()
            try:
                await call(ws, service, f"m{i}", timeout)
                rtts.append((time.perf_counter() - t0) * 1000)
            except asyncio.TimeoutError:
                timeouts += 1
            await asyncio.sleep(0.05)
    if not rtts:
        raise SystemExit("Aucun appel n'a abouti")
    return {
        "service": service,
        "calls": n,
        "ok": len(rtts),
        "timeouts": timeouts,
        "rtt_ms": {
            "p50": round(percentile(rtts, 0.50), 1),
            "p95": round(percentile(rtts, 0.95), 1),
            "max": round(max(rtts), 1),
            "mean": round(statistics.fmean(rtts), 1),
        },
    }


async def measure_stream(url: str, duration: float) -> dict:
    """Écoute /robot_status ; se reconnecte si la connexion tombe, et le compte."""
    received, reconnects, freezes, max_gap = 0, 0, 0, 0.0
    end = time.monotonic() + duration
    last = time.monotonic()
    while time.monotonic() < end:
        try:
            async with websockets.connect(url, open_timeout=10, ping_interval=None) as ws:
                await ws.send(json.dumps({"op": "subscribe", "topic": "/robot_status", "throttle_rate": 200}))
                while time.monotonic() < end:
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=max(0.1, end - time.monotonic())))
                    except asyncio.TimeoutError:
                        break
                    if msg.get("topic") == "/robot_status":
                        now = time.monotonic()
                        gap = now - last
                        max_gap = max(max_gap, gap)
                        if gap > FREEZE_S:
                            freezes += 1
                        last = now
                        received += 1
        except (OSError, websockets.WebSocketException):
            reconnects += 1
            await asyncio.sleep(1.0)
    return {
        "duration_s": duration,
        "messages": received,
        "rate_hz": round(received / duration, 2),
        "max_gap_s": round(max_gap, 2),
        f"gaps_over_{FREEZE_S:g}s": freezes,
        "reconnects": reconnects,
    }


async def run(args: argparse.Namespace) -> dict:
    url = f"ws://{args.host}:{args.port}"
    calls = await measure_calls(url, args.calls, args.timeout)
    stream = await measure_stream(url, args.listen) if args.listen > 0 else None
    return {
        "label": args.label or socket.gethostname(),
        "host": socket.gethostname(),
        "target": url,
        "at": datetime.now().isoformat(timespec="seconds"),
        "calls": calls,
        "stream": stream,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="10.42.0.1")
    ap.add_argument("--port", type=int, default=9090)
    ap.add_argument("--calls", type=int, default=100)
    ap.add_argument("--listen", type=float, default=60.0, help="durée d'écoute de /robot_status (s), 0 = aucune")
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--label", default="")
    ap.add_argument("--json", default="", help="fichier où écrire le résultat")
    args = ap.parse_args()
    result = asyncio.run(run(args))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
