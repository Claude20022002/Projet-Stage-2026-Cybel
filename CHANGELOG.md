# Changelog CYBEL

## [0.3.4] — 2026-07-14

### Reconnaissance faciale — scaffolding (branche `feature/face-presence`, phase 2)

- **App Android `CybelFaceBridge`** (nouvelle, `android/CybelFaceBridge/`) : headless
  (aucune Activity/icône), Camera2 sans preview → `android.media.FaceDetector` →
  embedding TensorFlow Lite → `POST /api/visitors/identify` (vecteur uniquement,
  jamais d'image envoyée)
- **Backend** : `sdk/visitor_utils.py` (cosine similarity, sans pydantic),
  `backend/routers/visitors.py` + `services/visitor_service.py`
  (`identify`/`enroll`/liste/suppression), persistance `data/visitors.json`
  (`sdk/persistence.py`)
- **Backend embarqué** : routes miroir dans `scripts/termux/cybel_lite.py` +
  diffusion WebSocket `{type: "visitor"}`
- **Kiosque** : accueil personnalisé (« Bonjour M./Mme X ») dans
  `frontend-kiosk`, se greffant sur le déclencheur de présence Phase 1
- **Config** : `face_recognition_threshold` (défaut 0.82, réglable via
  `PUT /api/kiosk/config` sans rebuild APK) ; correctif cohérence
  `backend/routers/kiosk.py` vs `cybel_lite.py` (clés `presence_*`/
  `face_recognition_*` manquantes côté PC)
- **Enrôlement** : `scripts/termux/enroll_visitor.sh`, déclenché par le
  personnel uniquement (jamais de capture automatique d'un visiteur non
  consentant)
- **Tests** : `test_visitor_utils.py`, `test_visitors_router.py` (+ extension
  `test_persistence.py`, `test_kiosk_config.py`) — matching backend vérifié
  par tests unitaires et par un test manuel HTTP réel
- **Non validé** : pipeline caméra/détection/embedding sur tablette physique
  (pas d'accès terrain depuis l'environnement de dev) — aucun modèle
  `.tflite` n'est fourni (provenance de licence/dataset des modèles publics
  souvent floue) ; voir [docs/FACE_PRESENCE.md](docs/FACE_PRESENCE.md) et
  [android/CybelFaceBridge/README.md](android/CybelFaceBridge/README.md)

## [0.3.3] — 2026-06-27

### POI laboV2 — alignement Deployment Tool

- **Élagage POI obsolètes** : `LG-10`, `LG-09`, `GAMME-CONTROLE-QUALITE` (liste noire `OBSOLETE_POI_NAMES`)
- **Point de charge** : `POINT-RECHARGE` synchronisé depuis ROS mais exclu visite et kiosque (`is_charge_poi_name`, `kiosk_visible: false`)
- **Sync stricte** : seuls les marqueurs Deployment Tool remplacent `points.json` ; destinations kiosque limitées aux arrêts `lab_tour.json`
- **Visite guidée** : `filter_tour_by_poi()` au démarrage — ignore POI absents, obsolètes ou charge
- **Parcours** : 10 arrêts laboV2 (retrait LG-10, GAMME-CONTROLE-QUALITE)
- **Actions accueil** : noms POI laboV2 (`PORTE-LABO`, `POSTE-REMPLISSAGE-BOUCHONNAGE`)
- Doc : [docs/labo/POI_LABOV2.md](docs/labo/POI_LABOV2.md)
- Tests : `test_poi_charge.py`, `test_lab_tour_filter.py` (+28 tests POI/tour)

### Détection de présence (branche `feature/face-presence`)

- Écoute ROS `/detected_people_array` → WebSocket kiosque
- Réveil veille + TTS accueil (`presence_*` dans `kiosk_config.json`)
- Doc : [FACE_PRESENCE.md](docs/FACE_PRESENCE.md)

## [0.3.2] — 2026-06-25

### Sync POI automatique + élagage carte

- **Sync au démarrage kiosque** : `GET /api/reception/destinations` lit ROS avant d'afficher la grille
- **Sync au démarrage visite** : `POST /api/tour/start` synchronise les POI avant les prérequis navigation
- **Élagage POI fantômes** : `merge_point_dicts` / `merge_robot_points` remplacent le cache (suppression des POI absents de la carte ROS courante)
- **Tablette** : `sync_poi_from_ros_map()` dans `cybel_lite.py`
- **Backend PC** : `backend/services/poi_bootstrap.py` → `ensure_poi_synced_from_robot()`
- **Carte laboV2** : parcours 12 arrêts documenté
- Doc : [SENTRYMOVE_POI_SYNC.md](docs/SENTRYMOVE_POI_SYNC.md), [GUIDE_CONTROLEUR_POI.md](docs/labo/GUIDE_CONTROLEUR_POI.md)

## [0.3.1] — 2026-06-24

### Démarrage automatique tablette

- **CybelVisitorKiosk v1.3** : lance `ensure_cybel_backend.sh` via Termux RUN_COMMAND (repli `su`) à l'ouverture
- Écran « Démarrage du service d'accueil… » pendant l'attente health check
- `start_cybel.sh` idempotent si backend déjà actif
- `setup_termux_kiosk.sh` : `allow-external-apps` + hook Termux:Boot
- **cybel_lite** : routes kiosque v0.3 (`/api/kiosk/config`, destinations, go, robot/speech status)

## [0.3.0] — 2026-06-24

### Kiosque visiteur — refonte accueil tablette

- Nouveau design clair professionnel (lisibilité tablette, touch targets 56px+)
- Écran **veille** avec timeout configurable (`standby_timeout_seconds`)
- Barre d'état : batterie, réseau, état robot, horloge, FR/EN
- **Destinations populaires** sur l'accueil (config `featured_destinations`)
- **Recherche** de destination en temps réel
- Bouton **Assistance** (scénario `inform_waiting` + TTS)
- Écrans déplacement et arrivée avec animations CSS
- Configuration branding : `data/kiosk_config.json` + `GET /api/kiosk/config`
- Logo SVG par défaut : `frontend-kiosk/public/logo.svg`
- Documentation : `UI_AUDIT.md`, `FEATURES_STATUS.md`, `MIGRATION_PLAN.md`

### Navigation / robustesse (session précédente)

- Repli coordonnées si POI ROS indisponible
- Messages d'erreur HTTP explicites (mode manuel, E-Stop, localisation)
- Patrouille : 400 pour prérequis, 409 seulement si déjà en cours
- ADB : `SPEECH_ADB_SERIAL` vide = USB uniquement (plus de timeout Wi-Fi)

## [0.2.0] — Phases 4–6

- Kiosque destinations, knowledge, patrouille, diagnostics, TTS prioritaire
