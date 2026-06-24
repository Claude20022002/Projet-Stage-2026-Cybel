# Diagrammes CYBEL

**Version :** 1.0  
**Date :** juin 2026  
**Références :** [01-architecture-cible.md](01-architecture-cible.md) · [02-cahier-des-charges-fonctionnel.md](02-cahier-des-charges-fonctionnel.md)

Ce document regroupe les diagrammes de conception du produit CYBEL. Tous les diagrammes utilisent la syntaxe **Mermaid** (rendu natif dans GitHub, Cursor, VS Code).

---

## 1. Diagramme de cas d'utilisation

### 1.1 Vue globale

```mermaid
flowchart TB
    subgraph Acteurs
        VIS((Visiteur))
        OP((Opérateur))
        ADM((Administrateur))
        DEV((Mainteneur))
        SYS((Système))
    end

    subgraph CYBEL["Plateforme CYBEL"]
        subgraph Supervision["Supervision"]
            UC01[UC-01 Connexion robot]
            UC02[UC-02 Superviser état]
            UC12[UC-12 Consulter carte]
        end
        subgraph Commande["Commande"]
            UC03[UC-03 Téléopération]
            UC04[UC-04 Naviguer POI]
            UC05[UC-05 Naviguer coords]
            UC06[UC-06 Annuler navigation]
            UC07[UC-07 Relocaliser]
        end
        subgraph Voix["Voix"]
            UC08[UC-08 Faire parler]
        end
        subgraph Reception["Réception & visite"]
            UC09[UC-09 Accueillir visiteur]
            UC10[UC-10 Visite guidée]
            UC16[UC-16 Enregistrer visiteur]
        end
        subgraph Gestion["Gestion & config"]
            UC11[UC-11 Gérer POI]
            UC14[UC-14 Patrouille]
            UC15[UC-15 Configurer]
            UC19[UC-19 Historique]
        end
        subgraph Energie["Énergie"]
            UC13[UC-13 Retour charge]
        end
        subgraph Avance["Fonctions avancées"]
            UC17[UC-17 Multi-étages]
            UC18[UC-18 Cartographier]
            UC20[UC-20 Mode mock]
        end
    end

    OP --> UC01 & UC02 & UC03 & UC04 & UC05 & UC06 & UC07 & UC08 & UC10 & UC12
    VIS --> UC09 & UC16
    VIS -.-> UC10
    ADM --> UC11 & UC14 & UC15 & UC17 & UC18 & UC19
    DEV --> UC20 & UC15
    SYS --> UC13

    UC09 --> UC08
    UC10 --> UC04 & UC08
    UC14 --> UC04 & UC08
    UC13 --> UC04 & UC08
```

### 1.2 Cas d'utilisation — Réception visiteur (détail)

```mermaid
flowchart LR
    VIS((Visiteur))
    KIOSK[Kiosque React]
    API[FastAPI]
    ROB((Robot))

    VIS -->|choisit destination| KIOSK
    KIOSK -->|POST /api/reception/action| API
    API -->|TTS accueil| ROB
    API -->|navigation| ROB
    API -->|TTS arrivée| ROB
```

### 1.3 Matrice acteur × cas d'utilisation

| Cas d'usage | Visiteur | Opérateur | Admin | Mainteneur | Système |
|-------------|:--------:|:---------:|:-----:|:----------:|:-------:|
| UC-01 Connexion | | ✓ | | ✓ | |
| UC-02 Supervision | | ✓ | | ✓ | |
| UC-03 Téléop | | ✓ | | | |
| UC-04 Nav POI | | ✓ | | | ✓ |
| UC-08 TTS | | ✓ | | | ✓ |
| UC-09 Accueil | ✓ | | | | |
| UC-10 Visite guidée | ✓ | ✓ | | | |
| UC-11 Gérer POI | | | ✓ | | |
| UC-13 Retour charge | | | | | ✓ |
| UC-14 Patrouille | | ✓ | ✓ | | |
| UC-15 Config | | | ✓ | ✓ | |
| UC-17 Multi-étages | | ✓ | ✓ | | |
| UC-20 Mock | | | | ✓ | |

