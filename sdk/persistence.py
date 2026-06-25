"""Persistance métier en fichiers JSON (Phase 3 — alternative PostgreSQL)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from sdk.json_store import append_log_entry, load_json, save_json, utc_now_iso
from sdk.models import Point, RobotSettings

logger = logging.getLogger(__name__)


class JsonPersistence:
    """Stocke POI, historique et paramètres dans ``data/*.json``."""

    def __init__(
        self,
        data_dir: Path,
        *,
        history_max_entries: int = 500,
    ) -> None:
        self.data_dir = data_dir
        self.history_max_entries = history_max_entries
        self.points_path = self.data_dir / "points.json"
        self.navigation_path = self.data_dir / "navigation_events.json"
        self.speech_path = self.data_dir / "speech_log.json"
        self.settings_path = self.data_dir / "app_settings.json"

    def load_points(self) -> list[Point]:
        document = load_json(self.points_path, {"version": 1, "points": []})
        raw_points = document.get("points") or []
        points: list[Point] = []
        for item in raw_points:
            if isinstance(item, dict):
                try:
                    points.append(Point.model_validate(item))
                except Exception:
                    continue
        return points

    def save_points(self, points: list[Point]) -> None:
        save_json(
            self.points_path,
            {
                "version": 1,
                "updated_at": utc_now_iso(),
                "points": [p.model_dump() for p in points],
            },
        )

    def merge_robot_points(self, ros_points: list[Point]) -> list[Point]:
        """Fusionne marqueurs ROS avec le cache JSON (ROS prioritaire sur les coords)."""
        saved = {p.name: p for p in self.load_points()}
        merged: dict[str, Point] = dict(saved)

        for rp in ros_points:
            existing = merged.get(rp.name)
            if existing:
                merged[rp.name] = rp.model_copy(
                    update={
                        "kiosk_visible": existing.kiosk_visible,
                        "source": "merged",
                    }
                )
            else:
                merged[rp.name] = rp.model_copy(update={"source": "ros"})

        result = sorted(merged.values(), key=lambda p: p.name.lower())
        self.save_points(result)
        logger.info("POI synchronisés : %d (ROS=%d)", len(result), len(ros_points))
        return result

    def upsert_point(self, point: Point) -> None:
        points = {p.name: p for p in self.load_points()}
        points[point.name] = point
        self.save_points(sorted(points.values(), key=lambda p: p.name.lower()))

    def remove_point(self, name: str) -> bool:
        points = {p.name: p for p in self.load_points()}
        if name not in points:
            return False
        del points[name]
        self.save_points(sorted(points.values(), key=lambda p: p.name.lower()))
        return True

    def kiosk_destinations(self) -> list[Point]:
        return [p for p in self.load_points() if p.kiosk_visible]

    def log_navigation(
        self,
        *,
        kind: str,
        success: bool,
        point_name: str | None = None,
        x: float | None = None,
        y: float | None = None,
        theta: float | None = None,
        nav_status: int | None = None,
        detail: str = "",
    ) -> dict[str, Any]:
        return append_log_entry(
            self.navigation_path,
            {
                "id": str(uuid.uuid4()),
                "kind": kind,
                "success": success,
                "point_name": point_name,
                "x": x,
                "y": y,
                "theta": theta,
                "nav_status": nav_status,
                "detail": detail,
            },
            list_key="events",
            max_entries=self.history_max_entries,
        )

    def log_speech(
        self,
        *,
        text: str,
        ok: bool,
        method: str = "",
        error: str = "",
    ) -> dict[str, Any]:
        return append_log_entry(
            self.speech_path,
            {
                "id": str(uuid.uuid4()),
                "text": text[:500],
                "ok": ok,
                "method": method,
                "error": error[:300],
            },
            list_key="entries",
            max_entries=self.history_max_entries,
        )

    def get_navigation_history(self, limit: int = 50) -> list[dict[str, Any]]:
        document = load_json(self.navigation_path, {"events": []})
        events = list(document.get("events") or [])
        return list(reversed(events[-limit:]))

    def get_speech_history(self, limit: int = 50) -> list[dict[str, Any]]:
        document = load_json(self.speech_path, {"entries": []})
        entries = list(document.get("entries") or [])
        return list(reversed(entries[-limit:]))

    def load_robot_settings(self) -> RobotSettings | None:
        raw = load_json(self.settings_path, {})
        if not raw:
            return None
        try:
            return RobotSettings.model_validate(raw)
        except Exception:
            return None

    def save_robot_settings(self, robot_settings: RobotSettings) -> None:
        save_json(
            self.settings_path,
            {
                "version": 1,
                "updated_at": utc_now_iso(),
                **robot_settings.model_dump(),
            },
        )
