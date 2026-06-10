import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException

from sdk.models import ReceptionAction, VoiceCommand
from services.reception_service import reception_service

router = APIRouter(prefix="/api/reception", tags=["reception"])


@router.get("/actions", response_model=list[ReceptionAction])
async def list_actions() -> list[ReceptionAction]:
    return reception_service.list_actions()


@router.post("/actions/{action_id}/execute")
async def execute_action(action_id: str) -> dict:
    result = await reception_service.execute(action_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Échec"))
    return result


@router.post("/voice")
async def voice_command(command: VoiceCommand) -> dict:
    result = await reception_service.handle_voice(command)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Non reconnu"))
    return result
