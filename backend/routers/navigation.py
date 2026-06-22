import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException

from sdk.models import AddPointCommand, NavigateCommand, NavigateCoordinateCommand, Point
from services.robot_service import robot_service
from services.tour_service import tour_service

router = APIRouter(prefix="/api/navigation", tags=["navigation"])


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
    status = robot_service.get_status()
    if not status.connected:
        raise HTTPException(
            status_code=503,
            detail="Navigation impossible : liaison rosbridge coupée (reconnexion en cours)",
        )
    success = await robot_service.navigate_to_point(command.point_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Point '{command.point_name}' introuvable")
    return {"ok": True, "point": command.point_name}


@router.post("/goto-coordinate")
async def navigate_to_coordinate(command: NavigateCoordinateCommand) -> dict:
    status = robot_service.get_status()
    if not status.connected:
        raise HTTPException(
            status_code=503,
            detail="Navigation impossible : liaison rosbridge coupée (reconnexion en cours)",
        )
    success = await robot_service.navigate_to_coordinate(command.x, command.y, command.theta)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Navigation impossible : destination inaccessible (obstacle ou hors carte)",
        )
    return {"ok": True, "x": command.x, "y": command.y}


@router.post("/cancel")
async def cancel_navigation() -> dict:
    await tour_service.stop()
    await robot_service.stop()
    return {"ok": True}
