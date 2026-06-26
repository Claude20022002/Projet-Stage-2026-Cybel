"""Convention de nommage des POI (Deployment Tool / Sentrymove)."""

from __future__ import annotations

import re

# Noms de test ou brouillon à ignorer même s'ils passent le filtre.
_JUNK_NAMES = frozenset({"move", "nous", "point2", "point1", "test"})

# MAJUSCULES, chiffres, tirets, espaces, accents (pas de minuscules latines).
_DEPLOYMENT_POI_RE = re.compile(
    r"^[A-Z0-9ÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ"
    r"]+(?:[- ][A-Z0-9ÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ]+)*$"
)


def is_valid_deployment_poi_name(name: str) -> bool:
    """Vrai si le nom respecte le format Deployment Tool (MAJUSCULES, mots séparés par - ou espace)."""
    cleaned = (name or "").strip()
    if not cleaned or cleaned.lower() in _JUNK_NAMES:
        return False
    if any("a" <= ch <= "z" for ch in cleaned):
        return False
    return bool(_DEPLOYMENT_POI_RE.match(cleaned))


def filter_valid_points(points: list) -> list:
    """Ne conserve que les points au format Deployment Tool valide."""
    return [p for p in points if is_valid_deployment_poi_name(getattr(p, "name", ""))]
