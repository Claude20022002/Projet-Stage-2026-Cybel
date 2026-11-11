"""Pont Android (sdk/android_bridge.py) et agent de la tête (scripts/termux/head_agent.py)."""

import importlib.util
import shlex
import subprocess
import threading
from pathlib import Path

import pytest

from sdk import android_bridge as ab

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "secret-de-test"
# Ce qu'un texte malveillant tenterait pour s'échapper d'un shell.
NASTY = "l'école\"; rm -rf / ; echo $(id) `whoami` 'fin"


def load_head_agent():
    spec = importlib.util.spec_from_file_location(
        "head_agent_under_test", ROOT / "scripts" / "termux" / "head_agent.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecordingBridge:
    """Bridge factice : enregistre les appels au lieu de lancer am."""

    mode = "fake"

    def __init__(self, ok: bool = True, running: bool = False) -> None:
        self.ok = ok
        self.running = running
        self.calls: list[tuple] = []

    def speak(self, text, lang="fr"):
        self.calls.append(("speak", text, lang))
        return self.ok

    def face_enroll(self, name, civility):
        self.calls.append(("face_enroll", name, civility))
        return self.ok

    def second_screen(self, show):
        self.calls.append(("second_screen", show))
        return self.ok

    def tts_running(self):
        return self.running


@pytest.fixture
def agent():
    head_agent = load_head_agent()
    bridge = RecordingBridge()
    server = head_agent.make_server("127.0.0.1", 0, TOKEN, bridge)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    yield url, bridge
    server.shutdown()
    server.server_close()


# ---- commandes ----------------------------------------------------------------

def test_text_stays_a_single_argument():
    argv = ab.tts_command(NASTY, "fr")
    assert argv[argv.index("text") + 1] == NASTY
    assert argv[0] == "am" and "sh" not in argv


def test_second_screen_command():
    assert ab.second_screen_command(True)[-1] == ab.SECOND_SCREEN_SERVICE
    assert ab.second_screen_command(False)[-2:] == ["-a", ab.SECOND_SCREEN_HIDE]


def test_su_fallback_keeps_arguments_intact(monkeypatch):
    attempts = []

    def fake_run(argv, **kwargs):
        attempts.append(argv)
        code = 1 if len(attempts) == 1 else 0
        return subprocess.CompletedProcess(argv, code, stdout="ok", stderr="")

    monkeypatch.setattr(ab.subprocess, "run", fake_run)
    argv = ab.tts_command(NASTY, "fr")
    ok, _ = ab.run_android(argv)
    assert ok
    assert attempts[0] == argv
    assert attempts[1][:2] == ["su", "-c"]
    # Le shell de su retrouve exactement les mêmes arguments, rien de plus.
    assert shlex.split(attempts[1][2]) == argv


def test_run_android_reports_failure(monkeypatch):
    def fail(argv, **kwargs):
        raise OSError("am introuvable")

    monkeypatch.setattr(ab.subprocess, "run", fail)
    assert ab.run_android(["am", "x"]) == (False, "")


def test_local_bridge_uses_runner():
    seen = []

    def runner(argv, timeout):
        seen.append(argv)
        out = f"ServiceRecord{{ {ab.TTS_SERVICE_MARKER} }}" if argv == ab.DUMPSYS_SERVICES else ""
        return True, out

    bridge = ab.LocalBridge(runner)
    assert bridge.speak("Bonjour", "fr")
    assert bridge.tts_running()
    assert seen[0] == ab.tts_command("Bonjour", "fr")


def test_local_bridge_tts_not_running_when_dumpsys_fails():
    assert not ab.LocalBridge(lambda argv, t: (False, ab.TTS_SERVICE_MARKER)).tts_running()


# ---- choix local / distant ----------------------------------------------------------

def test_bridge_from_env():
    assert isinstance(ab.bridge_from_env({}), ab.LocalBridge)
    remote = ab.bridge_from_env({ab.AGENT_URL_ENV: "http://10.0.0.2:8002/", ab.AGENT_TOKEN_ENV: "t"})
    assert isinstance(remote, ab.RemoteBridge) and remote.base_url == "http://10.0.0.2:8002"
    with pytest.raises(RuntimeError):
        ab.bridge_from_env({ab.AGENT_URL_ENV: "http://10.0.0.2:8002"})


# ---- agent + client distant, de bout en bout -------------------------------------------

def test_remote_speak_reaches_agent(agent):
    url, bridge = agent
    remote = ab.RemoteBridge(url, TOKEN)
    assert remote.speak(NASTY, "en")
    assert bridge.calls == [("speak", NASTY, "en")]


def test_remote_other_actions(agent):
    url, bridge = agent
    remote = ab.RemoteBridge(url, TOKEN)
    assert remote.face_enroll("Dupont", "M.")
    assert remote.second_screen(False)
    bridge.running = True
    assert remote.tts_running()
    assert remote.health()["ok"]
    assert ("face_enroll", "Dupont", "M.") in bridge.calls
    assert ("second_screen", False) in bridge.calls


def test_wrong_token_is_refused(agent):
    url, bridge = agent
    assert not ab.RemoteBridge(url, "mauvais").speak("Bonjour")
    assert bridge.calls == []


def test_agent_validates_input(agent):
    url, bridge = agent
    remote = ab.RemoteBridge(url, TOKEN)
    assert not remote.speak("Bonjour", "de")          # langue refusée
    assert not remote.speak("x" * 5000, "fr")          # texte trop long
    assert not remote.speak("   ", "fr")               # texte vide
    assert remote._call("/second-screen", {"show": "oui"}) == {}  # 400 → {}
    assert bridge.calls == []


def test_agent_reports_android_failure(agent):
    url, bridge = agent
    bridge.ok = False
    assert not ab.RemoteBridge(url, TOKEN).speak("Bonjour")


def test_unreachable_agent_fails_quietly():
    # Port 9 (discard) fermé sur 127.0.0.1 : refus immédiat, aucune exception.
    remote = ab.RemoteBridge("http://127.0.0.1:9", TOKEN, timeout=1.0)
    assert not remote.speak("Bonjour")
    assert not remote.tts_running()


def test_agent_refuses_empty_token():
    head_agent = load_head_agent()
    with pytest.raises(ValueError):
        head_agent.make_server("127.0.0.1", 0, "", RecordingBridge())
