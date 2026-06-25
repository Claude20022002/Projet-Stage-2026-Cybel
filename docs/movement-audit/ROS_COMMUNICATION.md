# Communication ROS — SentryMove vs CYBEL

> Canal unique : **WebSocket rosbridge** `ws://<host>:9090`  
> Protocole : JSON `{ "op": "advertise|publish|subscribe|call_service", "topic"|"service", "msg"|"args", "type" }`

---

## 1. Téléopération — topic principal

### SentryMove (Deployment Tool)

| Élément | Valeur |
|---------|--------|
| **Topic** | `/cmd_vel_mux/input/teleop` |
| **Type** | `geometry_msgs/Twist` |
| **Init** | `{"op":"advertise","topic":"/cmd_vel_mux/input/teleop","type":"geometry_msgs/Twist"}` |
| **Runtime** | `{"op":"publish","topic":"/cmd_vel_mux/input/teleop","msg":{...}}` |
| **Classe** | `MsgManager.velocityMsg(angularZ, linearX)` → `SelfChassis.setVelocity(wz, vx)` |
| **Champs utilisés** | `msg.linear.x`, `msg.angular.z` uniquement (y/z linéaire et x/y angulaire = 0) |

**Échelle constructeur :**

- `angular.z` publié = `wzSpeed × 0.8`
- Rampe linéaire : ±0.025 m/s toutes les **100 ms** (~10 Hz)
- Vitesses max (niveau App) : **0.3 / 0.5 / 0.8 m/s** selon `App.speedLevel`, synchronisé via `/velocity_control`

### CYBEL (SDK actuel)

| Élément | Valeur | Fichier |
|---------|--------|---------|
| **Topic** | `/cmd_vel_mux/input/teleop` | `sdk/constants.py` L22 |
| **Type** | `geometry_msgs/Twist` | `sdk/constants.py` L96 |
| **Init** | `advertise` au 1er `move()` | `sdk/real_robot.py` L620–625 |
| **Publish** | Twist nested complet | `sdk/real_robot.py` L626–631 |
| **Vitesses UI** | `linear_x=±0.2`, `angular_z=±0.5` | `frontend/src/app.ts` L37–38 |
| **Échelle angulaire ×0.8** | **Non appliquée** | — |
| **Rampe 10 Hz** | **Non** (intervalle frontend ~200 ms) | `frontend/src/app.ts` |

### Legacy CYBEL (scripts — obsolète)

| Script | Topic | Problème |
|--------|-------|----------|
| `scripts/robot_move.py` | `/mobile_base/commands/velocity` | Topic ignoré si mux actif |
| `scripts/teleop_test.py` | `/mobile_base/commands/velocity` | Format plat invalide pour Twist |
| `scripts/termux/cybel_lite.py` (stop) | `/mobile_base/commands/velocity` | Annulation partielle |

---

## 2. Payloads exacts — joystick 4 touches (SentryMove)

Vitesse par défaut : **niveau 1 → 0.5 m/s** (`App.getChassisSpeed()`).

### Avancer (UP)

```json
{
  "op": "publish",
  "topic": "/cmd_vel_mux/input/teleop",
  "msg": {
    "angular": { "x": 0.0, "y": 0.0, "z": 0.0 },
    "linear":  { "x": 0.5, "y": 0.0, "z": 0.0 }
  }
}
```

(`linear.x` monte par rampe +0.025 / 100 ms depuis 0)

### Reculer (DOWN)

```json
{ "msg": { "angular": { "z": 0.0 }, "linear": { "x": -0.5 } } }
```

### Tourner gauche (LEFT)

```json
{ "msg": { "angular": { "z": 0.64 }, "linear": { "x": 0.0 } } }
```

(0.8 × 0.8 = **0.64 rad/s**)

### Tourner droite (RIGHT)

```json
{ "msg": { "angular": { "z": -0.64 }, "linear": { "x": 0.0 } } }
```

### Arrêt (relâchement)

```json
{ "msg": { "angular": { "z": 0.0 }, "linear": { "x": 0.0 } } }
```

---

## 3. Navigation autonome

### Objectif coordonnées — `/navi_goal`

**SentryMove** — `MsgManager.sendGoalMsg(x, y, theta)` :

```json
{
  "op": "publish",
  "topic": "/navi_goal",
  "msg": {
    "header": { "frame_id": "map" },
    "pose": {
      "position": { "x": 1.0, "y": 2.0, "z": 0.0 },
      "orientation": {
        "x": 0.0, "y": 0.0,
        "z": "<sin(theta/2)>",
        "w": "<cos(theta/2)>"
      }
    }
  }
}
```

**CYBEL** — `RealRobot.navigate_to_coordinate()` : **même structure** (`sdk/real_robot.py` L981–995).

### Navigation POI nommé

