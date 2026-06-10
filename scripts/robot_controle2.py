import asyncio
import websockets
import json

ROSBRIDGE = "ws://10.42.0.1:9090"

# Topics alternatifs de commande a tester
CMD_TOPICS = [
    "/cmd_vel",
    "/mobile_base/commands/velocity",
    "/mobile_base/debug/raw_data_command",
    "/velocity_smoother/input",
    "/nav_vel",
    "/teleop_velocity_smoother/output",
]

async def main():
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecte\n")

        # S'abonner a tous pour voir lequel reagit
        for topic in CMD_TOPICS:
            await ws.send(json.dumps({
                "op": "subscribe",
                "topic": topic,
                "throttle_rate": 500
            }))

        # Publier sur chaque topic
        for topic in CMD_TOPICS:
            print(f"\n[TEST] Publication sur {topic}")
            await ws.send(json.dumps({
                "op": "publish",
                "topic": topic,
                "msg": {
                    "linear":  {"x": 0.1, "y": 0.0, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0}
                }
            }))
            await asyncio.sleep(0.5)

            # Stop
            await ws.send(json.dumps({
                "op": "publish",
                "topic": topic,
                "msg": {
                    "linear":  {"x": 0.0, "y": 0.0, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0}
                }
            }))

        print("\n[ECOUTE - observe si un topic reagit]\n")
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(msg)
                topic = data.get("topic", "?")
                print(f"[{topic}] {str(data.get('msg',''))[:200]}")
        except asyncio.TimeoutError:
            print("[Timeout]")

asyncio.run(main())