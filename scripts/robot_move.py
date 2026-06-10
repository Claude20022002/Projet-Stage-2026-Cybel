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

async def move(ws, linear_x=0.0, angular_z=0.0):
    await publish(ws, "/mobile_base/commands/velocity", {
        "linear":  {"x": linear_x, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0,      "y": 0.0, "z": angular_z}
    })

async def get_pose(ws):
    await ws.send(json.dumps({
        "op": "subscribe",
        "topic": "/robot_pose",
        "throttle_rate": 200
    }))
    msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
    return json.loads(msg).get("msg", {})

async def main():
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecté\n")

        pose = await get_pose(ws)
        print(f"[POSE INITIALE] x={pose.get('x'):.3f}  "
              f"y={pose.get('y'):.3f}  theta={pose.get('theta'):.3f}\n")

        # ── AVANCER ──────────────────────────────────────────
        input("ENTER → avancer 1 seconde (0.15 m/s)...")
        print("Avance...")
        for _ in range(15):
            await move(ws, linear_x=0.15, angular_z=0.0)
            await asyncio.sleep(0.1)
        await move(ws, 0.0, 0.0)
        print("[STOP]\n")

        await asyncio.sleep(0.5)
        pose = await get_pose(ws)
        print(f"[POSE APRES AVANCE] x={pose.get('x'):.3f}  "
              f"y={pose.get('y'):.3f}  theta={pose.get('theta'):.3f}\n")

        # ── TOURNER À GAUCHE ──────────────────────────────────
        input("ENTER → tourner gauche 1 seconde...")
        print("Rotation gauche...")
        for _ in range(15):
            await move(ws, linear_x=0.0, angular_z=0.5)
            await asyncio.sleep(0.1)
        await move(ws, 0.0, 0.0)
        print("[STOP]\n")

        await asyncio.sleep(0.5)
        pose = await get_pose(ws)
        print(f"[POSE APRES ROTATION] x={pose.get('x'):.3f}  "
              f"y={pose.get('y'):.3f}  theta={pose.get('theta'):.3f}\n")

        # ── RECULER ───────────────────────────────────────────
        input("ENTER → reculer 1 seconde...")
        print("Recule...")
        for _ in range(15):
            await move(ws, linear_x=-0.15, angular_z=0.0)
            await asyncio.sleep(0.1)
        await move(ws, 0.0, 0.0)
        print("[STOP]\n")

        await asyncio.sleep(0.5)
        pose = await get_pose(ws)
        print(f"[POSE FINALE] x={pose.get('x'):.3f}  "
              f"y={pose.get('y'):.3f}  theta={pose.get('theta'):.3f}")

asyncio.run(main())