# Écart d'état — CYBEL actuel vs constructeur

**Version :** 1.0  
**Date :** juin 2026  
**Références :** [AUDIT_APK_CONSTRUCTEUR.md](AUDIT_APK_CONSTRUCTEUR.md) · [02-cahier-des-charges-fonctionnel.md](02-cahier-des-charges-fonctionnel.md)

Ce document compare l'**état réel du dépôt CYBEL** (juin 2026) avec les fonctionnalités identifiées dans les APK constructeur `welcomepatrol` et `sentrymove`.

---

## 1. Synthèse exécutive

| Indicateur | Valeur |
|------------|--------|
| **Couverture fonctionnelle estimée** | ~45 % du périmètre v1 cible |
| **Canal ROSBridge** | ✅ Opérationnel (navigation, téléop, carte, TTS ADB) |
| **Canal MQTT backend** | ❌ Scripts seulement (`scripts/mqtt_*.py`) |
| **PostgreSQL** | ❌ Données en fichiers JSON (`data/`) |
| **Frontend cible React** | ⚠️ Implémenté en **TypeScript/Vite vanilla** (pas encore React) |
| **Kiosque visiteur** | ⚠️ Partiel (visite labo uniquement) |

### Ce que CYBEL sait déjà faire (confirmé dans le code)

| Capacité | Implémentation | Fichiers clés |
|----------|----------------|---------------|
| **Parler** | ✅ ADB → CybelTTSBridge (+ tentatives ROS/HTTP) | `sdk/speech.py`, `routers/speech.py` |
| **Se déplacer** | ✅ Téléop + nav POI + nav coordonnées | `sdk/real_robot.py`, `routers/robot.py`, `routers/navigation.py` |
| **ROSBridge** | ✅ Client WebSocket complet | `sdk/rosbridge.py`, `sdk/real_robot.py` |
| **MQTT** | ⚠️ Scripts d'exploration uniquement | `scripts/mqtt_listen_passive.py`, `scripts/mqtt_explore.py` |

---

## 2. Matrice de comparaison détaillée

Légende : ✅ Implémenté · ⚠️ Partiel · ❌ Absent · 🔲 Hors scope v1

### 2.1 Supervision et connexion

| Fonction constructeur | APK | CYBEL actuel | Écart |
|----------------------|-----|--------------|-------|
| Connexion ROSBridge | `SelfChassis.connectSelfChassis` | ✅ `RealRobot.start()`, reconnexion auto | Aligné |
| Affichage batterie | `/robot_status` | ✅ `statusBar.ts`, `_handle_status` | Aligné |
| État charge (charger) | `/robot_status` | ✅ Parsé (`charger` bool) | Affichage seulement |
| Position temps réel | `/robot_pose` | ✅ WS `/ws/telemetry` | Aligné |
| Carte SLAM | `/map` | ✅ `mapView.ts`, `get_current_map` | Aligné |
| LiDAR overlay | `/laser_data` | ✅ `/scan_filter` subscribe | Aligné |
| Détection personnes | — | ✅ `/detected_people_array` (bonus CYBEL) | Au-delà constructeur |
| Confiance localisation | `/localization_confidence` | ✅ Barre + seuil 60 % | Aligné |
| nav_status | `/navi_status` ou dans status | ⚠️ Via `/robot_status` uniquement | Pas de subscribe `/navi_status` dédié |
| Mode mock | — | ✅ `MockRobot` | Bonus CYBEL |
| MQTT télémétrie intégrée | Indirect (châssis) | ❌ Pas dans backend | **Gap majeur** |
| Multi-robot | `/robot_list` | ❌ | Absent |
| Diagnostic auto | `/self_diagnosis` | ❌ | Absent |

### 2.2 Commande et navigation

