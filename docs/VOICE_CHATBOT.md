# Chatbot vocal — parler au robot

> **Branche :** `feature/face-presence` · **Vosk STT** hors-ligne + moteur NLU réutilisé

Permet à un visiteur de **parler au robot** pour déclencher des actions déjà
implémentées : aller à un point (POI), lancer la visite guidée, retour charge,
ou poser une question sur HESTIM (FAQ). Le robot répond vocalement (TTS existant)
et affiche l'échange à l'écran.

## Vue d'ensemble

```
Visiteur touche 🎤  →  window.CybelVoice.startListening(lang)   (pont natif)
     →  Vosk STT hors-ligne (app CybelVisitorKioskTest)          [natif Android]
     →  window.__cybelVoiceResult(transcript, ok)                (retour WebView)
     →  POST /api/voice {text, lang}                             [kiosque JS]
     →  handle_voice_command : action / navigation POI / FAQ     [backend cybel_lite]
     →  exécute (TTS, navigation…) + WebSocket {type:"voice"}
     →  bulle réponse à l'écran + robot parle
```

**Principe** : le **STT est natif** (la WebView Chrome 49/Android 7.1 ne peut pas
faire de ML en JS), le **NLU est backend** (moteur partagé, réglable sans rebuild
APK), l'**UI est web** (bouton + overlay dans le kiosque).

## Ce qui est reconnu

| Exemple de phrase | Résultat |
|-------------------|----------|
| « emmène-moi à l'accueil », « va au poste machine » | Navigation vers le POI |
| « lance la visite guidée » | Démarre la visite (`/api/tour/start`) |
| « retour à la borne », « recharge » | Retour station de charge |
| « arrête », « stop » | Interrompt navigation/annonces |
| « qu'est-ce que HESTIM ? » | Réponse FAQ parlée |
| (non reconnu) | « Je n'ai pas compris… » |

Le matching vit dans **`sdk/voice_commands.py`** (`match_voice_command`,
`match_point_navigation`, `VOICE_COMMAND_MAP`) — module **sans pydantic**, partagé
entre le backend PC et le backend Termux. La FAQ passe par `sdk/knowledge_engine.py`.

## Composants

| Composant | Rôle | État |
|-----------|------|------|
| `sdk/voice_commands.py` | Matching commande/POI, normalisation (sans pydantic) | ✅ Testé (`test_voice_commands.py`) |
| `scripts/termux/cybel_lite.py` | `POST /api/voice` → `handle_voice_command` (réutilise `execute_action`, `navigate_to_point`, FAQ) | ✅ Testé via shim (chargement sans pydantic vérifié) |
| `backend/main.py` | Alias `/api/voice` (parité PC, contrat unique) | ✅ Testé live (curl) |
| `frontend-kiosk` | Bouton 🎤 + overlay écoute/réponse, `api.voice()`, WebSocket `type:"voice"` | ✅ `tsc`/build OK + rendu visuel validé |
| `android/CybelVisitorKioskTest` | Pont `CybelVoice` (`@JavascriptInterface`) + `VoiceRecognizer` (Vosk) | ✅ Build APK validé ; **STT sur device non encore testé** |

## Speech-to-text (Vosk)

- **Modèle** : `vosk-model-small-fr-0.22` (~41 Mo, **Apache 2.0**, provenance
  documentée — corpus publics). Contrairement au modèle de reconnaissance
  faciale, sa licence et ses données d'entraînement sont claires : il est
  récupéré et vérifié automatiquement au build (`fetch_vosk_model.sh`, SHA256),
  pas de sourcing manuel. Non committé dans git (41 Mo) mais turnkey.
- **Runtime vendorisé** dans `android/CybelVisitorKioskTest/libs/` +
  `jniLibs/{arm64-v8a,armeabi-v7a}/` : `vosk-android` 0.3.47 + JNA 5.13.0
  (jars fusionnés + `libvosk.so`/`libjnidispatch.so`), extraits des AAR Maven.
- Le modèle est copié d'`assets/` vers `filesDir` au premier lancement (Vosk a
  besoin d'un vrai répertoire), avec un marqueur pour éviter la recopie des
  41 Mo à chaque démarrage.

## Déclenchement

- **v1 (implémenté)** : bouton micro « Parler au robot » sur l'écran d'accueil
  (push-to-talk). Le bouton n'apparaît que si le pont natif `window.CybelVoice`
  est présent (masqué dans un navigateur classique).
- **v2 (prévu)** : mot d'éveil « Hé Cybel » (Vosk supporte la détection de
  mot-clé) — après validation de la latence/fiabilité en conditions réelles.

## Installation / test (nécessite le robot en USB/ADB)

**Script tout-en-un** (recommandé sur site) :

```bash
# Backend (code + UI) + validation automatique du moteur vocal :
scripts/deploy_voice_face.sh

# + déployer le STT vocal sur la tablette (build APK, install, permission micro) :
scripts/deploy_voice_face.sh --apk

# + reconnaissance faciale (nécessite le modèle .tflite fourni) :
scripts/deploy_voice_face.sh --all
```

Le script (voir `scripts/deploy_voice_face.sh`) : préflight ADB, build kiosque,
push code (`cybel_lite.py` + `sdk/` + `dist/`) vers `~/cybel-test/`, redémarrage
backend via RUN_COMMAND, puis **validation `/api/voice`** (4 cas : POI, visite,
stop, non reconnu). Avec `--apk`/`--face` : build+install APK + permissions +
relance. Auto-détecte le propriétaire Termux (robuste aux réinstallations).

**Manuellement**, si besoin :

```bash
# 1. Build (récupère le modèle Vosk automatiquement, nécessite ANDROID_HOME + internet PC)
cd android/CybelVisitorKioskTest && ./build.sh

# 2. Installer + accorder le micro (pas de dialogue runtime en mode kiosque)
adb install -r out/CybelVisitorKioskTest.apk
adb shell pm grant com.cybel.visitorkiosk.test android.permission.RECORD_AUDIO

# 3. Observer le STT en direct
adb logcat -s CybelVoice:* CybelKioskTest:*
# → toucher 🎤 sur l'écran, parler, vérifier le transcript puis l'action
```

**Test du moteur NLU sans micro ni robot** (dev PC) :

```powershell
python scripts/dev.py
# puis, en UTF-8 :
python -c "import urllib.request,json; d=json.dumps({'text':'va à la porte labo','lang':'fr'}).encode(); print(urllib.request.urlopen(urllib.request.Request('http://localhost:8000/api/voice',d,{'Content-Type':'application/json'})).read().decode())"
```

## Reste à valider sur le terrain

- Qualité du STT Vosk FR sur le micro réel de la tablette (bruit du labo, distance).
- Latence bout-en-bout (parole → action).
- Ajustement éventuel de `VOICE_COMMAND_MAP` / `_NAV_PATTERN` selon les formulations
  réelles des visiteurs.
- Mot d'éveil (v2).

## Liens

- [FACE_PRESENCE.md](FACE_PRESENCE.md) — reconnaissance faciale (chantier jumeau)
- [ARCHITECTURE_LOGICIELLE.md](ARCHITECTURE_LOGICIELLE.md) — SDK, backends
- [TTS_BRIDGE.md](TTS_BRIDGE.md) — synthèse vocale (le robot parle)
