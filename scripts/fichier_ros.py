import asyncio
import websockets
import json

async def main():
    async with websockets.connect("ws://10.42.0.1:9090") as ws:

        # Chercher des services qui exposent des infos système
        services_to_try = [
            ("/rosapi/get_param", {"name": "/robot_description"}),
            ("/rosapi/get_param", {"name": "/robot_id"}),
            ("/rosapi/get_param_names", {}),
            ("/rosapi/nodes", {}),
        ]

        for service, args in services_to_try:
            await ws.send(json.dumps({
                "op": "call_service",
                "service": service,
                "args": args
            }))
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(resp)
                print(f"\n[{service}]")
                print(json.dumps(data, indent=2)[:800])
            except asyncio.TimeoutError:
                print(f"[{service}] timeout")

asyncio.run(main())