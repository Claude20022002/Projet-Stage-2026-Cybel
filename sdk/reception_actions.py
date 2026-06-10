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
    ),
    ReceptionAction(
        id="go_reception",
        label="Aller à l'accueil",
        description="Navigation autonome vers le poste d'accueil",
        icon="map-pin",
        category="navigation",
        target_point="Accueil",
    ),
    ReceptionAction(
        id="go_meeting_room",
        label="Conduire en salle",
        description="Accompagner le visiteur vers la salle de réunion",
        icon="navigation",
        category="navigation",
        speech="Je vous accompagne en salle. Suivez-moi s'il vous plaît.",
        target_point="Salle A",
    ),
    ReceptionAction(
        id="wait_mode",
        label="Mode attente",
        description="Se placer au point d'attente et rester disponible",
        icon="clock",
        category="accueil",
        speech="Je reste à votre disposition.",
        target_point="Attente",
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
    ),
    ReceptionAction(
        id="inform_waiting",
        label="Informer d'un délai",
        description="Annoncer un temps d'attente estimé",
        icon="message",
        category="accueil",
        speech="Votre interlocuteur arrive dans quelques instants. Merci de patienter.",
    ),
    ReceptionAction(
        id="stop_all",
        label="Arrêter l'action",
        description="Interrompre navigation et annonces en cours",
        icon="stop",
        category="sécurité",
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
