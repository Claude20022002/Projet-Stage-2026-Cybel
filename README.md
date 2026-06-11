# Projet-Stage-2026-Cybel

# CYBEL - Plateforme de Commande Robot CIOT TY1251D

## Vue d'ensemble

Plateforme de commande complète pour le robot de réception mobile CIOT (modèle TY1251D-03195),
basée sur le protocole rosbridge WebSocket et MQTT. Cette plateforme permet le contrôle en temps
réel, la navigation autonome et le monitoring du robot via une interface web.

---

## Architecture de communication (découverte par reverse engineering)

```
┌─────────────────────────────────────────────────────────────┐
│                    PLATEFORME CYBEL                         │
│                                                             │
│   SDK Python (robot_client.py)                             │
│   Interface Web (React + Vite)                             │
│   API Backend (FastAPI)                                    │
└──────────┬──────────────────────┬──────────────────────────┘
           │                      │
     WebSocket                  MQTT
     rosbridge                  paho
     :9090                      :1883
           │                      │
┌──────────▼──────────────────────▼──────────────────────────┐
│              CHÂSSIS CIOT - 10.42.0.1                      │
│              WiFi : TY1251D-03195                          │
│              Mot de passe : 123456789                      │
│                                                            │
│  OS : Linux embarqué (ROS Noetic/Melodic)                  │
│  Upper body : Android 7.1 (RK3399) - 172.16.0.88          │
├────────────────────────────────────────────────────────────┤
│  PORTS OUVERTS                                             │
│  :1883  MQTT broker                                        │
│  :8082  Interface web déploiement (Vue.js)                 │
│  :8088  Interface debug CSST (chinois)                     │
│  :9090  rosbridge WebSocket (ROS)                          │
│  :21    FTP                                                │
│  :22    SSH (verrouillé)                                   │
└────────────────────────────────────────────────────────────┘
```

---

## Protocole de communication

### 1. rosbridge WebSocket (principal)

**Endpoint** : `ws://10.42.0.1:9090`
**Protocole** : rosbridge v2.0 (JSON)

#### Topics SUBSCRIBE (lecture)

| Topic                                 | Type ROS              | Description                   | Fréquence |
| ------------------------------------- | --------------------- | ----------------------------- | --------- |
| `/robot_pose`                         | custom                | Position `{x, y, theta}`      | ~10 Hz    |
| `/robot_status`                       | custom                | État complet du robot         | ~2 Hz     |
| `/scan_filter`                        | sensor_msgs/LaserScan | Données LiDAR filtrées        | ~25 Hz    |
| `/mobile_base/sensors/imu_data_raw`   | sensor_msgs/Imu       | Données IMU                   | ~10 Hz    |
| `/navi_status`                        | std_msgs/String       | État navigation               | ~2 Hz     |
| `/map_metadata`                       | nav_msgs/MapMetaData  | Métadonnées carte             | on change |
| `/detected_people_array`              | custom                | Personnes détectées           | ~5 Hz     |
| `/waypoints`                          | custom                | Points de navigation          | on change |
| `/get_current_map`                    | custom                | Carte courante                | on change |
| `/mobile_base/debug/raw_data_command` | std_msgs/String       | Commandes binaires bas niveau | ~10 Hz    |

#### Topics PUBLISH (commandes)

| Topic                            | Type ROS            | Description                          | Format payload                                    |
| -------------------------------- | ------------------- | ------------------------------------ | ------------------------------------------------- |
| `/mobile_base/commands/velocity` | geometry_msgs/Twist | **COMMANDE DE MOUVEMENT PRINCIPALE** | `{linear: {x, y:0, z:0}, angular: {x:0, y:0, z}}` |
| `/set_init_pose`                 | custom              | Définir position initiale            | `{x, y, theta}`                                   |
| `/path_follower/cancel`          | custom              | Annuler navigation en cours          | `{}`                                              |

#### Services ROS (call_service)

