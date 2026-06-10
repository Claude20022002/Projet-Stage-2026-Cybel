import asyncio
import websockets
import json
from datetime import datetime

ROSBRIDGE = "ws://10.42.0.1:9090"

# Tous les topics susceptibles de recevoir les commandes joystick
TOPICS = [
    "/cmd_vel",
    "/mobile_base/commands/velocity",
    "/mobile_base/debug/raw_data_command",
    "/velocity_smoother/input",
    "/nav_vel",
    "/joy",
    "/joystick",
    "/teleop/cmd_vel",
    "/robot_pose",
    "/robot_status",
    "/navi_status",
]

async def main():
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecté\n")

        # S'abonner à tous les topics
        for topic in TOPICS:
            await ws.send(json.dumps({
                "op": "subscribe",
                "topic": topic,
                "throttle_rate": 100  # 100ms = très réactif
            }))

        # S'abonner aussi au wildcard MQTT via rosbridge
        await ws.send(json.dumps({
            "op": "subscribe",
            "topic": "/mobile_base/commands/velocity",
            "throttle_rate": 100
        }))

        print("="*60)
        print("BOUGE LE JOYSTICK SUR L'ECRAN DU ROBOT MAINTENANT !")
        print("="*60 + "\n")

        # Garder en mémoire les dernières valeurs pour détecter les changements
        last_values = {}

        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                data = json.loads(msg)
                topic = data.get("topic", "?")
                payload = data.get("msg", {})
                payload_str = json.dumps(payload)

                # Afficher seulement si la valeur a changé
                if last_values.get(topic) != payload_str:
                    last_values[topic] = payload_str
                    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    print(f"\n[{ts}] CHANGEMENT sur {topic}")
                    print(json.dumps(payload, indent=2)[:400])
                    print("-"*50)

            except asyncio.TimeoutError:
                print("[Timeout 30s]")
                break

asyncio.run(main())