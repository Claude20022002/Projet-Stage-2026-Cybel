import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from typing import Literal

from fastapi import APIRouter, HTTPException

from services.tour_service import tour_service

router = APIRouter(prefix="/api/tour", tags=["tour"])


@router.get("")
async def get_tour() -> dict:
    return tour_service.get_tour()


@router.get("/status")
async def get_status() -> dict:
    return tour_service.get_status()


@router.post("/start")
async def start_tour(lang: Literal["fr", "en"] = "fr") -> dict:
    result = await tour_service.start(lang)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error", "Échec"))
    return result


@router.post("/stop")
async def stop_tour() -> dict:
    return await tour_service.stop()
