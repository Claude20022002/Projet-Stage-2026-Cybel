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

ROS_SERVICES = {
    "change_mode": "/change_location_mode",
    "poi": "/poi",
    "markers": "/marker_manager/get_markers_details",
    "global_localization": "/global_localization",
    "static_map": "/static_map",
}

NAV_STATUS_LABELS: dict[int, str] = {
    600: "En initialisation",
    601: "Prêt",
    602: "En navigation",
    603: "Arrivé",
    604: "Erreur",
}

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
SPEECH_HTTP_HOST = "172.16.0.88"
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
