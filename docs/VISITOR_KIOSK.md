# Interface visiteur (kiosque)

Documentation de l'**interface visiteur** du robot CYBEL, affichée en plein écran sur l'écran tactile de l'upper body Android. Elle permet à un visiteur de lancer une **visite guidée autonome du laboratoire** : le robot se déplace d'équipement en équipement et présente chaque poste à voix haute.

---

## État d'avancement (fin juin 2026)

| Composant | Statut | Notes |
|-----------|--------|-------|
| `frontend-kiosk/` — visite guidée FR/EN | ✅ Fonctionnel | Écran accueil, progression, arrêt visiteur |
| `data/lab_tour.json` — 8 arrêts labo | ✅ Configuré | Synthèse depuis `knowledgeV2-lab.json` |
| `sdk/lab_tour.py` — `TourEngine` | ✅ Fonctionnel | Navigation coordonnées + TTS séquentiel |
| API `/api/tour/*` | ✅ FastAPI + cybel_lite | CRUD, status, start, stop, halt |
| Déploiement Termux | ✅ Opérationnel | `deploy_termux.py`, health 200 |
| App Android `CybelVisitorKiosk` v1.2 | ✅ Validé | Build IIFE, safe-area, URL Wi-Fi |
| Contrôle opérateur pendant visite | ✅ | `POST /api/tour/halt` + panneau contrôleur |
| Navigation terrain multi-arrêts | ⏳ En validation | Coordonnées à affiner sur carte réelle |
| Démarrage auto au boot | ⏳ Optionnel | `termux-boot.sh` prêt |

---

## 1. Vue d'ensemble

Contrairement au tableau de bord opérateur (`frontend/`, port `5173`), le kiosque (`frontend-kiosk/`, port `5174` en dev) est une application web **dédiée aux visiteurs** :

- **Écran d'accueil** : présentation du parcours, liste des 8 équipements, bouton **Démarrer la visite** ;
- **Pendant la visite** : progression (étape N/8), phase (déplacement, présentation, observation), message vocal en cours ;
- **Fin** : écran de conclusion, possibilité de relancer une visite ;
- **Bascule FR / EN** : textes affichés et annonces vocales.

Le robot exécute le parcours de façon **autonome** : navigation (`/navi_goal`) → présentation à l'arrivée → pause d'observation → arrêt suivant.

### Mode déployé (sans PC, sans câble USB)

Sur la tablette / tête Android (Termux + `cybel_lite.py`) :

- **Navigation** : rosbridge vers le châssis (`ROBOT_HOST`, ex. `192.168.20.22`)
- **TTS** : `am broadcast` local (`speak_local`) — **pas d'ADB**, pas de PC
- **Démarrage visite** : app kiosque `CybelVisitorKiosk` ou dashboard si le backend tablette est joignable

Le contrôleur PC (`frontend/`) reste utile pour la supervision et l'édition du parcours ; la visite visiteur peut tourner **100 % sur la tablette**.

L'interface est servie par le backend (`/kiosk/`) et affichée dans l'app Android `CybelVisitorKiosk` (WebView plein écran).

## 2. Parcours de visite (`lab_tour.json`)

Fichier : [data/lab_tour.json](../data/lab_tour.json)

| # | Équipement | Source `knowledgeV2-lab.json` |
|---|------------|-------------------------------|
| 1 | Routeur CNC | `cnc router` |
| 2 | Station LG-10 | `lg-10` |
| 3 | Station LG-09 | `lg-09` |
| 4 | Extraction et soufflage | `extraction soufflage` |
| 5 | Poste remplissage / bouchonnage | `poste remplissage bouchonnage` |
| 6 | Thermoformage | `thermoformage` |
| 7 | Imprimante DTF C31 XP600 | `dtf c31 xp600` |
| 8 | Sérigraphie | `serigraphie` |

Chaque arrêt contient : `equipment_fr`, textes vocaux (`speech_fr`, `approach_speech_fr`), coordonnées `x`, `y`, `theta` (orientation = `z` dans knowledge), `dwell_seconds`.

Référence brute des équipements : [data/knowledgeV2-lab.json](../data/knowledgeV2-lab.json).

## 3. API visite guidée

