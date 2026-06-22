import pytest

from sdk.mock_robot import MockRobot


@pytest.mark.asyncio
async def test_delete_local_point():
    robot = MockRobot()
    await robot.start()
    await robot.add_point("Test A")
    assert len(robot.get_points()) >= 1
    assert await robot.delete_point("Test A") is True
    assert all(p.name != "Test A" for p in robot.get_points())


@pytest.mark.asyncio
async def test_cannot_delete_robot_marker():
    robot = MockRobot()
    await robot.start()
    initial = robot.get_points()[0]
    assert not initial.id.startswith("local-")
    assert await robot.delete_point(initial.name) is False
