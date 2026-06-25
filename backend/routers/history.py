import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, Query

from services.persistence_service import persistence_service

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/navigation")
async def navigation_history(limit: int = Query(50, ge=1, le=200)) -> dict:
    return {
        "events": persistence_service.get_navigation_history(limit),
        "source": "data/navigation_events.json",
    }


@router.get("/speech")
async def speech_history(limit: int = Query(50, ge=1, le=200)) -> dict:
    return {
        "entries": persistence_service.get_speech_history(limit),
        "source": "data/speech_log.json",
    }
