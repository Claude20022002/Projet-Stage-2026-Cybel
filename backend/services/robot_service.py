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
    async def ensure_automatic_navigation(self) -> bool: ...
    async def global_localization(self) -> bool: ...
    async def wait_for_localization(self, min_percent: float | None = None, timeout: float = 45.0) -> bool: ...
    async def ensure_localization(self, min_percent: float | None = None, timeout: float = 45.0) -> bool: ...
    async def wait_for_navigation_arrival(self, timeout: float | None = None) -> bool: ...
    async def navigate_to_point(self, point_name: str) -> bool: ...
    async def navigate_to_coordinate(
        self, x: float, y: float, theta: float = 0.0, *, check_map: bool = True
    ) -> bool: ...
    async def add_point(
        self, name: str, type: str = "common", x: float | None = None,
        y: float | None = None, theta: float | None = None
    ) -> Point: ...
    async def delete_point(self, name: str) -> bool: ...
    def get_speech_status(self) -> SpeechStatus: ...
    async def speak(self, text: str, interrupt: bool = True) -> dict: ...
    async def wait_for_speech(self, text: str) -> None: ...
    async def stop_speech(self) -> dict: ...


class RobotService:
    def __init__(self) -> None:
        self._backend: RobotBackend | None = None
        self._use_mock = settings.robot_mock
        self._settings = RobotSettings()
        self._telemetry_callbacks: list = []

    @property
    def is_mock(self) -> bool:
        return self._use_mock

    def get_settings(self) -> RobotSettings:
        return self._settings.model_copy(deep=True)

    def update_settings(self, data: RobotSettings) -> RobotSettings:
        self._settings = data
        return self.get_settings()

    async def connect(self) -> None:
        if self._backend:
            await self.disconnect()
        if self._use_mock:
            self._backend = MockRobot()
        else:
            self._backend = RealRobot(
                host=settings.robot_host,
                ws_port=settings.robot_ws_port,
                speech_topic=settings.speech_topic,
                speech_service=settings.speech_service,
                speech_http_host=settings.speech_http_host,
                speech_http_port=settings.speech_http_port,
                speech_http_path=settings.speech_http_path,
                speech_adb_serial=settings.speech_adb_serial,
                speech_local_broadcast=settings.speech_local_broadcast,
                localization_min_percent=settings.localization_min_percent,
                auto_relocalize_on_connect=settings.auto_relocalize_on_connect,
                navigation_wait_timeout=settings.navigation_wait_timeout,
            )
        await self._backend.start()
        for callback in self._telemetry_callbacks:
            self._backend.on_telemetry(callback)

    async def disconnect(self) -> None:
        if self._backend:
            await self._backend.stop()
            self._backend = None

    def _require(self) -> RobotBackend:
        if not self._backend:
            raise RuntimeError("Robot non connecté")
        return self._backend

    def on_telemetry(self, callback) -> None:
        self._telemetry_callbacks.append(callback)
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

    async def ensure_automatic_navigation(self) -> bool:
        return await self._require().ensure_automatic_navigation()

    async def global_localization(self) -> bool:
        return await self._require().global_localization()

    async def wait_for_localization(
        self, min_percent: float | None = None, timeout: float = 45.0
    ) -> bool:
        return await self._require().wait_for_localization(min_percent, timeout)

    async def ensure_localization(
        self, min_percent: float | None = None, timeout: float = 45.0
    ) -> bool:
        return await self._require().ensure_localization(min_percent, timeout)

    async def wait_for_navigation_arrival(self, timeout: float | None = None) -> bool:
        return await self._require().wait_for_navigation_arrival(timeout)

    async def navigate_to_point(self, point_name: str) -> bool:
        return await self._require().navigate_to_point(point_name)

    async def navigate_to_coordinate(
        self, x: float, y: float, theta: float = 0.0, *, check_map: bool = True
    ) -> bool:
        return await self._require().navigate_to_coordinate(
            x, y, theta, check_map=check_map
        )

    async def add_point(
        self, name: str, type: str = "common", x: float | None = None,
        y: float | None = None, theta: float | None = None
    ) -> Point:
        return await self._require().add_point(name, type=type, x=x, y=y, theta=theta)

    async def delete_point(self, name: str) -> bool:
        return await self._require().delete_point(name)

    def get_speech_status(self) -> SpeechStatus:
        return self._require().get_speech_status()

    async def speak(self, text: str, interrupt: bool = True) -> dict:
        return await self._require().speak(text, interrupt=interrupt)

    async def wait_for_speech(self, text: str) -> None:
        await self._require().wait_for_speech(text)

    async def stop_speech(self) -> dict:
        return await self._require().stop_speech()


robot_service = RobotService()
