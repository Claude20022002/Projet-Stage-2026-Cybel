import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException

from sdk.models import KnowledgeAskRequest
from services.knowledge_service import knowledge_service
from services.persistence_service import persistence_service

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/entries")
async def list_entries() -> dict:
    return {
        "lab": knowledge_service.list_lab_entries(),
        "faq": knowledge_service.list_faq(),
    }


@router.get("/faq")
async def get_faq() -> list[dict]:
    return knowledge_service.list_faq()


@router.post("/ask")
async def ask_knowledge(request: KnowledgeAskRequest) -> dict:
    point_names = [p.name for p in persistence_service.load_points()]
    result = knowledge_service.ask(
        request.text,
        lang=request.lang,
        point_names=point_names or None,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Aucune réponse trouvée")
    return result
