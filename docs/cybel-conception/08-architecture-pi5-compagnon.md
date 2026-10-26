# Architecture d'intégration d'un Raspberry Pi 5 compagnon sur CYBEL

> Document d'ingénierie robotique. Décrit l'ajout d'un **Raspberry Pi 5 comme calculateur
> compagnon** au robot CIOT TY1251D-03195, de façon **non destructive et réversible**, pour
> augmenter la puissance de calcul embarquée, moderniser la pile logicielle (ROS 2) et héberger
> l'IA de bord — **sans jamais modifier le châssis ni la tête Android**.
>
> Fait suite à l'étude de viabilité [07-upgrade-calculateur-embarque.md](07-upgrade-calculateur-embarque.md),
> qui classe cette option en tête (★★★★★).

---

## 1. Principes directeurs

1. **Non-destructif / réversible.** Le Pi s'ajoute ; on ne reflashe, ne repartitionne, ni ne
   remplace aucune carte interne. Démontable sans laisser de trace. C'est la même thèse que
   tout le projet CYBEL.
2. **Patron « companion computer ».** Architecture standard en robotique mobile : un calculateur
   de bord supplémentaire dialogue avec le contrôleur existant par un lien réseau/série, et
   porte les tâches de haut niveau (vision, IA, planification, IHM). Cf. ArduPilot et PX4, où
   le *companion / mission computer* (Linux) épaule le contrôleur temps réel.
3. **Réutilisation maximale de l'existant.** Le châssis n'expose que **rosbridge** (ROS 1,
   port 9090). CYBEL parle déjà ce protocole (JSON sur WebSocket) via `sdk/rosbridge.py`. Le Pi
   reprend ce canal tel quel — **aucune installation ROS n'est requise pour le niveau de base**.
4. **Dégradé gracieux.** Si le Pi tombe, le robot garde son app constructeur et sa tête Android
   intactes. Le Pi est un *plus*, pas un point de défaillance unique du robot.

---

## 2. Rappel du matériel existant (cible d'intégration)

| Calculateur | Rôle | OS | Interface exposée |
|---|---|---|---|
| **Châssis** | SLAM, `move_base`, moteurs, LiDAR, IMU, batterie 24 V/20 Ah | Linux + ROS 1 (Noetic/Melodic) | rosbridge WS `10.42.0.1:9090` ; SSH verrouillé |
| **Tête Android** | Écran tactile 15,6", caméras, HP, TTS, apps constructeur | Android 7.1 / RK3399 / 2 Go / 16 Go | `adb`, Termux, backend lite `:8001/:8000` |
| **MCU** | Contrôle bas niveau | firmware | pont série (`com.bjw.ComAssistant`) |

Segments réseau observés :

- **`10.42.0.0/24`** — Wi-Fi AP du châssis (SSID `TY1251D-03195`), passerelle `10.42.0.1`
  (rosbridge ici).
- **`192.168.20.0/24`** — lien interne filaire tête (`.1`) ↔ châssis (`.22`).
- **`172.16.0.0/16`** — Wi-Fi DHCP de la tête (IP variable).

> ⚠️ `ROS 1 Noetic` est **en fin de vie depuis mai 2025**. C'est un argument de plus pour
> **ne pas toucher au châssis** et passer par un pont applicatif (rosbridge) plutôt que de
> tenter de mettre à niveau sa distribution ROS.

---

## 3. Architecture physique (matériel)

### 3.1 Schéma d'intégration

