# Chapitre 4 — Implémentation et résultats (extrait rapport CYBEL)

> Extrait aligné sur `rapport_stage_cybel.md` §10–11, **fin juin 2026**.
> Les figures Mermaid sont dans `diagrammes/` (voir [README](diagrammes/README.md)).

## 4.1 Architecture logicielle

Trois couches : **SDK Python** (`sdk/`), **API** (FastAPI sur PC, Starlette lite sur Termux), **interfaces web** (`frontend/` opérateur, `frontend-kiosk/` visiteur).

Composants ajoutés pour la visite guidée :

- `sdk/lab_tour.py` — `TourEngine`, chargement/sauvegarde `lab_tour.json`
- `data/lab_tour.json` — parcours 8 arrêts (synthèse `knowledgeV2-lab.json`)
- `backend/routers/tour.py` — API REST tour
- `frontend/src/components/tourPanel.ts` — gestion opérateur

Figures : `architecture_couches.mmd`, `diagramme_composants.mmd`.

## 4.2 Interface opérateur

Dashboard temps réel (WebSocket) : carte SLAM, LiDAR, visiteurs, téléopération, E-STOP.

**Panneau Visite guidée** : CRUD des arrêts, suivi d'état, arrêt total relayé vers la tablette (`CYBEL_KIOSK_BACKEND_URL`).

Documentation détaillée : [docs/INTERFACE.md](../../INTERFACE.md) §5.3.1.

## 4.3 Interface visiteur (kiosque)

Application web dédiée, affichée dans `CybelVisitorKiosk` (WebView Android 7.1).

Parcours autonome : intro vocale → pour chaque arrêt (approche, navigation `/navi_goal`, présentation, pause) → conclusion.

Build **IIFE** (pas de `type="module"`) ; correctifs **safe-area** pour l'en-tête CYBEL.

Figure séquence : `sequence_lab_tour.mmd`.

Documentation : [docs/VISITOR_KIOSK.md](../../VISITOR_KIOSK.md).

## 4.4 Déploiement Termux

Backend `cybel_lite.py` sur la tablette : sert `/kiosk/` et `/api/tour/*` sans pydantic.

Déploiement : `scripts/deploy_termux.py`. Configuration : `scripts/termux/cybel.env` (`ROBOT_HOST=192.168.20.22`).

Documentation : [docs/TERMUX_DEPLOY.md](../../TERMUX_DEPLOY.md).

## 4.5 Résultats

| Livrable | Statut |
|----------|--------|
| Protocole ROS reconstruit | ✅ |
| Interface opérateur | ✅ |
| TTS (`CybelTTSBridge`) | ✅ |
| Kiosque affiché sur tablette | ✅ |
| Parcours 8 arrêts configuré | ✅ |
| Navigation terrain multi-arrêts | ⏳ Validation |

## 4.6 Diagrammes de séquence

| Flux | Fichier source |
|------|----------------|
| Navigation point nommé | `sequence_navigation.mmd` |
| TTS | `sequence_tts.mmd` |
| Télémétrie WebSocket | `sequence_telemetry.mmd` |
| Visite guidée labo | `sequence_lab_tour.mmd` |
| Arrêt total opérateur | `sequence_tour_halt.mmd` |

Exporter en PNG pour Overleaf (Mermaid Live Editor ou `mmdc`).
