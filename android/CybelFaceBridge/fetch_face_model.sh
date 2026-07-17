#!/usr/bin/env bash
# Télécharge + vérifie le modèle d'embedding facial dans assets/ (une seule fois).
#
# Provenance (choix conscient, voir README.md « Modèle vendorisé ») :
# FaceNet (David Sandberg, code MIT — davidsandberg/facenet), poids pré-entraînés
# sur CASIA-WebFace/VGGFace2 (PAS MS-Celeb-1M). La conversion .tflite n'est pas
# publiée comme fichier autonome ; elle est vendorée comme asset dans la release
# publique open-source de shubham0204/OnDevice-Face-Recognition-Android
# (elle-même sourcée depuis la bibliothèque deepface, MIT). On extrait
# assets/facenet.tflite (variante 128-d) directement de cet APK public.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS="$DIR/assets"
MODEL_FILE="$ASSETS/face_embedding.tflite"
APK_URL="https://github.com/shubham0204/OnDevice-Face-Recognition-Android/releases/download/v0.0.1/FaceNet-Android_v0.0.1.apk"
MODEL_SHA256="d7c1f7f130376982c7004920ddc41925ac2e5aecf6522f476c8bbb3669db7013"
ASSET_PATH_IN_APK="assets/facenet.tflite"

if [ -f "$MODEL_FILE" ]; then
  ACTUAL="$(sha256sum "$MODEL_FILE" | cut -d' ' -f1)"
  if [ "$ACTUAL" == "$MODEL_SHA256" ]; then
    echo "Modèle d'embedding facial déjà présent : $MODEL_FILE"
    exit 0
  fi
  echo "Modèle présent mais SHA256 inattendu — re-téléchargement."
  rm -f "$MODEL_FILE"
fi

TMP_APK="$(mktemp -t cybel_facenet_XXXXXX.apk)"
trap 'rm -f "$TMP_APK"' EXIT

echo "Téléchargement de l'APK source (~150 Mo, contient le modèle en asset)…"
curl -fSL -o "$TMP_APK" "$APK_URL"

echo "Extraction de $ASSET_PATH_IN_APK…"
mkdir -p "$ASSETS"
python3 -c "
import zipfile
with zipfile.ZipFile('$TMP_APK') as z:
    with z.open('$ASSET_PATH_IN_APK') as src, open('$MODEL_FILE', 'wb') as dst:
        dst.write(src.read())
"

echo "Vérification d'intégrité (SHA256)…"
ACTUAL="$(sha256sum "$MODEL_FILE" | cut -d' ' -f1)"
if [ "$ACTUAL" != "$MODEL_SHA256" ]; then
  echo "ERREUR: SHA256 inattendu ($ACTUAL) — extraction corrompue, abandon."
  rm -f "$MODEL_FILE"
  exit 1
fi

echo "OK — modèle prêt : $MODEL_FILE"
