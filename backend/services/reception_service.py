import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk.models import ReceptionAction, VoiceCommand
from sdk.reception_actions import DEFAULT_ACTIONS, match_voice_command
from services.robot_service import robot_service


class ReceptionService:
    def list_actions(self) -> list[ReceptionAction]:
        return [a.model_copy(deep=True) for a in DEFAULT_ACTIONS]

    def get_action(self, action_id: str) -> ReceptionAction | None:
        return next((a for a in DEFAULT_ACTIONS if a.id == action_id), None)

    async def execute(self, action_id: str) -> dict:
        action = self.get_action(action_id)
        if not action:
            return {"ok": False, "error": f"Action '{action_id}' inconnue"}

        events: list[str] = []

        if action_id == "stop_all":
            await robot_service.stop()
            events.append("Action interrompue")
            return {"ok": True, "action": action_id, "events": events}

        if action.speech:
            speech_result = await robot_service.speak(action.speech)
            if speech_result.get("ok"):
                method = speech_result.get("method", "unknown")
                events.append(f"Annonce : {action.speech} ({method})")
            else:
                events.append(f"TTS échoué : {speech_result.get('error', 'inconnu')}")
            await asyncio.sleep(0.3)

        if action.target_point:
            success = await robot_service.navigate_to_point(action.target_point)
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

    async def handle_voice(self, command: VoiceCommand) -> dict:
        action_id = match_voice_command(command.text)
        if not action_id:
            return {
                "ok": False,
                "error": "Commande vocale non reconnue",
                "text": command.text,
            }
        result = await self.execute(action_id)
        result["matched_action"] = action_id
        result["text"] = command.text
        return result


reception_service = ReceptionService()
