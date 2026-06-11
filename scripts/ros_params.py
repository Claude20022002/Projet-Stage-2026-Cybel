import asyncio
import websockets
import json

async def main():
    async with websockets.connect("ws://10.42.0.1:9090") as ws:

        # 1. Récupérer TOUS les noms de paramètres
        await ws.send(json.dumps({
            "op": "call_service",
            "service": "/rosapi/get_param_names",
            "args": {}
        }))
        resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(resp)
        all_params = data["values"]["names"]
        print(f"Total paramètres : {len(all_params)}\n")

        # 2. Filtrer les paramètres intéressants
        keywords = [
            "password", "passwd", "ssh", "user", "login",
            "secret", "key", "auth", "credential",
            "ip", "host", "network", "wifi",
            "robot_id", "serial", "device",
            "node_manager", "mqtt", "server"
        ]

        interesting = []
        for p in all_params:
            for kw in keywords:
                if kw.lower() in p.lower():
                    interesting.append(p)
                    break

        print(f"Paramètres potentiellement intéressants ({len(interesting)}) :")
        for p in interesting:
            print(f"  {p}")

        # 3. Lire chaque paramètre intéressant
        print("\n=== VALEURS ===\n")
        for param in interesting:
            await ws.send(json.dumps({
                "op": "call_service",
                "service": "/rosapi/get_param",
                "args": {"name": param}
            }))
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=3.0)
                val = json.loads(resp)
                value = val.get("values", {}).get("value", "N/A")
                if value not in ["null", "N/A", ""]:
                    print(f"{param}")
                    print(f"  → {value[:200]}\n")
            except asyncio.TimeoutError:
                pass

        # 4. Lire les paramètres node_manager (gestionnaire principal)
        print("\n=== NODE_MANAGER PARAMS ===\n")
        node_params = [p for p in all_params if "node_manager" in p.lower()
                      or "mqttclient" in p.lower()
                      or "robot_id" in p.lower()]

        for param in node_params[:30]:
            await ws.send(json.dumps({
                "op": "call_service",
                "service": "/rosapi/get_param",
                "args": {"name": param}
            }))
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=2.0)
                val = json.loads(resp)
                value = val.get("values", {}).get("value", "")
                print(f"{param} → {str(value)[:150]}")
            except asyncio.TimeoutError:
                pass

asyncio.run(main())