| Service                               | Type                         | Description                 | Args connues                   |
| ------------------------------------- | ---------------------------- | --------------------------- | ------------------------------ |
| `/rosapi/topics`                      | rosapi                       | Lister tous les topics      | `{}`                           |
| `/rosapi/services`                    | rosapi                       | Lister tous les services    | `{}`                           |
| `/rosapi/message_details`             | rosapi                       | Détails d'un type           | `{type: "..."}`                |
| `/poi`                                | yutong_assistance/poiRequest | Navigation vers point nommé | À déterminer par introspection |
| `/global_localization`                | std_srvs/Empty               | Localisation globale        | `{}`                           |
| `/change_location_mode`               | yutong_assistance/cmdRequest | Changer mode contrôle       | À déterminer                   |
| `/marker_manager/control`             | custom                       | Contrôle marqueurs          | À déterminer                   |
| `/marker_manager/get_markers_details` | custom                       | Obtenir points enregistrés  | `{}`                           |
| `/move_base/NavfnROS/make_plan`       | nav_msgs                     | Planifier trajectoire       | `{start, goal}`                |
| `/calculate_distance`                 | custom                       | Calculer distance           | À déterminer                   |

#### Format des messages rosbridge

```json
// SUBSCRIBE
{"op": "subscribe", "topic": "/robot_pose", "throttle_rate": 200}

// UNSUBSCRIBE
{"op": "unsubscribe", "topic": "/robot_pose"}

// PUBLISH
{
  "op": "publish",
  "topic": "/mobile_base/commands/velocity",
  "msg": {
    "linear":  {"x": 0.15, "y": 0.0, "z": 0.0},
    "angular": {"x": 0.0,  "y": 0.0, "z": 0.0}
  }
}

// CALL SERVICE
{"op": "call_service", "service": "/rosapi/topics", "args": {}}
```

### 2. MQTT

**Broker** : `10.42.0.1:1883`
**Authentification** : aucune

| Topic      | Description     | Format                        |
| ---------- | --------------- | ----------------------------- |
| `test_mul` | Odométrie brute | `TY1251D-03195,X,Y,Z,vitesse` |

### 3. Structure du robot_status

```json
{
  "current_building_name": "robotics lab",
  "soft_estop": false,
  "hard_estop": false,
  "battery": 46,
  "charger": 0,
  "nav_status": 600,
  "velocity": [linear, angular],
  "patrol_status": 0,
  "nav_mode": "auto_navi",
  "current_floor_name": "0",
  "current_goal_coordinate": {"y": 0.0, "x": 0.0, "theta": 0.0},
  "nav_internal_status": 600,
  "control_state": 30
}
```

**Codes nav_status connus** :

- `600` : Initializing / non localisé
- À documenter : idle, navigating, arrived, error

**Codes control_state connus** :

- `30` : mode auto_navi (navigation autonome)
- À documenter : mode téléopération

---

## Spécifications hardware du robot

| Paramètre                     | Valeur                                  |
| ----------------------------- | --------------------------------------- |
| Modèle                        | CIOT Mobile Reception Robot             |
| Châssis                       | TY1251D-03195                           |
| OS Upper body                 | Android 7.1                             |
| CPU                           | RK3399                                  |
| RAM                           | 2 GB                                    |
| ROM                           | 16 GB                                   |
| Réseau                        | 4G / WiFi                               |
| Batterie                      | 24V, 20Ah                               |
| Autonomie                     | 8h                                      |
| Vitesse max                   | 0.8 m/s                                 |
| Vitesse défaut                | 0.5 m/s                                 |
| Précision positionnement      | ±5 cm                                   |
| Capteurs                      | LiDAR, RGBD, ultrason, gyroscope 6 axes |
| Écran                         | 15.6 pouces tactile, 1920×1080          |
| Caméra reconnaissance faciale | 2M pixels, 0.5–3m                       |
| Caméras surveillance          | 4× 4.2M pixels IR                       |

---

## Architecture de la plateforme à développer

### Stack technologique recommandée

#### Backend

```
Python 3.11+
FastAPI          → API REST + WebSocket relay
websockets       → connexion rosbridge
paho-mqtt        → connexion MQTT broker
uvicorn          → serveur ASGI
asyncio          → gestion concurrence
pydantic         → validation données
```

#### Frontend

```
React 18 + TypeScript
Vite             → bundler
Tailwind CSS     → styling
shadcn/ui        → composants UI
react-use-websocket → WebSocket hook
leaflet / pixi.js   → affichage carte robot
nipplejs         → joystick virtuel tactile
recharts         → graphiques temps réel
zustand          → state management
```

