# Documentation CYBEL

Index central de la documentation — projet **CYBEL**, plateforme de commande pour le robot CIOT **TY1251D-03195**.

> Carte complète de l'organisation : [STRUCTURE.md](STRUCTURE.md)

---

## Parcours recommandés

### Je débute sur le projet

1. [README racine](../README.md) — vue d'ensemble et protocole ROS
2. [guides/DEMARRAGE-RAPIDE.md](guides/DEMARRAGE-RAPIDE.md) — lancer en local
3. [ROBOT_CONNECTION.md](ROBOT_CONNECTION.md) — réseau et connectivité
4. [INTERFACE.md](INTERFACE.md) — interface opérateur

### Je vais au labo avec le robot

1. [`scripts/preflight_labo.ps1`](../scripts/preflight_labo.ps1) — vérifications automatiques
2. [labo/TERRAIN.md](labo/TERRAIN.md) — procédure pas à pas + commandes
3. [guides/PHASE0_DEMARRAGE.md](guides/PHASE0_DEMARRAGE.md) — smoke test matin (PC + robot)

### Je déploie le kiosque visiteur

1. [kiosque/README.md](kiosque/README.md) — index kiosque
2. [kiosque/VISITOR_KIOSK.md](kiosque/VISITOR_KIOSK.md) — interface visiteur
3. [kiosque/TERMUX_DEPLOY.md](kiosque/TERMUX_DEPLOY.md) — backend sur tablette

### Je conçois / étends le produit

1. [cybel-conception/README.md](cybel-conception/README.md) — conception et backlog
2. [cybel-conception/05-backlog.md](cybel-conception/05-backlog.md) — tâches agent IA
3. [robot/movement-audit/](robot/movement-audit/) — audit protocole mouvement

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

## Scripts opérationnels

| Script | Usage |
|--------|-------|
| `scripts/dev.py` | Backend + opérateur + kiosque (dev local) |
| `scripts/preflight_labo.ps1` | Preflight avant session labo |
| `scripts/deploy_termux.py` | Déploiement SSH sur Termux |
| `scripts/sync_poi_from_robot.py` | Sync POI (branche `feature/hybrid-sentrymove-kiosk`) |
| `scripts/robot_status.py` | Test connexion rosbridge |

---

## Branches et documentation associée

| Branche | Rôle | Doc spécifique |
|---------|------|----------------|
| **`main`** | Production stable — navigation coords `/navi_goal` | Ce index, [labo/TERRAIN.md](labo/TERRAIN.md) |
| `feature/hybrid-sentrymove-kiosk` | Expérimentation POI Sentrymove, kiosque A/B | [06-plan-hybride](cybel-conception/06-plan-hybride-sentrymove-kiosk.md), [labo/KIOSK_AB_COMPARISON.md](labo/KIOSK_AB_COMPARISON.md) |

---

_Dernière révision doc : juin 2026 — branche `main`_