| Fonction constructeur | APK | CYBEL actuel | Écart |
|----------------------|-----|--------------|-------|
| Téléopération | `/cmd_vel_mux/input/teleop` | ✅ `controls.ts`, `move()` | Aligné |
| Nav par nom POI | `/tag_manager/navi` | ⚠️ Service `/poi` (pas `/tag_manager/navi`) | Service ROS différent |
| Nav par coordonnées | `/navi_goal` publish | ✅ `navigate_to_coordinate` | Aligné |
| Annulation navigation | `/move_base/cancel` | ⚠️ `/path_follower/cancel` | Topic différent |
| Soft e-stop | `/soft_stop` | ✅ `emergency_stop()` | À valider topic exact |
| Relocalisation | `/global_locate` | ⚠️ `/global_localization` | **Service ROS différent** — à valider sur robot |
| Mode manuel / auto | `NavigationHelper` | ✅ `set_manual_mode` | Aligné |
| Attente arrivée | `wait_for_navigation` | ✅ `wait_for_navigation_arrival` | Aligné |
| Vérif carte avant nav | — | ✅ `is_coordinate_navigable` | Bonus CYBEL |
| Nav inter-étages | `/cross_floor_navi` | ❌ | **Gap** |
| Ascenseur | `/lift_control/*` | ❌ | **Gap** |

### 2.3 POI et carte

| Fonction constructeur | APK | CYBEL actuel | Écart |
|----------------------|-----|--------------|-------|
| Liste marqueurs | `get_markers` | ✅ `/marker_manager/get_markers_details` | Aligné |
| CRUD POI | Realm + ROS | ⚠️ API add/delete, sync ROS partielle | Pas de PostgreSQL |
| Types POI (charge, ascenseur…) | `DeploymentToolConstant` | ⚠️ `MARKER_TYPE_MAP` basique | Types incomplets |
| Import USB `ServiceRobot/` | `NavigationConfig` | ❌ | Absent |
| Scan SLAM | `/bag_record` | ❌ | Absent (SentryMove) |
| Édition carte | `/layered_map_manager/pencil_op` | ❌ | Absent |
| Murs virtuels | `/virtual_wall_manager` | ❌ | Absent |
| Upload/download cartes | `/upload_maps` | ❌ | Absent |

### 2.4 Voix

| Fonction constructeur | APK | CYBEL actuel | Écart |
|----------------------|-----|--------------|-------|
| TTS local Iflytek | `RobotSpeechManager` | ⚠️ ADB CybelTTSBridge (autre stack) | Fonctionnel mais différent |
| TTS sur événements | `WelcomeManager` | ⚠️ Tour + réception partiels | Pas d'accueil automatique visage |
| Reconnaissance vocale | `IflytekAnalyzeManager` | ⚠️ Web Speech API navigateur | Expérimental, pas Iflytek |
| Sémantique → navigation | `SpeechNavigationManager` | ⚠️ `knowledge.py` + `voice_command` | JSON local, pas cloud |
| Commandes vocales grammaires | `TC_MOVE`, etc. | ❌ | Absent |
| Broadcast MCU `com.sunbo.McuCommand` | `startSpeakFromBrodcast` | ❌ | Non exploré |
| SROS `CONTROL_VOICE_BROADCAST` | TCP 28888 | ❌ | Non requis |

### 2.5 Accueil, réception, visite

| Fonction constructeur | APK | CYBEL actuel | Écart |
|----------------------|-----|--------------|-------|
| Écran accueil visiteur | `HomeFragment`, kiosk | ⚠️ `frontend-kiosk` visite labo | Périmètre réduit |
| Menu destinations | `CompanyListFragment` | ⚠️ Arrêts tour labo | Pas d'annuaire entreprises |
| Enregistrement visiteur | `RegisterVisitorFragment` | ❌ | Absent |
| Accueil automatique visage | `WelcomeManager.onFindFace` | ❌ | Absent |
| Visite guidée multi-arrêts | `NavGuideFragment`, `PatrolTask` | ✅ `TourEngine`, `tour_service.py` | **Bien couvert** |
| Halt / reprise visite | — | ✅ `halt_tour`, relocalisation | Bonus CYBEL |
| Trace JSON visite | — | ✅ `tour_trace.py` | Bonus CYBEL |
| Actions réception prédéfinies | `WelcomeManager` | ⚠️ `reception_service.py` (5 actions) | Partiel |
| FAQ / knowledge | `WuhanApiService` | ✅ `knowledgeV2-lab.json` | Local, pas cloud |
| Contenu CMS dynamique | HTTP cloud | ❌ JSON statique | Remplacement acceptable |

### 2.6 Patrouille

