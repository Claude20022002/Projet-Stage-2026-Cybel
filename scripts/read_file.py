import asyncio
import websockets
import json
import requests

# Ports roslaunch découverts
ROSLAUNCH_PORTS = [45489, 32979, 35897, 43215, 44839, 46421, 38641, 38383, 33429, 41967, 42551, 34905]

# Tentative d'accès direct aux URIs ROS Master API (XMLRPC)
for port in ROSLAUNCH_PORTS:
    try:
        r = requests.get(f"http://10.42.0.1:{port}/", timeout=2)
        print(f"[{port}] {r.status_code} → {r.text[:200]}")
    except Exception as e:
        print(f"[{port}] {e}")