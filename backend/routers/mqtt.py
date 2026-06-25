import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter

from services.mqtt_bridge_service import mqtt_bridge_service

router = APIRouter(prefix="/api/mqtt", tags=["mqtt"])


@router.get("/status")
async def mqtt_status() -> dict:
    return mqtt_bridge_service.get_status()
