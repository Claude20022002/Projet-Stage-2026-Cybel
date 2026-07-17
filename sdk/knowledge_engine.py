"""Moteur FAQ / knowledge local (JSON) — Phase 4 CYB-042."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sdk.json_store import load_json
from sdk.voice_commands import normalize_text as _normalize_text


@dataclass
class KnowledgeMatch:
    entry_id: str
    answer: str
    source: str  # lab | faq
    x: float | None = None
    y: float | None = None
    theta: float | None = None
    point_name: str | None = None
    score: float = 0.0


class KnowledgeEngine:
    def __init__(
        self,
        data_dir: Path,
        *,
        lab_knowledge_file: str = "knowledgeV2-labV2.json",
    ) -> None:
        self._data_dir = data_dir
        self._lab_knowledge_file = lab_knowledge_file
        self._lab_path = data_dir / lab_knowledge_file
        self._faq_path = data_dir / "hestim_knowledge_base.json"
        self._lab_cache: dict[str, Any] | None = None
        self._faq_cache: list[dict[str, Any]] | None = None

    def _lab_entries(self) -> dict[str, Any]:
        if self._lab_cache is None:
            self._lab_cache = load_json(self._lab_path, {})
        return self._lab_cache

    def _faq_entries(self) -> list[dict[str, Any]]:
        if self._faq_cache is None:
            document = load_json(self._faq_path, {})
            self._faq_cache = list(document.get("faq") or [])
        return self._faq_cache

    def reload(self, *, lab_knowledge_file: str | None = None) -> None:
        if lab_knowledge_file:
            self._lab_knowledge_file = lab_knowledge_file
            self._lab_path = self._data_dir / lab_knowledge_file
        self._lab_cache = None
        self._faq_cache = None

    def list_lab_entries(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for entry_id, raw in self._lab_entries().items():
            if not isinstance(raw, dict):
                continue
            items.append(
                {
                    "id": entry_id,
                    "answer": raw.get("answer", ""),
                    "keywords": raw.get("keywords", []),
                    "coordinates": raw.get("coordinates"),
                }
            )
        return items

    def list_faq(self) -> list[dict[str, Any]]:
        return [e.copy() for e in self._faq_entries()]

    def match(self, text: str, *, lang: str = "fr", point_names: list[str] | None = None) -> KnowledgeMatch | None:
        normalized = _normalize_text(text)
        if not normalized:
            return None

        tokens = set(normalized.split())
        best: KnowledgeMatch | None = None

        for entry_id, raw in self._lab_entries().items():
            if not isinstance(raw, dict):
                continue
            keywords = [str(k) for k in (raw.get("keywords") or [])]
            score = self._keyword_score(normalized, tokens, keywords + [entry_id])
            if score <= 0:
                continue
            coords = raw.get("coordinates") or {}
            candidate = KnowledgeMatch(
                entry_id=str(entry_id),
                answer=str(raw.get("answer", "")),
                source="lab",
                x=float(coords.get("x")) if coords.get("x") is not None else None,
                y=float(coords.get("y")) if coords.get("y") is not None else None,
                theta=float(coords.get("z", coords.get("theta", 0))) if coords else None,
                score=score,
            )
            if point_names:
                candidate.point_name = self._match_point_name(entry_id, keywords, point_names)
            if best is None or candidate.score > best.score:
                best = candidate

        for item in self._faq_entries():
            question = item.get("question_en" if lang == "en" else "question_fr", "")
            answer = item.get("reponse_en" if lang == "en" else "reponse_fr", "")
            q_norm = _normalize_text(str(question))
            score = self._keyword_score(normalized, tokens, q_norm.split())
            if score <= 0:
                continue
            candidate = KnowledgeMatch(
                entry_id=str(item.get("id", "faq")),
                answer=str(answer),
                source="faq",
                score=score * 0.95,
            )
            if best is None or candidate.score > best.score:
                best = candidate

        return best

    def _keyword_score(self, normalized: str, tokens: set[str], keywords: list[str]) -> float:
        score = 0.0
        for keyword in keywords:
            kw = _normalize_text(keyword)
            if not kw or len(kw) < 3:
                continue
            if kw == normalized:
                score += 3.0
            elif kw in tokens:
                score += 1.5
            elif len(kw) >= 4 and f" {kw} " in f" {normalized} ":
                score += 2.0
        return score

    def _match_point_name(self, entry_id: str, keywords: list[str], point_names: list[str]) -> str | None:
        normalized_points = {_normalize_text(name): name for name in point_names}
        candidates = [_normalize_text(entry_id), *(_normalize_text(k) for k in keywords)]
        for candidate in candidates:
            if candidate in normalized_points:
                return normalized_points[candidate]
        for norm_name, original in normalized_points.items():
            for candidate in candidates:
                if candidate and (candidate in norm_name or norm_name in candidate):
                    return original
        return None
