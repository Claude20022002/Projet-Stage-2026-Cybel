# Communication MQTT — rôle dans le mouvement

> **Conclusion immédiate : le joystick et la navigation Deployment Tool ne passent pas par MQTT.**

---

## 1. Constats APK

| Vérification | Résultat |
|--------------|----------|
| Client MQTT (Paho, etc.) dans `sentrymove` / `welcomepatrol` | **Absent** |
| Publish MQTT pour `cmd_vel` / vitesse | **Aucun** |
| Joystick → MQTT | **Non** |

Le mouvement manuel et autonome passent exclusivement par **rosbridge WebSocket port 9090**.

---

## 2. Rôle réel du MQTT dans SentryMove

MQTT est géré **côté châssis ROS**, configuré depuis l’app via un **service ROS** (pas un client MQTT Android).

### Service `/config_mqtt_server`

| Élément | Valeur |
|---------|--------|
| Classe | `MsgManager.configStationServer(cmd, host, switch)` |
| ID rosbridge | `set_mqtt_server` |
| Appelé à la connexion | `cmd=0` depuis `MainPresenter.contend(true)` |

**Format :**

```json
{
  "op": "call_service",
  "service": "/config_mqtt_server",
  "id": "set_mqtt_server",
  "args": {
    "cmd": 1,
    "host": "<broker_ip>",
    "switch_on": true,
    "wan_switch": false
  }
}
```

| cmd | Action |
|-----|--------|
| 0 | Init / désactivation (post-connexion) |
| 1 | Définir `host` du broker |
| 2 | `switch_on` on/off |
| 3 | `wan_switch` on/off |

### Topic `/robot_list`

```json
{
  "op": "subscribe",
  "topic": "/robot_list",
  "type": "mqtt_msg/RobotList",
  "id": "get_robot_list"
}
```

**Usage :** liste multi-robots sur la station — **pas de commande de déplacement**.

---

## 3. CYBEL et MQTT

| Composant | Rôle mouvement |
|-----------|----------------|
| `backend/services/mqtt_bridge_service.py` | **Écoute passive** → événements debug WebSocket |
| `sdk/constants.py` — `MQTT_DEFAULT_TOPICS` | `test_mul` (télémétrie odom passive) |
| `RealRobot.config_mqtt_server()` | Configure le broker châssis via ROS — **ne publie pas de cmd** |
| `scripts/mqtt_listen.py` | Exploration passive |

**Aucun chemin MQTT → mouvement** dans CYBEL. C’est cohérent avec l’APK constructeur.

---

## 4. Autres canaux (hors MQTT) — pour contexte

Deployment Tool et WelcomePatrol utilisent aussi :

| Canal | Port | Usage mouvement |
|-------|------|-----------------|
| **rosbridge WebSocket** | 9090 | **Téléop + nav + services** ← canal principal |
| TCP SROS | 28888 | Cloud CIOT — nav par nom/coordonnées (WelcomePatrol) |
| HTTP CMS | 80/443 | Contenu, patrouilles — pas cmd directe châssis |

CYBEL contourne SROS/cloud et parle directement rosbridge — **aligné avec SentryMove**.

---

## 5. Impact diagnostic « CYBEL ne bouge plus »

| Hypothèse | Verdict |
|-----------|---------|
| MQTT mal configuré empêche téléop | **Non** — téléop = WebSocket uniquement |
| Broker `10.42.0.1:1883` requis pour joystick | **Non** |
| `/config_mqtt_server` manquant bloque mouvement | **Non** pour téléop ; peut affecter multi-robot |

**Pistes réelles :** rosbridge `:9090`, topic `/cmd_vel_mux/input/teleop`, `nav_status`, mode `control_state`, localisation.

---

## 6. Tableau synthèse

| Question | Deployment Tool | CYBEL |
|----------|-----------------|-------|
| Joystick utilise MQTT ? | Non | Non |
| Nav autonome utilise MQTT ? | Non | Non |
| MQTT configuré comment ? | Service ROS `/config_mqtt_server` | Idem (optionnel) |
| MQTT observé par CYBEL ? | Via bridge châssis (`test_mul`) | Écoute passive seulement |
