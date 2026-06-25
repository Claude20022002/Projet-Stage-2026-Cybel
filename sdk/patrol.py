"""Patrouille cyclique — modèle et moteur d'exécution (Phase 5 CYB-050)."""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Literal

from sdk.lab_tour import slugify

PatrolMode = Literal["cycle", "round_trip", "random"]
PatrolPhase = Literal["", "navigating", "announcing", "dwell"]
PatrolStateName = Literal["idle", "running", "stopped", "error"]


@dataclass
class PatrolStop:
    id: str
    name: str
    name_en: str = ""
    speech_fr: str = ""
    speech_en: str = ""
    target_point: str | None = None
    x: float | None = None
    y: float | None = None
    theta: float | None = None
    dwell_seconds: float = 8.0

    def has_coordinates(self) -> bool:
        return self.x is not None and self.y is not None


@dataclass
class PatrolTask:
    id: str
    name: str
    mode: PatrolMode = "cycle"
    intro_speech_fr: str = ""
    intro_speech_en: str = ""
    stops: list[PatrolStop] | None = None

    def __post_init__(self) -> None:
        if self.stops is None:
            self.stops = []


@dataclass
class PatrolStatus:
    state: PatrolStateName = "idle"
    task_id: str | None = None
    task_name: str = ""
    mode: PatrolMode = "cycle"
    lang: str = "fr"
    current_index: int = -1
    total_stops: int = 0
    cycle_count: int = 0
    current_stop_id: str | None = None
    current_stop_name: str = ""
    phase: PatrolPhase = ""
    message: str = ""
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "mode": self.mode,
            "lang": self.lang,
            "current_index": self.current_index,
            "total_stops": self.total_stops,
            "cycle_count": self.cycle_count,
            "current_stop_id": self.current_stop_id,
            "current_stop_name": self.current_stop_name,
            "phase": self.phase,
            "message": self.message,
            "error": self.error,
        }


SpeakFn = Callable[[str], Awaitable[None]]
NavigateStopFn = Callable[[PatrolStop, int], Awaitable[None]]
StopMotionFn = Callable[[], Awaitable[None]]


def default_patrol_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "patrol_tasks.json"


def load_patrol_store(path: Path | None = None) -> dict:
    store_path = path or default_patrol_path()
    if not store_path.is_file():
        return {"version": 1, "tasks": []}
    with open(store_path, encoding="utf-8") as f:
        return json.load(f)


def save_patrol_store(data: dict, path: Path | None = None) -> None:
    store_path = path or default_patrol_path()
    store_path.parent.mkdir(parents=True, exist_ok=True)
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def validate_patrol_stop_dict(stop: dict) -> dict:
    stop_id = str(stop.get("id", "")).strip() or slugify(str(stop.get("name", "stop")))
    name = str(stop.get("name", "")).strip()
    if not name:
        raise ValueError("name est requis pour un arrêt de patrouille")
    has_coords = stop.get("x") is not None and stop.get("y") is not None
    has_point = bool(stop.get("target_point"))
    if not has_coords and not has_point:
        raise ValueError("Chaque arrêt doit avoir des coordonnées (x, y) ou un target_point")
    payload: dict = {
        "id": stop_id,
        "name": name,
        "name_en": str(stop.get("name_en", name)),
        "speech_fr": str(stop.get("speech_fr", "")),
        "speech_en": str(stop.get("speech_en", stop.get("speech_fr", ""))),
        "dwell_seconds": float(stop.get("dwell_seconds", 8)),
    }
    if has_point:
        payload["target_point"] = str(stop["target_point"])
    if has_coords:
        payload["x"] = float(stop["x"])
        payload["y"] = float(stop["y"])
        payload["theta"] = float(stop.get("theta", 0))
    return payload


def validate_patrol_task_dict(task: dict) -> dict:
    mode = str(task.get("mode", "cycle"))
    if mode not in ("cycle", "round_trip", "random"):
        raise ValueError("mode doit être cycle, round_trip ou random")
    stops = [validate_patrol_stop_dict(s) for s in task.get("stops", [])]
    if not stops:
        raise ValueError("Au moins un arrêt est requis")
    task_id = str(task.get("id", "")).strip() or slugify(str(task.get("name", "patrol")))
    name = str(task.get("name", "")).strip()
    if not name:
        raise ValueError("name est requis pour la tâche")
    return {
        "id": task_id,
        "name": name,
        "mode": mode,
        "intro_speech_fr": str(task.get("intro_speech_fr", "")),
        "intro_speech_en": str(task.get("intro_speech_en", task.get("intro_speech_fr", ""))),
        "stops": stops,
    }


def _stop_from_dict(raw: dict) -> PatrolStop:
    return PatrolStop(
        id=str(raw["id"]),
        name=str(raw["name"]),
        name_en=str(raw.get("name_en", raw["name"])),
        speech_fr=str(raw.get("speech_fr", "")),
        speech_en=str(raw.get("speech_en", raw.get("speech_fr", ""))),
        target_point=raw.get("target_point"),
        x=float(raw["x"]) if raw.get("x") is not None else None,
        y=float(raw["y"]) if raw.get("y") is not None else None,
        theta=float(raw["theta"]) if raw.get("theta") is not None else None,
        dwell_seconds=float(raw.get("dwell_seconds", 8)),
    )


