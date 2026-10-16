"""Circulation de la semaine d'intégration — TEMPORAIRE-INTEGRATION-2026."""

import asyncio

import pytest

from sdk.integration_event import (
    CirculationConfig,
    CirculationEngine,
    battery_low,
    safety_stop_reason,
)

GOOD = {
    "connected": True,
    "hard_estop": False,
    "soft_estop": False,
    "localization_percent": 85.0,
    "battery": 80,
}


class FakeRobot:
    """Navigation scriptée : résultats successifs par POI, journal des appels."""

    def __init__(self, results: dict[str, list[bool]] | None = None, status: dict | None = None):
        self.results = results or {}
        self.status = dict(status or GOOD)
        self.calls: list[str] = []
        self.cancels = 0
        self.announces = 0

    async def navigate(self, name: str) -> tuple[bool, str]:
        self.calls.append(name)
        queue = self.results.get(name)
        ok = queue.pop(0) if queue else True
        return ok, "" if ok else "aucune progression"

    async def read_status(self) -> dict:
        return dict(self.status)

    async def announce(self) -> None:
        self.announces += 1

    async def cancel(self) -> None:
        self.cancels += 1


def engine_for(robot: FakeRobot, config: CirculationConfig, stop_after_calls: int | None = None):
    async def sleep(_: float) -> None:
        # Laisse la main à la boucle ; arrête le moteur après N trajets.
        if stop_after_calls is not None and len(robot.calls) >= stop_after_calls:
            eng._stop_requested = True
        await asyncio.sleep(0)

    eng = CirculationEngine(
        config,
        navigate=robot.navigate,
        read_status=robot.read_status,
        announce=robot.announce,
        cancel=robot.cancel,
        sleep=sleep,
    )
    return eng


async def run_to_end(eng: CirculationEngine) -> None:
    eng.start()
    await asyncio.wait_for(eng._task, timeout=2)


def test_config_requires_stops():
    with pytest.raises(ValueError):
        CirculationConfig.from_dict({"stops": []})
    cfg = CirculationConfig.from_dict({"stops": ["A", " ", "B"], "dwell_seconds": -5})
    assert cfg.stops == ["A", "B"]
    assert cfg.dwell_seconds == 0.0


@pytest.mark.parametrize(
    "patch, expected",
    [
        ({}, None),
        ({"connected": False}, "Châssis"),
        ({"hard_estop": True}, "Arrêt d'urgence"),
        ({"soft_estop": True}, "Arrêt d'urgence"),
        ({"localization_percent": 40.0}, "Localisation faible"),
        ({"localization_percent": None}, "Localisation faible"),
    ],
)
def test_safety_stop_reason(patch, expected):
    reason = safety_stop_reason({**GOOD, **patch}, CirculationConfig(stops=["A"]))
    if expected is None:
        assert reason is None
    else:
        assert expected in reason


def test_battery_low_threshold():
    cfg = CirculationConfig(stops=["A"], battery_min=25)
    assert battery_low({"battery": 24}, cfg)
    assert not battery_low({"battery": 25}, cfg)
    assert not battery_low({}, cfg)


async def test_loops_over_stops_and_announces_on_arrival():
    robot = FakeRobot()
    cfg = CirculationConfig(stops=["A", "B"], dwell_seconds=0)
    eng = engine_for(robot, cfg, stop_after_calls=4)
    await run_to_end(eng)
    assert robot.calls == ["A", "B", "A", "B"]
    assert robot.announces == 4
    assert eng.get_status().legs_ok == 4
    assert eng.get_status().cycle == 2


async def test_estop_refuses_before_any_motion():
    robot = FakeRobot(status={**GOOD, "hard_estop": True})
    eng = engine_for(robot, CirculationConfig(stops=["A"]))
    await run_to_end(eng)
    assert robot.calls == []
    assert eng.get_status().state == "error"
    assert "Arrêt d'urgence" in eng.get_status().message


async def test_low_battery_returns_to_charge_point_then_stops():
    robot = FakeRobot(status={**GOOD, "battery": 10})
    cfg = CirculationConfig(stops=["A", "B"], return_point="POINT-CHARGE")
    eng = engine_for(robot, cfg)
    await run_to_end(eng)
    assert robot.calls == ["POINT-CHARGE"]
    assert eng.get_status().state == "stopped"


async def test_failed_leg_is_retried_once():
    robot = FakeRobot(results={"A": [False, True]})
    eng = engine_for(robot, CirculationConfig(stops=["A"], dwell_seconds=0), stop_after_calls=2)
    await run_to_end(eng)
    assert robot.calls == ["A", "A"]
    assert eng.get_status().legs_ok == 1
    assert eng.get_status().legs_failed == 0


async def test_consecutive_failures_stop_circulation():
    robot = FakeRobot(results={"A": [False] * 2, "B": [False] * 2})
    cfg = CirculationConfig(stops=["A", "B"], max_failed_legs=2)
    eng = engine_for(robot, cfg)
    await run_to_end(eng)
    assert robot.calls == ["A", "A", "B", "B"]
    assert eng.get_status().state == "error"
    assert "2 trajets ratés" in eng.get_status().message
    assert robot.announces == 0


async def test_navigation_exception_counts_as_failed_attempt():
    robot = FakeRobot()

    async def boom(name: str):
        robot.calls.append(name)
        raise RuntimeError("Localisation insuffisante")

    robot.navigate = boom
    eng = engine_for(robot, CirculationConfig(stops=["A"], max_failed_legs=1))
    await run_to_end(eng)
    assert eng.get_status().state == "error"
    assert "Localisation insuffisante" in (eng.get_status().error or "")


async def test_stop_cancels_motion_and_marks_stopped():
    robot = FakeRobot()
    gate = asyncio.Event()

    async def slow_nav(name: str):
        robot.calls.append(name)
        await gate.wait()
        return True, ""

    robot.navigate = slow_nav
    eng = engine_for(robot, CirculationConfig(stops=["A"]))
    eng.start()
    await asyncio.sleep(0.01)
    result = await eng.stop()
    assert result["ok"]
    assert eng.get_status().state == "stopped"
    assert robot.cancels >= 1
    assert not eng.is_running()


async def test_start_twice_is_refused():
    robot = FakeRobot()
    gate = asyncio.Event()

    async def slow_nav(name: str):
        await gate.wait()
        return True, ""

    robot.navigate = slow_nav
    eng = engine_for(robot, CirculationConfig(stops=["A"]))
    assert eng.start()["ok"]
    assert not eng.start()["ok"]
    await eng.stop()
