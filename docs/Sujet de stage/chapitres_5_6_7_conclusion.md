# Chapitres 5, 6 et 7 — Rapport de stage CYBEL (HESTIM)

> **Projet** : Conception et développement d'une plateforme de commande et d'interaction autonome pour un robot de service Android — CIOT TY1251D-03195  
> **Établissement** : HESTIM Engineering & Business School  
> **Encadrant** : Dr. Sridath Tula  
> **Stagiaire** : [Nom de l'étudiant]  
> **Période** : juin — septembre 2026  
> **État du projet** : fin juin 2026 — plateforme opérationnelle en démonstration, validation terrain du parcours en cours

---

# 5 Méthodologie et planification

## 5.1 Démarche adoptée

La méthodologie retenue combine **rétro-ingénierie incrémentale non destructive** et **développement logiciel itératif mock-first**. Elle répond directement à l'absence de documentation constructeur et à la disponibilité limitée du robot physique.

### Cycle de découverte protocolaire

Chaque hypothèse sur le protocole du robot suit le cycle suivant :

```mermaid
flowchart LR
    A[Observation passive] --> B[Introspection ROS]
    B --> C[Test isolé script]
    C --> D{Vérification effet réel?}
    D -->|Oui| E[Intégration SDK]
    D -->|Non| F[Rejet ou nouvelle piste]
    E --> G[Tests mock puis réel]
    F --> A
```

**Principes directeurs :**

1. **Observer avant d'agir** — écoute passive MQTT et rosbridge avant toute publication.
2. **Vérifier l'effet réel** — une commande acceptée par rosbridge n'est pas forcément exécutée (règle H4 du projet).
3. **Simuler d'abord** — chaque fonctionnalité est validée dans `MockRobot` avant portage dans `RealRobot`.
4. **Documenter au fil de l'eau** — scripts `scripts/` versionnés comme journal de bord exécutable.
5. **Sécuriser le matériel** — annulation de navigation prête, E-Stop accessible, pas de commandes destructives.

### Phases du stage (alignement sujet HESTIM)

| Phase | Objectif | Livrable principal |
|-------|----------|-------------------|
| 1 — Connectivité | Joindre le robot, cartographier le réseau | Topologie documentée |
| 2 — Investigation | Reconstruire le protocole ROS/MQTT | `constants.py`, scripts d'exploration |
| 3 — Développement | SDK, API, interfaces web et Android | Plateforme CYBEL |
| 4 — Validation | Tests terrain, rapport, démonstration | Parcours labo validé |

---

## 5.2 Organisation du travail

### Répartition des activités

```mermaid
pie title Répartition indicative du temps de stage
    "Rétro-ingénierie & réseau" : 25
    "Développement SDK + backend" : 30
    "Interfaces web (opérateur + kiosque)" : 20
    "Android + Termux + TTS" : 15
    "Tests terrain & documentation" : 10
```

### Organisation hebdomadaire type

| Jour | Activité principale | Environnement |
|------|---------------------|---------------|
| Lundi–Mercredi | Développement (mock) + documentation | PC, sans robot |
| Jeudi | Tests sur robot réel (si disponible) | Wi-Fi `TY1251D-03195` |
| Vendredi | Intégration, déploiement tablette, rédaction | PC + tablette Termux |

### Outils de suivi

- **Git** : historique des découvertes et du code (`main` synchronisé avec le dépôt).
- **Scripts d'exploration** : preuves reproductibles (`ros_explore.py`, `robot_status.py`, etc.).
- **Documentation Markdown** : `docs/` (6+ guides techniques).
- **Assistant IA (Cursor / Claude)** : accélération code et documentation, **toujours validé par le stagiaire** avant test sur robot.

### Points de synchronisation

- Réunions avec l'encadrant HESTIM (avancement, blocages).
- Tests sur site lorsque le robot et le laboratoire sont disponibles.
- Itérations rapides PC ↔ tablette via `deploy_termux.py`.

---

## 5.3 Outils et technologies utilisés

### Vue d'ensemble

```mermaid
flowchart TB
    subgraph Dev["Poste de développement"]
        PY[Python 3.13]
        TS[TypeScript + Vite]
        GIT[Git]
        ADB[ADB / Android SDK CLI]
    end

    subgraph Runtime["Exécution"]
        FA[FastAPI + uvicorn]
        RB[rosbridge WebSocket]
        TERM[Termux + Starlette]
    end

    subgraph Cible["Robot CIOT"]
        ROS[ROS Noetic/Melodic]
        AND[Android 7.1 RK3399]
    end

    PY --> FA
    PY --> RB
    TS --> FA
    FA --> RB
    TERM --> RB
    ADB --> AND
    RB --> ROS
```

### 5.3.1 ROS (Robot Operating System)

**Rôle dans le projet** : le châssis du robot exécute ROS pour la localisation SLAM, la planification (`move_base`) et l'exécution des trajectoires. CYBEL n'accède pas directement à ROS natif (C++/Python ROS) mais via **rosbridge** — pont WebSocket JSON.

| Élément | Usage CYBEL |
|---------|-------------|
| Topics lecture | `/robot_pose`, `/robot_status`, `/scan_filter`, `/get_current_map`, `/detected_people_array` |
| Topics commande | `/mobile_base/commands/velocity`, `/navi_goal`, `/path_follower/cancel` |
| Services | `/poi`, `/change_location_mode`, `/global_localization`, `/marker_manager/get_markers_details` |
| Introspection | `/rosapi/topics`, `/rosapi/services`, `/rosapi/subscribers` |

**Codes `nav_status` documentés** :

| Code | Libellé | Interprétation |
|------|---------|----------------|
| 600 | En initialisation | Robot non localisé |
| 601 | Prêt | Peut naviguer |
| 602 | En navigation | Trajectoire en cours |
| 603 | Arrivé | Objectif atteint |
| 604 | Erreur | Obstacle, chemin bloqué ou destination inaccessible |

### 5.3.2 FastAPI

**Rôle** : API REST + WebSocket pour l'interface opérateur PC.

- **Routers** : robot, navigation, carte, speech, reception, tour, settings.
- **WebSocket** `/ws/telemetry` : diffusion temps réel (pose, statut, carte, LiDAR).
- **Lifespan** : connexion rosbridge au démarrage (avec reconnexion en arrière-plan).
- **Configuration** : `backend/.env` via `pydantic-settings` (`ROBOT_MOCK`, `ROBOT_HOST`, etc.).

**Alternative embarquée** : sur tablette Termux, **Starlette** (`cybel_lite.py`) remplace FastAPI car `pydantic-core` ne compile pas sur Python 3.13 Termux.

### 5.3.3 TypeScript

**Rôle** : deux applications web sans framework lourd (Vite + TypeScript pur).

| Application | Port dev | Utilisateur |
|-------------|----------|-------------|
| `frontend/` | 5173 | Opérateur — carte, téléop, visite, accueil |
| `frontend-kiosk/` | 5174 | Visiteur — visite guidée FR/EN |

**Choix** : pas de React/Vue — surface UI maîtrisable par un développeur seul, HMR Vite rapide. Build **IIFE** pour le kiosque (compatibilité WebView Chrome 49 / Android 7.1).

### 5.3.4 Android

Deux applications Java légères, compilées **sans Gradle** (`javac`, `d8`, `apksigner`) :

| APK | Rôle |
|-----|------|
| **CybelTTSBridge** | `BroadcastReceiver` + `TextToSpeech` (Google TTS) |
| **CybelVisitorKiosk** | WebView plein écran → `/kiosk/`, mode kiosque |

**Contraintes Android 7.1** : pas de modules ES, safe-area (`viewport-fit=cover`), `network_security_config` pour HTTP local Termux.

### 5.3.5 ADB (Android Debug Bridge)

**Rôle** : pont TTS depuis le **PC développeur** vers la tête Android.

```bash
adb devices
adb shell am broadcast -n com.cybel.ttsbridge/.SpeakReceiver \
  -a com.cybel.ttsbridge.SPEAK --es text "Test vocal"
```

- Câble USB requis (pas de `adb connect` Wi-Fi fiable sur ce modèle).
- Sur **tablette autonome** : TTS via `speak_local` (broadcast sans ADB).

### 5.3.6 rosbridge et communication réseau

| Canal | Adresse | Protocole | Usage |
|-------|---------|-----------|-------|
| rosbridge | `ws://10.42.0.1:9090` (PC) ou `192.168.20.22:9090` (Termux) | WebSocket JSON | Principal |
| MQTT | `10.42.0.1:1883` | MQTT 3.1.1 | Télémétrie passive |
| ADB | USB | Android Debug Bridge | TTS PC |
| HTTP Termux | IP tablette `:8000` | HTTP | Kiosque embarqué |

**Client CYBEL** : `sdk/rosbridge.py` — connexion avec timeout 20 s, 3 tentatives, keepalive ping, reconnexion automatique.

---

## 5.4 Planning du projet

### Diagramme de Gantt

```mermaid
gantt
    title Planning du stage CYBEL (juin — septembre 2026)
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m

    section Phase 1 — Connectivité
    Analyse matérielle & réseau     :done, p1a, 2026-06-01, 10d
    Scan ports & topologie            :done, p1b, after p1a, 5d

    section Phase 2 — Investigation
    Introspection ROS rosapi          :done, p2a, 2026-06-10, 14d
    Exploration MQTT & commandes      :done, p2b, 2026-06-15, 10d
    Résolution TTS (ADB + bridge)   :done, p2c, 2026-06-20, 10d

    section Phase 3 — Développement
    SDK mock + real_robot           :done, p3a, 2026-06-01, 30d
    Backend FastAPI + WebSocket     :done, p3b, 2026-06-15, 25d
    Interface opérateur             :done, p3c, 2026-06-20, 25d
    TourEngine + lab_tour.json      :done, p3d, 2026-06-22, 15d
    Kiosque + CybelVisitorKiosk     :done, p3e, 2026-06-25, 15d
    Déploiement Termux              :done, p3f, 2026-06-28, 10d

    section Phase 4 — Validation
    Tests navigation terrain        :active, p4a, 2026-07-01, 30d
    Ajustement coordonnées parcours :p4b, after p4a, 20d
    Tests intégration & rapport     :p4c, 2026-08-01, 30d
    Soutenance & démonstration        :milestone, p4d, 2026-09-15, 1d
```

### Jalons atteints (fin juin 2026)

| Jalon | Date | Statut |
|-------|------|--------|
| Connectivité rosbridge PC | mi-juin 2026 | ✅ |
| TTS fonctionnel (ADB + bridge) | mi-juin 2026 | ✅ |
| Interface opérateur complète | fin juin 2026 | ✅ |
| Kiosque affiché sur tablette | fin juin 2026 | ✅ |
| Parcours 8 arrêts configuré | fin juin 2026 | ✅ |
| Navigation terrain sans erreur 604 | juillet 2026 | ⏳ |

---

## 5.5 Difficultés rencontrées durant la phase d'investigation

### Réseau et topologie

| Difficulté | Impact | Solution |
|------------|--------|----------|
| Topologie dual-stack (`10.42.0.1`, `172.16.0.x`, `192.168.20.x`) | Confusion des IP cibles | Documentation `ROBOT_CONNECTION.md`, `ROBOT_HOST` distinct PC/Termux |
| Latence Wi-Fi variable (89–1654 ms) | Timeouts rosbridge | Timeout 20 s, 3 retries, pas de `--reload` par défaut |
| rosbridge saturé (connexions zombies) | Handshake impossible | Une instance backend, redémarrage robot si besoin |
| IP DHCP tête Android instable | TTS/ADB cassés | `SPEECH_ADB_SERIAL` vide → premier USB ; broadcast local sur tablette |

### Protocole ROS

| Difficulté | Impact | Solution |
|------------|--------|----------|
| Publication sans abonné | Commande « silencieusement ignorée » | Vérification `/rosapi/subscribers` |
| Mode auto (`control_state: 30`) | `cmd_vel` ignoré en téléop | `change_location_mode` avant nav/téléop |
| Annulation navigation | `/path_follower/cancel` seul insuffisant | `/poi stop` + cancel service + marker stop |
| Aucun canal ROS pour TTS | Parole impossible via rosbridge | App `CybelTTSBridge` + ADB/broadcast |

### Environnement robot fermé

| Difficulté | Impact | Solution |
|------------|--------|----------|
| SSH verrouillé | Pas d'accès shell châssis | rosbridge + ADB tête uniquement |
| Application propriétaire boîte noire | Pas de doc API | Rétro-ingénierie, pas de décompilation |
| `nav_status` 604 fréquent | Visite interrompue | Affiner coordonnées `lab_tour.json` sur carte réelle |

---

## 5.6 Conclusion (chapitre 5)

La méthodologie adoptée — observation, vérification, simulation puis intégration — s'est avérée **indispensable** face à un système fermé et partiellement documenté. Le planning en quatre phases a été globalement respecté, avec un avance sur le déploiement tablette (phase 3) et un retard acceptable sur la validation navigation complète (phase 4). Les outils choisis (Python/FastAPI, TypeScript/Vite, rosbridge, ADB, Termux) forment un écosystème cohérent, adapté à un stage individuel et à des contraintes matérielles fortes.

---

# 6 Réalisation et implémentation

## 6.1 Mise en place de l'environnement

### Poste de développement (PC)

| Composant | Version / détail |
|-----------|------------------|
| OS | Windows 11 |
| Python | 3.13 + `pip install -r backend/requirements.txt` |
| Node.js | LTS + `npm install` dans `frontend/` et `frontend-kiosk/` |
| Android SDK | CLI (`adb`, `aapt2`, `javac`, `d8`) pour APK |
| IDE | Cursor / VS Code |
| Réseau | Connexion Wi-Fi robot `TY1251D-03195` pour tests réels |

### Lancement unifié

```powershell
cd cybel
python scripts\dev.py
# → Backend :8000, opérateur :5173, kiosque :5174
```

Configuration robot : `backend/.env` — `ROBOT_MOCK=false`, `ROBOT_HOST=10.42.0.1`.

### Environnement tablette (Termux)

- Bootstrap : `scripts/termux/bootstrap_lite.sh`
- Déploiement : `python scripts/deploy_termux.py --lite-only`
- Démarrage : `~/cybel/scripts/termux/start_cybel.sh`

---

## 6.2 Découverte et analyse du robot

### Matériel identifié

| Sous-système | Spécifications |
|--------------|----------------|
| Châssis | Linux embarqué, ROS, LiDAR, batterie 24V/20Ah |
| Upper body | Android 7.1, RK3399, 2 Go RAM, écran 15,6" tactile |
| Réseau | AP Wi-Fi `TY1251D-03195`, mot de passe documenté en interne |

### Services réseau découverts

| Port | Service |
|------|---------|
| 9090 | rosbridge WebSocket |
| 1883 | MQTT |
| 8082 | Interface déploiement constructeur |
| 8088 | Interface debug CSST |
| 21 | FTP |
| 22 | SSH (verrouillé) |

---

## 6.3 Reverse Engineering du système

### 6.3.1 Analyse réseau

```mermaid
flowchart LR
    PC[PC développeur\n10.42.0.x]
    RB[Châssis ROS\n10.42.0.1]
    AND[Tête Android\n172.16.0.x DHCP]
    ETH[Lien eth0 interne\n192.168.20.0/24]

    PC <-->|Wi-Fi AP robot| RB
    PC <-->|Wi-Fi| AND
    AND <-->|eth0| ETH
    RB <-->|eth0| ETH
```

**Découverte clé** : depuis Termux (tablette), rosbridge est joignable sur **`192.168.20.22:9090`**, pas sur `10.42.0.1`.

### 6.3.2 Identification des protocoles

1. **rosbridge v2** — canal principal (JSON sur WebSocket).
2. **MQTT** — télémétrie odométrie (`test_mul`), observation passive.
3. **HTTP** — interfaces constructeur non exploitées pour CYBEL.
4. **ADB** — accès tête Android pour TTS.

### 6.3.3 Étude des commandes

| Action | Mécanisme validé |
|--------|------------------|
| Téléopération | `/mobile_base/commands/velocity` (mode manuel requis) |
| Navigation point | Service `/poi` — `command: go` |
| Navigation coordonnée | Publication `/navi_goal` |
| Annuler navigation | `/poi stop` + `/path_follower/cancel` |
| Mode manuel/auto | Service `/change_location_mode` — `mode: 0/1` |
| Relocalisation | Service `/global_localization` |
| Parole | `am broadcast` → CybelTTSBridge (hors ROS) |

---

## 6.4 Développement du backend CYBEL

### Architecture

```mermaid
flowchart TB
    subgraph API["backend/ — FastAPI"]
        R[routers/]
        RS[robot_service.py]
        TS[tour_service.py]
        WS[websocket/manager]
    end

    subgraph SDK["sdk/"]
        RR[real_robot.py]
        MR[mock_robot.py]
        RB[rosbridge.py]
        LT[lab_tour.py]
    end

    R --> RS
    R --> TS
    RS --> RR
    RS --> MR
    RR --> RB
    TS --> LT
    RS --> WS
```

### Fonctionnalités API principales

| Domaine | Endpoints clés |
|---------|----------------|
| Robot | `/api/robot/status`, `/move`, `/stop`, `/emergency-stop`, `/relocalize` |
| Navigation | `/api/navigation/goto`, `/goto-coordinate`, `/cancel` |
| Carte | `/api/map/current` |
| Visite | `/api/tour/start`, `/stop`, `/halt`, CRUD `/stops` |
| Télémétrie | WebSocket `/ws/telemetry` |

**Tests automatisés** : 14 tests unitaires (`pytest tests/`).

---

## 6.5 Développement de l'application Android

### CybelTTSBridge

- Réception broadcast `com.cybel.ttsbridge.SPEAK`
- Initialisation `TextToSpeech` avec file d'attente (`pendingText`)
- Installée sur la tête Android du robot

### CybelVisitorKiosk

- WebView plein écran chargeant `http://<ip-tablette>:8000/kiosk/`
- `BootReceiver` pour démarrage automatique (optionnel)
- Correctifs safe-area et page d'erreur réseau

---

## 6.6 Développement de l'interface Web

### Interface opérateur (`frontend/`)

| Module | Fonction |
|--------|----------|
| Carte SLAM | Grille, LiDAR, pose, objectif, visiteurs |
| Panneau Points | Navigation, ajout/suppression points locaux |
| Téléopération | D-pad, mode manuel, arrêt |
| Page Visite | CRUD `lab_tour.json`, suivi état |
| Accueil | Actions vocales, FAQ, commande vocale |

### Interface visiteur (`frontend-kiosk/`)

- Écran accueil → visite en cours → fin / erreur
- Bascule FR/EN
- Polling `/api/tour/status` pendant la visite

---

## 6.7 Mise en place du système TTS

```mermaid
sequenceDiagram
    participant API as Backend CYBEL
    participant ADB as ADB (PC) ou broadcast (tablette)
    participant BR as CybelTTSBridge
    participant TTS as Google TTS

    API->>ADB: am broadcast SPEAK + texte
    ADB->>BR: Intent reçu
    BR->>TTS: speak(text)
    TTS-->>BR: audio haut-parleurs
```

**PC** : `sdk/speech.py` → subprocess ADB.  
**Tablette** : `speak_local()` dans `cybel_lite.py` — sans PC.

---

## 6.8 Intégration des différents modules

### Flux visite guidée (intégration bout en bout)

```mermaid
sequenceDiagram
    participant K as Kiosque tablette
    participant L as cybel_lite / FastAPI
    participant E as TourEngine
    participant R as RealRobot
    participant ROS as rosbridge

    K->>L: POST /api/tour/start
    L->>E: start(lang)
    E->>R: navigate_to_coordinate(x,y,θ)
    R->>ROS: /navi_goal + mode auto
    ROS-->>R: nav_status 602→603
    E->>L: speak(présentation)
    Note over E: Répète pour chaque arrêt
    E->>K: status completed
```

### Script de déploiement intégré

`scripts/deploy_termux.py` : build kiosque → upload SFTP → bootstrap → restart `cybel_lite`.

---

## 6.9 Conclusion (chapitre 6)

L'implémentation CYBEL couvre l'intégralité de la chaîne **du protocole robot aux interfaces utilisateur**, en passant par une API structurée et un déploiement embarqué sur tablette. L'architecture en couches (SDK / API / UI) a absorbé les évolutions (visite guidée, TTS, Termux) sans remise en cause du cœur logiciel. Le principal travail restant porte sur l'**alignement des données** (`lab_tour.json`) avec la carte SLAM réelle du laboratoire.

---

# 7 Validation, résultats et analyse critique

## 7.1 Stratégie de validation

| Niveau | Méthode | Périmètre |
|--------|---------|-----------|
| Unitaire | `pytest` (14 tests) | SDK, utils, tour, rosbridge |
| Intégration mock | `ROBOT_MOCK=true` | API + frontend sans robot |
| Intégration réelle | Tests manuels sur robot | Navigation, TTS, télémétrie |
| Acceptation terrain | Visite complète 8 arrêts | Tablette + laboratoire |

**Critères de succès visite guidée** :

1. Démarrage depuis kiosque sans erreur.
2. Robot atteint chaque coordonnée (`nav_status` → 603).
3. Annonces vocales audibles à chaque arrêt.
4. Arrêt visiteur et E-Stop opérateur fonctionnels.

---

## 7.2 Scénarios de tests

| ID | Scénario | Résultat attendu | Statut |
|----|----------|------------------|--------|
| T1 | `ping 10.42.0.1` + `robot_status.py` | Messages JSON `/robot_status` | ✅ |
| T2 | Téléop mode manuel | Robot se déplace au D-pad | ✅ |
| T3 | Navigation vers point carte | `nav_status` 602→603 | ✅ |
| T4 | Annulation navigation | Robot s'arrête, trait bleu disparaît | ✅ (après correctifs) |
| T5 | TTS via ADB | Audio audible | ✅ |
| T6 | TTS tablette (broadcast) | Audio sans PC | ✅ |
| T7 | Kiosque affiché WebView | Écran accueil CYBEL | ✅ |
| T8 | Visite 8 arrêts complète | Sans 604 | ⏳ |
| T9 | Relâcher E-Stop sans reprise nav | Robot immobile | ✅ (après correctifs) |
| T10 | `pytest tests/` | 14/14 passés | ✅ |

---

## 7.3 Résultats obtenus

### Fonctionnalités livrées

- Plateforme opérateur complète (carte, LiDAR, visiteurs, visite, accueil).
- Kiosque visiteur bilingue déployé sur tablette Termux.
- Protocole ROS documenté et intégré dans `sdk/constants.py`.
- Pont TTS Android opérationnel.
- Parcours laboratoire 8 arrêts configuré dans `data/lab_tour.json`.

### Incidents terrain documentés

| Incident | Cause | Résolution |
|----------|-------|------------|
| Erreur 604 visite | Coordonnée dans obstacle / chemin bloqué | Ajuster `lab_tour.json` |
| Handshake rosbridge timeout | Wi-Fi ou connexions saturées | Retries, pas de reload, redémarrage robot |
| Objectif conservé après annulation | Télémétrie robot non effacée | `_suppress_robot_goal` + `/poi stop` |
| Bouton Arrêt inefficace | Appelait `haltTour` au lieu de `cancel` | Correction `app.ts` |

---

## 7.4 Indicateurs de performance

| Indicateur | Valeur observée | Commentaire |
|------------|-----------------|-------------|
| **Temps de réponse** API REST | < 100 ms (hors rosbridge) | Localhost PC |
| **Temps de réponse** rosbridge connect | 2–60 s (selon Wi-Fi) | 3 × timeout 20 s max |
| **Fiabilité** connexion rosbridge | ~90 % en session stable | Dépend Wi-Fi et charge |
| **Stabilité communications** | Reconnexion auto après 25 s silence | Watchdog `real_robot.py` |
| **Fréquence télémétrie** pose | ~10 Hz | `/robot_pose` |
| **Fréquence télémétrie** LiDAR | ~25 Hz | `/scan_filter` |
| **Latence Wi-Fi** ping robot | 89–1654 ms | Variable |
| **Robustesse** navigation | Erreurs 604 sur certains arrêts | Coordonnées à calibrer |
| **Tests unitaires** | 14/14 passés | Juin 2026 |

---

## 7.5 Contributions personnelles

En tant que stagiaire HESTIM en charge du robot, les contributions principales incluent :

1. **Rétro-ingénierie complète** du protocole de communication du CIOT TY1251D — sans documentation constructeur.
2. **Conception et développement** de l'architecture CYBEL (SDK, API, deux interfaces web).
3. **Résolution du canal TTS** par développement de `CybelTTSBridge` et investigation ADB/broadcast.
4. **Déploiement embarqué** Termux + kiosque sur la tablette du robot.
5. **Conception du parcours pédagogique** laboratoire (`lab_tour.json` depuis `knowledgeV2-lab.json`).
6. **Documentation technique** exhaustive (`docs/`, scripts, diagrammes Mermaid).
7. **Correction itérative** des problèmes terrain (annulation nav, rosbridge, erreurs 604).

---

## 7.6 Difficultés rencontrées et solutions apportées

*(Synthèse — voir §5.5 pour le détail investigation)*

| Domaine | Difficulté | Solution CYBEL |
|---------|------------|----------------|
| Réseau | Multi-IP, DHCP | Documentation topologie, `ROBOT_HOST` adaptatif |
| Protocole | Commandes ignorées | Vérification abonnés ROS, modes manuel/auto |
| TTS | Aucun canal réseau | APK CybelTTSBridge |
| Tablette | FastAPI impossible Termux | `cybel_lite.py` Starlette |
| Tablette | Écran blanc WebView | Build IIFE + safe-area |
| Navigation | 604, annulation | Multi-cancel, masquage objectif |
| Dev | `--reload` sature rosbridge | `dev.py` sans reload par défaut |

---

## 7.7 Limites du projet

1. **Dépendance Wi-Fi robot** — pas de contrôle hors réseau `TY1251D-03195`.
2. **Un seul robot de test** — généralisation non garantie.
3. **Coordonnées parcours** — calibrage manuel sur carte SLAM.
4. **Pas de ROS natif** — dépendance totale à rosbridge.
5. **Android 7.1** — contraintes WebView, pas de modules ES modernes.
6. **Backend lite Termux** — sous-ensemble des fonctions opérateur.
7. **Pas de CI/CD** ni déploiement production industrialisé.
8. **Reconnaissance vocale visiteur** — non implémentée (v1).

---

## 7.8 Perspectives d'amélioration

| Priorité | Amélioration |
|----------|--------------|
| Haute | Calibrer les 8 arrêts sur carte réelle (éliminer 604) |
| Haute | Connexion rosbridge non bloquante au démarrage FastAPI |
| Moyenne | Aligner `cybel_lite.py` sur toute la logique `real_robot.py` |
| Moyenne | Tests d'intégration rosbridge simulé |
| Moyenne | Boot auto Termux (`termux-boot.sh`) |
| Basse | Sync POI robot ↔ `lab_tour.json` |
| Basse | Reconnaissance vocale visiteur (micro tablette) |
| Basse | Conteneurisation Docker pour poste opérateur dédié |

---

## 7.9 Conclusion (chapitre 7)

La validation démontre que CYBEL atteint son objectif principal : **commander et faire interagir le robot sans l'application propriétaire**. Les tests unitaires et d'intégration mock sont verts ; les tests terrain confirment téléopération, TTS, télémétrie et navigation ponctuelle. La visite guidée complète sur huit arrêts reste le **dernier jalon de validation**, conditionnée par l'affinage des coordonnées et la stabilité réseau. Les limites identifiées sont connues et documentées ; les perspectives d'amélioration constituent une feuille de route claire pour la suite du stage et une éventuelle exploitation au laboratoire HESTIM.

---

# CONCLUSION GÉNÉRALE

Le stage réalisé au sein de HESTIM sur le robot de réception CIOT TY1251D-03195 a permis de répondre à une problématique exigeante : **concevoir une plateforme tierce de commande et d'interaction en l'absence de toute documentation officielle**.

La démarche de rétro-ingénierie incrémentale, combinée à une architecture logicielle en couches et à un mode simulation, a permis de livrer en quelques semaines un système **fonctionnel et démontrable** : interface opérateur riche, visite guidée autonome du laboratoire sur tablette, synthèse vocale, et documentation technique reproductible.

Ce travail démontre qu'un robot de service « fermé » peut être intégré dans un écosystème pédagogique personnalisé, à condition d'accepter une phase d'investigation protocolaire substantielle et de maintenir une discipline stricte de validation sur le matériel réel.

Les compétences mobilisées — réseaux, ROS/rosbridge, développement full-stack, Android embarqué, robotique mobile — correspondent au profil visé par la formation en Informatique et Intelligence Artificielle à HESTIM. La suite du stage consacrera ses efforts à la **validation terrain complète du parcours** et à la rédaction finale du mémoire de soutenance.

---

# BIBLIOGRAPHIE

1. Quigley, M., Conley, K., Gerkey, B., Faust, J., Foote, T., Leibs, J., Wheeler, R., & Ng, A. Y. (2009). *ROS: an open-source Robot Operating System*. ICRA Workshop on Open Source Software.

2. Thrun, S., Burgard, W., & Fox, D. (2005). *Probabilistic Robotics*. MIT Press.

3. Siegwart, R., Nourbakhsh, I. R., & Scaramuzza, D. (2011). *Introduction to Autonomous Mobile Robots*. MIT Press.

4. OASIS. (2014). *MQTT Version 3.1.1 — OASIS Standard*. OASIS Open.

5. OWASP Foundation. *OWASP Internet of Things Top 10*. https://owasp.org/www-project-internet-of-things/

6. HESTIM Engineering & Business School. *Development of a Custom Interaction and Control System for an Android-Based Service Robot* — document de sujet de stage (Dr. Sridath Tula).

---

# WEBOGRAPHIE

1. Robot Web Tools — rosbridge_suite : https://github.com/RobotWebTools/rosbridge_suite

2. Robot Web Tools — roslibjs : https://github.com/RobotWebTools/roslibjs

3. FastAPI — documentation officielle : https://fastapi.tiangolo.com

4. Vite — documentation officielle : https://vitejs.dev

5. Pydantic — documentation : https://docs.pydantic.dev

6. Mozilla Developer Network — Web Speech API : https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API

7. Android Developers — TextToSpeech : https://developer.android.com/reference/android/speech/tts/TextToSpeech

8. Android Developers — Debug Bridge (ADB) : https://developer.android.com/tools/adb

9. Termux Wiki : https://wiki.termux.com

10. Mermaid — diagrammes as code : https://mermaid.js.org

11. Mermaid Live Editor (export PNG pour Overleaf) : https://mermaid.live

---

# ANNEXES

## Annexe A — Captures d'écran (à insérer)

| Réf. | Description | Fichier suggéré |
|------|-------------|-----------------|
| Fig. A.1 | Dashboard opérateur — mode robot réel | `captures/dashboard_operateur.png` |
| Fig. A.2 | Carte SLAM + LiDAR + trajectoire | `captures/carte_navigation.png` |
| Fig. A.3 | Panneau visite guidée (page Visite) | `captures/panneau_visite.png` |
| Fig. A.4 | Kiosque — écran d'accueil FR | `captures/kiosque_accueil.png` |
| Fig. A.5 | Kiosque — visite en cours | `captures/kiosque_running.png` |
| Fig. A.6 | Erreur navigation 604 (tablette) | `captures/erreur_604.png` |
| Fig. A.7 | App CybelVisitorKiosk sur tablette | `captures/apk_tablette.png` |

## Annexe B — Commandes utiles

```powershell
# Vérification réseau
ping 10.42.0.1
python scripts\robot_status.py

# Lancement développement
python scripts\dev.py

# Tests
python -m pytest tests/ -v

# TTS test (USB branché)
adb shell am broadcast -n com.cybel.ttsbridge/.SpeakReceiver `
  -a com.cybel.ttsbridge.SPEAK --es text "Test HESTIM"

# Déploiement tablette
python scripts\deploy_termux.py --skip-kiosk-build --lite-only --host <IP> --password <mdp>
```

```bash
# Termux (tablette)
cd ~/cybel/scripts/termux
./stop_cybel.sh && ./start_cybel.sh
curl http://127.0.0.1:8000/api/health
```

## Annexe C — Extraits de code significatifs

### C.1 Annulation navigation (`sdk/real_robot.py`)

```python
async def _cancel_navigation(self) -> None:
    # 1. Arrêt via service POI (navigation démarrée par /poi go)
    await self._client.call_service(ROS_SERVICES["poi"], {"command": "stop"})
    # 2. Annulation path follower
    await self._client.call_service(ROS_SERVICES["cancel_nav"], {})
    # 3. Publication topic cancel + arrêt vitesses
    await self._client.publish(ROS_TOPICS["cancel_nav"], {})
    await self._publish_velocity(0.0, 0.0)
```

### C.2 Publication objectif navigation

```python
await self._client.publish(ROS_TOPICS["navi_goal"], {
    "header": {"frame_id": "map"},
    "pose": {
        "position": {"x": x, "y": y, "z": 0.0},
        "orientation": {"z": math.sin(theta/2), "w": math.cos(theta/2)},
    },
})
```

### C.3 Structure d'un arrêt (`data/lab_tour.json`)

```json
{
  "id": "cnc_router",
  "equipment_fr": "Routeur CNC",
  "x": 2.72, "y": -0.83, "theta": -0.48,
  "speech_fr": "Le routeur CNC permet d'usiner...",
  "dwell_seconds": 12
}
```

## Annexe D — Diagrammes détaillés

Sources Mermaid dans `docs/Sujet de stage/diagrammes/` — exporter en PNG pour Overleaf :

| Fichier | Contenu |
|---------|---------|
| `architecture_generale_cybel.mmd` | Architecture globale |
| `architecture_couches.mmd` | Couches SDK / API / UI |
| `topologie_reseau.mmd` | Réseau robot |
| `sequence_navigation.mmd` | Navigation point nommé |
| `sequence_lab_tour.mmd` | Visite guidée |
| `sequence_tts.mmd` | Synthèse vocale |
| `sequence_telemetry.mmd` | WebSocket télémétrie |
| `sequence_tour_halt.mmd` | Arrêt total opérateur |
| `cas_utilisation_cybel.mmd` | Cas d'utilisation |
| `diagramme_classes_sdk.mmd` | Classes SDK |

Voir `diagrammes/README.md` pour la procédure d'export (Mermaid Live Editor ou `mmdc`).

## Annexe E — Documentation technique complémentaire

| Document | Chemin |
|----------|--------|
| README projet | `README.md` |
| Guide interface opérateur | `docs/INTERFACE.md` |
| Pont TTS | `docs/TTS_BRIDGE.md` |
| Kiosque visiteur | `docs/VISITOR_KIOSK.md` |
| Déploiement Termux | `docs/TERMUX_DEPLOY.md` |
| Connexion robot | `docs/ROBOT_CONNECTION.md` |
| Rapport complet (base) | `docs/Sujet de stage/rapport_stage_cybel.md` |

---

*Document généré pour intégration au rapport de stage HESTIM — Projet CYBEL, juin 2026.*
