#!/usr/bin/env bash
# Builds and signs CybelVisitorKiosk.apk using only Android SDK command-line tools
# (no Gradle/Android Studio required).
set -euo pipefail

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

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$DIR/out"

rm -rf "$OUT"
mkdir -p "$OUT/gen" "$OUT/obj" "$OUT/res"

echo "== 1/7 Compiling launcher icons =="
"$AAPT2" compile --dir "$DIR/res" -o "$OUT/res"

echo "== 2/7 Linking resources + manifest =="
mapfile -t FLAT_FILES < <(find "$OUT/res" -maxdepth 1 -name '*.flat' -print | sort)
if [ "${#FLAT_FILES[@]}" -eq 0 ]; then
  echo "ERREUR: aucun fichier .flat dans $OUT/res"
  exit 1
fi
"$AAPT2" link -o "$OUT/kiosk-unaligned.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$DIR/AndroidManifest.xml" \
  --java "$OUT/gen" \
  "${FLAT_FILES[@]}"

echo "== 3/7 Compiling Java sources =="
javac -source 8 -target 8 \
  -cp "$ANDROID_JAR" \
  -d "$OUT/obj" \
  "$OUT/gen/com/cybel/visitorkiosk/R.java" \
  "$DIR"/src/com/cybel/visitorkiosk/*.java

echo "== 4/7 Converting to dex =="
mapfile -t CLASS_FILES < <(find "$OUT/obj" -name '*.class' -print)
"$D8" --output "$OUT" --lib "$ANDROID_JAR" "${CLASS_FILES[@]}"

echo "== 5/7 Adding classes.dex to APK =="
( cd "$OUT" && "$AAPT" add kiosk-unaligned.apk classes.dex )

echo "== 6/7 Aligning APK =="
"$ZIPALIGN" -f -p 4 "$OUT/kiosk-unaligned.apk" "$OUT/kiosk-aligned.apk"

echo "== 7/7 Signing APK =="
KEYSTORE="$DIR/debug.keystore"
if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair -v -keystore "$KEYSTORE" -storepass android -alias androiddebugkey \
    -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Cybel Debug,O=Cybel,C=FR"
fi
"$APKSIGNER" sign --ks "$KEYSTORE" --ks-pass pass:android --key-pass pass:android \
  --ks-key-alias androiddebugkey --out "$OUT/CybelVisitorKiosk.apk" "$OUT/kiosk-aligned.apk"

echo ""
echo "Built: $OUT/CybelVisitorKiosk.apk"
