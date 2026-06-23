import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from sdk.constants import navigation_failure_message
from sdk.lab_tour import (
    TourEngine,
    TourStop,
    default_tour_path,
    load_lab_tour,
    load_tour_data,
    save_tour_data,
    slugify,
    tour_public_payload,
    validate_stop_dict,
)
from services.robot_service import robot_service


class TourService:
    def __init__(self) -> None:
        self._engine: TourEngine | None = None
        self._tour_path = default_tour_path()

    def _build_engine(self, tour_path: Path | None = None) -> TourEngine:
        path = tour_path or self._tour_path
        tour = load_lab_tour(path)

        async def speak(text: str) -> None:
            result = await robot_service.speak(text)
            if not result.get("ok"):
                raise RuntimeError(result.get("error", "TTS échoué"))
            await robot_service.wait_for_speech(text)

        async def navigate(stop: TourStop) -> None:
            if stop.has_coordinates():
                success = await robot_service.navigate_to_coordinate(
                    stop.x, stop.y, stop.theta or 0.0,
                    check_map=False,
                )
                if not success:
                    raise RuntimeError(
                        f"Navigation impossible vers ({stop.x}, {stop.y})"
                    )
                arrived = await robot_service.wait_for_navigation_arrival()
                if not arrived:
                    status = robot_service.get_status()
                    dest = stop.equipment_fr
                    raise RuntimeError(
                        navigation_failure_message(status.nav_status, destination=dest)
                    )
            elif stop.target_point:
                success = await robot_service.navigate_to_point(stop.target_point)
                if not success:
                    raise RuntimeError(
                        f"Point '{stop.target_point}' introuvable sur la carte"
                    )
                arrived = await robot_service.wait_for_navigation_arrival()
                if not arrived:
                    status = robot_service.get_status()
                    raise RuntimeError(
                        navigation_failure_message(
                            status.nav_status,
                            destination=stop.target_point or "",
                        )
                    )
            else:
                raise RuntimeError(f"Arrêt '{stop.id}' sans destination")

        async def stop_motion() -> None:
            await robot_service.stop()

        return TourEngine(tour, speak, navigate, stop_motion)

    def _ensure_engine(self) -> TourEngine:
        if self._engine is None:
            self._engine = self._build_engine()
        return self._engine

    def reset_engine(self) -> None:
        self._engine = None

    def reload_from_disk(self) -> dict:
        """Recharge lab_tour.json depuis le disque (après édition manuelle du fichier)."""
        self.reset_engine()
        return self.get_tour_full()

    def get_tour(self) -> dict:
        return tour_public_payload(load_lab_tour(self._tour_path))

    def get_tour_full(self) -> dict:
        return load_tour_data(self._tour_path)

    def get_status(self) -> dict:
        return self._ensure_engine().get_status().to_dict()

    async def start(self, lang: str = "fr") -> dict:
        if self._engine and self._engine.is_running():
            return {"ok": False, "error": "Une visite est déjà en cours"}
        # Recharge lab_tour.json à chaque démarrage (édition manuelle du fichier).
        self.reset_engine()
        if not robot_service.is_mock:
            localized = await robot_service.ensure_localization(
                settings.localization_min_percent
            )
            if not localized:
                return {
                    "ok": False,
                    "error": (
                        f"Localisation insuffisante (< {settings.localization_min_percent:.0f} %). "
                        "Placez le robot dans une zone connue et relancez la relocalisation."
                    ),
                }
            await robot_service.set_manual_mode(False)
        return await self._ensure_engine().start(lang)

    async def stop(self) -> dict:
        return await self._ensure_engine().stop()

    async def halt(self) -> dict:
        """Arrêt total : visite locale + robot + voix + backend kiosque."""
        await self.stop()
        await robot_service.stop()
        await robot_service.stop_speech()
        await self._halt_remote_kiosk()
        return {"ok": True, "message": "Arrêt total effectué"}

    async def _halt_remote_kiosk(self) -> None:
        base = settings.kiosk_backend_url.strip().rstrip("/")
        if not base:
            return
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(f"{base}/api/tour/halt")
        except Exception:
            pass

    def save_tour(self, data: dict) -> dict:
        stops = [validate_stop_dict(s) for s in data.get("stops", [])]
        payload = {**data, "stops": stops}
        save_tour_data(payload, self._tour_path)
        self.reset_engine()
        return payload

    def add_stop(self, stop: dict) -> dict:
        data = load_tour_data(self._tour_path)
        validated = validate_stop_dict(stop)
        if any(s.get("id") == validated["id"] for s in data.get("stops", [])):
            raise ValueError(f"Un arrêt avec l'id '{validated['id']}' existe déjà")
        data.setdefault("stops", []).append(validated)
        return self.save_tour(data)

    def update_stop(self, stop_id: str, stop: dict) -> dict:
        data = load_tour_data(self._tour_path)
        stops = data.get("stops", [])
        index = next((i for i, s in enumerate(stops) if s.get("id") == stop_id), None)
        if index is None:
            raise ValueError(f"Arrêt '{stop_id}' introuvable")
        updated = validate_stop_dict({**stops[index], **stop, "id": stop_id})
        stops[index] = updated
        data["stops"] = stops
        return self.save_tour(data)

    def delete_stop(self, stop_id: str) -> dict:
        data = load_tour_data(self._tour_path)
        stops = data.get("stops", [])
        filtered = [s for s in stops if s.get("id") != stop_id]
        if len(filtered) == len(stops):
            raise ValueError(f"Arrêt '{stop_id}' introuvable")
        data["stops"] = filtered
        return self.save_tour(data)

    def create_stop_from_pose(
        self,
        equipment_fr: str,
        x: float,
        y: float,
        theta: float = 0.0,
        **fields: str | float,
    ) -> dict:
        stop = {
            "id": slugify(equipment_fr),
            "equipment_fr": equipment_fr,
            "name_fr": fields.get("name_fr", equipment_fr),
            "speech_fr": fields.get(
                "speech_fr",
                f"Voici {equipment_fr}. Cet équipement fait partie de notre laboratoire.",
            ),
            "x": x,
            "y": y,
            "theta": theta,
            "dwell_seconds": fields.get("dwell_seconds", 12),
        }
        return self.add_stop(stop)


tour_service = TourService()
