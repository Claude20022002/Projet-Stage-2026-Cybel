import asyncio
import logging
import subprocess
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal
from urllib.parse import quote

import httpx

from sdk.constants import (
    SPEECH_ADB_ACTION,
    SPEECH_ADB_RECEIVER,
    SPEECH_ADB_SERIAL,
    SPEECH_HTTP_HOST,
    SPEECH_HTTP_PATHS,
    SPEECH_HTTP_PORTS,
    SPEECH_PUBLISH_PAYLOADS,
    SPEECH_PUBLISH_TOPICS,
    SPEECH_SERVICE_ARGS,
    SPEECH_SERVICES,
)
from sdk.models import SpeechStatus
from sdk.rosbridge import RosbridgeClient

logger = logging.getLogger(__name__)

SpeechPriority = Literal["urgent", "normal", "background"]
SPEECH_PRIORITY_VALUES = {"urgent": 0, "normal": 1, "background": 2}

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
        http_host: str = "",
        http_port: int = 0,
        http_path: str = "",
        adb_serial: str = "",
        local_broadcast: bool = False,
    ) -> None:
        self._client = client
        self._emit = emit
        self._mock = mock
        self._preferred_topic = preferred_topic
        self._preferred_service = preferred_service
        self._http_host = http_host or SPEECH_HTTP_HOST
        self._http_port = http_port
        self._http_path = http_path
        # Chaîne vide explicite = USB uniquement (pas de adb connect Wi-Fi automatique).
        if adb_serial:
            self._adb_serial = adb_serial
        elif local_broadcast:
            self._adb_serial = ""
        else:
            self._adb_serial = SPEECH_ADB_SERIAL
        self._local_broadcast = local_broadcast
        self._status = SpeechStatus(mock=mock)
        self._speech_task: asyncio.Task | None = None
        self._known_services: set[str] | None = None
        self._queue: asyncio.PriorityQueue[tuple[int, int, dict[str, Any]]] = asyncio.PriorityQueue()
        self._queue_seq = 0
        self._worker_task: asyncio.Task | None = None
        self._last_adb_connect_at = 0.0
        self._last_adb_connect_ok = False

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

    async def _clear_pending_speech(self) -> None:
        """Évite de bloquer l'UI si une tentative de canal échoue."""
        if not self._status.speaking:
            return
        self._status.speaking = False
        if self._emit:
            await self._emit(
                "speech",
                {
                    "text": self._status.last_text,
                    "status": "pending",
                    "method": self._status.last_method,
                    "speaking": False,
                },
            )

    async def _list_adb_devices(self) -> list[str]:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["adb", "devices"],
                capture_output=True,
                timeout=2.0,
                text=True,
            )
            return [
                line.split("\t")[0].strip()
                for line in (result.stdout or "").splitlines()[1:]
                if "\tdevice" in line
            ]
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.debug("Liste adb devices échouée: %s", exc)
            return []

    async def _resolve_adb_serial(self) -> str | None:
        """Retourne le serial ADB à utiliser (configuré ou premier appareil USB)."""
        configured = self._adb_serial
        connected = await self._list_adb_devices()
        if configured and configured in connected:
            return configured
        if connected:
            if configured:
                logger.info(
                    "ADB %s absent — utilisation de %s (USB)",
                    configured,
                    connected[0],
                )
            return connected[0]
        return configured or None

    async def _ensure_adb_connected(self, serial: str | None = None) -> bool:
        """Reconnecte ADB Wi-Fi si nécessaire (CYB-063)."""
        target = serial or self._adb_serial
        if not target:
            return False
        devices = await self._list_adb_devices()
        if target in devices:
            self._last_adb_connect_ok = True
            return True
        if ":" not in target:
            devices = await self._list_adb_devices()
            self._last_adb_connect_ok = target in devices
            return self._last_adb_connect_ok
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["adb", "connect", target],
                capture_output=True,
                timeout=8.0,
                text=True,
            )
            self._last_adb_connect_at = time.monotonic()
            output = ((result.stdout or "") + (result.stderr or "")).lower()
            devices = await self._list_adb_devices()
            self._last_adb_connect_ok = target in devices or "connected" in output
            if self._last_adb_connect_ok:
                logger.info("ADB reconnecté : %s", target)
            return self._last_adb_connect_ok
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("ADB connect %s échoué: %s", target, exc)
            self._last_adb_connect_ok = False
            return False

    async def ensure_adb_connected(self) -> dict[str, Any]:
        serial = await self._resolve_adb_serial()
        if not serial:
            return {
                "ok": False,
                "serial": self._adb_serial or None,
                "device_ready": False,
            }
        ok = (
            await self._ensure_adb_connected(serial)
            if ":" in serial
            else serial in await self._list_adb_devices()
        )
        ready = await self._adb_device_ready()
        return {"ok": ok and ready, "serial": serial, "device_ready": ready}

    def diagnostics(self) -> dict[str, Any]:
        return {
            "configured_serial": self._adb_serial or SPEECH_ADB_SERIAL,
            "last_connect_ok": self._last_adb_connect_ok,
            "last_connect_age_s": (
                round(time.monotonic() - self._last_adb_connect_at, 1)
                if self._last_adb_connect_at
                else None
            ),
            "queue_size": self._queue.qsize(),
            "worker_running": self._worker_task is not None and not self._worker_task.done(),
            "speaking": self._status.speaking,
            "last_method": self._status.last_method,
        }

    async def _adb_device_ready(self) -> bool:
        return bool(await self._resolve_adb_serial())

    def _priority_value(self, priority: SpeechPriority | str) -> int:
        return SPEECH_PRIORITY_VALUES.get(str(priority), 1)

    async def _flush_queue(self) -> None:
        if self._speech_task and not self._speech_task.done():
            self._speech_task.cancel()
            try:
                await self._speech_task
            except asyncio.CancelledError:
                pass
            self._speech_task = None
        while True:
            try:
                _, _, item = self._queue.get_nowait()
                future = item.get("future")
                if future and not future.done():
                    future.set_result(
                        {"ok": False, "error": "interrompu", "text": item.get("text", "")}
                    )
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self) -> None:
        while True:
            _, _, item = await self._queue.get()
            try:
                result = await self._speak_immediate(item["text"], item.get("lang", "fr"))
                future = item.get("future")
                if future and not future.done():
                    future.set_result(result)
            except Exception as exc:
                future = item.get("future")
                if future and not future.done():
                    future.set_exception(exc)
            finally:
                self._queue.task_done()

    async def speak(
        self,
        text: str,
        interrupt: bool = True,
        priority: SpeechPriority | str = "normal",
        lang: str = "fr",
    ) -> dict[str, Any]:
        text = text.strip()
        if not text:
            return {"ok": False, "error": "Texte vide"}

        if interrupt:
            await self._flush_queue()

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._queue_seq += 1
        await self._queue.put(
            (
                self._priority_value(priority),
                self._queue_seq,
                {"text": text, "lang": lang, "future": future},
            )
        )
        self._ensure_worker()
        return await future

    async def _speak_immediate(self, text: str, lang: str = "fr") -> dict[str, Any]:
        if self._mock:
            self._speech_task = asyncio.create_task(self._mock_speak(text))
            return {"ok": True, "method": "mock", "text": text}

        # ADB en premier : canal fiable (CybelTTSBridge) sur la tête Android.
        adb_serial = await self._resolve_adb_serial()
        if adb_serial and ":" in adb_serial:
            await self._ensure_adb_connected(adb_serial)
        if adb_serial:
            adb_method = await self._try_adb_speak(text, adb_serial, lang)
            if adb_method:
                return {"ok": True, "method": adb_method, "text": text}
            await self._clear_pending_speech()
        elif self._adb_serial:
            logger.warning("TTS ADB ignoré : aucun appareil dans `adb devices`")

        if self._client and self._client.connected:
            try:
                method = await asyncio.wait_for(self._try_real_speak(text), timeout=8.0)
            except asyncio.TimeoutError:
                logger.warning("TTS ROS : délai dépassé")
                method = None
            if method:
                return {"ok": True, "method": method, "text": text}
            await self._clear_pending_speech()

        local_method = await self._try_local_broadcast_speak(text, lang)
        if local_method:
            return {"ok": True, "method": local_method, "text": text}
        await self._clear_pending_speech()

        try:
            http_method = await asyncio.wait_for(self._try_http_speak(text), timeout=12.0)
        except asyncio.TimeoutError:
            logger.warning("TTS HTTP : délai dépassé sur %s", self._http_host)
            http_method = None
        if http_method:
            return {"ok": True, "method": http_method, "text": text}
        await self._clear_pending_speech()

        await self._notify(text, "failed", "none")
        return {
            "ok": False,
            "error": (
                "Aucun canal TTS (ADB/ROS/HTTP) — vérifiez adb connect "
                f"{self._adb_serial or SPEECH_ADB_SERIAL} ou scripts/speech_explore.py"
            ),
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

    async def _topic_has_subscribers(self, topic: str) -> bool:
        try:
            resp = await self._client.call_service(
                "/rosapi/subscribers", {"topic": topic}, timeout=1.0
            )
            subscribers = (resp.get("values") or {}).get("subscribers") or []
            return len(subscribers) > 0
        except Exception:
            return False

    async def _list_services(self) -> set[str]:
        if self._known_services is not None:
            return self._known_services
        try:
            resp = await self._client.call_service("/rosapi/services", {}, timeout=3.0)
            self._known_services = set((resp.get("values") or {}).get("services") or [])
        except Exception:
            self._known_services = set()
        return self._known_services

    async def _try_real_speak(self, text: str) -> str | None:
        topics = ([self._preferred_topic] if self._preferred_topic else []) + SPEECH_PUBLISH_TOPICS
        services = ([self._preferred_service] if self._preferred_service else []) + SPEECH_SERVICES

        for topic in dict.fromkeys(topics):
            if not topic:
                continue
            if not await self._topic_has_subscribers(topic):
                logger.debug("TTS topic %s ignoré : aucun abonné", topic)
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

        known_services = await self._list_services()
        for service in dict.fromkeys(services):
            if not service or service not in known_services:
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

    async def _try_adb_speak(
        self, text: str, adb_serial: str | None = None, lang: str = "fr"
    ) -> str | None:
        serial = adb_serial or self._adb_serial
        if not serial:
            return None

        # am broadcast --es passe par le shell distant : on échappe pour
        # rester dans des guillemets simples côté Android.
        escaped = text.replace("'", "'\\''")
        remote_cmd = (
            f"am broadcast -n {SPEECH_ADB_RECEIVER} -a {SPEECH_ADB_ACTION} "
            f"--es text '{escaped}' --es lang '{lang}'"
        )

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["adb", "-s", serial, "shell", remote_cmd],
                capture_output=True,
                timeout=5.0,
            )
            if result.returncode == 0:
                await self._notify(text, "done", "adb-tts")
                logger.info("TTS via adb broadcast (%s)", serial)
                return "adb-tts"
            stderr = result.stderr.decode(errors="ignore").strip()
            logger.warning(
                "TTS via adb échoué (code %s): %s",
                result.returncode,
                stderr or "pas de stderr",
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("TTS via adb échoué: %s", exc)

        return None

    async def _try_local_broadcast_speak(self, text: str, lang: str = "fr") -> str | None:
        """TTS via am broadcast sur le même appareil (Termux sur la tête Android)."""
        if not self._local_broadcast:
            return None

        escaped = text.replace("'", "'\\''")
        broadcast = (
            f"am broadcast -n {SPEECH_ADB_RECEIVER} -a {SPEECH_ADB_ACTION} "
            f"--es text '{escaped}' --es lang '{lang}'"
        )
        commands = [
            ["sh", "-c", broadcast],
            ["sh", "-c", f"su -c '{broadcast}'"],
        ]

        for cmd in commands:
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    timeout=5.0,
                )
                if result.returncode == 0:
                    await self._notify(text, "done", "local-broadcast")
                    logger.info("TTS via broadcast local")
                    return "local-broadcast"
                logger.debug(
                    "TTS broadcast local échoué (%s): %s",
                    result.returncode,
                    result.stderr.decode(errors="ignore"),
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                logger.debug("TTS broadcast local échoué: %s", exc)

        return None

    async def _try_http_speak(self, text: str) -> str | None:
        ports = [self._http_port] if self._http_port else list(SPEECH_HTTP_PORTS)
        paths = [self._http_path] if self._http_path else list(SPEECH_HTTP_PATHS)
        post_bodies = (
            {"text": text},
            {"data": text},
            {"content": text},
            {"message": text},
            {"voice": text},
            {"tts": text},
        )

        timeout = httpx.Timeout(2.0, connect=0.8)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for port in ports:
                base = f"http://{self._http_host}:{port}"
                for path in paths:
                    url = f"{base}{path}"

                    try:
                        resp = await client.get(
                            url,
                            params={"text": text, "content": text, "message": text},
                        )
                        if resp.status_code < 400:
                            await self._notify(text, "done", f"http-get:{url}")
                            logger.info("TTS via HTTP GET %s", url)
                            return f"http-get:{url}"
                    except Exception as exc:
                        logger.debug("TTS HTTP GET %s échoué: %s", url, exc)

                    for body in post_bodies:
                        try:
                            resp = await client.post(url, json=body)
                            if resp.status_code < 400:
                                await self._notify(text, "done", f"http-post:{url}")
                                logger.info("TTS via HTTP POST %s", url)
                                return f"http-post:{url}"
                        except Exception as exc:
                            logger.debug("TTS HTTP POST %s échoué: %s", url, exc)

                    encoded = quote(text)
                    for suffix in (f"?text={encoded}", f"?content={encoded}"):
                        try:
                            resp = await client.post(f"{url}{suffix}")
                            if resp.status_code < 400:
                                await self._notify(text, "done", f"http-post:{url}")
                                logger.info("TTS via HTTP POST %s%s", url, suffix)
                                return f"http-post:{url}"
                        except Exception as exc:
                            logger.debug("TTS HTTP POST query %s échoué: %s", url, exc)

        return None

    async def _is_adb_tts_service_running(self) -> bool:
        from sdk.speech_timing import tts_service_running_in_output

        serial = await self._resolve_adb_serial()
        if not serial:
            return False
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["adb", "-s", serial, "shell", "dumpsys", "activity", "services"],
                capture_output=True,
                timeout=4.0,
                text=True,
            )
            return tts_service_running_in_output(
                (result.stdout or "") + (result.stderr or "")
            )
        except (OSError, subprocess.TimeoutExpired):
            return False

    async def wait_for_completion(self, text: str, timeout: float = 90.0) -> None:
        """Attend la fin probable de l'annonce (TTS fire-and-forget)."""
        if self._mock and self._speech_task:
            try:
                await asyncio.wait_for(asyncio.shield(self._speech_task), timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            return

        from sdk.speech_timing import is_local_tts_service_running, wait_for_tts_completion

        method = self._status.last_method
        if method == "adb-tts":
            await wait_for_tts_completion(
                text,
                self._is_adb_tts_service_running,
                max_seconds=timeout,
            )
            return
        if method == "local-broadcast":
            await wait_for_tts_completion(
                text,
                is_local_tts_service_running,
                max_seconds=timeout,
            )
            return

        estimated = min(max(len(text.strip()) * 0.055, 1.5), timeout)
        deadline = asyncio.get_running_loop().time() + estimated
        while asyncio.get_running_loop().time() < deadline:
            if not self._status.speaking:
                await asyncio.sleep(0.35)
                return
            await asyncio.sleep(0.15)
        await asyncio.sleep(0.25)

    async def stop(self) -> dict[str, Any]:
        await self._flush_queue()

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
