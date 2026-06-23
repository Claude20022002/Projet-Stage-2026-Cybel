"""Journalisation structurée pendant la visite guidée (debug navigation)."""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cybel.tour_trace")


def default_tour_log_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "logs" / "tour"


def distance_xy(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y1 - y2)


def pose_dict(x: float | None, y: float | None, theta: float | None = None) -> dict[str, float | None]:
    return {"x": x, "y": y, "theta": theta}


def stop_target_dict(stop: Any) -> dict[str, Any]:
    """Résumé cible pour un TourStop ou dict JSON."""
    if hasattr(stop, "id"):
        data = {
            "id": stop.id,
            "equipment_fr": getattr(stop, "equipment_fr", ""),
            "name_fr": getattr(stop, "name_fr", ""),
            "target_point": getattr(stop, "target_point", None),
            "x": stop.x if hasattr(stop, "x") else None,
            "y": stop.y if hasattr(stop, "y") else None,
            "theta": stop.theta if hasattr(stop, "theta") else None,
        }
    else:
        data = {
            "id": stop.get("id"),
            "equipment_fr": stop.get("equipment_fr", ""),
            "name_fr": stop.get("name_fr", ""),
            "target_point": stop.get("target_point"),
            "x": stop.get("x"),
            "y": stop.get("y"),
            "theta": stop.get("theta"),
        }
    if data.get("x") is not None and data.get("y") is not None:
        data["target_type"] = "coordinates"
    elif data.get("target_point"):
        data["target_type"] = "poi"
    else:
        data["target_type"] = "unknown"
    return data


def snapshot_with_distance(
    robot: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any]:
    """Enrichit un snapshot robot avec distance à la cible."""
    out = dict(robot)
    tx, ty = target.get("x"), target.get("y")
    rx, ry = robot.get("x"), robot.get("y")
    if tx is not None and ty is not None and rx is not None and ry is not None:
        dist = distance_xy(float(rx), float(ry), float(tx), float(ty))
        out["distance_to_target_m"] = round(dist, 3)
    else:
        out["distance_to_target_m"] = None
    return out


@dataclass
class TourSessionLogger:
    """Écrit chaque événement en fichier et conserve un tampon pour l'API."""

    log_dir: Path | None = None
    tour_id: str = "labo_principal"
    max_buffer: int = 400
    _buffer: list[dict[str, Any]] = field(default_factory=list, init=False)
    _path: Path | None = field(default=None, init=False)
    _session_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        base = self.log_dir or default_tour_log_dir()
        base.mkdir(parents=True, exist_ok=True)
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._path = base / f"tour_{self._session_id}.log"

    @property
    def log_file(self) -> Path | None:
        return self._path

    @property
    def session_id(self) -> str:
        return self._session_id

    def record(self, event: str, **payload: Any) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session": self._session_id,
            "tour_id": self.tour_id,
            "event": event,
            **payload,
        }
        self._buffer.append(entry)
        if len(self._buffer) > self.max_buffer:
            self._buffer = self._buffer[-self.max_buffer :]

        line = json.dumps(entry, ensure_ascii=False)
        logger.info("[tour] %s", line)
        if self._path:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def tour_start(self, lang: str, stops: list[Any]) -> None:
        targets = [stop_target_dict(s) for s in stops]
        self.record("tour_start", lang=lang, stops_count=len(stops), targets=targets)

    def phase(self, phase: str, *, index: int = -1, stop: Any | None = None, message: str = "") -> None:
        payload: dict[str, Any] = {"phase": phase, "message": message}
        if index >= 0:
            payload["stop_index"] = index
        if stop is not None:
            payload["stop"] = stop_target_dict(stop)
        self.record("phase", **payload)

    def robot_snapshot(self, label: str, robot: dict[str, Any], *, stop: Any | None = None) -> None:
        target = stop_target_dict(stop) if stop is not None else {}
        self.record(label, robot=snapshot_with_distance(robot, target), target=target or None)

    def nav_command(
        self,
        stop: Any,
        *,
        index: int,
        robot: dict[str, Any],
        nav_status: int | None = None,
        nav_status_label: str = "",
        ok: bool | None = None,
        detail: str = "",
    ) -> None:
        target = stop_target_dict(stop)
        self.record(
            "nav_command",
            stop_index=index,
            target=target,
            robot=snapshot_with_distance(robot, target),
            nav_status=nav_status,
            nav_status_label=nav_status_label,
            command_ok=ok,
            detail=detail,
        )

    def nav_progress(
        self,
        stop: Any,
        *,
        index: int,
        robot: dict[str, Any],
        nav_status: int | None = None,
        nav_status_label: str = "",
        elapsed_s: float | None = None,
    ) -> None:
        target = stop_target_dict(stop)
        payload: dict[str, Any] = {
            "stop_index": index,
            "target": target,
            "robot": snapshot_with_distance(robot, target),
            "nav_status": nav_status,
            "nav_status_label": nav_status_label,
        }
        if elapsed_s is not None:
            payload["elapsed_s"] = round(elapsed_s, 1)
        self.record("nav_progress", **payload)

    def nav_result(
        self,
        stop: Any,
        *,
        index: int,
        robot: dict[str, Any],
        success: bool,
        nav_status: int | None = None,
        nav_status_label: str = "",
        error: str = "",
    ) -> None:
        target = stop_target_dict(stop)
        self.record(
            "nav_result",
            stop_index=index,
            target=target,
            robot=snapshot_with_distance(robot, target),
            success=success,
            nav_status=nav_status,
            nav_status_label=nav_status_label,
            error=error or None,
        )

    def tour_end(self, state: str, error: str | None = None) -> None:
        self.record("tour_end", state=state, error=error)

    def recent(self, limit: int = 80) -> list[dict[str, Any]]:
        return list(self._buffer[-limit:])

    def status_payload(self) -> dict[str, Any]:
        return {
            "session_id": self._session_id,
            "log_file": str(self._path) if self._path else None,
            "entries": self.recent(),
        }


_active_logger: TourSessionLogger | None = None


def get_active_tour_logger() -> TourSessionLogger | None:
    return _active_logger


def start_tour_logger(tour_id: str = "labo_principal", log_dir: Path | None = None) -> TourSessionLogger:
    global _active_logger
    _active_logger = TourSessionLogger(tour_id=tour_id, log_dir=log_dir)
    return _active_logger


def clear_active_tour_logger() -> None:
    global _active_logger
    _active_logger = None
