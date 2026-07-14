import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/kiosk", tags=["kiosk"])

_KIOSK_CONFIG_PATH = ROOT / "data" / "kiosk_config.json"

_DEFAULT_CONFIG = {
    "organization_name_fr": "CYBEL",
    "organization_name_en": "CYBEL",
    "welcome_message_fr": "Bienvenue ! Touchez l'écran pour commencer.",
    "welcome_message_en": "Welcome! Touch the screen to begin.",
    "logo_url": "/kiosk/logo.svg",
    "standby_timeout_seconds": 90,
    "featured_destinations": [],
    "reception_actions": ["welcome_guest", "go_meeting_room", "wait_mode"],
    "presence_welcome_enabled": True,
    "presence_max_distance_m": 3.0,
    "presence_cooldown_seconds": 90,
    "presence_speak_welcome": True,
    "face_recognition_enabled": False,
    "face_recognition_threshold": 0.82,
}


class KioskConfigUpdate(BaseModel):
    organization_name_fr: str | None = None
    organization_name_en: str | None = None
    welcome_message_fr: str | None = None
    welcome_message_en: str | None = None
    logo_url: str | None = None
    standby_timeout_seconds: int | None = Field(default=None, ge=0, le=600)
    featured_destinations: list[str] | None = None
    reception_actions: list[str] | None = None
    presence_welcome_enabled: bool | None = None
    presence_max_distance_m: float | None = Field(default=None, ge=0.0, le=20.0)
    presence_cooldown_seconds: int | None = Field(default=None, ge=0, le=3600)
    presence_speak_welcome: bool | None = None
    face_recognition_enabled: bool | None = None
    face_recognition_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


def _load_config() -> dict:
    if not _KIOSK_CONFIG_PATH.is_file():
        return _DEFAULT_CONFIG.copy()
    try:
        data = json.loads(_KIOSK_CONFIG_PATH.read_text(encoding="utf-8"))
        return {**_DEFAULT_CONFIG, **data}
    except (OSError, json.JSONDecodeError):
        return _DEFAULT_CONFIG.copy()


def _save_config(data: dict) -> None:
    _KIOSK_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _KIOSK_CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


@router.get("/config")
async def get_kiosk_config() -> dict:
    """Configuration d'affichage du kiosque visiteur (branding, veille, destinations mises en avant)."""
    return _load_config()


@router.put("/config")
async def update_kiosk_config(body: KioskConfigUpdate) -> dict:
    """Met à jour la configuration kiosque (page Paramètres opérateur)."""
    current = _load_config()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Aucun champ à mettre à jour")
    current.update(updates)
    try:
        _save_config(current)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "config": current}
