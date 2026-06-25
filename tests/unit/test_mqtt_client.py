"""Tests Phase 2 — client MQTT."""

import pytest

from sdk.mqtt_client import parse_mqtt_payload, parse_test_mul


def test_parse_test_mul_odometry() -> None:
    parsed = parse_test_mul("TY1251D-03195,-0.01,0.01,0.0,0.52")
    assert parsed["chassis_id"] == "TY1251D-03195"
    assert parsed["x"] == pytest.approx(-0.01)
    assert parsed["y"] == pytest.approx(0.01)
    assert parsed["z"] == pytest.approx(0.0)
    assert parsed["speed"] == pytest.approx(0.52)
    assert parsed["source"] == "mqtt"


def test_parse_test_mul_invalid() -> None:
    parsed = parse_test_mul("incomplete")
    assert parsed["raw"] == "incomplete"


def test_parse_mqtt_payload_other_topic() -> None:
    parsed = parse_mqtt_payload("custom/topic", "hello")
    assert parsed["topic"] == "custom/topic"
    assert parsed["raw"] == "hello"
