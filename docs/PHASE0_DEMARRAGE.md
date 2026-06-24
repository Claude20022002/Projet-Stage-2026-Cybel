# Phase 0 — Démarrage et smoke test robot

Guide pour valider CYBEL **le matin sur le robot** avant d'ouvrir l'interface web.
Couvre la préparation réseau, le smoke test CLI, les tests unitaires hors robot,
puis le lancement complet de la plateforme.

Robot de référence : **CIOT TY1251D-03195**  
Réseau : châssis `10.42.0.1` (ROSBridge `:9090`), tablette `172.16.0.194` (TTS ADB).

Complète [ROBOT_CONNECTION.md](ROBOT_CONNECTION.md) et [INTERFACE.md](INTERFACE.md).

---

## 1. Prérequis

| Élément | Vérification |
|---------|----------------|
| PC sur le **Wi-Fi du robot** | Ping `10.42.0.1` |
| Python 3.11+ | `python --version` |
| Dépendances installées | `pip install -r requirements.txt` (racine) |
| Node.js (interface web) | `npm install` dans `frontend/` et `frontend-kiosk/` |
| ADB (TTS optionnel) | `adb connect 172.16.0.194:5555` puis `adb devices` |

---

## 2. Configuration `backend/.env`

Créer ou éditer `backend/.env` :

```ini
ROBOT_MOCK=false
ROBOT_HOST=10.42.0.1
ROBOT_WS_PORT=9090
SPEECH_ADB_SERIAL=172.16.0.194:5555
LOCALIZATION_MIN_PERCENT=60
AUTO_RELOCALIZE_ON_CONNECT=true
```

Le smoke test lit ce fichier pour l'hôte robot et l'ADB.  
Le basculement mock/réel se fait **uniquement** via `ROBOT_MOCK` (pas depuis l'UI).

---

## 3. Séquence recommandée (matin)

### Étape A — Tests unitaires hors robot (la veille ou en premier)

Valide le code Phase 0 sans réseau :

```powershell
cd C:\Users\clusa\Desktop\cybel
$env:ROBOT_MOCK="true"
python -m pytest tests/unit -v --tb=short
```

Attendu : **37 passed**.

### Étape B — Smoke test CLI (sur le robot, ~2 min)

**Avant** de lancer le backend ou le frontend :

```powershell
cd C:\Users\clusa\Desktop\cybel
python scripts/phase0_robot_check.py
```

Contrôles par défaut (sans mouvement) :

- Connexion ROSBridge `ws://10.42.0.1:9090`
- Télémétrie pose et statut
- `nav_status` (601 = prêt)
- Services APK listés (`/tag_manager/navi`, `/global_locate`, `/poi`, …)
- Marqueurs POI chargés
- Téléop : publish vitesse **nulle** sur `/cmd_vel_mux/input/teleop`
- Annulation multi-canal

**Code de sortie** : `0` = OK (PASS ou WARN), `1` = au moins un FAIL.

#### Options utiles

```powershell
# Vérifier le script sans robot
python scripts/phase0_robot_check.py --mock

# Relocalisation (le robot peut tourner sur lui-même)
python scripts/phase0_robot_check.py --relocalize

# Pulse téléop court en mode manuel (espace dégagé !)
python scripts/phase0_robot_check.py --teleop

# Navigation vers un marqueur connu, arrêt après 5 s
python scripts/phase0_robot_check.py --nav-poi Accueil --nav-seconds 5

# TTS tablette (ADB requis)
python scripts/phase0_robot_check.py --tts

# Session complète avant l'UI
python scripts/phase0_robot_check.py --relocalize --nav-poi Accueil --nav-seconds 5 --tts
```

| Option | Effet |
|--------|--------|
| `--host`, `--port` | Surcharge `ROBOT_HOST` / port |
| `--adb-serial` | Surcharge `SPEECH_ADB_SERIAL` |
| `--relocalize` | Lance `/global_locate` puis fallback |
| `--teleop` | Avance ~0,3 s à 0,08 m/s puis arrêt |
| `--nav-poi NOM` | Navigation POI puis `stop()` |
| `--tts` | Phrase « Test CYBEL phase zéro » |
| `--no-probe-services` | Ne pas appeler le service POI avec un marqueur fictif |

### Étape C — Lancer la plateforme web

Une fois le smoke test vert (ou WARN acceptables) :

```powershell
cd C:\Users\clusa\Desktop\cybel
python scripts/dev.py
```

| Service | URL |
|---------|-----|
| API + santé | http://localhost:8000/api/health |
| Interface opérateur | http://localhost:5173 |
| Kiosk | http://localhost:5173 (port kiosk Vite — voir sortie console) |
| Kiosk build statique | http://localhost:8000/kiosk (si `frontend-kiosk/dist` existe) |

> **Astuce** : `dev.py` lance le backend **sans** `--reload` par défaut pour ne pas saturer rosbridge.  
> Rechargement auto : `$env:CYBEL_DEV_RELOAD="1"` avant `python scripts/dev.py`.

#### Alternative — backend seul

```powershell
cd backend
$env:ROBOT_MOCK="false"
python -m uvicorn main:app --port 8000
```

Puis dans un autre terminal :

```powershell
cd frontend
npm run dev
```

---

## 4. Checklist rapide sur le robot

1. **Smoke test** → connexion + marqueurs + `nav_status` 601
2. **Relocaliser** (UI ou `--relocalize`) → localisation ≥ 60 %
3. **Téléop** (`--teleop` ou UI mode manuel) → robot répond
4. **Nav POI** → événement avec `method: /tag_manager/navi` ou `/poi`
5. **TTS** (`--tts` ou UI) → `method: adb-tts`
6. **Arrêt / E-Stop** → robot immobile, `nav_status` repasse à 601

---

## 5. Interprétation des résultats smoke test

| Résultat | Action |
|----------|--------|
| **FAIL Connexion ROSBridge** | Wi-Fi, robot allumé, rosbridge actif sur `:9090` |
| **FAIL Télémétrie** | Redémarrer le robot, réessayer après 30 s |
| **WARN Services absents** | Fallback `/poi` ou `/global_localization` — noter ce qui répond demain |
| **WARN Marqueurs vides** | Vérifier `/marker_manager/get_markers_details` ; cartographie chargée ? |
| **WARN Carte SLAM** | Non bloquant pour téléop ; nécessaire pour nav coordonnées |

Les événements `method` dans l'interface (ou la console backend) indiquent quel service APK a répondu — utile pour affiner `sdk/constants.py` après la session.

---

## 6. Dépannage express

```powershell
# Écouter statuts ROS en direct
python scripts/robot_status.py

# Lister services / POI
python scripts/poi_introspect.py

# Santé API une fois le backend lancé
curl http://localhost:8000/api/health
```

Voir [ROBOT_CONNECTION.md](ROBOT_CONNECTION.md) pour ADB, IP tablette DHCP, et reconnexion après reboot.

---

## 7. Références conception

| Document | Contenu |
|----------|---------|
| [cybel-conception/05-backlog.md](cybel-conception/05-backlog.md) | Tâches CYB-001 → CYB-006 (Phase 0) |
| [cybel-conception/AUDIT_APK_CONSTRUCTEUR.md](cybel-conception/AUDIT_APK_CONSTRUCTEUR.md) | Protocole APK de référence |
