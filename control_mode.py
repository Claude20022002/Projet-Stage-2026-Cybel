import asyncio
import websockets
import json

ROSBRIDGE = "ws://10.42.0.1:9090"

async def call_service(ws, service, args={}):
    await ws.send(json.dumps({
        "op": "call_service",
        "service": service,
        "args": args
    }))
    print(f"[SERVICE] {service}  args={args}")
    try:
        resp = await asyncio.wait_for(ws.recv(), timeout=3.0)
        print(f"[REPONSE] {resp[:300]}")
        return json.loads(resp)
    except asyncio.TimeoutError:
        print("[REPONSE] timeout")
        return {}

async def publish(ws, topic, msg):
    await ws.send(json.dumps({
        "op": "publish",
        "topic": topic,
        "msg": msg
    }))

async def move(ws, linear_x=0.0, angular_z=0.0):
    await publish(ws, "/mobile_base/commands/velocity", {
        "linear":  {"x": linear_x, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0,      "y": 0.0, "z": angular_z}
    })

async def main():
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecté\n")

        # S'abonner au robot_status pour surveiller control_state
        await ws.send(json.dumps({
            "op": "subscribe",
            "topic": "/robot_status",
            "throttle_rate": 500
        }))

        # ── Essayer tous les modes de contrôle connus ──────────
        print("=== TEST des modes de contrôle ===\n")

        # Mode 0 = manuel ?
        await call_service(ws, "/change_location_mode", {"mode": 0})
        await asyncio.sleep(0.5)

        # Lire le control_state après changement
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
            data = json.loads(msg)
            if data.get("topic") == "/robot_status":
                cs = data["msg"].get("control_state")
                print(f"control_state après mode 0 : {cs}\n")
        except asyncio.TimeoutError:
            pass

        # Essayer le topic set_navi_status pour stopper la navigation
        print("=== TEST stop navigation ===\n")
        await publish(ws, "/path_follower/cancel", {})
        await asyncio.sleep(0.3)

        # Essayer de publier sur set_init_pose pour forcer un état
        await publish(ws, "/set_init_pose", {
            "x": -3.040, "y": 0.200, "theta": -0.760
        })
        await asyncio.sleep(0.3)

        # Tester le service /poi avec mode stop
        await call_service(ws, "/poi", {"command": "stop"})
        await asyncio.sleep(0.3)

        # Essayer le service marker_manager
        await call_service(ws, "/marker_manager/control",
                          {"command": "stop"})
        await asyncio.sleep(0.5)

        # ── Maintenant tenter le mouvement ────────────────────
        print("\n=== TEST mouvement après reset ===\n")
        print("Envoi commande avance...")
        for _ in range(20):
            await move(ws, linear_x=0.15, angular_z=0.0)
            await asyncio.sleep(0.1)
        await move(ws, 0.0, 0.0)

        # Lire la pose
        await ws.send(json.dumps({
            "op": "subscribe",
            "topic": "/robot_pose",
            "throttle_rate": 200
        }))
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(msg)
                if data.get("topic") == "/robot_pose":
                    print(f"[POSE] {data['msg']}")
                    break
                elif data.get("topic") == "/robot_status":
                    cs = data["msg"].get("control_state")
                    nm = data["msg"].get("nav_mode")
                    print(f"[STATUS] control_state={cs}  nav_mode={nm}")
        except asyncio.TimeoutError:
            print("[Timeout]")

asyncio.run(main())