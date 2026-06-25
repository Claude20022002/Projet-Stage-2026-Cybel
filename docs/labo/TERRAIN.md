# Procédure terrain — labo CYBEL

Guide pas à pas pour une session au laboratoire avec le robot CIOT TY1251D (**branche `main`** : kiosque coords, port 8000).

> **Preflight** : `.\scripts\preflight_labo.ps1 -TabletHost <IP>`

Index labo : [README.md](README.md) · Index doc : [../README.md](../README.md)

---

## Sommaire

1. [Connexion](#1-connexion)
2. [Preflight automatique](#2-preflight-automatique)
3. [Smoke test opérateur (PC)](#3-smoke-test-opérateur-pc)
4. [Déploiement / redémarrage kiosque](#4-déploiement--redémarrage-kiosque)
5. [Validation visite guidée](#5-validation-visite-guidée)
6. [Dépannage](#6-dépannage)
7. [Variante POI (branche hybrid)](#7-variante-poi-branche-hybrid)
8. [Checklist](#8-checklist)

---

## 1. Connexion

| Action | Commande |
|--------|----------|
| Wi-Fi robot | Se connecter à `TY1251D-03195` |
| Ping châssis | `ping 10.42.0.1` |
| Ping eth0 interne | `ping 192.168.20.22` |
| IP tablette | `adb shell ip -4 addr show wlan0` |
| TTS installé | `adb shell pm list packages \| findstr cybel.ttsbridge` |

Notez **`<IP_TABLETTE>`** (ex. `172.16.0.130`, SSH port **8022**).

---

## 2. Preflight automatique

```powershell
cd C:\Users\clusa\Desktop\cybel
.\scripts\preflight_labo.ps1 -TabletHost <IP_TABLETTE>
```

Contrôles : ping, sync POI dry-run (si rosbridge joignable), health `:8000`, `lab_tour.json`, ADB.

Codes sortie : `0` OK · `1` échecs · `2` avertissements.

---

## 3. Smoke test opérateur (PC)

Voir [guides/PHASE0_DEMARRAGE.md](../guides/PHASE0_DEMARRAGE.md).

```powershell
# backend/.env : ROBOT_MOCK=false, ROBOT_HOST=10.42.0.1
python scripts/robot_status.py
python scripts/dev.py
```

Ouvrir http://127.0.0.1:5173 — carte, batterie, un déplacement test.

---

## 4. Déploiement / redémarrage kiosque

### Build frontend (si modifié)

```powershell
cd frontend-kiosk
npm run build
```

### Déployer sur Termux

```powershell
python scripts/deploy_termux.py --host <IP_TABLETTE> --lite-only
```

### Réinstaller APK (si rebuild)

```powershell
cd android\CybelVisitorKiosk
bash build.sh
adb install -r out\CybelVisitorKiosk.apk
```

### Vérifications

```powershell
curl http://<IP_TABLETTE>:8000/api/health
curl http://<IP_TABLETTE>:8000/api/tour/full
```

Redémarrage manuel :

```powershell
ssh -p 8022 u0_a92@<IP_TABLETTE> "bash ~/cybel/scripts/termux/start_cybel.sh"
```

Logs : `ssh … "tail -50 ~/cybel-uvicorn.log"`

---

## 5. Validation visite guidée

1. Ouvrir **CYBEL Accueil** sur la tablette.
2. Vérifier barre statut (réseau, batterie).
3. **Démarrer la visite** — 8 arrêts labo.
4. Noter pour chaque arrêt :

| Arrêt | Robot bouge | Bon endroit | TTS OK | Notes |
|-------|-------------|-------------|--------|-------|
| Routeur CNC | | | | |
| Station LG-10 | | | | |
| Station LG-09 | | | | |
| Extraction et soufflage | | | | |
| Poste remplissage et bouchonnage | | | | |
| Thermoformage | | | | |
| Imprimante DTF C31 XP600 | | | | |
| Sérigraphie | | | | |

Symptômes connus (coords) : parle sans bouger, mauvaise destination, lenteur au départ → voir [TOUR_NAVIGATION.md](../TOUR_NAVIGATION.md).

---

## 6. Dépannage

| Problème | Action |
|----------|--------|
| Backend down | `bash ~/cybel/scripts/termux/start_cybel.sh` |
| Écran blanc WebView | Vérifier `frontend-kiosk/dist`, regénérer URL : `start_cybel.sh` |
| Pas de voix | `CybelTTSBridge` + `SPEECH_LOCAL_BROADCAST=true` |
| rosbridge HS | `ping 192.168.20.22`, relocaliser via Sentrymove |
| Arrêt urgence | Opérateur : `POST /api/tour/halt` |

---

## 7. Variante POI (branche hybrid)

Test A/B coords vs POI Sentrymove — **non inclus dans `main`** :

```powershell
git checkout feature/hybrid-sentrymove-kiosk
```

Puis suivre [KIOSK_AB_COMPARISON.md](KIOSK_AB_COMPARISON.md) et [06-plan-hybride](../cybel-conception/06-plan-hybride-sentrymove-kiosk.md).

---

## 8. Checklist

- [ ] Wi-Fi robot + preflight OK
- [ ] `deploy_termux.py` ou backend déjà actif
- [ ] `curl …8000/api/health` OK
- [ ] CybelTTSBridge installé
- [ ] Visite 8 arrêts testée / fiche remplie