---

## 2. Diagrammes de séquence

### 2.1 Connexion et supervision (UC-01, UC-02)

```mermaid
sequenceDiagram
    autonumber
    participant OP as Opérateur
    participant FE as React Dashboard
    participant API as FastAPI
    participant RS as RobotService
    participant SDK as SDK real_robot
    participant ROS as ROSBridge :9090
    participant MQTT as MQTT :1883
    participant WS as WS /ws/telemetry

    OP->>FE: Ouvre application
    FE->>API: GET /api/health
    API-->>FE: { status, mock, robot_host }

    Note over API,ROS: Lifespan startup
    API->>RS: connect()
    RS->>SDK: start()
    SDK->>ROS: WebSocket connect ws://10.42.0.1:9090
    ROS-->>SDK: connected
    SDK->>ROS: subscribe /robot_status
    SDK->>ROS: subscribe /robot_pose
    SDK->>ROS: subscribe /navi_status
  opt MQTT actif
        RS->>MQTT: subscribe test_mul, #
    end

    FE->>WS: WebSocket connect
    loop Télémétrie temps réel
        ROS-->>SDK: robot_status, robot_pose
        SDK-->>RS: callback on_telemetry
        RS-->>WS: broadcast status, pose
        WS-->>FE: mise à jour UI
        MQTT-->>RS: odométrie (optionnel)
    end
    OP->>FE: Consulte batterie, position, carte
```

### 2.2 Navigation vers un POI (UC-04)

```mermaid
sequenceDiagram
    autonumber
    participant OP as Opérateur
    participant FE as React Dashboard
    participant API as FastAPI
    participant NAV as NavigationService
    participant SDK as SDK
    participant ROS as ROSBridge
    participant PG as PostgreSQL
    participant SP as SpeechService

    OP->>FE: Clic POI "Labo"
    FE->>API: POST /api/navigation/go { point_name: "Labo" }

    API->>NAV: navigate_to_point("Labo")
    NAV->>SDK: ensure_localization(min 60%)
    SDK->>ROS: call_service /global_locate
    ROS-->>SDK: localized
    SDK->>ROS: call_service /tag_manager/navi { name: "Labo" }
    NAV->>PG: INSERT navigation_events (started)

    loop Suivi navigation
        ROS-->>SDK: /navi_status (602 en cours)
        SDK-->>FE: WS telemetry
    end

    alt Arrivée réussie
        ROS-->>SDK: /navi_status (603)
        NAV->>PG: UPDATE navigation_events (arrived)
        opt Annonce activée
            NAV->>SP: speak("Nous sommes arrivés au Labo")
            SP->>SP: ADB → CybelTTSBridge
        end
        API-->>FE: 200 OK
    else Échec navigation
        ROS-->>SDK: /navi_status (604)
        NAV->>PG: UPDATE navigation_events (failed)
        API-->>FE: 422 + message relocalisation
    end
```

### 2.3 Accueil visiteur via kiosque (UC-09)

```mermaid
sequenceDiagram
    autonumber
    participant V as Visiteur
    participant K as Kiosque React
    participant API as FastAPI
    participant REC as ReceptionService
    participant SP as SpeechService
    participant NAV as NavigationService
    participant PG as PostgreSQL

    V->>K: Touche écran d'accueil
    K->>API: GET /api/reception/destinations
    API->>PG: SELECT points WHERE kiosk_visible
    API-->>K: Liste destinations

    V->>K: Sélectionne "Salle réunion"
    K->>API: POST /api/reception/action { action, destination }

    API->>REC: handle_action()
    REC->>PG: INSERT reception_sessions
    REC->>SP: speak("Bienvenue, suivez-moi")
    SP->>SP: ADB broadcast SPEAK

    REC->>NAV: navigate_to_point("Salle réunion")
    Note over NAV: Voir séquence 2.2

    NAV-->>REC: arrived
    REC->>SP: speak("Nous sommes arrivés")
    REC->>PG: UPDATE reception_sessions (completed)
    K-->>V: Écran confirmation
```

### 2.4 Visite guidée multi-arrêts (UC-10)

