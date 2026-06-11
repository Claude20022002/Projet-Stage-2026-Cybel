import asyncio
import websockets
import json

async def main():
    async with websockets.connect("ws://10.42.0.1:9090") as ws:

        # Services du node_manager
        await ws.send(json.dumps({
            "op": "call_service",
            "service": "/rosapi/node_details",
            "args": {"node": "/node_manager"}
        }))
        try:
            resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
            print("NODE_MANAGER DETAILS:")
            print(json.dumps(json.loads(resp), indent=2)[:1000])
        except asyncio.TimeoutError:
            print("timeout")

        # Services du mqttclient
        await ws.send(json.dumps({
            "op": "call_service",
            "service": "/rosapi/node_details",
            "args": {"node": "/mqttclient"}
        }))
        try:
            resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
            print("\nMQTTCLIENT DETAILS:")
            print(json.dumps(json.loads(resp), indent=2)[:1000])
        except asyncio.TimeoutError:
            print("timeout")

asyncio.run(main())