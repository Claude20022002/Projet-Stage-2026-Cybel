# CYBEL — Plateforme de commande pour le robot de réception CIOT TY1251D-03195

Reverse-engineering non destructif d'un robot de réception commercial fermé (châssis ROS +
tête Android), puis reconstruction d'une plateforme ouverte offrant les mêmes fonctionnalités
que l'application constructeur (voire davantage) : téléopération, navigation autonome, visite
guidée, chatbot vocal hors-ligne et reconnaissance faciale sur l'appareil.

Ce dépôt contient le SDK Python, le backend FastAPI, l'interface opérateur, le kiosque visiteur
(déployable en autonome sur la tête Android via Termux), et l'article scientifique associé
(IEEE ICRA 2027).

**Index complet de la documentation : [docs/README.md](docs/README.md)**

---

## Fonctionnalités

Statut détaillé et comparaison avec l'application constructeur :
**[FEATURES_STATUS.md](FEATURES_STATUS.md)**.

| Domaine | Fonctionnalité | Statut |
|---------|----------------|--------|
| Robot | Téléopération, navigation POI/coordonnées, visite guidée multi-arrêts | ✅ Validé terrain |
| Robot | Retour à la borne de recharge | ⚠️ Navigation vers le point de charge validée ; accostage précis non confirmé |
| Robot | Réglage du profil de vitesse (sécurité/équilibre/efficacité) | ✅ |
| Voix | Chatbot vocal hors-ligne (STT Vosk, vocabulaire fermé, mot d'éveil) | ✅ Validé terrain |
| Voix | Dialogue proactif (proposition de visite après accueil) | ✅ |
| Voix | Synthèse vocale bilingue FR/EN (locale correcte selon la langue) | ✅ |
| Vision | Reconnaissance faciale sur l'appareil (embeddings, jamais d'image transmise) | ✅ Validé terrain |
| Vision | Enrôlement de visiteur à distance depuis l'interface opérateur | ✅ |
| Kiosque | Interface visiteur tactile (accueil, sélection destination, recherche, favoris) | ✅ |
| Kiosque | Déploiement autonome sur la tête Android (Termux, sans PC) | ✅ |
| Opérateur | Dashboard, carte SLAM, téléopération, diagnostics, patrouille | ✅ |
| Opérateur | Gestion visiteurs (liste live, suppression), aide contrôleur | ✅ |
| Recherche | Méthodologie de reverse-engineering documentée, 4 hypothèses testées | ✅ Voir `paper/icra_2027/` |

---

## Démarrage rapide (développement, sans robot)

```powershell
python --version    # 3.11+
node --version      # 18+
pip install -r requirements.txt
cd frontend && npm install
cd ../frontend-kiosk && npm install
```

```powershell
# Depuis la racine du dépôt — lance backend + opérateur + kiosque ensemble
python scripts/dev.py
```

| Service | URL |
|---------|-----|
| Backend API | http://127.0.0.1:8000 |
| Interface opérateur | http://127.0.0.1:5173 |
| Kiosque visiteur | http://127.0.0.1:5174/kiosk/ |

Mode simulation par défaut (`ROBOT_MOCK=true`). Pour se connecter au robot réel, créer un
fichier **`.env` à la racine du dépôt** (pas dans `backend/`) avec au minimum :

```env
ROBOT_MOCK=false
ROBOT_HOST=10.42.0.1
ROBOT_WS_PORT=9090
```

Tests unitaires :

```powershell
python -m pytest tests/unit -q
```

---

## Démarrage sur le robot (session labo / kiosque terrain)

Procédure détaillée, pas à pas : **[docs/labo/DEMARRAGE_ET_DEPANNAGE.md](docs/labo/DEMARRAGE_ET_DEPANNAGE.md)**
(rédigée pour un contrôleur non-développeur) et **[docs/labo/TERRAIN.md](docs/labo/TERRAIN.md)**
(procédure complète avec commandes).

Résumé de l'ordre de démarrage habituel sur la tête Android du robot :

1. **Deployment Tool** (app constructeur) — vérifier que le châssis répond.
2. **Termux** — démarre le backend embarqué (`.\scripts\kiosk_test.ps1 demarrer` depuis le PC,
   ou automatique si déjà configuré au démarrage).