#### Infrastructure

```
Docker + docker-compose   → containerisation
nginx                     → reverse proxy
```

---

## Structure du projet

```
cybel/
├── README.md
├── .gitignore
├── docs/                         # Documentation constructeur
│
├── sdk/                          # Couche robot (réutilisable)
│   ├── __init__.py
│   ├── models.py                 # Modèles Pydantic partagés
│   ├── constants.py              # Topics ROS, services, codes
│   ├── rosbridge.py              # Client WebSocket rosbridge
│   ├── map_utils.py              # Parse cartes OccupancyGrid
│   ├── mock_map.py               # Carte simulée
│   ├── mock_robot.py             # Simulateur (hors robot)
│   └── real_robot.py             # Adaptateur robot réel
│
├── backend/                      # API REST + WebSocket
│   ├── main.py                   # Point d'entrée FastAPI
│   ├── config.py                 # Variables d'environnement
│   ├── requirements.txt
│   ├── routers/
│   │   ├── robot.py              # /api/robot/*
│   │   ├── navigation.py         # /api/navigation/*
│   │   ├── map.py                # /api/map/*
│   │   └── settings.py           # /api/settings
│   ├── services/
│   │   └── robot_service.py      # Façade mock / réel
│   └── websocket/
│       └── manager.py            # Broadcast télémétrie
│
├── frontend/                     # Interface opérateur (Vite + TS)
│   └── src/
│       ├── app.ts                # Routeur pages
│       ├── api.ts                # Client REST
│       ├── state.ts              # État global
│       ├── telemetry.ts          # WebSocket temps réel
│       ├── icons/                # Icônes SVG inline
│       ├── components/           # UI (layout, carte, contrôles…)
│       └── pages/
│           └── settings.ts       # Page paramètres
│
└── scripts/                      # Outils reverse-engineering
    ├── robot_move.py
    ├── robot_status.py
    ├── ros_explore.py
    ├── mqtt_listen.py
    └── api_discover.py
```

---

## Phase A - SDK Python (RobotClient)

### Interface publique de la classe RobotClient

```python
class RobotClient:
    # Connexion
    def __init__(self, host="10.42.0.1", ws_port=9090, mqtt_port=1883)
    async def connect() -> bool
    async def disconnect()

    # Mouvement
    async def move(linear_x: float, angular_z: float, duration: float = None)
    async def stop()
    async def forward(speed: float = 0.15, duration: float = 1.0)
    async def backward(speed: float = 0.15, duration: float = 1.0)
    async def rotate(angular_z: float, duration: float = 1.0)
    async def rotate_left(speed: float = 0.5, duration: float = 1.0)
    async def rotate_right(speed: float = 0.5, duration: float = 1.0)

    # Télémétrie
    async def get_pose() -> Pose           # {x, y, theta}
    async def get_status() -> RobotStatus  # état complet
    async def get_battery() -> int         # pourcentage
    async def get_velocity() -> tuple      # (linear, angular)

    # Navigation
    async def navigate_to_point(point_name: str) -> bool
    async def navigate_to_coord(x: float, y: float, theta: float) -> bool
    async def cancel_navigation() -> bool
    async def get_navigation_status() -> str

    # Carte & Points
    async def get_points() -> list[Point]
    async def get_map_metadata() -> MapMetadata

    # Localisation
    async def global_localization() -> bool
    async def set_init_pose(x: float, y: float, theta: float) -> bool

    # Callbacks (temps réel)
    def on_pose_update(callback: Callable)
    def on_status_update(callback: Callable)
    def on_people_detected(callback: Callable)

    # Urgence
    async def emergency_stop()
    async def release_emergency_stop()
```

---

## Phase B - Interface web

### Pages et fonctionnalités

#### Dashboard (page principale)

- Barre de statut en temps réel (batterie, état, mode, matching degree)
- Carte 2D avec position du robot en temps réel
- Joystick virtuel (tactile + clavier)
- Visualisation LiDAR overlay sur la carte
- Bouton E-Stop rouge proéminent
- Panneau vitesse et orientation

#### Navigation

