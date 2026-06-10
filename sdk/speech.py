import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sdk.constants import (
    SPEECH_PUBLISH_PAYLOADS,
    SPEECH_PUBLISH_TOPICS,
    SPEECH_SERVICE_ARGS,
    SPEECH_SERVICES,
)
from sdk.models import SpeechStatus
from sdk.rosbridge import RosbridgeClient

logger = logging.getLogger(__name__)

EmitCallback = Callable[[str, dict], Awaitable[None]]


class RobotSpeech:
    """Couche synthèse vocale — essaie plusieurs topics/services ROS connus."""

    def __init__(
        self,
        client: RosbridgeClient | None = None,
        emit: EmitCallback | None = None,
        mock: bool = False,
        preferred_topic: str = "",
        preferred_service: str = "",
    ) -> None:
        self._client = client
        self._emit = emit
        self._mock = mock
        self._preferred_topic = preferred_topic
        self._preferred_service = preferred_service
        self._status = SpeechStatus(mock=mock)
        self._speech_task: asyncio.Task | None = None

    def get_status(self) -> SpeechStatus:
        return self._status.model_copy(deep=True)

    async def _notify(self, text: str, status: str, method: str = "") -> None:
        self._status.last_text = text
        self._status.speaking = status == "speaking"
        if method:
            self._status.last_method = method
        if self._emit:
            await self._emit(
                "speech",
                {
                    "text": text,
                    "status": status,
                    "method": method,
                    "speaking": self._status.speaking,
                },
            )

    async def speak(self, text: str, interrupt: bool = True) -> dict[str, Any]:
        text = text.strip()
        if not text:
            return {"ok": False, "error": "Texte vide"}

        if interrupt and self._speech_task:
            self._speech_task.cancel()

        if self._mock:
            self._speech_task = asyncio.create_task(self._mock_speak(text))
            return {"ok": True, "method": "mock", "text": text}

        if not self._client or not self._client.connected:
            return {"ok": False, "error": "Robot non connecté"}

        method = await self._try_real_speak(text)
        if method:
            return {"ok": True, "method": method, "text": text}

        await self._notify(text, "failed", "none")
        return {
            "ok": False,
            "error": "Aucun canal TTS ROS n'a répondu — lancez scripts/speech_explore.py",
            "text": text,
        }

    async def _mock_speak(self, text: str) -> None:
        try:
            await self._notify(text, "speaking", "mock")
            duration = min(max(len(text) * 0.06, 1.0), 8.0)
            await asyncio.sleep(duration)
            await self._notify(text, "done", "mock")
        except asyncio.CancelledError:
            await self._notify(text, "cancelled", "mock")
            raise

    async def _try_real_speak(self, text: str) -> str | None:
        topics = ([self._preferred_topic] if self._preferred_topic else []) + SPEECH_PUBLISH_TOPICS
        services = ([self._preferred_service] if self._preferred_service else []) + SPEECH_SERVICES

        await self._notify(text, "speaking", "rosbridge")

        for topic in dict.fromkeys(topics):
            if not topic:
                continue
            for build in SPEECH_PUBLISH_PAYLOADS:
                try:
                    await self._client.publish(topic, build(text))
                    await asyncio.sleep(0.15)
                    await self._notify(text, "done", f"publish:{topic}")
                    logger.info("TTS via publish %s", topic)
                    return f"publish:{topic}"
                except Exception as exc:
                    logger.debug("TTS publish %s échoué: %s", topic, exc)

        for service in dict.fromkeys(services):
            if not service:
                continue
            for build in SPEECH_SERVICE_ARGS:
                try:
                    resp = await self._client.call_service(service, build(text), timeout=3.0)
                    if resp.get("result", True):
                        await self._notify(text, "done", f"service:{service}")
                        logger.info("TTS via service %s", service)
                        return f"service:{service}"
                except Exception as exc:
                    logger.debug("TTS service %s échoué: %s", service, exc)

        return None

    async def stop(self) -> dict[str, Any]:
        if self._speech_task:
            self._speech_task.cancel()
            self._speech_task = None

        self._status.speaking = False
        if self._emit:
            await self._emit("speech", {"text": "", "status": "stopped", "speaking": False})

        if self._mock or not self._client or not self._client.connected:
            return {"ok": True}

        for topic in ("/stop_tts", "/tts_stop", "/speaker/stop"):
            try:
                await self._client.publish(topic, {})
            except Exception:
                pass

        return {"ok": True}
