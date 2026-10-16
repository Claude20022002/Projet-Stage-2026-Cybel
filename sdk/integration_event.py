"""Circulation de la semaine d'intégration HESTIM — TEMPORAIRE-INTEGRATION-2026.

Boucle sur une liste de POI : trajet, annonce vocale, pause, POI suivant. Lancée
depuis le panneau staff du kiosque (CYBEL Accueil), exécutée par le backend
Termux de la tête : le robot n'a pas besoin du PC.

Moteur pur (stdlib seule, chargé par fichier dans cybel_lite comme lab_tour) :
la navigation, l'état robot, la parole et l'annulation sont injectés, ce qui
le rend testable sans robot.

Garde-fous, avant chaque trajet : arrêt d'urgence, châssis déconnecté ou
localisation faible -> fin ; batterie basse -> retour au point de charge puis
fin ; MAX_FAILED_LEGS trajets ratés d'affilée -> fin.

À retirer après l'événement : voir docs/labo/JOURNEE_INTEGRATION.md, « Retrait ».
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal

CirculationState = Literal["idle", "running", "stopped", "error"]
CirculationPhase = Literal["", "navigating", "announcing", "dwell", "returning"]

NavigateFn = Callable[[str], Awaitable[tuple[bool, str]]]
ReadStatusFn = Callable[[], Awaitable[dict]]
AnnounceFn = Callable[[], Awaitable[None]]
CancelFn = Callable[[], Awaitable[None]]
SleepFn = Callable[[float], Awaitable[None]]

ATTEMPTS_PER_LEG = 2


@dataclass
class CirculationConfig:
    stops: list[str]
    dwell_seconds: float = 20.0
    battery_min: int = 25
    min_localization: float = 60.0
    return_point: str = "POINT-CHARGE"
    announce_on_arrival: bool = True
    max_failed_legs: int = 2

    @classmethod
    def from_dict(cls, raw: dict | None) -> "CirculationConfig":
        raw = raw or {}
        stops = [str(s).strip() for s in raw.get("stops") or [] if str(s).strip()]
        if not stops:
            raise ValueError("event.circulation.stops : au moins un POI est requis")
        return cls(
            stops=stops,
            dwell_seconds=max(0.0, float(raw.get("dwell_seconds", 20))),
            battery_min=int(raw.get("battery_min", 25)),
            min_localization=float(raw.get("min_localization", 60)),
            return_point=str(raw.get("return_point", "POINT-CHARGE")),
            announce_on_arrival=bool(raw.get("announce_on_arrival", True)),
            max_failed_legs=max(1, int(raw.get("max_failed_legs", 2))),
        )


@dataclass
class CirculationStatus:
    state: CirculationState = "idle"
    phase: CirculationPhase = ""
    cycle: int = 0
    current_stop: str = ""
    legs_ok: int = 0
    legs_failed: int = 0
    message: str = ""
    error: str | None = None
    started_at: float | None = None
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "phase": self.phase,
            "cycle": self.cycle,
            "current_stop": self.current_stop,
            "legs_ok": self.legs_ok,
            "legs_failed": self.legs_failed,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at,
            "history": self.history[-10:],
        }


def safety_stop_reason(status: dict, config: CirculationConfig) -> str | None:
    """Raison d'interrompre la circulation avant un trajet, ou None."""
    if not status.get("connected"):
        return "Châssis non connecté"
    if status.get("hard_estop") or status.get("soft_estop"):
        return "Arrêt d'urgence enclenché"
    loc = status.get("localization_percent")
    if loc is None or float(loc) < config.min_localization:
        return (
            f"Localisation faible ({loc} %) — relocaliser avec Deployment Tool"
        )
    return None


def battery_low(status: dict, config: CirculationConfig) -> bool:
    battery = status.get("battery")
    return battery is not None and int(battery) < config.battery_min


