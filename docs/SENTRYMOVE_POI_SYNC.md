# Procédure — POI Sentrymove → Kiosque CYBEL

Guide opérateur pour l'option hybride : **Sentrymove / Deployment Tool** + **kiosque CYBEL** (visiteur).

> **Formation complète** : **[labo/GUIDE_CONTROLEUR_POI.md](labo/GUIDE_CONTROLEUR_POI.md)** (format noms, sync, déploiement CybelVisitorKioskTest)  
> **Terrain** : [labo/TERRAIN.md](labo/TERRAIN.md) · Preflight : [`scripts/preflight_labo.ps1`](../scripts/preflight_labo.ps1)

---

## Principe

1. Créer / modifier les POI dans **Deployment Tool** (Sentrymove) — noms **MAJUSCULES**, mots séparés par **tirets**.
2. **Synchroniser** vers `data/points.json` (script ou API).
3. Le **kiosque** navigue par **nom de POI** (`/tag_manager/navi`), comme Sentrymove.

---

## Format des noms (obligatoire)

| Valide | Obsolète |
|--------|----------|
| `CNC ROUTEUR` | `Routeur CNC` |
| `EXTRUSION-SOUFFLAGE` | `Extraction et soufflage` |
| `POSTE-REMPLISSAGE-BOUCHONNAGE` | `Poste remplissage et bouchonnage` |
| `LG-10` | `Station LG-10` |
| `SÉRIGRAPHIE` | `Sérigraphie` |

Voir le guide contrôleur pour la règle complète et le parcours à 6 arrêts.

---

## Étape 1 — Créer les POI dans Sentrymove

```powershell
adb shell am start -n com.ciot.sentrymove/mc.csst.com.selfchassis.ui.activity.main.MainActivity
```

1. Connexion rosbridge : `ws://192.168.20.22:9090`
2. Relocaliser si nécessaire.
3. Placer le robot devant chaque équipement.
4. **Ajouter un marqueur** avec le nom **exact** (format Deployment Tool).
5. Tester « Naviguer vers ce marqueur ».

| Équipement visite | Nom POI Deployment Tool |
|-------------------|-------------------------|
| Routeur CNC | `CNC ROUTEUR` |
| Station LG-10 | `LG-10` |
| Extrusion et soufflage | `EXTRUSION-SOUFFLAGE` |
| Poste remplissage | `POSTE-REMPLISSAGE-BOUCHONNAGE` |
| Thermoformage | `THERMOFORMAGE` |
| Sérigraphie | `SÉRIGRAPHIE` |

⚠️ Les noms doivent correspondre **exactement** à `target_point` dans `data/lab_tour.json`.

---

## Étape 2 — Synchroniser vers CYBEL

### Depuis le PC (Wi-Fi robot)

```powershell
cd C:\Users\clusa\Desktop\cybel
python scripts/sync_poi_from_robot.py --host 192.168.20.22
```

Les POI en minuscules / brouillons sont **automatiquement ignorés**.

### Depuis la tablette (Termux)

```bash
curl -X POST http://127.0.0.1:8001/api/navigation/sync
curl http://127.0.0.1:8001/api/reception/destinations
```

---

## Étape 3 — Déployer sur la tablette (CybelVisitorKioskTest)

```powershell
python scripts/deploy_termux.py --host <IP_TABLETTE> --target test --lite-only
```

Détail ADB et redémarrage : [GUIDE_CONTROLEUR_POI.md](labo/GUIDE_CONTROLEUR_POI.md) §4.

---

## Étape 4 — Tester le kiosque

| Test | Action | Succès |
|------|--------|--------|
| Destinations | Ouvrir kiosque TEST → grille | POI MAJUSCULES visibles |
| Nav simple | Toucher `CNC ROUTEUR` | Robot bouge + TTS |
| Visite | Démarrer visite guidée | 6 arrêts via POI |
| Trace | `GET /api/tour/trace` | nav_status 602 puis 603 |

```powershell
python scripts/phase0_robot_check.py --host 192.168.20.22 --nav-poi "CNC ROUTEUR"
```

---

## Dépannage

| Symptôme | Action |
|----------|--------|
| Sync vide | Créer POI dans Deployment Tool d'abord |
| POI inconnu kiosque | Vérifier format MAJUSCULES, relancer sync |
| Anciens noms en minuscules | Resync — filtre automatique |
| Parle sans bouger | Relocaliser via Sentrymove |

---

## Références

- **Guide contrôleur** : [labo/GUIDE_CONTROLEUR_POI.md](labo/GUIDE_CONTROLEUR_POI.md)
- Plan hybride : [06-plan-hybride-sentrymove-kiosk.md](cybel-conception/06-plan-hybride-sentrymove-kiosk.md)
- Navigation : [TOUR_NAVIGATION.md](TOUR_NAVIGATION.md)
- Déploiement : [TERMUX_DEPLOY.md](TERMUX_DEPLOY.md)
