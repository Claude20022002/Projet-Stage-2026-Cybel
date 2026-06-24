import asyncio
import json
import logging
import math
import time
from typing import Any, Awaitable, Callable

from sdk.constants import (
    CANCEL_NAV_PUBLISH_TOPICS,
    CANCEL_NAV_SERVICE_CHAIN,
    LIDAR_TOPICS,
    MARKER_TYPE_MAP,
    NAV_STATUS_LABELS,
    ROS_MSG_TYPES,
    ROS_SERVICES,
    ROS_TOPICS,
    navigation_failure_message,
)
from sdk.lidar_utils import parse_laser_scan
from sdk.map_utils import is_coordinate_navigable, parse_map_metadata, parse_occupancy_grid
from sdk.models import Coordinate, DetectedPerson, MapData, Point, Pose, RobotStatus, SpeechStatus
from sdk.ros_ops import build_global_locate_chain, build_poi_nav_chain, call_service_first, publish_first
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


def normalize_localization_percent(value: float) -> float:
    """Normalise matching_degree (0–1 ou 0–100) en pourcentage."""
    if value <= 0:
        return 0.0
    if value <= 1.0:
        return value * 100.0
    return value


def nav_mode_label(mode: str) -> str:
    return {
        "auto_navi": "Automatique",
        "manual": "Manuel",
        "teleop": "Téléopération",
    }.get(mode, mode)


def nav_status_label(code: int) -> str:
    return NAV_STATUS_LABELS.get(code, f"Code {code}")


