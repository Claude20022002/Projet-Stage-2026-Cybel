import math
import random

from sdk.models import DetectedPerson, Pose

_MOCK_PEOPLE: list[dict[str, float | str]] = [
    {"id": "visitor_1", "angle": 0.8, "radius": 2.4, "speed": 0.12},
    {"id": "visitor_2", "angle": 2.6, "radius": 3.1, "speed": -0.08},
]


def mock_detected_people(pose: Pose) -> list[DetectedPerson]:
    """Simule des visiteurs proches du robot pour le mode mock."""
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
