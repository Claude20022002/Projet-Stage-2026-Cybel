"""Découverte du canal TTS ROS sur le robot CIOT — à lancer connecté au WiFi robot."""
import asyncio
import json
import sys
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sdk.constants import (
    SPEECH_PUBLISH_PAYLOADS,
    SPEECH_PUBLISH_TOPICS,
    SPEECH_SERVICE_ARGS,
    SPEECH_SERVICES,
)

ROSBRIDGE = "ws://10.42.0.1:9090"
TEST_PHRASE = "Bonjour, je suis le robot d'accueil."


async def call_service(ws, service: str, args: dict) -> dict:
    await ws.send(json.dumps({"op": "call_service", "service": service, "args": args}))
    try:
        resp = await asyncio.wait_for(ws.recv(), timeout=3.0)
        return json.loads(resp)
    except asyncio.TimeoutError:
        return {}


async def main() -> None:
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecté à rosbridge\n")
        print("=== Recherche topics/services contenant 'tts', 'speak', 'voice' ===\n")

        topics_resp = await call_service(ws, "/rosapi/topics", {})
        services_resp = await call_service(ws, "/rosapi/services", {})

        topics = topics_resp.get("values", {}).get("topics", [])
        services = services_resp.get("values", {}).get("services", [])

        keywords = ("tts", "speak", "voice", "audio", "sound", "play")
        for t in topics:
            if any(k in t.lower() for k in keywords):
                print(f"  TOPIC  : {t}")
        for s in services:
            if any(k in s.lower() for k in keywords):
                print(f"  SERVICE: {s}")

        print(f"\n=== Test publication TTS : « {TEST_PHRASE} » ===\n")
        for topic in SPEECH_PUBLISH_TOPICS:
            for build in SPEECH_PUBLISH_PAYLOADS[:2]:
                payload = build(TEST_PHRASE)
                await ws.send(
                    json.dumps({"op": "publish", "topic": topic, "msg": payload})
                )
                print(f"  >> publish {topic}  {payload}")

        print("\n=== Test services TTS ===\n")
        for service in SPEECH_SERVICES:
            for build in SPEECH_SERVICE_ARGS[:2]:
                args = build(TEST_PHRASE)
                resp = await call_service(ws, service, args)
                if resp:
                    print(f"  >> service {service}  args={args}")
                    print(f"     réponse: {str(resp)[:200]}")
                await asyncio.sleep(0.2)

        print("\n[Écoute 15s — observez si le robot parle ou si un topic répond]\n")
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
                data = json.loads(msg)
                if data.get("topic") or data.get("op") == "service_response":
                    print(json.dumps(data, ensure_ascii=False)[:400])
        except asyncio.TimeoutError:
            print("[Timeout]")


if __name__ == "__main__":
    asyncio.run(main())
