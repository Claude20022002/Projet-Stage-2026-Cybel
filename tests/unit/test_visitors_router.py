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


def test_list_and_current_never_expose_embedding() -> None:
    client.post(
        "/api/visitors/enroll",
        json={"name": "Alice", "civility": "Mme", "embedding": [1.0, 0.0, 0.0], "consent": True},
    )
    client.post(
        "/api/visitors/identify",
        json={"embedding": [1.0, 0.0, 0.0], "confidence": 0.9},
    )

    list_response = client.get("/api/visitors")
    assert "embedding" not in list_response.text

    current_response = client.get("/api/visitors/current")
    assert "embedding" not in current_response.text
    assert current_response.json()["visitor"]["name"] == "Alice"


def test_delete_unknown_visitor_returns_404() -> None:
    response = client.delete("/api/visitors/does-not-exist")
    assert response.status_code == 404


def test_delete_existing_visitor() -> None:
    enroll = client.post(
        "/api/visitors/enroll",
        json={"name": "Alice", "civility": "Mme", "embedding": [1.0, 0.0, 0.0], "consent": True},
    )
    visitor_id = enroll.json()["id"]
    response = client.delete(f"/api/visitors/{visitor_id}")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert client.get("/api/visitors").json() == []
