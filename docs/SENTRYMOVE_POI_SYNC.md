# Procédure — POI Sentrymove → Kiosque CYBEL

Guide opérateur pour l'option hybride : **Sentrymove / Deployment Tool** + **kiosque CYBEL** (visiteur).

> **Formation complète** : **[labo/GUIDE_CONTROLEUR_POI.md](labo/GUIDE_CONTROLEUR_POI.md)** (format noms, sync, déploiement CybelVisitorKioskTest)  
> **Terrain** : [labo/TERRAIN.md](labo/TERRAIN.md) · Preflight : [`scripts/preflight_labo.ps1`](../scripts/preflight_labo.ps1)

---

## Principe

1. Créer / modifier les POI dans **Deployment Tool** (Sentrymove) — noms **MAJUSCULES**, mots séparés par **tirets**.
2. **Synchroniser** vers `data/points.json` (automatique au kiosque, ou manuel via script / API).
3. Le **kiosque** navigue par **nom de POI** (`/tag_manager/navi`), comme Sentrymove.

**Source de vérité** : les marqueurs ROS de la **carte courante** sur le robot. CYBEL ne conserve pas les POI absents de cette carte.

---

## Synchronisation automatique (juin 2026)

Depuis la mise à jour « sync au démarrage », le kiosque **ne lit plus un cache obsolète** : il interroge ROS avant d'afficher les destinations ou de lancer une visite.

| Déclencheur | Endpoint | Comportement |
|-------------|----------|--------------|
| **Ouverture du kiosque** | `GET /api/reception/destinations` | Sync ROS → `points.json`, puis liste `kiosk_visible` |
| **Démarrage visite guidée** | `POST /api/tour/start` | Sync ROS, puis contrôles prérequis + lancement |
| **Sync manuelle** | `POST /api/navigation/sync` | Sync explicite (opérateur / script) |

Si le robot est **hors ligne** ou sans marqueurs ROS, ces appels renvoient **503** avec un message explicite — le kiosque n'affiche **pas** d'anciens POI d'une carte précédente.

### Remplacement (pas fusion)

À chaque sync réussie :

- `data/points.json` est **remplacé** par les marqueurs ROS de la carte active ;
- les POI présents dans l'ancien fichier mais **absents sur la carte** sont **supprimés** ;
- les noms invalides (minuscules, brouillons) et **obsolètes** (`LG-10`, `LG-09`, `GAMME-CONTROLE-QUALITE`) sont **ignorés** ;
- les points de **charge** (`POINT-RECHARGE`, type `charging`) sont synchronisés mais `kiosk_visible: false` ;
- seuls les POI listés dans `lab_tour.json` (`target_point`) sont marqués `kiosk_visible: true` pour le kiosque visiteur.

> **Référence à jour** : [labo/POI_LABOV2.md](labo/POI_LABOV2.md)

Modules concernés : `sdk/marker_utils.py`, `sdk/persistence.py`, `sdk/poi_sync.py`, `sdk/poi_names.py`.

### Implémentation

| Cible | Fichier | Fonction |
|-------|---------|----------|
| Tablette (cybel_lite) | `scripts/termux/cybel_lite.py` | `sync_poi_from_ros_map()` |
| Backend PC | `backend/services/poi_bootstrap.py` | `ensure_poi_synced_from_robot()` |

---

## Format des noms (obligatoire)

| Valide | Obsolète |
|--------|----------|
| `CNC ROUTEUR` | `Routeur CNC` |
| `EXTRUSION-SOUFFLAGE` | `Extraction et soufflage` |
| `POSTE-REMPLISSAGE-BOUCHONNAGE` | `Poste remplissage et bouchonnage` |
| `LG-10` | `Station LG-10` |
| `SÉRIGRAPHIE` | `Sérigraphie` |

Voir le guide contrôleur pour la règle complète.

---

## Carte laboV2 — 12 POI

Parcours actuel (`data/lab_tour.json`, `map_name: laboV2`) :

| Ordre | `target_point` |
|-------|----------------|
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

⚠️ Chaque `target_point` doit exister **exactement** sur le robot (carte **laboV2** active dans Deployment Tool).

---

## Étape 1 — Créer les POI dans Sentrymove

```powershell
adb shell am start -n com.ciot.sentrymove/mc.csst.com.selfchassis.ui.activity.main.MainActivity
```

1. Connexion rosbridge : `ws://192.168.20.22:9090`
2. Vérifier que la carte active est **laboV2**.
3. Relocaliser si nécessaire.
4. Placer le robot devant chaque équipement.
5. **Ajouter un marqueur** avec le nom **exact** (format Deployment Tool).
6. Tester « Naviguer vers ce marqueur ».

