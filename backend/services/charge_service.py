"""Gestion retour borne et alerte batterie basse (Phase 1 CYBEL)."""

from __future__ import annotations

import logging
import time

from config import settings

logger = logging.getLogger(__name__)


class ChargeService:
    def __init__(self) -> None:
        self._auto_return_in_progress = False
        self._last_auto_return_at = 0.0
        self._attached = False

    def attach(self, robot_service) -> None:
        if self._attached:
            return
        self._attached = True
        self._robot_service = robot_service

        async def on_status(event_type: str, payload: dict) -> None:
            if event_type != "status":
                return
            await self._on_robot_status(payload)

        robot_service.on_telemetry(on_status)

    async def go_home(self, *, speak: bool = True) -> dict:
        from services.tour_service import tour_service

        await tour_service.halt()
        await self._robot_service.stop()
        ok = await self._robot_service.go_home()
        if speak and ok:
            try:
                await self._robot_service.speak(
                    "Je retourne à la borne de recharge.",
                    interrupt=True,
                )
            except Exception as exc:
                logger.debug("TTS retour borne ignoré : %s", exc)
        return {
            "ok": ok,
            "returning_to_charge": self._robot_service.get_status().returning_to_charge,
            "charge_state": self._robot_service.get_status().charge_state,
        }

    async def _on_robot_status(self, status: dict) -> None:
        if not settings.auto_return_charge:
            return
        if status.get("mock"):
            return
        if status.get("charger"):
            self._auto_return_in_progress = False
            return
        if status.get("returning_to_charge"):
            return
        if self._auto_return_in_progress:
            return

        battery = int(status.get("battery") or 0)
        if battery > settings.low_battery_threshold:
            return

        now = time.monotonic()
        if now - self._last_auto_return_at < 120.0:
            return

        self._auto_return_in_progress = True
        self._last_auto_return_at = now
        logger.warning("Batterie basse (%s%%) — retour automatique vers la borne", battery)
        try:
            from services.tour_service import tour_service

            await tour_service.halt()
            await self.go_home(speak=True)
        except Exception as exc:
            logger.error("Retour charge auto échoué : %s", exc)
            self._auto_return_in_progress = False

    def get_config(self) -> dict:
        return {
            "low_battery_threshold": settings.low_battery_threshold,
            "auto_return_charge": settings.auto_return_charge,
        }


charge_service = ChargeService()
