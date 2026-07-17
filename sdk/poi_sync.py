"""Synchronisation des POI ROS (Sentrymove / marker_manager) vers data/points.json."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sdk.marker_utils import (
    MARKER_SERVICES,
    extract_marker_dicts_from_service_response,
    merge_point_dicts,
    parse_marker_to_dict,
)
from sdk.models import Point
from sdk.persistence import JsonPersistence
from sdk.ros_ops import extract_markers_from_ros_response
from sdk.poi_names import is_valid_deployment_poi_name, is_visitor_poi
from sdk.rosbridge import RosbridgeClient

logger = logging.getLogger(__name__)

# Réexport pour compatibilité
__all__ = [
    "MARKER_SERVICES",
    "fetch_robot_markers",
    "marker_dict_to_point",
    "merge_point_dicts",
    "parse_marker_to_dict",
    "sync_from_robot",
    "sync_points_file",
]


def marker_dict_to_point(raw: dict[str, Any], index: int) -> Point | None:
    parsed = parse_marker_to_dict(raw, index)
    if not parsed:
        return None
    return Point.model_validate(parsed)


def markers_to_points(markers: list[dict[str, Any]]) -> list[Point]:
    points: list[Point] = []
    for index, raw in enumerate(markers):
        if not isinstance(raw, dict):
            continue
        point = marker_dict_to_point(raw, index)
        if point:
            points.append(point)
    return points


async def fetch_robot_markers(
    host: str,
    *,
    ws_port: int = 9090,
    timeout: float = 8.0,
) -> list[Point]:
    """Récupère les marqueurs depuis rosbridge (même services que Sentrymove)."""
    client = RosbridgeClient(f"ws://{host}:{ws_port}")
    await client.connect()
    try:
        markers: list[dict[str, Any]] = []
        for service in MARKER_SERVICES:
            response = await client.call_service(service, {}, timeout=timeout)
            values = response.get("values") or response
            markers = extract_markers_from_ros_response(
                values if isinstance(values, dict) else {}
            )
            if markers:
                logger.info("Marqueurs ROS via %s : %d", service, len(markers))
                break
        return markers_to_points(markers)
    finally:
        await client.disconnect()


def apply_kiosk_flags(points: list[Point], mark_kiosk: set[str] | None) -> list[Point]:
    result: list[Point] = []
    for point in points:
        visitor = is_visitor_poi(point.name, str(point.type))
        visible = visitor and (point.name in mark_kiosk if mark_kiosk is not None else True)
        result.append(point.model_copy(update={"kiosk_visible": visible}))
    return result


def _merge_points_in_memory(saved: list[Point], ros_points: list[Point]) -> list[Point]:
    saved_by_name = {p.name: p for p in saved if is_valid_deployment_poi_name(p.name)}
    merged: dict[str, Point] = {}
    for rp in ros_points:
        if not is_valid_deployment_poi_name(rp.name):
            continue
        existing = saved_by_name.get(rp.name)
        merged[rp.name] = rp.model_copy(
            update={
                "kiosk_visible": is_visitor_poi(rp.name, str(rp.type)),
                "source": "merged" if existing else "ros",
            }
        )
    return sorted(merged.values(), key=lambda p: p.name.lower())


def _merge_ros_points(
    store: JsonPersistence,
    ros_points: list[Point],
    *,
    dry_run: bool = False,
) -> list[Point]:
    if dry_run:
        return _merge_points_in_memory(store.load_points(), ros_points)
    return store.merge_robot_points(ros_points)


def sync_points_file(
    data_dir: Path,
    ros_points: list[Point],
    *,
    mark_kiosk: set[str] | None = None,
    dry_run: bool = False,
) -> tuple[list[Point], dict[str, Any]]:
    """Fusionne marqueurs ROS (Deployment Tool) dans ``data/points.json``."""
    store = JsonPersistence(data_dir)
    merged = _merge_ros_points(store, ros_points, dry_run=dry_run)
    final = apply_kiosk_flags(merged, mark_kiosk)
    if not dry_run:
        store.save_points(final)
    summary = {
        "ros_count": len(ros_points),
        "total_count": len(final),
        "kiosk_visible_count": sum(1 for p in final if p.kiosk_visible),
        "names": [p.name for p in final],
        "dry_run": dry_run,
    }
    return final, summary


async def sync_from_robot(
    data_dir: Path,
    host: str,
    *,
    ws_port: int = 9090,
    mark_kiosk: set[str] | None = None,
    dry_run: bool = False,
) -> tuple[list[Point], dict[str, Any]]:
    ros_points = await fetch_robot_markers(host, ws_port=ws_port)
    if not ros_points:
        raise RuntimeError(
            "Aucun marqueur ROS — créez les POI dans Sentrymove puis réessayez."
        )
    return sync_points_file(data_dir, ros_points, mark_kiosk=mark_kiosk, dry_run=dry_run)