```mermaid
sequenceDiagram
    autonumber
    participant OP as Opérateur
    participant FE as React Tour
    participant API as FastAPI
    participant TOUR as TourService
    participant NAV as NavigationService
    participant SP as SpeechService
    participant PG as PostgreSQL

    OP->>FE: Démarrer visite "Tour labo"
    FE->>API: POST /api/tour/start { tour_id }
    API->>TOUR: start_tour()
    TOUR->>PG: SELECT tour_stops ORDER BY order

    loop Pour chaque arrêt
        TOUR->>NAV: navigate_to_point(stop.point)
        alt Navigation OK
            NAV-->>TOUR: arrived
            TOUR->>SP: speak(stop.speech_text)
            TOUR->>FE: WS tour_progress
            OP->>FE: Pause ou continuer
        else Erreur 604
            TOUR->>FE: WS tour_halted
            OP->>FE: Relocaliser puis reprendre
        end
    end

    TOUR->>NAV: goto_reception()
    TOUR->>PG: UPDATE tour_runs (completed)
    API-->>FE: Visite terminée
```

### 2.5 Synthèse vocale TTS (UC-08)

```mermaid
sequenceDiagram
    autonumber
    participant UI as Frontend
    participant API as FastAPI
    participant SP as SpeechService
    participant SDK as sdk/speech.py
    participant ADB as ADB Wi-Fi
    participant TAB as CybelTTSBridge<br/>Tablette Android

    UI->>API: POST /api/speech/speak { text }
    API->>SP: speak(text, interrupt=true)
    SP->>SDK: try ROS topic (si configuré)
    alt ROS TTS non disponible
        SDK->>ADB: adb shell am broadcast<br/>-a com.cybel.ttsbridge.SPEAK<br/>--es text "..."
        ADB->>TAB: SpeakReceiver
        TAB->>TAB: Synthèse vocale Android
    end
    SDK-->>SP: result
    SP-->>API: SpeechStatus
    API-->>UI: 200 + speaking=true
```

### 2.6 Retour charge batterie basse (UC-13)

```mermaid
sequenceDiagram
    autonumber
    participant SYS as Système
    participant RS as RobotService
    participant CHG as ChargeService
    participant SDK as SDK
    participant ROS as ROSBridge
    participant SP as SpeechService
    participant PG as PostgreSQL

    loop Surveillance
        ROS-->>RS: /robot_status (battery %)
    end

    RS->>CHG: on_battery_low(threshold)
    CHG->>SP: speak("Batterie faible, retour à la borne")
    CHG->>SDK: cancel_navigation()
    SDK->>ROS: /move_base/cancel
    CHG->>SDK: go_home()
    SDK->>ROS: publish /charge_server/home_pose
    SDK->>ROS: call_service /start_recharge
    CHG->>PG: INSERT charge_events

    alt Recharge OK
        ROS-->>SDK: /charge_server/result (success)
        CHG->>PG: UPDATE charge_events (charging)
    else Échec
        ROS-->>SDK: /charge_server/result (failed)
        CHG->>PG: UPDATE charge_events (failed)
    end
```

### 2.7 Téléopération manuelle (UC-03)

```mermaid
sequenceDiagram
    autonumber
    participant OP as Opérateur
    participant FE as controls.ts
    participant API as FastAPI
    participant RS as RobotService
    participant SDK as SDK
    participant ROS as ROSBridge

    OP->>FE: Maintient touche flèche (avant)
    FE->>API: POST /api/robot/move { linear_x: 0.2, angular_z: 0 }
    API->>RS: move(0.2, 0)
    RS->>SDK: publish velocity
    SDK->>ROS: advertise /cmd_vel_mux/input/teleop
    SDK->>ROS: publish Twist { linear.x: 0.2 }

    OP->>FE: Relâche touche
    FE->>API: POST /api/robot/stop
    SDK->>ROS: publish Twist { linear.x: 0, angular.z: 0 }
```

---

## 3. Diagramme de composants

### 3.1 Composants logiciels CYBEL