3. **CYBEL Accueil** — lancer l'app kiosque visiteur.
4. Si le robot ne semble pas localisé (`nav_status` bloqué, ne bouge pas alors que l'app dit
   que ça a marché) : **relocaliser depuis Deployment Tool**, pas depuis l'app CYBEL — voir
   [dépannage](#dépannage-rapide) ci-dessous.

```powershell
.\scripts\kiosk_test.ps1 demarrer     # tout enchaîner automatiquement
.\scripts\kiosk_test.ps1 status       # juste vérifier l'état
.\scripts\kiosk_test.ps1 logs         # voir ce qui se passe
```

---

## Dépannage rapide

Guide complet avec arbre de décision : **[docs/labo/DEMARRAGE_ET_DEPANNAGE.md](docs/labo/DEMARRAGE_ET_DEPANNAGE.md)**.

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| « Backend ne répond pas » dans l'app | Le moteur web (port 8001) est arrêté | `.\scripts\kiosk_test.ps1 redemarrer` |
| Toujours en panne après redémarrage | Dépendances Python manquantes sur la tablette | `.\scripts\kiosk_test.ps1 reparer` puis `demarrer` |
| L'app dit "succès" mais le robot ne bouge pas (navigation, retour borne, relocalisation) | `nav_status` bloqué sur un code inhabituel | **Ouvrir Deployment Tool** et relocaliser/déplacer manuellement — méthode fiable confirmée en direct |
| Le kiosque garde l'ancienne interface après une mise à jour | La WebView garde l'ancien code en mémoire | Forcer l'arrêt de l'app puis la relancer (pas juste redémarrer le backend) |
| Tunnel `adb forward` mort après avoir débranché/rebranché l'USB | Le tunnel ne survit pas à une reconnexion | Relancer `adb forward tcp:18001 tcp:8001` (`kiosk_test.ps1` le refait automatiquement) |
| Robot mal prononcé en anglais | — (corrigé) | Locale TTS fr/en désormais correcte de bout en bout |
| Aucune tablette détectée en USB | Câble ou autorisation débogage | Rebrancher, accepter "Débogage USB" sur la tablette |

---

## Architecture (résumé)

```
┌───────────────────────────────────────────────────────────┐
│  PC (dev/opérateur)              Tête Android (embarqué)  │
│  ┌─────────────┐                 ┌──────────────────────┐ │
│  │ backend/    │  rosbridge:9090 │ Termux (cybel_lite)   │ │
│  │ (FastAPI)   │◄───────────────►│ + CybelVisitorKiosk   │ │
│  │ frontend/   │       MQTT:1883 │ + CybelFaceBridge     │ │
│  │ (opérateur) │                 │ + CybelTTSBridge      │ │
│  └─────────────┘                 └──────────────────────┘ │
└───────────────────────────────────────────────────────────┘
                    │
                    ▼
        ┌───────────────────────────┐
        │ Châssis CIOT (ROS)        │
        │ 10.42.0.1 (Wi-Fi robot)   │
        │ 192.168.20.22 (interne)   │
        └───────────────────────────┘
```

Détails complets (protocole rosbridge, topics/services découverts, schémas) :
**[docs/ARCHITECTURE_LOGICIELLE.md](docs/ARCHITECTURE_LOGICIELLE.md)** ·
**[docs/ROBOT_CONNECTION.md](docs/ROBOT_CONNECTION.md)** ·
identifiants Wi-Fi du robot : voir [docs/labo/TERRAIN.md](docs/labo/TERRAIN.md).

## Structure du dépôt

```
cybel/
├── sdk/              # Couche robot réutilisable (rosbridge, MQTT, mock/réel)
├── backend/          # API REST + WebSocket (FastAPI)
├── frontend/         # Interface opérateur (dashboard, carte, téléop)
├── frontend-kiosk/   # Interface visiteur (kiosque tactile)
├── android/          # Apps Android embarquées (kiosque, TTS, reconnaissance faciale)
├── scripts/          # Outils de dev, déploiement Termux, reverse-engineering
├── docs/             # Documentation détaillée — voir docs/README.md
├── paper/            # Article scientifique (IEEE ICRA 2027)
└── tests/            # Tests unitaires (pytest)
```

## Documentation

**[docs/README.md](docs/README.md)** est l'index complet (session labo, kiosque, protocole
robot, conception, rapport de stage). Points d'entrée fréquents :

| Besoin | Document |
|--------|----------|
| Débuter sur le projet | [docs/guides/DEMARRAGE-RAPIDE.md](docs/guides/DEMARRAGE-RAPIDE.md) |
| Session labo / terrain | [docs/labo/TERRAIN.md](docs/labo/TERRAIN.md) |
| Kiosque visiteur (démarrage + dépannage) | [docs/labo/DEMARRAGE_ET_DEPANNAGE.md](docs/labo/DEMARRAGE_ET_DEPANNAGE.md) |
| Chatbot vocal | [docs/VOICE_CHATBOT.md](docs/VOICE_CHATBOT.md) |
| Reconnaissance faciale | [docs/FACE_PRESENCE.md](docs/FACE_PRESENCE.md) |
| Synthèse vocale (TTS) | [docs/TTS_BRIDGE.md](docs/TTS_BRIDGE.md) |
| Audit APK constructeur (JADX) | [docs/cybel-conception/AUDIT_APK_CONSTRUCTEUR.md](docs/cybel-conception/AUDIT_APK_CONSTRUCTEUR.md) |
| Historique des changements | [CHANGELOG.md](CHANGELOG.md) |

---

_Projet CYBEL — Robot CIOT TY1251D-03195 — HESTIM_
