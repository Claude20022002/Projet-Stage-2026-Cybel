# CybelFaceBridge

App Android headless (aucune `Activity`, aucune icône de lancement) qui fait tourner
en continu la caméra frontale de la tablette pour reconnaître les visiteurs enrôlés
et personnaliser l'accueil kiosque ("Bonjour M./Mme X"). Voir
[`docs/FACE_PRESENCE.md`](../../docs/FACE_PRESENCE.md) pour le contexte produit.

Ne pas confondre avec la Phase 1 (détection de présence via la caméra du **châssis
robot**, topic ROS `/detected_people_array`) — ce bridge utilise la caméra de la
**tablette** elle-même, car la WebView Android 7.1/Chrome 49 du kiosque ne peut pas
exécuter de ML en JavaScript.

## Modèle vendorisé — FaceNet (David Sandberg), CASIA-WebFace/VGGFace2

`assets/face_embedding.tflite` est récupéré au build par `fetch_face_model.sh`
(comme le modèle Vosk du kiosque) — non committé dans git (23 Mo).

**Provenance (décision consciente, prise le 2026-07-17 avec l'équipe projet)** :
les modèles de reconnaissance faciale qui circulent publiquement ont presque
toujours une provenance de dataset discutable. Plusieurs tracent leur lignée
jusqu'à **MS-Celeb-1M**, un dataset que Microsoft a retiré en 2019 après des
controverses sur le consentement des personnes photographiées. Après recherche,
aucune alternative *prête à l'emploi* avec provenance irréprochable n'a été
trouvée : les jeux de données entièrement synthétiques (ex. `DigiFace-1M` de
Microsoft, créé en réponse directe à la controverse MS-Celeb-1M) existent mais
nécessitent d'entraîner soi-même un modèle — un chantier ML à part entière, pas
un fichier à télécharger.

Le modèle retenu ici est **FaceNet** ([davidsandberg/facenet](https://github.com/davidsandberg/facenet),
code sous licence MIT), avec les poids pré-entraînés sur **CASIA-WebFace** ou
**VGGFace2** — **pas** MS-Celeb-1M. Ce sont aussi des jeux de données collectés
sans consentement individuel explicite (constat général du domaine, pas
spécifique à ce choix), mais leur provenance est au moins documentée et connue,
contrairement à beaucoup de conversions `.tflite` qui circulent sans aucune
traçabilité. La conversion `.tflite` elle-même n'est pas publiée comme fichier
autonome ; `fetch_face_model.sh` l'extrait d'une release publique open-source
([shubham0204/OnDevice-Face-Recognition-Android](https://github.com/shubham0204/OnDevice-Face-Recognition-Android),
elle-même sourcée depuis la bibliothèque [`deepface`](https://github.com/serengil/deepface),
MIT), avec vérification SHA256.

**Prétraitement vérifié dans le code source amont** (`facenet.py`,
« fixed image standardization ») : `(pixel - 127.5) / 128.0` — reflété dans
`assets/face_embedding_config.json` :

```json
{
  "input_size": 160,
  "mean": 127.5,
  "std": 128.0,
  "output_dim": 128,
  "quantized": false,
  "l2_normalize": true
}
```

Le code (`FaceEmbedder.java`) lit les formes de tenseurs directement sur
l'interpréteur TFLite plutôt que de les coder en dur — seuls `mean`/`std`/
`quantized`/`l2_normalize` (non déductibles du modèle) viennent de ce fichier.

**Si vous préférez un autre modèle** (ex. un modèle entraîné en interne sur des
visiteurs consentants), remplacez simplement `assets/face_embedding.tflite` et
ajustez `face_embedding_config.json` en conséquence — rien d'autre à changer.

## Architecture

- **Aucune Activity** : `FaceRecognitionService` (foreground) + deux
  `BroadcastReceiver` (`BootReceiver`, `EnrollReceiver`). Ne peut donc jamais
  voler le focus écran au kiosque `CybelVisitorKiosk`.
- **Capture headless** (`CameraPipeline`) : Camera2 avec un unique `ImageReader`
  comme cible — pas de `SurfaceView`/`TextureView`. Throttle logiciel (~1
  frame/s) pour préserver batterie/CPU sur un kiosque qui tourne des heures.
- **Le téléphone fait tout le ML, le backend fait le matching** : l'app envoie
  uniquement un vecteur d'embedding (jamais une image) à
  `POST /api/visitors/identify` (backend local, toujours `127.0.0.1:8000`). La
  comparaison par similarité cosinus et le seuil (`face_recognition_threshold`)
  restent côté backend (`sdk/visitor_utils.py`), réglables via
  `PUT /api/kiosk/config` sans reconstruire l'APK.
- **Enrôlement** = même pipeline d'embedding que la reconnaissance en direct,
  déclenché par le personnel via `scripts/termux/enroll_visitor.sh` (broadcast
  `com.cybel.facebridge.ENROLL`) — jamais de capture automatique/silencieuse
  d'un visiteur non consentant.

## Provisioning (à faire manuellement)

```bash
# 1. Vendorer le modèle (voir avertissement ci-dessus)
cp /chemin/vers/votre_modele.tflite android/CybelFaceBridge/assets/face_embedding.tflite

# 2. Builder (nécessite ANDROID_HOME, comme CybelTTSBridge/CybelVisitorKiosk)
cd android/CybelFaceBridge
./build.sh

# 3. Installer
adb install -r out/CybelFaceBridge.apk

# 4. Accorder la permission caméra manuellement — pas d'Activity donc pas de
#    dialogue runtime possible
adb shell pm grant com.cybel.facebridge android.permission.CAMERA

# 5. Démarrer (ou redémarrer la tablette — BootReceiver le relance automatiquement)
adb shell am startservice -n com.cybel.facebridge/.FaceRecognitionService
```

`libs/tensorflow-lite-2.9.0.jar` (fusion des classes de `org.tensorflow:tensorflow-lite:2.9.0`
et `org.tensorflow:tensorflow-lite-api:2.9.0` — ce dernier fournit `InterpreterApi`/`Tensor`,
absents du premier jar seul) et `jniLibs/{arm64-v8a,armeabi-v7a}/libtensorflowlite_jni.so`
sont déjà vendorés (extraits des AAR officiels Maven Central, licence Apache 2.0 —
voir `libs/TENSORFLOW_LITE_LICENSE.txt`). Seul le modèle d'embedding manque.

> **Version 2.9.0, pas la dernière** : testé sur le châssis CIOT TY1251D-03195
> (Android 7.1.2/API 25) — les versions TFLite plus récentes (2.14.0 confirmé)
> référencent le symbole libc `strtod_l@LIBC_O`, introduit dans Bionic à partir
> d'API 26 (Android 8) : `UnsatisfiedLinkError: cannot locate symbol "strtod_l"`
> au chargement sur ce matériel. 2.9.0 ne dépend que de `strtod` (non versionné),
> compatible API 25. Si vous changez de version, vérifiez d'abord avec
> `readelf --dyn-syms libtensorflowlite_jni.so | grep strtod` qu'aucun symbole
> `@LIBC_O` (ou supérieur) n'apparaît.

## Validation terrain (2026-07-14, châssis CIOT TY1251D-03195 réel)

Testé en direct sur le robot (tablette RK3399 branchée en USB/ADB) avec un
modèle `.tflite` factice (données aléatoires, juste pour exercer le pipeline
caméra/détection — pas la reconnaissance elle-même). Plusieurs bugs réels ont
été trouvés et corrigés à cette occasion, invisibles sans le matériel :

| Constat | Bug trouvé | Statut |
|---------|-----------|--------|
| Une seule caméra physique, classée `BACK` par Android (pas `FRONT`) | `findBestCameraId()` ne cherchait que `FRONT` → échec silencieux garanti | ✅ Corrigé (repli sur la caméra disponible) |
| Ce capteur n'annonce qu'une plage 25-30 fps | `CONTROL_AE_TARGET_FPS_RANGE` codé en dur à (2,5) → risque d'échec `setRepeatingRequest` | ✅ Corrigé (plage lue dynamiquement) |
| TensorFlow Lite 2.14.0 crash au chargement (`UnsatisfiedLinkError: strtod_l`) | Symbole Bionic API26+, absent sur Android 7.1/API25 | ✅ Corrigé (passage à TFLite 2.9.0, voir note ci-dessus) |
| Ce crash tuait tout le service au lieu d'être ignoré | `catch (Exception e)` ne rattrape pas `UnsatisfiedLinkError` (un `Error`, pas une `Exception`) | ✅ Corrigé (`catch (Throwable t)`) |
| `getCameraCharacteristics()` pendant que la caméra est ouverte entre en conflit avec elle-même sur ce HAL LEGACY | Provoquait un `CAMERA_IN_USE` en boucle toutes les 5s | ✅ Corrigé (caractéristiques mises en cache, plus de second appel) |
| Plusieurs `scheduleReopen()` rapprochés s'empilaient sans s'annuler | Une connexion caméra fonctionnelle finissait détruite par une tentative en retard | ✅ Corrigé (callback unique, `removeCallbacks` avant `postDelayed`) |
| Conversion NV21→RGB565 (`ImageConversions`) | — | ✅ **Validée visuellement** : image nette, bien colorée, correctement orientée (capture réelle inspectée) |
| Détection de visage (`android.media.FaceDetector`) | — | ✅ **Validée** : détection répétée, confiance ~0.51, quand le visiteur est bien de face à 2-3 m |
| Cadrage caméra | Le module face (petit objectif + émetteur IR, au sommet de la tête du robot, distinct des deux "yeux" IR) est orienté de façon à ne cadrer un visage qu'à distance ~2-3 m ; à moins d'1 m il ne capte que le plafond/haut du mur | ⚠️ Contrainte terrain à communiquer à l'UX (afficher une invite "reculez-vous" ?) |

**Ce qui reste réellement non testé** (nécessite un vrai modèle `.tflite`) :
- Qualité des embeddings / précision de la reconnaissance (le test a validé la
  détection, pas l'identification — un modèle random ne produit rien
  d'exploitable).
- Heuristique de cadrage du visage avant embedding (`cropFaceRegion`,
  `eyesDistance()`/`getMidPoint()`) — non exercée par ce test.
- Comportement batterie/thermique sur plusieurs heures.
- `face_recognition_threshold` (défaut 0.82) — à calibrer avec de vrais scores
  de similarité une fois un modèle réel en place.
