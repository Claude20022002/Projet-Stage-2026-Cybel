"""Pont MQTT → télémétrie WebSocket (Phase 2 CYBEL)."""

from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from config import settings
from sdk.mqtt_client import MqttClient

logger = logging.getLogger(__name__)

TelemetryCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class MqttBridgeService:
    def __init__(self) -> None:
        self._client: MqttClient | None = None
        self._emit: TelemetryCallback | None = None
        self._started = False
        self._last_odom: dict[str, Any] | None = None

    @property
    def is_active(self) -> bool:
        return self._started and self._client is not None and self._client.connected

    async def start(self, emit: TelemetryCallback) -> bool:
        if self._started:
            return self.is_active
        if settings.robot_mock or not settings.mqtt_enabled:
            logger.info("MQTT bridge désactivé (mock=%s, enabled=%s)", settings.robot_mock, settings.mqtt_enabled)
            return False

        self._emit = emit
        topics = ["#"] if settings.mqtt_subscribe_all else list(settings.mqtt_topics)
        self._client = MqttClient(
            host=settings.mqtt_host or settings.robot_host,
            port=settings.mqtt_port,
            topics=topics,
            subscribe_all=settings.mqtt_subscribe_all,
        )
        self._client.on_message(self._on_mqtt_message)
        ok = await self._client.connect(timeout=settings.mqtt_connect_timeout)
        self._started = ok
        if ok:
            await self._emit(
                "event",
                {
                    "message": (
                        f"MQTT connecté — écoute {topics if not settings.mqtt_subscribe_all else ['#']}"
                    ),
                },
            )
        else:
            await self._emit(
                "event",
                {"message": f"MQTT indisponible : {self._client.last_error or 'erreur inconnue'}"},
            )
        return ok

    async def stop(self) -> None:
        if self._client:
            await self._client.disconnect()
        self._client = None
        self._started = False
        self._emit = None

    async def _on_mqtt_message(self, topic: str, payload: str, parsed: dict[str, Any]) -> None:
        if not self._emit:
            return

        event: dict[str, Any] = {
            "topic": topic,
            "payload": payload[:500],
            "parsed": parsed,
            "received_at": time.time(),
        }

        if topic == "test_mul" and "x" in parsed:
            self._last_odom = parsed
            event["message"] = (
                f"MQTT odom {parsed.get('chassis_id', '?')}: "
                f"x={parsed['x']:.2f} y={parsed['y']:.2f} v={parsed.get('speed', 0):.2f}"
            )
        else:
            preview = payload.replace("\n", " ")[:80]
            event["message"] = f"MQTT [{topic}] {preview}"

        await self._emit("mqtt", event)

    def get_status(self) -> dict[str, Any]:
        base = {
            "enabled": settings.mqtt_enabled,
            "active": self.is_active,
            "last_odom": self._last_odom,
        }
        if self._client:
            base.update(self._client.status_dict())
        return base


mqtt_bridge_service = MqttBridgeService()
