"""Parsing marqueurs ROS — sans dépendance pydantic (compatible Termux lite)."""

from __future__ import annotations

from typing import Any

from sdk.constants import MARKER_TYPE_MAP, ROS_SERVICES
from sdk.poi_names import OBSOLETE_POI_NAMES, is_valid_deployment_poi_name
from sdk.ros_ops import extract_markers_from_ros_response, yaw_from_quaternion

MARKER_SERVICES = (
    ROS_SERVICES["markers"],
    ROS_SERVICES["marker_operation_get"],
)


def _parse_point_type(raw: str) -> str:
    key = (raw or "common").lower().replace(" ", "_")
    return MARKER_TYPE_MAP.get(key, "common")


def parse_marker_to_dict(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    """Convertit un marqueur ROS en dict compatible ``points.json``."""
    name = (
        raw.get("name")
        or raw.get("marker_name")
        or raw.get("label")
        or raw.get("point_name")
    )
    if not name:
        return None

    pose = raw.get("pose") or {}
    position = pose.get("position") if isinstance(pose.get("position"), dict) else pose
    orientation = pose.get("orientation") if isinstance(pose.get("orientation"), dict) else {}

    x = float(raw.get("x") or position.get("x") or pose.get("x") or 0.0)
    y = float(raw.get("y") or position.get("y") or pose.get("y") or 0.0)
    theta = float(raw.get("theta") or raw.get("yaw") or pose.get("theta") or 0.0)
    if not raw.get("theta") and not raw.get("yaw") and orientation:
        theta = yaw_from_quaternion(orientation)

    return {
        "id": str(raw.get("id") or f"m{index}"),
        "name": str(name),
        "type": _parse_point_type(str(raw.get("type") or raw.get("marker_type") or "common")),
        "x": x,
        "y": y,
        "theta": theta,
        "floor": str(raw.get("floor") or raw.get("floor_name") or "0"),
        "kiosk_visible": True,
        "source": "ros",
    }


def extract_raw_markers(response: dict[str, Any]) -> list[dict[str, Any]]:
    values = response.get("values") or response
    return extract_markers_from_ros_response(
        values if isinstance(values, dict) else {}
    )


def extract_marker_dicts_from_service_response(response: dict[str, Any]) -> list[dict[str, Any]]:
    raw_markers = extract_raw_markers(response)
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_markers):
        if not isinstance(raw, dict):
            continue
        parsed = parse_marker_to_dict(raw, index)
        if parsed:
            result.append(parsed)
    return result


def merge_point_dicts(
    saved: list[dict[str, Any]],
    ros_markers: list[dict[str, Any]],
    *,
    mark_kiosk: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Remplace le cache par les marqueurs ROS de la carte courante (supprime les POI absents)."""
    saved_by_name: dict[str, dict[str, Any]] = {
        str(item.get("name")): dict(item)
        for item in saved
        if isinstance(item, dict) and item.get("name")
    }
    merged: dict[str, dict[str, Any]] = {}

    for index, raw in enumerate(ros_markers):
        payload = parse_marker_to_dict(raw, index)
        if not payload:
            continue
        name = str(payload["name"])
        if name in OBSOLETE_POI_NAMES or not is_valid_deployment_poi_name(name):
            continue
        existing = saved_by_name.get(name)
        if existing:
            payload["kiosk_visible"] = existing.get("kiosk_visible", True)
            payload["source"] = "merged"
        else:
            payload["kiosk_visible"] = name in mark_kiosk if mark_kiosk else True
            payload["source"] = "ros"
        if mark_kiosk and name in mark_kiosk:
            payload["kiosk_visible"] = True
        merged[name] = payload

    return sorted(merged.values(), key=lambda p: str(p.get("name", "")).lower())