| Méthode | Endpoint | Rôle |
|---------|----------|------|
| `GET` | `/api/tour` | Résumé public du parcours |
| `GET` | `/api/tour/full` | Parcours complet (édition) |
| `PUT` | `/api/tour/full` | Sauvegarde du parcours |
| `GET` | `/api/tour/status` | État en cours (phase, étape, message) |
| `POST` | `/api/tour/start?lang=fr\|en` | Démarrer la visite |
| `POST` | `/api/tour/stop` | Arrêter la visite (visiteur) |
| `POST` | `/api/tour/halt` | **Arrêt total** (visite + robot + TTS) |
| `POST` | `/api/tour/stops` | Ajouter un arrêt |
| `PUT` | `/api/tour/stops/{id}` | Modifier un arrêt |
| `DELETE` | `/api/tour/stops/{id}` | Supprimer un arrêt |

Implémentation : `sdk/lab_tour.py` (`TourEngine`), `backend/services/tour_service.py`, `scripts/termux/cybel_lite.py` (Termux).

## 4. Contrôle opérateur pendant une visite

Depuis l'interface opérateur (`frontend/`, voir [INTERFACE.md](INTERFACE.md)) :

- Panneau **Visite guidée** : état live, CRUD des arrêts, bouton **ARRÊT TOTAL** ;
- Boutons **Arrêt**, **E-STOP**, **Annuler navigation** → appellent aussi `/api/tour/halt` ;
- Le backend PC relaie l'arrêt vers la tablette via `CYBEL_KIOSK_BACKEND_URL` (défaut `http://172.16.0.131:8000`).

## 5. Démarrage (développement)

```bash
python scripts/dev.py   # backend :8000, opérateur :5173, kiosque :5174
```

Navigateur : `http://127.0.0.1:5174`

## 6. Build production

```bash
cd frontend-kiosk
npm install
npm run build    # → dist/ (bundle IIFE Chrome 49, sans type="module")
```

**WebView Android 7.1** : le build utilise un bundle **IIFE** (`vite.config.ts`, cible `chrome >= 49`). Sans cela, la WebView ignore le JavaScript → écran blanc.

Le backend monte `frontend-kiosk/dist/` sur `/kiosk/` (`backend/main.py`, `cybel_lite.py`).

## 7. Application Android (`CybelVisitorKiosk`)

- WebView plein écran, mode immersif ;
- URL lue depuis `/sdcard/Download/cybel_kiosk_url.txt` (écrit par `start_cybel.sh`) ;
- Fallbacks : IP Wi-Fi, `127.0.0.1`, `192.168.20.1` ;
- **Responsive** : `viewport-fit=cover`, `env(safe-area-inset-top)`, injection `--android-safe-top` depuis Java ;
- APK v1.2 (`versionCode=3`).

Installation :

```bash
python scripts/install_kiosk_apk.py --host 172.16.0.XXX --password ***
```

Voir [TERMUX_DEPLOY.md](TERMUX_DEPLOY.md) pour le déploiement complet.

## 8. Déploiement Termux

```bash
python scripts/deploy_termux.py --host 172.16.0.XXX --password ***
bash ~/cybel/scripts/termux/start_cybel.sh   # sur la tablette
```

Vérifications :

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/tour
cat /sdcard/Download/cybel_kiosk_url.txt
```

## 9. Historique des problèmes (résolus)

| Problème | Solution |
|----------|----------|
| Backend PC injoignable depuis tablette | Backend Termux local |
| FastAPI/pydantic sur Termux | `cybel_lite.py` (Starlette) |
| Écran blanc WebView | Build IIFE + URL IP Wi-Fi |
| Logo CYBEL coupé (barre statut) | safe-area + padding Android |
| `sdk.lab_tour` → pydantic sur Termux | Import direct du module sans `sdk/__init__.py` |
| rosbridge depuis Termux | `ROBOT_HOST=192.168.20.22` |

## 10. Limites / suite

- Pas de reconnaissance vocale côté visiteur (tactile uniquement).
- Coordonnées des arrêts à valider/ajuster sur la carte SLAM réelle.
- Pas de reprise automatique après arrêt d'urgence (relancer manuellement).
- L'opérateur doit maintenir `CYBEL_KIOSK_BACKEND_URL` à jour si l'IP Wi-Fi change.

---

_Voir aussi : [INTERFACE.md](INTERFACE.md) (panneau visite opérateur), [rapport de stage](Sujet%20de%20stage/rapport_stage_cybel.md)._
