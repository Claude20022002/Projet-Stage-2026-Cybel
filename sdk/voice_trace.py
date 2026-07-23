"""Journalisation structurée des échanges vocaux (latence bout-en-bout,
déclenchements du mot d'éveil) — même schéma que sdk/tour_trace.py, pour
alimenter scripts/measure_voice_latency.py (métriques papier ICRA 2027)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cybel.voice_trace")


def default_voice_log_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "logs" / "voice"


@dataclass
class VoiceSessionLogger:
    """Écrit chaque événement (échange vocal, déclenchement mot d'éveil) en
    fichier JSONL — un fichier par démarrage de processus backend."""

    log_dir: Path | None = None
    max_buffer: int = 400
    _buffer: list[dict[str, Any]] = field(default_factory=list, init=False)
    _path: Path | None = field(default=None, init=False)
    _session_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        base = self.log_dir or default_voice_log_dir()
        base.mkdir(parents=True, exist_ok=True)
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._path = base / f"voice_{self._session_id}.log"

    @property
    def log_file(self) -> Path | None:
        return self._path

    def record(self, event: str, **payload: Any) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session": self._session_id,
            "event": event,
            **payload,
        }
        self._buffer.append(entry)
        if len(self._buffer) > self.max_buffer:
            self._buffer = self._buffer[-self.max_buffer :]

        line = json.dumps(entry, ensure_ascii=False)
        logger.info("[voice] %s", line)
        if self._path:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
