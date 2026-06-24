import pytest

from sdk.rosbridge import RosbridgeClient, _format_exc


def test_format_exc_with_message() -> None:
    assert _format_exc(TimeoutError("handshake")) == "TimeoutError: handshake"


def test_format_exc_empty_message() -> None:
    assert _format_exc(TimeoutError()) == "TimeoutError"


@pytest.mark.asyncio
async def test_advertise_sends_correct_op(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict] = []

    async def fake_send(payload: dict) -> None:
        sent.append(payload)

    client = RosbridgeClient("ws://127.0.0.1:9090")
    monkeypatch.setattr(client, "_send", fake_send)

    await client.advertise("/cmd_vel_mux/input/teleop", "geometry_msgs/Twist")

    assert sent == [
        {
            "op": "advertise",
            "topic": "/cmd_vel_mux/input/teleop",
            "type": "geometry_msgs/Twist",
        }
    ]
