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
        resp = await asyncio.wait_for(ws.recv(), timeout=4.0)
        data = json.loads(resp)
        print(f"\n[{service}]")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:600])
        return data
    except asyncio.TimeoutError:
        print(f"[{service}] timeout")
        return {}

async def main():
    async with websockets.connect(ROSBRIDGE) as ws:
        print("[OK] Connecté\n")

        # Introspection rosapi — obtenir les champs exacts des types
        services_to_inspect = [
            ("/rosapi/service_type",
             {"service": "/change_location_mode"}),
            ("/rosapi/service_type",
             {"service": "/poi"}),
            ("/rosapi/service_type",
             {"service": "/marker_manager/control"}),
            ("/rosapi/service_type",
             {"service": "/set_robot_id"}),
            ("/rosapi/message_details",
             {"type": "yutong_assistance/cmdRequest"}),
            ("/rosapi/message_details",
             {"type": "yutong_assistance/poiRequest"}),
            # Lister tous les services disponibles
            ("/rosapi/service_providers",
             {"service": "/change_location_mode"}),
        ]

        for service, args in services_to_inspect:
            await call(ws, service, args)
            await asyncio.sleep(0.3)

        # Introspection des topics de commande
        print("\n\n=== TYPES DES TOPICS DE COMMANDE ===\n")
        topics_to_inspect = [
            "/mobile_base/commands/velocity",
            "/navi_status",
            "/waypoints",
            "/set_init_pose",
        ]
        for topic in topics_to_inspect:
            await call(ws, "/rosapi/topic_type", {"topic": topic})
            await asyncio.sleep(0.2)

asyncio.run(main())