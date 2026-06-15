# Connexion au robot réel — configuration, reconnexion, débogage

Guide pratique pour faire tourner le backend CYBEL en **mode réel** (robot
physique, pas le mock), reconnecter les différents canaux après un
redémarrage du robot, et déboguer en cas de problème. Complète
[docs/TTS_BRIDGE.md](TTS_BRIDGE.md) (qui documente l'investigation et la
solution TTS elle-même).

---

## Table des matières

1. [Vue d'ensemble des connexions](#1-vue-densemble-des-connexions)
2. [Configuration `.env`](#2-configuration-env)
3. [Lancer la plateforme en mode réel](#3-lancer-la-plateforme-en-mode-réel)
4. [Procédure de (re)connexion ADB à la tête Android](#4-procédure-de-reconnexion-adb-à-la-tête-android)
5. [Checklist après un redémarrage du robot](#5-checklist-après-un-redémarrage-du-robot)
6. [Débogage](#6-débogage)
7. [Test de bout en bout depuis l'interface web](#7-test-de-bout-en-bout-depuis-linterface-web)

---

## 1. Vue d'ensemble des connexions

Le PC doit être connecté au **réseau Wi-Fi du robot**. Trois canaux
distincts, tous indépendants du câble USB une fois configurés :

| Canal | Cible | Port | Usage | Configuré par |
|-------|-------|------|-------|----------------|
| **rosbridge** (châssis) | `10.42.0.1` | `9090` (WebSocket) | Déplacement, télémétrie, carte SLAM | `ROBOT_HOST` / `ROBOT_WS_PORT` |
| **ADB Wi-Fi** (tête Android) | `172.16.0.194` | `5555` | Synthèse vocale (CybelTTSBridge) | `SPEECH_ADB_SERIAL` |
| **HTTP** (tête Android, fallback) | `172.16.0.194` | variable | Fallback TTS (jamais confirmé fonctionnel) | `SPEECH_HTTP_HOST` |

⚠️ **Les deux IP `10.42.0.1` et `172.16.0.194` sont sur le même réseau Wi-Fi
mais désignent deux ordinateurs différents du robot** (châssis/MCU vs tête
Android RK3399). Ne pas les confondre.

L'IP `172.16.0.194` est attribuée par **DHCP** côté tête Android — elle peut
changer après un redémarrage du robot ou du point d'accès (voir §5).

## 2. Configuration `.env`

Fichier : `backend/.env` (chargé par `pydantic_settings`, `cwd=backend` au
lancement via `scripts/dev.py`).

```ini
ROBOT_MOCK=false
ROBOT_HOST=10.42.0.1
ROBOT_WS_PORT=9090
SPEECH_TOPIC=
SPEECH_SERVICE=
SPEECH_HTTP_HOST=172.16.0.194
```

### ⚠️ À propos de `BACKEND_PORT=5555`

Ce réglage existe dans `backend/config.py` (`backend_port: int = 8000`) mais
**n'est lu par aucun lanceur** :

- `scripts/dev.py` lance uvicorn avec `--port 8000` **codé en dur**.
- Le proxy Vite (`frontend/vite.config.ts`) pointe vers
  `http://127.0.0.1:8000` / `ws://127.0.0.1:8000` **codé en dur**.

➡️ Mettre `BACKEND_PORT=5555` dans `.env` n'a donc **aucun effet** — le
backend continuera d'écouter sur `8000`, et c'est ce que le frontend attend.
Ce n'est pas un conflit avec l'ADB du robot (`172.16.0.194:5555` est un autre
hôte), mais c'est trompeur. **Recommandation : supprimer la ligne
`BACKEND_PORT=5555`** (ou la mettre à `8000` pour qu'elle reflète la réalité).
Si un jour on veut vraiment un autre port, il faudra aussi modifier
`scripts/dev.py` et `vite.config.ts` en cohérence.

### Variable manquante : `SPEECH_ADB_SERIAL`

`backend/config.py` définit `speech_adb_serial: str = ""`, qui retombe sur la
constante `SPEECH_ADB_SERIAL = "172.16.0.194:5555"` de `sdk/constants.py` si
vide. Pas besoin de la renseigner dans `.env` tant que l'IP ne change pas
(sinon, ajouter `SPEECH_ADB_SERIAL=<ip>:5555`).

## 3. Lancer la plateforme en mode réel

```bash
cd c:\Users\clusa\Desktop\cybel
python scripts/dev.py
```

- Backend FastAPI : `http://127.0.0.1:8000` (uvicorn `--reload`)
- Frontend Vite : `http://127.0.0.1:5173` (proxy `/api` et WebSocket vers le
  backend)

Avec `ROBOT_MOCK=false`, le backend se connecte à `ws://10.42.0.1:9090`
(rosbridge) au démarrage. Si la connexion échoue, le backend reste up mais
les commandes de déplacement échoueront — voir §6.

## 4. Procédure de (re)connexion ADB à la tête Android

À faire **une fois par session** (ou après un redémarrage du robot, voir
§5). Nécessite un accès physique temporaire (câble USB-C) côté tête Android.

```bash
# 1. Brancher le câble USB-C -> USB sur la tête Android (mode Host/OTG côté robot)
adb devices                                   # doit lister un device USB, ex: 1f4311e7d7

# 2. Basculer adbd en écoute TCP
adb -s <serial_usb> tcpip 5555

# 3. Récupérer l'IP Wi-Fi actuelle de la tête Android
export MSYS_NO_PATHCONV=1
adb -s <serial_usb> shell ip addr show wlan0  # cherche "inet x.x.x.x/.."

# 4. Se connecter en Wi-Fi (le câble peut être débranché après cette étape)
adb connect <ip_wifi>:5555

# 5. Vérifier
adb devices   # doit lister "<ip_wifi>:5555  device"
```

Si `<ip_wifi>` ≠ `172.16.0.194`, mettre à jour :
- `SPEECH_ADB_SERIAL` dans `sdk/constants.py` (valeur par défaut), **et/ou**
- `SPEECH_ADB_SERIAL=<ip_wifi>:5555` dans `backend/.env`
- `SPEECH_HTTP_HOST` (même IP, autre constante) si on veut garder le fallback
  HTTP cohérent.

## 5. Checklist après un redémarrage du robot

Un redémarrage du robot (châssis ou tête Android) peut casser un ou
plusieurs canaux :

| Symptôme | Cause probable | Action |
|----------|------------------|--------|
| Déplacement KO, carte ne charge plus | rosbridge (`10.42.0.1:9090`) pas encore prêt ou robot pas reconnecté au Wi-Fi | Attendre le démarrage complet, vérifier `ping 10.42.0.1`, redémarrer le backend |
| TTS muet, `adb devices` ne liste plus `<ip>:5555` | `adbd` a perdu le mode `tcpip` (redémarre en USB-only par défaut) | Refaire la procédure §4 (câble requis) |
| TTS muet mais `adb devices` OK | IP Wi-Fi de la tête a changé (DHCP) | `adb shell ip addr show wlan0` en USB, mettre à jour `SPEECH_ADB_SERIAL`/`SPEECH_HTTP_HOST` |
| `am broadcast` ne déclenche rien | App `CybelTTSBridge` désinstallée (reset usine) | Réinstaller : `adb -s <ip>:5555 install -r android/CybelTTSBridge/out/CybelTTSBridge.apk` |

## 6. Débogage

### ADB / TTS

```bash
adb devices                                              # connexions actives
adb -s 172.16.0.194:5555 logcat -c                       # vider le buffer
# ... déclencher une action TTS depuis l'UI ou en CLI ...
adb -s 172.16.0.194:5555 logcat -d | grep -iE "cybel|texttospeech|audiotrack"
```

Test manuel direct (sans passer par le backend) :

```bash
adb -s 172.16.0.194:5555 shell \
  "am broadcast -n com.cybel.ttsbridge/.SpeakReceiver \
   -a com.cybel.ttsbridge.SPEAK --es text 'Test de synthese vocale'"
```

Test du module Python isolément :

```bash
cd c:\Users\clusa\Desktop\cybel
python -c "
import asyncio
from sdk.speech import RobotSpeech

async def main():
    print(await RobotSpeech(mock=False).speak('Test depuis le SDK'))

asyncio.run(main())
"
```
Réponse attendue : `{'ok': True, 'method': 'adb-tts', ...}`.

### rosbridge / déplacement

```bash
ping 10.42.0.1
# Vérifier que rosbridge répond (nécessite websocat ou un script Python) :
python -c "
import asyncio
from sdk.rosbridge import RosbridgeClient

async def main():
    c = RosbridgeClient('ws://10.42.0.1:9090')
    await c.connect()
    print('connected:', c.connected)
    resp = await c.call_service('/rosapi/topics', {}, timeout=3.0)
    print(resp)

asyncio.run(main())
"
```

### Backend / frontend

- Logs `scripts/dev.py` : préfixe `[backend]` / `[frontend]` dans la console.
- `GET http://127.0.0.1:8000/api/...` directement (sans passer par Vite) pour
  isoler un souci de proxy.
- Onglet réseau du navigateur : vérifier que la connexion WebSocket
  `ws://127.0.0.1:5173/...` (proxyée vers `8000`) reste ouverte.

## 7. Test de bout en bout depuis l'interface web

1. `ROBOT_MOCK=false` dans `backend/.env`, câble débranché.
2. `python scripts/dev.py`, ouvrir `http://127.0.0.1:5173`.
3. Vérifier la barre de statut : connexion robot OK, batterie/localisation
   affichées (confirme rosbridge).
4. Tester un déplacement court (point prédéfini ou téléopération).
5. Saisir un texte dans le panneau TTS et valider — le robot doit parler
   (confirme le pont `CybelTTSBridge` via `adb-tts`).
6. En cas d'échec sur l'un des deux, se référer à la checklist §5 et au
   débogage §6 selon le canal concerné.
