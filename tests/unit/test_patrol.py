"""Tests Phase 5 — patrouille."""

import asyncio

import pytest

from sdk.patrol import PatrolEngine, PatrolStop, PatrolTask


@pytest.mark.asyncio
async def test_patrol_cycle_speaks_at_each_stop() -> None:
    events: list[str] = []

    task = PatrolTask(
        id="p1",
        name="Test",
        mode="cycle",
        stops=[
            PatrolStop(
                id="a",
                name="Point A",
                speech_fr="Surveillance A",
                x=1.0,
                y=2.0,
                dwell_seconds=0.05,
            ),
            PatrolStop(
                id="b",
                name="Point B",
                speech_fr="Surveillance B",
                x=3.0,
                y=4.0,
                dwell_seconds=0.05,
            ),
        ],
    )

    async def speak(text: str) -> None:
        events.append(f"speak:{text}")

    async def navigate(stop: PatrolStop, index: int) -> None:
        events.append(f"nav:{stop.id}")
        await asyncio.sleep(0.01)

    engine = PatrolEngine(task, speak, navigate, lambda: asyncio.sleep(0))

    async def run_one_cycle() -> None:
        await engine.start("fr")
        deadline = asyncio.get_running_loop().time() + 2.0
        while asyncio.get_running_loop().time() < deadline:
            if engine.get_status().cycle_count >= 1 and "speak:Surveillance B" in events:
                break
            await asyncio.sleep(0.05)
        await engine.stop()

    await run_one_cycle()

    assert "nav:a" in events
    assert "speak:Surveillance A" in events
    assert "nav:b" in events
    assert "speak:Surveillance B" in events
    assert events.index("nav:a") < events.index("speak:Surveillance A")
    assert events.index("nav:b") < events.index("speak:Surveillance B")


@pytest.mark.asyncio
async def test_patrol_stop_cancels_cleanly() -> None:
    task = PatrolTask(
        id="p2",
        name="Long",
        mode="cycle",
        stops=[
            PatrolStop(
                id="a",
                name="A",
                speech_fr="A",
                x=0.0,
                y=0.0,
                dwell_seconds=30,
            ),
        ],
    )
    engine = PatrolEngine(
        task,
        lambda text: asyncio.sleep(0),
        lambda stop, index: asyncio.sleep(0),
        lambda: asyncio.sleep(0),
    )
    await engine.start("fr")
    await asyncio.sleep(0.05)
    result = await engine.stop()
    assert result["ok"] is True
    assert result["status"]["state"] == "stopped"


def test_validate_patrol_task_requires_stops() -> None:
    from sdk.patrol import validate_patrol_task_dict

    with pytest.raises(ValueError, match="arrêt"):
        validate_patrol_task_dict({"id": "x", "name": "X", "stops": []})


def test_round_trip_reverses_on_second_cycle() -> None:
    task = PatrolTask(
        id="rt",
        name="RT",
        mode="round_trip",
        stops=[
            PatrolStop(id="a", name="A", x=0, y=0),
            PatrolStop(id="b", name="B", x=1, y=1),
        ],
    )

    async def noop_speak(text: str) -> None:
        return None

    async def noop_nav(stop: PatrolStop, index: int) -> None:
        return None

    async def noop_stop() -> None:
        return None

    engine = PatrolEngine(task, noop_speak, noop_nav, noop_stop)
    first = [s.id for s in engine._ordered_stops(0)]
    second = [s.id for s in engine._ordered_stops(1)]
    assert first == ["a", "b"]
    assert second == ["b", "a"]
