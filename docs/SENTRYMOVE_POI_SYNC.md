# Procédure — POI Sentrymove → Kiosque CYBEL

Guide opérateur pour l'option hybride : **Sentrymove** (superviseur + cartographie) + **kiosque CYBEL** (visiteur).

> **Terrain** : [labo/TERRAIN.md](labo/TERRAIN.md) · Preflight : [`scripts/preflight_labo.ps1`](../scripts/preflight_labo.ps1)

---

## Principe

1. Créer / modifier les POI dans **Sentrymove** (`com.ciot.sentrymove`).
2. **Synchroniser** vers `data/points.json` (script ou API).
3. Le **kiosque** navigue par **nom de POI** (`/tag_manager/navi`), comme Sentrymove.

---

## Étape 1 — Créer les POI dans Sentrymove

```powershell
adb shell am start -n com.ciot.sentrymove/mc.csst.com.selfchassis.ui.activity.main.MainActivity
```

1. Connexion rosbridge : `ws://192.168.20.22:9090`
2. Relocaliser si nécessaire (localisation visible sur la carte).
3. Placer le robot devant chaque équipement.
4. **Ajouter un marqueur** avec le nom **exact** (voir tableau ci-dessous).
5. Tester « Naviguer vers ce marqueur ».

| Équipement visite | Nom POI à créer dans Sentrymove |
|-------------------|----------------------------------|
| Routeur CNC | `Routeur CNC` |
| Station LG-10 | `Station LG-10` |
| Station LG-09 | `Station LG-09` |
| Extraction et soufflage | `Extraction et soufflage` |
| Poste remplissage | `Poste remplissage et bouchonnage` |
| Thermoformage | `Thermoformage` |
| Imprimante DTF | `Imprimante DTF C31 XP600` |
| Sérigraphie | `Sérigraphie` |

⚠️ Les noms doivent correspondre **exactement** à `target_point` dans `data/lab_tour.json`.

---

## Étape 2 — Synchroniser vers CYBEL

### Depuis le PC (Wi-Fi robot)

```powershell
cd C:\Users\clusa\Desktop\cybel
git checkout feature/hybrid-sentrymove-kiosk
python scripts/sync_poi_from_robot.py --host 192.168.20.22
```

Options :

```powershell
# Simulation sans écriture
python scripts/sync_poi_from_robot.py --host 192.168.20.22 --dry-run

# PC connecté au hotspot robot
python scripts/sync_poi_from_robot.py --host 10.42.0.1

# API backend (robot connecté)
curl -X POST http://127.0.0.1:8000/api/navigation/sync
```

### Depuis la tablette (Termux)

```bash
curl -X POST http://127.0.0.1:8000/api/navigation/sync
curl http://127.0.0.1:8000/api/navigation/points
curl http://127.0.0.1:8000/api/reception/destinations
```

---

## Étape 3 — Déployer sur la tablette

```powershell
python scripts/deploy_termux.py --host <IP_TABLETTE> --lite-only
```

Sur la tablette :

```bash
bash ~/cybel/scripts/termux/start_cybel.sh
```

---

## Étape 4 — Tester le kiosque

| Test | Action | Succès |
|------|--------|--------|
| Destinations | Ouvrir kiosque → grille destinations | POI Sentrymove visibles |
| Nav simple | Toucher « Routeur CNC » | Robot bouge + TTS |
| Visite | Démarrer visite guidée | 8 arrêts via POI |
| Trace | `GET /api/tour/trace` | nav_status 602 puis 603 |

Smoke test :

```powershell
python scripts/phase0_robot_check.py --host 192.168.20.22 --nav-poi "Routeur CNC"
```

---

## Dépannage

| Symptôme | Action |
|----------|--------|
| Sync vide | Créer POI dans Sentrymove d'abord |
| POI inconnu kiosque | Relancer sync, vérifier nom exact |
| Parle sans bouger | Relocaliser via Sentrymove, `nav_status` = 601 |
| Mauvais endroit | Supprimer coords dans lab_tour, garder `target_point` |

---

## Références

- Plan complet : [06-plan-hybride-sentrymove-kiosk.md](cybel-conception/06-plan-hybride-sentrymove-kiosk.md)
- Navigation : [TOUR_NAVIGATION.md](TOUR_NAVIGATION.md)
- Déploiement : [TERMUX_DEPLOY.md](TERMUX_DEPLOY.md)
