"""Tests Phase 4 — réception go destination."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sdk.models import Point
from services.reception_service import ReceptionService


@pytest.fixture
def service() -> ReceptionService:
    return ReceptionService()


@pytest.mark.asyncio
async def test_go_unknown_destination(service: ReceptionService, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.reception_service.persistence_service.load_points",
        lambda: [],
    )
    monkeypatch.setattr(
        "services.reception_service.robot_service.get_points",
        lambda: [],
    )
    result = await service.go_to_destination("Inconnu")
    assert result["ok"] is False
    assert "inconnue" in result["error"].lower()


@pytest.mark.asyncio
async def test_go_starts_navigation(service: ReceptionService, monkeypatch: pytest.MonkeyPatch) -> None:
    point = Point(
        id="1",
        name="Accueil",
        type="common",
        x=1.0,
        y=2.0,
        kiosk_visible=True,
        source="local",
    )
    speak = AsyncMock(return_value={"ok": True, "method": "mock"})
    navigate_point = AsyncMock(return_value=False)
    navigate_coord = AsyncMock(return_value=True)
    wait_arrival = AsyncMock(return_value=True)

    monkeypatch.setattr(
        "services.reception_service.persistence_service.load_points",
        lambda: [point],
    )
    monkeypatch.setattr("services.reception_service.robot_service.speak", speak)
    monkeypatch.setattr(
        "services.reception_service.robot_service.navigate_to_point",
        navigate_point,
    )
    monkeypatch.setattr(
        "services.reception_service.robot_service.navigate_to_coordinate",
        navigate_coord,
    )
    monkeypatch.setattr(
        "services.reception_service.robot_service.wait_for_navigation_arrival",
        wait_arrival,
    )
    monkeypatch.setattr(
        "services.reception_service.robot_service.get_status",
        lambda: type("S", (), {"nav_status": 603})(),
    )
    monkeypatch.setattr(
        "services.reception_service.persistence_service.log_navigation",
        lambda **kwargs: {},
    )

    result = await service.go_to_destination("Accueil", lang="fr")
    assert result["ok"] is True
    assert result["point"] == "Accueil"
    speak.assert_awaited()
    navigate_coord.assert_awaited_with(1.0, 2.0, 0.0, check_map=False)
