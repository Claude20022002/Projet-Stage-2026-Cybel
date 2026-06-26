"""Synchronisation POI au démarrage kiosque / visite (backend PC)."""

from __future__ import annotations

from pathlib import Path

from config import settings
from sdk.lab_tour import default_tour_path, load_lab_tour
from sdk.poi_sync import sync_from_robot
from services.robot_service import robot_service


async def ensure_poi_synced_from_robot() -> None:
    """Lit les marqueurs ROS et remplace data/points.json (supprime les POI absents)."""
    if robot_service.is_mock:
        return

    tour = load_lab_tour(default_tour_path(settings.data_dir))
    mark_kiosk = {stop.target_point for stop in tour.stops if stop.target_point}
    merged, _ = await sync_from_robot(
        Path(settings.data_dir),
        settings.robot_host,
        ws_port=settings.robot_ws_port,
        mark_kiosk=mark_kiosk or None,
    )
    robot_service.apply_synced_points(merged)