- Liste des points enregistrés
- Envoi vers un point en un clic
- Suivi de trajectoire en temps réel
- Historique des navigations

#### Monitoring

- Graphiques temps réel (vitesse, batterie)
- Log des événements
- Statut des capteurs

#### Settings

- Configuration vitesse
- Mode de déplacement (sécurité/balance/efficacité)
- Paramètres réseau

### API Backend endpoints

```
GET  /api/robot/status          → état complet
GET  /api/robot/pose            → position actuelle
POST /api/robot/move            → {linear_x, angular_z, duration}
POST /api/robot/stop            → arrêt immédiat
POST /api/robot/emergency_stop  → E-Stop

GET  /api/navigation/points     → liste des points nommés
POST /api/navigation/goto       → {point_name}
POST /api/navigation/goto_coord → {x, y, theta}
POST /api/navigation/cancel     → annuler navigation

GET  /api/map/current           → carte courante
GET  /api/map/metadata          → métadonnées carte

WS   /ws/telemetry              → stream temps réel (pose, status, lidar)
```

---

## Phase C - Navigation autonome

### Service /poi - Navigation par point nommé

Le service ROS `/poi` accepte des requêtes de type `yutong_assistance/poiRequest`.
Les champs exacts sont à déterminer via introspection :

```python
await call_service(ws, "/rosapi/message_details",
                   {"type": "yutong_assistance/poiRequest"})
```

### Récupération des points enregistrés

```python
await call_service(ws, "/marker_manager/get_markers_details", {})
```

### Flux de navigation complet

```
1. get_points()              → récupérer liste points disponibles
2. navigate_to_point(name)   → appel service /poi
3. subscribe /navi_status    → suivre progression
4. subscribe /robot_pose     → afficher position en temps réel
5. on_arrived callback       → notification arrivée
```

---

## Variables d'environnement

```env
ROBOT_HOST=10.42.0.1
ROBOT_WS_PORT=9090
ROBOT_MQTT_PORT=1883
ROBOT_WIFI_SSID=TY1251D-03195
ROBOT_WIFI_PASSWORD=123456789
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

---

## Contraintes et points d'attention

1. **Connexion WiFi obligatoire** : se connecter au réseau `TY1251D-03195` avant tout
2. **control_state 30** : en mode `auto_navi`, les commandes `/cmd_vel` sont ignorées.
   Utiliser `/mobile_base/commands/velocity` + toggle "Télécommande manuelle" activé
3. **Matching degree** : en dessous de ~80%, la localisation est instable.
   Lancer `/global_localization` si matching < 60%
4. **Throttle rate** : limiter les subscriptions à 200ms minimum pour ne pas saturer le rosbridge
5. **E-Stop** : toujours implémenter et tester en premier
6. **Latence WiFi** : prévoir une latence variable 7–1654ms sur le réseau du robot
7. **Batterie** : robot actuellement à ~43%. Prévoir reconnexion auto si déconnexion

---

## Documentation interface opérateur

Guide complet du fonctionnement de l'interface web (panneaux, workflows, API, WebSocket, mode simulation) :

**[docs/INTERFACE.md](docs/INTERFACE.md)**

---

## Commandes de démarrage rapide

```bash
# Connexion WiFi (Windows)
netsh wlan connect name="TY1251D-03195"

# Test de connexion
ping 10.42.0.1

# Lancer le SDK
cd cybel
python -m sdk.tests.test_connection

# Lancer le backend + le frontend en une seule commande (depuis la racine)
python scripts/dev.py

# --- Ou séparément ---

# Lancer le backend
cd backend
uvicorn main:app --reload --port 8000

# Lancer le frontend
cd frontend
npm run dev
```

---

## Fichiers de référence (reverse engineering)

```
scripts/mqtt_listen.py        → découverte MQTT
scripts/ros_explore.py        → liste topics/services ROS
scripts/joystick_capture.py   → capture commandes joystick
scripts/robot_move.py         → test mouvement (VALIDÉ ✅)
scripts/robot_status.py       → monitoring état robot
scripts/introspect.py         → introspection types ROS
```

---

_Projet CYBEL - Robot CIOT TY1251D-03195_
_Protocole validé le 10/06/2026_
