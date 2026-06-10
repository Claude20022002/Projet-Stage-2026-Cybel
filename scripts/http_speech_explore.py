"""Découverte du canal TTS HTTP sur l'upper body Android — WiFi robot requis."""
import asyncio
import sys
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sdk.constants import SPEECH_HTTP_HOST, SPEECH_HTTP_PATHS, SPEECH_HTTP_PORTS

TEST_PHRASE = "Bonjour, test de synthese vocale."
TIMEOUT = 2.5


async def probe_url(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> bool:
    try:
        if method == "GET":
            resp = await client.get(url, **kwargs)
        else:
            resp = await client.post(url, **kwargs)
        ok = resp.status_code < 400
        preview = resp.text[:120].replace("\n", " ")
        status = "OK" if ok else "FAIL"
        print(f"  [{status} {resp.status_code}] {method} {url}")
        if preview:
            print(f"           → {preview}")
        return ok
    except Exception as exc:
        print(f"  [ERR] {method} {url} — {exc}")
        return False


async def main() -> None:
    host = SPEECH_HTTP_HOST
    print(f"=== Exploration TTS HTTP — {host} ===\n")
    print(f"Phrase test : « {TEST_PHRASE} »\n")

    hits: list[str] = []
    encoded = quote(TEST_PHRASE)
    post_bodies = (
        {"text": TEST_PHRASE},
        {"content": TEST_PHRASE},
        {"message": TEST_PHRASE},
        {"data": TEST_PHRASE},
    )

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for port in SPEECH_HTTP_PORTS:
            base = f"http://{host}:{port}"
            print(f"--- Port {port} ---")
            try:
                if await probe_url(client, "GET", base):
                    hits.append(base)
            except Exception:
                pass

            for path in SPEECH_HTTP_PATHS:
                url = f"{base}{path}"
                if await probe_url(
                    client,
                    "GET",
                    url,
                    params={"text": TEST_PHRASE, "content": TEST_PHRASE},
                ):
                    hits.append(f"GET {url}")

                for body in post_bodies:
                    if await probe_url(client, "POST", url, json=body):
                        hits.append(f"POST {url} json={list(body.keys())[0]}")

                for suffix in (f"?text={encoded}", f"?content={encoded}"):
                    if await probe_url(client, "POST", f"{url}{suffix}"):
                        hits.append(f"POST {url}{suffix}")

            print()

    if hits:
        print("=== Candidats prometteurs ===")
        for hit in dict.fromkeys(hits):
            print(f"  • {hit}")
        print("\nConfigurez backend/.env :")
        print("  SPEECH_HTTP_HOST=172.16.0.88")
        print("  SPEECH_HTTP_PORT=<port>")
        print("  SPEECH_HTTP_PATH=<chemin>")
    else:
        print("Aucune réponse HTTP — vérifiez la connectivité vers 172.16.0.88 depuis le robot.")


if __name__ == "__main__":
    asyncio.run(main())
