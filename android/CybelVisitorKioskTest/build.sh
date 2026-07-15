#!/usr/bin/env bash
# Builds CybelVisitorKioskTest.apk (variante POI, port 8001) — réutilise les icônes du kiosque principal.
# Intègre la reconnaissance vocale hors-ligne (Vosk STT français).
set -euo pipefail

if [ -z "${ANDROID_HOME:-}" ]; then
  echo "ERREUR: ANDROID_HOME non défini"
  exit 1
fi
# Normaliser les chemins Windows pour Git Bash
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
if command -v cygpath >/dev/null 2>&1; then
  DIR="$(cygpath -m "$DIR")"
fi
RES_SRC="$DIR/../CybelVisitorKiosk/res"
OUT="$DIR/out"
VOSK_JAR="$DIR/libs/vosk-0.3.47.jar"

if [ ! -f "$VOSK_JAR" ]; then
  echo "ERREUR: $VOSK_JAR manquant (vendoring Vosk incomplet)"
  exit 1
fi

echo "== 0/8 Modèle Vosk (télécharge si absent) =="
bash "$DIR/fetch_vosk_model.sh"

rm -rf "$OUT"
mkdir -p "$OUT/gen" "$OUT/obj" "$OUT/res"

echo "== 1/8 Compiling launcher icons (shared res) =="
"$AAPT2" compile --dir "$RES_SRC" -o "$OUT/res"
if [ -d "$DIR/res" ]; then
  "$AAPT2" compile --dir "$DIR/res" -o "$OUT/res"
fi

echo "== 2/8 Linking resources + manifest + assets =="
mapfile -t FLAT_FILES < <(find "$OUT/res" -maxdepth 1 -name '*.flat' -print | sort)
if [ "${#FLAT_FILES[@]}" -eq 0 ]; then
  echo "ERREUR: aucun fichier .flat dans $OUT/res"
  exit 1
fi
"$AAPT2" link -o "$OUT/kiosk-unaligned.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$DIR/AndroidManifest.xml" \
  -A "$DIR/assets" \
  --java "$OUT/gen" \
  "${FLAT_FILES[@]}"

echo "== 3/8 Compiling Java sources =="
# Séparateur ';' pour javac.exe natif Windows (collision avec la lettre de lecteur sinon).
javac -source 8 -target 8 \
  -cp "$ANDROID_JAR;$VOSK_JAR" \
  -d "$OUT/obj" \
  "$OUT/gen/com/cybel/visitorkiosk/test/R.java" \
  "$DIR"/src/com/cybel/visitorkiosk/test/*.java

echo "== 4/8 Converting to dex (nos classes + runtime Vosk/JNA) =="
mapfile -t CLASS_FILES < <(find "$OUT/obj" -name '*.class' -print)
"$D8" --output "$OUT" --lib "$ANDROID_JAR" "${CLASS_FILES[@]}" "$VOSK_JAR"

echo "== 5/8 Adding classes*.dex to APK =="
mapfile -t DEX_FILES < <(cd "$OUT" && find . -maxdepth 1 -name 'classes*.dex' -printf '%f\n' | sort)
( cd "$OUT" && "$AAPT" add kiosk-unaligned.apk "${DEX_FILES[@]}" )

echo "== 6/8 Injecting native libraries (Vosk + JNA) =="
STAGE="$OUT/native_stage"
rm -rf "$STAGE"
for ABI in arm64-v8a armeabi-v7a; do
  if [ -d "$DIR/jniLibs/$ABI" ]; then
    mkdir -p "$STAGE/lib/$ABI"
    cp "$DIR/jniLibs/$ABI"/*.so "$STAGE/lib/$ABI/"
  fi
done
( cd "$STAGE" && find lib -type f -exec "$AAPT" add "$OUT/kiosk-unaligned.apk" {} \; )

echo "== 7/8 Aligning APK =="
"$ZIPALIGN" -f -p 4 "$OUT/kiosk-unaligned.apk" "$OUT/kiosk-aligned.apk"

echo "== 8/8 Signing APK =="
KEYSTORE="$DIR/../CybelVisitorKiosk/debug.keystore"
if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair -v -keystore "$KEYSTORE" -storepass android -alias androiddebugkey \
    -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Cybel Debug,O=Cybel,C=FR"
fi
"$APKSIGNER" sign --ks "$KEYSTORE" --ks-pass pass:android --key-pass pass:android \
  --ks-key-alias androiddebugkey --out "$OUT/CybelVisitorKioskTest.apk" "$OUT/kiosk-aligned.apk"

echo ""
echo "Built: $OUT/CybelVisitorKioskTest.apk"
echo "Package: com.cybel.visitorkiosk.test — label « CYBEL Accueil »"
echo "N'oubliez pas : adb shell pm grant com.cybel.visitorkiosk.test android.permission.RECORD_AUDIO"