| Fonction constructeur | APK | CYBEL actuel | Écart |
|----------------------|-----|--------------|-------|
| Tâche patrouille | `PatrolTask`, Realm | ❌ | Absent — réutilisable via tour |
| Modes cycle / aléatoire | `PatrolMode` | ❌ | Absent |
| Annonces sur points patrouille | `BroadcastTask` | ⚠️ Tour stops avec speech | Modèle proche, pas dédié |
| Sync patrouille cloud | SROS + HTTP | ❌ | Non requis |

### 2.7 Énergie et recharge

| Fonction constructeur | APK | CYBEL actuel | Écart |
|----------------------|-----|--------------|-------|
| Affichage batterie % | `/robot_status` | ✅ | Aligné |
| Seuil batterie basse | `SP_LOW_BATTERY_CHARGE` | ❌ Pas de logique auto | **Gap** |
| Retour borne automatique | `lowPowerBack2ChargePile` | ❌ | **Gap critique** |
| Retour borne manuel | `sendGoHome` | ❌ | **Gap** |
| Service recharge | `/start_recharge` | ❌ | Absent |
| Topics charge | `/charge_server/*` | ❌ | Absent |

### 2.8 Configuration et persistance

| Fonction constructeur | APK | CYBEL actuel | Écart |
|----------------------|-----|--------------|-------|
| SharedPreferences | `MySpUtils` | ⚠️ `RobotSettings` en mémoire + `.env` | Pas persisté en BDD |
| Realm local | `RobotControlService.realm` | ❌ Fichiers JSON | **Gap architecture** |
| PostgreSQL | — | ❌ Cible non implémentée | **Gap majeur** |
| Config URL WebSocket | `NAVIGATION_X86_URL` | ✅ `.env` `ROBOT_HOST` | Aligné |
| Config ADB TTS | — | ✅ `.env` `SPEECH_ADB_SERIAL` | Aligné |
| Boot auto | `BootBroadcastReceiver` | ❌ | Hors scope web |

### 2.9 Cloud constructeur (SROS / HTTP)

| Fonction | APK | CYBEL | Décision |
|----------|-----|-------|----------|
| TCP SROS :28888 | `TcpService` | ❌ | Non requis v1 |
| HTTP Wuhan CMS | `RetrofitManager` | ❌ | Remplacé par JSON local |
| Sync employés / visiteurs cloud | SROS messages | ❌ | Non requis v1 |

### 2.10 Stack technique cible vs réel

| Composant cible | État réel juin 2026 | Écart |
|-----------------|---------------------|-------|
| React frontend | TypeScript/Vite **vanilla DOM** | Migration React à planifier |
| FastAPI backend | ✅ v0.2.0 | Conforme |
| ROSBridge | ✅ SDK complet | Conforme |
| MQTT backend | Scripts seulement | Intégration à faire |
| PostgreSQL | Absent (`data/*.json`) | Migration à faire |

---

## 3. Fonctionnalités déjà implémentées

### 3.1 Liste validée (avec preuves code)

| # | Fonctionnalité | Module CYBEL | Référence constructeur couverte |
|---|----------------|--------------|-------------------------------|
| 1 | Connexion ROSBridge + reconnexion auto | `sdk/real_robot.py` | `SelfChassis` |
| 2 | Télémétrie temps réel (WS) | `backend/main.py`, `telemetry.ts` | `SelfChassisListener` |
| 3 | Affichage carte + pose robot | `mapView.ts` | `MapRlView` (SentryMove) |
| 4 | Overlay LiDAR | `real_robot.py` | `/laser_data` |
| 5 | Téléopération clavier | `controls.ts` | `MsgManager.velocityMsg` |
| 6 | Navigation vers POI | `navigate_to_point` → `/poi` | `sendMoveByMarkerName` |
| 7 | Navigation coordonnées | `navigate_to_coordinate` → `/navi_goal` | `sendGoalMsg` |
| 8 | Annulation navigation | `_cancel_navigation` | `sendCancelMove` |
| 9 | E-stop logiciel | `emergency_stop` | `sendEStop` |
| 10 | Relocalisation globale | `global_localization` | `global_locate` (service différent) |
| 11 | Liste / ajout / suppression POI | `routers/navigation.py` | `insertMarker`, `deleteMarker` |
| 12 | Synthèse vocale (ADB) | `sdk/speech.py` | `RobotSpeechManager` |
| 13 | Visite guidée complète | `sdk/lab_tour.py`, `tour_service.py` | `PatrolTask`, `NavGuideFragment` |
| 14 | Halt / reprise visite | `tour_service.halt` | — (bonus) |
| 15 | Trace diagnostic visite | `sdk/tour_trace.py` | — (bonus) |
| 16 | Actions réception | `reception_service.py` | `WelcomeManager` (partiel) |
| 17 | FAQ sémantique locale | `knowledge.py`, JSON | `SemanticHelper` (partiel) |
| 18 | Kiosque visite labo | `frontend-kiosk/` | `HomeFragment` (partiel) |
| 19 | Mode mock développement | `sdk/mock_robot.py` | — (bonus) |
| 20 | Détection personnes | `/detected_people_array` | — (bonus) |
| 21 | Vérification navigabilité carte | `map_utils.is_coordinate_navigable` | — (bonus) |
| 22 | Tests unitaires SDK | `tests/unit/` (11 fichiers) | — (bonus) |

