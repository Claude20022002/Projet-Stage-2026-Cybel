"""Estimation et attente de fin TTS (CybelTTSBridge / Android TextToSpeech)."""
from __future__ import annotations

import asyncio
import inspect
import subprocess
from collections.abc import Awaitable, Callable

TTS_SERVICE_MARKER = "com.cybel.ttsbridge/.SpeakService"


def estimate_speech_seconds(text: str) -> float:
    return min(max(len(text.strip()) * 0.055, 1.5), 90.0)


def tts_service_running_in_output(output: str) -> bool:
    return TTS_SERVICE_MARKER in output


def read_dumpsys_services(*shell_commands: str) -> str:
    """Exécute une ou plusieurs commandes shell et retourne la sortie dumpsys."""
    for cmd in shell_commands:
        try:
            result = subprocess.run(
                ["sh", "-c", cmd],
                capture_output=True,
                timeout=4.0,
                text=True,
            )
            out = (result.stdout or "") + (result.stderr or "")
            if out.strip():
                return out
        except (OSError, subprocess.TimeoutExpired):
            continue
    return ""


def is_local_tts_service_running() -> bool:
    """Détecte SpeakService sur le même appareil (Termux / tête Android)."""
    output = read_dumpsys_services(
        "dumpsys activity services",
        "su -c 'dumpsys activity services'",
    )
    return tts_service_running_in_output(output)


async def _probe_running(probe: Callable[[], bool | Awaitable[bool]]) -> bool:
    value = probe()
    if inspect.isawaitable(value):
        return bool(await value)
    return bool(value)


async def wait_for_tts_completion(
    text: str,
    probe_running: Callable[[], bool | Awaitable[bool]] | None = None,
    *,
    max_seconds: float = 90.0,
    poll_interval: float = 0.2,
    settle_seconds: float = 0.35,
) -> None:
    """Attend la fin du TTS via SpeakService, ou retombe sur une estimation."""
    estimate = estimate_speech_seconds(text)
    if probe_running is None:
        await asyncio.sleep(estimate)
        return

    loop = asyncio.get_running_loop()
    started = loop.time()
    deadline = started + min(max(max_seconds, estimate * 1.25), 90.0)
    saw_service = False
    idle_since: float | None = None

    await asyncio.sleep(0.12)

    while loop.time() < deadline:
        running = await _probe_running(probe_running)
        now = loop.time()
        if running:
            saw_service = True
            idle_since = None
        elif saw_service:
            if idle_since is None:
                idle_since = now
            elif now - idle_since >= settle_seconds:
                return
        elif now - started >= estimate:
            return
        await asyncio.sleep(poll_interval)

    await asyncio.sleep(0.25)
