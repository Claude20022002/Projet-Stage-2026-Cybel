import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter

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
}


@router.get("/config")
async def get_kiosk_config() -> dict:
    """Configuration d'affichage du kiosque visiteur (branding, veille, destinations mises en avant)."""
    if not _KIOSK_CONFIG_PATH.is_file():
        return _DEFAULT_CONFIG.copy()
    try:
        data = json.loads(_KIOSK_CONFIG_PATH.read_text(encoding="utf-8"))
        return {**_DEFAULT_CONFIG, **data}
    except (OSError, json.JSONDecodeError):
        return _DEFAULT_CONFIG.copy()
