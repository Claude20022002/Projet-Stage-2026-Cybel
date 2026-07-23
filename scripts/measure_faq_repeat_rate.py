#!/usr/bin/env python3
"""
measure_faq_repeat_rate.py — mesure le taux de succès du moteur FAQ (sdk/knowledge_engine.py)
sur des reformulations des questions HESTIM (data/hestim_knowledge_base.json).

Ne nécessite pas le robot : KnowledgeEngine.match() est du Python pur, testable hors-ligne.
Chaque question canonique de la FAQ est associée à plusieurs reformulations plausibles
(façons dont un visiteur ou le STT embarqué pourrait la phraser différemment). Un essai est
un succès si match() retourne l'entrée FAQ attendue avec un score franchissant le seuil réel
utilisé en production (< 2.0 rejeté, cf. scripts/termux/cybel_lite.py).

Usage :
  python scripts/measure_faq_repeat_rate.py
  python scripts/measure_faq_repeat_rate.py --lang en

Sortie : résumé console + data/faq_repeat_rate.json, avec la ligne \\ph{} prête à copier
dans paper/icra_2027/main.tex.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk.knowledge_engine import KnowledgeEngine  # noqa: E402

FAQ_SCORE_THRESHOLD = 2.0  # aligné sur scripts/termux/cybel_lite.py:2013

# Reformulations plausibles par id de question canonique (data/hestim_knowledge_base.json).
PARAPHRASES_FR: dict[str, list[str]] = {
    "presentation": [
        "C'est quoi HESTIM ?",
        "Pouvez-vous me présenter HESTIM ?",
        "Parlez-moi de HESTIM",
        "HESTIM c'est quoi exactement ?",
    ],
    "localisation": [
        "Où est situé le campus ?",
        "L'école se trouve où ?",
        "Quelle est l'adresse de HESTIM ?",
        "Où se situe HESTIM ?",
    ],
    "ecoles": [
        "Combien d'écoles y a-t-il à HESTIM ?",
        "Quelles sont les écoles de HESTIM ?",
        "HESTIM regroupe quelles écoles ?",
        "Quelles écoles compose HESTIM ?",
    ],
    "filieres_ingenierie": [
        "Quelles sont les filières d'ingénierie ?",
        "Que peut-on étudier à l'école d'ingénieurs ?",
        "Les filières de l'école d'ingénierie sont lesquelles ?",
        "Quelles filières d'ingénieur propose HESTIM ?",
    ],
    "filieres_business": [
        "Quelles filières à l'école de commerce ?",
        "Que propose la business school ?",
        "Les filières de l'école de commerce sont quoi ?",
        "Quelles filières de commerce propose HESTIM ?",
    ],
    "direction": [
        "Qui est le directeur de HESTIM ?",
        "Qui est à la tête de l'école ?",
        "Qui dirige l'établissement ?",
        "Qui est le directeur général de HESTIM ?",
    ],
    "valeurs": [
        "Quelles valeurs défend HESTIM ?",
        "Les valeurs de l'école sont lesquelles ?",
        "HESTIM a quelles valeurs ?",
        "Quelles sont les valeurs de l'établissement ?",
    ],
    "contact": [
        "Comment puis-je contacter HESTIM ?",
        "Quel est le numéro pour contacter HESTIM ?",
        "Comment joindre l'école ?",
        "Comment vous contacter ?",
    ],
    "incubateur": [
        "Est-ce que HESTIM aide à entreprendre ?",
        "HESTIM a-t-il un incubateur ?",
        "Y a-t-il un accompagnement entrepreneurial à HESTIM ?",
        "HESTIM aide-t-il les entrepreneurs ?",
    ],
    "recherche": [
        "Est-ce que HESTIM fait de la recherche ?",
        "HESTIM a-t-il un centre de recherche ?",
        "Y a-t-il de la recherche à HESTIM ?",
        "HESTIM fait de la recherche scientifique ?",
    ],
    "international": [
        "Est-ce que HESTIM a des partenariats à l'international ?",
        "HESTIM a des partenaires internationaux ?",
        "Y a-t-il des échanges internationaux à HESTIM ?",
        "HESTIM a-t-il des accords avec des écoles étrangères ?",
    ],
    "campus": [
        "Quelle est la taille du campus ?",
        "Le campus fait quelle surface ?",
        "Est-ce que le campus est grand ?",
        "Le campus est-il spacieux ?",
    ],
}

PARAPHRASES_EN: dict[str, list[str]] = {
    "presentation": [
        "What exactly is HESTIM?",
        "Can you tell me about HESTIM?",
        "Tell me about HESTIM",
        "What does HESTIM do?",
    ],
    "localisation": [
        "Where is the campus located?",
        "Where can I find the school?",
        "What is HESTIM's address?",
        "Where is HESTIM situated?",
    ],
}


def run(lang: str) -> dict:
    engine = KnowledgeEngine(ROOT / "data")
    paraphrases = PARAPHRASES_FR if lang == "fr" else PARAPHRASES_EN

    results: list[dict] = []
    for entry_id, variants in paraphrases.items():
        for text in variants:
            match = engine.match(text, lang=lang)
            success = bool(
                match is not None
                and match.score >= FAQ_SCORE_THRESHOLD
                and match.entry_id == entry_id
            )
            results.append(
                {
                    "expected_id": entry_id,
                    "text": text,
                    "matched_id": match.entry_id if match else None,
                    "score": round(match.score, 2) if match else 0.0,
                    "success": success,
                }
            )
            mark = "OK" if success else "ECHEC"
            got = match.entry_id if match else "(aucun)"
            score = f"{match.score:.2f}" if match else "0.00"
            print(f"  [{mark}] « {text} » -> {got} (score {score}, attendu {entry_id})")

    n_total = len(results)
    n_ok = sum(1 for r in results if r["success"])
    rate = round(100 * n_ok / n_total, 1) if n_total else 0.0

    failures = [r for r in results if not r["success"]]

    print(f"\n{'=' * 66}")
    print(f"  Taux de succès FAQ (reformulations) : {rate}%  ({n_ok}/{n_total} essais)")
    if failures:
        print(f"  Échecs ({len(failures)}) :")
        for f in failures:
            print(f"    - « {f['text']} » (attendu {f['expected_id']}, obtenu {f['matched_id']})")
    print(f"\n  -> Dans main.tex, remplacez :")
    print(f"      \\ph{{repeat-question success rate, N trials}}")
    print(f"      par  {rate}\\% ({n_total} trials)")
    print(f"{'=' * 66}")

    return {
        "lang": lang,
        "score_threshold": FAQ_SCORE_THRESHOLD,
        "trials": n_total,
        "successes": n_ok,
        "success_rate_pct": rate,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", default="fr", choices=["fr", "en"])
    args = parser.parse_args()

    summary = run(args.lang)

    output = ROOT / "data" / "faq_repeat_rate.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRésultats sauvegardés -> {output}")


if __name__ == "__main__":
    # Force UTF-8 sur stdout (evite un affichage corrompu sur Windows/cp1252)
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
