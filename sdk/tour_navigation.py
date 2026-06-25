"""Prérequis et récupération navigation pour la visite guidée.

Sans import ``sdk.*`` pour rester chargeable sur Termux lite (pas de pydantic).
"""
from __future__ import annotations

import math
from typing import Sequence

DEFAULT_LOCALIZATION_MIN_PERCENT = 60.0
GOAL_TOLERANCE_M = 0.45
VELOCITY_STOP_THRESHOLD = 0.05

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
    605: (
        "Robot en recharge sur la borne — éloignez-le du socle ou attendez "
        "la fin de charge avant de naviguer."
    ),
}


def navigation_failure_message(nav_status: int, *, destination: str = "") -> str:
    hint = NAV_STATUS_HINTS.get(nav_status, f"Code navigation {nav_status}")
    if destination:
        return f"{hint} (destination : {destination})"
    return hint


def navigation_precondition_detail(
    *,
    connected: bool,
    soft_estop: bool,
    nav_status: int,
    nav_mode: str = "",
    localization_percent: float | None = None,
    min_localization: float = DEFAULT_LOCALIZATION_MIN_PERCENT,
    point_name: str | None = None,
) -> str | None:
    """Raison explicite si une navigation doit être refusée, sinon ``None``."""
    if not connected:
        return "Liaison rosbridge coupée (reconnexion en cours)"
    if soft_estop:
        return "E-Stop actif — relâchez l'arrêt d'urgence avant de naviguer"
    if nav_mode == "manual":
        return (
            "Mode manuel actif — passez en mode automatique avant de naviguer "
            "(bouton Auto ou relâchez la téléopération)"
        )
    if nav_status == 600:
        return NAV_STATUS_HINTS[600]
    if nav_status == 604:
        return (
            f"{NAV_STATUS_HINTS[604]} Annulez la navigation en cours puis relocalisez."
        )
    if nav_status == 602:
        return (
            "Navigation déjà en cours — attendez l'arrivée ou annulez avant un nouvel objectif"
        )
    if nav_status not in (601, 603):
        dest = f" vers « {point_name} »" if point_name else ""
        return f"État navigation inattendu ({nav_status}){dest}"
    if localization_percent is not None and localization_percent < min_localization:
        return (
            f"Localisation insuffisante ({localization_percent:.0f} % < "
            f"{min_localization:.0f} %) — relocalisez le robot"
        )
    return None


def navigation_recovery_hint(nav_status: int) -> str:
    """Conseil opérateur après échec ou blocage navigation (CYB-061)."""
    return {
        604: (
            "Dégagez le passage, relocalisez le robot depuis le contrôleur, "
            "puis relancez la navigation."
        ),
        600: "Placez le robot dans une zone connue et lancez la relocalisation.",
        601: (
            "Le robot n'a pas démarré — vérifiez le mode automatique et la destination sur la carte."
        ),
        602: "Attendez la fin du déplacement ou annulez la navigation en cours.",
    }.get(nav_status, "Consultez le diagnostic connexion (Paramètres) si le problème persiste.")


def pose_distance_to_goal(
    pose_x: float,
    pose_y: float,
    goal_x: float | None,
    goal_y: float | None,
) -> float | None:
    if goal_x is None or goal_y is None:
        return None
    return math.hypot(pose_x - goal_x, pose_y - goal_y)


def evaluate_navigation_arrival(
    *,
    nav_status: int,
    saw_active: bool,
    pose_x: float,
    pose_y: float,
    goal_x: float | None,
    goal_y: float | None,
    velocity: tuple[float, float],
    tolerance: float = GOAL_TOLERANCE_M,
) -> bool:
    """Combine nav_status, proximité objectif et vitesse nulle (CYB-061)."""
    distance = pose_distance_to_goal(pose_x, pose_y, goal_x, goal_y)
    if distance is not None and distance <= tolerance:
        return True
    if nav_status == 604:
        return False
    if saw_active and nav_status == 603:
        if distance is None or distance <= tolerance:
            vx, vy = velocity[0], velocity[1]
            if abs(vx) < VELOCITY_STOP_THRESHOLD and abs(vy) < VELOCITY_STOP_THRESHOLD:
                return True
    return False


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
            "matching_degree",
            "match_degree",
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


CHARGING_NAV_STATUS = 605


def is_charging_navigation_block(nav_status: int) -> bool:
    """605 observé sur TY1251D lorsque le robot est sur la borne de recharge."""
    return nav_status == CHARGING_NAV_STATUS


def charging_navigation_message() -> str:
    return NAV_STATUS_HINTS[CHARGING_NAV_STATUS]


def is_ghost_navigation(
    nav_status: int,
    *,
    velocity: Sequence[float] | None = None,
    navigating_to: str | None = None,
) -> bool:
    """602 sans cible ni mouvement — état bloquant fréquent après annulation ratée."""
    if nav_status != 602:
        return False
    if navigating_to:
        return False
    if velocity:
        vx = float(velocity[0]) if velocity else 0.0
        vy = float(velocity[1]) if len(velocity) > 1 else 0.0
        if abs(vx) >= VELOCITY_STOP_THRESHOLD or abs(vy) >= VELOCITY_STOP_THRESHOLD:
            return False
    return True


def assess_tour_readiness(
    nav_status: int,
    localization_percent: float | None,
    *,
    min_localization: float = DEFAULT_LOCALIZATION_MIN_PERCENT,
    require_known_localization: bool = False,
    velocity: Sequence[float] | None = None,
    navigating_to: str | None = None,
    ghost_nav_recovered: bool = False,
    charger: bool = False,
    charging_recovered: bool = False,
) -> tuple[bool, str]:
    """Vérifie si le robot peut démarrer une visite."""
    if nav_status == 600:
        return False, NAV_STATUS_HINTS[600]
    if is_charging_navigation_block(nav_status):
        if charging_recovered:
            pass
        else:
            return False, charging_navigation_message()
    if nav_status == 604:
        return False, (
            f"{NAV_STATUS_HINTS[604]} "
            "Annulez la navigation en cours, relocalisez le robot, puis relancez la visite."
        )
    if nav_status == 602:
        if is_ghost_navigation(
            nav_status, velocity=velocity, navigating_to=navigating_to
        ):
            if ghost_nav_recovered:
                pass
            else:
                return False, (
                    "Navigation fantôme (602) — le robot croit être en déplacement "
                    "mais est immobile. Annulez la navigation puis relancez la visite."
                )
        else:
            return False, (
                "Navigation déjà en cours — attendez l'arrivée ou annulez "
                "avant de lancer une visite."
            )
    nav_ok = nav_status in (601, 603) or (
        nav_status == 602
        and ghost_nav_recovered
        and is_ghost_navigation(
            nav_status, velocity=velocity, navigating_to=navigating_to
        )
    )
    if not nav_ok:
        return False, (
            f"État navigation inattendu ({nav_status}). "
            "Attendez que le robot soit prêt (601) avant de lancer la visite."
        )
    if require_known_localization and localization_percent is None:
        return False, (
            "Localisation inconnue — placez le robot sur la carte et lancez la relocalisation."
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