```mermaid
flowchart TB
    subgraph Presentation["Couche Présentation"]
        FE_OP["frontend/<br/>Dashboard React"]
        FE_KIOSK["frontend-kiosk/<br/>Kiosque React"]
    end

    subgraph API_Layer["Couche API — FastAPI"]
        ROUTERS["Routers REST<br/>robot · navigation · map<br/>speech · reception · tour<br/>knowledge · settings"]
        WS_MGR["WebSocket Manager<br/>/ws/telemetry"]
        LIFESPAN["Lifespan<br/>connect / disconnect"]
    end

    subgraph Services["Couche Services métier"]
        ROBOT_SVC["RobotService"]
        NAV_SVC["NavigationService"]
        SPEECH_SVC["SpeechService"]
        RECEPTION_SVC["ReceptionService"]
        TOUR_SVC["TourService"]
        PATROL_SVC["PatrolService"]
        MAP_SVC["MapService"]
        CHARGE_SVC["ChargeService"]
        ELEVATOR_SVC["ElevatorService"]
        MQTT_SVC["MqttBridgeService"]
        KNOWLEDGE_SVC["KnowledgeService"]
    end

    subgraph SDK_Layer["Couche SDK — sdk/"]
        ROSBRIDGE["rosbridge.py"]
        REAL_ROBOT["real_robot.py"]
        MOCK_ROBOT["mock_robot.py"]
        SPEECH_SDK["speech.py"]
        MQTT_SDK["mqtt_client.py"]
        CONSTANTS["constants.py"]
    end

    subgraph Persistence["Couche Persistance"]
        DB["SQLAlchemy ORM"]
        PG[("PostgreSQL")]
        ALEMBIC["Alembic migrations"]
    end

    subgraph External["Systèmes externes"]
        ROSB["ROSBridge :9090"]
        MQTT_B["MQTT :1883"]
        ADB["ADB :5555"]
        TTS_APK["CybelTTSBridge"]
    end

    FE_OP --> ROUTERS
    FE_OP --> WS_MGR
    FE_KIOSK --> ROUTERS

    ROUTERS --> Services
    LIFESPAN --> ROBOT_SVC
    WS_MGR --> ROBOT_SVC

    ROBOT_SVC --> REAL_ROBOT
    ROBOT_SVC --> MOCK_ROBOT
    NAV_SVC --> REAL_ROBOT
    MAP_SVC --> REAL_ROBOT
    CHARGE_SVC --> REAL_ROBOT
    ELEVATOR_SVC --> REAL_ROBOT
    SPEECH_SVC --> SPEECH_SDK
    MQTT_SVC --> MQTT_SDK

    REAL_ROBOT --> ROSBRIDGE
    MQTT_SDK --> MQTT_B
    SPEECH_SDK --> ROSBRIDGE
    SPEECH_SDK --> ADB
    ADB --> TTS_APK

    Services --> DB
    DB --> PG
    ALEMBIC --> PG
```

### 3.2 Composants frontend (détail)

```mermaid
flowchart LR
    subgraph frontend["frontend/ — Opérateur"]
        APP["app.ts<br/>orchestration"]
        STATE["state.ts"]
        API_TS["api.ts"]
        TELEM["telemetry.ts"]
        VOICE["voice.ts"]

        subgraph Pages
            DASH["Dashboard"]
            TOUR_P["pages/tour.ts"]
            SET_P["pages/settings.ts"]
        end

        subgraph Components
            STATUS["statusBar.ts"]
            MAP["mapView.ts"]
            CTRL["controls.ts"]
            POINTS["pointsList.ts"]
            RECEPT["receptionPanel.ts"]
            TOUR_UI["tourPanel.ts"]
        end
    end

    APP --> STATE & API_TS & TELEM
    DASH --> STATUS & MAP & CTRL & POINTS & RECEPT & TOUR_UI
    API_TS -->|HTTP| FastAPI
    TELEM -->|WS| FastAPI
```

### 3.3 Interfaces entre composants

