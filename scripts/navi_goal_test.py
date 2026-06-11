import asyncio
import websockets
import json

ROSBRIDGE = "ws://10.42.0.1:9090"

async def publish(ws, topic, msg):
    await ws.send(json.dumps({
        "op": "publish",
        "topic": topic,
        "msg": msg
    }))

async def main():
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecté\n")

        # Lire la pose actuelle
        await ws.send(json.dumps({
            "op": "subscribe",
            "topic": "/robot_pose",
            "throttle_rate": 500
        }))
        await ws.send(json.dumps({
            "op": "subscribe",
            "topic": "/navi_status",
            "throttle_rate": 500
        }))
        await ws.send(json.dumps({
            "op": "subscribe",
            "topic": "/robot_status",
            "throttle_rate": 1000
        }))

        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        pose = json.loads(msg).get("msg", {})
        print(f"[POSE ACTUELLE] x={pose.get('x')} y={pose.get('y')} theta={pose.get('theta')}\n")

        # Méthode 1 — PoseStamped via /navi_goal
        print("=== TEST 1 : /navi_goal (PoseStamped) ===")
        target_x = pose.get('x', 0) + 0.5  # 50cm devant
        target_y = pose.get('y', 0)
        target_theta = pose.get('theta', 0)

        import math
        qz = math.sin(target_theta / 2)
        qw = math.cos(target_theta / 2)

        await publish(ws, "/navi_goal", {
            "header": {
                "frame_id": "map",
                "stamp": {"secs": 0, "nsecs": 0}
            },
            "pose": {
                "position": {"x": target_x, "y": target_y, "z": 0.0},
                "orientation": {"x": 0.0, "y": 0.0, "z": qz, "w": qw}
            }
        })
        print(f"[ENVOYÉ] Naviguer vers x={target_x:.2f} y={target_y:.2f}")

        # Surveiller le statut pendant 15 secondes
        print("\n[SURVEILLANCE 15 secondes]\n")
        for _ in range(30):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(msg)
                topic = data.get("topic")
                payload = data.get("msg", {})

                if topic == "/robot_pose":
                    print(f"[POSE] x={payload.get('x'):.3f} "
                          f"y={payload.get('y'):.3f} "
                          f"theta={payload.get('theta'):.3f}")
                elif topic == "/navi_status":
                    print(f"[NAVI_STATUS] {payload}")
                elif topic == "/robot_status":
                    ns = payload.get('nav_status')
                    v = payload.get('velocity', [])
                    print(f"[STATUS] nav_status={ns} velocity={v}")
            except asyncio.TimeoutError:
                pass

        # Méthode 2 — navigation_mode string
        print("\n=== TEST 2 : /navigation_mode ===")
        for mode in ["manual", "teleop", "joystick", "0", "1", "stop"]:
            await publish(ws, "/navigation_mode", {"data": mode})
            print(f"[ENVOYÉ] navigation_mode = {mode}")
            await asyncio.sleep(0.5)
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(msg)
                if data.get("topic") == "/robot_status":
                    cs = data["msg"].get("control_state")
                    nm = data["msg"].get("nav_mode")
                    print(f"  → control_state={cs} nav_mode={nm}")
            except asyncio.TimeoutError:
                pass

asyncio.run(main())