# Comparaison A/B — deux kiosques CYBEL sur la même tablette

Deux applications Android **installables en parallèle** permettent de comparer demain au labo l’approche **coordonnées** (actuelle) et l’approche **POI Sentrymove** (test).

## Vue d’ensemble

| | **A — Production (actuelle)** | **B — Test demain (POI)** |
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
| **Branche Git recommandée** | `main` (coords) | `feature/hybrid-sentrymove-kiosk` (POI) |
| **Badge UI kiosque** | « Coords /navi_goal » | « TEST POI — Sentrymove » |

Les deux backends peuvent tourner **simultanément** (ports différents). L’app A ne touche pas à l’app B.

## Différence fonctionnelle (navigation visite)

| | **A — Coords** | **B — POI** |
|---|---|---|
| **Source des arrêts** | `data/lab_tour.json` avec `x`, `y`, `theta` | `data/lab_tour.json` avec `target_point` (nom POI) |
| **Commande ROS** | Publication `/navi_goal` (`PoseStamped`) | Service `/poi` ou navigation par nom (alignée Sentrymove) |
| **Alignement carte** | Dépend du repère SLAM CYBEL / coords extraites | Reprend les POI créés dans **Deployment Tool** (Sentrymove) |
| **Sync POI** | Non requise | `python scripts/sync_poi_from_robot.py --host 192.168.20.22` |
| **Prérequis terrain** | Coords calibrées dans `knowledgeV2-lab.json` | POI Sentrymove avec **noms exacts** = `target_point` dans `lab_tour.json` |
| **Symptômes connus (A)** | Parle sans bouger, mauvaise destination, lenteur | — |
| **Hypothèse (B)** | — | Même pipeline que l’app constructeur → meilleure fiabilité navigation |

## Déploiement

### App A (déjà en place)

```powershell
# Branche main ou config coords
python scripts/deploy_termux.py --host <IP_TABLETTE> --lite-only

# APK (si rebuild nécessaire)
cd android/CybelVisitorKiosk && bash build.sh
adb install -r out/CybelVisitorKiosk.apk
```

### App B (test demain)

```powershell
# Depuis la branche hybrid (POI + sync)
git checkout feature/hybrid-sentrymove-kiosk

python scripts/deploy_termux.py --host <IP_TABLETTE> --lite-only --target test

cd android/CybelVisitorKioskTest && bash build.sh
adb install -r out/CybelVisitorKioskTest.apk
```

### Sync POI (avant test B)

1. Créer / vérifier les POI dans **Sentrymove** (Deployment Tool) sur la tablette constructeur.
2. Sur le PC :

```powershell
python scripts/sync_poi_from_robot.py --host 192.168.20.22
python scripts/sync_poi_from_robot.py --host 192.168.20.22 --dry-run   # vérification
```

3. Redéployer la cible test ou copier `data/points.json` vers `~/cybel-test/data/` sur Termux.

## Vérifications rapides

```bash
# Termux SSH — les deux backends
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8001/api/health

# Variante kiosque affichée
curl -s http://127.0.0.1:8000/api/kiosk/config | grep kiosk_variant
curl -s http://127.0.0.1:8001/api/kiosk/config | grep kiosk_variant

# Points POI sync (test)
curl -s http://127.0.0.1:8001/api/navigation/points
```

## Protocole de test demain (labo)

Pour chaque variante, noter sur une fiche :

1. **Démarrage visite** — délai avant premier déplacement (s)
2. **Chaque arrêt (×8)** — robot bouge ? bon endroit ? TTS OK ?
3. **Échecs** — `nav_status`, message erreur, « parle sans bouger » ?
4. **Localisation** — % affiché, blocages
5. **Arrêt visiteur / urgence** — réaction

| Arrêt | A coords — OK ? | B POI — OK ? | Notes |
|---|---|---|---|
| Intro | | | |
| Routeur CNC | | | |
| … | | | |

## Fichiers clés

| Fichier | Rôle |
|---|---|
| `android/CybelVisitorKiosk/` | App A |
| `android/CybelVisitorKioskTest/` | App B |
| `data/kiosk_config.coords.json` | Config badge + variante A |
| `data/kiosk_config.poi.json` | Config badge + variante B |
| `data/lab_tour.json` | Parcours (coords ou `target_point` selon branche) |
| `docs/SENTRYMOVE_POI_SYNC.md` | Détail sync POI |
| `docs/cybel-conception/06-plan-hybride-sentrymove-kiosk.md` | Stratégie hybride |

## Désinstallation / retour arrière

```bash
adb uninstall com.cybel.visitorkiosk.test   # retire uniquement B
bash ~/cybel-test/scripts/termux/stop_cybel_test.sh
```

L’app A et `~/cybel` restent intacts.
