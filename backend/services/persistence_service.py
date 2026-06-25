"""Façade backend pour la persistance JSON."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from sdk.persistence import JsonPersistence

persistence_service = JsonPersistence(
    settings.data_dir,
    history_max_entries=settings.history_max_entries,
)
