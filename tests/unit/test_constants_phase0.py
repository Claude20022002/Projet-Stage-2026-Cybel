"""Phase 0 — constantes alignées APK constructeur."""

from sdk.constants import (
    CANCEL_NAV_PUBLISH_TOPICS,
    CANCEL_NAV_SERVICE_CHAIN,
    GLOBAL_LOCATE_SERVICE_CHAIN,
    MARKER_TYPE_CODES,
    POI_NAV_SERVICE_CHAIN,
    ROS_MSG_TYPES,
    ROS_SERVICES,
    ROS_TOPICS,
)


def test_teleop_topic_replaces_legacy_velocity() -> None:
    assert ROS_TOPICS["teleop"] == "/cmd_vel_mux/input/teleop"
    assert ROS_TOPICS["velocity_cmd"] == ROS_TOPICS["teleop"]


def test_apk_navigation_services_present() -> None:
    assert ROS_SERVICES["tag_manager_navi"] == "/tag_manager/navi"
    assert ROS_SERVICES["global_locate"] == "/global_locate"
    assert ROS_TOPICS["navi_status"] == "/navi_status"
    assert ROS_TOPICS["soft_stop"] == "/soft_stop"


def test_fallback_chains_order() -> None:
    assert POI_NAV_SERVICE_CHAIN[0] == "/tag_manager/navi"
    assert POI_NAV_SERVICE_CHAIN[1] == "/poi"
    assert GLOBAL_LOCATE_SERVICE_CHAIN[0] == "/global_locate"
    assert GLOBAL_LOCATE_SERVICE_CHAIN[1] == "/global_localization"
    assert CANCEL_NAV_PUBLISH_TOPICS[0] == "/move_base/cancel"
    assert "/path_follower/cancel" in CANCEL_NAV_PUBLISH_TOPICS
    assert CANCEL_NAV_SERVICE_CHAIN[0] == "/move_base/cancel"


def test_ros_msg_types_twist() -> None:
    assert ROS_MSG_TYPES["twist"] == "geometry_msgs/Twist"


def test_marker_type_charge_code() -> None:
    assert MARKER_TYPE_CODES["charge"] == 11
