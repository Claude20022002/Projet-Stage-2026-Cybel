"""Tests Phase 6 — navigation et TTS."""

import asyncio

import pytest

from sdk.mock_robot import MockRobot
from sdk.models import Coordinate
from sdk.speech import RobotSpeech
from sdk.tour_navigation import (
    evaluate_navigation_arrival,
    navigation_recovery_hint,
    pose_distance_to_goal,
)


def test_pose_distance_to_goal() -> None:
    assert pose_distance_to_goal(0.0, 0.0, 3.0, 4.0) == pytest.approx(5.0)


def test_evaluate_arrival_by_proximity_during_navigation() -> None:
    assert evaluate_navigation_arrival(
        nav_status=602,
        saw_active=True,
        pose_x=1.0,
        pose_y=0.0,
        goal_x=1.2,
        goal_y=0.0,
        velocity=(0.0, 0.0),
    )


def test_recovery_hint_for_604() -> None:
    assert "relocalisez" in navigation_recovery_hint(604).lower()


@pytest.mark.asyncio
async def test_speech_priority_and_interrupt() -> None:
    speech = RobotSpeech(mock=True)
    bg = asyncio.create_task(speech.speak("message long en arriere plan", interrupt=False, priority="background"))
    await asyncio.sleep(0.02)
    urgent = await speech.speak("alerte", interrupt=True, priority="urgent")
    assert urgent.get("ok") is True
    bg.cancel()
    try:
        await bg
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_speech_sequential_queue() -> None:
    speech = RobotSpeech(mock=True)
    r1 = await speech.speak("un", interrupt=False, priority="normal")
    r2 = await speech.speak("deux", interrupt=False, priority="background")
    assert r1.get("ok") and r2.get("ok")


@pytest.mark.asyncio
async def test_wait_near_goal_without_603_cycle() -> None:
    robot = MockRobot()
    await robot.start()
    robot.status.current_goal = Coordinate(x=0.1, y=0.0, theta=0.0)
    robot.pose.x = 0.05
    robot.pose.y = 0.0
    robot.status.nav_status = 602
    arrived = await robot.wait_for_navigation_arrival(timeout=1.0)
    assert arrived is True
