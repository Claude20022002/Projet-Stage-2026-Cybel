import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter

from services.charge_service import charge_service
from services.robot_service import robot_service

router = APIRouter(prefix="/api/charge", tags=["charge"])


@router.get("/status")
async def get_charge_status() -> dict:
    status = robot_service.get_status()
    return {
        "battery": status.battery,
        "charger": status.charger,
        "returning_to_charge": status.returning_to_charge,
        "charge_state": status.charge_state,
        "charge_state_label": status.charge_state_label,
        **charge_service.get_config(),
    }


@router.post("/go-home")
async def go_home() -> dict:
    return await charge_service.go_home()