| Ordre | Service SentryMove | Args typiques | CYBEL SDK |
|-------|-------------------|---------------|-----------|
| 1 | `/tag_manager/navi` | `{name, tag_name}` | ✅ `build_poi_nav_chain()` |
| 2 | `/poi` | `{name, point_name, command:"go"}` | ✅ fallback |
| — | cybel_lite | `/poi` seul | ⚠️ pas de `tag_manager` |

### Annulation navigation

| Action | Topic / service | SentryMove | CYBEL SDK | cybel_lite |
|--------|-----------------|------------|-----------|------------|
| Cancel move_base | `/move_base/cancel` publish + service | ✅ | ✅ | ❌ publish seulement via path_follower |
| Cancel path | `/path_follower/cancel` | ✅ | ✅ | ✅ |
| POI stop | `/poi` `{command:"stop"}` | ✅ | ✅ | ✅ |
| Marqueurs | `/marker_manager/control` `{command:"stop"}` | ✅ | ✅ | ✅ |
| Vitesse zéro | `/cmd_vel_mux/input/teleop` | ✅ | ✅ | ⚠️ `mobile_base/commands/velocity` |

---

## 4. Services ROS — mouvement

| Service | Usage | Args / cmd | SentryMove | CYBEL |
|---------|-------|------------|------------|-------|
| `/change_location_mode` | Mode manuel (0) / auto (1) | `{mode: 0\|1}` | Config / nav | ✅ `set_manual_mode`, `ensure_automatic_navigation` |
| `/velocity_control` | Profil vitesse max | cmd 2–8, 60/61, 99 | ✅ ConfigFragment | ❌ non exposé UI |
| `/global_locate` | Relocalisation | `{}` | ✅ | ✅ chaîne prioritaire |
| `/global_localization` | Relocalisation fallback | `{}` | fallback | ✅ |
| `/poi` | Nav / stop POI | `command`, `name` | ✅ | ✅ |
| `/tag_manager/navi` | Nav tag nommé | `name`, `tag_name` | ✅ | ✅ |
| `/start_recharge` | Retour borne | — | ✅ | ✅ |
| `/config_mqtt_server` | Config broker MQTT | `cmd`, `host`, `switch_on` | ✅ à la connexion | ✅ `config_mqtt_server()` |

### Codes `/velocity_control` (constructeur)

| cmd | Niveau App | Vitesse linéaire max |
|-----|------------|----------------------|
| 0–2 | 0 (sécurité) | 0.3 m/s |
| 3–5 | 1 (équilibre) | 0.5 m/s |
| 6–8 | 2 (efficacité) | 0.8 m/s |
| 60 / 61 | — | smooth control on/off |
| 99 | — | GET état actuel |

---

## 5. Topics d’état (abonnements)

| Topic | Type | Usage mouvement |
|-------|------|-----------------|
| `/robot_pose` | `geometry_msgs/Pose2D` | Position |
| `/robot_status` | `yutong_assistance/RobotStatus` | `control_state`, `nav_status`, `matching_degree` |
| `/navi_status` | — | Codes 600–604 |
| `/localization_confidence` | `std_msgs/Float64` | Seuil localisation |
| `/soft_stop` | `std_msgs/Bool` | E-stop logiciel |

### Codes `nav_status` (impact navigation auto)

| Code | Signification | CYBEL bloque ? |
|------|---------------|----------------|
| 600 | Non localisé | ✅ oui |
| 601 | Prêt | non |
| 602 | En navigation | ✅ nouvelle nav |
| 603 | Arrivé | non |
| 604 | Erreur | ✅ oui |

---

## 6. E-stop logiciel

```json
{
  "op": "publish",
  "topic": "/soft_stop",
  "msg": { "data": true }
}
```

SentryMove : `MainPresenter.softStop()` → toggle via `SelfChassis.sendEStop()`.  
CYBEL : `RealRobot.emergency_stop()` — même topic.

---

## 7. Réponse à la question opérationnelle

| Action utilisateur | Instructions exactes Deployment Tool |
|--------------------|-------------------------------------|
| **Avancer** | Publish répété `/cmd_vel_mux/input/teleop` : `linear.x` → +0.5 m/s (rampe), `angular.z=0` |
| **Reculer** | `linear.x` → -0.5 m/s, `angular.z=0` |
| **Gauche** | `angular.z=+0.64`, `linear.x=0` |
| **Droite** | `angular.z=-0.64`, `linear.x=0` |
| **Stop** | `linear.x=0`, `angular.z=0` |

**Reproduire dans CYBEL :**

1. `advertise` + `publish` sur `/cmd_vel_mux/input/teleop` (déjà fait dans `RealRobot._publish_velocity`)
2. **Pas besoin** de `/change_location_mode` mode 0 pour téléop côté constructeur — CYBEL l’exige actuellement si `control_state==30`
3. Appliquer échelle `angular.z × 0.8` et rampe 10 Hz pour parité fine (optionnel)
4. Pour navigation auto : `/navi_goal` ou `/tag_manager/navi` + prérequis `nav_status` 601 et localisation ≥ 60 %
