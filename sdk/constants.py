ROS_TOPICS = {
    "pose": "/robot_pose",
    "status": "/robot_status",
    "navi_status": "/navi_status",
    "velocity_cmd": "/mobile_base/commands/velocity",
    "cancel_nav": "/path_follower/cancel",
    "init_pose": "/set_init_pose",
    "current_map": "/get_current_map",
    "map_metadata": "/map_metadata",
    "waypoints": "/waypoints",
    "lidar": "/scan_filter",
    "people": "/detected_people_array",
    "localization_confidence": "/localization_confidence",
    "navi_goal": "/navi_goal",
}

LIDAR_TOPICS = [
    "/scan_filter",
    "/scan",
]

ROS_SERVICES = {
    "change_mode": "/change_location_mode",
    "poi": "/poi",
    "markers": "/marker_manager/get_markers_details",
    "global_localization": "/global_localization",
    "static_map": "/static_map",
    "cancel_nav": "/path_follower/cancel",
    "marker_control": "/marker_manager/control",
}

NAV_STATUS_LABELS: dict[int, str] = {
    600: "En initialisation",
    601: "Prêt",
    602: "En navigation",
    603: "Arrivé",
    604: "Erreur",
}

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


def tour_recovery_hint() -> str:
    return (
        "Procédure : Arrêt → Relocaliser (interface opérateur) → "
        "attendre nav_status 601 et localisation ≥ 60 % → relancer la visite."
    )

MARKER_TYPE_MAP: dict[str, str] = {
    "charging": "charging",
    "charging_pile": "charging",
    "charge": "charging",
    "common": "common",
    "normal": "common",
    "gate": "gate",
    "access": "access",
    "access_control": "access",
    "ride": "ride",
    "elevator": "ride",
    "wait": "wait",
    "label": "label",
    "stop": "stop",
}

SPEED_GEAR_VALUES = {
    "low": 0.3,
    "medium": 0.5,
    "high": 0.8,
}

# Candidats TTS — à valider sur robot via scripts/speech_explore.py
SPEECH_PUBLISH_TOPICS = [
    "/play_tts",
    "/tts_play",
    "/robot_tts",
    "/speaker/tts",
    "/yutong_assistance/tts",
    "/android_tts",
    "/voice_play",
]

SPEECH_SERVICES = [
    "/speak",
    "/tts",
    "/play_tts",
    "/play_voice",
    "/yutong_assistance/speak",
    "/yutong_assistance/tts",
]

SPEECH_PUBLISH_PAYLOADS = [
    lambda text: {"data": text},
    lambda text: {"text": text},
    lambda text: {"content": text},
    lambda text: {"voice": text},
    lambda text: {"msg": text},
    lambda text: {"message": text},
]

SPEECH_SERVICE_ARGS = [
    lambda text: {"text": text},
    lambda text: {"data": text},
    lambda text: {"content": text},
    lambda text: {"voice": text},
    lambda text: {"message": text},
]

# Upper body Android (RK3399) — fallback HTTP si ROS échoue
SPEECH_HTTP_HOST = "172.16.0.194"
SPEECH_HTTP_PORTS = (80, 8080, 8888, 9000, 9090)
SPEECH_HTTP_PATHS = (
    "/tts",
    "/api/tts",
    "/api/voice/play",
    "/api/speech",
    "/voice/play",
    "/speak",
    "/robot/tts",
    "/yutong/tts",
    "/android/tts",
)

# TTS via la tête Android — app CybelTTSBridge installée sur l'appareil
# (voir android/CybelTTSBridge), déclenchée par broadcast ADB.
SPEECH_ADB_SERIAL = "172.16.0.194:5555"
SPEECH_ADB_RECEIVER = "com.cybel.ttsbridge/.SpeakReceiver"
SPEECH_ADB_ACTION = "com.cybel.ttsbridge.SPEAK"
