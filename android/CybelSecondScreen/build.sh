#!/usr/bin/env bash
# Builds and signs CybelSecondScreen.apk using only Android SDK command-line tools
# (no Gradle/Android Studio required). Same toolchain as CybelTTSBridge.
set -euo pipefail

if [ -z "${ANDROID_HOME:-}" ]; then
  echo "ERREUR: ANDROID_HOME non défini"
  exit 1
fi
ANDROID_HOME="${ANDROID_HOME//\\//}"

# Le PC peut n'avoir qu'une version de build-tools (34.0.0 au 2026-10-16) :
# prendre la plus récente installée plutôt qu'une version codée en dur.
BUILD_TOOLS_VER="${BUILD_TOOLS_VER:-$(ls "$ANDROID_HOME/build-tools" | sort -V | tail -1)}"
PLATFORM_VER="${PLATFORM_VER:-android-34}"

ANDROID_JAR="$ANDROID_HOME/platforms/$PLATFORM_VER/android.jar"
BUILD_TOOLS="$ANDROID_HOME/build-tools/$BUILD_TOOLS_VER"
AAPT2="$BUILD_TOOLS/aapt2.exe"
AAPT="$BUILD_TOOLS/aapt.exe"
D8="$BUILD_TOOLS/d8.bat"
ZIPALIGN="$BUILD_TOOLS/zipalign.exe"
APKSIGNER="$BUILD_TOOLS/apksigner.bat"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v cygpath >/dev/null 2>&1; then
  DIR="$(cygpath -m "$DIR")"
fi
OUT="$DIR/out"

echo "build-tools $BUILD_TOOLS_VER, $PLATFORM_VER"
rm -rf "$OUT"
mkdir -p "$OUT/gen" "$OUT/obj"

echo "== 1/6 Linking resources + manifest =="
"$AAPT2" link -o "$OUT/screen-unaligned.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$DIR/AndroidManifest.xml" \
  --java "$OUT/gen"

echo "== 2/6 Compiling Java sources =="
javac -source 8 -target 8 -encoding UTF-8 \
  -cp "$ANDROID_JAR" \
  -d "$OUT/obj" \
  "$OUT/gen/com/cybel/secondscreen/R.java" \
  "$DIR"/src/com/cybel/secondscreen/*.java

echo "== 3/6 Converting to dex =="
mapfile -t CLASS_FILES < <(find "$OUT/obj" -name '*.class' -print)
"$D8" --output "$OUT" --lib "$ANDROID_JAR" "${CLASS_FILES[@]}"

echo "== 4/6 Adding classes.dex to APK =="
( cd "$OUT" && "$AAPT" add screen-unaligned.apk classes.dex )

echo "== 5/6 Aligning APK =="
"$ZIPALIGN" -f -p 4 "$OUT/screen-unaligned.apk" "$OUT/screen-aligned.apk"

echo "== 6/6 Signing APK =="
KEYSTORE="$DIR/debug.keystore"
if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair -v -keystore "$KEYSTORE" -storepass android -alias androiddebugkey \
    -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Cybel Debug,O=Cybel,C=FR"
fi
"$APKSIGNER" sign --ks "$KEYSTORE" --ks-pass pass:android --key-pass pass:android \
  --ks-key-alias androiddebugkey --out "$OUT/CybelSecondScreen.apk" "$OUT/screen-aligned.apk"

echo ""
echo "Built: $OUT/CybelSecondScreen.apk"
echo "Installation :"
echo "  adb install -r out/CybelSecondScreen.apk"
echo "  adb shell appops set com.cybel.secondscreen SYSTEM_ALERT_WINDOW allow"
echo "  adb shell am startservice -n com.cybel.secondscreen/.SecondScreenService"
