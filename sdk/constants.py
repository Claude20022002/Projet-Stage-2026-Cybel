# Référence APK : TopicContent.java / ServiceContent.java (selfchassislibrary)
# DeploymentToolConstant.java — types POI

ROS_TOPICS = {
  # Télémétrie
    "pose": "/robot_pose",
    "status": "/robot_status",
    "navi_status": "/navi_status",
    "localization_confidence": "/localization_confidence",
    # Carte
    "current_map": "/get_current_map",
    "map": "/map",
    "map_metadata": "/map_metadata",
    # Navigation — commandes
    "navi_goal": "/navi_goal",
    "navi_goal_id": "/navi_goal_id",
    "move_base_cancel": "/move_base/cancel",
    "cancel_nav": "/path_follower/cancel",  # legacy CYBEL
    "soft_stop": "/soft_stop",
    "global_path": "/global_path",
    # Téléopération (APK MsgManager — cmd_vel_mux)
    "teleop": "/cmd_vel_mux/input/teleop",
    "velocity_cmd": "/cmd_vel_mux/input/teleop",  # alias — remplace mobile_base/commands/velocity
    # Recharge (WelcomeManager / SelfChassis.sendGoHome)
    "charge_home_pose": "/charge_server/home_pose",
    "charge_result": "/charge_server/result",
    # Multi-étages (phase ultérieure)
    "cross_floor_navi": "/cross_floor_navi",
    # Capteurs
    "lidar": "/scan_filter",
    "people": "/detected_people_array",
    "init_pose": "/set_init_pose",
    "waypoints": "/waypoints",
}

LIDAR_TOPICS = [
    "/scan_filter",
    "/scan",
]

ROS_SERVICES = {
    # Navigation POI
    "tag_manager_navi": "/tag_manager/navi",  # APK SelfChassis.sendMoveByMarkerName
    "poi": "/poi",  # fallback legacy CYBEL
    # Localisation
    "global_locate": "/global_locate",  # APK ServiceContent.GLOBAL_LOCATE
    "global_localization": "/global_localization",  # fallback CYBEL
    # Marqueurs / carte
    "markers": "/marker_manager/get_markers_details",
    "marker_control": "/marker_manager/control",
    "marker_operation_get": "/marker_operation/get_markers",
    "static_map": "/static_map",
    # Modes
    "change_mode": "/change_location_mode",
    # Recharge
    "start_recharge": "/start_recharge",
    # Annulation (services)
    "move_base_cancel": "/move_base/cancel",
    "cancel_nav": "/path_follower/cancel",
}

# Ordre de tentative pour relocalisation (CYB-003)
GLOBAL_LOCATE_SERVICE_CHAIN: list[str] = [
    ROS_SERVICES["global_locate"],
    ROS_SERVICES["global_localization"],
]

# Ordre pour navigation vers POI nommé (CYB-002)
POI_NAV_SERVICE_CHAIN: list[str] = [
    ROS_SERVICES["tag_manager_navi"],
    ROS_SERVICES["poi"],
]

# Annulation navigation — publish puis services (CYB-005)
CANCEL_NAV_PUBLISH_TOPICS: list[str] = [
    ROS_TOPICS["move_base_cancel"],
    ROS_TOPICS["cancel_nav"],
]

CANCEL_NAV_SERVICE_CHAIN: list[str] = [
    ROS_SERVICES["move_base_cancel"],
    ROS_SERVICES["cancel_nav"],
]

# Types ROS rosbridge (APK TypeContent)
ROS_MSG_TYPES = {
    "twist": "geometry_msgs/Twist",
    "pose2d": "geometry_msgs/Pose2D",
    "robot_status": "yutong_assistance/RobotStatus",
    "bool": "std_msgs/Bool",
    "goal_id": "actionlib_msgs/GoalID",
}

# Types POI constructeur (DeploymentToolConstant.POINT_*)
MARKER_TYPE_CODES: dict[str, int] = {
    "common": 0,
    "elevator_out": 3,
    "elevator_in": 4,
    "wait": 5,
    "gate": 7,
    "door_guard": 8,
    "charge": 11,
    "charging": 11,
    "trajectory": -65535,
}

CHARGE_STATE_LABELS: dict[str, str] = {
    "idle": "Hors charge",
    "returning": "Retour borne…",
    "charging": "En charge",
    "failed": "Échec recharge",
    "disconnect": "Borne déconnectée",
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
    "elevator_in": "ride",
    "elevator_out": "ride",
    "wait": "wait",
    "label": "label",
    "stop": "stop",
}

SPEED_GEAR_VALUES = {
    "low": 0.3,
    "medium": 0.5,
    "high": 0.8,
}

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

SPEECH_ADB_SERIAL = "172.16.0.194:5555"
SPEECH_ADB_RECEIVER = "com.cybel.ttsbridge/.SpeakReceiver"
SPEECH_ADB_ACTION = "com.cybel.ttsbridge.SPEAK"
