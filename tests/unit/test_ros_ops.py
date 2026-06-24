"""Tests helpers ROS Phase 0 (hors robot)."""

import pytest

from sdk.ros_ops import (
    build_global_locate_chain,
    build_poi_nav_chain,
    call_service_first,
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


@pytest.mark.asyncio
async def test_publish_first() -> None:
    client = FakeRosClient()
    topic = await publish_first(client, ["/move_base/cancel", "/path_follower/cancel"], {})
    assert topic == "/move_base/cancel"
    assert len(client.published) == 1
