"""Scan des endpoints REST de l'interface usine (:8082)."""
import json

import requests

BASE = "http://10.42.0.1:8082"

ENDPOINTS = [
    "/api/status",
    "/api/robot/status",
    "/api/map/list",
    "/api/point/list",
    "/status",
    "/health",
]

print(f"Scan des endpoints sur {BASE}\n" + "=" * 50)

for endpoint in ENDPOINTS:
    try:
        r = requests.get(f"{BASE}{endpoint}", timeout=3)
        if r.status_code != 404:
            print(f"\n[{r.status_code}] {endpoint}")
            try:
                print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:300])
            except Exception:
                print(r.text[:200])
    except requests.exceptions.ConnectionError:
        pass

print("\n" + "=" * 50)
print("Scan termine")
