"""Diagnostic unifié des canaux robot (Phase 6 CYB-064)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from services.mqtt_bridge_service import mqtt_bridge_service
from services.robot_service import robot_service


class DiagnosticsService:
    def snapshot(self) -> dict:
        rosbridge = {"connected": False, "host": settings.robot_host, "last_message_age_s": None, "stale": False}
        speech: dict = {"device_ready": False, "configured_serial": settings.speech_adb_serial or ""}
        mock = robot_service.is_mock

        if not mock:
            try:
                rosbridge = robot_service.get_connection_diagnostics()
                speech = robot_service.get_speech_diagnostics()
            except RuntimeError:
                rosbridge["connected"] = False
        else:
            rosbridge = {"connected": True, "host": "mock", "last_message_age_s": 0.0, "stale": False}
            try:
                speech = robot_service.get_speech_diagnostics()
            except RuntimeError:
                pass

        data_dir = settings.data_dir
        persistence_ok = data_dir.is_dir()

        mqtt = mqtt_bridge_service.get_status()
        mqtt_ok = (not settings.mqtt_enabled) or mqtt.get("active") or mock

        adb_ok = mock or speech.get("last_connect_ok") or speech.get("device_ready", False)

        return {
            "mock": mock,
            "rosbridge": {
                **rosbridge,
                "ok": bool(rosbridge.get("connected")) and not rosbridge.get("stale", False),
            },
            "mqtt": {
                **mqtt,
                "ok": mqtt_ok,
            },
            "adb_tts": {
                **speech,
                "ok": adb_ok if not mock else True,
            },
            "persistence": {
                "backend": "json",
                "data_dir": str(data_dir),
                "ok": persistence_ok,
            },
            "overall_ok": (
                (mock or rosbridge.get("connected"))
                and mqtt_ok
                and (mock or adb_ok)
                and persistence_ok
            ),
        }


diagnostics_service = DiagnosticsService()
