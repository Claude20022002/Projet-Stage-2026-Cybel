import asyncio
import websockets
import json

ROSBRIDGE = "ws://10.42.0.1:9090"

# Topics essentiels identifies dans la liste ROS
TOPICS = [
    "/navi_status",
    "/waypoints", 
    "/map_metadata",
    "/set_init_pose",
    "/detected_people_array",
    "/mobile_base/sensors/imu_data_raw",
    "/lift_control/deployment",
    "/get_current_map",
    "/scan_filter",
    "/path_follower/cancel",
]

async def main():
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecte a rosbridge ROS\n")

        # S'abonner a tous les topics
        for topic in TOPICS:
            await ws.send(json.dumps({
                "op": "subscribe",
                "topic": topic,
                "throttle_rate": 2000
            }))
            print(f"[SUB] {topic}")

        print("\n" + "="*60)
        print("ECOUTE EN COURS - effectue des actions sur l'interface web")
        print("="*60 + "\n")

        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=60.0)
                data = json.loads(msg)
                topic = data.get("topic", "?")
                payload = data.get("msg", data)
                print(f"\n>>> TOPIC: {topic}")
                print(json.dumps(payload, indent=2, ensure_ascii=False)[:600])
                print("-"*50)
        except asyncio.TimeoutError:
            print("[Timeout 60s - pas de messages]")

asyncio.run(main())