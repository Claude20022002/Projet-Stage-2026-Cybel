import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException

from sdk.models import NavigateCommand, Point
from services.robot_service import robot_service

router = APIRouter(prefix="/api/navigation", tags=["navigation"])


@router.get("/points", response_model=list[Point])
async def get_points() -> list[Point]:
    return robot_service.get_points()


@router.post("/goto")
async def navigate_to(command: NavigateCommand) -> dict:
    success = await robot_service.navigate_to_point(command.point_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Point '{command.point_name}' introuvable")
    return {"ok": True, "point": command.point_name}


@router.post("/cancel")
async def cancel_navigation() -> dict:
    await robot_service.stop()
    return {"ok": True}