| Composant source | Composant cible | Interface | Protocole |
|------------------|-----------------|-----------|-----------|
| `frontend/api.ts` | Routers FastAPI | REST JSON | HTTP |
| `frontend/telemetry.ts` | `ws_manager` | Événements temps réel | WebSocket |
| `RobotService` | `real_robot.py` | Méthodes async | Python |
| `real_robot.py` | `rosbridge.py` | Messages ROS | WebSocket JSON |
| `MqttBridgeService` | Broker robot | Pub/Sub | MQTT 3.1.1 |
| `SpeechService` | `speech.py` | speak(), stop() | Python + ADB |
| Services métier | SQLAlchemy ORM | CRUD | SQL / PostgreSQL |
| `frontend-kiosk/api.ts` | `reception.router` | Actions kiosk | HTTP |

---

## 4. Diagramme d'architecture

### 4.1 Architecture physique (déploiement)

```mermaid
flowchart TB
    subgraph LAN["Réseau Wi-Fi Robot 10.42.0.0/24"]
        subgraph PC["Poste opérateur"]
            BROWSER["Navigateur<br/>React :5173"]
            BACKEND["FastAPI :8000"]
            PG_SRV[("PostgreSQL<br/>:5432")]
        end

        subgraph Robot["Robot CIOT TY1251D"]
            subgraph Chassis["Châssis Linux/ROS"]
                RB["rosbridge :9090"]
                MQTT["Mosquitto :1883"]
                ROS_NODES["Nodes ROS<br/>navigation · charge · SLAM"]
            end
            subgraph Tablet["Tablette Android RK3399"]
                TTS["CybelTTSBridge<br/>172.16.0.194:5555"]
                KIOSK_TAB["Kiosque React<br/>frontend-kiosk"]
            end
        end
    end

    BROWSER <-->|HTTP + WS| BACKEND
    BACKEND <-->|SQL| PG_SRV
    BACKEND <-->|WebSocket| RB
    BACKEND <-->|MQTT| MQTT
    BACKEND <-->|ADB TCP| TTS
    KIOSK_TAB <-->|HTTP| BACKEND
    RB <--> ROS_NODES
    MQTT <--> ROS_NODES
```

### 4.2 Architecture logique (couches)

```mermaid
flowchart TB
    subgraph L1["L1 — Expérience utilisateur"]
        L1A["Dashboard opérateur"]
        L1B["Kiosque visiteur"]
    end

    subgraph L2["L2 — API & temps réel"]
        L2A["REST API"]
        L2B["WebSocket télémétrie"]
    end

    subgraph L3["L3 — Logique métier"]
        L3A["Navigation · Tour · Patrouille"]
        L3B["Réception · Voix · Charge"]
        L3C["Carte · POI · Config"]
    end

    subgraph L4["L4 — Intégration robot"]
        L4A["SDK ROSBridge"]
        L4B["SDK MQTT"]
        L4C["SDK Speech ADB"]
        L4D["Mock robot"]
    end

    subgraph L5["L5 — Données"]
        L5A["PostgreSQL"]
        L5B["Fichiers JSON knowledge"]
    end

    subgraph L6["L6 — Robot physique"]
        L6A["Châssis ROS"]
        L6B["Tablette Android"]
    end

    L1 --> L2 --> L3 --> L4 --> L6
    L3 --> L5
```

### 4.3 Architecture flux de données

```mermaid
flowchart LR
    subgraph Commandes["Flux commandes"]
        C1["UI Action"] --> C2["FastAPI Router"]
        C2 --> C3["Service métier"]
        C3 --> C4["SDK"]
        C4 --> C5["ROSBridge"]
        C5 --> C6["Robot"]
    end

    subgraph Telemetry["Flux télémétrie"]
        T1["ROS / MQTT"] --> T2["SDK callbacks"]
        T2 --> T3["RobotService"]
        T3 --> T4["WS broadcast"]
        T4 --> T5["React UI"]
        T3 --> T6["PostgreSQL<br/>snapshots optionnels"]
    end

    subgraph Config["Flux configuration"]
        CF1["Admin UI"] --> CF2["Settings API"]
        CF2 --> CF3["PostgreSQL settings"]
        CF3 --> CF4["Services au démarrage"]
    end
```

