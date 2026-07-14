import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = ROOT / "backend"
for path in (str(ROOT), str(BACKEND)):
    if path not in sys.path:
        sys.path.insert(0, path)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.kiosk import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_kiosk_config_endpoint() -> None:
    response = client.get("/api/kiosk/config")
    assert response.status_code == 200
    data = response.json()
    assert "organization_name_fr" in data
    assert "welcome_message_fr" in data
    assert "standby_timeout_seconds" in data
    assert isinstance(data["featured_destinations"], list)
    assert data["face_recognition_enabled"] is False
    assert data["face_recognition_threshold"] == pytest.approx(0.82)


def test_kiosk_config_merges_file(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "kiosk_config.json"
    config_path.write_text(
        json.dumps({"organization_name_fr": "Test Lab"}),
        encoding="utf-8",
    )
    import routers.kiosk as kiosk_router

    monkeypatch.setattr(kiosk_router, "_KIOSK_CONFIG_PATH", config_path)
    response = client.get("/api/kiosk/config")
    assert response.status_code == 200
    assert response.json()["organization_name_fr"] == "Test Lab"


def test_kiosk_config_put(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "kiosk_config.json"
    config_path.write_text(json.dumps({"organization_name_fr": "Avant"}), encoding="utf-8")
    import routers.kiosk as kiosk_router

    monkeypatch.setattr(kiosk_router, "_KIOSK_CONFIG_PATH", config_path)
    response = client.put(
        "/api/kiosk/config",
        json={"welcome_message_fr": "Bonjour test", "organization_name_fr": "Après"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["config"]["organization_name_fr"] == "Après"
    assert data["config"]["welcome_message_fr"] == "Bonjour test"