---

## Étape 2 — Synchroniser vers CYBEL

### Option A — Automatique (kiosque / visite)

Ouvrir **CybelVisitorKioskTest** ou rafraîchir le kiosque : la sync se fait à l'ouverture (grille destinations).

Démarrer une **visite guidée** : sync avant le premier déplacement.

### Option B — Depuis le PC (Wi-Fi robot)

```powershell
cd C:\Users\clusa\Desktop\cybel
python scripts/sync_poi_from_robot.py --host 192.168.20.22
```

Simulation sans écriture :

```powershell
python scripts/sync_poi_from_robot.py --host 192.168.20.22 --dry-run
```

### Option C — Depuis la tablette (Termux)

```bash
curl -X POST http://127.0.0.1:8001/api/navigation/sync
curl http://127.0.0.1:8001/api/reception/destinations
```

Réponse sync (`POST /api/navigation/sync`) :

```json
{
  "ok": true,
  "summary": { "ros_count": 12, "total_count": 12, "kiosk_visible_count": 12 },
  "points": [ ... ]
}
```

`GET /api/reception/destinations` renvoie un **tableau** JSON (pas un objet) — format attendu par le frontend kiosque.

---

## Étape 3 — Déployer sur la tablette (CybelVisitorKioskTest)

```powershell
python scripts/deploy_termux.py --host <IP_TABLETTE> --target test --lite-only
```

Détail ADB et redémarrage : [GUIDE_CONTROLEUR_POI.md](labo/GUIDE_CONTROLEUR_POI.md) §4.

Après mise à jour du code, pousser au minimum :

- `scripts/termux/cybel_lite.py`
- `sdk/marker_utils.py`
- `sdk/persistence.py`

Puis redémarrer le backend TEST (port **8001**) via RUN_COMMAND (voir guide contrôleur §4C).

---

## Étape 4 — Tester le kiosque

| Test | Action | Succès |
|------|--------|--------|
| Destinations | Ouvrir kiosque TEST → grille | Uniquement POI de la carte laboV2 |
| Pas de fantômes | Après changement de carte | Anciens POI absents de la liste |
| Nav simple | Toucher `CNC ROUTEUR` | Robot bouge + TTS |
| Visite | Démarrer visite guidée | 12 arrêts via POI |
| Trace | `GET /api/tour/trace` | nav_status 602 puis 603 |

```powershell
adb forward tcp:18001 tcp:8001
curl http://127.0.0.1:18001/api/reception/destinations
curl -X POST "http://127.0.0.1:18001/api/tour/start?lang=fr"

python scripts/phase0_robot_check.py --host 192.168.20.22 --nav-poi "CNC ROUTEUR"
```

---

## Dépannage

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| Sync vide / 503 | Aucun marqueur ROS | Créer POI dans Deployment Tool ; vérifier carte active |
| POI fantômes (ancienne carte) | Backend pas à jour | Déployer `cybel_lite.py` + `marker_utils.py` ; redémarrer :8001 |
| « Synchronisation POI impossible » au démarrage | Robot hors ligne | Allumer robot, rosbridge `9090`, même réseau |
| POI inconnu kiosque | Nom différent robot / CYBEL | Vérifier format MAJUSCULES, resync |
| Anciens noms en minuscules | Marqueurs brouillon Sentrymove | Resync — filtre automatique |
| Parle sans bouger | Pas relocalisé / E-stop | Relocaliser via Sentrymove ; relâcher E-stop |

---

## Références techniques

| Sujet | Fichier |
|-------|---------|
| Merge / élagage POI | `sdk/marker_utils.py` → `merge_point_dicts` |
| Persistance JSON | `sdk/persistence.py` → `merge_robot_points` |
| Sync async (PC) | `sdk/poi_sync.py` → `sync_from_robot` |
| Bootstrap backend | `backend/services/poi_bootstrap.py` |
| Lite tablette | `scripts/termux/cybel_lite.py` → `sync_poi_from_ros_map` |
| Tests | `tests/unit/test_poi_sync.py` |

---

## Références

- **Guide contrôleur** : [labo/GUIDE_CONTROLEUR_POI.md](labo/GUIDE_CONTROLEUR_POI.md)
- Plan hybride : [06-plan-hybride-sentrymove-kiosk.md](cybel-conception/06-plan-hybride-sentrymove-kiosk.md)
- Navigation : [TOUR_NAVIGATION.md](TOUR_NAVIGATION.md)
- Déploiement : [TERMUX_DEPLOY.md](TERMUX_DEPLOY.md)

_Dernière mise à jour : juin 2026 — sync automatique au démarrage kiosque / visite, élagage POI absents de la carte ROS_
