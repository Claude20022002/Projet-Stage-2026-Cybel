"""Tests Phase 1 — retour borne."""

import asyncio

import pytest

from sdk.mock_robot import MockRobot


@pytest.mark.asyncio
async def test_mock_go_home_sets_returning_state() -> None:
    robot = MockRobot()
    await robot.start()
    ok = await robot.go_home()
    assert ok is True
    assert robot.status.returning_to_charge is True
    assert robot.status.charge_state == "returning"
    await robot.stop()


@pytest.mark.asyncio
async def test_mock_go_home_reaches_charger() -> None:
    robot = MockRobot()
    await robot.start()
    await robot.go_home()
    await asyncio.sleep(7.0)
    assert robot.status.charger is True
    assert robot.status.charge_state == "charging"
    await robot.stop()
