import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException

from sdk.models import AddPointCommand, NavigateCommand, NavigateCoordinateCommand, Point
from sdk.tour_navigation import navigation_failure_message, navigation_recovery_hint
from services.robot_service import robot_service
from services.tour_service import tour_service

router = APIRouter(prefix="/api/navigation", tags=["navigation"])


def _navigation_failure_detail(*, point_name: str | None = None) -> str:
    reason = robot_service.navigation_block_reason(point_name=point_name)
    if reason:
        return reason
    status = robot_service.get_status()
    if status.nav_mode == "manual":
        return (
            "Le robot n'a pas confirmé le mode navigation automatique — "
            "réessayez ou relocalisez"
        )
    if point_name:
        return (
            f"Navigation impossible vers « {point_name} » "
            f"({status.nav_status_label or status.nav_status})"
        )
    return (
        "Navigation impossible : destination inaccessible "
        f"({status.nav_status_label or status.nav_status}). "
        f"{navigation_recovery_hint(status.nav_status)}"
    )


@router.get("/points", response_model=list[Point])
async def get_points() -> list[Point]:
    return robot_service.get_points()


@router.post("/points", response_model=Point)
async def add_point(command: AddPointCommand) -> Point:
    return await robot_service.add_point(
        command.name,
        type=command.type,
        x=command.x,
        y=command.y,
        theta=command.theta,
    )


@router.delete("/points/{point_name}")
async def delete_point(point_name: str) -> dict:
    success = await robot_service.delete_point(point_name)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Impossible de supprimer « {point_name} » "
                "(introuvable ou point carte robot non supprimable)"
            ),
        )
    return {"ok": True, "point": point_name}


@router.post("/goto")
async def navigate_to(command: NavigateCommand) -> dict:
    reason = robot_service.navigation_block_reason(point_name=command.point_name)
    if reason:
        raise HTTPException(status_code=400, detail=reason)

    if robot_service.find_point(command.point_name) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Point « {command.point_name} » introuvable",
        )

    success = await robot_service.navigate_to_point(command.point_name)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=_navigation_failure_detail(point_name=command.point_name),
        )
    return {"ok": True, "point": command.point_name}


@router.post("/goto-coordinate")
async def navigate_to_coordinate(command: NavigateCoordinateCommand) -> dict:
    reason = robot_service.navigation_block_reason()
    if reason:
        raise HTTPException(status_code=400, detail=reason)

    success = await robot_service.navigate_to_coordinate(command.x, command.y, command.theta)
    if not success:
        status = robot_service.get_status()
        if status.nav_status in (600, 604):
            raise HTTPException(
                status_code=400,
                detail=navigation_failure_message(status.nav_status),
            )
        raise HTTPException(
            status_code=400,
            detail=_navigation_failure_detail(),
        )
    return {"ok": True, "x": command.x, "y": command.y}


@router.post("/cancel")
async def cancel_navigation() -> dict:
    await tour_service.stop()
    await robot_service.stop()
    return {"ok": True}
