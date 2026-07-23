"""Parcours de visite du laboratoire — chargement et exécution séquentielle."""
from __future__ import annotations

import asyncio
import json
import math
import re
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Awaitable, Callable, Literal, Any

TourPhase = Literal["", "intro", "navigating", "presenting", "dwell", "outro", "returning"]
TourStateName = Literal["idle", "running", "completed", "stopped", "error"]


@dataclass
class TourStop:
    id: str
    name_fr: str
    name_en: str
    equipment_fr: str
    equipment_en: str
    speech_fr: str
    speech_en: str
    target_point: str | None = None
    x: float | None = None
    y: float | None = None
    theta: float | None = None
    approach_speech_fr: str | None = None
    approach_speech_en: str | None = None
    dwell_seconds: float = 10.0

    def has_coordinates(self) -> bool:
        return self.x is not None and self.y is not None

    def prefers_poi_navigation(self) -> bool:
        """POI nommé (Sentrymove) prioritaire sur coordonnées brutes."""
        return bool(self.target_point)


@dataclass
class LabTour:
    id: str
    title_fr: str
    title_en: str
    subtitle_fr: str
    subtitle_en: str
    intro_speech_fr: str
    intro_speech_en: str
    outro_speech_fr: str
    outro_speech_en: str
    stops: list[TourStop]
    return_point: str | None = None


@dataclass
class TourStatus:
    state: TourStateName = "idle"
    lang: str = "fr"
    current_index: int = -1
    total_stops: int = 0
    current_stop_id: str | None = None
    current_stop_name: str = ""
    current_equipment: str = ""
    phase: TourPhase = ""
    message: str = ""
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "lang": self.lang,
            "current_index": self.current_index,
            "total_stops": self.total_stops,
            "current_stop_id": self.current_stop_id,
            "current_stop_name": self.current_stop_name,
            "current_equipment": self.current_equipment,
            "phase": self.phase,
            "message": self.message,
            "error": self.error,
        }


SpeakFn = Callable[[str], Awaitable[None]]
NavigateStopFn = Callable[[TourStop, int], Awaitable[None]]
StopMotionFn = Callable[[], Awaitable[None]]


def default_tour_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "lab_tour.json"


def load_tour_data(path: Path | None = None) -> dict:
    tour_path = path or default_tour_path()
    with open(tour_path, encoding="utf-8") as f:
        return json.load(f)


def save_tour_data(data: dict, path: Path | None = None) -> None:
    tour_path = path or default_tour_path()
    tour_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tour_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    return slug or "stop"


def validate_stop_dict(stop: dict) -> dict:
    stop_id = str(stop.get("id", "")).strip() or slugify(
        str(stop.get("equipment_fr", "stop"))
    )
    equipment_fr = str(stop.get("equipment_fr", "")).strip()
    if not equipment_fr:
        raise ValueError("equipment_fr est requis")
    has_coords = stop.get("x") is not None and stop.get("y") is not None
    has_point = bool(stop.get("target_point"))
    if not has_coords and not has_point:
        raise ValueError("Chaque arrêt doit avoir des coordonnées (x, y) ou un target_point")
    return {
        "id": stop_id,
        "name_fr": str(stop.get("name_fr", equipment_fr)),
        "name_en": str(stop.get("name_en", stop.get("name_fr", equipment_fr))),
        "equipment_fr": equipment_fr,
        "equipment_en": str(stop.get("equipment_en", equipment_fr)),
        "speech_fr": str(stop.get("speech_fr", "")),
        "speech_en": str(stop.get("speech_en", stop.get("speech_fr", ""))),
        **({"target_point": str(stop["target_point"])} if has_point else {}),
        **(
            {
                "x": float(stop["x"]),
                "y": float(stop["y"]),
                "theta": float(stop.get("theta", 0)),
            }
            if has_coords
            else {}
        ),
        **(
            {"approach_speech_fr": stop["approach_speech_fr"]}
            if stop.get("approach_speech_fr")
            else {}
        ),
        **(
            {"approach_speech_en": stop["approach_speech_en"]}
            if stop.get("approach_speech_en")
            else {}
        ),
        "dwell_seconds": float(stop.get("dwell_seconds", 12)),
    }


