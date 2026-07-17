import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from sdk.lab_tour import (
    TourEngine,
    TourStop,
    default_tour_path,
    filter_tour_by_poi,
    load_lab_tour,
    load_tour_data,
    save_tour_data,
    slugify,
    tour_public_payload,
    validate_stop_dict,
)
from sdk.tour_navigation import (
    assess_tour_readiness,
    navigation_recovery_hint,
    navigation_wait_failure_message,
)
from sdk.tour_trace import (
    get_active_tour_logger,
    pose_dict,
    start_tour_logger,
)
from services.robot_service import robot_service


def _robot_snapshot() -> dict:
    status = robot_service.get_status()
    pose = robot_service.get_pose()
    goal = status.current_goal
    snap = {
        **pose_dict(round(pose.x, 3), round(pose.y, 3), round(pose.theta, 3)),
        "nav_status": status.nav_status,
        "nav_status_label": status.nav_status_label,
        "localization_percent": round(status.localization_percent, 1),
        "navigating_to": status.navigating_to,
    }
    if goal is not None:
        snap["current_goal"] = pose_dict(
            round(goal.x, 3), round(goal.y, 3), round(goal.theta, 3)
        )
    return snap


async def _wait_navigation_traced(
    tracer,
    stop: TourStop,
    index: int,
) -> bool:
    loop = asyncio.get_running_loop()
    started = loop.time()

    async def _poll() -> None:
        while True:
            await asyncio.sleep(3.0)
            status = robot_service.get_status()
            tracer.nav_progress(
                stop,
                index=index,
                robot=_robot_snapshot(),
                nav_status=status.nav_status,
                nav_status_label=status.nav_status_label,
                elapsed_s=loop.time() - started,
            )

    poll_task = asyncio.create_task(_poll())
    try:
        return await robot_service.wait_for_navigation_arrival()
    finally:
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass


