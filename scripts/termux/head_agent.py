#!/usr/bin/env python3
"""Agent de la tête Android : exécute les actions Android pour un backend distant.

Quand le backend CYBEL tourne sur le Raspberry Pi compagnon et non plus dans
Termux, il ne peut plus lancer ``am broadcast`` lui-même. Cet agent, lancé
dans Termux sur la tête, le fait à sa place (voir sdk/android_bridge.py,
``RemoteBridge``).

    CYBEL_HEAD_TOKEN=<secret> python head_agent.py              # port 8002
    CYBEL_HEAD_TOKEN=<secret> python head_agent.py --dry-run    # journalise sans exécuter

Routes (en-tête ``X-Cybel-Token`` obligatoire sauf /health) :
    GET  /health          {"ok": true, "dry_run": …}
    POST /speak           {"text", "lang"}       → CybelTTSBridge
    GET  /tts/running     {"running": bool}       → dumpsys
    POST /face/enroll     {"name", "civility"}    → CybelFaceBridge
    POST /second-screen   {"show": bool}          → CybelSecondScreen

Stdlib uniquement : rien à installer dans Termux.
"""

from __future__ import annotations

import argparse
import hmac
import importlib.util
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_PORT = 8002
MAX_BODY_BYTES = 8192
MAX_TEXT_CHARS = 2000
MAX_NAME_CHARS = 100
LANGS = ("fr", "en")


def _load_android_bridge():
    """sdk/android_bridge.py, depuis CYBEL_HOME ou depuis ce dépôt."""
    candidates = [
        Path(os.environ.get("CYBEL_HOME", Path.home() / "cybel")) / "sdk" / "android_bridge.py",
        Path(__file__).resolve().parents[2] / "sdk" / "android_bridge.py",
    ]
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location("cybel_android_bridge", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    sys.exit(f"android_bridge.py introuvable ({', '.join(map(str, candidates))})")


android_bridge = _load_android_bridge()


def dry_run_runner(argv: list[str], timeout: float) -> tuple[bool, str]:
    print(f"[dry-run] {argv}", flush=True)
    return True, ""


class _Rejected(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _text(body: dict, key: str, limit: int) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _Rejected(400, f"« {key} » manquant")
    if len(value) > limit:
        raise _Rejected(413, f"« {key} » trop long (max {limit} caractères)")
    return value


def make_server(host: str, port: int, token: str, bridge, *, dry_run: bool = False) -> ThreadingHTTPServer:
    if not token:
        raise ValueError("token vide : l'agent refuse de démarrer sans secret partagé")
    expected = token.encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        server_version = "CybelHeadAgent/1.0"

        def log_message(self, fmt: str, *args) -> None:
            print(f"{time.strftime('%H:%M:%S')} {self.client_address[0]} {fmt % args}", flush=True)

        def _reply(self, status: int, payload: dict) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self) -> bool:
            given = self.headers.get(android_bridge.TOKEN_HEADER, "").encode("utf-8")
            return hmac.compare_digest(given, expected)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                raise _Rejected(413, "requête trop grosse")
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                raise _Rejected(400, "JSON invalide") from None
            if not isinstance(body, dict):
                raise _Rejected(400, "objet JSON attendu")
            return body

        def _handle(self, method: str) -> None:
            if self.path == "/health" and method == "GET":
                return self._reply(200, {"ok": True, "dry_run": dry_run})
            if not self._authorized():
                return self._reply(401, {"ok": False, "error": "jeton invalide"})
            try:
                if self.path == "/tts/running" and method == "GET":
                    return self._reply(200, {"running": bridge.tts_running()})
                if method != "POST":
                    raise _Rejected(404, "route inconnue")
                body = self._body()
                if self.path == "/speak":
                    lang = body.get("lang", "fr")
                    if lang not in LANGS:
                        raise _Rejected(400, f"langue non prise en charge : {lang!r}")
                    ok = bridge.speak(_text(body, "text", MAX_TEXT_CHARS), lang)
                elif self.path == "/face/enroll":
                    ok = bridge.face_enroll(
                        _text(body, "name", MAX_NAME_CHARS),
                        _text(body, "civility", MAX_NAME_CHARS),
                    )
                elif self.path == "/second-screen":
                    if not isinstance(body.get("show"), bool):
                        raise _Rejected(400, "« show » doit être true ou false")
                    ok = bridge.second_screen(body["show"])
                else:
                    raise _Rejected(404, "route inconnue")
            except _Rejected as exc:
                return self._reply(exc.status, {"ok": False, "error": str(exc)})
            self._reply(200 if ok else 502, {"ok": ok})

        def do_GET(self) -> None:  # noqa: N802 (API http.server)
            self._handle("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._handle("POST")

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CYBEL_HEAD_AGENT_PORT", DEFAULT_PORT)))
    parser.add_argument("--dry-run", action="store_true", help="journalise les commandes sans les exécuter")
    args = parser.parse_args()

    token = os.environ.get(android_bridge.AGENT_TOKEN_ENV, "").strip()
    if not token:
        sys.exit(f"{android_bridge.AGENT_TOKEN_ENV} vide : définir le secret partagé avec le backend")
    runner = dry_run_runner if args.dry_run else android_bridge.run_android
    server = make_server(args.host, args.port, token, android_bridge.LocalBridge(runner), dry_run=args.dry_run)
    print(f"Agent tête CYBEL — http://{args.host}:{args.port}{' (dry-run)' if args.dry_run else ''}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