def load_lab_tour(path: Path | None = None) -> LabTour:
    raw = load_tour_data(path)
    stops = [
        TourStop(
            id=str(s["id"]),
            name_fr=str(s["name_fr"]),
            name_en=str(s.get("name_en", s["name_fr"])),
            equipment_fr=str(s["equipment_fr"]),
            equipment_en=str(s.get("equipment_en", s["equipment_fr"])),
            speech_fr=str(s["speech_fr"]),
            speech_en=str(s.get("speech_en", s["speech_fr"])),
            target_point=s.get("target_point"),
            x=float(s["x"]) if s.get("x") is not None else None,
            y=float(s["y"]) if s.get("y") is not None else None,
            theta=float(s["theta"]) if s.get("theta") is not None else None,
            approach_speech_fr=s.get("approach_speech_fr"),
            approach_speech_en=s.get("approach_speech_en"),
            dwell_seconds=float(s.get("dwell_seconds", 10)),
        )
        for s in raw.get("stops", [])
    ]
    return LabTour(
        id=str(raw.get("id", "lab_tour")),
        title_fr=str(raw.get("title_fr", "Visite du laboratoire")),
        title_en=str(raw.get("title_en", "Laboratory tour")),
        subtitle_fr=str(raw.get("subtitle_fr", "")),
        subtitle_en=str(raw.get("subtitle_en", "")),
        intro_speech_fr=str(raw.get("intro_speech_fr", "")),
        intro_speech_en=str(raw.get("intro_speech_en", "")),
        outro_speech_fr=str(raw.get("outro_speech_fr", "")),
        outro_speech_en=str(raw.get("outro_speech_en", "")),
        stops=stops,
        return_point=raw.get("return_point") or None,
    )


def filter_tour_by_poi(tour: LabTour, available_names: set[str]) -> LabTour:
    """Ne conserve que les arrêts dont le POI existe sur la carte courante (hors obsolètes / charge)."""
    from sdk.poi_names import OBSOLETE_POI_NAMES, is_charge_poi_name

    kept: list[TourStop] = []
    for stop in tour.stops:
        if stop.target_point:
            if stop.target_point in OBSOLETE_POI_NAMES:
                continue
            if is_charge_poi_name(stop.target_point):
                continue
            if available_names and stop.target_point not in available_names:
                continue
        kept.append(stop)
    return replace(tour, stops=kept)


def reorder_stops_nearest_first(
    tour: LabTour,
    start_xy: tuple[float, float],
    point_coords: dict[str, tuple[float, float]],
) -> LabTour:
    """Réordonne les arrêts du plus proche au plus proche (glouton, style plus-proche-voisin),
    en partant de la position actuelle du robot, au lieu de l'ordre fixe défini dans le
    fichier de la visite. Réduit la distance totale parcourue (donc la durée de la visite)
    sans changer le contenu présenté.

    `point_coords` : nom de POI → (x, y), résolu par l'appelant (ex. depuis data/points.json)
    car ce module reste agnostique du mécanisme de résolution des POI. Les arrêts dont les
    coordonnées ne peuvent pas être résolues (POI inconnu, pas de x/y direct) sont ajoutés
    à la fin dans leur ordre d'origine plutôt que de faire échouer tout le réordonnancement.
    """

    def _coords(stop: TourStop) -> tuple[float, float] | None:
        if stop.target_point and stop.target_point in point_coords:
            return point_coords[stop.target_point]
        if stop.has_coordinates():
            return (float(stop.x), float(stop.y))
        return None

    remaining = list(tour.stops)
    ordered: list[TourStop] = []
    cx, cy = start_xy

    while remaining:
        best_index: int | None = None
        best_dist = math.inf
        best_coords: tuple[float, float] | None = None
        for i, stop in enumerate(remaining):
            coords = _coords(stop)
            if coords is None:
                continue
            dist = math.hypot(coords[0] - cx, coords[1] - cy)
            if dist < best_dist:
                best_dist = dist
                best_index = i
                best_coords = coords
        if best_index is None:
            # Plus aucun arrêt restant n'a de coordonnées résolues — on garde
            # le reste dans l'ordre d'origine plutôt que d'abandonner.
            ordered.extend(remaining)
            break
        ordered.append(remaining.pop(best_index))
        cx, cy = best_coords  # type: ignore[misc]

    return replace(tour, stops=ordered)


def tour_public_payload(tour: LabTour) -> dict:
    return {
        "id": tour.id,
        "title_fr": tour.title_fr,
        "title_en": tour.title_en,
        "subtitle_fr": tour.subtitle_fr,
        "subtitle_en": tour.subtitle_en,
        "stops": [
            {
                "id": s.id,
                "name_fr": s.name_fr,
                "name_en": s.name_en,
                "equipment_fr": s.equipment_fr,
                "equipment_en": s.equipment_en,
                **({"target_point": s.target_point} if s.target_point else {}),
                **(
                    {"x": s.x, "y": s.y, "theta": s.theta}
                    if s.has_coordinates()
                    else {}
                ),
            }
            for s in tour.stops
        ],
    }


