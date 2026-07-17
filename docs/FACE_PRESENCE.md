# Reconnaissance faciale et détection de présence

> **Branche :** `feature/face-presence`  
> **Référence backlog :** CYB-073 · APK constructeur : `WelcomeManager.onFindFace`

---

## Objectif

1. **Phase 1 — Présence** (implémentée) : détecter qu'un visiteur s'approche du robot et réveiller le kiosque (veille → accueil + TTS).
2. **Phase 2 — Reconnaissance faciale** (validée terrain, 2026-07-17) : identifier un visiteur enregistré, personnaliser l'accueil, et proposer une visite.

Les deux déclencheurs (présence châssis, reconnaissance faciale tablette)
alimentent désormais le **même point d'entrée** côté kiosque
(`tryGreetAndOfferTour()`, `frontend-kiosk/src/app.ts`), avec un cooldown
partagé — un visiteur détecté par les deux systèmes à quelques instants
d'écart n'est salué qu'une fois. Après l'accueil, le robot propose
systématiquement une visite (voir
[VOICE_CHATBOT.md § Dialogue proactif](VOICE_CHATBOT.md#dialogue-proactif--proposition-de-visite)).

---

## Phase 1 — Détection de présence (implémentée)

### Source

Topic ROS **`/detected_people_array`** (caméra du châssis robot), déjà exploité sur le dashboard opérateur.

### Chaîne

```
/detected_people_array  →  cybel_lite (_people_listener_loop)
       →  WebSocket /ws/telemetry  { type: "people", people: [...] }
       →  frontend-kiosk (handlePresenceWelcome)
```

### Comportement kiosque

| Condition | Action |
|-----------|--------|
| Visiteur à ≤ `presence_max_distance_m` (défaut 3 m) | Sortie veille → écran accueil |
| `presence_speak_welcome: true` | TTS message de bienvenue (`welcome_message_fr/en`) |
| Cooldown `presence_cooldown_seconds` (défaut 90 s) | Évite les annonces en boucle |

### Configuration (`data/kiosk_config.json`)

```json
{
  "presence_welcome_enabled": true,
  "presence_max_distance_m": 3.0,
  "presence_cooldown_seconds": 90,
  "presence_speak_welcome": true,
  "face_recognition_enabled": false
}
```

### API

| Endpoint | Description |
|----------|-------------|
| `GET /api/robot/people` | Liste courante des personnes détectées |
| WebSocket `type: "people"` | Flux temps réel (~1,5 s) |

### Vérification terrain

```powershell
adb forward tcp:18001 tcp:8001
curl http://127.0.0.1:18001/api/robot/people
```

Placez-vous devant le robot : le tableau `people` doit contenir au moins une entrée avec `distance` faible.

---

## Phase 2 — Reconnaissance faciale (validée terrain)

> **État réel (2026-07-17)** : pipeline complet validé de bout en bout sur le
> châssis CIOT TY1251D-03195 avec un **vrai modèle d'embedding** (FaceNet,
> voir provenance ci-dessous) — enrôlement, embedding, matching backend et
> identification continue tous confirmés fonctionnels sur device. Le
> 2026-07-14, seule la chaîne caméra → détection avait été validée (modèle
> factice, données aléatoires) ; l'identification elle-même restait bloquée
> sur l'absence de modèle réel.

### Contraintes

- WebView Android 7.1 : pas de ML dans le JS du kiosque → nécessite une app Android
  native dédiée (`CybelFaceBridge`), séparée du kiosque WebView.
- L'APK constructeur utilise **Iflytek local** (`WelcomeManager.onFindFace`) — non exposé via ROS.

### Architecture retenue

| Composant | Rôle | État |
|-----------|------|------|
| App Android **`CybelFaceBridge`** (`android/CybelFaceBridge/`) | Capture caméra tablette (Camera2 headless, sans preview), détection (`android.media.FaceDetector`) + embedding (TensorFlow Lite, FaceNet) | ✅ **Validé sur le châssis réel** : caméra, détection, embedding, identification continue |
| `sdk/visitor_utils.py` | Similarité cosinus + seuil, sans pydantic (partagé backend PC / Termux lite) | ✅ Testé (`tests/unit/test_visitor_utils.py`) |
| `data/visitors.json` | Annuaire visiteurs (nom, embedding, consentement) — jamais d'image stockée | ✅ |
| `POST /api/visitors/identify` | Reçoit l'embedding calculé par le bridge, renvoie `{ ok, visitor, confidence }` ; diffuse `{type:"face_status"}` (détecté/matché, sans image) même sans correspondance | ✅ Testé + validé terrain |
| `POST /api/visitors/enroll` | Enrôlement (refuse sans `consent: true`) | ✅ Testé + validé terrain |
| `POST /api/visitors/enroll-trigger` (`cybel_lite.py`) + relais `backend/` | Déclenche l'enrôlement à distance (`am broadcast` local sur la tablette) depuis l'interface opérateur PC, sans accès ADB direct | ✅ Testé (unitaire, relais mocké) |
| `scripts/termux/enroll_visitor.sh` | Déclenche l'enrôlement en local (ADB/Termux direct) | ✅ Validé terrain |
| `frontend/` — onglet **Visiteurs** | Enrôlement à distance, statut de détection en direct (sans image), liste + suppression | ✅ Codé et testé (tsc/build) ; usage réel nécessite `backend/` lancé depuis un PC sur le Wi-Fi du robot |
| Kiosque (`frontend-kiosk`) | « Bonjour M./Mme X » + proposition de visite si `face_recognition_enabled` et identité fraîche (`type: "visitor"` sur `/ws/telemetry`) | ✅ Validé terrain |

Le téléphone fait tout le calcul ML ; seul un **vecteur d'embedding** (jamais une image)
transite vers le backend, qui fait le matching et applique le seuil
`face_recognition_threshold` (réglable via `PUT /api/kiosk/config`, pas besoin de
rebuilder l'APK pour ajuster la sensibilité).

### Modèle vendorisé — provenance

Les modèles de reconnaissance faciale pré-entraînés qui circulent publiquement ont
souvent une provenance de licence/dataset floue (plusieurs tracent leur lignée
jusqu'à MS-Celeb-1M, retiré par Microsoft en 2019 pour des raisons de consentement).
Après recherche (2026-07-17), aucune alternative *prête à l'emploi* avec
provenance irréprochable n'a été trouvée — les jeux de données synthétiques
existent (ex. `DigiFace-1M` de Microsoft) mais nécessitent d'entraîner un
modèle soi-même, un chantier ML à part entière.

Le modèle retenu est **FaceNet** ([davidsandberg/facenet](https://github.com/davidsandberg/facenet),
code MIT), poids **CASIA-WebFace/VGGFace2** — **pas** MS-Celeb-1M. Récupéré et
vérifié (SHA256) par `android/CybelFaceBridge/fetch_face_model.sh` (non
committé, comme le modèle Vosk) depuis une release Android open-source
publique qui le vendore comme asset. Détail complet, y compris pourquoi ce
choix reste un compromis assumé plutôt qu'une solution parfaite :
[`android/CybelFaceBridge/README.md`](../android/CybelFaceBridge/README.md).

### Comment tester

**Ce qui se teste dès maintenant, sans tablette ni robot** (logique de matching) :

```powershell
pytest tests/unit/test_visitor_utils.py tests/unit/test_visitors_router.py -q

# ou en conditions réelles (backend PC démarré, ROBOT_MOCK peu importe) :
python scripts/dev.py
curl -X POST http://localhost:8000/api/visitors/enroll `
  -H "Content-Type: application/json" `
  -d '{"name":"Test","embedding":[1.0,0.0,0.0],"consent":true}'
curl -X POST http://localhost:8000/api/visitors/identify `
  -H "Content-Type: application/json" `
  -d '{"embedding":[1.0,0.0,0.0],"confidence":0.9}'
# -> {"ok":true,"visitor":{"name":"Test",...},"confidence":1.0}
```

**Ce qui a été fait sur la tablette physique (2026-07-14)** :

1. `adb shell pm grant com.cybel.facebridge android.permission.CAMERA` (pas de dialogue
   runtime possible — app headless sans Activity).
2. `adb logcat -s CybelFaceService:* CybelCameraPipeline:*` pour observer la caméra en direct.
3. Build+install avec un modèle `.tflite` factice (données aléatoires) — suffisant pour
   valider caméra/détection, pas l'identification elle-même.
4. Capture d'une frame réelle (`getExternalFilesDir` + `adb pull`) pour inspection
   visuelle directe — a permis de découvrir que le module caméra dédié (au sommet de
   la tête du robot, distinct des deux "yeux" IR) ne cadre un visage qu'à ~2-3 m,
   pas en dessous d'1 m.
5. Détection de visage confirmée (`android.media.FaceDetector`, confiance ~0.51,
   répétée sur plusieurs frames) à bonne distance, visiteur de face.

**Ce qui a été fait sur la tablette physique avec le vrai modèle (2026-07-17)** :

1. `fetch_face_model.sh` exécuté, modèle FaceNet vérifié (SHA256) et vendoré.
2. Build+install avec le vrai modèle — log `CybelFaceEmbedder: Modèle chargé :
   input=160x160 output_dim=128 quantized=false` confirmé au démarrage.
3. Enrôlement déclenché (`am broadcast` → `EnrollReceiver`, fenêtre 15 s) —
   visage détecté (confiance ~0.51), embedding calculé, `POST
   /api/visitors/enroll` réussi.
4. **Identification continue confirmée** : `GET /api/visitors/current` reflète
   le visiteur enrôlé en continu tant qu'il reste face caméra
   (`last_identified_at` avancé à chaque cycle, ~1/s).
5. Accueil personnalisé kiosque exercé (« Bonjour {nom} ! ») une fois
   `face_recognition_enabled: true` — nécessitait un correctif : la
   proposition n'était déclenchée que par la détection de présence châssis
   (système séparé de la caméra tablette), jamais par l'identification faciale
   elle-même. Voir `tryGreetAndOfferTour()` (déclenchement unifié).
6. `face_recognition_threshold` (défaut 0.82) non encore calibré avec des cas
   négatifs réels (plusieurs personnes enrôlées, distinction entre elles) —
   voir onglet **Visiteurs** de `frontend/` pour ce test.

### Bugs trouvés et corrigés grâce au test terrain

Invisibles depuis l'environnement de développement — seul le matériel réel les a révélés :

| Bug | Cause | Correctif |
|-----|-------|-----------|
| Aucune caméra trouvée | Le code cherchait uniquement `LENS_FACING_FRONT` ; ce robot n'expose qu'une caméra, classée `BACK` | Repli sur la caméra disponible si aucune `FRONT` |
| Risque d'échec `setRepeatingRequest` | Plage FPS `(2,5)` codée en dur, incompatible avec les 25-30 fps annoncés par ce capteur | Plage lue dynamiquement sur les caractéristiques caméra |
| Crash total du service au démarrage | TensorFlow Lite 2.14.0 référence un symbole libc (`strtod_l@LIBC_O`) introduit à l'API 26 ; absent sur Android 7.1/API 25 | Passage à TensorFlow Lite 2.9.0 (sans cette dépendance) |
| Ce crash n'était pas rattrapé | `UnsatisfiedLinkError` hérite de `Error`, pas `Exception` — le `catch` ne le voyait pas | `catch (Throwable t)` autour du chargement du modèle |
| `CAMERA_IN_USE` en boucle toutes les 5s malgré une caméra fonctionnelle | Deux causes cumulées : `getCameraCharacteristics()` rappelé pendant que la caméra est déjà ouverte entre en conflit avec elle-même sur ce HAL LEGACY ; et les tentatives de réouverture programmées s'empilaient sans s'annuler | Caractéristiques mises en cache (pas de second appel) + callback de réouverture unique (`removeCallbacks` avant `postDelayed`) |

Détail complet : [`android/CybelFaceBridge/README.md`](../android/CybelFaceBridge/README.md).

---

## Tests unitaires

```powershell
pytest tests/unit/test_people_utils.py -q
pytest tests/unit/test_visitor_utils.py tests/unit/test_visitors_router.py -q
```

---

## Liens

- [VOICE_CHATBOT.md](VOICE_CHATBOT.md) — chatbot vocal + dialogue proactif de visite (chantier jumeau)
- [../android/CybelFaceBridge/README.md](../android/CybelFaceBridge/README.md) — app Android, provisioning, limites connues
- [labo/POI_LABOV2.md](labo/POI_LABOV2.md) — référence POI carte laboV2
- [AUDIT_APK_CONSTRUCTEUR.md](cybel-conception/AUDIT_APK_CONSTRUCTEUR.md) — `onFindFace`
