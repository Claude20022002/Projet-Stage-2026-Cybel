#!/usr/bin/env python3
"""Construit le dépôt d'artefacts anonyme accompagnant l'article ICRA 2027.

Le dépôt de travail contient l'historique git, les noms des auteurs, le nom de
l'établissement et des chemins locaux. Aucun de ces éléments n'a sa place dans
un artefact de soumission en double aveugle, et un service d'anonymisation
d'URL ne nettoie que l'adresse, pas le contenu.

Ce script produit une copie autonome ne contenant que ce que l'article déclare
publier : les scripts d'exploration, la description de l'interface reconstruite,
et les journaux derrière les résultats. Il remplace les jetons identifiants,
puis vérifie qu'il n'en reste aucun avant de rendre la main.

    python scripts/build_artifact.py                # -> ../artifact-icra2027
    python scripts/build_artifact.py --out CHEMIN

Le dossier produit ne contient pas de dépôt git : initialisez-le à neuf pour
qu'aucun historique ne remonte.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Fichiers repris tels quels. Chaque entrée doit être justifiable par une
# affirmation de l'article : si rien ne s'y appuie, elle n'a rien à faire ici.
MANIFEST: list[tuple[str, str]] = [
    # Scripts d'exploration et de mesure
    ("scripts/collect_paper_data.py",     "scripts/collect_paper_data.py"),
    ("scripts/test_poi_nav.py",           "scripts/test_poi_nav.py"),
    ("scripts/measure_voice_latency.py",  "scripts/measure_voice_latency.py"),
    ("scripts/measure_faq_repeat_rate.py","scripts/measure_faq_repeat_rate.py"),
    ("scripts/introspect.py",             "scripts/introspect.py"),
    # Description de l'interface reconstruite + moteur nécessaire au résultat FAQ.
    # sdk/__init__.py n'est PAS repris : celui du dépôt de travail importe
    # avidement MockRobot, RealRobot et leurs dépendances, qui n'ont pas leur
    # place ici et casseraient l'import. On en génère un vide (voir plus bas).
    ("sdk/constants.py",                  "sdk/constants.py"),
    ("sdk/knowledge_engine.py",           "sdk/knowledge_engine.py"),
    ("sdk/voice_commands.py",             "sdk/voice_commands.py"),
    ("sdk/json_store.py",                 "sdk/json_store.py"),
    # Recalcul des statistiques citées
    ("paper/icra_2027/tools/stats.py",    "tools/stats.py"),
    # Journaux derrière les résultats
    ("data/paper_metrics.json",           "data/paper_metrics.json"),
    ("data/navigation_events.json",       "data/navigation_events.json"),
    ("data/faq_repeat_rate.json",         "data/faq_repeat_rate.json"),
    ("data/points.json",                  "data/points.json"),
    ("data/lab_tour.json",                "data/lab_tour.json"),
    ("data/hestim_knowledge_base.json",   "data/knowledge_base.json"),
    # Presentation de l'artefact, redigee a la main et versionnee cote source :
    # le dossier de sortie est efface a chaque construction.
    ("paper/icra_2027/artifact/README.md", "README.md"),
]

LOG_DIRS = [("data/logs/voice", "data/logs/voice"),
            ("data/logs/tour",  "data/logs/tour")]

# Substitutions appliquées au contenu texte. L'ordre compte : du plus long au
# plus court, pour éviter qu'une règle courte ne morde sur une plus longue.
SUBSTITUTIONS: list[tuple[str, str]] = [
    (r"hestim_knowledge_base", "knowledge_base"),
    # Établissement. On garde une forme de nom propre pour ne pas casser la
    # grammaire des phrases françaises de la base de connaissances.
    (r"HESTIM",     "INSTITUT"),
    (r"Hestim",     "Institut"),
    (r"hestim",     "institut"),
    # Lieu.
    (r"Casablanca", "METROPOLE"),
    (r"casablanca", "metropole"),
    (r"Maroc",      "PAYS"),
    (r"maroc",      "pays"),
    # Applications du constructeur : l'article les désigne génériquement.
    (r"SentryMove", "DeploymentTool"),
    (r"Sentrymove", "DeploymentTool"),
    (r"sentrymove", "deployment_tool"),
    (r"WelcomePatrol", "WelcomeApp"),
    (r"welcomepatrol", "welcome_app"),
]

# Ce qui ne doit subsister nulle part dans la sortie.
FORBIDDEN = re.compile(
    r"hestim|casablanca|morocco|maroc|clusa|lusamote|kimfuta|"
    r"\btula\b|ciot|ty1251|welcomepatrol|sentrymove|"
    r"[A-Za-z]:\\Users\\|Projet-Stage-2026",
    re.IGNORECASE,
)

TEXT_SUFFIXES = {".py", ".json", ".log", ".md", ".txt", ".cfg", ".toml"}


def scrub(text: str) -> str:
    for pattern, repl in SUBSTITUTIONS:
        text = re.sub(pattern, repl, text)
    return text


def copy_file(src: Path, dst: Path, counters: dict) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in TEXT_SUFFIXES:
        raw = src.read_text(encoding="utf-8", errors="replace")
        cleaned = scrub(raw)
        if cleaned != raw:
            counters["scrubbed"] += 1
        dst.write_text(cleaned, encoding="utf-8")
    else:
        shutil.copy2(src, dst)
    counters["copied"] += 1


def verify(out: Path) -> list[str]:
    """Relit toute la sortie et signale le moindre jeton identifiant restant."""
    hits: list[str] = []
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in {".pyc", ".pyo"} or "__pycache__" in path.parts:
            hits.append(f"{path.relative_to(out)}: bytecode compilé — "
                        f"contient le chemin source absolu, donc l'utilisateur")
            continue
        try:
            # latin1 ne rejette aucun octet : on inspecte aussi les binaires,
            # où un chemin absolu se lit tout aussi bien que dans du texte.
            text = path.read_bytes().decode("latin1")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            m = FORBIDDEN.search(line)
            if m:
                hits.append(f"{path.relative_to(out)}:{n}: {m.group(0)!r}")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT.parent / "artifact-icra2027")
    args = ap.parse_args()
    out: Path = args.out.resolve()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    counters = {"copied": 0, "scrubbed": 0, "missing": 0}

    for rel_src, rel_dst in MANIFEST:
        src = ROOT / rel_src
        if not src.is_file():
            print(f"  ABSENT  {rel_src}")
            counters["missing"] += 1
            continue
        copy_file(src, out / rel_dst, counters)

    for rel_src, rel_dst in LOG_DIRS:
        src_dir = ROOT / rel_src
        if not src_dir.is_dir():
            print(f"  ABSENT  {rel_src}/")
            counters["missing"] += 1
            continue
        for f in sorted(src_dir.glob("*.log")):
            copy_file(f, out / rel_dst / f.name, counters)

    # .gitignore : un simple import cree des __pycache__, et les .pyc portent
    # le chemin absolu du fichier source — donc le nom d'utilisateur.
    (out / ".gitignore").write_text(
        "\n".join(["__pycache__/", "*.py[cod]", ".venv/", ""]), encoding="utf-8")
    counters["copied"] += 1

    # Paquet sdk minimal : le __init__ du dépôt de travail tire tout le SDK.
    (out / "sdk" / "__init__.py").write_text(
        '"""Subset of the robot SDK needed to reproduce the results in this repository."""\n',
        encoding="utf-8")
    counters["copied"] += 1

    print(f"\n{counters['copied']} fichiers copiés, "
          f"{counters['scrubbed']} nettoyés, {counters['missing']} manquants")

    hits = verify(out)
    if hits:
        print(f"\nECHEC — {len(hits)} jeton(s) identifiant(s) restant(s) :")
        for h in hits[:25]:
            print(f"  {h}")
        return 1

    print("Verification : aucun jeton identifiant dans la sortie.")
    print(f"\nDossier : {out}")
    print("Initialisez un depot NEUF (sans historique) :")
    print(f"  cd {out} && git init && git add -A && git commit -m \"Artifact\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
