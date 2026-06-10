import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException

from sdk.models import SpeechRequest, SpeechStatus
from services.robot_service import robot_service

router = APIRouter(prefix="/api/speech", tags=["speech"])


@router.get("/status", response_model=SpeechStatus)
async def get_speech_status() -> SpeechStatus:
    return robot_service.get_speech_status()


@router.post("/say")
async def say(request: SpeechRequest) -> dict:
    result = await robot_service.speak(request.text, interrupt=request.interrupt)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Échec TTS"))
    return result


@router.post("/stop")
async def stop_speech() -> dict:
    return await robot_service.stop_speech()
