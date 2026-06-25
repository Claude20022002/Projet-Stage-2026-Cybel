import sys
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.patrol_service import patrol_service

router = APIRouter(prefix="/api/patrol", tags=["patrol"])


class PatrolStopPayload(BaseModel):
    id: str | None = None
    name: str
    name_en: str = ""
    speech_fr: str = ""
    speech_en: str = ""
    target_point: str | None = None
    x: float | None = None
    y: float | None = None
    theta: float | None = None
    dwell_seconds: float = 8.0


class PatrolTaskPayload(BaseModel):
    id: str | None = None
    name: str
    mode: Literal["cycle", "round_trip", "random"] = "cycle"
    intro_speech_fr: str = ""
    intro_speech_en: str = ""
    stops: list[PatrolStopPayload] = Field(default_factory=list)


@router.get("")
async def list_patrol_tasks() -> list[dict]:
    return patrol_service.list_tasks()


@router.get("/status")
async def get_patrol_status() -> dict:
    return patrol_service.get_status()


@router.get("/{task_id}")
async def get_patrol_task(task_id: str) -> dict:
    try:
        return patrol_service.get_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("")
async def create_patrol_task(payload: PatrolTaskPayload) -> dict:
    try:
        task = patrol_service.create_task(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "task": task}


@router.put("/{task_id}")
async def update_patrol_task(task_id: str, payload: PatrolTaskPayload) -> dict:
    try:
        task = patrol_service.update_task(
            task_id, payload.model_dump(exclude_none=True)
        )
    except ValueError as exc:
        status = 409 if "en cours" in str(exc) else 404
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return {"ok": True, "task": task}


@router.delete("/{task_id}")
async def delete_patrol_task(task_id: str) -> dict:
    try:
        patrol_service.delete_task(task_id)
    except ValueError as exc:
        status = 409 if "en cours" in str(exc) else 404
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/{task_id}/start")
async def start_patrol(task_id: str, lang: Literal["fr", "en"] = "fr") -> dict:
    result = await patrol_service.start(task_id, lang)
    if not result.get("ok"):
        status = 409 if result.get("code") == "busy" else 400
        raise HTTPException(status_code=status, detail=result.get("error", "Échec"))
    return result


@router.post("/stop")
async def stop_patrol() -> dict:
    return await patrol_service.stop()
