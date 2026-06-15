# Synthèse vocale (TTS) — résolution et pont CybelTTSBridge

Documentation technique du travail effectué pour permettre au robot **CYBEL
(TY1251D-03195)** de prononcer un texte arbitraire (synthèse vocale / TTS) à
la demande de l'opérateur. Couvre l'investigation complète, les pistes
écartées, la solution retenue et son intégration dans le backend.

---

## Table des matières

1. [Contexte et problème initial](#1-contexte-et-problème-initial)
2. [Pistes explorées et écartées](#2-pistes-explorées-et-écartées)
3. [Accès ADB à la tête Android](#3-accès-adb-à-la-tête-android)
4. [Exploration des applications Android candidates](#4-exploration-des-applications-android-candidates)
5. [Validation du pipeline audio natif](#5-validation-du-pipeline-audio-natif)
6. [Solution retenue : CybelTTSBridge](#6-solution-retenue--cybelttsbridge)
7. [Intégration dans le backend CYBEL](#7-intégration-dans-le-backend-cybel)
8. [Tests réalisés](#8-tests-réalisés)
9. [Limites connues et points d'attention](#9-limites-connues-et-points-dattention)
10. [Pistes pour aller plus loin](#10-pistes-pour-aller-plus-loin)

---

## 1. Contexte et problème initial

La plateforme CYBEL doit pouvoir faire parler le robot (annonces d'accueil,
texte libre saisi par l'opérateur). `sdk/speech.py` (`RobotSpeech`) tentait
deux familles de canaux :

- **ROS/rosbridge** : publication sur une liste de topics candidats
  (`/play_tts`, `/robot_tts`, …) ou appel de services candidats (`/speak`,
  `/tts`, …) — voir `SPEECH_PUBLISH_TOPICS` / `SPEECH_SERVICES` dans
  `sdk/constants.py`.
- **HTTP** : requêtes GET/POST sur une liste de ports/chemins candidats vers
  `172.16.0.88` (IP supposée de la tête Android).

Aucun des deux canaux n'a jamais répondu : aucun topic ROS candidat n'a
d'abonné, aucun service candidat n'existe côté `rosapi`, et aucun port HTTP
n'était joignable sur `172.16.0.88`. Le texte saisi dans l'interface restait
donc muet (`{"ok": false, "error": "Aucun canal TTS ..."}`).

## 2. Pistes explorées et écartées

Avant d'obtenir un accès physique au robot, plusieurs pistes ont été testées
depuis le réseau du robot (`10.42.0.1` / Wi-Fi `172.16.0.x`) :

| Piste | Script | Résultat |
|-------|--------|----------|
| Brute-force SSH sur `csst@10.42.0.1` (mots de passe constructeur) | `scripts/ssh_csst.py`, `scripts/ssh_csst2.py` | Échec — le serveur SSH finit par limiter/abandonner les connexions (comportement type fail2ban) |
| Écoute passive du broker MQTT (`10.42.0.1:1883`, tous topics) | `scripts/mqtt_listen_passive.py` | Seul `test_mul` actif, payload d'odométrie châssis (`TY1251D-03195,-0.01,0.01,...`) — sans lien avec le TTS |
| Sonde HTTP sur `172.16.0.88` (ports 80/8080/8888/9000/9090, chemins `/tts`, `/api/tts`, …) | `_try_http_speak` | Aucun port ouvert |

**Conclusion à ce stade** : aucune API réseau (ROS, HTTP, MQTT) n'expose de
commande TTS exploitable depuis l'extérieur. Il fallait un accès direct au
système Android de la tête du robot.

## 3. Accès ADB à la tête Android

### 3.1 Activation côté robot (accès physique)

1. Activer les **options développeur** (taper 7× sur le numéro de build).
2. Activer **Débogage USB**.
3. Brancher un câble **USB-C → USB** entre le PC et le port de la tête
   Android (mode **USB Host/OTG** sélectionné côté robot).
4. Autoriser l'ordinateur sur la popup RSA affichée sur l'écran du robot.

### 3.2 Bascule USB → Wi-Fi

```bash
adb devices                     # confirme le device en USB (ex: 1f4311e7d7)
adb -s 1f4311e7d7 tcpip 5555     # bascule le démon adb en écoute TCP 5555
adb -s 1f4311e7d7 shell ip addr show wlan0   # récupère l'IP Wi-Fi actuelle
adb connect 172.16.0.194:5555    # connexion sans fil, câble débranchable
```

### 3.3 Découverte critique : l'IP documentée était périmée

La documentation/constantes du projet référençaient `172.16.0.88` pour la
tête Android. Une fois l'accès ADB obtenu (par USB), la commande
`ip addr show wlan0` a révélé que la tête Android répond en réalité sur
**`172.16.0.194`** (réattribution DHCP depuis l'exploration précédente).

➡️ Cela explique a posteriori l'échec de **toutes** les sondes HTTP : elles
visaient une IP qui n'est plus celle de la tête Android.

`SPEECH_HTTP_HOST` a été mis à jour de `172.16.0.88` → `172.16.0.194` dans
`sdk/constants.py` et `backend/config.py`.

## 4. Exploration des applications Android candidates

Avec l'accès `adb shell`, inventaire des paquets installés (`pm list
packages`) et inspection des plus pertinents (`dumpsys package <pkg>`) :

| Paquet | Rôle | Observations |
|--------|------|---------------|
| `com.ciot.welcomepatrol` (V3.0.1, uid 10096) | App « accueil/réception » CIOT | Service `MessengerUtils$ServerService` (action `com.ciot.welcomepatrol.messenger`) — IPC custom, format de message inconnu (nécessiterait une rétro-ingénierie de l'APK) |
| `com.ciot.sentrymove` (uid 10090) | App navigation/châssis | Même pattern `MessengerUtils$ServerService` (`com.ciot.sentrymove.messenger`) |
| `com.bjw.ComAssistant` (system, uid 10088) | Pont série Android ↔ MCU châssis | App système minimaliste (`minSdk=10`), pas de composant exporté exploitable directement |
| `com.google.android.tts` | Moteur **Google Text-to-Speech** | Présent et fonctionnel — confirmé via les réglages Android |
| `com.termux` | Terminal Linux | Présent, mais `com.termux.api` (requis pour `termux-tts-speak`) absent |

Les apps `com.ciot.welcomepatrol` / `com.ciot.sentrymove` exposent bien un
canal IPC « messenger », mais sans connaître le format de `Message`/`Bundle`
attendu par leur `Handler`, l'exploiter aurait nécessité de décompiler
l'APK (`base.apk`) — piste plus longue, gardée en réserve (§10).

## 5. Validation du pipeline audio natif

Avant de construire une solution, vérification que le moteur **Google TTS**
peut effectivement produire du son sur le robot :

```bash
adb shell am start -a com.android.settings.TTS_SETTINGS
adb shell uiautomator dump /sdcard/ui.xml
adb shell cat /sdcard/ui.xml   # repère le bouton "Listen to an example"
adb shell input tap 960 614    # tape sur "Listen to an example"
```

➡️ Confirme que `com.google.android.tts` est l'« Engine » TTS par défaut et
que le haut-parleur du robot est fonctionnel. Cet écran ne permet toutefois
de lire qu'une **phrase d'exemple fixe**, pas un texte arbitraire — d'où la
nécessité d'une app dédiée (§6).

## 6. Solution retenue : CybelTTSBridge

### 6.1 Principe

Une petite app Android (`android/CybelTTSBridge/`, package
`com.cybel.ttsbridge`) installée sur la tête du robot :

- expose un **`BroadcastReceiver`** exporté (`SpeakReceiver`) sur l'action
  `com.cybel.ttsbridge.SPEAK`, avec un extra texte `text` ;
- démarre un **`Service`** (`SpeakService`) qui initialise
  `android.speech.tts.TextToSpeech` (moteur Google TTS, locale FR), prononce
  le texte, puis s'arrête lui-même (`stopSelf`).

Déclenchement depuis n'importe quelle machine avec `adb` :

```bash
adb -s 172.16.0.194:5555 shell \
  "am broadcast -n com.cybel.ttsbridge/.SpeakReceiver \
   -a com.cybel.ttsbridge.SPEAK --es text 'Bonjour, je suis le robot Cybel'"
```

### 6.2 Build sans Gradle/Android Studio

`android/CybelTTSBridge/build.sh` construit et signe l'APK avec uniquement
les outils en ligne de commande du SDK (`$ANDROID_HOME/build-tools/35.0.0`,
`platforms/android-35`) :

1. `aapt2 link` — compile `AndroidManifest.xml` + ressources → APK non signé
   + génère `R.java`.
2. `javac` — compile `R.java` et les sources Java (`SpeakReceiver`,
   `SpeakService`) contre `android.jar`.
3. `d8` — convertit les `.class` en `classes.dex`.
4. `aapt add` — ajoute `classes.dex` dans l'APK.
5. `zipalign` — alignement de l'APK.
6. `keytool` (génère `debug.keystore` si absent) + `apksigner` — signature.

Résultat : `android/CybelTTSBridge/out/CybelTTSBridge.apk`.

### 6.3 Bug rencontré et corrigé : race condition `TextToSpeech`

Premier test : le broadcast démarrait bien le processus
`com.cybel.ttsbridge`, mais le logcat affichait :

```
TextToSpeech: Sucessfully bound to com.google.android.tts
TextToSpeech: speak failed: not bound to TTS engine
TextToSpeech: Connected to ComponentInfo{com.google.android.tts/...}
```

**Cause** : `tts.speak(...)` était appelé immédiatement dans
`onStartCommand()`, en se basant sur un test `tts == null` — or `tts` est
non-nul dès `new TextToSpeech(this, this)`, bien avant que la connexion au
moteur soit réellement prête.

**Correctif** (`SpeakService.java`) :

- ajout d'un drapeau `ttsReady`, mis à `true` uniquement dans
  `onInit(TextToSpeech.SUCCESS)` ;
- `speak()` met le texte en attente (`pendingText`) si `!ttsReady` ;
- dans `onInit`, le texte en attente est prononcé après un court délai
  (`Handler.postDelayed(..., 300)`) pour laisser la connexion au service se
  stabiliser.

### 6.4 Autre point bloquant : broadcast ignoré au premier essai

Un premier essai avec `am broadcast -a com.cybel.ttsbridge.SPEAK` (sans
composant explicite) n'a déclenché **aucun** démarrage de processus. Cause :
Android met les apps **jamais lancées** en état *stopped*, ce qui exclut
leurs receivers des broadcasts implicites.

**Solution** : cibler explicitement le composant avec `-n` :

```bash
am broadcast -n com.cybel.ttsbridge/.SpeakReceiver -a com.cybel.ttsbridge.SPEAK --es text '...'
```

(Le ciblage explicite par composant contourne le filtre « stopped
packages ».)

### 6.5 Validation finale

```bash
adb -s 172.16.0.194:5555 install -r android/CybelTTSBridge/out/CybelTTSBridge.apk
adb -s 172.16.0.194:5555 shell "am broadcast -n com.cybel.ttsbridge/.SpeakReceiver \
  -a com.cybel.ttsbridge.SPEAK --es text 'Bonjour, je suis le robot Cybel. Ceci est un test de synthese vocale.'"
```

Logcat confirme le cycle complet : démarrage du service → `Successfully
bound` / `Connected` à `GoogleTTSService` → création d'un `AudioTrack`
(lecture audio réelle) → arrêt propre du service (`stopSelf`). Le robot a
prononcé la phrase.

## 7. Intégration dans le backend CYBEL

### 7.1 `sdk/constants.py`

```python
# Upper body Android (RK3399) — fallback HTTP si ROS échoue
SPEECH_HTTP_HOST = "172.16.0.194"   # corrigé (était 172.16.0.88, IP périmée)
...
# TTS via la tête Android — app CybelTTSBridge installée sur l'appareil
SPEECH_ADB_SERIAL = "172.16.0.194:5555"
SPEECH_ADB_RECEIVER = "com.cybel.ttsbridge/.SpeakReceiver"
SPEECH_ADB_ACTION = "com.cybel.ttsbridge.SPEAK"
```

### 7.2 `sdk/speech.py` — nouvelle méthode `_try_adb_speak`

Nouveau canal essayé entre ROS et HTTP :

```python
async def _try_adb_speak(self, text: str) -> str | None:
    if not self._adb_serial:
        return None
    escaped = text.replace("'", "'\\''")
    remote_cmd = (
        f"am broadcast -n {SPEECH_ADB_RECEIVER} -a {SPEECH_ADB_ACTION} "
        f"--es text '{escaped}'"
    )
    result = await asyncio.to_thread(
        subprocess.run,
        ["adb", "-s", self._adb_serial, "shell", remote_cmd],
        capture_output=True,
        timeout=5.0,
    )
    ...
```

`RobotSpeech.speak()` essaie désormais, dans l'ordre :
**ROS/rosbridge → ADB (CybelTTSBridge) → HTTP**.

#### Bug rencontré lors du test réel : `NotImplementedError` sous Windows

Première implémentation avec `asyncio.create_subprocess_exec(...)`. En
lançant le backend réel via `python scripts/dev.py` (uvicorn, Windows), tout
appel à `/api/speech/say` renvoyait `500 Internal Server Error` :

```text
File ".../asyncio/base_events.py", line 539, in _make_subprocess_transport
    raise NotImplementedError
NotImplementedError
```

**Cause** : sous Windows, les méthodes subprocess d'`asyncio` ne sont
implémentées que par `ProactorEventLoop` ; uvicorn (avec `--reload`) tourne
sur `SelectorEventLoop`, qui ne les supporte pas. L'exception était levée
**après** l'appel à `_notify(text, "speaking", "adb-tts")`, donc le statut
affichait `last_method: "adb-tts"` alors que le broadcast ADB n'avait
**jamais été envoyé** (et `(OSError, asyncio.TimeoutError)` ne capturait pas
`NotImplementedError`).

**Correctif** : remplacer `asyncio.create_subprocess_exec` +
`proc.communicate()` par `asyncio.to_thread(subprocess.run, ...)` — exécute
`adb` dans un thread, ce qui fonctionne quel que soit le type de boucle
asyncio. `except (OSError, subprocess.TimeoutExpired)` remplace
`(OSError, asyncio.TimeoutError)`.

### 7.3 Correction d'un blocage architectural

`speak()` retournait auparavant `{"ok": false, "error": "Robot non
connecté"}` dès que `rosbridge` n'était pas connecté, **avant même** d'essayer
ADB/HTTP. Or le pont ADB ne dépend pas de rosbridge. La garde a été déplacée :
le canal ROS n'est tenté que **si** `self._client.connected`, mais ADB/HTTP
sont toujours tentés ensuite.

### 7.4 Plomberie de configuration

- `sdk/real_robot.py` : nouveau paramètre `speech_adb_serial` transmis à
  `RobotSpeech`.
- `backend/config.py` : nouveau réglage `speech_adb_serial: str = ""`
  (configurable via `.env`), et `speech_http_host` corrigé à
  `172.16.0.194`.
- `backend/services/robot_service.py` : transmet
  `settings.speech_adb_serial` au constructeur de `RealRobot`.

Si `speech_adb_serial` est vide, `RobotSpeech` retombe sur la constante
`SPEECH_ADB_SERIAL` (même mécanisme que `speech_http_host` /
`SPEECH_HTTP_HOST`).

## 8. Tests réalisés

| Test | Commande / méthode | Résultat |
|------|---------------------|----------|
| Broadcast direct ADB | `adb shell am broadcast -n com.cybel.ttsbridge/.SpeakReceiver -a com.cybel.ttsbridge.SPEAK --es text '...'` | OK — audio joué (AudioTrack créé), service arrêté proprement |
| Intégration SDK | `RobotSpeech(mock=False).speak("Bonjour, ceci est un test depuis le backend Cybel.")` (sans rosbridge connecté) | `{"ok": True, "method": "adb-tts", "text": "..."}` — audio joué |
| Import backend | `from backend.config import settings` + `RealRobot` | imports OK, `speech_http_host == "172.16.0.194"` |
| **Bout en bout (réel)** | `POST /api/speech/say` sur le backend lancé via `python scripts/dev.py` (`ROBOT_MOCK=false`, câble débranché) | `200 OK`, `{"ok": True, "method": "adb-tts", ...}` ; logcat confirme `TextToSpeech: Connected to ... GoogleTTSService` + `AudioTrack` ; robot a parlé |

## 9. Limites connues et points d'attention

- **IP DHCP instable** : `172.16.0.194` peut changer après un redémarrage du
  robot ou du point d'accès Wi-Fi. Si le TTS cesse de fonctionner, reconnecter
  en USB et relancer `adb shell ip addr show wlan0`, puis mettre à jour
  `SPEECH_ADB_SERIAL` (et `SPEECH_HTTP_HOST`) dans `sdk/constants.py` (ou
  `speech_adb_serial` dans `.env`).
- **Dépendance à `adb`** : la machine qui exécute le backend doit avoir `adb`
  sur le `PATH` et l'appareil déjà autorisé (clé RSA acceptée). Sans cela,
  `_try_adb_speak` échoue silencieusement (log `debug`) et le flux retombe sur
  HTTP.
- **Connexion ADB Wi-Fi persistante** : `adb connect` doit avoir été exécuté
  au moins une fois (et le daemon `adbd` du robot doit être en mode `tcpip`) —
  cet état ne survit pas forcément à un reboot du robot (`adbd` peut revenir
  en mode USB only). Prévoir un script de reconnexion si nécessaire.
- **Locale figée en français** (`tts.setLanguage(Locale.FRENCH)`) — à adapter
  si le robot doit parler dans une autre langue.
- **Pas de file d'attente** : chaque broadcast utilise `QUEUE_FLUSH`, donc un
  nouveau texte interrompt le précédent (comportement voulu, cohérent avec
  `interrupt=True` côté `RobotSpeech.speak`).

## 10. Pistes pour aller plus loin

- **Décompiler `com.ciot.welcomepatrol`** (`adb pull
  /data/app/com.ciot.welcomepatrol-1/base.apk` + `jadx`) pour documenter le
  format de message attendu par `MessengerUtils$ServerService`
  (`com.ciot.welcomepatrol.messenger`). Si exploitable, permettrait de
  déclencher les animations/comportements « accueil » natifs en plus de la
  voix.
- **Démarrage automatique du pont** : ajouter un `BOOT_COMPLETED` receiver à
  `CybelTTSBridge` pour pré-chauffer `TextToSpeech` au démarrage de la tête
  Android (réduit la latence du premier énoncé).
- **Script de reconnexion ADB** : petit script `scripts/adb_reconnect.py` qui
  détecte l'IP Wi-Fi actuelle via USB et relance `adb connect` automatiquement
  au démarrage du backend.