### 3.2 APIs REST exposées aujourd'hui

| Endpoint | Fonction |
|----------|----------|
| `GET /api/health` | Santé backend |
| `GET /api/robot/status` | État robot |
| `GET /api/robot/pose` | Position |
| `POST /api/robot/move` | Téléop |
| `POST /api/robot/stop` | Arrêt mouvement |
| `POST /api/robot/emergency-stop` | E-stop |
| `POST /api/robot/relocalize` | Relocalisation |
| `GET/POST/DELETE /api/navigation/points` | CRUD POI |
| `POST /api/navigation/goto` | Nav POI |
| `POST /api/navigation/goto-coordinate` | Nav coords |
| `POST /api/navigation/cancel` | Annulation |
| `GET /api/map` | Carte courante |
| `POST /api/speech/say` | TTS |
| `GET/POST /api/tour/*` | Visite guidée |
| `GET/POST /api/reception/*` | Réception |
| `GET /api/knowledge/faq` | FAQ |
| `WS /ws/telemetry` | Temps réel |

### 3.3 Topics ROS utilisés aujourd'hui

| Topic / Service | Usage CYBEL | Usage APK |
|---------------|-------------|-----------|
| `/robot_pose` | Subscribe | Subscribe |
| `/robot_status` | Subscribe | Subscribe |
| `/localization_confidence` | Subscribe | Subscribe |
| `/get_current_map` | Subscribe | Subscribe |
| `/scan_filter`, `/scan` | Subscribe LiDAR | `/laser_data` |
| `/detected_people_array` | Subscribe | — |
| `/navi_goal` | Publish (nav coords) | Publish |
| `/poi` | Call service (nav POI) | `/tag_manager/navi` |
| `/marker_manager/get_markers_details` | Call service | `/marker_operation/get_markers` |
| `/marker_manager/control` | Add point | `tag_manager/control` |
| `/global_localization` | Relocalisation | `/global_locate` |
| `/path_follower/cancel` | Annulation | `/move_base/cancel` |
| `/mobile_base/commands/velocity` | Téléop (via publish) | `/cmd_vel_mux/input/teleop` |

---

## 4. Fonctionnalités manquantes

### 4.1 Manques critiques (bloquent parité usage réel)

| # | Fonctionnalité | Référence APK | Impact |
|---|----------------|---------------|--------|
| M-01 | **Retour automatique en charge** | `WelcomeManager.lowPowerBack2ChargePile` | Robot peut s'éteindre en session |
| M-02 | **Retour borne manuel** | `SelfChassis.sendGoHome` | Pas de fin de journée autonome |
| M-03 | **Intégration MQTT backend** | Broker `:1883` | Télémétrie incomplète, bus événements absent |
| M-04 | **PostgreSQL** | Realm → PG | Pas de persistance métier durable |
| M-05 | **Alignement services ROS** | `/tag_manager/navi`, `/global_locate` | Risque échec navigation selon firmware |
| M-06 | **Téléop topic** | `/cmd_vel_mux/input/teleop` | Topic velocity potentiellement incorrect |

### 4.2 Manques importantes (parité fonctionnelle)

