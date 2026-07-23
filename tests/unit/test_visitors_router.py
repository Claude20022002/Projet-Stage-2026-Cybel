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

import services.persistence_service as persistence_service_module
import services.visitor_service as visitor_service_module
from routers.visitors import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_visitors_storage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        persistence_service_module.persistence_service, "visitors_path", tmp_path / "visitors.json"
    )
    visitor_service_module.visitor_service._current = None


def test_enroll_requires_consent() -> None:
    response = client.post(
        "/api/visitors/enroll",
        json={"name": "Alice", "civility": "Mme", "embedding": [1.0, 0.0, 0.0], "consent": False},
    )
    assert response.status_code == 400


def test_enroll_then_identify_above_threshold() -> None:
    enroll = client.post(
        "/api/visitors/enroll",
        json={"name": "Alice", "civility": "Mme", "embedding": [1.0, 0.0, 0.0], "consent": True},
    )
    assert enroll.status_code == 200

    identify = client.post(
        "/api/visitors/identify",
        json={"embedding": [1.0, 0.0, 0.0], "confidence": 0.9},
    )
    assert identify.status_code == 200
    data = identify.json()
    assert data["ok"] is True
    assert data["visitor"]["name"] == "Alice"


def test_identify_below_threshold_returns_not_ok() -> None:
    client.post(
        "/api/visitors/enroll",
        json={"name": "Alice", "civility": "Mme", "embedding": [1.0, 0.0, 0.0], "consent": True},
    )
    identify = client.post(
        "/api/visitors/identify",
        json={"embedding": [0.0, 1.0, 0.0], "confidence": 0.9},
    )
    assert identify.status_code == 200
    data = identify.json()
    assert data["ok"] is False
    assert data["visitor"] is None


def test_current_never_exposes_embedding() -> None:
    client.post(
        "/api/visitors/enroll",
        json={"name": "Alice", "civility": "Mme", "embedding": [1.0, 0.0, 0.0], "consent": True},
    )
    client.post(
        "/api/visitors/identify",
        json={"embedding": [1.0, 0.0, 0.0], "confidence": 0.9},
    )

    current_response = client.get("/api/visitors/current")
    assert "embedding" not in current_response.text
    assert current_response.json()["visitor"]["name"] == "Alice"


def test_list_relays_to_kiosk_and_never_exposes_embedding(monkeypatch) -> None:
    async def fake_list_remote() -> list[dict]:
        return [
            {
                "id": "abc",
                "name": "Alice",
                "civility": "Mme",
                "consent": True,
                "enrolled_at": "2026-07-23T00:00:00+00:00",
                "last_identified_at": None,
            }
        ]

    monkeypatch.setattr(visitor_service_module.visitor_service, "list_remote", fake_list_remote)
    response = client.get("/api/visitors")
    assert response.status_code == 200
    assert "embedding" not in response.text
    assert response.json()[0]["name"] == "Alice"


def test_list_no_kiosk_configured_returns_503(monkeypatch) -> None:
    async def fake_list_remote() -> list[dict]:
        raise RuntimeError("kiosk_backend_url non configuré")

    monkeypatch.setattr(visitor_service_module.visitor_service, "list_remote", fake_list_remote)
    response = client.get("/api/visitors")
    assert response.status_code == 503


def test_delete_unknown_visitor_returns_404(monkeypatch) -> None:
    async def fake_remove_remote(visitor_id: str) -> tuple[int, dict]:
        return 404, {"ok": False, "error": f"Visiteur '{visitor_id}' introuvable"}

    monkeypatch.setattr(visitor_service_module.visitor_service, "remove_remote", fake_remove_remote)
    response = client.delete("/api/visitors/does-not-exist")
    assert response.status_code == 404


def test_delete_existing_visitor_relays_to_kiosk(monkeypatch) -> None:
    async def fake_remove_remote(visitor_id: str) -> tuple[int, dict]:
        assert visitor_id == "abc"
        return 200, {"ok": True}

    monkeypatch.setattr(visitor_service_module.visitor_service, "remove_remote", fake_remove_remote)
    response = client.delete("/api/visitors/abc")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_enroll_trigger_requires_name() -> None:
    response = client.post("/api/visitors/enroll-trigger", json={"name": ""})
    assert response.status_code == 400


def test_enroll_trigger_relays_to_kiosk(monkeypatch) -> None:
    async def fake_trigger(name: str, civility: str) -> dict:
        assert name == "Bob"
        assert civility == "M."
        return {"ok": True, "name": name, "window_seconds": 15}

    monkeypatch.setattr(
        visitor_service_module.visitor_service, "trigger_remote_enrollment", fake_trigger
    )
    response = client.post(
        "/api/visitors/enroll-trigger", json={"name": "Bob", "civility": "M."}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_enroll_trigger_no_kiosk_configured_returns_503(monkeypatch) -> None:
    async def fake_trigger(name: str, civility: str) -> dict:
        raise RuntimeError("kiosk_backend_url non configuré")

    monkeypatch.setattr(
        visitor_service_module.visitor_service, "trigger_remote_enrollment", fake_trigger
    )
    response = client.post("/api/visitors/enroll-trigger", json={"name": "Bob"})
    assert response.status_code == 503


def test_kiosk_telemetry_ws_url_derives_from_http_setting(monkeypatch) -> None:
    from config import settings

    monkeypatch.setattr(settings, "kiosk_backend_url", "http://192.168.20.22:8001")
    assert (
        visitor_service_module.visitor_service.kiosk_telemetry_ws_url()
        == "ws://192.168.20.22:8001/ws/telemetry"
    )

    monkeypatch.setattr(settings, "kiosk_backend_url", "")
    assert visitor_service_module.visitor_service.kiosk_telemetry_ws_url() is None


def test_kiosk_status_url_reflects_config(monkeypatch) -> None:
    monkeypatch.setattr(
        visitor_service_module.visitor_service,
        "kiosk_telemetry_ws_url",
        lambda: "ws://192.168.20.22:8001/ws/telemetry",
    )
    response = client.get("/api/visitors/kiosk-status-url")
    assert response.status_code == 200
    assert response.json()["ws_url"] == "ws://192.168.20.22:8001/ws/telemetry"
