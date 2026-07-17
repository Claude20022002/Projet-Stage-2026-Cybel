"""Tests Phase 4 — knowledge engine."""

from pathlib import Path

import pytest

from sdk.knowledge_engine import KnowledgeEngine

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"


@pytest.fixture
def engine() -> KnowledgeEngine:
    return KnowledgeEngine(DATA)


def test_match_lab_cnc(engine: KnowledgeEngine) -> None:
    match = engine.match("montre moi la fraiseuse cnc", lang="fr")
    assert match is not None
    assert match.source == "lab"
    assert "cnc" in match.entry_id
    assert match.x is not None
    assert match.y is not None


def test_match_faq_hestim(engine: KnowledgeEngine) -> None:
    match = engine.match("Qu'est-ce que HESTIM", lang="fr")
    assert match is not None
    assert match.source == "faq"
    assert "HESTIM" in match.answer


def test_match_unknown(engine: KnowledgeEngine) -> None:
    assert engine.match("zzqwxkjl mnpqrst vbcdfgh", lang="fr") is None


def test_list_entries(engine: KnowledgeEngine) -> None:
    lab = engine.list_lab_entries()
    faq = engine.list_faq()
    assert len(lab) >= 5
    assert len(faq) >= 3


def test_point_name_resolution(engine: KnowledgeEngine) -> None:
    match = engine.match(
        "cnc routeur",
        lang="fr",
        point_names=["CNC ROUTEUR", "ACCUEIL"],
    )
    assert match is not None
    assert match.point_name == "CNC ROUTEUR"
