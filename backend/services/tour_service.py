import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk.lab_tour import TourEngine, TourStop, load_lab_tour, tour_public_payload
from services.robot_service import robot_service


class TourService:
    def __init__(self) -> None:
        self._engine: TourEngine | None = None

    def _ensure_engine(self) -> TourEngine:
        if self._engine is None:
            tour = load_lab_tour()

            async def speak(text: str) -> None:
                result = await robot_service.speak(text)
                if not result.get("ok"):
                    raise RuntimeError(result.get("error", "TTS échoué"))
                await asyncio.sleep(0.3)

            async def navigate(stop: TourStop) -> None:
                if stop.has_coordinates():
                    success = await robot_service.navigate_to_coordinate(
                        stop.x, stop.y, stop.theta or 0.0
                    )
                    if not success:
                        raise RuntimeError(
                            f"Navigation impossible vers ({stop.x}, {stop.y})"
                        )
                elif stop.target_point:
                    success = await robot_service.navigate_to_point(stop.target_point)
                    if not success:
                        raise RuntimeError(
                            f"Point '{stop.target_point}' introuvable sur la carte"
                        )
                else:
                    raise RuntimeError(f"Arrêt '{stop.id}' sans destination")

            async def stop_motion() -> None:
                await robot_service.stop()

            self._engine = TourEngine(tour, speak, navigate, stop_motion)
        return self._engine

    def get_tour(self) -> dict:
        return tour_public_payload(load_lab_tour())

    def get_status(self) -> dict:
        engine = self._ensure_engine()
        return engine.get_status().to_dict()

    async def start(self, lang: str = "fr") -> dict:
        engine = self._ensure_engine()
        return await engine.start(lang)

    async def stop(self) -> dict:
        engine = self._ensure_engine()
        return await engine.stop()


tour_service = TourService()
