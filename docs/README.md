# Documentation CYBEL

Index de la documentation du projet **CYBEL** — plateforme de commande pour le robot CIOT TY1251D-03195.

> Carte complète de l'organisation : [STRUCTURE.md](STRUCTURE.md)

## Démarrage rapide

| Besoin | Document |
|--------|----------|
| Lancer en dev (PC) | [README racine](../README.md) § Commandes |
| **Kiosque tablette (lundi / panne)** | **[labo/DEMARRAGE_ET_DEPANNAGE.md](labo/DEMARRAGE_ET_DEPANNAGE.md)** + `scripts/kiosk_test.ps1` |
| Connecter le robot | [ROBOT_CONNECTION.md](ROBOT_CONNECTION.md) |
| Interface opérateur | [INTERFACE.md](INTERFACE.md) |
| **Session labo / terrain** | **[labo/TERRAIN.md](labo/TERRAIN.md)** |
| Preflight automatique | [`scripts/preflight_labo.ps1`](../scripts/preflight_labo.ps1) |
| Smoke test matin (PC + robot) | [PHASE0_DEMARRAGE.md](PHASE0_DEMARRAGE.md) |
| Débuter sur le projet | [guides/DEMARRAGE-RAPIDE.md](guides/DEMARRAGE-RAPIDE.md) |

---

## Labo & terrain

Procédures sur le robot physique, sync POI, tests kiosque A/B.

| Document | Description |
|----------|-------------|
| [labo/README.md](labo/README.md) | Index section labo |
| [labo/TERRAIN.md](labo/TERRAIN.md) | **Procédure pas à pas + commandes** |
| [labo/DEMARRAGE_ET_DEPANNAGE.md](labo/DEMARRAGE_ET_DEPANNAGE.md) | **Démarrage kiosque TEST (contrôleur)** |
| [labo/GUIDE_CONTROLEUR_POI.md](labo/GUIDE_CONTROLEUR_POI.md) | **Formation POI → CybelVisitorKioskTest** |
| [labo/KIOSK_AB_COMPARISON.md](labo/KIOSK_AB_COMPARISON.md) | Comparaison kiosque coords vs POI |
| [SENTRYMOVE_POI_SYNC.md](SENTRYMOVE_POI_SYNC.md) | Sync POI ROS → `points.json` |
| [COLLECTE_MESURES.md](COLLECTE_MESURES.md) | **Campagnes de mesures : lancement, wake lock, dépannage des coupures** |

---

## Kiosque visiteur & Termux

| Document | Description |
|----------|-------------|
| [VISITOR_KIOSK.md](VISITOR_KIOSK.md) | Interface visiteur, WebView, parcours |
| [TERMUX_DEPLOY.md](TERMUX_DEPLOY.md) | Backend lite sur tablette Android |
| [TOUR_NAVIGATION.md](TOUR_NAVIGATION.md) | Moteur visite, diagnostic navigation |
| [TTS_BRIDGE.md](TTS_BRIDGE.md) | Synthèse vocale (`CybelTTSBridge`) |
| [VOICE_CHATBOT.md](VOICE_CHATBOT.md) | Chatbot vocal (STT, mot d'éveil, dialogue de visite) |
| [FACE_PRESENCE.md](FACE_PRESENCE.md) | Reconnaissance faciale, détection de présence |

---

## Robot & protocole

| Document | Description |
|----------|-------------|
| [ROBOT_CONNECTION.md](ROBOT_CONNECTION.md) | Topologie réseau, IPs, rosbridge |
| [movement-audit/](movement-audit/) | Audit communication ROS/MQTT |
| [cybel-conception/AUDIT_APK_CONSTRUCTEUR.md](cybel-conception/AUDIT_APK_CONSTRUCTEUR.md) | Audit APK constructeur (JADX) |

---

## Conception produit

| Document | Description |
|----------|-------------|
| [cybel-conception/README.md](cybel-conception/README.md) | Index conception + backlog agent |
| [cybel-conception/06-plan-hybride-sentrymove-kiosk.md](cybel-conception/06-plan-hybride-sentrymove-kiosk.md) | Stratégie hybride Sentrymove |
| [ARCHITECTURE_LOGICIELLE.md](ARCHITECTURE_LOGICIELLE.md) | SDK, backends, flux de données |

---

## Rapport de stage (HESTIM)

| Document | Description |
|----------|-------------|
| [Sujet de stage/rapport_stage_cybel.md](Sujet%20de%20stage/rapport_stage_cybel.md) | Rapport principal |
| [Sujet de stage/chapitres_5_6_7_conclusion.md](Sujet%20de%20stage/chapitres_5_6_7_conclusion.md) | Chapitres méthodologie / validation |

---

## Sections

| Section | Contenu |
|---------|---------|
| [guides/](guides/) | Démarrage dev, smoke test, prompts IA |
| [labo/](labo/) | Procédures terrain, validation navigation |
| [kiosque/](kiosque/) | Visiteur, Termux, tour, TTS |
| [robot/](robot/) | Connexion, ROS/MQTT, audit constructeur |
| [cybel-conception/](cybel-conception/) | Architecture cible, CDC, backlog, plans |
| [stage/](stage/) | Rapport de stage HESTIM (lien) |
| [archive/](archive/) | Documents constructeur, notes IA historiques |

---

## Scripts utiles

| Script | Usage |
|--------|-------|
| `scripts/dev.py` | Backend + opérateur + kiosque (dev local) |
| `scripts/preflight_labo.ps1` | Vérifications avant session labo |
| `scripts/deploy_termux.py` | Déploiement SSH sur Termux (`--target test`) |
| `scripts/sync_poi_from_robot.py` | Sync POI depuis rosbridge |
| `scripts/deploy_voice_face.sh` | Déploiement + validation chatbot vocal / reconnaissance faciale sur le kiosque |
| `scripts/robot_status.py` | Test connexion rosbridge |

---

_Dernière mise à jour : 17 juillet 2026 — fusion `feature/face-presence` (chatbot vocal, reconnaissance faciale) dans `main`_
