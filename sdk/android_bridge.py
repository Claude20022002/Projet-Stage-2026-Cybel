"""Pont vers les applications Android de la tête du robot.

Le backend embarqué (scripts/termux/cybel_lite.py) déclenche quatre actions
Android : la synthèse vocale (CybelTTSBridge), l'état de cette synthèse
(dumpsys), l'enrôlement facial (CybelFaceBridge) et l'écran du dessous
(CybelSecondScreen). Deux façons de les exécuter :

- ``LocalBridge`` : le backend tourne SUR la tête (Termux) et lance les
  commandes ``am`` / ``dumpsys`` lui-même — fonctionnement historique ;
- ``RemoteBridge`` : le backend tourne ailleurs (Raspberry Pi compagnon) et
  demande à l'agent de la tête (scripts/termux/head_agent.py) de les lancer.

``bridge_from_env()`` choisit selon ``CYBEL_HEAD_AGENT_URL``.

Les commandes sont passées en liste d'arguments, jamais à un shell : un texte
contenant une apostrophe ou un point-virgule reste un seul argument. L'ancien
code les assemblait en chaîne pour ``sh -c``, et son repli ``su -c '…'``
cassait les guillemets dès la première apostrophe (« l'école »).

Stdlib uniquement : chargé par fichier dans cybel_lite (Termux) et sur le Pi.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping

TTS_RECEIVER = "com.cybel.ttsbridge/.SpeakReceiver"
TTS_ACTION = "com.cybel.ttsbridge.SPEAK"
TTS_SERVICE_MARKER = "com.cybel.ttsbridge/.SpeakService"
FACE_ENROLL_RECEIVER = "com.cybel.facebridge/.EnrollReceiver"
FACE_ENROLL_ACTION = "com.cybel.facebridge.ENROLL"
SECOND_SCREEN_SERVICE = "com.cybel.secondscreen/.SecondScreenService"
SECOND_SCREEN_HIDE = "com.cybel.secondscreen.HIDE"
DUMPSYS_SERVICES = ["dumpsys", "activity", "services"]

AGENT_URL_ENV = "CYBEL_HEAD_AGENT_URL"
AGENT_TOKEN_ENV = "CYBEL_HEAD_TOKEN"
TOKEN_HEADER = "X-Cybel-Token"

# (argv, timeout) -> (réussi, sortie)
Runner = Callable[[list[str], float], tuple[bool, str]]


def tts_command(text: str, lang: str) -> list[str]:
    return ["am", "broadcast", "-n", TTS_RECEIVER, "-a", TTS_ACTION,
            "--es", "text", text, "--es", "lang", lang]


def face_enroll_command(name: str, civility: str) -> list[str]:
    return ["am", "broadcast", "-n", FACE_ENROLL_RECEIVER, "-a", FACE_ENROLL_ACTION,
            "--es", "name", name, "--es", "civility", civility]


def second_screen_command(show: bool) -> list[str]:
    argv = ["am", "startservice", "-n", SECOND_SCREEN_SERVICE]
    return argv if show else [*argv, "-a", SECOND_SCREEN_HIDE]


def run_android(argv: list[str], timeout: float = 5.0) -> tuple[bool, str]:
    """Lance la commande, puis en root si elle échoue (certaines tablettes
    refusent ``am`` à l'utilisateur Termux). ``shlex.join`` garde chaque
    argument intact une fois dans la chaîne passée à ``su -c``."""
    for attempt in (argv, ["su", "-c", shlex.join(argv)]):
        try:
            result = subprocess.run(attempt, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return True, (result.stdout or "") + (result.stderr or "")
    return False, ""


class LocalBridge:
    """Exécute les actions sur l'appareil courant (tête Android)."""

    mode = "local"

    def __init__(self, runner: Runner = run_android) -> None:
        self._run = runner

    def speak(self, text: str, lang: str = "fr") -> bool:
        return self._run(tts_command(text, lang), 5.0)[0]

    def face_enroll(self, name: str, civility: str) -> bool:
        return self._run(face_enroll_command(name, civility), 5.0)[0]

    def second_screen(self, show: bool) -> bool:
        return self._run(second_screen_command(show), 5.0)[0]

    def tts_running(self) -> bool:
        ok, output = self._run(DUMPSYS_SERVICES, 4.0)
        return ok and TTS_SERVICE_MARKER in output


class RemoteBridge:
    """Demande à l'agent de la tête d'exécuter les actions.

    Une panne réseau ne lève jamais d'exception : l'action est signalée comme
    échouée (``False``), comme un ``am`` refusé en local. Pour ``tts_running``,
    ``False`` fait retomber l'attente de fin de parole sur l'estimation par la
    longueur du texte (sdk/speech_timing.py).
    """

    mode = "remote"

    def __init__(self, base_url: str, token: str, timeout: float = 4.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def _call(self, path: str, body: dict | None = None, timeout: float | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method="POST" if body is not None else "GET",
            headers={"Content-Type": "application/json", TOKEN_HEADER: self._token},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout or self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (OSError, ValueError):  # URLError, HTTPError, délai, JSON invalide
            return {}

    def speak(self, text: str, lang: str = "fr") -> bool:
        return bool(self._call("/speak", {"text": text, "lang": lang}).get("ok"))

    def face_enroll(self, name: str, civility: str) -> bool:
        return bool(self._call("/face/enroll", {"name": name, "civility": civility}).get("ok"))

    def second_screen(self, show: bool) -> bool:
        return bool(self._call("/second-screen", {"show": show}).get("ok"))

    def tts_running(self) -> bool:
        # Sondé toutes les 0,2 s pendant la parole : délai court.
        return bool(self._call("/tts/running", timeout=1.0).get("running"))

    def health(self) -> dict:
        return self._call("/health")


def bridge_from_env(env: Mapping[str, str] | None = None) -> LocalBridge | RemoteBridge:
    env = os.environ if env is None else env
    url = env.get(AGENT_URL_ENV, "").strip()
    if not url:
        return LocalBridge()
    token = env.get(AGENT_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"{AGENT_URL_ENV} est défini mais {AGENT_TOKEN_ENV} est vide")
    return RemoteBridge(url, token)
