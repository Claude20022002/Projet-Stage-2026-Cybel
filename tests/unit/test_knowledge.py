"""Tests Phase 4 — knowledge engine."""

import sys
from pathlib import Path

import pytest

from sdk.knowledge_engine import KnowledgeEngine

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


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


def test_faq_repeat_question_rate_stays_reasonable(engine: KnowledgeEngine) -> None:
    """Régression pour le taux de succès FAQ rapporté dans le papier ICRA 2027
    (paper/icra_2027/main.tex) — mesuré par scripts/measure_faq_repeat_rate.py.
    Un score bien en-dessous de la mesure de référence signalerait une régression
    du matching, pas juste une reformulation malchanceuse."""
    from measure_faq_repeat_rate import FAQ_SCORE_THRESHOLD, PARAPHRASES_FR

    n_total = 0
    n_ok = 0
    for entry_id, variants in PARAPHRASES_FR.items():
        for text in variants:
            match = engine.match(text, lang="fr")
            n_total += 1
            if match is not None and match.score >= FAQ_SCORE_THRESHOLD and match.entry_id == entry_id:
                n_ok += 1

    rate = 100 * n_ok / n_total
    assert n_total == 48
    assert rate >= 40.0
