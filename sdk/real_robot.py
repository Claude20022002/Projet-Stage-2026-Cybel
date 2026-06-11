import asyncio
import json
import logging
import math
from typing import Any, Awaitable, Callable

from sdk.constants import MARKER_TYPE_MAP, NAV_STATUS_LABELS, ROS_SERVICES, ROS_TOPICS
from sdk.lidar_utils import parse_laser_scan
from sdk.map_utils import parse_map_metadata, parse_occupancy_grid
from sdk.models import Coordinate, DetectedPerson, MapData, Point, Pose, RobotStatus, SpeechStatus
from sdk.rosbridge import RosbridgeClient
from sdk.speech import RobotSpeech

logger = logging.getLogger(__name__)

TelemetryCallback = Callable[[str, dict], Awaitable[None]]


def localization_label(percent: float) -> str:
    if percent < 60:
        return "Faible"
    if percent < 80:
        return "Moyenne"
    return "Bonne"


def nav_mode_label(mode: str) -> str:
    return {
        "auto_navi": "Automatique",
        "manual": "Manuel",
        "teleop": "Téléopération",
    }.get(mode, mode)


def nav_status_label(code: int) -> str:
    return NAV_STATUS_LABELS.get(code, f"Code {code}")


def _parse_point_type(raw: str) -> str:
    key = (raw or "common").lower().replace(" ", "_")
    return MARKER_TYPE_MAP.get(key, "common")


def _parse_marker(raw: dict, index: int) -> Point | None:
    name = (
        raw.get("name")
        or raw.get("marker_name")
        or raw.get("label")
        or raw.get("point_name")
    )
    if not name:
        return None

    x = float(raw.get("x") or raw.get("pose", {}).get("x") or 0.0)
    y = float(raw.get("y") or raw.get("pose", {}).get("y") or 0.0)
    theta = float(raw.get("theta") or raw.get("yaw") or raw.get("pose", {}).get("theta") or 0.0)
    ptype = _parse_point_type(str(raw.get("type") or raw.get("marker_type") or "common"))

    return Point(
        id=str(raw.get("id") or f"m{index}"),
        name=str(name),
        type=ptype,  # type: ignore[arg-type]
        x=x,
        y=y,
        theta=theta,
        floor=str(raw.get("floor") or raw.get("floor_name") or "0"),
    )


