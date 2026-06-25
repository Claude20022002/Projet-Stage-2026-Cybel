# Changelog CYBEL

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
