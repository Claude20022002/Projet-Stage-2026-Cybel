import asyncio
import math
import random
from typing import Awaitable, Callable

from sdk.lidar_utils import mock_lidar_points
from sdk.people_utils import mock_detected_people
from sdk.mock_map import generate_mock_map
from sdk.models import Coordinate, MapData, Point, Pose, RobotStatus, SpeechStatus
from sdk.speech import RobotSpeech

TelemetryCallback = Callable[[str, dict], Awaitable[None]]

MOCK_POINTS: list[Point] = [
    Point(id="p1", name="Accueil", type="common", x=2.1, y=1.0, theta=0.0),
    Point(id="p2", name="Salle A", type="common", x=5.5, y=3.2, theta=1.57),
    Point(id="p3", name="Pile", type="charging", x=-3.0, y=0.2, theta=-0.76),
    Point(id="p4", name="Porte principale", type="gate", x=0.5, y=-2.0, theta=3.14),
    Point(id="p5", name="Attente", type="wait", x=1.8, y=4.5, theta=0.5),
]

NAV_STATUS_LABELS = {
    600: "En initialisation",
    601: "Prêt",
    602: "En navigation",
    603: "Arrivé",
    604: "Erreur",
}


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


class MockRobot:
    def __init__(self) -> None:
        self.pose = Pose(x=0.0, y=0.0, theta=0.0)
        self.status = RobotStatus(
            connected=True,
            mock=True,
            chassis_id="TY1251D-03195",
            battery=75,
            charger=False,
            nav_status=601,
            nav_status_label="Prêt",
            control_state=30,
            nav_mode="auto_navi",
            nav_mode_label="Automatique",
            localization_percent=72.0,
            localization_label="Moyenne",
            velocity=(0.0, 0.0),
            current_building_name="robotics lab",
            current_floor_name="0",
        )
        self.manual_mode = False
        self.navigating_to: str | None = None
        self._navigation_task: asyncio.Task | None = None
        self._telemetry_callbacks: list[TelemetryCallback] = []
        self._simulation_task: asyncio.Task | None = None
        self.map_data: MapData = generate_mock_map()
        self._speech = RobotSpeech(emit=self._emit, mock=True)

    def on_telemetry(self, callback: TelemetryCallback) -> None:
        self._telemetry_callbacks.append(callback)

    async def _emit(self, event_type: str, payload: dict) -> None:
        for callback in self._telemetry_callbacks:
            await callback(event_type, payload)

    async def start(self) -> None:
        await self._emit("map", self.map_data.model_dump())
        if self._simulation_task is None:
            self._simulation_task = asyncio.create_task(self._simulation_loop())

    async def stop(self) -> None:
        if self._navigation_task:
            self._navigation_task.cancel()
        if self._simulation_task:
            self._simulation_task.cancel()

    async def _simulation_loop(self) -> None:
        tick = 0
        while True:
            tick += 1
            if not self.navigating_to and tick % 5 == 0:
                drift = random.uniform(-0.02, 0.02)
                self.pose.theta = (self.pose.theta + drift) % (2 * math.pi)
                self.status.localization_percent = max(
                    35.0,
                    min(95.0, self.status.localization_percent + random.uniform(-1.5, 1.5)),
                )
                self.status.localization_label = localization_label(
                    self.status.localization_percent
                )

            if tick % 10 == 0 and not self.status.charger and not self.navigating_to:
                self.status.battery = max(0, self.status.battery - 1)

            await self._emit("pose", self.pose.model_dump())
            await self._emit("status", self.status.model_dump())
            if tick % 2 == 0:
                lidar = mock_lidar_points(self.pose)
                await self._emit(
                    "lidar",
                    {"points": [p.model_dump() for p in lidar]},
                )
            if tick % 4 == 0:
                people = mock_detected_people(self.pose)
                await self._emit(
                    "people",
                    {"people": [p.model_dump() for p in people]},
                )
            await asyncio.sleep(0.5)

    def get_status(self) -> RobotStatus:
        return self.status.model_copy(deep=True)

    def get_pose(self) -> Pose:
        return self.pose.model_copy(deep=True)

    def get_points(self) -> list[Point]:
        return [point.model_copy(deep=True) for point in MOCK_POINTS]

    def get_map(self) -> MapData | None:
        return self.map_data.model_copy(deep=True)

    def get_speech_status(self) -> SpeechStatus:
        return self._speech.get_status()

    async def speak(self, text: str, interrupt: bool = True) -> dict:
        return await self._speech.speak(text, interrupt=interrupt)

    async def stop_speech(self) -> dict:
        return await self._speech.stop()

    async def move(self, linear_x: float, angular_z: float) -> None:
        if not self.manual_mode:
            await self._emit("event", {"message": "Activez le mode manuel pour piloter"})
            return

        self.status.velocity = (linear_x, angular_z)
        dt = 0.1
        self.pose.x += linear_x * dt * math.cos(self.pose.theta)
        self.pose.y += linear_x * dt * math.sin(self.pose.theta)
        self.pose.theta = (self.pose.theta + angular_z * dt) % (2 * math.pi)
        await self._emit("pose", self.pose.model_dump())
        await self._emit("status", self.status.model_dump())

    async def stop(self) -> None:
        self.status.velocity = (0.0, 0.0)
        if self._navigation_task:
            self._navigation_task.cancel()
            self._navigation_task = None
        self.navigating_to = None
        self.status.nav_status = 601
        self.status.nav_status_label = "Prêt"
        self.status.navigating_to = None
        self.status.current_goal = None
        await self._emit("event", {"message": "Arrêt"})
        await self._emit("status", self.status.model_dump())

    async def emergency_stop(self) -> None:
        await self.stop()
        self.status.soft_estop = True
        self.status.nav_status = 604
        self.status.nav_status_label = "Arrêt d'urgence"
        await self._emit("event", {"message": "E-Stop activé"})
        await self._emit("status", self.status.model_dump())

    async def release_emergency_stop(self) -> None:
        self.status.soft_estop = False
        self.status.nav_status = 601
        self.status.nav_status_label = "Prêt"
        await self._emit("event", {"message": "E-Stop relâché"})
        await self._emit("status", self.status.model_dump())

    async def set_manual_mode(self, enabled: bool) -> None:
        self.manual_mode = enabled
        if enabled:
            self.status.control_state = 0
            self.status.nav_mode = "manual"
        else:
            self.status.control_state = 30
            self.status.nav_mode = "auto_navi"
        self.status.nav_mode_label = nav_mode_label(self.status.nav_mode)
        await self._emit(
            "event",
            {"message": "Mode manuel activé" if enabled else "Mode automatique activé"},
        )
        await self._emit("status", self.status.model_dump())

    async def navigate_to_coordinate(self, x: float, y: float, theta: float = 0.0) -> bool:
        if self._navigation_task:
            self._navigation_task.cancel()

        target = Point(id="click", name=f"({x:.1f}, {y:.1f})", type="common", x=x, y=y, theta=theta)

        self.manual_mode = False
        self.status.control_state = 30
        self.status.nav_mode = "auto_navi"
        self.status.nav_mode_label = nav_mode_label(self.status.nav_mode)
        self.navigating_to = None
        self.status.navigating_to = None
        self.status.nav_status = 602
        self.status.nav_status_label = "En navigation"
        self.status.current_goal = Coordinate(x=x, y=y, theta=theta)
        await self._emit("event", {"message": f"Navigation vers ({x:.1f}, {y:.1f})"})
        await self._emit("status", self.status.model_dump())
        self._navigation_task = asyncio.create_task(self._simulate_navigation(target))
        return True

    async def navigate_to_point(self, point_name: str) -> bool:
        target = next((p for p in MOCK_POINTS if p.name == point_name), None)
        if not target:
            return False

        if self._navigation_task:
            self._navigation_task.cancel()

        self.manual_mode = False
        self.status.control_state = 30
        self.status.nav_mode = "auto_navi"
        self.status.nav_mode_label = nav_mode_label(self.status.nav_mode)
        self.navigating_to = point_name
        self.status.navigating_to = point_name
        self.status.nav_status = 602
        self.status.nav_status_label = "En navigation"
        self.status.current_goal = Coordinate(x=target.x, y=target.y, theta=target.theta)
        await self._emit("event", {"message": f"Navigation vers {point_name}"})
        await self._emit("status", self.status.model_dump())
        self._navigation_task = asyncio.create_task(self._simulate_navigation(target))
        return True

    async def _simulate_navigation(self, target: Point) -> None:
        try:
            steps = 40
            start_x, start_y = self.pose.x, self.pose.y
            for step in range(1, steps + 1):
                t = step / steps
                self.pose.x = start_x + (target.x - start_x) * t
                self.pose.y = start_y + (target.y - start_y) * t
                self.pose.theta = math.atan2(
                    target.y - self.pose.y, target.x - self.pose.x
                )
                self.status.velocity = (0.5, 0.0)
                await self._emit("pose", self.pose.model_dump())
                await self._emit("status", self.status.model_dump())
                await asyncio.sleep(0.15)

            self.pose = Pose(x=target.x, y=target.y, theta=target.theta)
            self.status.velocity = (0.0, 0.0)
            self.status.nav_status = 603
            self.status.nav_status_label = "Arrivé"
            self.navigating_to = None
            self.status.navigating_to = None
            await self._emit("event", {"message": f"Arrivé à {target.name}"})
            await self._emit("pose", self.pose.model_dump())
            await self._emit("status", self.status.model_dump())
        except asyncio.CancelledError:
            self.status.velocity = (0.0, 0.0)
            raise
