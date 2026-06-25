import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from typing import Literal

from fastapi import APIRouter, HTTPException

from sdk.models import GoDestinationRequest, Point, ReceptionAction, VoiceCommand
from services.persistence_service import persistence_service
from services.reception_service import reception_service

router = APIRouter(prefix="/api/reception", tags=["reception"])


@router.get("/destinations", response_model=list[Point])
async def list_destinations() -> list[Point]:
    """POI visibles sur le kiosque (``kiosk_visible=true`` dans data/points.json)."""
    return persistence_service.kiosk_destinations()


@router.post("/go")
async def go_to_destination(body: GoDestinationRequest) -> dict:
    result = await reception_service.go_to_destination(body.point_name, lang=body.lang)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Échec"))
    return result


@router.get("/actions", response_model=list[ReceptionAction])
async def list_actions() -> list[ReceptionAction]:
    return reception_service.list_actions()


@router.post("/actions/{action_id}/execute")
async def execute_action(action_id: str, lang: Literal["fr", "en"] = "fr") -> dict:
    result = await reception_service.execute(action_id, lang)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Échec"))
    return result


@router.post("/voice")
async def voice_command(command: VoiceCommand, lang: Literal["fr", "en"] = "fr") -> dict:
    result = await reception_service.handle_voice(command, lang)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Non reconnu"))
    return result
