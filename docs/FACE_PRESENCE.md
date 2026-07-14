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

> **État réel (2026-07-14)** : le pipeline complet est codé (app Android, backend PC,
> backend embarqué, kiosque). Le **matching backend est vérifié** (tests unitaires +
> HTTP réel) et surtout, **le pipeline caméra → conversion → détection de visage a été
> validé en direct sur le châssis CIOT TY1251D-03195** (tablette branchée en USB/ADB) :
> détection de visage confirmée (confiance ~0.51) à 2-3 m de distance. Cinq bugs réels
> ont été trouvés et corrigés à cette occasion (voir tableau ci-dessous et
> [`android/CybelFaceBridge/README.md`](../android/CybelFaceBridge/README.md)).
> Seule l'**identification** (avec un vrai modèle `.tflite`) reste non testée.

### Contraintes

- WebView Android 7.1 : pas de ML dans le JS du kiosque → nécessite une app Android
  native dédiée (`CybelFaceBridge`), séparée du kiosque WebView.
- L'APK constructeur utilise **Iflytek local** (`WelcomeManager.onFindFace`) — non exposé via ROS.

### Architecture retenue

| Composant | Rôle | État |
|-----------|------|------|
| App Android **`CybelFaceBridge`** (`android/CybelFaceBridge/`) | Capture caméra tablette (Camera2 headless, sans preview), détection (`android.media.FaceDetector`) + embedding (TensorFlow Lite) | ✅ **Validé sur le châssis réel** : caméra, conversion image, détection de visage tous confirmés fonctionnels |
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

**Reste à faire** : `scripts/termux/enroll_visitor.sh` + `GET /api/visitors/current` +
accueil personnalisé kiosque n'ont pas encore été exercés sur device (nécessitent un
vrai modèle `.tflite` pour produire des embeddings exploitables).

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

- [FACE_PRESENCE.md](FACE_PRESENCE.md) — détection de présence (branche en cours)
- [../android/CybelFaceBridge/README.md](../android/CybelFaceBridge/README.md) — app Android, provisioning, limites connues
- [labo/POI_LABOV2.md](labo/POI_LABOV2.md) — référence POI carte laboV2
- [AUDIT_APK_CONSTRUCTEUR.md](cybel-conception/AUDIT_APK_CONSTRUCTEUR.md) — `onFindFace`
