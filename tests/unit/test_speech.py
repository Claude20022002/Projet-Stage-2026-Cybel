import asyncio

import pytest

from sdk.speech import RobotSpeech


@pytest.mark.asyncio
async def test_mock_speech_wait_for_completion():
    speech = RobotSpeech(mock=True)
    await speech.speak("Bonjour test")
    await speech.wait_for_completion("Bonjour test", timeout=5.0)
    assert speech.get_status().speaking is False
