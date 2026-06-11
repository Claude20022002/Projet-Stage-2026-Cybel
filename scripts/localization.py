import asyncio
import websockets
import json

ROSBRIDGE = "ws://10.42.0.1:9090"

async def call(ws, service, args={}):
    await ws.send(json.dumps({
        "op": "call_service",
        "service": service,
        "args": args
    }))
    try:
        resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(resp)
        print(f"[{service}] {json.dumps(data)[:300]}")
        return data
    except asyncio.TimeoutError:
        print(f"[{service}] timeout")
        return {}

async def publish(ws, topic, msg):
    await ws.send(json.dumps({
        "op": "publish",
        "topic": topic,
        "msg": msg
    }))

async def main():
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecté\n")

        # Souscrire au statut
        for topic in ["/robot_status", "/robot_pose", "/navi_status"]:
            await ws.send(json.dumps({
                "op": "subscribe",
                "topic": topic,
                "throttle_rate": 1000
            }))

        # 1. Lancer la localisation globale AMCL
        print("=== LOCALISATION GLOBALE ===")
        await call(ws, "/global_localization", {})
        await asyncio.sleep(2.0)

        # 2. Lire le matching degree après localisation
        print("\n=== MATCHING DEGREE (30 sec) ===")
        best_matching = 0
        for i in range(30):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(msg)
                if data.get("topic") == "/robot_status":
                    payload = data["msg"]
                    # Chercher le champ matching degree
                    print(json.dumps(payload, indent=2))
                    break
            except asyncio.TimeoutError:
                pass

        # 3. Essayer /poi_init pour initialiser la position
        print("\n=== POI_INIT ===")
        # Essayer différents formats
        for args in [
            {},
            {"data": ""},
            {"name": ""},
            {"id": 0},
            {"pose": {"x": 0.0, "y": 0.0, "theta": 0.0}}
        ]:
            result = await call(ws, "/poi_init", args)
            if result.get("result"):
                print(f"[OK] poi_init réussi avec args={args}")
                break
            await asyncio.sleep(0.3)

        # 4. Essayer /node_manager_control
        print("\n=== NODE_MANAGER_CONTROL ===")
        for args in [
            {"command": "teleop"},
            {"command": "manual"},
            {"command": "stop_navi"},
            {"data": "teleop"},
            {"mode": 1},
        ]:
            result = await call(ws, "/node_manager_control", args)
            if result.get("result"):
                print(f"[OK] node_manager_control réussi : {args}")
                break
            await asyncio.sleep(0.3)

asyncio.run(main())