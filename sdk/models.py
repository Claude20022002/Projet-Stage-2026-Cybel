from typing import Literal

from pydantic import BaseModel, Field


class Pose(BaseModel):
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0


class Coordinate(Pose):
    pass


class RobotStatus(BaseModel):
    connected: bool = False
    mock: bool = False
    chassis_id: str = "TY1251D-03195"
    battery: int = 0
    charger: bool = False
    soft_estop: bool = False
    hard_estop: bool = False
    nav_status: int = 600
    nav_status_label: str = "En initialisation"
    control_state: int = 30
    nav_mode: str = "auto_navi"
    nav_mode_label: str = "Automatique"
    localization_percent: float = 0.0
    localization_label: str = "Inconnue"
    velocity: tuple[float, float] = (0.0, 0.0)
    current_building_name: str = ""
    current_floor_name: str = "0"
    current_goal: Coordinate | None = None
    navigating_to: str | None = None


class Point(BaseModel):
    id: str
    name: str
    type: Literal[
        "charging",
        "common",
        "gate",
        "access",
        "ride",
        "wait",
        "label",
        "stop",
    ] = "common"
    x: float
    y: float
    theta: float = 0.0
    floor: str = "0"


class MoveCommand(BaseModel):
    linear_x: float = Field(0.0, ge=-0.8, le=0.8)
    angular_z: float = Field(0.0, ge=-2.0, le=2.0)


class NavigateCommand(BaseModel):
    point_name: str


class MapMetadata(BaseModel):
    name: str = "carte"
    floor: str = "0"
    width: int = 0
    height: int = 0
    resolution: float = 0.05
    origin_x: float = 0.0
    origin_y: float = 0.0
    area_sqm: float | None = None


class MapData(BaseModel):
    metadata: MapMetadata
    data: list[int]


class RobotSettings(BaseModel):
    speed_gear: Literal["low", "medium", "high"] = "medium"
    travel_mode: Literal["safety", "balance", "efficiency"] = "balance"
    directional_mode: Literal["arrows", "joystick"] = "joystick"
    robot_host: str = "10.42.0.1"
    mock_mode: bool = True


class LidarPoint(BaseModel):
    x: float
    y: float
    distance: float


class DetectedPerson(BaseModel):
    id: str = ""
    x: float = 0.0
    y: float = 0.0
    distance: float = 0.0


class ReceptionAction(BaseModel):
    id: str
    label: str
    description: str
    icon: str = "circle"
    category: Literal["accueil", "navigation", "maintenance", "sécurité"] = "accueil"
    speech: str | None = None
    target_point: str | None = None
    route_name: str | None = None


class VoiceCommand(BaseModel):
    text: str


class TelemetryMessage(BaseModel):
    type: Literal["status", "pose", "event", "map", "points", "lidar", "people", "speech"]
    status: RobotStatus | None = None
    pose: Pose | None = None
    event: str | None = None
