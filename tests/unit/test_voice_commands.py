"""Tests du moteur de commandes vocales (sdk/voice_commands.py)."""

from sdk.voice_commands import (
    VOICE_COMMAND_MAP,
    match_point_navigation,
    match_voice_command,
    normalize_text,
)


def test_normalize_strips_accents_and_punctuation() -> None:
    assert normalize_text("Éàù CNC-Routeur !") == "eau cnc routeur"
    assert normalize_text("  L'accueil  ") == "l accueil"


def test_match_voice_command_exact() -> None:
    assert match_voice_command("accueil") == "welcome_guest"
    assert match_voice_command("stop") == "stop_all"


def test_match_voice_command_substring() -> None:
    assert match_voice_command("peux-tu lancer la visite guidée maintenant") == "guided_tour"
    assert match_voice_command("s'il te plaît arrête tout") == "stop_all"


def test_match_voice_command_longest_wins() -> None:
    # « visite guidée » (plus long) doit l'emporter sur « visite »
    assert match_voice_command("je veux la visite guidée") == "guided_tour"


def test_match_voice_command_unknown() -> None:
    assert match_voice_command("quelle heure est-il") is None


def test_match_point_navigation_basic() -> None:
    points = ["PORTE-LABO", "CNC ROUTEUR", "ACCUEIL"]
    assert match_point_navigation("va à la porte labo", points) == "PORTE-LABO"
    assert match_point_navigation("conduis-moi vers le cnc routeur", points) == "CNC ROUTEUR"


def test_match_point_navigation_accent_insensitive() -> None:
    assert match_point_navigation("emmène-moi à l'accueil", ["ACCUEIL"]) == "ACCUEIL"


def test_match_point_navigation_no_nav_verb() -> None:
    # Pas de verbe de déplacement → pas de match navigation
    assert match_point_navigation("la porte labo est fermée", ["PORTE-LABO"]) is None


def test_match_point_navigation_unknown_point() -> None:
    assert match_point_navigation("va à la cafétéria", ["PORTE-LABO"]) is None


def test_voice_command_map_targets_are_known_actions() -> None:
    # Toutes les cibles doivent correspondre à des ids d'action réels
    known = {
        "welcome_guest", "go_reception", "go_meeting_room", "wait_mode",
        "return_charge", "guided_tour", "inform_waiting", "stop_all",
    }
    assert set(VOICE_COMMAND_MAP.values()) <= known


def test_reception_actions_reexports_still_work() -> None:
    # Rétrocompat : reception_actions doit continuer d'exposer les mêmes symboles
    from sdk.reception_actions import (  # noqa: F401
        VOICE_COMMAND_MAP as reexport_map,
        _normalize_text,
        match_point_navigation as reexport_nav,
        match_voice_command as reexport_cmd,
    )

    assert reexport_map is VOICE_COMMAND_MAP
    assert reexport_cmd("stop") == "stop_all"
    assert _normalize_text("Café") == "cafe"
    assert reexport_nav("va au poste machine", ["POSTE-MACHINE"]) == "POSTE-MACHINE"
