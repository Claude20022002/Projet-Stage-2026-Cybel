import asyncio
import websockets
import json

async def listen():
    uri = "ws://10.42.0.1:9090"
    print(f"Connexion rosbridge sur {uri} ...")

    async with websockets.connect(uri) as ws:
        print("[OK] Connecte !\n")

        # 1. Lister tous les topics ROS
        await ws.send(json.dumps({
            "op": "call_service",
            "service": "/rosapi/topics"
        }))
        print("[>>] Demande de la liste des topics...")

        # 2. Lister tous les services ROS
        await ws.send(json.dumps({
            "op": "call_service",
            "service": "/rosapi/services"
        }))
        print("[>>] Demande de la liste des services...")

        # 3. Ecouter les reponses pendant 10 secondes
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(msg)
                print(f"\n[REPONSE]")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
                print("-" * 60)
        except asyncio.TimeoutError:
            print("\n[Timeout - pas de nouveaux messages]")

asyncio.run(listen())