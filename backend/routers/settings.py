import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import settings
from sdk.models import RobotSettings
from services.robot_service import robot_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


class MqttConfigRequest(BaseModel):
    host: str = Field(..., min_length=1)
    switch_on: bool = True


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


@router.post("/mqtt-config")
async def configure_mqtt(payload: MqttConfigRequest) -> dict:
    if robot_service.is_mock:
        raise HTTPException(status_code=400, detail="Indisponible en mode simulation")
    ok = await robot_service.config_mqtt_server(payload.host, switch_on=payload.switch_on)
    return {"ok": ok, "host": payload.host, "switch_on": payload.switch_on}
