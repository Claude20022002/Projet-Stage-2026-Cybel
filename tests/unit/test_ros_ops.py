"""Tests helpers ROS Phase 0 (hors robot)."""

import pytest

from sdk.ros_ops import (
    build_global_locate_chain,
    build_poi_nav_chain,
    call_service_first,
    extract_markers_from_ros_response,
    publish_first,
    service_succeeded,
)


class FakeRosClient:
    def __init__(
        self,
        *,
        service_results: dict[str, bool] | None = None,
        publish_ok: bool = True,
    ) -> None:
        self.service_results = service_results or {}
        self.publish_ok = publish_ok
        self.calls: list[tuple[str, dict]] = []
        self.published: list[tuple[str, dict]] = []

    async def call_service(self, service: str, args: dict | None = None, timeout: float = 5.0) -> dict:
        self.calls.append((service, args or {}))
        ok = self.service_results.get(service, True)
        return {"op": "service_response", "result": ok, "values": {}}

    async def publish(self, topic: str, msg: dict) -> None:
        if not self.publish_ok:
            raise RuntimeError("publish failed")
        self.published.append((topic, msg))

    async def advertise(self, topic: str, msg_type: str) -> None:
        pass


def test_service_succeeded() -> None:
    assert service_succeeded({"result": True})
    assert not service_succeeded({"result": False})
    assert service_succeeded({"values": {}})


@pytest.mark.asyncio
async def test_call_service_first_stops_on_success() -> None:
    client = FakeRosClient(
        service_results={
            "/tag_manager/navi": False,
            "/poi": True,
        }
    )
    service, _ = await call_service_first(client, build_poi_nav_chain("Accueil"))
    assert service == "/poi"
    assert [c[0] for c in client.calls] == ["/tag_manager/navi", "/poi"]


@pytest.mark.asyncio
async def test_call_service_first_global_locate() -> None:
    client = FakeRosClient(service_results={"/global_locate": True})
    service, _ = await call_service_first(client, build_global_locate_chain())
    assert service == "/global_locate"
    assert len(client.calls) == 1


def test_build_global_locate_chain_sends_typed_cmd_for_global_locate() -> None:
    """Régression : /global_locate est yutong_assistance/GlobalLocate (champ
    "cmd" requis), pas un service vide — un appel avec args={} ne répond
    jamais côté châssis (observé sur le robot le 2026-07-23 : timeout, aucune
    rotation réelle). /global_localization reste std_srvs/Empty (args={})."""
    chain = dict(build_global_locate_chain())
    assert chain["/global_locate"]["cmd"] == 0
    assert "search_step_linear" in chain["/global_locate"]
    assert chain["/global_localization"] == {}


@pytest.mark.asyncio
async def test_publish_first() -> None:
    client = FakeRosClient()
    topic = await publish_first(client, ["/move_base/cancel", "/path_follower/cancel"], {})
    assert topic == "/move_base/cancel"
    assert len(client.published) == 1


def test_extract_markers_from_floors_response() -> None:
    values = {
        "floors": [
            {
                "floor_name": "0",
                "markers": [
                    {
                        "name": "nous",
                        "pose": {
                            "position": {"x": -3.01, "y": -0.21, "z": 0.0},
                            "orientation": {"z": 0.552, "w": 0.834},
                        },
                    }
                ],
            }
        ]
    }
    markers = extract_markers_from_ros_response(values)
    assert len(markers) == 1
    assert markers[0]["name"] == "nous"
    assert markers[0]["floor"] == "0"


def test_extract_markers_from_waypoints_dict() -> None:
    values = {
        "markers": {
            "waypoints": [
                {"name": "gate", "pose": {"position": {"x": -7.87, "y": -0.68}}},
            ]
        }
    }
    markers = extract_markers_from_ros_response(values)
    assert len(markers) == 1
    assert markers[0]["name"] == "gate"