def _pose_near_goal(pose: Pose, goal: Coordinate, tolerance: float = 0.45) -> bool:
    return math.hypot(pose.x - goal.x, pose.y - goal.y) <= tolerance


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
        speech_adb_serial: str = "",
        speech_local_broadcast: bool = False,
        localization_min_percent: float = 60.0,
        auto_relocalize_on_connect: bool = True,
        navigation_wait_timeout: float = 300.0,
        connect_timeout: float = 20.0,
        connect_retries: int = 3,
        stale_seconds: float = 25.0,
    ) -> None:
        self._host = host
        self._chassis_id = chassis_id
        self._client = RosbridgeClient(
            f"ws://{host}:{ws_port}",
            connect_timeout=connect_timeout,
            connect_retries=connect_retries,
        )
        self._speech = RobotSpeech(
            client=self._client,
            emit=self._emit,
            mock=False,
            preferred_topic=speech_topic,
            preferred_service=speech_service,
            http_host=speech_http_host,
            http_port=speech_http_port,
            http_path=speech_http_path,
            adb_serial=speech_adb_serial,
            local_broadcast=speech_local_broadcast,
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
        self._localization_min_percent = localization_min_percent
        self._auto_relocalize_on_connect = auto_relocalize_on_connect
        self._navigation_wait_timeout = navigation_wait_timeout
        self._stale_seconds = stale_seconds
        self._relocalize_task: asyncio.Task | None = None
        self._nav_saw_active = False
        self._last_ros_message_at = 0.0
        self._suppress_robot_goal = False
        self._teleop_advertised = False

    def on_telemetry(self, callback: TelemetryCallback) -> None:
        self._telemetry_callbacks.append(callback)

    async def _emit(self, event_type: str, payload: dict) -> None:
        for callback in self._telemetry_callbacks:
            asyncio.create_task(self._invoke_telemetry(callback, event_type, payload))

    async def _invoke_telemetry(
        self, callback: TelemetryCallback, event_type: str, payload: dict
    ) -> None:
        try:
            await callback(event_type, payload)
        except Exception as exc:
            logger.warning("Callback télémétrie (%s): %s", event_type, exc)

    async def start(self) -> None:
        self._client.on_message(self._on_ros_message)
        self._client.on_disconnect(self._on_ros_disconnect)
        self._ensure_reconnect_loop()
        connected = await self._client.connect()
        self.status.connected = connected
        self._last_ros_message_at = time.monotonic()

        if not connected:
            await self._emit("event", {"message": "Robot inaccessible — vérifiez le WiFi"})
            await self._emit("status", self.status.model_dump())
            return

        await self._after_connect(announce=True)
        self._last_ros_message_at = time.monotonic()

    def _ensure_reconnect_loop(self) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _after_connect(self, *, announce: bool = False) -> None:
        await self._subscribe_topics()
        await self._load_points()
        await self._load_map()
        if announce:
            await self._emit("event", {"message": "Connecté au robot"})
        await self._emit("status", self.status.model_dump())
        await self._emit("pose", self.pose.model_dump())
        if self.map_data:
            await self._emit("map", self.map_data.model_dump())
        if self._auto_relocalize_on_connect:
            if self._relocalize_task and not self._relocalize_task.done():
                self._relocalize_task.cancel()
            self._relocalize_task = asyncio.create_task(self._auto_relocalize_if_needed())

    async def _on_ros_disconnect(self) -> None:
        if self.status.connected:
            self.status.connected = False
            await self._emit("event", {"message": "Connexion robot perdue — reconnexion…"})
            await self._emit("status", self.status.model_dump())
        self._ensure_reconnect_loop()

    async def _auto_relocalize_if_needed(self) -> None:
        await asyncio.sleep(2.0)
        if not self._client.connected:
            return
        if self._localization_percent >= self._localization_min_percent:
            return
        await self._emit(
            "event",
            {
                "message": (
                    f"Localisation faible ({self._localization_percent:.0f} %) "
                    "— relocalisation automatique…"
                )
            },
        )
        await self.ensure_localization(self._localization_min_percent)

    async def stop(self) -> None:
        if self._relocalize_task:
            self._relocalize_task.cancel()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        await self._client.disconnect()

    async def _reconnect_loop(self) -> None:
        while True:
            await asyncio.sleep(5.0)
            stale = (time.monotonic() - self._last_ros_message_at) > self._stale_seconds
            if self._client.connected and not stale:
                continue

            if self._client.connected and stale:
                logger.warning(
                    "rosbridge silencieux depuis %.0f s — reconnexion",
                    self._stale_seconds,
                )
                await self._client.disconnect()
                await asyncio.sleep(2.0)
                if self.status.connected:
                    self.status.connected = False
                    await self._emit("event", {"message": "Connexion robot perdue — reconnexion…"})
                    await self._emit("status", self.status.model_dump())

            if self._client.connected:
                continue

            if self.status.connected:
                self.status.connected = False
                await self._emit("event", {"message": "Connexion robot perdue — reconnexion…"})
                await self._emit("status", self.status.model_dump())

            if await self._client.connect():
                self.status.connected = True
                self._last_ros_message_at = time.monotonic()
                await self._after_connect()
                await self._emit("event", {"message": "Robot reconnecté"})

    async def _subscribe_topics(self) -> None:
        for topic, throttle in (
            (ROS_TOPICS["pose"], 200),
            (ROS_TOPICS["status"], 500),
            (ROS_TOPICS["navi_status"], 500),
            (ROS_TOPICS["current_map"], 2000),
            (ROS_TOPICS["map_metadata"], 2000),
            (ROS_TOPICS["people"], 500),
            (ROS_TOPICS["localization_confidence"], 500),
        ):
            await self._client.subscribe(topic, throttle_rate=throttle)
        for topic in LIDAR_TOPICS:
            await self._client.subscribe(topic, throttle_rate=100)

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
        self._last_ros_message_at = time.monotonic()

        if topic == ROS_TOPICS["pose"]:
            self.pose = Pose(
                x=float(msg.get("x") or 0.0),
                y=float(msg.get("y") or 0.0),
                theta=float(msg.get("theta") or 0.0),
            )
            await self._emit("pose", self.pose.model_dump())

        elif topic == ROS_TOPICS["status"]:
            await self._handle_status(msg)

        elif topic == ROS_TOPICS["navi_status"]:
            code = int(
                msg.get("data")
                if msg.get("data") is not None
                else msg.get("nav_status", msg.get("status", 0))
            )
            if code:
                self.status.nav_status = code
                self.status.nav_status_label = nav_status_label(code)
                await self._emit("status", self.status.model_dump())

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

        elif topic in LIDAR_TOPICS:
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
            self._localization_percent = normalize_localization_percent(
                float(msg.get("data") or 0.0)
            )
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
        if control_state != 30:
            nav_mode = "manual"
        velocity = msg.get("velocity") or [0.0, 0.0]

        goal_raw = msg.get("current_goal_coordinate")
        current_goal = None
        if isinstance(goal_raw, dict):
            gx = float(goal_raw.get("x") or 0.0)
            gy = float(goal_raw.get("y") or 0.0)
            if abs(gx) > 1e-4 or abs(gy) > 1e-4:
                current_goal = Coordinate(
                    x=gx,
                    y=gy,
                    theta=float(goal_raw.get("theta") or 0.0),
                )

        navigating_to = self.status.navigating_to
        if self._suppress_robot_goal:
            current_goal = None
            navigating_to = None
            if nav_status in (601, 603):
                self._suppress_robot_goal = False
        elif nav_status not in (602,) and current_goal is None:
            navigating_to = None

        self._localization_percent = normalize_localization_percent(
            float(
                msg.get("matching_degree")
                or msg.get("localization_percent")
                or msg.get("match_degree")
                or self._localization_percent
            )
        )

        self.status = RobotStatus(
            connected=self._client.connected,
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
            navigating_to=navigating_to,
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
        self.status.connected = self._client.connected
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

    async def wait_for_speech(self, text: str) -> None:
        await self._speech.wait_for_completion(text)

    async def stop_speech(self) -> dict:
        return await self._speech.stop()

    async def _cancel_navigation(self) -> None:
        point_name = self.status.navigating_to
        if self._client.connected:
            poi_stops: list[dict[str, Any]] = [{"command": "stop"}]
            if point_name:
                poi_stops.insert(
                    0,
                    {"name": point_name, "point_name": point_name, "command": "stop"},
                )
            for args in poi_stops:
                try:
                    await self._client.call_service(ROS_SERVICES["poi"], args, timeout=3.0)
                except Exception:
                    pass
            await call_service_first(
                self._client,
                [(service, {}) for service in CANCEL_NAV_SERVICE_CHAIN]
                + [(ROS_SERVICES["marker_control"], {"command": "stop"})],
                timeout=3.0,
            )
            await publish_first(
                self._client,
                CANCEL_NAV_PUBLISH_TOPICS,
                {},
            )
        await self._publish_velocity(0.0, 0.0)
        self._suppress_robot_goal = True
        self.status.navigating_to = None
        self.status.current_goal = None
        self._nav_saw_active = False
        if self.status.nav_status in (602, 604):
            self.status.nav_status = 601
            self.status.nav_status_label = nav_status_label(601)
        await self._emit("event", {"message": "Navigation annulée"})
        await self._emit("status", self.status.model_dump())

    async def _publish_velocity(self, linear_x: float, angular_z: float) -> None:
        if not self._client.connected:
            return
        if not self._teleop_advertised:
            await self._client.advertise(
                ROS_TOPICS["teleop"],
                ROS_MSG_TYPES["twist"],
            )
            self._teleop_advertised = True
        await self._client.publish(
            ROS_TOPICS["teleop"],
            {
                "linear": {"x": linear_x, "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": angular_z},
            },
        )

    async def _wait_control_mode(self, *, manual: bool, timeout: float = 5.0) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if manual:
                if self.status.control_state != 30 or self.status.nav_mode == "manual":
                    return True
            elif self.status.control_state == 30 and self.status.nav_mode != "manual":
                return True
            await asyncio.sleep(0.25)
        return False

    async def ensure_automatic_navigation(self) -> bool:
        """Passe en mode auto et annule une navigation bloquée avant un objectif."""
        if not self._client.connected:
            return False

        await self._cancel_navigation()
        await asyncio.sleep(0.3)

        if self.status.control_state == 30 and self.status.nav_mode != "manual":
            return True

        await self._client.call_service(ROS_SERVICES["change_mode"], {"mode": 1})
        self._manual_mode = False
        if await self._wait_control_mode(manual=False):
            self.status.nav_mode = "auto_navi"
            self.status.control_state = 30
            self.status.nav_mode_label = nav_mode_label("auto_navi")
            await self._emit("event", {"message": "Mode navigation automatique activé"})
            await self._emit("status", self.status.model_dump())
            return True

        await self._emit(
            "event",
            {"message": "Le robot n'a pas confirmé le mode navigation automatique"},
        )
        return False

    async def _ensure_manual_control(self) -> bool:
        if not self._client.connected:
            return False
        if self.status.control_state != 30 and self.status.nav_mode == "manual":
            return True
        await self._cancel_navigation()
        await self._client.call_service(ROS_SERVICES["change_mode"], {"mode": 0})
        self._manual_mode = True
        if await self._wait_control_mode(manual=True):
            self.status.nav_mode = "manual"
            self.status.control_state = 0
            self.status.nav_mode_label = nav_mode_label("manual")
            await self._emit("status", self.status.model_dump())
            return True
        return False

    async def move(self, linear_x: float, angular_z: float) -> None:
        if not self._client.connected:
            return
        if self.status.control_state == 30 and self.status.nav_mode != "manual":
            if self._manual_mode:
                if not await self._ensure_manual_control():
                    await self._emit(
                        "event",
                        {"message": "Téléopération refusée — mode manuel non confirmé"},
                    )
                    return
            else:
                await self._emit(
                    "event",
                    {"message": "Téléopération refusée — activez le mode manuel"},
                )
                return
        await self._publish_velocity(linear_x, angular_z)

    async def stop(self) -> None:
        await self._cancel_navigation()

    async def emergency_stop(self) -> None:
        await self.stop()
        if self._client.connected:
            try:
                await self._client.publish(ROS_TOPICS["soft_stop"], {"data": True})
            except Exception:
                pass
        self.status.soft_estop = True
        self.status.nav_status_label = "Arrêt d'urgence"
        await self._emit("event", {"message": "E-Stop activé"})
        await self._emit("status", self.status.model_dump())

    async def release_emergency_stop(self) -> None:
        await self._cancel_navigation()
        self.status.soft_estop = False
        await self._emit("event", {"message": "E-Stop relâché — objectif de navigation effacé"})
        await self._emit("status", self.status.model_dump())

    async def set_manual_mode(self, enabled: bool) -> None:
        if not self._client.connected:
            await self._emit("event", {"message": "Robot non connecté — mode manuel impossible"})
            return

        if enabled:
            await self._cancel_navigation()
            await asyncio.sleep(0.3)
            await self._client.call_service(ROS_SERVICES["change_mode"], {"mode": 0})
            self._manual_mode = True
            confirmed = await self._wait_control_mode(manual=True)
        else:
            await self._client.call_service(ROS_SERVICES["change_mode"], {"mode": 1})
            self._manual_mode = False
            confirmed = await self._wait_control_mode(manual=False)

        self.status.nav_mode = "manual" if enabled else "auto_navi"
        self.status.control_state = 0 if enabled else 30
        self.status.nav_mode_label = nav_mode_label(self.status.nav_mode)
        if not confirmed:
            await self._emit(
                "event",
                {
                    "message": (
                        f"Mode {'manuel' if enabled else 'automatique'} demandé "
                        "— en attente de confirmation robot"
                    )
                },
            )
        else:
            await self._emit(
                "event",
                {"message": "Mode manuel activé" if enabled else "Mode automatique activé"},
            )
        await self._emit("status", self.status.model_dump())

    async def global_localization(self) -> bool:
        """Relance la relocalisation globale (recalage du lidar sur la carte).

        Fait généralement tourner le robot sur lui-même pendant quelques
        secondes — le pourcentage de localisation remonte ensuite via
        /localization_confidence.
        """
        if not self._client.connected:
            return False
        service, _ = await call_service_first(
            self._client,
            build_global_locate_chain(),
            timeout=8.0,
        )
        if service:
            await self._emit(
                "event",
                {"message": "Relocalisation globale lancée", "method": service},
            )
            return True
        await self._emit("event", {"message": "Relocalisation — aucun service ROS disponible"})
        return False

    async def wait_for_localization(
        self,
        min_percent: float | None = None,
        timeout: float = 45.0,
    ) -> bool:
        target = min_percent if min_percent is not None else self._localization_min_percent
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if self._localization_percent >= target:
                return True
            await asyncio.sleep(0.5)
        return self._localization_percent >= target

    async def ensure_localization(
        self,
        min_percent: float | None = None,
        timeout: float = 45.0,
    ) -> bool:
        target = min_percent if min_percent is not None else self._localization_min_percent
        if self._localization_percent >= target:
            return True
        if not await self.global_localization():
            return False
        return await self.wait_for_localization(target, timeout=timeout)

    async def wait_for_navigation_arrival(
        self,
        timeout: float | None = None,
    ) -> bool:
        limit = timeout if timeout is not None else self._navigation_wait_timeout
        loop = asyncio.get_running_loop()
        deadline = loop.time() + limit
        goal = self.status.current_goal
        activation_deadline = loop.time() + 12.0

        if goal and _pose_near_goal(self.pose, goal):
            return True

        self._nav_saw_active = False

        while loop.time() < deadline:
            nav_status = self.status.nav_status
            if nav_status == 602:
                self._nav_saw_active = True
            if nav_status == 604:
                await self._emit(
                    "event",
                    {"message": navigation_failure_message(604)},
                )
                return False
            if self._nav_saw_active and nav_status == 603:
                if goal is None or _pose_near_goal(self.pose, goal):
                    vel = self.status.velocity
                    if abs(vel[0]) < 0.05 and abs(vel[1]) < 0.05:
                        return True
            if not self._nav_saw_active and loop.time() > activation_deadline:
                logger.warning(
                    "Navigation non démarrée (nav_status=%s, goal=%s)",
                    nav_status,
                    goal,
                )
                return False
            await asyncio.sleep(0.4)
        return False

    async def _wait_nav_ready_after_cancel(self, timeout: float = 8.0) -> bool:
        """Annule une nav bloquée et attend un état prêt (601/603)."""
        await self._cancel_navigation()
        await asyncio.sleep(0.5)
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if self.status.nav_status in (601, 603):
                return True
            await asyncio.sleep(0.4)
        return self.status.nav_status in (601, 603)

    async def navigate_to_coordinate(
        self, x: float, y: float, theta: float = 0.0, *, check_map: bool = True
    ) -> bool:
        if not self._client.connected:
            return False

        if not await self.ensure_automatic_navigation():
            return False

        self._suppress_robot_goal = False

        if self.status.nav_status in (604, 600):
            if not await self._wait_nav_ready_after_cancel():
                await self._emit(
                    "event",
                    {
                        "message": (
                            f"Navigation refusée — état {self.status.nav_status} "
                            f"({self.status.nav_status_label}). Relocalisez le robot."
                        )
                    },
                )
                return False

        if self.status.nav_status == 600:
            await self._emit(
                "event",
                {"message": "Navigation refusée — robot non localisé (nav_status 600)"},
            )
            return False

        if (
            check_map
            and self.map_data
            and not is_coordinate_navigable(self.map_data, x, y, strict=True)
        ):
            await self._emit(
                "event",
                {"message": f"Destination ({x:.2f}, {y:.2f}) inaccessible (obstacle ou hors carte)"},
            )
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
        self._nav_saw_active = False
        await self._emit("event", {"message": f"Navigation vers ({x:.2f}, {y:.2f})"})
        await self._emit("status", self.status.model_dump())
        return True

    async def add_point(
        self,
        name: str,
        type: str = "common",
        x: float | None = None,
        y: float | None = None,
        theta: float | None = None,
    ) -> Point:
        point = Point(
            id=f"local-{len(self._points) + 1}",
            name=name,
            type=type,  # type: ignore[arg-type]
            x=x if x is not None else self.pose.x,
            y=y if y is not None else self.pose.y,
            theta=theta if theta is not None else self.pose.theta,
            floor=self.status.current_floor_name,
        )

        if self._client.connected:
            # Tentative non vérifiée : aucun POI ajouté ainsi n'a été testé sur
            # le robot réel (voir docs/INTERFACE.md).
            await self._client.call_service(
                ROS_SERVICES["poi"],
                {
                    "name": point.name,
                    "point_name": point.name,
                    "command": "add",
                    "x": point.x,
                    "y": point.y,
                    "theta": point.theta,
                },
            )

        self._points.append(point)
        await self._emit("points", {"points": [p.model_dump() for p in self._points]})
        await self._emit("event", {"message": f"Point '{name}' ajouté"})
        return point

    async def delete_point(self, name: str) -> bool:
        index = next((i for i, p in enumerate(self._points) if p.name == name), None)
        if index is None:
            return False

        point = self._points[index]
        if not point.id.startswith("local-"):
            return False

        if self._client.connected:
            for command in ("delete", "remove", "del"):
                try:
                    await self._client.call_service(
                        ROS_SERVICES["poi"],
                        {"name": name, "point_name": name, "command": command},
                    )
                    break
                except Exception:
                    pass

        del self._points[index]
        if self.status.navigating_to == name:
            self.status.navigating_to = None
        await self._emit("points", {"points": [p.model_dump() for p in self._points]})
        await self._emit("event", {"message": f"Point '{name}' supprimé"})
        return True

    async def navigate_to_point(self, point_name: str) -> bool:
        target = next((p for p in self._points if p.name == point_name), None)
        if not target and not self._client.connected:
            return False

        if not await self.ensure_automatic_navigation():
            return False

        self._suppress_robot_goal = False

        if self.status.nav_status in (604, 600):
            if not await self._wait_nav_ready_after_cancel():
                await self._emit(
                    "event",
                    {
                        "message": (
                            f"Navigation refusée — état {self.status.nav_status}. "
                            "Relocalisez le robot."
                        )
                    },
                )
                return False

        if self.status.nav_status == 600:
            await self._emit(
                "event",
                {"message": "Navigation refusée — robot non localisé (nav_status 600)"},
            )
            return False

        nav_method: str | None = None
        if self._client.connected:
            nav_method, _ = await call_service_first(
                self._client,
                build_poi_nav_chain(point_name),
                timeout=5.0,
            )
            if not nav_method:
                await self._emit(
                    "event",
                    {"message": f"Navigation vers {point_name} — échec appel service ROS"},
                )
                return False

        self.status.navigating_to = point_name
        if target:
            self.status.current_goal = Coordinate(x=target.x, y=target.y, theta=target.theta)
        self.status.nav_status = 602
        self.status.nav_status_label = "En navigation"
        self._nav_saw_active = False
        event: dict[str, Any] = {"message": f"Navigation vers {point_name}"}
        if nav_method:
            event["method"] = nav_method
        await self._emit("event", event)
        await self._emit("status", self.status.model_dump())
        return True
