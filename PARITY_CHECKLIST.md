# Fonctionnalités WelcomePatrol — Parité CYBEL

## Interface visiteur (priorité tablette)

- [x] Écran d'accueil visiteur (refonte v0.3)
- [x] Logo entreprise (`kiosk_config.json`)
- [x] Message de bienvenue configurable
- [x] Sélection de destination (grille tactile)
- [x] Recherche de destination
- [x] Destinations favorites (accueil)
- [x] Écran de veille / attract
- [x] Écran de déplacement (animation)
- [x] Écran d'arrivée
- [x] État du robot (barre statut)
- [x] Niveau de batterie
- [x] État réseau (connecté / hors ligne)
- [x] Synthèse vocale (go destination + assistance)
- [x] Visite guidée autonome
- [x] Bascule FR / EN
- [x] Démarrage auto backend (app Accueil v1.3)
- [x] Scénarios prédéfinis complets (accueil, salle, attente visiteur)
- [x] Retour à la base (kiosque)
- [ ] Reconnaissance faciale
- [x] Détection de présence ROS → accueil kiosque (branche `feature/face-presence`, phase 1)
- [ ] Météo / média

## Opérateur & robot

- [x] Dashboard opérateur
- [x] Navigation POI / coordonnées
- [x] Destinations kiosque (`kiosk_visible`)
- [x] Sync POI auto au démarrage kiosque / visite (ROS → `points.json`, élagage carte)
- [x] Synthèse vocale
- [ ] Gestion visiteurs (enregistrement)
- [ ] Historique missions (UI)
- [x] Gestion cartes (lecture SLAM)
- [x] Patrouille (backend + UI opérateur)
- [x] Retour station (API go_home)
- [x] Paramètres avancés + diagnostics

## Documentation

- [x] UI_AUDIT.md
- [x] FEATURES_STATUS.md
- [x] MIGRATION_PLAN.md
- [x] CHANGELOG.md
