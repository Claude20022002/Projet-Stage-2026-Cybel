import sys
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.tour_service import tour_service

router = APIRouter(prefix="/api/tour", tags=["tour"])


class TourStopPayload(BaseModel):
    id: str | None = None
    name_fr: str = ""
    name_en: str = ""
    equipment_fr: str
    equipment_en: str = ""
    speech_fr: str = ""
    speech_en: str = ""
    target_point: str | None = None
    x: float | None = None
    y: float | None = None
    theta: float | None = None
    approach_speech_fr: str | None = None
    approach_speech_en: str | None = None
    dwell_seconds: float = 12.0


class TourSavePayload(BaseModel):
    id: str = "labo_principal"
    title_fr: str = "Visite du laboratoire"
    title_en: str = "Laboratory tour"
    subtitle_fr: str = ""
    subtitle_en: str = ""
    intro_speech_fr: str = ""
    intro_speech_en: str = ""
    outro_speech_fr: str = ""
    outro_speech_en: str = ""
    stops: list[TourStopPayload] = Field(default_factory=list)
    knowledge_source: str | None = None


@router.get("")
async def get_tour() -> dict:
    return tour_service.get_tour()


@router.get("/full")
async def get_tour_full() -> dict:
    return tour_service.get_tour_full()


@router.put("/full")
async def save_tour_full(payload: TourSavePayload) -> dict:
    try:
        data = tour_service.save_tour(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "tour": data}


@router.post("/reload")
async def reload_tour() -> dict:
    """Recharge le parcours depuis data/lab_tour.json (sans redémarrer le backend)."""
    try:
        tour = tour_service.reload_from_disk()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "stops": len(tour.get("stops", [])), "tour": tour}


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


@router.post("/halt")
async def halt_tour() -> dict:
    return await tour_service.halt()


@router.post("/stops")
async def add_stop(payload: TourStopPayload) -> dict:
    try:
        data = tour_service.add_stop(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "tour": data}


@router.put("/stops/{stop_id}")
async def update_stop(stop_id: str, payload: TourStopPayload) -> dict:
    try:
        data = tour_service.update_stop(
            stop_id, payload.model_dump(exclude_none=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "tour": data}


@router.delete("/stops/{stop_id}")
async def delete_stop(stop_id: str) -> dict:
    try:
        data = tour_service.delete_stop(stop_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "tour": data}


@router.post("/stops/from-pose")
async def add_stop_from_pose(payload: dict[str, Any]) -> dict:
    equipment = str(payload.get("equipment_fr", "")).strip()
    if not equipment:
        raise HTTPException(status_code=400, detail="equipment_fr requis")
    try:
        data = tour_service.create_stop_from_pose(
            equipment,
            float(payload["x"]),
            float(payload["y"]),
            float(payload.get("theta", 0)),
            **{
                k: v
                for k, v in payload.items()
                if k in ("name_fr", "speech_fr", "dwell_seconds")
            },
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "tour": data}
