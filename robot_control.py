import asyncio
import websockets
import json

ROSBRIDGE = "ws://10.42.0.1:9090"

async def send_command(ws, linear_x=0.0, angular_z=0.0):
    """Envoyer une commande de vitesse au robot"""
    cmd = {
        "op": "publish",
        "topic": "/cmd_vel",
        "msg": {
            "linear":  {"x": linear_x, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0,      "y": 0.0, "z": angular_z}
        }
    }
    await ws.send(json.dumps(cmd))
    print(f"[CMD] linear_x={linear_x:.2f}  angular_z={angular_z:.2f}")

async def get_pose(ws):
    """Lire la position actuelle"""
    await ws.send(json.dumps({
        "op": "subscribe",
        "topic": "/robot_pose",
        "throttle_rate": 500
    }))

async def main():
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecte\n")

        # Lire la position
        await get_pose(ws)
        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(msg)
        print(f"[POSE INITIALE] {data.get('msg', {})}\n")

        # ⚠️  DEPLACER LE ROBOT EN AVANT (0.1 m/s, 1 seconde)
        # Assure-toi que la voie est libre devant le robot !
        input("Appuie sur ENTER pour avancer le robot (0.1m/s, 1 sec)...")

        # Avancer
        for _ in range(10):  # 10 x 100ms = 1 seconde
            await send_command(ws, linear_x=0.1, angular_z=0.0)
            await asyncio.sleep(0.1)

        # STOP
        await send_command(ws, linear_x=0.0, angular_z=0.0)
        print("\n[STOP]")

        # Lire la nouvelle position
        await asyncio.sleep(0.5)
        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(msg)
        print(f"[POSE FINALE] {data.get('msg', {})}")

asyncio.run(main())