"""Tests parsing présence /detected_people_array."""

from sdk.people_utils import parse_people_from_ros_message, people_within_distance


def test_parse_people_from_ros_message_list() -> None:
    msg = {
        "people": [
            {"id": "p1", "x": 1.0, "y": 2.0, "distance": 2.5},
            {"id": "p2", "position": {"x": 0.5, "y": 0.5}},
        ]
    }
    parsed = parse_people_from_ros_message(msg)
    assert len(parsed) == 2
    assert parsed[0]["id"] == "p1"
    assert parsed[0]["distance"] == 2.5


def test_people_within_distance() -> None:
    people = [
        {"id": "a", "distance": 1.2},
        {"id": "b", "distance": 4.0},
    ]
    near = people_within_distance(people, 3.0)
    assert len(near) == 1
    assert near[0]["id"] == "a"
