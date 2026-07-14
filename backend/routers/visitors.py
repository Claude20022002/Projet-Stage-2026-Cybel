import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException

from sdk.models import VisitorEnrollRequest, VisitorIdentifyRequest, VisitorIdentifyResult, VisitorPublic
from routers.kiosk import _load_config as _load_kiosk_config
from services.visitor_service import DEFAULT_THRESHOLD, visitor_service

router = APIRouter(prefix="/api/visitors", tags=["visitors"])


def _current_threshold() -> float:
    config = _load_kiosk_config()
    try:
        return float(config.get("face_recognition_threshold", DEFAULT_THRESHOLD))
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD


@router.get("", response_model=list[VisitorPublic])
async def list_visitors() -> list[VisitorPublic]:
    return visitor_service.list_public()


@router.get("/current")
async def get_current_visitor() -> dict:
    current = visitor_service.get_current()
    if current is None:
        return {"visitor": None}
    return {"visitor": current["visitor"], "confidence": current["confidence"], "at": current["at"]}


@router.post("/identify", response_model=VisitorIdentifyResult)
async def identify_visitor(body: VisitorIdentifyRequest) -> VisitorIdentifyResult:
    return visitor_service.identify(body.embedding, threshold=_current_threshold())


@router.post("/enroll", response_model=VisitorPublic)
async def enroll_visitor(body: VisitorEnrollRequest) -> VisitorPublic:
    try:
        return visitor_service.enroll(body.name, body.civility, body.embedding, body.consent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{visitor_id}")
async def delete_visitor(visitor_id: str) -> dict:
    removed = visitor_service.remove(visitor_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Visiteur '{visitor_id}' introuvable")
    return {"ok": True}
