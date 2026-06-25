#!/usr/bin/env python3
"""Diagnostic carte / POI robot vs CYBEL."""
import asyncio
import json
import math
import sys
from pathlib import Path

import websockets

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.20.22"
ROOT = Path(__file__).resolve().parent.parent


async def call_service(ws, service: str, args: dict | None = None) -> dict:
    await ws.send(json.dumps({"op": "call_service", "service": service, "args": args or {}}))
    while True:
        data = json.loads(await asyncio.wait_for(ws.recv(), 15))
        if data.get("op") == "service_response" and data.get("service") == service:
            return data.get("values") or {}


def yaw_from_pose(pose: dict) -> float:
    o = pose.get("orientation") or {}
    z, w = float(o.get("z") or 0), float(o.get("w") or 1)
    return math.atan2(2 * w * z, 1 - 2 * z * z)


async def main() -> None:
    uri = f"ws://{HOST}:9090"
    async with websockets.connect(uri, open_timeout=8) as ws:
        sm = await call_service(ws, "/static_map")
        grid = (sm or {}).get("map") or {}
        info = grid.get("info") or {}
        origin = (info.get("origin") or {}).get("position") or {}
        print(
            f"Carte SLAM: {info.get('width')}x{info.get('height')} "
            f"res={info.get('resolution')} origin=({origin.get('x')},{origin.get('y')})"
        )

        await ws.send(json.dumps({"op": "subscribe", "topic": "/robot_pose", "throttle_rate": 200}))
        pose = {}
        for _ in range(30):
            msg = json.loads(await asyncio.wait_for(ws.recv(), 2))
            if msg.get("topic") == "/robot_pose":
                pose = msg.get("msg") or {}
                break
        print(f"Pose robot: x={pose.get('x')} y={pose.get('y')} theta={pose.get('theta')}")

        details = await call_service(ws, "/marker_manager/get_markers_details")
        floors = details.get("floors") or []
        ros_markers: list[dict] = []
        for floor in floors:
            for m in floor.get("markers") or []:
                pos = (m.get("pose") or {}).get("position") or {}
                ros_markers.append(
                    {
                        "name": m.get("name"),
                        "x": round(float(pos.get("x") or 0), 2),
                        "y": round(float(pos.get("y") or 0), 2),
                        "theta": round(yaw_from_pose(m.get("pose") or {}), 2),
                    }
                )
        print(f"\nMarqueurs ROS ({len(ros_markers)}):")
        for m in ros_markers:
            print(f"  - {m['name']}: ({m['x']}, {m['y']})")

        poi = await call_service(ws, "/poi", {})
        print(f"\n/poi disponibles: {poi.get('avaliable_list') or poi.get('available_list')}")

        cybel_pts = json.loads((ROOT / "data" / "points.json").read_text(encoding="utf-8"))["points"]
        print(f"\nPOI CYBEL points.json ({len(cybel_pts)}):")
        px, py = float(pose.get("x") or 0), float(pose.get("y") or 0)
        for p in cybel_pts:
            dist = math.hypot(float(p["x"]) - px, float(p["y"]) - py)
            match = next(
                (m for m in ros_markers if m["name"].lower() == p["name"].lower()),
                None,
            )
            flag = ""
            if match:
                dd = math.hypot(match["x"] - float(p["x"]), match["y"] - float(p["y"]))
                flag = f" ROS même nom à {dd:.1f}m" if dd > 0.3 else " ≈ ROS"
            elif dist < 0.5:
                flag = " proche du robot"
            print(f"  - {p['name']}: ({p['x']}, {p['y']}) dist_robot={dist:.2f}m{flag}")

        names_cybel = {p["name"] for p in cybel_pts}
        names_ros = {m["name"] for m in ros_markers}
        missing_on_robot = sorted(names_cybel - names_ros)
        if missing_on_robot:
            print("\nNoms CYBEL absents du robot ROS:")
            for n in missing_on_robot:
                print(f"  - {n}")


if __name__ == "__main__":
    asyncio.run(main())
