"""Façade knowledge JSON — Phase 4 CYB-042."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config import settings
from sdk.knowledge_engine import KnowledgeEngine


class KnowledgeService:
    def __init__(self) -> None:
        self._engine = KnowledgeEngine(settings.data_dir)

    def reload(self) -> None:
        self._engine.reload()

    def list_lab_entries(self) -> list[dict]:
        return self._engine.list_lab_entries()

    def list_faq(self) -> list[dict]:
        return self._engine.list_faq()

    def ask(self, text: str, *, lang: str = "fr", point_names: list[str] | None = None) -> dict | None:
        match = self._engine.match(text, lang=lang, point_names=point_names)
        if not match or match.score < 2.0:
            return None
        payload: dict = {
            "entry_id": match.entry_id,
            "answer": match.answer,
            "source": match.source,
            "score": match.score,
            "point_name": match.point_name,
        }
        if match.x is not None and match.y is not None:
            payload["coordinates"] = {
                "x": match.x,
                "y": match.y,
                "theta": match.theta or 0.0,
            }
        return payload


knowledge_service = KnowledgeService()
