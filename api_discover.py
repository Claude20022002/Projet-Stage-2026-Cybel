import requests
import json

BASE = "http://10.42.0.1:8082"

# Endpoints REST typiques des interfaces robot web
endpoints = [
    "/api/status",
    "/api/robot/status", 
    "/api/map/list",
    "/api/point/list",
    "/api/navigation/status",
    "/api/chassis/status",
    "/status",
    "/robot/status",
    "/map",
    "/points",
    "/navigate",
    "/health",
    "/info",
    "/api/v1/status",
    "/api/v1/robot",
    "/api/v1/map",
    "/api/v1/navigate",
]

print(f"Scan des endpoints sur {BASE}\n" + "="*50)

for endpoint in endpoints:
    try:
        r = requests.get(f"{BASE}{endpoint}", timeout=3)
        if r.status_code != 404:
            print(f"\n[{r.status_code}] {endpoint}")
            try:
                data = r.json()
                print(json.dumps(data, indent=2, ensure_ascii=False)[:300])
            except:
                print(r.text[:200])
    except requests.exceptions.ConnectionError:
        pass
    except Exception as e:
        print(f"[ERR] {endpoint}: {e}")

print("\n" + "="*50)
print("Scan termine")