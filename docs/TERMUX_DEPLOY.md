# Déploiement CYBEL sur Termux (tête Android)

Guide pour faire tourner le **backend + kiosque visiteur** directement sur la tablette Android du robot, sans dépendre du PC développeur.

---

## Pourquoi Termux ?

La tête Android (`172.16.0.x`) ne peut pas joindre le backend sur le PC (`10.42.0.x`) à cause du routage réseau asymétrique (voir [VISITOR_KIOSK.md](VISITOR_KIOSK.md)).

Solution : héberger FastAPI sur la tablette → la WebView charge `http://127.0.0.1:8000/kiosk/`.

---

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

- **CybelVisitorKiosk** — affiche `/kiosk/` en plein écran (`KIOSK_URL = http://127.0.0.1:8000/kiosk/`)
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
- API kiosque : actions, FAQ, TTS local, navigation ROS
- Dépendances : `uvicorn`, `starlette`, `websockets` uniquement

```bash
python scripts/deploy_termux.py --skip-kiosk-build
# ou, si déjà uploadé :
python scripts/termux_lite_deploy.py
```

Le script tente d'abord `bootstrap_lite.sh`, puis le bootstrap complet en secours.

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
```

### Démarrage automatique (optionnel)

Installer [Termux:Boot](https://f-droid.org/packages/com.termux.boot/) puis :

```bash
mkdir -p ~/.termux/boot
cp ~/cybel/scripts/termux/termux-boot.sh ~/.termux/boot/00-cybel.sh
chmod +x ~/.termux/boot/00-cybel.sh
```

---

## 5. Rebuild APK kiosque

Après changement de `KIOSK_URL` :

```bash
cd android/CybelVisitorKiosk
./build.sh
adb install -r out/CybelVisitorKiosk.apk
```

---

## 6. Dépannage

| Symptôme | Piste |
|----------|-------|
| SSH timeout | WiFi robot, IP DHCP changée (`termux_explore.py` → `ip`) |
| `pip install` échoue (pydantic-core) | `pkg install rust binutils` puis relancer `bootstrap.sh` |
| Health check KO | `tail ~/cybel-uvicorn.log` — import manquant ? |
| Kiosque boucle rechargement | Backend down ou `/kiosk/` 404 → rebuild `frontend-kiosk` |
| TTS silencieux | `CybelTTSBridge` installé ? `su` disponible ? |
| Robot non connecté | `ping 192.168.20.22` depuis Termux — pas `10.42.0.1` |
| Espace disque | **~1,5–2 Go libres** requis pour le backend complet (compilation pydantic-core). En dessous → mode lite. |

---

## Fichiers du dépôt

| Fichier | Rôle |
|---------|------|
| `scripts/deploy_termux.py` | Déploiement depuis le PC |
| `scripts/termux_lite_deploy.py` | Bootstrap lite + démarrage (sans re-upload) |
| `scripts/termux_explore.py` | Diagnostic SSH |
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
