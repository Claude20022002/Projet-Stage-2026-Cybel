# Robot & protocole — CYBEL

Connectivité réseau, protocole ROS/MQTT et audits de communication.

Index : [docs/README.md](../README.md)

---

## Documents

| Document | Description |
|----------|-------------|
| [ROBOT_CONNECTION.md](../ROBOT_CONNECTION.md) | Topologie réseau, IPs, rosbridge, ADB |
| [movement-audit/MOVEMENT_ARCHITECTURE.md](../movement-audit/MOVEMENT_ARCHITECTURE.md) | Architecture mouvement constructeur |
| [movement-audit/ROS_COMMUNICATION.md](../movement-audit/ROS_COMMUNICATION.md) | Topics / services ROS |
| [movement-audit/MQTT_COMMUNICATION.md](../movement-audit/MQTT_COMMUNICATION.md) | Broker MQTT |
| [movement-audit/JOYSTICK_FLOW.md](../movement-audit/JOYSTICK_FLOW.md) | Flux téléopération |
| [movement-audit/CYBEL_GAP_ANALYSIS.md](../movement-audit/CYBEL_GAP_ANALYSIS.md) | Écarts CYBEL vs constructeur |

---

## Audit APK constructeur

Analyse JADX `welcomepatrol` / `sentrymove` :

[cybel-conception/AUDIT_APK_CONSTRUCTEUR.md](../cybel-conception/AUDIT_APK_CONSTRUCTEUR.md)

---

## Scripts d'exploration

```powershell
python scripts/ros_explore.py
python scripts/robot_status.py
python scripts/mqtt_listen.py
python scripts/introspect.py
```

Protocole détaillé (topics, services) : [README racine](../../README.md) § Protocole.
