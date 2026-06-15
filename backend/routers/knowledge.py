import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter

KNOWLEDGE_BASE_PATH = ROOT / "data" / "hestim_knowledge_base.json"

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/faq")
async def get_faq() -> list[dict]:
    with open(KNOWLEDGE_BASE_PATH, encoding="utf-8") as f:
        knowledge_base = json.load(f)
    return knowledge_base.get("faq", [])
