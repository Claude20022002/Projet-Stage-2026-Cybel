import asyncio
import websockets
import json

async def main():
    async with websockets.connect("ws://10.42.0.1:9090") as ws:
        await ws.send(json.dumps({
            "op": "subscribe",
            "topic": "/robot_status",
            "throttle_rate": 1000
        }))
        await ws.send(json.dumps({
            "op": "subscribe", 
            "topic": "/navi_status",
            "throttle_rate": 1000
        }))
        print("[ECOUTE robot_status et navi_status]\n")
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
            data = json.loads(msg)
            print(f"\n[{data.get('topic')}]")
            print(json.dumps(data.get('msg', {}), indent=2)[:400])

asyncio.run(main())