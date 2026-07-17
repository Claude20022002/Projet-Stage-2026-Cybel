"""Tests du moteur de commandes vocales (sdk/voice_commands.py)."""

from sdk.voice_commands import (
    VOICE_COMMAND_MAP,
    build_vocabulary,
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


def test_match_voice_command_greeting() -> None:
    assert match_voice_command("bonjour") == "greeting"
    assert match_voice_command("salut") == "greeting"
    assert match_voice_command("coucou") == "greeting"


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


def test_match_point_navigation_fallback_truncated_stt() -> None:
    # Le STT contraint par grammaire tronque souvent le verbe et la préposition
    # (« va jusqu'à Stendhal » -> « jusqu stendhal ») : le mot « jusqu » seul
    # devant un point reconnu doit suffire à déclencher la navigation.
    assert match_point_navigation("jusqu stendhal", ["ENTREE-STENDHAL"]) == "ENTREE-STENDHAL"


def test_match_point_navigation_fallback_does_not_match_unknown_word() -> None:
    # "jusqu est" (destination perdue par le STT) ne doit matcher aucun point.
    assert match_point_navigation("jusqu est", ["ENTREE-STENDHAL", "PORTE-LABO"]) is None


def test_voice_command_map_targets_are_known_actions() -> None:
    # Toutes les cibles doivent correspondre à des ids d'action réels
    known = {
        "welcome_guest", "go_reception", "go_meeting_room", "wait_mode",
        "return_charge", "guided_tour", "inform_waiting", "stop_all", "greeting",
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


def test_build_vocabulary_includes_command_words() -> None:
    words = build_vocabulary()
    assert "visite" in words
    assert "guidée" in words
    assert "accueil" in words
    assert "à" in words  # préposition de _NAV_WORDS_FR, accent conservé


def test_build_vocabulary_includes_point_names_and_extra_phrases() -> None:
    words = build_vocabulary(
        point_names=["PORTE-LABO", "CNC ROUTEUR"],
        extra_phrases=["Qu'est-ce que HESTIM ?"],
    )
    assert "porte" in words
    assert "labo" in words
    assert "cnc" in words
    assert "routeur" in words
    assert "hestim" in words
    assert "qu" in words or "est" in words  # tokenisation basique sur l'apostrophe


def test_build_vocabulary_sorted_and_deduplicated() -> None:
    words = build_vocabulary(point_names=["ACCUEIL"])
    assert words == sorted(set(words))
    # "accueil" apparaît à la fois dans VOICE_COMMAND_MAP et point_names -> une seule fois
    assert words.count("accueil") == 1


def test_build_vocabulary_empty_inputs_still_returns_base_words() -> None:
    words = build_vocabulary(point_names=[], extra_phrases=[])
    assert len(words) > 0
    assert "stop" in words


def test_build_vocabulary_includes_yes_no_words() -> None:
    # Nécessaire pour les mini-dialogues (ex. "voulez-vous faire une visite ?").
    words = build_vocabulary()
    assert "oui" in words
    assert "non" in words
