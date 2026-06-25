"""Client MQTT asyncio — observation passive broker châssis (Phase 2 CYBEL)."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import paho.mqtt.client as mqtt

from sdk.constants import MQTT_DEFAULT_TOPICS, MQTT_TOPIC_TEST_MUL

logger = logging.getLogger(__name__)

MqttCallback = Callable[[str, str, dict[str, Any]], Awaitable[None]]


@dataclass
class MqttMessage:
    topic: str
    payload: str
    raw: bytes
    received_at: float
    parsed: dict[str, Any] = field(default_factory=dict)


def parse_test_mul(payload: str) -> dict[str, Any]:
    """Parse odométrie châssis : ``TY1251D-03195,X,Y,Z,vitesse``."""
    parts = [p.strip() for p in payload.split(",")]
    if len(parts) < 5:
        return {"raw": payload, "source": "mqtt"}
    try:
        return {
            "chassis_id": parts[0],
            "x": float(parts[1]),
            "y": float(parts[2]),
            "z": float(parts[3]),
            "speed": float(parts[4]),
            "source": "mqtt",
            "topic": MQTT_TOPIC_TEST_MUL,
        }
    except ValueError:
        return {"raw": payload, "source": "mqtt"}


def parse_mqtt_payload(topic: str, payload: str) -> dict[str, Any]:
    if topic == MQTT_TOPIC_TEST_MUL:
        return parse_test_mul(payload)
    return {"raw": payload, "topic": topic, "source": "mqtt"}


class MqttClient:
    """Wrapper paho-mqtt avec file asyncio (thread-safe)."""

    def __init__(
        self,
        host: str = "10.42.0.1",
        port: int = 1883,
        *,
        topics: list[str] | None = None,
        subscribe_all: bool = False,
        client_id: str = "cybel-mqtt",
        queue_size: int = 500,
    ) -> None:
        self._host = host
        self._port = port
        self._topics = ["#"] if subscribe_all else list(topics or MQTT_DEFAULT_TOPICS)
        self._client_id = client_id
        self._queue_size = queue_size
        self._client: mqtt.Client | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[MqttMessage] | None = None
        self._consumer_task: asyncio.Task | None = None
        self._callbacks: list[MqttCallback] = []
        self.connected = False
        self.last_error: str = ""
        self.last_message_at: float = 0.0
        self.seen_topics: set[str] = set()
        self.message_count: int = 0

    def on_message(self, callback: MqttCallback) -> None:
        self._callbacks.append(callback)

    def _enqueue(self, message: MqttMessage) -> None:
        if not self._queue:
            return
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("File MQTT pleine — message ignoré (%s)", message.topic)

    def _paho_on_connect(self, client, userdata, flags, rc) -> None:
        if rc != 0:
            self.last_error = f"connexion refusée (rc={rc})"
            logger.warning("MQTT %s", self.last_error)
            return
        self.connected = True
        self.last_error = ""
        for topic in self._topics:
            client.subscribe(topic)
        logger.info("MQTT abonné %s:%s → %s", self._host, self._port, self._topics)

    def _paho_on_disconnect(self, client, userdata, rc) -> None:
        self.connected = False
        if rc != 0:
            self.last_error = f"déconnexion inattendue (rc={rc})"

    def _paho_on_message(self, client, userdata, msg) -> None:
        try:
            payload = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload = msg.payload.hex()
        parsed = parse_mqtt_payload(msg.topic, payload)
        message = MqttMessage(
            topic=msg.topic,
            payload=payload,
            raw=msg.payload,
            received_at=time.monotonic(),
            parsed=parsed,
        )
        if self._loop:
            self._loop.call_soon_threadsafe(self._enqueue, message)

    async def connect(self, timeout: float = 10.0) -> bool:
        if self._client and self.connected:
            return True

        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=self._queue_size)
        if self._consumer_task is None or self._consumer_task.done():
            self._consumer_task = asyncio.create_task(self._consume_loop())

        self._client = mqtt.Client(client_id=self._client_id)
        self._client.on_connect = self._paho_on_connect
        self._client.on_disconnect = self._paho_on_disconnect
        self._client.on_message = self._paho_on_message

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._client.connect, self._host, self._port, 60),
                timeout=timeout,
            )
            self._client.loop_start()
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.connected:
                    return True
                await asyncio.sleep(0.1)
            self.last_error = "timeout connexion MQTT"
            await self.disconnect()
            return False
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("MQTT connexion échouée : %s", exc)
            await self.disconnect()
            return False

    async def _consume_loop(self) -> None:
        while True:
            if not self._queue:
                await asyncio.sleep(0.05)
                continue
            message = await self._queue.get()
            self.last_message_at = message.received_at
            self.message_count += 1
            self.seen_topics.add(message.topic)
            for callback in self._callbacks:
                asyncio.create_task(self._invoke(callback, message))

    async def _invoke(self, callback: MqttCallback, message: MqttMessage) -> None:
        try:
            await callback(message.topic, message.payload, message.parsed)
        except Exception as exc:
            logger.warning("Callback MQTT : %s", exc)

    async def disconnect(self) -> None:
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        self._consumer_task = None

        if self._client:
            try:
                self._client.loop_stop()
                await asyncio.to_thread(self._client.disconnect)
            except Exception:
                pass
            self._client = None
        self.connected = False
        self._queue = None

    def status_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "host": self._host,
            "port": self._port,
            "topics": self._topics,
            "seen_topics": sorted(self.seen_topics),
            "message_count": self.message_count,
            "last_error": self.last_error,
            "last_message_age_s": (
                round(time.monotonic() - self.last_message_at, 1)
                if self.last_message_at
                else None
            ),
        }
