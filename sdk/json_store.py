"""Lecture/écriture JSON atomique — persistance locale CYBEL (Phase 3)."""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: T) -> T:
    if not path.is_file():
        return default
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def append_log_entry(
    path: Path,
    entry: dict[str, Any],
    *,
    list_key: str = "entries",
    max_entries: int = 500,
    version: int = 1,
) -> dict[str, Any]:
    document = load_json(path, {list_key: [], "version": version})
    entries: list[dict[str, Any]] = list(document.get(list_key) or [])
    entry.setdefault("at", utc_now_iso())
    entries.append(entry)
    if len(entries) > max_entries:
        entries = entries[-max_entries:]
    document[list_key] = entries
    document["version"] = version
    document["updated_at"] = utc_now_iso()
    save_json(path, document)
    return entry
