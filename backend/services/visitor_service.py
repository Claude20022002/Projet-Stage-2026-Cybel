"""Reconnaissance faciale — matching des embeddings visiteurs (Phase 2 face-presence)."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk.json_store import utc_now_iso
from sdk.models import Visitor, VisitorIdentifyResult, VisitorPublic
from sdk.visitor_utils import find_best_match, validate_embedding
from services.persistence_service import persistence_service

DEFAULT_THRESHOLD = 0.82


class VisitorService:
    def __init__(self) -> None:
        self._current: dict | None = None

    def list_public(self) -> list[VisitorPublic]:
        return [
            VisitorPublic.model_validate(v.model_dump())
            for v in persistence_service.load_visitors()
        ]

    def identify(
        self, embedding: list[float], *, threshold: float = DEFAULT_THRESHOLD
    ) -> VisitorIdentifyResult:
        if not validate_embedding(embedding):
            return VisitorIdentifyResult(ok=False, message="Embedding invalide")

        visitors = persistence_service.load_visitors()
        candidates = [(v.id, v.embedding) for v in visitors]
        visitor_id, score = find_best_match(embedding, candidates, threshold)

        if visitor_id is None:
            return VisitorIdentifyResult(ok=False, confidence=score, message="Visiteur inconnu")

        matched = next(v for v in visitors if v.id == visitor_id)
        matched.last_identified_at = utc_now_iso()
        persistence_service.upsert_visitor(matched)

        public = VisitorPublic.model_validate(matched.model_dump())
        self._current = {"visitor": public, "confidence": score, "at": matched.last_identified_at}
        return VisitorIdentifyResult(ok=True, visitor=public, confidence=score)

    def enroll(
        self, name: str, civility: str, embedding: list[float], consent: bool
    ) -> VisitorPublic:
        if not consent:
            raise ValueError("Le consentement du visiteur est requis pour l'enrôlement")
        if not validate_embedding(embedding):
            raise ValueError("Embedding invalide")

        visitor = Visitor(
            id=str(uuid.uuid4()),
            name=name,
            civility=civility,
            consent=consent,
            enrolled_at=utc_now_iso(),
            embedding=embedding,
        )
        persistence_service.upsert_visitor(visitor)
        return VisitorPublic.model_validate(visitor.model_dump())

    def get_current(self, *, ttl_seconds: float = 120.0) -> dict | None:
        if self._current is None:
            return None
        from datetime import datetime, timezone

        at = datetime.fromisoformat(self._current["at"])
        age = (datetime.now(timezone.utc) - at).total_seconds()
        if age > ttl_seconds:
            return None
        return self._current

    def remove(self, visitor_id: str) -> bool:
        removed = persistence_service.remove_visitor(visitor_id)
        if removed and self._current and self._current["visitor"].id == visitor_id:
            self._current = None
        return removed


visitor_service = VisitorService()