```
                         ROBOT CIOT TY1251D-03195
┌──────────────────────────────────────────────────────────────────────┐
│                                                                        │
│   TÊTE ANDROID (RK3399)                 CHÂSSIS (Linux + ROS 1)        │
│   ┌───────────────────┐                 ┌───────────────────┐          │
│   │ Écran 15,6" tactile│  eth0 interne   │ rosbridge :9090    │          │
│   │ Caméras / HP / TTS │◄───192.168.20──►│ move_base / SLAM   │          │
│   │ Kiosque (WebView)  │                 │ LiDAR / IMU / MCU  │          │
│   └─────────┬─────────┘                 └─────────┬─────────┘          │
│             │ Wi-Fi 172.16.x                       │ Wi-Fi AP 10.42.0.1  │
│             │                                       │                    │
│   ╔═════════╪═══════════════════════════════════════╪═══════════════╗  │
│   ║  AJOUT : RASPBERRY PI 5 (companion)              │               ║  │
│   ║  ┌────────────────────────────────────────────┐ │               ║  │
│   ║  │ Ubuntu 24.04 + (ROS 2 Jazzy)                │ │               ║  │
│   ║  │ Backend CYBEL (FastAPI) + SDK rosbridge     │◄┘ WS 9090       ║  │
│   ║  │ IA de bord (reco faciale, STT, dialogue)    │                 ║  │
│   ║  │ (option) rosbridge→ROS2 republisher / Nav2  │                 ║  │
│   ║  └────────────────────────────────────────────┘                 ║  │
│   ║         ▲ alimentation                                            ║  │
│   ╚═════════╪════════════════════════════════════════════════════════╝  │
│             │                                                            │
│   ┌─────────┴─────────┐                                                  │
│   │ Buck 24 V → 5,1 V  │◄──── Batterie robot 24 V / 20 Ah (via fusible)   │
│   │ 5 A régulé (+fuse) │      (ou, phase 1 : batterie USB-C PD séparée)   │
│   └───────────────────┘                                                  │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 Nomenclature (BOM) indicative

| Élément | Spéc. / choix recommandé | Rôle | Justification / source |
|---|---|---|---|
| **Raspberry Pi 5** | 8 Go (ou 16 Go) RAM | Calculateur compagnon | 4× Cortex-A76 2,4 GHz ≫ RK3399 ; Ubuntu 24.04 Tier 1 pour ROS 2 |
| **Active Cooler** officiel | ventirad actif | Refroidissement | sans refroidissement, throttling en ~200 s sous charge ; l'Active Cooler stabilise à ~60–63 °C |
| **Stockage** | SSD NVMe + HAT M.2, **ou** microSD A2 ≥ 32 Go | OS + modèles IA | NVMe = fiabilité et I/O ; microSD = plus simple pour prototyper |
| **Alim phase 1** | Alim USB-C PD 27 W (5,1 V/5 A) officielle, **ou** powerbank PD | Bench / prototype | 5 A requis pour le budget USB complet du Pi 5 (sinon ports USB bridés ~600 mA) |
| **Alim phase 2** | Convertisseur buck 24 V→5,1 V, **5 A continu**, tolérance serrée | Alim depuis batterie robot | Pi sensible à la surtension (certains UBEC dérivent à 5,35 V) ; viser 5,1 V régulé |
| **Protection** | Fusible/polyfuse en entrée buck, condensateur de découplage | Sécurité électrique | isoler le Pi du bruit des moteurs ; régulateur dédié, pas partagé moteurs |
| **Réseau** | Wi-Fi interne du Pi 5 (ou dongle Wi-Fi USB) | Lien châssis (rosbridge) | rejoint l'AP `10.42.0.1` comme le PC aujourd'hui |
| **Caméra (option)** | caméra USB UVC | IA vision sur le Pi | si l'on déporte la reco faciale hors de la tête |
| **Fixation** | platine/entretoises à l'arrière, sangle | Montage non invasif | réversible, aucun perçage structurel |

> **Dimensionnement électrique.** Le Pi 5 dissipe ~5–12 W selon la charge (chiffres variables
> selon sources) ; l'IA de bord le pousse vers le haut. Prévoir **5 A à 5,1 V** avec marge, et
> **mesurer la conso réelle** avec ta charge avant de figer le buck. Vérifier l'autonomie de la
> batterie 24 V/20 Ah avec le Pi branché.

### 3.3 Refroidissement et thermique

- **Active Cooler obligatoire** : un Pi 5 nu *throttle* en quelques minutes sous charge
  soutenue (IA continue). Avec l'Active Cooler, la Fondation mesure ~60–63 °C en charge
  prolongée (seuils de throttling : 80 °C soft, 85 °C hard).
- Boîtier ventilé ou flux d'air ; attention à la poussière au sol (robot au rez-de-chaussée).

---

## 4. Architecture réseau

### 4.1 Plan d'adressage proposé

| Interface Pi | Réseau | Rôle |
|---|---|---|
| `wlan0` → AP robot | `10.42.0.0/24`, IP statique ex. `10.42.0.50` | **Accès rosbridge** châssis `10.42.0.1:9090` |
| `wlan1` (dongle, option) ou AP du Pi | réseau dédié / bâtiment | Accès opérateur (PC/tablette), SSH, maintenance |
| vers la **tête** | via le réseau commun (Wi-Fi) | TTS, caméras, affichage kiosque |

Trois stratégies de connexion au châssis, par ordre de simplicité :

1. **Wi-Fi sur l'AP du châssis (recommandé, phase 1).** Le Pi rejoint `TY1251D-03195`, IP
   statique, parle à `10.42.0.1:9090`. Identique à ce que fait le PC CYBEL — validé.
2. **Filaire sur le segment interne `192.168.20.x`** si un port Ethernet libre existe sur le
   châssis/tête. Plus stable (pas de gel Wi-Fi), mais dépend d'un port physique disponible.
3. **Pi en point d'accès** pour l'opérateur, tout en étant client de l'AP robot : le Pi devient
   la passerelle unique vers CYBEL.

> Le journal de la semaine d'intégration a montré des **gels Wi-Fi** (5 s sans message sur
> 60 s) sur l'AP du robot. Le client rosbridge du Pi doit donc **gérer la reconnexion
> automatique** (déjà implémenté dans `scripts/circulation.py` — à reprendre).

---

## 5. Architecture logicielle

### 5.1 Vue en couches (cible)

```
┌────────────────────────────────────────────────────────────┐
│  RASPBERRY PI 5 — Ubuntu 24.04 LTS                          │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Présentation : kiosque + opérateur (servis par FastAPI)│ │
│  └───────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Application : Backend CYBEL (FastAPI REST + WS)         │ │
│  │   + IA de bord : reco faciale, STT, dialogue           │ │
│  └───────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Domaine : SDK CYBEL (RobotReal / RobotMock)            │ │
│  │   ── client rosbridge JSON/WS ──┐                      │ │
│  └─────────────────────────────────┼──────────────────────┘ │
│  ┌─────────────────────────────────┼──────────────────────┐ │
│  │ (OPTION) Pont ROS 2 : node rclpy │ republie en topics   │ │
│  │   roslibpy → /cybel/* ROS 2  → Nav2 / rviz2 / rosbag2  │ │
│  └─────────────────────────────────┼──────────────────────┘ │
└────────────────────────────────────┼────────────────────────┘
                                      │ WebSocket rosbridge :9090
                                      ▼
                         CHÂSSIS ROS 1 (inchangé)
```

### 5.2 Deux niveaux d'intégration

**Niveau 0 — Pragmatique (à faire en premier, aucun ROS sur le Pi).**
Le Pi exécute le **backend CYBEL existant** (Python/FastAPI). Le SDK se connecte au châssis par
rosbridge, **exactement comme aujourd'hui depuis le PC**. Gain immédiat : backend permanent à
bord, beaucoup plus de RAM/CPU que Termux, IA lourde possible. **Zéro ROS à installer, zéro
dépendance sur les messages custom du châssis.** C'est le portage le plus sûr.

**Niveau 1 — ROS 2 natif (évolution).**
Installer **Ubuntu 24.04 + ROS 2 Jazzy** (`ros-jazzy-ros-base` + `ros-dev-tools`). Écrire un
**node pont** `rclpy` qui s'abonne au châssis via **roslibpy** (client rosbridge Python) et
**republie** les flux utiles (`/robot_pose`, `/scan`, `/robot_status`…) en topics ROS 2
`/cybel/*`. On accède alors à l'écosystème moderne (**Nav2, rviz2, rosbag2, tf2**) **sans
toucher au châssis**.

> **Pourquoi pas `ros1_bridge` directement ?** Le pont officiel ROS 1 ↔ ROS 2 exige un **master
> ROS 1 accessible** et la **recompilation des types de messages custom** dans les deux
> espaces de travail. Or le châssis n'expose pas un master ROS joignable mais **rosbridge**, et
> ses messages sont **propriétaires** (`yutong_assistance/GlobalLocate`, `yutong_assistance/cmd`,
> partiellement rétro-conçus). Le pont applicatif **roslibpy → rclpy** contourne ces deux
> obstacles : rosbridge transporte du **JSON type-agnostique**, et l'on ne republie que ce dont
> on a besoin, avec nos propres définitions `.msg`. Garder `ros1_bridge` seulement si un accès
> master ROS 1 complet devient disponible.

### 5.3 Répartition des tâches Pi ↔ tête Android

| Fonction | Où l'exécuter | Remarque |
|---|---|---|
| Backend CYBEL, navigation, logique visite | **Pi** | déménage depuis Termux |
| IA : reco faciale, STT, dialogue | **Pi** (si caméra/micro accessibles) | sinon garder sur la tête |
| **Caméras** | **tête** (physiquement dessus) | soit garder la reco faciale sur la tête, soit ajouter une **caméra USB au Pi** |
| **TTS** | **tête** (HP + moteur Google TTS) | le Pi déclenche via **endpoint HTTP** sur la tête (plus fiable qu'adb Wi-Fi, fermé à Ghandi) |
| **Écran tactile / kiosque** | **tête** (WebView) | pointer la WebView vers `http://<pi>:8000/kiosk/` |

> **Vie privée conservée.** Que la reco faciale tourne sur la tête ou sur le Pi, elle reste
> **on-device** : embeddings seulement, aucune image ne quitte le robot. Ne jamais streamer les
> images caméra de la tête vers le Pi en clair sur le Wi-Fi.

### 5.4 Exploitation (systemd)

- Backend CYBEL en service `systemd` (redémarrage auto, logs `journald`).
- Node pont ROS 2 en service séparé (si niveau 1).
- Démarrage au boot ; watchdog de reconnexion rosbridge.

---

## 6. Flux de données (séquence navigation)

```
Kiosque (tête)        Backend CYBEL (Pi)       rosbridge (châssis)
     │  POST /poi            │                        │
     │─────────────────────►│                         │
     │                      │  publish /poi (WS JSON) │
     │                      │────────────────────────►│
     │                      │                         │ move_base exécute
     │                      │  sub /robot_pose,status │
     │                      │◄────────────────────────│
     │                      │  (vérif. pose + nav_status 602→603 ;
     │                      │   garde-fou « transport ≠ exécution »)
     │  WS /ws/telemetry    │                         │
     │◄─────────────────────│                         │
     │  TTS (HTTP → tête)   │                         │
     │◄─────────────────────│                         │
```

La logique métier (visite, circulation, garde-fous H4) est **inchangée** : seul l'hôte
d'exécution passe de Termux au Pi.

---

## 7. Plan de migration (phasé)

| Phase | Contenu | Critère de sortie |
|---|---|---|
| **P0 — Bench** | Pi 5 + Ubuntu 24.04, alim USB-C PD, SDK CYBEL en mock | backend tourne, tests unitaires OK sur le Pi |
| **P1 — Lien châssis** | Pi sur Wi-Fi AP robot, `ROBOT_MOCK=false`, rosbridge | télémétrie reçue, latence mesurée vs PC |
| **P2 — Backend à bord** | backend CYBEL en `systemd` sur le Pi ; kiosque pointe sur le Pi | navigation POI + visite guidée depuis le Pi |
| **P3 — TTS / IA** | endpoint TTS sur la tête ; reco faciale (tête ou caméra Pi) | accueil vocal + reco bout en bout |
| **P4 — Alim embarquée** | buck 24 V→5,1 V + fusible, montage arrière | autonomie et thermique validées en roulant |
| **P5 — ROS 2 (option)** | node pont roslibpy→rclpy, Nav2/rviz2 | visualisation ROS 2 des flux châssis |

---

## 8. Risques et mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Surtension buck → Pi | Destruction du Pi | buck régulé à tolérance serrée, viser 5,1 V, tester à vide avant branchement |
| Bruit moteurs sur l'alim | Reboots aléatoires | régulateur **dédié** au Pi, découplage, fusible ; en P1 batterie séparée |
| Gel Wi-Fi AP robot | Perte commande | reconnexion auto rosbridge (reprise de `circulation.py`) ; envisager lien filaire |
| Throttling thermique | Perte de perf IA | Active Cooler officiel, boîtier ventilé |
| `adb` Wi-Fi fermé (tête) | TTS Pi→tête KO | endpoint **HTTP** TTS sur la tête, pas d'adb réseau |
| Messages custom châssis | Pont ROS 2 incomplet | rester en rosbridge JSON ; ne republier que les types maîtrisés |
| Conso batterie accrue | Autonomie réduite | mesurer ; couper le Pi quand robot en charge si besoin |

---

## 9. Plan de validation (mesures)

Réutiliser l'esprit instrumenté du projet (cf. `paper/icra_2027/tools/stats.py`) :

- **Latence rosbridge** aller-retour depuis le Pi vs depuis le PC (p50/p95).
- **Taux de complétion** visite guidée / circulation depuis le Pi (viser ≥ celui du PC).
- **Charge CPU / température** du Pi sous IA continue (reco faciale + STT).
- **Autonomie** : durée de fonctionnement sur batterie 24 V avec le Pi alimenté par le buck.
- **Robustesse Wi-Fi** : nombre de reconnexions rosbridge / heure, impact sur les trajets.

---

## 10. Sources et références

### Matériel — Raspberry Pi 5 et alimentation
- Raspberry Pi — *Heating and cooling Raspberry Pi 5* (seuils 80/85 °C, Active Cooler ~60–63 °C) :
  https://www.raspberrypi.com/news/heating-and-cooling-raspberry-pi-5/
- Raspberry Pi — *Use case specific thermal performance of Raspberry Pi SBCs* (white paper) :
  https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-010139-WP-1-Use-case-specific%20thermal%20performance%20of%20Raspberry%20Pi%20SBCs.pdf
- Alim officielle 27 W USB-C PD (5,1 V/5 A), fiche revendeur :
  https://raspberrypi.dk/en/product/raspberry-pi-power-supply-usb-c-eu-5v-5a-black/
- Convertisseur buck 24 V→5 V/5 A (exemple de module) :
  https://zbotic.in/product/dc-dc-step-down-buck-converter-power-supply-module-24v-12v-9v-to-5v-5a-25w-replace-lm2596s/
- UBEC 5 V/3 A — avertissement tolérance (dérive jusqu'à 5,35 V) :
  https://thepihut.com/products/ubec-dc-dc-step-down-buck-converter-5v-3a-output

### Logiciel — ROS 2 sur Pi 5
- ROS 2 Jazzy — installation Ubuntu/Debian (doc officielle) : https://docs.ros.org/en/jazzy/Installation.html
- Guide install ROS 2 Jazzy sur Ubuntu 24.04 : https://techoverflow.net/2024/12/08/how-to-install-ros2-jazzy-desktop-on-ubuntu-24-04/
- Retour pratique Pi 5 + Ubuntu 24 + Jazzy : https://forum.dexterindustries.com/t/argh-they-want-us-to-try-ros-2-jazzy-jalisco/9729

### Pont ROS 1 ↔ ROS 2 et rosbridge
- `ros1_bridge` — page d'index (compatibilité, Noetic EOL mai 2025) : https://index.ros.org/p/ros1_bridge/
- `ros1_bridge` — doc API et mapping des messages : https://docs.ros.org/en/humble/p/ros1_bridge/
- `rosbridge_suite` (JSON/WebSocket vers ROS) : https://github.com/RobotWebTools/rosbridge_suite
- Spécification du protocole rosbridge v2 : https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md
- `roslibpy` — client Python rosbridge (API) : https://roslibpy.readthedocs.io/en/latest/

### Patron « companion computer »
- ArduPilot — *Companion Computers* (MAVLink, SBC ARM de bord) : https://ardupilot.org/dev/docs/companion-computers.html
- PX4 — *System Architecture* (flight controller + companion/mission computer Linux) :
  https://docs.px4.io/main/en/concept/px4_systems_architecture.html
- ModalAI — *Top 5 companion computers for UAVs* (panorama matériel) :
  https://www.modalai.com/blogs/blog/top-5-companion-computers-for-uavs

### Références internes CYBEL
- [07-upgrade-calculateur-embarque.md](07-upgrade-calculateur-embarque.md) — étude de viabilité.
- [../ROBOT_CONNECTION.md](../ROBOT_CONNECTION.md) — topologie réseau, IP, rosbridge.
- [../ARCHITECTURE_LOGICIELLE.md](../ARCHITECTURE_LOGICIELLE.md) — couches logicielles, ports, débits.
- `sdk/rosbridge.py`, `sdk/real_robot.py` — client rosbridge réutilisé par le Pi.
- `scripts/circulation.py` — reconnexion rosbridge automatique à reprendre.
```
