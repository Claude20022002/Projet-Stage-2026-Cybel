#!/usr/bin/env bash
# Builds and signs CybelTTSBridge.apk using only Android SDK command-line tools
# (no Gradle/Android Studio required).
set -euo pipefail

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
mkdir -p "$OUT/gen" "$OUT/obj"

echo "== 1/6 Linking resources + manifest =="
"$AAPT2" link -o "$OUT/bridge-unaligned.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$DIR/AndroidManifest.xml" \
  --java "$OUT/gen"

echo "== 2/6 Compiling Java sources =="
# -encoding UTF-8 : sans elle, javac lit les .java avec l'encodage plateforme
# (Cp1252 sous Windows) et corrompt les littéraux accentués (même bug trouvé
# dans CybelVisitorKioskTest/CybelFaceBridge).
javac -source 8 -target 8 -encoding UTF-8 \
  -cp "$ANDROID_JAR" \
  -d "$OUT/obj" \
  "$OUT/gen/com/cybel/ttsbridge/R.java" \
  "$DIR"/src/com/cybel/ttsbridge/*.java

echo "== 3/6 Converting to dex =="
"$D8" --output "$OUT" --lib "$ANDROID_JAR" $(find "$OUT/obj" -name "*.class")

echo "== 4/6 Adding classes.dex to APK =="
( cd "$OUT" && "$AAPT" add bridge-unaligned.apk classes.dex )

echo "== 5/6 Aligning APK =="
"$ZIPALIGN" -f -p 4 "$OUT/bridge-unaligned.apk" "$OUT/bridge-aligned.apk"

echo "== 6/6 Signing APK =="
KEYSTORE="$DIR/debug.keystore"
if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair -v -keystore "$KEYSTORE" -storepass android -alias androiddebugkey \
    -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Cybel Debug,O=Cybel,C=FR"
fi
"$APKSIGNER" sign --ks "$KEYSTORE" --ks-pass pass:android --key-pass pass:android \
  --ks-key-alias androiddebugkey --out "$OUT/CybelTTSBridge.apk" "$OUT/bridge-aligned.apk"

echo ""
echo "Built: $OUT/CybelTTSBridge.apk"
