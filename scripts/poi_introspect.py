import asyncio
import websockets
import json

async def call(ws, service, args={}):
    await ws.send(json.dumps({
        "op": "call_service",
        "service": service,
        "args": args
    }))
    try:
        resp = await asyncio.wait_for(ws.recv(), timeout=4.0)
        data = json.loads(resp)
        print(f"\n[{service}]")
        print(json.dumps(data, indent=2)[:800])
        return data
    except asyncio.TimeoutError:
        print(f"[{service}] timeout")
        return {}

async def main():
    async with websockets.connect("ws://10.42.0.1:9090") as ws:
        print("[OK] Connecté\n")

        # Introspection des types de services /poi
        poi_services = [
            "/poi", "/poi_cross_floor", "/poi_id",
            "/poi_init", "/poi_patrol",
            "/change_location_mode", "/node_manager_control",
            "/start_recharge", "/record_miles"
        ]

        for svc in poi_services:
            await call(ws, "/rosapi/service_type", {"service": svc})

        # Obtenir les détails des types de messages
        print("\n\n=== DETAILS DES TYPES ===\n")
        types_to_inspect = [
            "yutong_assistance/poiRequest",
            "yutong_assistance/poiResponse",
            "yutong_assistance/cmdRequest",
            "yutong_assistance/cmdResponse",
        ]

        for t in types_to_inspect:
            await call(ws, "/rosapi/message_details", {"type": t})

        # Topics du node_manager non encore explorés
        print("\n\n=== TOPICS NODE_MANAGER ===\n")
        important_topics = [
            "/navigation_mode",
            "/navi_goal",
            "/navi_goal_id",
            "/cancel_operation",
            "/mqtt_status",
            "/robot_list",
        ]
        for topic in important_topics:
            await call(ws, "/rosapi/topic_type", {"topic": topic})

        # S'abonner aux topics publiés par mqttclient
        print("\n\n=== MQTT STATUS ===\n")
        await ws.send(json.dumps({
            "op": "subscribe",
            "topic": "/mqtt_status",
            "throttle_rate": 1000
        }))
        await ws.send(json.dumps({
            "op": "subscribe",
            "topic": "/robot_list",
            "throttle_rate": 1000
        }))

        for _ in range(5):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(msg)
                print(f"[{data.get('topic')}] {json.dumps(data.get('msg',{}))[:300]}")
            except asyncio.TimeoutError:
                break

asyncio.run(main())