# Connexion au robot réel — configuration, reconnexion, débogage

> Index : [docs/README.md](README.md) · Section : [robot/README.md](robot/README.md)

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

À faire **à chaque session** sur le robot CIOT TY1251D du labo : la tête
Android n'expose ADB **que via câble USB** (pas de `adb connect` Wi-Fi sur
cet appareil). Branchez le câble sur le PC qui exécute le backend, puis :

```bash
# 1. Brancher le câble USB-C -> USB sur la tête Android
adb devices   # doit lister un device USB, ex: 1f4311e7d7

# 2. Test TTS direct
adb shell "am broadcast -n com.cybel.ttsbridge/.SpeakReceiver -a com.cybel.ttsbridge.SPEAK --es text 'Test vocal'"
```

Dans `backend/.env`, laissez `SPEECH_ADB_SERIAL` vide : Cybel utilise
automatiquement le premier appareil USB listé par `adb devices`.

<details>
<summary>Autres robots : ADB Wi-Fi (optionnel)</summary>

Sur certains modèles, on peut basculer en TCP après une première connexion USB :

```bash
adb -s <serial_usb> tcpip 5555
adb connect <ip_wifi>:5555
```

</details>

### Reconnexion ADB automatique (CYBEL Phase 6)

Le backend tente désormais automatiquement :

1. **`adb connect <SPEECH_ADB_SERIAL>`** avant chaque annonce TTS si l'appareil Wi-Fi n'est pas listé dans `adb devices`.
2. Un **health check toutes les 90 s** au démarrage du backend (lifespan FastAPI).
3. Un **diagnostic unifié** via `GET /api/diagnostics` et la page **Paramètres** du contrôleur.

Si le TTS reste muet, ouvrez Paramètres → Diagnostic et vérifiez la ligne **ADB TTS**.

## 5. Checklist après un redémarrage du robot

Un redémarrage du robot (châssis ou tête Android) peut casser un ou
plusieurs canaux :

| Symptôme | Cause probable | Action |
|----------|------------------|--------|
| Déplacement KO, carte ne charge plus | rosbridge (`10.42.0.1:9090`) pas encore prêt ou robot pas reconnecté au Wi-Fi | Attendre le démarrage complet, vérifier `ping 10.42.0.1`, redémarrer le backend |
| TTS muet, `adb devices` vide | Câble USB non branché sur le PC backend | Brancher USB, vérifier `adb devices` |
| TTS muet, device USB listé | App `CybelTTSBridge` absente ou TTS Android | Voir §6, réinstaller l'APK si besoin |

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

### 7.1 Résultat du test réel (2026-06-15)

- **TTS** : `POST /api/speech/say` → `200 OK`,
  `{"ok": true, "method": "adb-tts", ...}`. Robot a parlé (confirmé logcat :
  connexion à `GoogleTTSService` + `AudioTrack`).
- **Déplacement** : `POST /api/robot/move` (`angular_z=0.2` ~0.7s) puis
  `POST /api/robot/stop` → `200 OK` chacun, robot observé en rotation
  (confirmé visuellement), vélocité revenue à `[0, 0]` après stop.
- **Bug corrigé pendant ce test** : voir §6.2 ci-dessous
  (`NotImplementedError` sur `asyncio.create_subprocess_exec` côté TTS ADB).
- **Point d'attention relevé** : `localization_percent` ≈ 42–48 %
  (`"Faible"`, seuil "Faible" = `< 60`), `nav_status` reste à `600` ("En
  initialisation"). La téléopération directe (`/api/robot/move`) fonctionne
  malgré tout (commande `cmd_vel` bas niveau). La **navigation par point**
  (`/api/navigation/goto`) risque en revanche de rester bloquée tant que la
  localisation n'est pas meilleure — voir §6.3.

### 7.2 Bug Windows : TTS ADB renvoyait 500 (`NotImplementedError`)

`sdk/speech.py` utilisait `asyncio.create_subprocess_exec` pour lancer `adb`.
Sous Windows, uvicorn tourne sur `SelectorEventLoop`, qui ne supporte pas les
sous-processus asyncio → `NotImplementedError`, levée **après** la mise à
jour du statut (`last_method: "adb-tts"`) mais **avant** l'envoi réel du
broadcast. Résultat : `500 Internal Server Error` côté API, et le robot ne
parlait pas malgré un statut trompeur.

**Corrigé** dans `sdk/speech.py` (`_try_adb_speak`) : `adb` est maintenant
lancé via `asyncio.to_thread(subprocess.run, ...)`, indépendant du type de
boucle asyncio. Voir [docs/TTS_BRIDGE.md §7.2](TTS_BRIDGE.md#72-sdkspeechpy--nouvelle-méthode-_try_adb_speak)
pour le détail.

⚠️ Si une erreur similaire (`NotImplementedError` / 500 sur un endpoint qui
lance un sous-processus) réapparaît après une modification du code : vérifier
qu'aucun nouvel appel `asyncio.create_subprocess_*` n'a été introduit.

### 7.3 Localisation faible — piste pour plus tard

`sdk/constants.py` référence un service ROS `/global_localization`
(relocalisation globale, généralement une rotation sur place pour recaler le
lidar sur la carte) mais il n'est **pas encore câblé** dans
`sdk/real_robot.py`. Si la navigation par point reste bloquée en `nav_status
600`, ajouter un appel à ce service (ex. bouton "Relocaliser" dans l'UI) —
⚠️ ceci fera aussi tourner le robot.
