import re
import unicodedata

from sdk.models import ReceptionAction

DEFAULT_ACTIONS: list[ReceptionAction] = [
    ReceptionAction(
        id="welcome_guest",
        label="Accueillir un visiteur",
        description="Annonce de bienvenue puis déplacement vers le point d'accueil",
        icon="hand-wave",
        category="accueil",
        speech="Bienvenue ! Je suis votre robot d'accueil. Suivez-moi.",
        target_point="Accueil",
        label_en="Welcome a visitor",
        description_en="Welcome announcement, then move to the reception point",
        speech_en="Welcome! I am your reception robot. Follow me.",
    ),
    ReceptionAction(
        id="go_reception",
        label="Aller à l'accueil",
        description="Navigation autonome vers le poste d'accueil",
        icon="map-pin",
        category="navigation",
        target_point="Accueil",
        label_en="Go to reception",
        description_en="Autonomous navigation to the reception desk",
    ),
    ReceptionAction(
        id="go_meeting_room",
        label="Conduire en salle",
        description="Accompagner le visiteur vers la salle de réunion",
        icon="navigation",
        category="navigation",
        speech="Je vous accompagne en salle. Suivez-moi s'il vous plaît.",
        target_point="Salle A",
        label_en="Lead to meeting room",
        description_en="Accompany the visitor to the meeting room",
        speech_en="I will take you to the meeting room. Please follow me.",
    ),
    ReceptionAction(
        id="wait_mode",
        label="Mode attente",
        description="Se placer au point d'attente et rester disponible",
        icon="clock",
        category="accueil",
        speech="Je reste à votre disposition.",
        target_point="Attente",
        label_en="Standby mode",
        description_en="Move to the waiting point and stay available",
        speech_en="I remain available for you.",
    ),
    ReceptionAction(
        id="return_charge",
        label="Retour à la pile",
        description="Renvoyer le robot vers la station de charge",
        icon="plug",
        category="maintenance",
        target_point="Pile",
    ),
    ReceptionAction(
        id="guided_tour",
        label="Visite guidée",
        description="Lancer un parcours de visite prédéfini (GUIDED)",
        icon="route",
        category="accueil",
        speech="Bienvenue pour la visite guidée. Nous allons commencer.",
        route_name="visite_standard",
        label_en="Guided tour",
        description_en="Start a predefined visit route (GUIDED)",
        speech_en="Welcome to the guided tour. Let's get started.",
    ),
    ReceptionAction(
        id="inform_waiting",
        label="Informer d'un délai",
        description="Annoncer un temps d'attente estimé",
        icon="message",
        category="accueil",
        speech="Votre interlocuteur arrive dans quelques instants. Merci de patienter.",
        label_en="Announce a delay",
        description_en="Announce an estimated waiting time",
        speech_en="Your contact will arrive shortly. Thank you for waiting.",
    ),
    ReceptionAction(
        id="stop_all",
        label="Arrêter l'action",
        description="Interrompre navigation et annonces en cours",
        icon="stop",
        category="sécurité",
        label_en="Stop",
        description_en="Interrupt current navigation and announcements",
    ),
]

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
    normalized = text.lower().strip()
    if normalized in VOICE_COMMAND_MAP:
        return VOICE_COMMAND_MAP[normalized]
    for phrase, action_id in sorted(VOICE_COMMAND_MAP.items(), key=lambda x: -len(x[0])):
        if phrase in normalized:
            return action_id
    return None


def _normalize_text(text: str) -> str:
    """Minuscules, sans accents, sans ponctuation, espaces normalisés."""
    decomposed = unicodedata.normalize("NFD", text)
    without_accents = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    lowered = without_accents.lower().strip()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


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
    normalized = _normalize_text(text)
    match = _NAV_PATTERN.match(normalized)
    if not match:
        return None

    destination = _ARTICLE_PREFIX.sub("", match.group(1).strip()).strip()
    if not destination:
        return None

    normalized_points = {_normalize_text(name): name for name in point_names}

    if destination in normalized_points:
        return normalized_points[destination]

    for norm_name, original in normalized_points.items():
        if _ARTICLE_PREFIX.sub("", norm_name).strip() == destination:
            return original

    for norm_name, original in normalized_points.items():
        if destination in norm_name or norm_name in destination:
            return original

    return None
