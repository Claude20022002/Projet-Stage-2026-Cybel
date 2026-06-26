"""Tests sync POI et marker_utils."""

from sdk.marker_utils import merge_point_dicts, parse_marker_to_dict


def test_parse_marker_to_dict_from_pose() -> None:
    raw = {
        "name": "Routeur CNC",
        "pose": {
            "position": {"x": -8.38, "y": 1.45, "z": 0},
            "orientation": {"x": 0, "y": 0, "z": 0.42, "w": 0.9},
        },
    }
    parsed = parse_marker_to_dict(raw, 0)
    assert parsed is not None
    assert parsed["name"] == "Routeur CNC"
    assert parsed["x"] == -8.38
    assert parsed["y"] == 1.45
    assert parsed["source"] == "ros"


def test_merge_point_dicts_preserves_kiosk_flag() -> None:
    saved = [
        {
            "id": "1",
            "name": "LG-10",
            "type": "common",
            "x": 1.0,
            "y": 2.0,
            "theta": 0.0,
            "floor": "0",
            "kiosk_visible": False,
            "source": "local",
        }
    ]
    ros = [{"name": "LG-10", "x": 3.0, "y": 4.0, "theta": 0.5, "type": "common"}]
    merged = merge_point_dicts(saved, ros)
    assert len(merged) == 1
    assert merged[0]["x"] == 3.0
    assert merged[0]["kiosk_visible"] is False
    assert merged[0]["source"] == "merged"


def test_merge_point_dicts_prunes_obsolete_names() -> None:
    saved = [{"name": "LG-10", "x": 0, "y": 0, "kiosk_visible": True}]
    ros = [{"name": "LG-10", "x": 3.0, "y": 4.0, "type": "common"}]
    merged = merge_point_dicts(saved, ros)
    assert merged == []


def test_merge_point_dicts_prunes_absent_from_ros() -> None:
    saved = [
        {
            "id": "old",
            "name": "CNC ROUTEUR",
            "type": "common",
            "x": 1.0,
            "y": 2.0,
            "theta": 0.0,
            "floor": "0",
            "kiosk_visible": True,
            "source": "local",
        },
        {
            "id": "ghost",
            "name": "ANCIEN-POI-SUPPRIME",
            "type": "common",
            "x": 0.0,
            "y": 0.0,
            "theta": 0.0,
            "floor": "0",
            "kiosk_visible": True,
            "source": "local",
        },
    ]
    ros = [{"name": "LG-10", "x": -1.7, "y": -2.2, "type": "common"}]
    merged = merge_point_dicts(saved, ros)
    names = {p["name"] for p in merged}
    assert names == {"LG-10"}
    assert "ANCIEN-POI-SUPPRIME" not in names
    assert "CNC ROUTEUR" not in names


def test_merge_point_dicts_marks_kiosk_tour_stops() -> None:
    saved: list[dict] = []
    ros = [
        {"name": "CNC ROUTEUR", "x": 1.0, "y": 2.0, "type": "common"},
        {"name": "POSTE-MACHINE", "x": 0.0, "y": 0.0, "type": "common"},
    ]
    merged = merge_point_dicts(
        saved,
        ros,
        mark_kiosk={"CNC ROUTEUR", "LG-10"},
    )
    by_name = {p["name"]: p for p in merged}
    assert by_name["CNC ROUTEUR"]["kiosk_visible"] is True
    assert by_name["POSTE-MACHINE"]["kiosk_visible"] is False
