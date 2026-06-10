from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models import MoveCommand, Pose, RobotStatus
from services.robot_service import robot_service

router = APIRouter(prefix="/api/robot", tags=["robot"])


class ManualModeRequest(BaseModel):
    enabled: bool


@router.get("/status", response_model=RobotStatus)
async def get_status() -> RobotStatus:
    return robot_service.get_status()


@router.get("/pose", response_model=Pose)
async def get_pose() -> Pose:
    return robot_service.get_pose()


@router.post("/move")
async def move(command: MoveCommand) -> dict:
    await robot_service.move(command)
    return {"ok": True}


@router.post("/stop")
async def stop() -> dict:
    await robot_service.stop()
    return {"ok": True}


@router.post("/emergency-stop")
async def emergency_stop() -> dict:
    await robot_service.emergency_stop()
    return {"ok": True}


@router.post("/release-emergency-stop")
async def release_emergency_stop() -> dict:
    await robot_service.release_emergency_stop()
    return {"ok": True}


@router.post("/mode/manual")
async def set_manual_mode(request: ManualModeRequest) -> dict:
    await robot_service.set_manual_mode(request.enabled)
    return {"ok": True, "manual": request.enabled}
