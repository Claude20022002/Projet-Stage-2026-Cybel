import asyncio

import pytest

from sdk.speech_timing import (
    estimate_speech_seconds,
    tts_service_running_in_output,
    wait_for_tts_completion,
)


def test_estimate_speech_seconds_bounds():
    assert estimate_speech_seconds("") == 1.5
    assert estimate_speech_seconds("x" * 2000) == 90.0


def test_tts_service_marker_detection():
    assert tts_service_running_in_output(
        "ServiceRecord{abc com.cybel.ttsbridge/.SpeakService}"
    )
    assert not tts_service_running_in_output("ServiceRecord{other}")


@pytest.mark.asyncio
async def test_wait_for_tts_completion_uses_estimate_without_probe():
    started = asyncio.get_running_loop().time()
    await wait_for_tts_completion("Bonjour", probe_running=None)
    elapsed = asyncio.get_running_loop().time() - started
    assert elapsed >= 1.4


@pytest.mark.asyncio
async def test_wait_for_tts_completion_waits_until_service_stops():
    state = {"running": True}

    async def probe() -> bool:
        return state["running"]

    async def stop_later() -> None:
        await asyncio.sleep(0.25)
        state["running"] = False

    task = asyncio.create_task(stop_later())
    started = asyncio.get_running_loop().time()
    await wait_for_tts_completion("Court", probe, max_seconds=5.0)
    await task
    elapsed = asyncio.get_running_loop().time() - started
    assert elapsed >= 0.45
