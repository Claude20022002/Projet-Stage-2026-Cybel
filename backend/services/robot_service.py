from config import settings
from mock_robot import MockRobot
from models import MoveCommand, Point, Pose, RobotStatus


class RobotService:
    def __init__(self) -> None:
        self._mock: MockRobot | None = None
        self._use_mock = settings.robot_mock

    @property
    def is_mock(self) -> bool:
        return self._use_mock

    async def connect(self) -> None:
        if self._use_mock:
            self._mock = MockRobot()
            await self._mock.start()
            return
        # Connexion rosbridge à implémenter quand le robot est accessible
        raise NotImplementedError("Mode réel non encore implémenté — utilisez ROBOT_MOCK=true")

    async def disconnect(self) -> None:
        if self._mock:
            await self._mock.stop()
            self._mock = None

    def _require_mock(self) -> MockRobot:
        if not self._mock:
            raise RuntimeError("Robot non connecté")
        return self._mock

    def on_telemetry(self, callback) -> None:
        if self._mock:
            self._mock.on_telemetry(callback)

    def get_status(self) -> RobotStatus:
        return self._require_mock().get_status()

    def get_pose(self) -> Pose:
        return self._require_mock().get_pose()

    def get_points(self) -> list[Point]:
        return self._require_mock().get_points()

    async def move(self, command: MoveCommand) -> None:
        await self._require_mock().move(command.linear_x, command.angular_z)

    async def stop(self) -> None:
        await self._require_mock().stop()

    async def emergency_stop(self) -> None:
        await self._require_mock().emergency_stop()

    async def release_emergency_stop(self) -> None:
        await self._require_mock().release_emergency_stop()

    async def set_manual_mode(self, enabled: bool) -> None:
        await self._require_mock().set_manual_mode(enabled)

    async def navigate_to_point(self, point_name: str) -> bool:
        return await self._require_mock().navigate_to_point(point_name)


robot_service = RobotService()
