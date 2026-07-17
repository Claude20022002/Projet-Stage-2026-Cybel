"""Reconnaissance de commandes vocales — matching texte → action / point / FAQ.

Module volontairement SANS pydantic (ni aucun import de sdk.models), pour être
chargeable tel quel par le backend embarqué Termux (`cybel_lite.py`) via le shim
`_load_sdk_module_from_file`, exactement comme `people_utils` et `visitor_utils`.

`sdk/reception_actions.py` et `sdk/knowledge_engine.py` ré-importent depuis ici
pour éviter toute duplication (le matching vocal était historiquement défini dans
`reception_actions`, qui dépend de pydantic via DEFAULT_ACTIONS).
"""

from __future__ import annotations

import re
import unicodedata

# Mots/phrases déclencheurs → identifiant d'action (voir scripts/termux/actions.json
# et sdk/reception_actions.DEFAULT_ACTIONS). Trié par longueur décroissante au moment
# du matching pour que « visite guidée » l'emporte sur « visite ».
VOICE_COMMAND_MAP: dict[str, str] = {
    "accueil": "welcome_guest",
    "accueillir": "welcome_guest",
    "visiteur": "welcome_guest",
    "bienvenue": "welcome_guest",
    "accueil point": "go_reception",
    "aller accueil": "go_reception",
    "va à l'accueil": "go_reception",
    "salle": "go_meeting_room",
    "salle a": "go_meeting_room",
    "réunion": "go_meeting_room",
    "attente": "wait_mode",
    "attendre": "wait_mode",
    "pile": "return_charge",
    "charge": "return_charge",
    "recharge": "return_charge",
    "visite": "guided_tour",
    "visite guidée": "guided_tour",
    "arrête": "stop_all",
    "stop": "stop_all",
    "arrêter": "stop_all",
}


def match_voice_command(text: str) -> str | None:
    """Retourne l'id d'action déclenché par la commande, ou None."""
    normalized = text.lower().strip()
    if normalized in VOICE_COMMAND_MAP:
        return VOICE_COMMAND_MAP[normalized]
    for phrase, action_id in sorted(VOICE_COMMAND_MAP.items(), key=lambda x: -len(x[0])):
        if phrase in normalized:
            return action_id
    return None


def normalize_text(text: str) -> str:
    """Minuscules, sans accents, sans ponctuation, espaces normalisés."""
    decomposed = unicodedata.normalize("NFD", text)
    without_accents = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    lowered = without_accents.lower().strip()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


# Alias interne conservé pour compat (reception_actions exportait `_normalize_text`).
_normalize_text = normalize_text

_ARTICLE_PREFIX = re.compile(r"^(?:l|la|le|les|du|des|de la|de l)\s+")

# Verbes/tournures de déplacement suivis d'une préposition + destination,
# ex. « va à l'accueil », « rends-toi vers la salle b », « conduis-moi au point 3 ».
_NAV_PATTERN = re.compile(
    r"^(?:va|vas|aller|allez|aille|emmene|emmenez|conduis|conduisez|amene|amenez|"
    r"deplace|deplacez|dirige|dirigez|rends toi|rendez vous)\s*"
    r"(?:toi|vous|moi)?\s+"
    r"(?:jusqu\s+)?(?:au|aux|a|vers|en|dans)\s+(.+)$"
)


def match_point_navigation(text: str, point_names: list[str]) -> str | None:
    """Reconnaît une commande du type « va à <point> » et la fait correspondre
    à un nom de point existant (insensible aux accents/casse/articles)."""
    normalized = normalize_text(text)
    match = _NAV_PATTERN.match(normalized)
    if not match:
        return None

    destination = _ARTICLE_PREFIX.sub("", match.group(1).strip()).strip()
    if not destination:
        return None

    normalized_points = {normalize_text(name): name for name in point_names}

    if destination in normalized_points:
        return normalized_points[destination]

    for norm_name, original in normalized_points.items():
        if _ARTICLE_PREFIX.sub("", norm_name).strip() == destination:
            return original

    for norm_name, original in normalized_points.items():
        if destination in norm_name or norm_name in destination:
            return original

    return None


# Verbes/prépositions de déplacement, orthographe française réelle (accents
# conservés) — utilisés pour le vocabulaire STT, pas pour le matching NLU
# (qui, lui, passe par normalize_text et tolère l'absence d'accents).
_NAV_WORDS_FR = [
    "va", "vas", "aller", "allez", "aille", "emmène", "emmenez", "conduis",
    "conduisez", "amène", "amenez", "déplace", "déplacez", "dirige", "dirigez",
    "rends", "rendez", "toi", "vous", "moi", "au", "aux", "à", "vers", "en",
    "dans", "jusqu",
]

_WORD_RE = re.compile(r"[a-zà-ÿ]+")


def _stt_tokens(text: str) -> list[str]:
    """Découpe en mots pour le vocabulaire STT — conserve les accents
    (contrairement à normalize_text) car le dictionnaire du moteur de
    reconnaissance vocale attend l'orthographe française réelle, pas la forme
    sans accent utilisée pour le matching NLU."""
    return _WORD_RE.findall(text.lower())


def build_vocabulary(
    point_names: list[str] | None = None,
    extra_phrases: list[str] | None = None,
) -> list[str]:
    """Construit un vocabulaire fermé (mots triés, sans doublons) pour
    contraindre un moteur STT à ce que le backend est effectivement capable de
    comprendre : actions connues, POI actuellement déployés, questions/mots-clés
    FAQ. Un dictaphone généraliste ne connaît pas les noms propres du site
    (« HESTIM », noms de salles) — restreindre son vocabulaire à ce périmètre
    réduit ces confusions au lieu de les corriger après coup.
    """
    words: set[str] = set()
    for phrase in VOICE_COMMAND_MAP:
        words.update(_stt_tokens(phrase))
    words.update(_NAV_WORDS_FR)
    for name in point_names or []:
        words.update(_stt_tokens(name))
    for phrase in extra_phrases or []:
        words.update(_stt_tokens(phrase))
    words.discard("")
    return sorted(words)
