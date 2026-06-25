"""Tests persistance JSON Phase 3."""

from pathlib import Path

import pytest

from sdk.json_store import append_log_entry, load_json, save_json
from sdk.models import Point
from sdk.persistence import JsonPersistence


def test_save_and_load_json(tmp_path: Path) -> None:
    path = tmp_path / "test.json"
    save_json(path, {"hello": "world"})
    assert load_json(path, {}) == {"hello": "world"}


def test_merge_robot_points_preserves_kiosk_flag(tmp_path: Path) -> None:
    store = JsonPersistence(tmp_path)
    store.save_points(
        [
            Point(
                id="1",
                name="Accueil",
                type="common",
                x=1.0,
                y=2.0,
                kiosk_visible=False,
                source="local",
            )
        ]
    )
    merged = store.merge_robot_points(
        [
            Point(
                id="m1",
                name="Accueil",
                type="common",
                x=3.0,
                y=4.0,
                source="ros",
            )
        ]
    )
    assert len(merged) == 1
    assert merged[0].x == pytest.approx(3.0)
    assert merged[0].kiosk_visible is False
    assert merged[0].source == "merged"


def test_navigation_history_trim(tmp_path: Path) -> None:
    store = JsonPersistence(tmp_path)
    path = store.navigation_path
    for i in range(5):
        append_log_entry(path, {"kind": "test", "index": i}, list_key="events", max_entries=3)
    events = load_json(path, {}).get("events", [])
    assert len(events) == 3
    assert events[0]["index"] == 2
