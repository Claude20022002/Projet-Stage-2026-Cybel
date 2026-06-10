import asyncio
import websockets
import json

ROSBRIDGE = "ws://10.42.0.1:9090"

async def explore():
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecte a rosbridge\n")

        # --- Abonnement aux topics essentiels ---
        subscriptions = [
            {"topic": "/navi_status",          "type": "std_msgs/String"},
            {"topic": "/mobile_base/sensors/imu_data_raw", "type": "sensor_msgs/Imu"},
            {"topic": "/waypoints",             "type": "std_msgs/String"},
            {"topic": "/map_metadata",          "type": "nav_msgs/MapMetaData"},
            {"topic": "/detected_people_array", "type": "std_msgs/String"},
        ]

        for sub in subscriptions:
            await ws.send(json.dumps({
                "op": "subscribe",
                "topic": sub["topic"],
                "throttle_rate": 1000  # max 1 message/sec
            }))
            print(f"[SUB] {sub['topic']}")

        print("\n[ECOUTE EN COURS...]\n" + "="*60)

        # Ecouter pendant 30 secondes
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                data = json.loads(msg)
                topic = data.get("topic", "inconnu")
                msg_data = data.get("msg", {})
                print(f"\n[{topic}]")
                print(json.dumps(msg_data, indent=2, ensure_ascii=False)[:500])
                print("-" * 60)
        except asyncio.TimeoutError:
            print("\n[Timeout]")

asyncio.run(explore())