### 4.4 Comparaison architecture constructeur vs CYBEL

```mermaid
flowchart TB
    subgraph Constructeur["APK Constructeur (welcomepatrol)"]
        WP_UI["MainActivity + Fragments"]
        WP_NAV["NavigationHelper"]
        WP_SPEECH["Iflytek TTS local"]
        WP_SROS["TcpService :28888"]
        WP_ROS["SelfChassis → ROSBridge"]
        WP_REALM[("Realm local")]
        WP_CLOUD["HTTP Wuhan CMS"]
    end

    subgraph CYBEL["CYBEL (cible)"]
        CY_UI["React Dashboard + Kiosk"]
        CY_NAV["NavigationService"]
        CY_SPEECH["SpeechService → ADB"]
        CY_MQTT["MqttBridgeService"]
        CY_ROS["SDK → ROSBridge"]
        CY_PG[("PostgreSQL")]
        CY_LOCAL["JSON knowledge local"]
    end

    WP_UI -.remplacé par.-> CY_UI
    WP_NAV -.remplacé par.-> CY_NAV
    WP_SPEECH -.remplacé par.-> CY_SPEECH
    WP_ROS == même canal ==> CY_ROS
    WP_REALM -.remplacé par.-> CY_PG
    WP_CLOUD -.remplacé par.-> CY_LOCAL
    WP_SROS -.non requis.-> CY_MQTT
```

### 4.5 Topologie réseau

```mermaid
flowchart LR
    PC["PC développeur<br/>10.42.0.x"]
    CHASSIS["Châssis ROS<br/>10.42.0.1<br/>:9090 WS · :1883 MQTT"]
    TABLET["Tablette Android<br/>172.16.0.194<br/>:5555 ADB"]

    PC -->|"ROSBridge commandes"| CHASSIS
    PC -->|"MQTT télémétrie"| CHASSIS
    PC -->|"ADB TTS"| TABLET
    TABLET -.->|"réseau interne robot"| CHASSIS
```

| Hôte | IP | Ports | Rôle |
|------|-----|-------|------|
| Châssis | `10.42.0.1` | 9090, 1883 | ROSBridge, MQTT |
| Tablette | `172.16.0.194` (DHCP) | 5555 | ADB, TTS, kiosque |
| PC / serveur CYBEL | `10.42.0.x` | 8000, 5432 | Backend, PostgreSQL |
| Frontend dev | localhost | 5173 | Vite dev server |

---

## 5. Diagramme d'états — Navigation

```mermaid
stateDiagram-v2
    [*] --> Deconnecte
    Deconnecte --> Connecte : WS rosbridge OK
    Connecte --> NonLocalise : nav_status 600
    Connecte --> Pret : nav_status 601
    NonLocalise --> Pret : global_locate OK
    Pret --> EnNavigation : navigate_to_point()
    EnNavigation --> Arrive : nav_status 603
    EnNavigation --> Erreur : nav_status 604
    EnNavigation --> Pret : cancel()
    Erreur --> Pret : relocalize + retry
    Arrive --> Pret : tâche terminée
    Pret --> EnCharge : batterie basse
    EnCharge --> Pret : charge terminée
```

---

## 6. Diagramme d'états — Visite guidée

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Running : start_tour()
    Running --> AtStop : arrived
    AtStop --> Speaking : TTS
    Speaking --> Running : next stop
    Running --> Halted : nav_error 604
    Halted --> Running : resume après relocalize
    Running --> Completed : dernier arrêt
    Running --> Cancelled : stop manuel
    Completed --> Idle
    Cancelled --> Idle
```

---

## 7. Légende et conventions

| Symbole | Signification |
|---------|---------------|
| Flèche pleine | Appel / flux de données actif |
| Flèche pointillée | Relation optionnelle ou remplacement |
| `==>` | Même canal technique conservé |
| Rectangle | Composant logiciel |
| Cylindre `(())` | Base de données |
| Acteur `((...))` | Utilisateur ou système externe |

---

*Document suivant prévu : [04-ecart-etat-actuel.md](04-ecart-etat-actuel.md) — sur validation client.*
