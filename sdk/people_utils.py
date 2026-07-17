import json
import math
import random
from typing import Any

_MOCK_PEOPLE: list[dict[str, float | str]] = [
    {"id": "visitor_1", "angle": 0.8, "radius": 2.4, "speed": 0.12},
    {"id": "visitor_2", "angle": 2.6, "radius": 3.1, "speed": -0.08},
]


def extract_people_raw(msg: Any) -> list[Any]:
    """Extrait la liste brute depuis un message ROS /detected_people_array."""
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
        if isinstance(value, list):
            return value
    if "x" in msg and "y" in msg:
        return [msg]
    return []


def parse_person_dict(item: Any, index: int, *, origin_x: float = 0.0, origin_y: float = 0.0) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    x = item.get("x")
    y = item.get("y")
    if x is None and isinstance(item.get("position"), dict):
        x = item["position"].get("x")
        y = item["position"].get("y")
    if x is None and isinstance(item.get("pose"), dict):
        x = item["pose"].get("x")
        y = item["pose"].get("y")
    try:
        px = float(x or 0.0)
        py = float(y or 0.0)
    except (TypeError, ValueError):
        return None
    distance = item.get("distance") or item.get("dist")
    if distance is None:
        distance = math.hypot(px - origin_x, py - origin_y)
    return {
        "id": str(item.get("id") or item.get("name") or f"person_{index}"),
        "x": px,
        "y": py,
        "distance": round(float(distance), 2),
    }


def parse_people_from_ros_message(
    msg: Any,
    *,
    origin_x: float = 0.0,
    origin_y: float = 0.0,
) -> list[dict[str, Any]]:
    """Parse un message ROS en liste de dicts (compatible Termux lite)."""
    raw = extract_people_raw(msg)
    people: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        person = parse_person_dict(item, index, origin_x=origin_x, origin_y=origin_y)
        if person:
            people.append(person)
    return people


def mock_detected_people_dict(pose_x: float, pose_y: float) -> list[dict[str, Any]]:
    """Simule des visiteurs proches (dicts) pour tests / mock."""
    people: list[dict[str, Any]] = []
    for spec in _MOCK_PEOPLE:
        angle = float(spec["angle"]) + random.uniform(-0.05, 0.05)
        radius = float(spec["radius"]) + random.uniform(-0.15, 0.15)
        x = pose_x + math.cos(angle) * radius
        y = pose_y + math.sin(angle) * radius
        people.append(
            {
                "id": str(spec["id"]),
                "x": round(x, 3),
                "y": round(y, 3),
                "distance": round(math.hypot(x - pose_x, y - pose_y), 2),
            }
        )
        spec["angle"] = angle + float(spec["speed"])
    return people


def mock_detected_people(pose) -> list:
    """Simule des visiteurs proches du robot pour le mode mock."""
    from sdk.models import DetectedPerson

    people: list[DetectedPerson] = []
    for spec in _MOCK_PEOPLE:
        angle = float(spec["angle"]) + random.uniform(-0.05, 0.05)
        radius = float(spec["radius"]) + random.uniform(-0.15, 0.15)
        x = pose.x + math.cos(angle) * radius
        y = pose.y + math.sin(angle) * radius
        distance = math.hypot(x - pose.x, y - pose.y)
        people.append(
            DetectedPerson(
                id=str(spec["id"]),
                x=x,
                y=y,
                distance=round(distance, 2),
            )
        )
        spec["angle"] = angle + float(spec["speed"])
    return people


def people_within_distance(
    people: list[dict[str, Any]],
    max_distance_m: float,
) -> list[dict[str, Any]]:
    return [p for p in people if float(p.get("distance") or 99.0) <= max_distance_m]
