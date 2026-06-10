import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter

from config import settings
from sdk.models import RobotSettings
from services.robot_service import robot_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=RobotSettings)
async def get_settings() -> RobotSettings:
    data = robot_service.get_settings()
    data.robot_host = settings.robot_host
    data.mock_mode = robot_service.is_mock
    return data


@router.put("", response_model=RobotSettings)
async def update_settings(payload: RobotSettings) -> RobotSettings:
    current = robot_service.get_settings()
    updated = current.model_copy(update={
        "speed_gear": payload.speed_gear,
        "travel_mode": payload.travel_mode,
        "directional_mode": payload.directional_mode,
    })
    return robot_service.update_settings(updated)
