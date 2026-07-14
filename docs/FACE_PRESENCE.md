# Reconnaissance faciale et détection de présence

> **Branche :** `feature/face-presence`  
> **Référence backlog :** CYB-073 · APK constructeur : `WelcomeManager.onFindFace`

---

## Objectif

1. **Phase 1 — Présence** (implémentée) : détecter qu'un visiteur s'approche du robot et réveiller le kiosque (veille → accueil + TTS).
2. **Phase 2 — Reconnaissance faciale** (scaffolding implémenté, validation terrain restante) : identifier un visiteur enregistré et personnaliser l'accueil.

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

## Phase 2 — Reconnaissance faciale (scaffolding implémenté)

> **État réel (juillet 2026)** : le pipeline complet est codé (app Android, backend PC,
> backend embarqué, kiosque) et le **matching backend est vérifié** (tests unitaires +
> test manuel via HTTP réel, voir plus bas). Le **pipeline caméra/détection/embedding
> sur tablette n'a pas pu être validé** faute d'accès à la tablette physique et de
> modèle `.tflite` réel — voir « Reste à valider sur le terrain ».

### Contraintes

- WebView Android 7.1 : pas de ML dans le JS du kiosque → nécessite une app Android
  native dédiée (`CybelFaceBridge`), séparée du kiosque WebView.
- L'APK constructeur utilise **Iflytek local** (`WelcomeManager.onFindFace`) — non exposé via ROS.

### Architecture retenue

| Composant | Rôle | État |
|-----------|------|------|
| App Android **`CybelFaceBridge`** (`android/CybelFaceBridge/`) | Capture caméra frontale tablette (Camera2 headless, sans preview), détection (`android.media.FaceDetector`) + embedding (TensorFlow Lite) | Code complet, build testé de bout en bout ; **runtime caméra/détection non testé sur device réel** |
| `sdk/visitor_utils.py` | Similarité cosinus + seuil, sans pydantic (partagé backend PC / Termux lite) | ✅ Testé (`tests/unit/test_visitor_utils.py`) |
| `data/visitors.json` | Annuaire visiteurs (nom, embedding, consentement) — jamais d'image stockée | ✅ |
| `POST /api/visitors/identify` | Reçoit l'embedding calculé par le bridge, renvoie `{ ok, visitor, confidence }` | ✅ Testé (unitaire + HTTP réel) |
| `POST /api/visitors/enroll` | Enrôlement (refuse sans `consent: true`) | ✅ Testé |
| `scripts/termux/enroll_visitor.sh` | Déclenche l'enrôlement côté personnel (`am broadcast` → `EnrollReceiver`) | ✅ Code écrit, non exécuté sur device |
| Kiosque (`frontend-kiosk`) | « Bonjour M./Mme X » si `face_recognition_enabled` et identité fraîche (`type: "visitor"` sur `/ws/telemetry`) | ✅ Compile, non testé visuellement |

Le téléphone fait tout le calcul ML ; seul un **vecteur d'embedding** (jamais une image)
transite vers le backend, qui fait le matching et applique le seuil
`face_recognition_threshold` (réglable via `PUT /api/kiosk/config`, pas besoin de
rebuilder l'APK pour ajuster la sensibilité).

### Pourquoi aucun modèle `.tflite` n'est fourni

Les modèles de reconnaissance faciale pré-entraînés qui circulent publiquement ont
souvent une provenance de licence/dataset floue (plusieurs tracent leur lignée
jusqu'à MS-Celeb-1M, retiré par Microsoft en 2019 pour des raisons de consentement).
Le choix du modèle reste donc une décision volontaire à prendre en connaissance de
cause — voir [`android/CybelFaceBridge/README.md`](../android/CybelFaceBridge/README.md).
`build.sh` refuse de builder tant qu'aucun modèle n'est placé dans `assets/`.

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

**Ce qui nécessite la tablette physique** (non fait) :

1. Fournir un vrai modèle `.tflite` dans `android/CybelFaceBridge/assets/`.
2. `cd android/CybelFaceBridge && ./build.sh` puis `adb install -r out/CybelFaceBridge.apk`.
3. `adb shell pm grant com.cybel.facebridge android.permission.CAMERA` (pas de dialogue
   runtime possible — app headless sans Activity).
4. `adb logcat -s CybelFaceService:* CybelCameraPipeline:* CybelFaceEmbedder:*` pour
   observer la détection/embedding en direct.
5. `scripts/termux/enroll_visitor.sh "Nom Test" "M."` puis se placer devant la caméra.
6. Vérifier `GET /api/visitors/current` et l'accueil personnalisé sur le kiosque.

### Reste à valider sur le terrain

- Conversion NV21→RGB565 manuelle sur les vraies données du capteur RK3399.
- Heuristique de cadrage du visage (`FaceDetector` ne donne pas de rectangle, seulement
  `eyesDistance()`/`getMidPoint()`) — probablement à ajuster visuellement.
- Bitness tablette (32 vs 64 bits) — `arm64-v8a` et `armeabi-v7a` vendorés par précaution.
- `face_recognition_threshold` (défaut 0.82) — démarrer conservateur, ajuster après
  observation de scores réels.

---

## Tests unitaires

```powershell
pytest tests/unit/test_people_utils.py -q
pytest tests/unit/test_visitor_utils.py tests/unit/test_visitors_router.py -q
```

---

## Liens

- [FACE_PRESENCE.md](FACE_PRESENCE.md) — détection de présence (branche en cours)
- [../android/CybelFaceBridge/README.md](../android/CybelFaceBridge/README.md) — app Android, provisioning, limites connues
- [labo/POI_LABOV2.md](labo/POI_LABOV2.md) — référence POI carte laboV2
- [AUDIT_APK_CONSTRUCTEUR.md](cybel-conception/AUDIT_APK_CONSTRUCTEUR.md) — `onFindFace`
