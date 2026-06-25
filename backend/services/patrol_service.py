import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from sdk.patrol import (
    PatrolEngine,
    PatrolStop,
    default_patrol_path,
    list_patrol_tasks,
    load_patrol_store,
    load_patrol_task,
    patrol_task_from_dict,
    patrol_task_public_payload,
    save_patrol_store,
    validate_patrol_stop_dict,
    validate_patrol_task_dict,
)
from sdk.tour_navigation import assess_tour_readiness, navigation_wait_failure_message
from services.robot_service import robot_service


class PatrolService:
    def __init__(self) -> None:
        self._engine: PatrolEngine | None = None
        self._store_path = default_patrol_path()

    def is_running(self) -> bool:
        return self._engine is not None and self._engine.is_running()

    def _build_engine(self, task_id: str) -> PatrolEngine:
        task = load_patrol_task(task_id, self._store_path)

        async def speak(text: str) -> None:
            result = await robot_service.speak(text)
            if not result.get("ok"):
                raise RuntimeError(result.get("error", "TTS échoué"))
            await robot_service.wait_for_speech(text)

        async def navigate(stop: PatrolStop, index: int) -> None:
            if stop.has_coordinates():
                success = await robot_service.navigate_to_coordinate(
                    stop.x,
                    stop.y,
                    stop.theta or 0.0,
                    check_map=False,
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

            arrived = await robot_service.wait_for_navigation_arrival()
            if not arrived:
                status = robot_service.get_status()
                dest = stop.name
                err = navigation_wait_failure_message(
                    status.nav_status,
                    destination=dest,
                    never_started=status.nav_status == 601,
                )
                raise RuntimeError(err)

        async def stop_motion() -> None:
            await robot_service.stop()

        return PatrolEngine(task, speak, navigate, stop_motion)

    def list_tasks(self) -> list[dict]:
        return [patrol_task_public_payload(t) for t in list_patrol_tasks(self._store_path)]

    def get_task(self, task_id: str) -> dict:
        return patrol_task_public_payload(load_patrol_task(task_id, self._store_path))

    def get_status(self) -> dict:
        if self._engine is None:
            return {
                "state": "idle",
                "task_id": None,
                "task_name": "",
                "mode": "cycle",
                "lang": "fr",
                "current_index": -1,
                "total_stops": 0,
                "cycle_count": 0,
                "current_stop_id": None,
                "current_stop_name": "",
                "phase": "",
                "message": "",
                "error": None,
            }
        return self._engine.get_status().to_dict()

    async def start(self, task_id: str, lang: str = "fr") -> dict:
        if self.is_running():
            return {"ok": False, "error": "Une patrouille est déjà en cours", "code": "busy"}

        from services.tour_service import tour_service

        if tour_service._engine and tour_service._engine.is_running():
            return {"ok": False, "error": "Une visite guidée est en cours", "code": "busy"}

        self._engine = self._build_engine(task_id)

        if not robot_service.is_mock:
            status = robot_service.get_status()
            if status.nav_status in (602, 604):
                await robot_service.stop()
                await asyncio.sleep(0.5)
            if not await robot_service.ensure_automatic_navigation():
                self._engine = None
                return {
                    "ok": False,
                    "error": (
                        "Le robot n'a pas confirmé le mode navigation automatique — "
                        "annulez la navigation en cours puis réessayez"
                    ),
                    "code": "not_ready",
                }

            status = robot_service.get_status()
            ready, reason = assess_tour_readiness(
                status.nav_status,
                status.localization_percent,
                min_localization=settings.localization_min_percent,
            )
            if not ready:
                self._engine = None
                return {"ok": False, "error": reason, "code": "not_ready"}
            localized = await robot_service.ensure_localization(
                settings.localization_min_percent
            )
            if not localized:
                self._engine = None
                return {
                    "ok": False,
                    "error": (
                        f"Localisation insuffisante (< {settings.localization_min_percent:.0f} %). "
                        "Relocalisez le robot avant de lancer la patrouille."
                    ),
                    "code": "not_ready",
                }

        return await self._engine.start(lang)

    async def stop(self) -> dict:
        if self._engine is None:
            return {"ok": True, "status": self.get_status()}
        result = await self._engine.stop()
        self._engine = None
        return result

    def create_task(self, data: dict) -> dict:
        store = load_patrol_store(self._store_path)
        validated = validate_patrol_task_dict(data)
        tasks = store.get("tasks", [])
        if any(t.get("id") == validated["id"] for t in tasks):
            raise ValueError(f"Une tâche '{validated['id']}' existe déjà")
        tasks.append(validated)
        store["tasks"] = tasks
        save_patrol_store(store, self._store_path)
        return patrol_task_public_payload(patrol_task_from_dict(validated))

    def update_task(self, task_id: str, data: dict) -> dict:
        store = load_patrol_store(self._store_path)
        tasks = store.get("tasks", [])
        index = next((i for i, t in enumerate(tasks) if t.get("id") == task_id), None)
        if index is None:
            raise ValueError(f"Tâche '{task_id}' introuvable")
        merged = {**tasks[index], **data, "id": task_id}
        validated = validate_patrol_task_dict(merged)
        tasks[index] = validated
        store["tasks"] = tasks
        save_patrol_store(store, self._store_path)
        if self._engine and self._engine.task.id == task_id and self.is_running():
            raise ValueError("Impossible de modifier une patrouille en cours")
        return patrol_task_public_payload(patrol_task_from_dict(validated))

    def delete_task(self, task_id: str) -> None:
        if self.is_running() and self._engine and self._engine.task.id == task_id:
            raise ValueError("Arrêtez la patrouille avant de supprimer la tâche")
        store = load_patrol_store(self._store_path)
        tasks = store.get("tasks", [])
        filtered = [t for t in tasks if t.get("id") != task_id]
        if len(filtered) == len(tasks):
            raise ValueError(f"Tâche '{task_id}' introuvable")
        store["tasks"] = filtered
        save_patrol_store(store, self._store_path)


patrol_service = PatrolService()
