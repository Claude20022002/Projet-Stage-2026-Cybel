# Déploiement CYBEL sur Termux (tête Android)

Guide pour faire tourner le **backend + kiosque visiteur** directement sur la tablette Android du robot, sans dépendre du PC développeur.

---

## État d'avancement (fin juin 2026)

| Étape | Statut | Détail |
|-------|--------|--------|
| SSH Termux (`:8022`) | ✅ | `deploy_termux.py`, `install_kiosk_apk.py` |
| Bootstrap lite (Starlette) | ✅ | Sans pydantic ; ~45 KiB d'archive |
| Backend `cybel_lite.py` | ✅ | Health 200 ; `/kiosk/` + API `/api/tour/*` |
| Config ROS embarquée | ✅ | `ROBOT_HOST=192.168.20.22` |
| TTS local | ✅ | `SPEECH_LOCAL_BROADCAST=true` |
| Build kiosk IIFE (WebView 7.1) | ✅ | Bundle `app.js` sans `type="module"` |
| Parcours `lab_tour.json` (8 arrêts) | ✅ | Coordonnées depuis `knowledgeV2-lab.json` |
| APK `CybelVisitorKiosk` v1.2 | ✅ | Safe-area, affichage validé |
| Démarrage auto (`termux-boot`) | ⏳ | Script prêt, non activé |

**Priorité actuelle** : valider la navigation autonome sur les 8 arrêts en conditions réelles (carte du laboratoire).

> Diagnostic visite, journal `tour_*.log` et garde-fous navigation → [TOUR_NAVIGATION.md](TOUR_NAVIGATION.md)

> **Aide IA** : brief complet pour Claude AI → [PROMPT_CLAUDE_KIOSK_TABLETTE.md](PROMPT_CLAUDE_KIOSK_TABLETTE.md)

### Procédure de redéploiement (après correctif écran blanc)

```bash
# 1. Rebuild kiosk legacy (PC)
cd frontend-kiosk && npm install && npm run build

# 2. Upload dist/ + scripts Termux + redémarrage backend
python scripts/deploy_termux.py --skip-kiosk-build --lite-only --host 172.16.0.XXX --password ***

# 3. Rebuild et réinstaller l'APK
cd android/CybelVisitorKiosk && ./build.sh
python scripts/install_kiosk_apk.py --host 172.16.0.XXX --password ***

# 4. Vérifications sur Termux
bash ~/cybel/scripts/termux/start_cybel.sh
cat /sdcard/Download/cybel_kiosk_url.txt
curl http://127.0.0.1:8000/api/health
```

---

## Pourquoi Termux ?

