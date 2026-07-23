"""Helpers ROS/rosbridge — chaînes de fallback alignées APK (Phase 0 CYBEL)."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class RosbridgeLike(Protocol):
    async def call_service(
        self,
        service: str,
        args: dict[str, Any] | None = None,
        timeout: float = 5.0,
    ) -> dict[str, Any]: ...

    async def publish(self, topic: str, msg: dict[str, Any]) -> None: ...

    async def advertise(self, topic: str, msg_type: str) -> None: ...


def service_succeeded(response: dict[str, Any]) -> bool:
    """True si le service ROS a répondu positivement (ou sans champ result)."""
    if not response:
        return False
    if response.get("result") is False:
        return False
    return True


async def call_service_first(
    client: RosbridgeLike,
    candidates: list[tuple[str, dict[str, Any]]],
    *,
    timeout: float = 5.0,
) -> tuple[str | None, dict[str, Any]]:
    """Essaie les services dans l'ordre ; retourne (nom_service, réponse) ou (None, {})."""
    last_response: dict[str, Any] = {}
    for service, args in candidates:
        try:
            response = await client.call_service(service, args, timeout=timeout)
            last_response = response
            if service_succeeded(response):
                logger.debug("Service ROS OK : %s", service)
                return service, response
            logger.debug("Service ROS refusé : %s → %s", service, response)
        except Exception as exc:
            logger.debug("Service ROS erreur %s : %s", service, exc)
    return None, last_response


async def publish_first(
    client: RosbridgeLike,
    topics: list[str],
    msg: dict[str, Any],
) -> str | None:
    """Publie sur le premier topic disponible."""
    for topic in topics:
        try:
            await client.publish(topic, msg)
            return topic
        except Exception as exc:
            logger.debug("Publish ROS échoué %s : %s", topic, exc)
    return None


def poi_nav_args(point_name: str, *, command: str = "go") -> dict[str, Any]:
    """Arguments communs navigation POI (tag_manager + legacy poi)."""
    return {
        "name": point_name,
        "tag_name": point_name,
        "point_name": point_name,
        "command": command,
    }


def build_poi_nav_chain(point_name: str) -> list[tuple[str, dict[str, Any]]]:
    from sdk.constants import POI_NAV_SERVICE_CHAIN, ROS_SERVICES

    args = poi_nav_args(point_name)
    # tag_manager/navi n'utilise pas toujours "command"
    tag_args = {"name": point_name, "tag_name": point_name}
    chain: list[tuple[str, dict[str, Any]]] = []
    for service in POI_NAV_SERVICE_CHAIN:
        if service == ROS_SERVICES["tag_manager_navi"]:
            chain.append((service, tag_args))
        else:
            chain.append((service, args))
    return chain


# yutong_assistance/GlobalLocate.cmd constants (via /rosapi/service_request_details) —
# /global_locate n'est PAS un service vide : sans "cmd" explicite, le châssis ne
# répond jamais (observé : timeout, aucune rotation réelle malgré un éventuel
# faux "succès" renvoyé par le service de repli /global_localization, lui
# authentiquement std_srvs/Empty).
GLOBAL_LOCATE_CMD_GLOBAL = 0


def build_global_locate_chain() -> list[tuple[str, dict[str, Any]]]:
    from sdk.constants import ROS_SERVICES, GLOBAL_LOCATE_SERVICE_CHAIN

    args_by_service: dict[str, dict[str, Any]] = {
        ROS_SERVICES["global_locate"]: {
            "cmd": GLOBAL_LOCATE_CMD_GLOBAL,
            "search_step_linear": 0.0,
            "search_step_angular": 0.0,
            "search_boundary": {},
        },
    }
    return [(service, args_by_service.get(service, {})) for service in GLOBAL_LOCATE_SERVICE_CHAIN]


def yaw_from_quaternion(orientation: dict[str, Any]) -> float:
    """Extrait le yaw depuis un quaternion geometry_msgs."""
    import math

    z = float(orientation.get("z") or 0.0)
    w = float(orientation.get("w") or 1.0)
    return math.atan2(2.0 * w * z, 1.0 - 2.0 * z * z)


def extract_markers_from_ros_response(values: dict[str, Any]) -> list[dict[str, Any]]:
    """Aplatit les réponses ``get_markers_details`` / ``get_markers`` en liste de dicts."""
    if not values:
        return []

    collected: list[dict[str, Any]] = []

    def _append_items(items: Any, *, floor: str = "0") -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if isinstance(item, dict):
                marker = dict(item)
                if floor and not marker.get("floor") and not marker.get("floor_name"):
                    marker["floor"] = floor
                collected.append(marker)

    floors = values.get("floors")
    if isinstance(floors, list):
        for floor in floors:
            if not isinstance(floor, dict):
                continue
            floor_name = str(floor.get("floor_name") or floor.get("name") or "0")
            _append_items(floor.get("markers"), floor=floor_name)

    markers = values.get("markers")
    if isinstance(markers, list):
        _append_items(markers)
    elif isinstance(markers, dict):
        _append_items(markers.get("markers"))
        _append_items(markers.get("waypoints"))
        for key in ("points", "data"):
            _append_items(markers.get(key))

    for key in ("marker_list", "data", "points"):
        _append_items(values.get(key))

    return collected