class TourService:
    def __init__(self) -> None:
        self._engine: TourEngine | None = None
        self._tour_path = default_tour_path()

    def _build_engine(
        self,
        tour_path: Path | None = None,
        tracer=None,
        available_poi: set[str] | None = None,
    ) -> TourEngine:
        path = tour_path or self._tour_path
        tour = load_lab_tour(path)
        if available_poi is not None:
            tour = filter_tour_by_poi(tour, available_poi)

        async def speak(text: str) -> None:
            result = await robot_service.speak(text)
            if not result.get("ok"):
                raise RuntimeError(result.get("error", "TTS échoué"))
            await robot_service.wait_for_speech(text)

        async def navigate(stop: TourStop, index: int) -> None:
            snap_before = _robot_snapshot()
            if tracer:
                tracer.robot_snapshot("nav_before", snap_before, stop=stop)
            if stop.target_point:
                if tracer:
                    tracer.nav_command(
                        stop,
                        index=index,
                        robot=snap_before,
                        nav_status=snap_before.get("nav_status"),
                        nav_status_label=str(snap_before.get("nav_status_label", "")),
                        detail=f"service /tag_manager/navi → {stop.target_point}",
                    )
                success = await robot_service.navigate_to_point(stop.target_point)
                if not success:
                    if tracer:
                        tracer.nav_result(
                            stop,
                            index=index,
                            robot=_robot_snapshot(),
                            success=False,
                            error=f"Point '{stop.target_point}' introuvable",
                        )
                    raise RuntimeError(
                        f"Point '{stop.target_point}' introuvable sur la carte"
                    )
                arrived = (
                    await _wait_navigation_traced(tracer, stop, index)
                    if tracer
                    else await robot_service.wait_for_navigation_arrival()
                )
                if not arrived:
                    status = robot_service.get_status()
                    err = navigation_wait_failure_message(
                        status.nav_status,
                        destination=stop.target_point or "",
                        never_started=status.nav_status == 601,
                    )
                    err = f"{err} {navigation_recovery_hint(status.nav_status)}"
                    if tracer:
                        tracer.nav_result(
                            stop,
                            index=index,
                            robot=_robot_snapshot(),
                            success=False,
                            nav_status=status.nav_status,
                            nav_status_label=status.nav_status_label,
                            error=err,
                        )
                    raise RuntimeError(err)
                if tracer:
                    status = robot_service.get_status()
                    tracer.nav_result(
                        stop,
                        index=index,
                        robot=_robot_snapshot(),
                        success=True,
                        nav_status=status.nav_status,
                        nav_status_label=status.nav_status_label,
                    )
            elif stop.has_coordinates():
                if tracer:
                    tracer.nav_command(
                        stop,
                        index=index,
                        robot=snap_before,
                        nav_status=snap_before.get("nav_status"),
                        nav_status_label=str(snap_before.get("nav_status_label", "")),
                        detail=f"publish /navi_goal ({stop.x}, {stop.y}, {stop.theta or 0})",
                    )
                success = await robot_service.navigate_to_coordinate(
                    stop.x, stop.y, stop.theta or 0.0,
                    check_map=False,
                )
                if not success:
                    status = robot_service.get_status()
                    if tracer:
                        tracer.nav_result(
                            stop,
                            index=index,
                            robot=_robot_snapshot(),
                            success=False,
                            nav_status=status.nav_status,
                            nav_status_label=status.nav_status_label,
                            error="Commande navigation refusée",
                        )
                    raise RuntimeError(
                        f"Navigation impossible vers ({stop.x}, {stop.y})"
                    )
                arrived = (
                    await _wait_navigation_traced(tracer, stop, index)
                    if tracer
                    else await robot_service.wait_for_navigation_arrival()
                )
                if not arrived:
                    status = robot_service.get_status()
                    dest = stop.equipment_fr
                    err = navigation_wait_failure_message(
                        status.nav_status,
                        destination=dest,
                        never_started=status.nav_status == 601,
                    )
                    err = f"{err} {navigation_recovery_hint(status.nav_status)}"
                    if tracer:
                        tracer.nav_result(
                            stop,
                            index=index,
                            robot=_robot_snapshot(),
                            success=False,
                            nav_status=status.nav_status,
                            nav_status_label=status.nav_status_label,
                            error=err,
                        )
                    raise RuntimeError(err)
                if tracer:
                    status = robot_service.get_status()
                    tracer.nav_result(
                        stop,
                        index=index,
                        robot=_robot_snapshot(),
                        success=True,
                        nav_status=status.nav_status,
                        nav_status_label=status.nav_status_label,
                    )
            else:
                raise RuntimeError(f"Arrêt '{stop.id}' sans destination")

        async def stop_motion() -> None:
            await robot_service.stop()

        return TourEngine(tour, speak, navigate, stop_motion, tracer=tracer)

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

    def get_trace(self) -> dict:
        tracer = get_active_tour_logger()
        if tracer is None:
            return {"session_id": None, "log_file": None, "entries": []}
        return tracer.status_payload()

    async def start(self, lang: str = "fr") -> dict:
        if self._engine and self._engine.is_running():
            return {"ok": False, "error": "Une visite est déjà en cours"}

        from services.patrol_service import patrol_service

        if patrol_service.is_running():
            return {"ok": False, "error": "Une patrouille est en cours"}

        if not robot_service.is_mock:
            from services.poi_bootstrap import ensure_poi_synced_from_robot

            try:
                await ensure_poi_synced_from_robot()
            except Exception as exc:
                return {"ok": False, "error": f"Synchronisation POI impossible : {exc}"}

        self.reset_engine()
        tour = load_lab_tour(self._tour_path)
        tracer = start_tour_logger(tour_id=tour.id)
        tracer.robot_snapshot("tour_start_pose", _robot_snapshot())
        from services.persistence_service import persistence_service

        available_poi = {p.name for p in persistence_service.load_points()}
        self._engine = self._build_engine(
            tracer=tracer,
            available_poi=available_poi,
        )
        if not robot_service.is_mock:
            status = robot_service.get_status()
            ready, reason = assess_tour_readiness(
                status.nav_status,
                status.localization_percent,
                min_localization=settings.localization_min_percent,
                require_known_localization=True,
            )
            if not ready:
                return {"ok": False, "error": reason}
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
        result = await self._engine.start(lang)
        tracer = get_active_tour_logger()
        if result.get("ok") and tracer:
            result = {
                **result,
                "trace_session": tracer.session_id,
                "trace_log": str(tracer.log_file) if tracer.log_file else None,
            }
        return result

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