class RealRobot:
    def __init__(
        self,
        host: str = "10.42.0.1",
        ws_port: int = 9090,
        chassis_id: str = "TY1251D-03195",
        speech_topic: str = "",
        speech_service: str = "",
        speech_http_host: str = "",
        speech_http_port: int = 0,
        speech_http_path: str = "",
    ) -> None:
        self._host = host
        self._chassis_id = chassis_id
        self._client = RosbridgeClient(f"ws://{host}:{ws_port}")
        self._speech = RobotSpeech(
            client=self._client,
            emit=self._emit,
            mock=False,
            preferred_topic=speech_topic,
            preferred_service=speech_service,
            http_host=speech_http_host,
            http_port=speech_http_port,
            http_path=speech_http_path,
        )
        self._telemetry_callbacks: list[TelemetryCallback] = []
        self._reconnect_task: asyncio.Task | None = None

        self.pose = Pose()
        self.status = RobotStatus(
            connected=False,
            mock=False,
            chassis_id=self._chassis_id,
            nav_status=600,
            nav_status_label="En initialisation",
            localization_label="Inconnue",
        )
        self.map_data: MapData | None = None
        self._points: list[Point] = []
        self._manual_mode = False
        self._localization_percent = 0.0

    def on_telemetry(self, callback: TelemetryCallback) -> None:
        self._telemetry_callbacks.append(callback)

    async def _emit(self, event_type: str, payload: dict) -> None:
        for callback in self._telemetry_callbacks:
            await callback(event_type, payload)

    async def start(self) -> None:
        self._client.on_message(self._on_ros_message)
        connected = await self._client.connect()
        self.status.connected = connected

        if not connected:
            await self._emit("event", {"message": "Robot inaccessible — vérifiez le WiFi"})
            await self._emit("status", self.status.model_dump())
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())
            return

        await self._subscribe_topics()
        await self._load_points()
        await self._load_map()
        await self._emit("event", {"message": "Connecté au robot"})
        await self._emit("status", self.status.model_dump())
        await self._emit("pose", self.pose.model_dump())
        if self.map_data:
            await self._emit("map", self.map_data.model_dump())

    async def stop(self) -> None:
        if self._reconnect_task:
            self._reconnect_task.cancel()
        await self._client.disconnect()

    async def _reconnect_loop(self) -> None:
        while True:
            await asyncio.sleep(5.0)
            if self._client.connected:
                continue
            if await self._client.connect():
                self.status.connected = True
                await self._subscribe_topics()
                await self._load_points()
                await self._emit("event", {"message": "Robot reconnecté"})
                await self._emit("status", self.status.model_dump())

    async def _subscribe_topics(self) -> None:
        for topic, throttle in (
            (ROS_TOPICS["pose"], 200),
            (ROS_TOPICS["status"], 500),
            (ROS_TOPICS["current_map"], 2000),
            (ROS_TOPICS["map_metadata"], 2000),
            (ROS_TOPICS["lidar"], 200),
            (ROS_TOPICS["people"], 500),
            (ROS_TOPICS["localization_confidence"], 500),
        ):
            await self._client.subscribe(topic, throttle_rate=throttle)

    async def _load_map(self) -> None:
        response = await self._client.call_service(ROS_SERVICES["static_map"], {})
        grid = (response.get("values") or {}).get("map")
        if not grid:
            return
        parsed = parse_occupancy_grid(grid)
        if parsed:
            self.map_data = parsed
            await self._emit("map", parsed.model_dump())

    async def _on_ros_message(self, topic: str, msg: dict[str, Any]) -> None:
        if topic == ROS_TOPICS["pose"]:
            self.pose = Pose(
                x=float(msg.get("x") or 0.0),
                y=float(msg.get("y") or 0.0),
                theta=float(msg.get("theta") or 0.0),
            )
            await self._emit("pose", self.pose.model_dump())

        elif topic == ROS_TOPICS["status"]:
            await self._handle_status(msg)

        elif topic == ROS_TOPICS["current_map"]:
            parsed = parse_occupancy_grid(msg)
            if parsed:
                self.map_data = parsed
                await self._emit("map", parsed.model_dump())

        elif topic == ROS_TOPICS["map_metadata"]:
            meta = parse_map_metadata(msg)
            if meta and self.map_data:
                self.map_data.metadata = meta
                await self._emit("map", self.map_data.model_dump())

        elif topic == ROS_TOPICS["lidar"]:
            points = parse_laser_scan(msg, self.pose)
            if points:
                await self._emit(
                    "lidar",
                    {"points": [p.model_dump() for p in points[:360]]},
                )

        elif topic == ROS_TOPICS["people"]:
            people = self._parse_people(msg)
            await self._emit(
                "people",
                {"people": [p.model_dump() for p in people]},
            )

        elif topic == ROS_TOPICS["localization_confidence"]:
            self._localization_percent = float(msg.get("data") or 0.0) * 100
            self.status.localization_percent = self._localization_percent
            self.status.localization_label = localization_label(self._localization_percent)
            await self._emit("status", self.status.model_dump())

    def _parse_people(self, msg: dict[str, Any]) -> list[DetectedPerson]:
        raw = self._extract_people_raw(msg)
        if not isinstance(raw, list):
            return []

        people: list[DetectedPerson] = []
        for i, item in enumerate(raw):
            person = self._parse_person_item(item, i)
            if person:
                people.append(person)
        return people

    def _extract_people_raw(self, msg: Any) -> Any:
        if isinstance(msg, list):
            return msg

        if not isinstance(msg, dict):
            return []

        for key in ("people", "data", "array", "detected_people"):
            if key not in msg:
                continue
            value = msg[key]
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    continue
            return value

        if all(k in msg for k in ("x", "y")):
            return [msg]

        return []

    def _parse_person_item(self, item: Any, index: int) -> DetectedPerson | None:
        if not isinstance(item, dict):
            return None

        x = item.get("x")
        y = item.get("y")
        if x is None and "position" in item and isinstance(item["position"], dict):
            x = item["position"].get("x")
            y = item["position"].get("y")
        if x is None and "pose" in item and isinstance(item["pose"], dict):
            x = item["pose"].get("x")
            y = item["pose"].get("y")

        try:
            px = float(x or 0.0)
            py = float(y or 0.0)
        except (TypeError, ValueError):
            return None

        distance = item.get("distance") or item.get("dist")
        if distance is None and self.pose:
            distance = math.hypot(px - self.pose.x, py - self.pose.y)

        return DetectedPerson(
            id=str(item.get("id") or item.get("name") or f"person_{index}"),
            x=px,
            y=py,
            distance=float(distance or 0.0),
        )

    async def _handle_status(self, msg: dict[str, Any]) -> None:
        battery = int(msg.get("battery") or 0)
        charger = bool(int(msg.get("charger") or 0))
        nav_status = int(msg.get("nav_status") or msg.get("nav_internal_status") or 600)
        control_state = int(msg.get("control_state") or 30)
        nav_mode = str(msg.get("nav_mode") or "auto_navi")
        velocity = msg.get("velocity") or [0.0, 0.0]

        goal_raw = msg.get("current_goal_coordinate")
        current_goal = None
        if isinstance(goal_raw, dict):
            current_goal = Coordinate(
                x=float(goal_raw.get("x") or 0.0),
                y=float(goal_raw.get("y") or 0.0),
                theta=float(goal_raw.get("theta") or 0.0),
            )

        self._localization_percent = float(
            msg.get("matching_degree")
            or msg.get("localization_percent")
            or msg.get("match_degree")
            or self._localization_percent
        )

        self.status = RobotStatus(
            connected=True,
            mock=False,
            chassis_id=self._chassis_id,
            battery=battery,
            charger=charger,
            soft_estop=bool(msg.get("soft_estop")),
            hard_estop=bool(msg.get("hard_estop")),
            nav_status=nav_status,
            nav_status_label=nav_status_label(nav_status),
            control_state=control_state,
            nav_mode=nav_mode,
            nav_mode_label=nav_mode_label(nav_mode),
            localization_percent=self._localization_percent,
            localization_label=localization_label(self._localization_percent),
            velocity=(float(velocity[0]), float(velocity[1])) if velocity else (0.0, 0.0),
            current_building_name=str(msg.get("current_building_name") or ""),
            current_floor_name=str(msg.get("current_floor_name") or "0"),
            current_goal=current_goal,
            navigating_to=self.status.navigating_to,
        )
        await self._emit("status", self.status.model_dump())

    async def _load_points(self) -> None:
        response = await self._client.call_service(ROS_SERVICES["markers"], {})
        values = response.get("values") or {}
        markers = (
            values.get("markers")
            or values.get("marker_list")
            or values.get("data")
            or values.get("points")
            or []
        )

        if isinstance(markers, dict):
            markers = markers.get("markers") or list(markers.values())

        if not isinstance(markers, list):
            return

        self._points = [
            p for i, m in enumerate(markers) if isinstance(m, dict) and (p := _parse_marker(m, i))
        ]
        if self._points:
            await self._emit("points", {"points": [p.model_dump() for p in self._points]})

    def get_status(self) -> RobotStatus:
        return self.status.model_copy(deep=True)

    def get_pose(self) -> Pose:
        return self.pose.model_copy(deep=True)

    def get_points(self) -> list[Point]:
        return [p.model_copy(deep=True) for p in self._points]

    def get_map(self) -> MapData | None:
        return self.map_data.model_copy(deep=True) if self.map_data else None

    def get_speech_status(self) -> SpeechStatus:
        return self._speech.get_status()

    async def speak(self, text: str, interrupt: bool = True) -> dict:
        return await self._speech.speak(text, interrupt=interrupt)

    async def stop_speech(self) -> dict:
        return await self._speech.stop()

    async def move(self, linear_x: float, angular_z: float) -> None:
        if not self._client.connected:
            return
        await self._client.publish(
            ROS_TOPICS["velocity_cmd"],
            {
                "linear": {"x": linear_x, "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": angular_z},
            },
        )

    async def stop(self) -> None:
        await self.move(0.0, 0.0)
        if self._client.connected:
            await self._client.publish(ROS_TOPICS["cancel_nav"], {})
        self.status.navigating_to = None
        self.status.current_goal = None
        await self._emit("event", {"message": "Arrêt"})
        await self._emit("status", self.status.model_dump())

    async def emergency_stop(self) -> None:
        await self.stop()
        self.status.soft_estop = True
        self.status.nav_status_label = "Arrêt d'urgence"
        await self._emit("event", {"message": "E-Stop activé"})
        await self._emit("status", self.status.model_dump())

    async def release_emergency_stop(self) -> None:
        self.status.soft_estop = False
        await self._emit("event", {"message": "E-Stop relâché"})
        await self._emit("status", self.status.model_dump())

    async def set_manual_mode(self, enabled: bool) -> None:
        if not self._client.connected:
            return
        mode = 0 if enabled else 1
        await self._client.call_service(ROS_SERVICES["change_mode"], {"mode": mode})
        self._manual_mode = enabled
        await self._emit(
            "event",
            {"message": "Mode manuel activé" if enabled else "Mode automatique activé"},
        )

    async def navigate_to_coordinate(self, x: float, y: float, theta: float = 0.0) -> bool:
        if not self._client.connected:
            return False

        await self._client.publish(
            ROS_TOPICS["navi_goal"],
            {
                "header": {"frame_id": "map"},
                "pose": {
                    "position": {"x": x, "y": y, "z": 0.0},
                    "orientation": {
                        "x": 0.0,
                        "y": 0.0,
                        "z": math.sin(theta / 2),
                        "w": math.cos(theta / 2),
                    },
                },
            },
        )

        self.status.navigating_to = None
        self.status.current_goal = Coordinate(x=x, y=y, theta=theta)
        self.status.nav_status = 602
        self.status.nav_status_label = "En navigation"
        await self._emit("event", {"message": f"Navigation vers ({x:.2f}, {y:.2f})"})
        await self._emit("status", self.status.model_dump())
        return True

    async def navigate_to_point(self, point_name: str) -> bool:
        target = next((p for p in self._points if p.name == point_name), None)
        if not target and not self._client.connected:
            return False

        if self._client.connected:
            await self._client.call_service(
                ROS_SERVICES["poi"],
                {"name": point_name, "point_name": point_name, "command": "go"},
            )

        self.status.navigating_to = point_name
        if target:
            self.status.current_goal = Coordinate(x=target.x, y=target.y, theta=target.theta)
        self.status.nav_status = 602
        self.status.nav_status_label = "En navigation"
        await self._emit("event", {"message": f"Navigation vers {point_name}"})
        await self._emit("status", self.status.model_dump())
        return True
