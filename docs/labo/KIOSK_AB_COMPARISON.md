# Comparaison A/B — deux kiosques CYBEL sur la même tablette

Deux applications Android **installables en parallèle** permettent de comparer au labo l'approche **coordonnées** (actuelle) et l'approche **POI Sentrymove** (test).

> Procédure complète : [TERRAIN.md](TERRAIN.md) · Preflight : [`scripts/preflight_labo.ps1`](../../scripts/preflight_labo.ps1)

## Vue d'ensemble

| | **A — Production (actuelle)** | **B — Test POI** |
|---|---|---|
| **App Android** | `CybelVisitorKiosk` | `CybelVisitorKioskTest` |
| **Package** | `com.cybel.visitorkiosk` | `com.cybel.visitorkiosk.test` |
| **Label launcher** | CYBEL Accueil | CYBEL Accueil POI |
| **Écran démarrage** | Bleu — « CYBEL Accueil » | Orange — badge « TEST POI » |
| **Backend Termux** | `~/cybel` | `~/cybel-test` |
| **Port HTTP** | **8000** | **8001** |
| **Fichier URL** | `/sdcard/Download/cybel_kiosk_url.txt` | `/sdcard/Download/cybel_kiosk_test_url.txt` |
| **Script démarrage** | `start_cybel.sh` | `start_cybel_test.sh` |
| **Logs** | `~/cybel-uvicorn.log` | `~/cybel-test-uvicorn.log` |
| **Branche Git** | `main` (coords) | `feature/hybrid-sentrymove-kiosk` (POI) |
| **Badge UI kiosque** | « Coords /navi_goal » | « TEST POI — Sentrymove » |

Les deux backends peuvent tourner **simultanément** (ports différents). L'app A ne touche pas à l'app B.

## Différence fonctionnelle (navigation visite)

| | **A — Coords** | **B — POI** |
|---|---|---|
| **Source des arrêts** | `lab_tour.json` avec `x`, `y`, `theta` | `lab_tour.json` avec `target_point` |
| **Commande ROS** | Publication `/navi_goal` | Service `/poi` / navigation par nom (Sentrymove) |
| **Alignement carte** | Repère SLAM CYBEL / coords extraites | POI créés dans Deployment Tool |
| **Sync POI** | Non requise | `sync_poi_from_robot.py` |
| **Symptômes connus (A)** | Parle sans bouger, mauvaise destination, lenteur | — |
| **Hypothèse (B)** | — | Même pipeline constructeur → meilleure fiabilité |

## Déploiement

### App A (production)

```powershell
python scripts/deploy_termux.py --host <IP_TABLETTE> --lite-only
adb install -r android\CybelVisitorKiosk\out\CybelVisitorKiosk.apk
```

### App B (test POI)

```powershell
git checkout feature/hybrid-sentrymove-kiosk
python scripts/deploy_termux.py --host <IP_TABLETTE> --lite-only --target test
adb install -r android\CybelVisitorKioskTest\out\CybelVisitorKioskTest.apk
```

### Sync POI (avant B)

```powershell
python scripts/sync_poi_from_robot.py --host 192.168.20.22 --dry-run
python scripts/sync_poi_from_robot.py --host 192.168.20.22
```

## Vérifications rapides

```bash
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8001/api/health
curl -s http://127.0.0.1:8001/api/navigation/points
```

Ou : `.\scripts\preflight_labo.ps1 -TabletHost <IP>`

## Protocole de test

| Arrêt | A coords — OK ? | B POI — OK ? | Notes |
|---|---|---|---|
| Intro + Routeur CNC | | | |
| Station LG-10 | | | |
| Station LG-09 | | | |
| Extraction et soufflage | | | |
| Poste remplissage et bouchonnage | | | |
| Thermoformage | | | |
| Imprimante DTF C31 XP600 | | | |
| Sérigraphie | | | |

## Désinstallation test

```bash
adb uninstall com.cybel.visitorkiosk.test
bash ~/cybel-test/scripts/termux/stop_cybel_test.sh
```

L'app A et `~/cybel` restent intacts.