| # | Fonctionnalité | Référence APK |
|---|----------------|---------------|
| M-07 | Patrouille dédiée (hors tour) | `PatrolTask`, `SetPatrolFragment` |
| M-08 | Kiosque accueil générique (destinations POI) | `VisitorFragment`, `CompanyListFragment` |
| M-09 | Accueil automatique (proximité / visage) | `WelcomeManager.onFindFace` |
| M-10 | Navigation inter-étages | `crossFloorNavi` |
| M-11 | Ascenseur | `ElevatorDialog`, `/lift_control/*` |
| M-12 | Historique navigation / sessions | Realm stats |
| M-13 | Seuils et alertes batterie configurables | `SP_LOW_BATTERY_CHARGE` |
| M-14 | Migration frontend → React | Architecture cible |
| M-15 | Types POI complets (charge=11, ascenseur=4…) | `DeploymentToolConstant` |
| M-16 | Subscribe `/navi_status` dédié | `NavigationManager` |

### 4.3 Manques optionnelles (hors labo / v2)

| # | Fonctionnalité | Référence APK |
|---|----------------|---------------|
| M-17 | Cartographie SLAM | `MainPresenter.createMap` (SentryMove) |
| M-18 | Édition carte / murs virtuels | `SetEditMap`, `/virtual_wall_manager` |
| M-19 | Reconnaissance faciale | `FaceResultFragment` |
| M-20 | Reconnaissance vocale Iflytek | `IflytekAnalyzeManager` |
| M-21 | Enregistrement visiteur | `RegisterVisitorFragment` |
| M-22 | Multi-robot | `ScheduleFragment`, `/robot_list` |
| M-23 | Appel vidéo | LinPhone |
| M-24 | Publicité plein écran | `com.ciot.ads` |
| M-25 | Sync cloud SROS/HTTP | `TcpService`, `WuhanApiService` |
| M-26 | Import USB `ServiceRobot/` | `NavigationConfig.IMPPORT_DATA_DIR` |
| M-27 | Diagnostic matériel auto | `DiagnosisFragment` |

---

## 5. Fonctionnalités critiques à développer en priorité

Classement basé sur : risque opérationnel, effort/coût, dépendances, valeur pour le labo HESTIM.

```mermaid
quadrantChart
    title Priorisation (impact vs effort)
    x-axis Effort faible --> Effort élevé
    y-axis Impact faible --> Impact élevé
    quadrant-1 Faire en premier
    quadrant-2 Planifier
    quadrant-3 Quick wins
    quadrant-4 Reporter
    Alignement ROS services: [0.25, 0.85]
    Retour charge: [0.35, 0.90]
    MQTT backend: [0.45, 0.75]
    PostgreSQL: [0.70, 0.80]
    Kiosque POI: [0.40, 0.70]
    Patrouille: [0.50, 0.55]
    Multi-étages: [0.85, 0.40]
    SLAM: [0.90, 0.30]
```

### Priorité P0 — Critique (sprint immédiat)

| Rang | Fonctionnalité | Justification | Effort estimé |
|------|----------------|---------------|---------------|
| **P0-1** | Valider et aligner services ROS (`/tag_manager/navi`, `/global_locate`, `/cmd_vel_mux/input/teleop`) | Écarts constants.py vs APK peuvent casser la nav en production | 2–3 j |
| **P0-2** | Retour borne + `/start_recharge` | Autonomie robot ~8 h, risque panne batterie | 3–5 j |
| **P0-3** | Alerte batterie basse + seuil configurable | Prérequis recharge auto | 1–2 j |

### Priorité P1 — Importante (sprint suivant)

| Rang | Fonctionnalité | Justification | Effort estimé |
|------|----------------|---------------|---------------|
| **P1-1** | `MqttBridgeService` intégré au backend | Contrainte architecture + télémétrie complémentaire | 3–5 j |
| **P1-2** | PostgreSQL + migration données JSON | Contrainte architecture, base pour tout le métier | 5–8 j |
| **P1-3** | Kiosque : sélection destination depuis POI BDD | Parité accueil visiteur WelcomePatrol | 3–5 j |
| **P1-4** | Module patrouille (réutiliser TourEngine) | Patrouille = cas d'usage constructeur clé | 3–5 j |
| **P1-5** | Historique `navigation_events` + `speech_log` | Supervision et debug sessions | 2–3 j |

### Priorité P2 — Amélioration (backlog)

| Rang | Fonctionnalité | Effort estimé |
|------|----------------|---------------|
| P2-1 | Migration frontend vanilla TS → React | 8–15 j |
| P2-2 | Navigation inter-étages + ascenseur | 10–15 j |
| P2-3 | Accueil automatique (capteur présence / caméra) | 8–12 j |
| P2-4 | Cartographie SLAM (outil technicien) | 15–20 j |
| P2-5 | Reconnaissance vocale avancée | 10+ j |

