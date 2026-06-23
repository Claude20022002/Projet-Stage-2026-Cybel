import pytest

from sdk.rosbridge import _format_exc


def test_format_exc_with_message() -> None:
    assert _format_exc(TimeoutError("handshake")) == "TimeoutError: handshake"


def test_format_exc_empty_message() -> None:
    assert _format_exc(TimeoutError()) == "TimeoutError"
