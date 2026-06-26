# Procédure terrain — labo CYBEL

Guide pas à pas pour une session au laboratoire avec le robot CIOT TY1251D : préparation POI Sentrymove, déploiement kiosque test POI, comparaison A/B avec le kiosque coords existant.

> **Vérification rapide** : exécutez d'abord le preflight automatique :
> ```powershell
> .\scripts\preflight_labo.ps1 -TabletHost <IP_TABLETTE>
> ```

---

## Sommaire

1. [Avant le labo](#1-avant-le-labo)
2. [Connexion au robot](#2-connexion-au-robot)
3. [POI dans Sentrymove](#3-poi-dans-sentrymove)
4. [Sync POI vers CYBEL](#4-sync-poi-vers-cybel)
5. [Déploiement backend test](#5-déploiement-backend-test)
6. [Installation APK test](#6-installation-apk-test)
7. [Smoke test POI](#7-smoke-test-poi)
8. [Comparaison A/B](#8-comparaison-ab)
9. [Dépannage](#9-dépannage)
10. [Checklist finale](#10-checklist-finale)

---

## 1. Avant le labo

### Branche Git (approche POI)

```powershell
cd C:\Users\clusa\Desktop\cybel
git checkout feature/hybrid-sentrymove-kiosk
git pull
```

### APK test (déjà buildable offline)

```powershell
cd android\CybelVisitorKioskTest
bash build.sh
# → android\CybelVisitorKioskTest\out\CybelVisitorKioskTest.apk
```

### Matériel

- PC + câble USB (ADB)
- Accès Wi-Fi robot `TY1251D-03195` (mot de passe constructeur)

---

## 2. Connexion au robot

| Étape | Commande |
|-------|----------|
| Ping châssis (Wi-Fi PC) | `ping 10.42.0.1` |
| Ping lien eth0 interne | `ping 192.168.20.22` |
| IP tablette Termux | `adb shell ip -4 addr show wlan0` |
| Preflight automatique | `.\scripts\preflight_labo.ps1 -TabletHost <IP>` |
| Vérifier TTS | `adb shell pm list packages \| findstr cybel` → `com.cybel.ttsbridge` |

Notez **`<IP_TABLETTE>`** (souvent `172.16.0.x`, port SSH **8022**).

---

## 3. POI dans Sentrymove

Sur la tablette : ouvrir **Deployment Tool** (`com.ciot.sentrymove`).

Carte active : **laboV2**. Créer les **12 POI** — noms **exactement** comme dans `data/lab_tour.json` :

| # | `target_point` |
|---|----------------|
| 1 | `PORTE-LABO` |
| 2 | `CNC ROUTEUR` |
| 3 | `LG-10` |
| 4 | `IMPRIMANTE 3D` |
| 5 | `POINT-MACHINE` |
| 6 | `THERMOFORMAGE` |
| 7 | `EXTRUSION-SOUFFLAGE` |
| 8 | `POSTE-MACHINE` |
| 9 | `POSTE-REMPLISSAGE-BOUCHONNAGE` |
| 10 | `POSTE-ETIQUETAGE` |
| 11 | `GAMME-CONTROLE-QUALITE` |
| 12 | `SÉRIGRAPHIE` |

**Validation** : dans Sentrymove, envoyer le robot vers **un** POI → il doit bouger correctement.

---

## 4. Sync POI vers CYBEL

### Automatique (kiosque / visite)

Depuis juin 2026, la sync se fait **sans action manuelle** à l'ouverture du kiosque ou au démarrage de la visite. Les POI d'une ancienne carte sont **retirés** du cache local.

Voir [SENTRYMOVE_POI_SYNC.md](../SENTRYMOVE_POI_SYNC.md) § « Synchronisation automatique ».

### Manuelle depuis le PC (préparation déploiement)

```powershell
cd C:\Users\clusa\Desktop\cybel

# Vérification (sans écrire)
python scripts/sync_poi_from_robot.py --host 192.168.20.22 --dry-run

# Écriture data/points.json (remplace le fichier, pas de fusion)
python scripts/sync_poi_from_robot.py --host 192.168.20.22
```

Si `192.168.20.22` ne répond pas depuis le PC :

```powershell
python scripts/sync_poi_from_robot.py --host 10.42.0.1 --dry-run
```

Contrôle : les 12 noms laboV2 doivent apparaître dans la sortie du script.

---

## 5. Déploiement backend test

Déploie le code dans `~/cybel-test`, port **8001**, config POI :

```powershell
python scripts/deploy_termux.py --host <IP_TABLETTE> --lite-only --target test
```

Vérifications :

```powershell
# HTTP depuis le PC (Wi-Fi robot)
curl http://<IP_TABLETTE>:8001/api/health
curl http://<IP_TABLETTE>:8001/api/navigation/points

# Ou via SSH Termux
ssh -p 8022 u0_a92@<IP_TABLETTE> "curl -s http://127.0.0.1:8001/api/health"
```

Redémarrer le backend test si besoin :

```powershell
ssh -p 8022 u0_a92@<IP_TABLETTE> "bash ~/cybel-test/scripts/termux/start_cybel_test.sh"
```

Logs :

```powershell
ssh -p 8022 u0_a92@<IP_TABLETTE> "tail -50 ~/cybel-test-uvicorn.log"
```

---

## 6. Installation APK test

```powershell
adb install -r android\CybelVisitorKioskTest\out\CybelVisitorKioskTest.apk
```

Sur la tablette — **deux icônes** :

| App | Label | Port |
|-----|-------|------|
| A (existant) | CYBEL Accueil | 8000 |
| B (test) | CYBEL Accueil POI | 8001 |

---

## 7. Smoke test POI

1. Ouvrir **CYBEL Accueil POI** (orange).
2. Vérifier le badge **« TEST POI — Sentrymove »**.
3. Lancer **« Démarrer la visite »**.
4. Observer le 1er arrêt (Routeur CNC) : mouvement + TTS + bon emplacement.

---

## 8. Comparaison A/B

Tester **B (POI)** puis **A (Coords)** — ou l'inverse, mais toujours le même ordre.

| Critère | App A (8000) | App B (8001) |
|---------|------------|--------------|
| Délai avant 1er mouvement | | |
| 8 arrêts — robot bouge | | |
| 8 arrêts — bon endroit | | |
| TTS pendant déplacement | | |
| « Parle sans bouger » | | |
| Blocage localisation | | |
| Arrêt visiteur | | |

Fiche par arrêt : voir [KIOSK_AB_COMPARISON.md](KIOSK_AB_COMPARISON.md).

---

## 9. Dépannage

| Problème | Commande / action |
|----------|-------------------|
| Backend 8001 down | `ssh … "bash ~/cybel-test/scripts/termux/start_cybel_test.sh"` |
| POI inconnu | Re-sync §4, vérifier noms Sentrymove |
| Parle sans bouger | `curl …/api/navigation/points` — POI présent ? |
| Écran erreur orange | Vérifier `cybel_kiosk_test_url.txt` sur SD |
| Pas de voix | Installer / vérifier `CybelTTSBridge` |
| rosbridge HS | `ping 192.168.20.22`, relocaliser via Sentrymove |

---

## 10. Checklist finale

- [ ] PC sur Wi-Fi robot
- [ ] `preflight_labo.ps1` → OK ou avertissements acceptables
- [ ] 8 POI Sentrymove créés
- [ ] `sync_poi_from_robot.py` exécuté (sans `--dry-run`)
- [ ] `deploy_termux.py --target test` OK
- [ ] `curl …8001/api/health` → OK
- [ ] APK POI installé
- [ ] CybelTTSBridge présent
- [ ] Smoke test 1er arrêt OK

---

## Références

- [Index labo](README.md)
- [Comparaison A/B détaillée](KIOSK_AB_COMPARISON.md)
- [Sync POI](../SENTRYMOVE_POI_SYNC.md)
- [Déploiement Termux](../TERMUX_DEPLOY.md)
