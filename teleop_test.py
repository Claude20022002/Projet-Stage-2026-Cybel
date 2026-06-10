import asyncio
import websockets
import json

ROSBRIDGE = "ws://10.42.0.1:9090"

async def call_service(ws, service, args={}):
    msg = {
        "op": "call_service",
        "service": service,
        "args": args
    }
    await ws.send(json.dumps(msg))
    print(f"[SERVICE] {service} appelé avec {args}")

async def publish(ws, topic, msg):
    await ws.send(json.dumps({
        "op": "publish",
        "topic": topic,
        "msg": msg
    }))

async def main():
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecté\n")

        # Ecouter les réponses
        await ws.send(json.dumps({
            "op": "subscribe",
            "topic": "/robot_status",
            "throttle_rate": 1000
        }))

        print("=== ETAPE 1 : Changer le mode de contrôle ===")
        # Essayer de passer en mode manuel/téléop
        await call_service(ws, "/change_location_mode", {"mode": 0})
        await asyncio.sleep(1.0)

        # Lire la réponse
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
            print(f"Réponse: {json.loads(msg)}")
        except asyncio.TimeoutError:
            pass

        print("\n=== ETAPE 2 : Publier sur mobile_base directement ===")
        # Topic de commande directe bas niveau
        await publish(ws, "/mobile_base/commands/velocity", {
            "linear": 0.1,
            "angular": 0.0
        })
        await asyncio.sleep(1.0)

        # STOP
        await publish(ws, "/mobile_base/commands/velocity", {
            "linear": 0.0,
            "angular": 0.0
        })
        print("[STOP]")

        print("\n=== ETAPE 3 : Lire le nouveau control_state ===")
        for _ in range(3):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(msg)
                if data.get("topic") == "/robot_status":
                    status = data.get("msg", {})
                    print(f"control_state: {status.get('control_state')}")
                    print(f"nav_status:    {status.get('nav_status')}")
                    print(f"velocity:      {status.get('velocity')}")
            except asyncio.TimeoutError:
                break

asyncio.run(main())