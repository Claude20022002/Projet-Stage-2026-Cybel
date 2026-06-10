import sys
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from sdk.mock_robot import MockRobot
from sdk.models import MapData, MoveCommand, Point, Pose, RobotSettings, RobotStatus, SpeechStatus
from sdk.real_robot import RealRobot


class RobotBackend(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def on_telemetry(self, callback) -> None: ...
    def get_status(self) -> RobotStatus: ...
    def get_pose(self) -> Pose: ...
    def get_points(self) -> list[Point]: ...
    def get_map(self) -> MapData | None: ...
    async def move(self, linear_x: float, angular_z: float) -> None: ...
    async def stop(self) -> None: ...
    async def emergency_stop(self) -> None: ...
    async def release_emergency_stop(self) -> None: ...
    async def set_manual_mode(self, enabled: bool) -> None: ...
    async def navigate_to_point(self, point_name: str) -> bool: ...
    def get_speech_status(self) -> SpeechStatus: ...
    async def speak(self, text: str, interrupt: bool = True) -> dict: ...
    async def stop_speech(self) -> dict: ...


class RobotService:
    def __init__(self) -> None:
        self._backend: RobotBackend | None = None
        self._use_mock = settings.robot_mock
        self._settings = RobotSettings()

    @property
    def is_mock(self) -> bool:
        return self._use_mock

    def get_settings(self) -> RobotSettings:
        return self._settings.model_copy(deep=True)

    def update_settings(self, data: RobotSettings) -> RobotSettings:
        self._settings = data
        return self.get_settings()

    async def connect(self) -> None:
        if self._use_mock:
            self._backend = MockRobot()
        else:
            self._backend = RealRobot(
                host=settings.robot_host,
                ws_port=settings.robot_ws_port,
                speech_topic=settings.speech_topic,
                speech_service=settings.speech_service,
            )
        await self._backend.start()

    async def disconnect(self) -> None:
        if self._backend:
            await self._backend.stop()
            self._backend = None

    def _require(self) -> RobotBackend:
        if not self._backend:
            raise RuntimeError("Robot non connecté")
        return self._backend

    def on_telemetry(self, callback) -> None:
        if self._backend:
            self._backend.on_telemetry(callback)

    def get_status(self) -> RobotStatus:
        return self._require().get_status()

    def get_pose(self) -> Pose:
        return self._require().get_pose()

    def get_points(self) -> list[Point]:
        return self._require().get_points()

    def get_map(self) -> MapData | None:
        return self._require().get_map()

    async def move(self, command: MoveCommand) -> None:
        await self._require().move(command.linear_x, command.angular_z)

    async def stop(self) -> None:
        await self._require().stop()

    async def emergency_stop(self) -> None:
        await self._require().emergency_stop()

    async def release_emergency_stop(self) -> None:
        await self._require().release_emergency_stop()

    async def set_manual_mode(self, enabled: bool) -> None:
        await self._require().set_manual_mode(enabled)

    async def navigate_to_point(self, point_name: str) -> bool:
        return await self._require().navigate_to_point(point_name)

    def get_speech_status(self) -> SpeechStatus:
        return self._require().get_speech_status()

    async def speak(self, text: str, interrupt: bool = True) -> dict:
        return await self._require().speak(text, interrupt=interrupt)

    async def stop_speech(self) -> dict:
        return await self._require().stop_speech()


robot_service = RobotService()
