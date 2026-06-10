import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)

MessageHandler = Callable[[str, dict[str, Any]], Awaitable[None]]


class RosbridgeClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self._ws: ClientConnection | None = None
        self._listener_task: asyncio.Task | None = None
        self._handlers: list[MessageHandler] = []
        self._pending_services: dict[str, asyncio.Future] = {}
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected and self._ws is not None

    def on_message(self, handler: MessageHandler) -> None:
        self._handlers.append(handler)

    async def connect(self, timeout: float = 5.0) -> bool:
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(self.url, open_timeout=timeout),
                timeout=timeout,
            )
            self._connected = True
            self._listener_task = asyncio.create_task(self._listen())
            logger.info("Connecté à rosbridge %s", self.url)
            return True
        except Exception as exc:
            logger.warning("Connexion rosbridge échouée: %s", exc)
            self._connected = False
            self._ws = None
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
                    await handler(topic, msg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Écoute rosbridge interrompue: %s", exc)
            self._connected = False

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
