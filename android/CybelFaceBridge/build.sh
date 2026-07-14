#!/usr/bin/env bash
# Builds and signs CybelFaceBridge.apk using only Android SDK command-line tools
# (no Gradle/Android Studio required) — same recipe as CybelTTSBridge/CybelVisitorKiosk,
# extended to vendor the TensorFlow Lite runtime (jar + native libs) and the model asset.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$DIR/out"

if [ ! -f "$DIR/assets/face_embedding.tflite" ]; then
  echo "ERREUR: assets/face_embedding.tflite manquant."
  echo "Ce build refuse de continuer sans modèle fourni — voir README.md"
  echo "(aucun modèle pré-entraîné n'est téléchargé automatiquement par ce script)."
  exit 1
fi

if [ -z "${ANDROID_HOME:-}" ]; then
  echo "ERREUR: ANDROID_HOME non défini"
  exit 1
fi
ANDROID_HOME="${ANDROID_HOME//\\//}"

BUILD_TOOLS_VER="35.0.0"
PLATFORM_VER="android-35"

ANDROID_JAR="$ANDROID_HOME/platforms/$PLATFORM_VER/android.jar"
BUILD_TOOLS="$ANDROID_HOME/build-tools/$BUILD_TOOLS_VER"
AAPT2="$BUILD_TOOLS/aapt2.exe"
AAPT="$BUILD_TOOLS/aapt.exe"
D8="$BUILD_TOOLS/d8.bat"
ZIPALIGN="$BUILD_TOOLS/zipalign.exe"
APKSIGNER="$BUILD_TOOLS/apksigner.bat"

TFLITE_JAR="$DIR/libs/tensorflow-lite-2.14.0.jar"
if [ ! -f "$TFLITE_JAR" ]; then
  echo "ERREUR: $TFLITE_JAR manquant (vendoring TensorFlow Lite incomplet — voir README.md)"
  exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT/gen" "$OUT/obj"

echo "== 1/8 Linking resources + manifest + assets =="
"$AAPT2" link -o "$OUT/facebridge-unaligned.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$DIR/AndroidManifest.xml" \
  -A "$DIR/assets" \
  --java "$OUT/gen"

echo "== 2/8 Compiling Java sources =="
javac -source 8 -target 8 \
  -cp "$ANDROID_JAR:$TFLITE_JAR" \
  -d "$OUT/obj" \
  "$OUT/gen/com/cybel/facebridge/R.java" \
  "$DIR"/src/com/cybel/facebridge/*.java

echo "== 3/8 Converting to dex (nos classes + runtime TensorFlow Lite) =="
mapfile -t CLASS_FILES < <(find "$OUT/obj" -name '*.class' -print)
"$D8" --output "$OUT" --lib "$ANDROID_JAR" "${CLASS_FILES[@]}" "$TFLITE_JAR"

echo "== 4/8 Adding classes*.dex to APK =="
mapfile -t DEX_FILES < <(cd "$OUT" && find . -maxdepth 1 -name 'classes*.dex' -printf '%f\n' | sort)
if [ "${#DEX_FILES[@]}" -eq 0 ]; then
  echo "ERREUR: aucun fichier classes*.dex produit par d8"
  exit 1
fi
( cd "$OUT" && "$AAPT" add facebridge-unaligned.apk "${DEX_FILES[@]}" )

echo "== 5/8 Injecting native libraries (arm64-v8a, armeabi-v7a) =="
STAGE="$OUT/native_stage"
rm -rf "$STAGE"
for ABI in arm64-v8a armeabi-v7a; do
  SO="$DIR/jniLibs/$ABI/libtensorflowlite_jni.so"
  if [ -f "$SO" ]; then
    mkdir -p "$STAGE/lib/$ABI"
    cp "$SO" "$STAGE/lib/$ABI/"
  fi
done
( cd "$STAGE" && find lib -type f -exec "$AAPT" add "$OUT/facebridge-unaligned.apk" {} \; )

echo "== 6/8 Aligning APK =="
"$ZIPALIGN" -f -p 4 "$OUT/facebridge-unaligned.apk" "$OUT/facebridge-aligned.apk"

echo "== 7/8 Signing APK =="
KEYSTORE="$DIR/debug.keystore"
if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair -v -keystore "$KEYSTORE" -storepass android -alias androiddebugkey \
    -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Cybel Debug,O=Cybel,C=FR"
fi
"$APKSIGNER" sign --ks "$KEYSTORE" --ks-pass pass:android --key-pass pass:android \
  --ks-key-alias androiddebugkey --out "$OUT/CybelFaceBridge.apk" "$OUT/facebridge-aligned.apk"

echo "== 8/8 Terminé =="
echo ""
echo "Built: $OUT/CybelFaceBridge.apk"
echo "N'oubliez pas : adb shell pm grant com.cybel.facebridge android.permission.CAMERA"