La tête Android (`172.16.0.x`) ne peut pas joindre le backend sur le PC (`10.42.0.x`) à cause du routage réseau asymétrique (voir [VISITOR_KIOSK.md §6.2](VISITOR_KIOSK.md#62-configuration-de-lurl-kiosk--résolution-termux-juin-2026)).

**Solution retenue** : héberger le backend sur la tablette via Termux. La WebView
charge `/kiosk/` sur l'IP locale (fichier `cybel_kiosk_url.txt`) ou en secours
sur `127.0.0.1:8000`.

> Depuis Termux, `curl http://127.0.0.1:8000/api/health` peut réussir alors que
> la WebView (autre processus Android) échoue sur la même URL — d'où l'usage
> de l'IP Wi-Fi écrite par `start_cybel.sh`.

## Prérequis

### Sur la tablette (Termux)

```bash
pkg install openssh
sshd
# Mot de passe utilisateur Termux (passwd)
```

SSH par défaut : port **8022**, utilisateur du type `u0_a92`.

### Sur le PC

```bash
pip install paramiko
```

Variables optionnelles (évitez de taper le mot de passe à chaque fois) :

```powershell
$env:CYBEL_TERMUX_HOST="172.16.0.130"
$env:CYBEL_TERMUX_PORT="8022"
$env:CYBEL_TERMUX_USER="u0_a92"
$env:CYBEL_TERMUX_PASSWORD="***"
```

> Ne commitez **jamais** le mot de passe dans le dépôt. Préférez une clé SSH (`ssh-copy-id -p 8022`).

### Apps Android sur la tablette

- **CybelVisitorKiosk** — affiche `/kiosk/` en plein écran ; lit
  `/sdcard/Download/cybel_kiosk_url.txt` au démarrage
- **CybelTTSBridge** — TTS via `am broadcast` local

---

## 1. Exploration SSH

Inventaire réseau, Python, ping châssis, rosbridge :

```bash
python scripts/termux_explore.py
```

Vérifiez notamment :

| Test | Attendu |
|------|---------|
| `ping 10.42.0.1` | Échec attendu (pas de route) |
| `ping 192.168.20.22` | **OK** — châssis via eth0 interne |
| `curl http://192.168.20.22:9090` | **HTTP 200** — rosbridge joignable |
| `pkg list-installed \| grep python` | `pkg install python` si absent |
| `su -c id` | Root disponible (TTS local) |

> **ROBOT_HOST** sur Termux : utiliser `192.168.20.22`, pas `10.42.0.1`.

---

## 2. Déploiement

### Mode recommandé : **CYBEL lite** (Termux)

Le backend complet (FastAPI + pydantic) nécessite ~2 Go libres pour compiler Rust.
Sur la tablette RK3399 (8 Go, souvent >90 % plein), utilisez le **mode lite** :

- `scripts/termux/cybel_lite.py` — Starlette, sans pydantic
- API : actions, FAQ, TTS local, navigation ROS, **API tour** (`/api/tour/*`)
- Données : `data/lab_tour.json`, `data/knowledgeV2-lab.json`
- Dépendances : `uvicorn`, `starlette`, `websockets` uniquement

```bash
python scripts/deploy_termux.py --skip-kiosk-build
# ou, si déjà uploadé :
python scripts/termux_lite_deploy.py
```

Le script tente d'abord `bootstrap_lite.sh`, puis le bootstrap complet en secours.

**Important** : avant déploiement, reconstruire le kiosk (bundle **IIFE** pour WebView 7.1) :

```bash
cd frontend-kiosk
npm install
npm run build    # produit assets/app.js (sans type="module")
```

### Déploiement complet (poste de dev puissant / tablette avec espace)

```bash
python scripts/deploy_termux.py
```

Étapes automatiques :

1. `npm run build` dans `frontend-kiosk/`
2. Archive : `backend/`, `sdk/`, `data/`, `frontend-kiosk/dist/`, `scripts/termux/`
3. Upload SFTP → `~/cybel/`
4. `bootstrap.sh` — `pip install -r backend/requirements.txt`
5. `start_cybel.sh` — uvicorn sur `0.0.0.0:8000`

Options :

```bash
python scripts/deploy_termux.py --skip-kiosk-build   # dist déjà à jour
python scripts/deploy_termux.py --no-bootstrap       # deps déjà installées
python scripts/deploy_termux.py --no-restart         # upload seul
```

---

## 3. Configuration embarquée

Fichier : `scripts/termux/cybel.env` (déployé sur la tablette)

```env
ROBOT_MOCK=false
ROBOT_HOST=192.168.20.22
ROBOT_WS_PORT=9090
SPEECH_LOCAL_BROADCAST=true
SPEECH_ADB_SERIAL=
BACKEND_PORT=8000
```

- **ROS** : rosbridge sur le châssis via lien eth0 `192.168.20.22:9090` (depuis Termux, `10.42.0.1` n'est pas routé)
- **TTS** : broadcast local vers `CybelTTSBridge` (pas d'ADB depuis le PC)

---

## 4. Commandes sur la tablette

```bash
# Démarrer
bash ~/cybel/scripts/termux/start_cybel.sh

# Arrêter
bash ~/cybel/scripts/termux/stop_cybel.sh

# Logs
tail -f ~/cybel-uvicorn.log

# Health check
curl http://127.0.0.1:8000/api/health

# URL pour l'app Android (générée au démarrage)
cat /sdcard/Download/cybel_kiosk_url.txt

# Vérifier les assets legacy du kiosk
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/kiosk/assets/index-legacy-*.js
```

### Démarrage automatique (optionnel)

Installer [Termux:Boot](https://f-droid.org/packages/com.termux.boot/) puis :

```bash
mkdir -p ~/.termux/boot
cp ~/cybel/scripts/termux/termux-boot.sh ~/.termux/boot/00-cybel.sh
chmod +x ~/.termux/boot/00-cybel.sh
```

### Fichier URL kiosk (`cybel_kiosk_url.txt`)

À chaque démarrage réussi, `start_cybel.sh` écrit sur la SD :

```text
/sdcard/Download/cybel_kiosk_url.txt
```

Contenu typique : `http://172.16.0.128:8000/kiosk/` (IP Wi-Fi actuelle).
L'app `CybelVisitorKiosk` lit ce fichier pour contourner l'isolation réseau
Termux ↔ WebView sur `127.0.0.1`.

---

## 5. Rebuild et installation APK kiosque

```bash
# Build APK (PowerShell — voir build.sh si ANDROID_HOME est défini)
cd android/CybelVisitorKiosk
./build.sh

# Installation à distance via SSH (recommandé sur site)
python scripts/install_kiosk_apk.py --password *** --host 172.16.0.XXX

# Ou via ADB
adb install -r out/CybelVisitorKiosk.apk
```

L'APK inclut : lecture de `cybel_kiosk_url.txt`, fallbacks réseau, page
d'erreur visible, `usesCleartextTraffic`, logs console WebView.

---

## 6. Dépannage

| Symptôme | Cause probable | Solution |
|----------|----------------|----------|
| SSH timeout | IP DHCP changée | `termux_explore.py` → `ip -4 addr show wlan0` ; mettre à jour `--host` |
| `pip install` échoue (pydantic-core) | Pas de wheel Android + disque plein | Mode **lite** : `bootstrap_lite.sh` |
| Health check KO | Import manquant, port occupé | `tail ~/cybel-uvicorn.log` ; `stop_cybel.sh` puis `start_cybel.sh` |
| **Écran blanc** (app kiosque) | WebView 7.1 + build Vite moderne | Rebuild avec `@vitejs/plugin-legacy` ; redéployer `dist/` + réinstaller APK |
| Écran blanc + health 200 (Termux) | Isolation réseau Termux ↔ WebView | Vérifier `cybel_kiosk_url.txt` (IP Wi-Fi) ; tester URL dans navigateur tablette |
| Page « connexion impossible » | Backend down ou mauvaise URL | `start_cybel.sh` ; noter l'URL affichée par l'app |
| Kiosque boucle rechargement | `/kiosk/` 404 | `npm run build` puis `deploy_termux.py` |
| TTS silencieux | Bridge absent ou pas de root | `CybelTTSBridge` installé ? `su -c id` |
| Robot non connecté | Mauvais host ROS | `ping 192.168.20.22` — **pas** `10.42.0.1` depuis Termux |
| Espace disque | Compilation Rust échoue | `free_disk.sh` ; viser ~2 Go libres pour bootstrap complet |

### Scripts de diagnostic

```bash
python scripts/kiosk_network_probe.py   # curl Termux + IP wlan + assets kiosk
python scripts/termux_explore.py        # inventaire complet
```

---

## Fichiers du dépôt

| Fichier | Rôle |
|---------|------|
| `scripts/deploy_termux.py` | Déploiement depuis le PC |
| `scripts/termux_lite_deploy.py` | Bootstrap lite + démarrage (sans re-upload) |
| `scripts/termux_explore.py` | Diagnostic SSH |
| `scripts/kiosk_network_probe.py` | Diagnostic accès kiosk (Termux vs Android) |
| `scripts/install_kiosk_apk.py` | Build push + `pm install` via SSH |
| `scripts/termux/cybel_lite.py` | **Backend lite** (Starlette) |
| `scripts/termux/actions.json` | Catalogue actions kiosque |
| `scripts/termux/requirements-lite.txt` | Dépendances sans pydantic |
| `scripts/termux/bootstrap_lite.sh` | Install deps lite |
| `scripts/termux/bootstrap.sh` | Install deps complètes (Rust) |
| `scripts/termux/start_cybel.sh` | Lance uvicorn |
| `scripts/termux/stop_cybel.sh` | Arrête uvicorn |
| `scripts/termux/cybel.env` | Config robot embarquée |
| `scripts/termux/termux-boot.sh` | Hook démarrage Termux |

---

_Voir aussi : [VISITOR_KIOSK.md](VISITOR_KIOSK.md), [ROBOT_CONNECTION.md](ROBOT_CONNECTION.md), [TTS_BRIDGE.md](TTS_BRIDGE.md)_
