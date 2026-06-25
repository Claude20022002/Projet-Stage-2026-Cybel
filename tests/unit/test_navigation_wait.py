import asyncio

import pytest

from sdk.mock_robot import MockRobot
from sdk.models import Coordinate


@pytest.mark.asyncio
async def test_wait_rejects_idle_603_without_navigation():
    """Ne doit pas valider l'arrivée si le robot reste à l'état 603 (repos)."""
    robot = MockRobot()
    await robot.start()
    robot.status.nav_status = 603
    robot.status.current_goal = Coordinate(x=5.0, y=5.0, theta=0.0)

    arrived = await robot.wait_for_navigation_arrival(timeout=2.0)
    assert arrived is False


@pytest.mark.asyncio
async def test_wait_accepts_after_navigation_cycle():
    robot = MockRobot()
    await robot.start()
    robot.status.current_goal = Coordinate(x=1.0, y=0.0, theta=0.0)
    robot.status.nav_status = 602

    async def finish_nav():
        await asyncio.sleep(0.3)
        robot.pose.x = 1.0
        robot.pose.y = 0.0
        robot.status.nav_status = 603

    asyncio.create_task(finish_nav())
    arrived = await robot.wait_for_navigation_arrival(timeout=3.0)
    assert arrived is True