def patrol_task_from_dict(raw: dict) -> PatrolTask:
    validated = validate_patrol_task_dict(raw)
    return PatrolTask(
        id=validated["id"],
        name=validated["name"],
        mode=validated["mode"],
        intro_speech_fr=validated["intro_speech_fr"],
        intro_speech_en=validated["intro_speech_en"],
        stops=[_stop_from_dict(s) for s in validated["stops"]],
    )


def load_patrol_task(task_id: str, path: Path | None = None) -> PatrolTask:
    store = load_patrol_store(path)
    for raw in store.get("tasks", []):
        if str(raw.get("id")) == task_id:
            return patrol_task_from_dict(raw)
    raise ValueError(f"Tâche de patrouille '{task_id}' introuvable")


def list_patrol_tasks(path: Path | None = None) -> list[PatrolTask]:
    store = load_patrol_store(path)
    tasks: list[PatrolTask] = []
    for raw in store.get("tasks", []):
        try:
            tasks.append(patrol_task_from_dict(raw))
        except ValueError:
            continue
    return tasks


def patrol_task_public_payload(task: PatrolTask) -> dict:
    return {
        "id": task.id,
        "name": task.name,
        "mode": task.mode,
        "intro_speech_fr": task.intro_speech_fr,
        "intro_speech_en": task.intro_speech_en,
        "stops": [
            {
                "id": s.id,
                "name": s.name,
                "name_en": s.name_en,
                "speech_fr": s.speech_fr,
                "speech_en": s.speech_en,
                **({"target_point": s.target_point} if s.target_point else {}),
                **(
                    {"x": s.x, "y": s.y, "theta": s.theta}
                    if s.has_coordinates()
                    else {}
                ),
                "dwell_seconds": s.dwell_seconds,
            }
            for s in task.stops or []
        ],
    }


class PatrolEngine:
    def __init__(
        self,
        task: PatrolTask,
        speak: SpeakFn,
        navigate: NavigateStopFn,
        stop_motion: StopMotionFn,
    ) -> None:
        self.task = task
        self._speak = speak
        self._navigate = navigate
        self._stop_motion = stop_motion
        self._status = PatrolStatus(
            task_id=task.id,
            task_name=task.name,
            mode=task.mode,
            total_stops=len(task.stops or []),
        )
        self._task: asyncio.Task | None = None
        self._cancel = False

    def get_status(self) -> PatrolStatus:
        return self._status

    def is_running(self) -> bool:
        return self._status.state == "running"

    async def start(self, lang: str = "fr") -> dict:
        if self.is_running():
            return {"ok": False, "error": "Une patrouille est déjà en cours"}
        if not self.task.stops:
            return {"ok": False, "error": "Aucun arrêt configuré"}

        self._cancel = False
        self._status = PatrolStatus(
            state="running",
            task_id=self.task.id,
            task_name=self.task.name,
            mode=self.task.mode,
            lang=lang,
            total_stops=len(self.task.stops),
            message="Démarrage de la patrouille…",
        )
        self._task = asyncio.create_task(self._run(lang))
        return {"ok": True, "status": self._status.to_dict()}

    async def stop(self) -> dict:
        self._cancel = True
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        try:
            await self._stop_motion()
        except Exception:
            pass
        self._status.state = "stopped"
        self._status.phase = ""
        self._status.message = "Patrouille interrompue"
        self._task = None
        return {"ok": True, "status": self._status.to_dict()}

    def _pick(self, fr: str, en: str | None, lang: str) -> str:
        if lang == "en" and en:
            return en
        return fr

    def _ordered_stops(self, cycle_index: int) -> list[PatrolStop]:
        stops = list(self.task.stops or [])
        if self.task.mode == "random":
            random.shuffle(stops)
        elif self.task.mode == "round_trip" and cycle_index % 2 == 1:
            stops = list(reversed(stops))
        return stops

    async def _run(self, lang: str) -> None:
        try:
            intro = self._pick(
                self.task.intro_speech_fr,
                self.task.intro_speech_en,
                lang,
            )
            if intro:
                self._status.message = "Annonce de départ"
                await self._speak(intro)
            if self._cancel:
                return

            cycle = 0
            while not self._cancel:
                cycle += 1
                self._status.cycle_count = cycle
                ordered = self._ordered_stops(cycle - 1)

                for index, stop in enumerate(ordered):
                    if self._cancel:
                        return

                    label = self._pick(stop.name, stop.name_en, lang)
                    self._status.current_index = index
                    self._status.current_stop_id = stop.id
                    self._status.current_stop_name = label

                    self._status.phase = "navigating"
                    self._status.message = f"Direction {label}"
                    await self._navigate(stop, index)
                    if self._cancel:
                        return

                    speech = self._pick(stop.speech_fr, stop.speech_en, lang)
                    if speech:
                        self._status.phase = "announcing"
                        self._status.message = speech
                        await self._speak(speech)
                        if self._cancel:
                            return

                    dwell = max(stop.dwell_seconds, 0)
                    if dwell > 0:
                        self._status.phase = "dwell"
                        self._status.message = f"Surveillance — {label}"
                        await asyncio.sleep(dwell)

                if self.task.mode == "cycle":
                    continue
                if self.task.mode in ("round_trip", "random"):
                    continue

        except asyncio.CancelledError:
            self._status.state = "stopped"
            self._status.message = "Patrouille interrompue"
            raise
        except Exception as exc:
            self._status.state = "error"
            self._status.error = str(exc)
            self._status.message = "Erreur pendant la patrouille"
        finally:
            self._task = None