class CirculationEngine:
    def __init__(
        self,
        config: CirculationConfig,
        *,
        navigate: NavigateFn,
        read_status: ReadStatusFn,
        announce: AnnounceFn,
        cancel: CancelFn,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self.config = config
        self._navigate = navigate
        self._read_status = read_status
        self._announce = announce
        self._cancel = cancel
        self._sleep = sleep
        self._status = CirculationStatus()
        self._task: asyncio.Task | None = None
        self._stop_requested = False

    def get_status(self) -> CirculationStatus:
        return self._status

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> dict:
        if self.is_running():
            return {"ok": False, "error": "La circulation est déjà en cours"}
        self._stop_requested = False
        self._status = CirculationStatus(
            state="running",
            message="Démarrage de la circulation",
            started_at=time.time(),
        )
        self._task = asyncio.create_task(self._run())
        return {"ok": True, "status": self._status.to_dict()}

    async def stop(self) -> dict:
        self._stop_requested = True
        if self.is_running():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        try:
            await self._cancel()
        except Exception:
            pass
        if self._status.state == "running":
            self._finish("stopped", "Circulation arrêtée par le staff")
        return {"ok": True, "status": self._status.to_dict()}

    # ---- interne -----------------------------------------------------------
    def _record(self, event: str, **data) -> None:
        self._status.history.append(
            {"at": time.strftime("%H:%M:%S"), "event": event, **data}
        )
        del self._status.history[:-50]

    def _finish(self, state: CirculationState, message: str, error: str | None = None) -> None:
        self._status.state = state
        self._status.phase = ""
        self._status.message = message
        self._status.error = error
        self._record("fin", raison=message)

    async def _leg(self, name: str) -> bool:
        for attempt in range(1, ATTEMPTS_PER_LEG + 1):
            self._record("depart", vers=name, tentative=attempt)
            try:
                ok, err = await self._navigate(name)
            except Exception as exc:  # préparation refusée, rosbridge, etc.
                ok, err = False, str(exc)
            if ok:
                self._record("arrivee", vers=name)
                return True
            self._record("echec", vers=name, erreur=err)
            self._status.message = f"Trajet vers {name} échoué : {err}"
            if self._stop_requested:
                return False
            await self._cancel()
        return False

    async def _run(self) -> None:
        cfg = self.config
        failed_in_a_row = 0
        try:
            while not self._stop_requested:
                self._status.cycle += 1
                self._record("cycle", numero=self._status.cycle)
                for name in cfg.stops:
                    status = await self._read_status()
                    reason = safety_stop_reason(status, cfg)
                    if reason:
                        await self._cancel()
                        self._finish("error", reason, error=reason)
                        return
                    if battery_low(status, cfg):
                        self._status.phase = "returning"
                        self._status.current_stop = cfg.return_point
                        self._status.message = (
                            f"Batterie {status.get('battery')} % : retour à {cfg.return_point}"
                        )
                        await self._leg(cfg.return_point)
                        self._finish("stopped", "Batterie basse — robot renvoyé au point de charge")
                        return

                    self._status.phase = "navigating"
                    self._status.current_stop = name
                    self._status.message = f"Direction {name}"
                    if await self._leg(name):
                        failed_in_a_row = 0
                        self._status.legs_ok += 1
                        if cfg.announce_on_arrival:
                            self._status.phase = "announcing"
                            try:
                                await self._announce()
                            except Exception as exc:  # une annonce ratée n'arrête rien
                                self._record("annonce_echec", erreur=str(exc))
                        self._status.phase = "dwell"
                        self._status.message = f"Pause à {name}"
                        await self._sleep(cfg.dwell_seconds)
                    else:
                        failed_in_a_row += 1
                        self._status.legs_failed += 1
                        if failed_in_a_row >= cfg.max_failed_legs:
                            await self._cancel()
                            reason = f"{failed_in_a_row} trajets ratés d'affilée"
                            self._finish("error", reason, error=self._status.message)
                            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            try:
                await self._cancel()
            except Exception:
                pass
            self._finish("error", "Erreur pendant la circulation", error=str(exc))