---

## 6. Tableau de couverture par module

| Module | Constructeur | CYBEL | Couverture |
|--------|--------------|-------|------------|
| Supervision | 10 fonctions | 7 | **70 %** |
| Commande / navigation | 10 fonctions | 7 | **70 %** |
| Voix | 6 fonctions | 2 | **33 %** |
| Accueil / visite | 8 fonctions | 4 | **50 %** |
| POI / carte | 8 fonctions | 4 | **50 %** |
| Patrouille | 4 fonctions | 1 | **25 %** |
| Énergie | 5 fonctions | 1 | **20 %** |
| Configuration | 5 fonctions | 2 | **40 %** |
| Persistance | Realm + SP | JSON fichiers | **15 %** |
| MQTT | Indirect chassis | Scripts only | **10 %** |
| Cloud constructeur | 5 fonctions | 0 | **0 %** (volontaire) |

**Couverture globale pondérée (périmètre v1 labo) : ~45 %**

---

## 7. Écarts techniques précis à corriger

### 7.1 `sdk/constants.py` vs APK `TopicContent` / `ServiceContent`

| Constante CYBEL | Valeur actuelle | Valeur APK recommandée | Action |
|-----------------|-----------------|------------------------|--------|
| `ROS_SERVICES["poi"]` | `/poi` | `/tag_manager/navi` | Tester les deux, prioriser APK |
| `ROS_SERVICES["global_localization"]` | `/global_localization` | `/global_locate` | Valider sur robot labo |
| `ROS_TOPICS["velocity_cmd"]` | `/mobile_base/commands/velocity` | `/cmd_vel_mux/input/teleop` | Corriger téléop |
| `ROS_SERVICES["cancel_nav"]` | `/path_follower/cancel` | `/move_base/cancel` | Tester les deux |
| Topics manquants | — | `/navi_status`, `/charge_server/*`, `/cross_floor_navi` | Ajouter à constants.py |

### 7.2 Persistance actuelle (à migrer vers PostgreSQL)

| Fichier actuel | Contenu | Table PG cible |
|----------------|---------|----------------|
| `data/lab_tour.json` | Visite guidée | `tours`, `tour_stops` |
| `data/knowledgeV2-lab.json` | FAQ sémantique | `knowledge_entries` |
| `data/hestim_knowledge_base.json` | Base connaissance | `knowledge_entries` |
| POI en mémoire robot | Marqueurs ROS | `points` |
| `.env` / `RobotSettings` | Config | `settings` |
| `tour_trace` logs | Traces JSON | `navigation_events` |

---

## 8. Forces compétitives CYBEL (au-delà du constructeur)

Fonctionnalités que CYBEL possède **sans équivalent direct** dans l'APK accueil :

| Force CYBEL | Description |
|-------------|-------------|
| Interface web distante | Opérateur sur PC, pas lié à la tablette |
| Mode mock | Développement sans robot |
| Trace visite JSON | Diagnostic post-mortem navigation |
| Halt / reprise visite | Gestion erreur 604 structurée |
| Vérification navigabilité | Refus nav vers obstacle/hors carte |
| Détection personnes | Affichage présence sur carte |
| Stack ouverte | SDK Python, API REST documentée |
| Indépendance cloud | Pas de compte CIOT requis |

---

## 9. Recommandation stratégique

### Court terme (avant mise en production labo)

1. Corriger les **écarts ROS** (P0-1) — risque technique immédiat.
2. Implémenter **recharge** (P0-2, P0-3) — risque matériel.
3. Ne pas bloquer sur React : le frontend vanilla TS est **fonctionnel** ; migration React en P2.

### Moyen terme (parité accueil)

4. PostgreSQL + kiosque POI (P1-2, P1-3).
5. MQTT backend (P1-1).
6. Patrouille (P1-4).

### Long terme (si déploiement multi-étages)

7. Ascenseur / cross-floor (P2-2).
8. SLAM technicien (P2-4) — seulement si CYBEL remplace aussi SentryMove.

---

*Document suivant prévu : [05-backlog.md](05-backlog.md) — sur validation client.*
