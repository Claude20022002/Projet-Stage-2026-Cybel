import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)

MessageHandler = Callable[[str, dict[str, Any]], Awaitable[None]]


def _format_exc(exc: Exception | None) -> str:
    if exc is None:
        return "erreur inconnue"
    message = str(exc).strip()
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


class RosbridgeClient:
    def __init__(
        self,
        url: str,
        *,
        connect_timeout: float = 20.0,
        connect_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        self.url = url
        self._connect_timeout = connect_timeout
        self._connect_retries = max(1, connect_retries)
        self._retry_delay = retry_delay
        self._ws: ClientConnection | None = None
        self._listener_task: asyncio.Task | None = None
        self._handlers: list[MessageHandler] = []
        self._pending_services: dict[str, asyncio.Future] = {}
        self._connected = False
        self._disconnect_handlers: list[Callable[[], Awaitable[None]]] = []

    @property
    def connected(self) -> bool:
        if not self._connected or self._ws is None:
            return False
        if self._listener_task is None or self._listener_task.done():
            return False
        return True

    def on_message(self, handler: MessageHandler) -> None:
        self._handlers.append(handler)

    def on_disconnect(self, handler: Callable[[], Awaitable[None]]) -> None:
        self._disconnect_handlers.append(handler)

    async def connect(self, timeout: float | None = None) -> bool:
        if self._ws is not None:
            await self.disconnect()

        open_timeout = timeout if timeout is not None else self._connect_timeout
        last_exc: Exception | None = None

        for attempt in range(1, self._connect_retries + 1):
            try:
                self._ws = await websockets.connect(
                    self.url,
                    open_timeout=open_timeout,
                    close_timeout=5,
                    ping_interval=20,
                    ping_timeout=20,
                )
                self._connected = True
                self._listener_task = asyncio.create_task(self._listen())
                logger.info("Connecté à rosbridge %s", self.url)
                return True
            except Exception as exc:
                last_exc = exc
                self._connected = False
                self._ws = None
                if attempt < self._connect_retries:
                    logger.warning(
                        "Connexion rosbridge tentative %s/%s échouée (%s) — nouvel essai dans %.0f s",
                        attempt,
                        self._connect_retries,
                        _format_exc(exc),
                        self._retry_delay,
                    )
                    await asyncio.sleep(self._retry_delay)

        logger.warning(
            "Connexion rosbridge échouée après %s tentative(s) vers %s: %s",
            self._connect_retries,
            self.url,
            _format_exc(last_exc),
        )
        return False

    async def disconnect(self) -> None:
        self._connected = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _listen(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                data = json.loads(raw)
                op = data.get("op")

                if op == "service_response":
                    service = data.get("service", "")
                    future = self._pending_services.pop(service, None)
                    if future and not future.done():
                        future.set_result(data)
                    continue

                topic = data.get("topic")
                if not topic:
                    continue

                msg = data.get("msg", {})
                for handler in self._handlers:
                    try:
                        await handler(topic, msg)
                    except Exception as exc:
                        logger.warning("Handler rosbridge (%s): %s", topic, exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Écoute rosbridge interrompue: %s", _format_exc(exc))
            self._connected = False
            for handler in self._disconnect_handlers:
                try:
                    await handler()
                except Exception as handler_exc:
                    logger.warning("Handler déconnexion rosbridge: %s", handler_exc)

    async def _send(self, payload: dict[str, Any]) -> None:
        if not self._ws:
            raise RuntimeError("rosbridge non connecté")
        await self._ws.send(json.dumps(payload))

    async def subscribe(self, topic: str, throttle_rate: int = 200) -> None:
        await self._send({
            "op": "subscribe",
            "topic": topic,
            "throttle_rate": throttle_rate,
        })

    async def unsubscribe(self, topic: str) -> None:
        await self._send({"op": "unsubscribe", "topic": topic})

    async def publish(self, topic: str, msg: dict[str, Any]) -> None:
        await self._send({"op": "publish", "topic": topic, "msg": msg})

    async def advertise(self, topic: str, msg_type: str) -> None:
        await self._send({"op": "advertise", "topic": topic, "type": msg_type})

    async def unadvertise(self, topic: str) -> None:
        await self._send({"op": "unadvertise", "topic": topic})

    async def call_service(
        self,
        service: str,
        args: dict[str, Any] | None = None,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending_services[service] = future
        await self._send({
            "op": "call_service",
            "service": service,
            "args": args or {},
        })
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_services.pop(service, None)
            return {"op": "service_response", "result": False, "values": {}}
