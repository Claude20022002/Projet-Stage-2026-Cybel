import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from sdk.models import Point, ReceptionAction, VoiceCommand
from sdk.reception_actions import DEFAULT_ACTIONS, match_point_navigation, match_voice_command
from services.knowledge_service import knowledge_service
from services.persistence_service import persistence_service
from services.robot_service import robot_service


class ReceptionService:
    def list_actions(self) -> list[ReceptionAction]:
        return [a.model_copy(deep=True) for a in DEFAULT_ACTIONS]

    def get_action(self, action_id: str) -> ReceptionAction | None:
        return next((a for a in DEFAULT_ACTIONS if a.id == action_id), None)

    def find_point(self, point_name: str) -> Point | None:
        for point in persistence_service.load_points():
            if point.name == point_name:
                return point
        return next((p for p in robot_service.get_points() if p.name == point_name), None)

    async def execute(self, action_id: str, lang: str = "fr") -> dict:
        action = self.get_action(action_id)
        if not action:
            return {"ok": False, "error": f"Action '{action_id}' inconnue"}

        events: list[str] = []

        if action_id == "stop_all":
            await robot_service.stop()
            events.append("Action interrompue")
            return {"ok": True, "action": action_id, "events": events}

        speech_text = action.speech_en if lang == "en" and action.speech_en else action.speech
        if speech_text:
            speech_result = await robot_service.speak(speech_text)
            if speech_result.get("ok"):
                method = speech_result.get("method", "unknown")
                events.append(f"Annonce : {speech_text} ({method})")
            else:
                events.append(f"TTS échoué : {speech_result.get('error', 'inconnu')}")
            await asyncio.sleep(0.3)

        if action.target_point:
            success = await self._navigate_to_point_or_coordinate(action.target_point)
            if not success:
                return {
                    "ok": False,
                    "error": f"Point '{action.target_point}' introuvable sur la carte",
                }
            events.append(f"Navigation vers {action.target_point}")

        if action.route_name:
            events.append(
                f"Visite guidée '{action.route_name}' — à synchroniser avec le module GUIDED du robot"
            )

        if not events:
            events.append(f"Action '{action.label}' exécutée")

        return {"ok": True, "action": action_id, "events": events}

    async def go_to_destination(self, point_name: str, lang: str = "fr") -> dict:
        point = self.find_point(point_name)
        if not point:
            return {"ok": False, "error": f"Destination « {point_name} » inconnue"}

        welcome_fr = f"Bienvenue ! Je vous accompagne vers {point_name}. Suivez-moi."
        welcome_en = f"Welcome! I will take you to {point_name}. Please follow me."
        arrival_fr = f"Nous sommes arrivés à {point_name}."
        arrival_en = f"We have arrived at {point_name}."

        speech = welcome_en if lang == "en" else welcome_fr
        speech_result = await robot_service.speak(speech)
        events: list[str] = [f"Accueil : {speech}"]
        if not speech_result.get("ok"):
            events.append(f"TTS échoué : {speech_result.get('error', 'inconnu')}")

        success = await self._navigate_to_point_or_coordinate(point_name, point)
        if not success:
            return {
                "ok": False,
                "error": f"Impossible de naviguer vers « {point_name} »",
                "point": point_name,
                "events": events,
            }
        events.append(f"Navigation vers {point_name}")

        asyncio.create_task(
            self._announce_arrival(
                point_name,
                arrival_fr if lang == "fr" else arrival_en,
            )
        )

        return {"ok": True, "point": point_name, "events": events}

    async def handle_voice(self, command: VoiceCommand, lang: str = "fr") -> dict:
        action_id = match_voice_command(command.text)
        if action_id:
            result = await self.execute(action_id, lang)
            result["matched_action"] = action_id
            result["text"] = command.text
            return result

        points = persistence_service.load_points() or robot_service.get_points()
        point_names = [p.name for p in points]

        knowledge = knowledge_service.ask(command.text, lang=lang, point_names=point_names)
        if knowledge:
            return await self._execute_knowledge(knowledge, command.text)

        point_name = match_point_navigation(command.text, point_names)
        if point_name:
            success = await self._navigate_to_point_or_coordinate(point_name)
            if not success:
                return {
                    "ok": False,
                    "error": f"Point '{point_name}' introuvable sur la carte",
                    "text": command.text,
                }
            return {
                "ok": True,
                "matched_point": point_name,
                "events": [f"Navigation vers {point_name}"],
                "text": command.text,
            }

        return {
            "ok": False,
            "error": "Commande vocale non reconnue",
            "text": command.text,
        }

    async def _execute_knowledge(self, knowledge: dict, text: str) -> dict:
        events: list[str] = []
        answer = str(knowledge.get("answer", ""))
        if answer:
            speech_result = await robot_service.speak(answer)
            events.append(f"Réponse : {answer}")
            if not speech_result.get("ok"):
                events.append(f"TTS échoué : {speech_result.get('error', 'inconnu')}")

        navigated = False
        point_name = knowledge.get("point_name")
        coords = knowledge.get("coordinates")
        if point_name:
            navigated = await self._navigate_to_point_or_coordinate(str(point_name))
            if navigated:
                events.append(f"Navigation vers {point_name}")
        elif isinstance(coords, dict) and coords.get("x") is not None and coords.get("y") is not None:
            navigated = await robot_service.navigate_to_coordinate(
                float(coords["x"]),
                float(coords["y"]),
                float(coords.get("theta") or 0.0),
                check_map=False,
            )
            if navigated:
                events.append(
                    f"Navigation vers ({coords['x']}, {coords['y']})"
                )

        if not answer and not navigated:
            return {
                "ok": False,
                "error": "Entrée knowledge sans action exploitable",
                "text": text,
            }

        return {
            "ok": True,
            "matched_knowledge": knowledge.get("entry_id"),
            "source": knowledge.get("source"),
            "events": events,
            "text": text,
        }

    async def _navigate_to_point_or_coordinate(
        self, point_name: str, point: Point | None = None
    ) -> bool:
        point = point or self.find_point(point_name)
        success = await robot_service.navigate_to_point(point_name)
        if success:
            return True
        if point is not None:
            return await robot_service.navigate_to_coordinate(
                point.x,
                point.y,
                point.theta,
                check_map=False,
            )
        return False

    async def _announce_arrival(self, point_name: str, speech: str) -> None:
        arrived = await robot_service.wait_for_navigation_arrival(
            timeout=settings.navigation_wait_timeout
        )
        if arrived:
            await robot_service.speak(speech)
            persistence_service.log_navigation(
                kind="kiosk_arrival",
                success=True,
                point_name=point_name,
                nav_status=robot_service.get_status().nav_status,
                detail="TTS arrivée kiosque",
            )


reception_service = ReceptionService()
