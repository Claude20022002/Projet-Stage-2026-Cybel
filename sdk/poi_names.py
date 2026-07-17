"""Convention de nommage des POI (Deployment Tool / Sentrymove)."""

from __future__ import annotations

import re

# Noms de test ou brouillon à ignorer même s'ils passent le filtre.
_JUNK_NAMES = frozenset({"move", "nous", "point2", "point1", "test"})

# POI de l'ancienne carte labo — exclus même s'ils restent dans ROS / le cache.
OBSOLETE_POI_NAMES = frozenset(
    {
        "LG-10",
        "LG-09",
        "GAMME-CONTROLE-QUALITE",
    }
)

# MAJUSCULES, chiffres, tirets, espaces, accents (pas de minuscules latines).
_DEPLOYMENT_POI_RE = re.compile(
    r"^[A-Z0-9ÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ"
    r"]+(?:[- ][A-Z0-9ÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ]+)*$"
)


def is_valid_deployment_poi_name(name: str) -> bool:
    """Vrai si le nom respecte le format Deployment Tool (MAJUSCULES, mots séparés par - ou espace)."""
    cleaned = (name or "").strip()
    if not cleaned or cleaned.lower() in _JUNK_NAMES or cleaned in OBSOLETE_POI_NAMES:
        return False
    if any("a" <= ch <= "z" for ch in cleaned):
        return False
    return bool(_DEPLOYMENT_POI_RE.match(cleaned))


def is_charge_poi_name(name: str) -> bool:
    """Vrai pour les bornes / points de recharge (hors visite et kiosque visiteur)."""
    cleaned = (name or "").strip().upper()
    if not cleaned:
        return False
    return any(token in cleaned for token in ("RECHARGE", "CHARGING", "PILE"))


def is_charge_point(name: str, point_type: str | None = None) -> bool:
    if (point_type or "").lower() == "charging":
        return True
    return is_charge_poi_name(name)


def is_visitor_poi(name: str, point_type: str | None = None) -> bool:
    """POI Deployment Tool éligible accueil / visite (pas charge ni obsolète)."""
    return is_valid_deployment_poi_name(name) and not is_charge_point(name, point_type)


def filter_valid_points(points: list) -> list:
    """Ne conserve que les points au format Deployment Tool valide."""
    return [p for p in points if is_valid_deployment_poi_name(getattr(p, "name", ""))]