class TourEngine:
    def __init__(
        self,
        tour: LabTour,
        speak: SpeakFn,
        navigate: NavigateStopFn,
        stop_motion: StopMotionFn,
        tracer: Any | None = None,
    ) -> None:
        self.tour = tour
        self._speak = speak
        self._navigate = navigate
        self._stop_motion = stop_motion
        self._tracer = tracer
        self._status = TourStatus(total_stops=len(tour.stops))
        self._task: asyncio.Task | None = None
        self._cancel = False

    def get_status(self) -> TourStatus:
        return self._status

    def is_running(self) -> bool:
        return self._status.state == "running"

    async def start(self, lang: str = "fr") -> dict:
        if self.is_running():
            return {"ok": False, "error": "Une visite est déjà en cours"}

        self._cancel = False
        self._status = TourStatus(
            state="running",
            lang=lang,
            total_stops=len(self.tour.stops),
            message="Démarrage de la visite…",
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
        self._status.message = "Visite interrompue"
        self._task = None
        return {"ok": True, "status": self._status.to_dict()}

    def _pick(self, fr: str, en: str | None, lang: str) -> str:
        if lang == "en" and en:
            return en
        return fr

    async def _run(self, lang: str) -> None:
        if self._tracer:
            self._tracer.tour_start(lang, self.tour.stops)
        try:
            self._status.phase = "intro"
            self._status.message = "Introduction"
            if self._tracer:
                self._tracer.phase("intro", message="Introduction")
            intro = self._pick(
                self.tour.intro_speech_fr, self.tour.intro_speech_en, lang
            )
            if intro:
                await self._speak(intro)
            if self._cancel:
                return

            for index, stop in enumerate(self.tour.stops):
                if self._cancel:
                    return

                name = self._pick(stop.name_fr, stop.name_en, lang)
                equipment = self._pick(stop.equipment_fr, stop.equipment_en, lang)
                self._status.current_index = index
                self._status.current_stop_id = stop.id
                self._status.current_stop_name = name
                self._status.current_equipment = equipment

                self._status.phase = "navigating"
                self._status.message = f"Direction {equipment}"
                if self._tracer:
                    self._tracer.phase(
                        "navigating",
                        index=index,
                        stop=stop,
                        message=f"Direction {equipment}",
                    )
                await self._navigate(stop, index)
                if self._cancel:
                    return

                approach = self._pick(
                    stop.approach_speech_fr or "",
                    stop.approach_speech_en,
                    lang,
                )
                if approach:
                    self._status.phase = "presenting"
                    self._status.message = approach
                    if self._tracer:
                        self._tracer.phase(
                            "presenting",
                            index=index,
                            stop=stop,
                            message="approach_speech",
                        )
                    await self._speak(approach)
                    if self._cancel:
                        return

                presentation = self._pick(stop.speech_fr, stop.speech_en, lang)
                self._status.phase = "presenting"
                self._status.message = presentation
                if self._tracer:
                    self._tracer.phase(
                        "presenting",
                        index=index,
                        stop=stop,
                        message="presentation",
                    )
                await self._speak(presentation)
                if self._cancel:
                    return

                self._status.phase = "dwell"
                self._status.message = "Observation des équipements"
                if self._tracer:
                    self._tracer.phase(
                        "dwell",
                        index=index,
                        stop=stop,
                        message="Observation",
                    )
                await asyncio.sleep(max(stop.dwell_seconds, 0))

            if self._cancel:
                return

            self._status.phase = "outro"
            outro = self._pick(
                self.tour.outro_speech_fr, self.tour.outro_speech_en, lang
            )
            if outro:
                self._status.message = "Fin de visite"
                if self._tracer:
                    self._tracer.phase("outro", message="Fin de visite")
                await self._speak(outro)

            if self.tour.return_point and not self._cancel:
                self._status.phase = "returning"
                self._status.message = f"Retour à {self.tour.return_point}"
                if self._tracer:
                    self._tracer.phase(
                        "returning", message=f"Retour {self.tour.return_point}"
                    )
                _return_stop = TourStop(
                    id="return_charge",
                    name_fr="Retour base de recharge",
                    name_en="Return to charging station",
                    equipment_fr=self.tour.return_point,
                    equipment_en=self.tour.return_point,
                    speech_fr="",
                    speech_en="",
                    target_point=self.tour.return_point,
                )
                try:
                    await self._navigate(_return_stop, len(self.tour.stops))
                except Exception:
                    pass

            self._status.state = "completed"
            self._status.phase = ""
            self._status.message = "Visite terminée"
            if self._tracer:
                self._tracer.tour_end("completed")
        except asyncio.CancelledError:
            self._status.state = "stopped"
            self._status.message = "Visite interrompue"
            if self._tracer:
                self._tracer.tour_end("stopped")
            raise
        except Exception as exc:
            self._status.state = "error"
            self._status.error = str(exc)
            self._status.message = "Erreur pendant la visite"
            if self._tracer:
                self._tracer.tour_end("error", error=str(exc))
        finally:
            self._task = None
