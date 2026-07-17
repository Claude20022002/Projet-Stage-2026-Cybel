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
from sdk.tour_navigation import navigation_precondition_detail
from services.persistence_service import persistence_service


class RobotBackend(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def on_telemetry(self, callback) -> None: ...
    def get_status(self) -> RobotStatus: ...
    def get_pose(self) -> Pose: ...
    def get_points(self) -> list[Point]: ...
    def set_points(self, points: list[Point]) -> None: ...
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
    async def go_home(self) -> bool: ...
    async def config_mqtt_server(self, host: str, *, switch_on: bool = True) -> bool: ...
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
        saved = persistence_service.load_robot_settings()
        self._settings = saved or RobotSettings()
        self._telemetry_callbacks: list = []

    @property
    def is_mock(self) -> bool:
        return self._use_mock

    def get_settings(self) -> RobotSettings:
        return self._settings.model_copy(deep=True)

    def update_settings(self, data: RobotSettings) -> RobotSettings:
        self._settings = data
        persistence_service.save_robot_settings(self._settings)
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
                connect_timeout=settings.robot_connect_timeout,
                connect_retries=settings.robot_connect_retries,
                stale_seconds=settings.robot_stale_seconds,
            )
        await self._backend.start()
        merged = persistence_service.merge_robot_points(self._backend.get_points())
        if hasattr(self._backend, "set_points"):
            self._backend.set_points(merged)
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

    def apply_synced_points(self, points: list[Point]) -> None:
        if self._backend and hasattr(self._backend, "set_points"):
            self._backend.set_points(points)

    def find_point(self, point_name: str) -> Point | None:
        for point in persistence_service.load_points():
            if point.name == point_name:
                return point
        return next((p for p in self.get_points() if p.name == point_name), None)

    def navigation_block_reason(
        self, *, point_name: str | None = None
    ) -> str | None:
        status = self.get_status()
        return navigation_precondition_detail(
            connected=status.connected,
            soft_estop=status.soft_estop,
            hard_estop=status.hard_estop,
            nav_status=status.nav_status,
            nav_mode=status.nav_mode,
            localization_percent=status.localization_percent,
            min_localization=settings.localization_min_percent,
            point_name=point_name,
        )

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

    async def go_home(self) -> bool:
        success = await self._require().go_home()
        status = self.get_status()
        persistence_service.log_navigation(
            kind="go_home",
            success=success,
            nav_status=status.nav_status,
            detail="retour borne",
        )
        return success

    async def config_mqtt_server(self, host: str, *, switch_on: bool = True) -> bool:
        return await self._require().config_mqtt_server(host, switch_on=switch_on)

    async def navigate_to_point(self, point_name: str) -> bool:
        success = await self._require().navigate_to_point(point_name)
        if not success:
            point = self.find_point(point_name)
            if point is not None:
                success = await self._require().navigate_to_coordinate(
                    point.x,
                    point.y,
                    point.theta,
                    check_map=False,
                )
        status = self.get_status()
        persistence_service.log_navigation(
            kind="navigate_point",
            success=success,
            point_name=point_name,
            nav_status=status.nav_status,
        )
        return success

    async def navigate_to_coordinate(
        self, x: float, y: float, theta: float = 0.0, *, check_map: bool = True
    ) -> bool:
        success = await self._require().navigate_to_coordinate(
            x, y, theta, check_map=check_map
        )
        status = self.get_status()
        persistence_service.log_navigation(
            kind="navigate_coordinate",
            success=success,
            x=x,
            y=y,
            theta=theta,
            nav_status=status.nav_status,
        )
        return success

    async def add_point(
        self, name: str, type: str = "common", x: float | None = None,
        y: float | None = None, theta: float | None = None
    ) -> Point:
        point = await self._require().add_point(name, type=type, x=x, y=y, theta=theta)
        persistence_service.upsert_point(point)
        return point

    async def delete_point(self, name: str) -> bool:
        success = await self._require().delete_point(name)
        if success:
            persistence_service.remove_point(name)
        return success

    def get_speech_status(self) -> SpeechStatus:
        return self._require().get_speech_status()

    async def speak(self, text: str, interrupt: bool = True, priority: str = "normal") -> dict:
        result = await self._require().speak(text, interrupt=interrupt, priority=priority)
        persistence_service.log_speech(
            text=text,
            ok=bool(result.get("ok")),
            method=str(result.get("method", "")),
            error=str(result.get("error", "")),
        )
        return result

    async def wait_for_speech(self, text: str) -> None:
        await self._require().wait_for_speech(text)

    async def stop_speech(self) -> dict:
        return await self._require().stop_speech()

    def get_connection_diagnostics(self) -> dict:
        backend = self._require()
        if hasattr(backend, "connection_diagnostics"):
            return backend.connection_diagnostics()
        return {"connected": False}

    def get_speech_diagnostics(self) -> dict:
        backend = self._require()
        if hasattr(backend, "speech_diagnostics"):
            return backend.speech_diagnostics()
        return {}

    async def ensure_adb_tts(self) -> dict:
        backend = self._require()
        if hasattr(backend, "ensure_adb_tts"):
            return await backend.ensure_adb_tts()
        return {"ok": False}


robot_service = RobotService()
