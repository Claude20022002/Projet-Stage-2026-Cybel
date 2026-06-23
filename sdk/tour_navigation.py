"""Prérequis et récupération navigation pour la visite guidée.

Sans import ``sdk.*`` pour rester chargeable sur Termux lite (pas de pydantic).
"""
from __future__ import annotations

DEFAULT_LOCALIZATION_MIN_PERCENT = 60.0

NAV_STATUS_HINTS: dict[int, str] = {
    600: "Robot non localisé — utilisez Relocaliser avant de naviguer.",
    601: "Prêt à naviguer.",
    602: "Navigation en cours.",
    603: "Destination atteinte.",
    604: (
        "Échec de navigation — obstacle, chemin bloqué, destination inaccessible "
        "ou localisation insuffisante. Dégagez le passage, relocalisez le robot, "
        "puis relancez."
    ),
}


def navigation_failure_message(nav_status: int, *, destination: str = "") -> str:
    hint = NAV_STATUS_HINTS.get(nav_status, f"Code navigation {nav_status}")
    if destination:
        return f"{hint} (destination : {destination})"
    return hint


def normalize_localization_percent(value: float) -> float:
    """Normalise un score de localisation (0–1 ou 0–100) en pourcentage."""
    if value <= 1.0:
        return round(value * 100.0, 1)
    return round(min(max(value, 0.0), 100.0), 1)


def parse_localization_percent(status_msg: dict, loc_msg: dict | None = None) -> float | None:
    """Extrait le pourcentage de localisation depuis les messages ROS."""
    sources: list[dict] = []
    if loc_msg:
        sources.append(loc_msg)
    sources.append(status_msg)
    for msg in sources:
        for key in (
            "data",
            "confidence",
            "localization_percent",
            "localization",
            "location_score",
            "score",
            "percent",
        ):
            raw = msg.get(key)
            if raw is None:
                continue
            try:
                return normalize_localization_percent(float(raw))
            except (TypeError, ValueError):
                continue
    return None


def assess_tour_readiness(
    nav_status: int,
    localization_percent: float | None,
    *,
    min_localization: float = DEFAULT_LOCALIZATION_MIN_PERCENT,
) -> tuple[bool, str]:
    """Vérifie si le robot peut démarrer une visite."""
    if nav_status == 600:
        return False, NAV_STATUS_HINTS[600]
    if nav_status == 604:
        return False, (
            f"{NAV_STATUS_HINTS[604]} "
            "Annulez la navigation en cours, relocalisez le robot, puis relancez la visite."
        )
    if nav_status == 602:
        return False, (
            "Navigation fantôme (602) — le robot croit être en déplacement mais est immobile. "
            "Annulez la navigation puis relancez la visite."
        )
    if nav_status not in (601, 603):
        return False, (
            f"État navigation inattendu ({nav_status}). "
            "Attendez que le robot soit prêt (601) avant de lancer la visite."
        )
    if localization_percent is not None and localization_percent < min_localization:
        return False, (
            f"Localisation insuffisante ({localization_percent:.0f} % < {min_localization:.0f} %). "
            "Placez le robot dans une zone connue et lancez la relocalisation."
        )
    return True, ""


def navigation_wait_failure_message(
    nav_status: int,
    *,
    destination: str = "",
    never_started: bool = False,
    distance_to_target_m: float | None = None,
) -> str:
    """Message d'échec après attente d'arrivée (évite de confondre 601 et 604)."""
    if never_started or nav_status == 601:
        dest = f" vers {destination}" if destination else ""
        extra = ""
        if distance_to_target_m is not None:
            extra = f" Distance résiduelle : {distance_to_target_m:.2f} m."
        return (
            f"Le robot n'a pas démarré la navigation{dest} "
            f"(statut {nav_status}, objectif ignoré ou mode incorrect).{extra} "
            "Relocalisez, vérifiez le mode automatique et réessayez."
        )
    if nav_status == 600:
        return navigation_failure_message(600, destination=destination)
    return navigation_failure_message(nav_status, destination=destination)
