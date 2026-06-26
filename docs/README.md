# Documentation CYBEL

Index de la documentation du projet **CYBEL** — plateforme de commande pour le robot CIOT TY1251D.

## Démarrage rapide

| Besoin | Document |
|--------|----------|
| Lancer en dev (PC) | [README racine](../README.md) § Commandes |
| Connecter le robot | [ROBOT_CONNECTION.md](ROBOT_CONNECTION.md) |
| Interface opérateur | [INTERFACE.md](INTERFACE.md) |
| **Session labo / terrain** | **[labo/TERRAIN.md](labo/TERRAIN.md)** |
| Preflight automatique | [`scripts/preflight_labo.ps1`](../scripts/preflight_labo.ps1) |

---

## Labo & terrain

Procédures sur le robot physique, sync POI, tests kiosque A/B.

| Document | Description |
|----------|-------------|
| [labo/README.md](labo/README.md) | Index section labo |
| [labo/TERRAIN.md](labo/TERRAIN.md) | **Procédure pas à pas + commandes** |
| [labo/GUIDE_CONTROLEUR_POI.md](labo/GUIDE_CONTROLEUR_POI.md) | **Formation POI → CybelVisitorKioskTest** |
| [labo/KIOSK_AB_COMPARISON.md](labo/KIOSK_AB_COMPARISON.md) | Comparaison kiosque coords vs POI |
| [SENTRYMOVE_POI_SYNC.md](SENTRYMOVE_POI_SYNC.md) | Sync POI ROS → `points.json` |

---

## Kiosque visiteur & Termux

| Document | Description |
|----------|-------------|
| [VISITOR_KIOSK.md](VISITOR_KIOSK.md) | Interface visiteur, WebView, parcours |
| [TERMUX_DEPLOY.md](TERMUX_DEPLOY.md) | Backend lite sur tablette Android |
| [TOUR_NAVIGATION.md](TOUR_NAVIGATION.md) | Moteur visite, diagnostic navigation |
| [TTS_BRIDGE.md](TTS_BRIDGE.md) | Synthèse vocale (`CybelTTSBridge`) |

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

---

## Rapport de stage (HESTIM)

| Document | Description |
|----------|-------------|
| [Sujet de stage/rapport_stage_cybel.md](Sujet%20de%20stage/rapport_stage_cybel.md) | Rapport principal |
| [Sujet de stage/chapitres_5_6_7_conclusion.md](Sujet%20de%20stage/chapitres_5_6_7_conclusion.md) | Chapitres méthodologie / validation |

---

## Scripts utiles

| Script | Usage |
|--------|-------|
| `scripts/preflight_labo.ps1` | Vérifications avant session labo |
| `scripts/sync_poi_from_robot.py` | Sync POI depuis rosbridge |
| `scripts/deploy_termux.py` | Déploiement SSH sur Termux (`--target test`) |
| `scripts/dev.py` | Backend + frontend dev local |

---

_Dernière mise à jour : juin 2026 — branche hybrid Sentrymove / kiosque POI_
