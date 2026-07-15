#!/usr/bin/env bash
# Télécharge + vérifie le modèle Vosk français dans assets/ (une seule fois).
# Modèle vosk-model-small-fr-0.22 — Apache 2.0, ~41 Mo, provenance documentée
# (corpus publics : voir README du modèle). Non committé dans git pour ne pas
# alourdir le dépôt de 41 Mo ; récupéré au build sur le PC (qui a internet).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS="$DIR/assets"
MODEL_DIR="$ASSETS/vosk-model-fr"
ZIP_URL="https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip"
ZIP_SHA256="cabf6180e177eb9b3a9a9d43a437bd5e549f3a7d09525e5d69a3fed787be12ad"
TMP_ZIP="$DIR/out/vosk-model-small-fr-0.22.zip"

if [ -f "$MODEL_DIR/conf/model.conf" ]; then
  echo "Modèle Vosk déjà présent : $MODEL_DIR"
  exit 0
fi

echo "Téléchargement du modèle Vosk FR (~41 Mo)…"
mkdir -p "$ASSETS" "$DIR/out"
curl -fSL -o "$TMP_ZIP" "$ZIP_URL"

echo "Vérification d'intégrité (SHA256)…"
ACTUAL="$(sha256sum "$TMP_ZIP" | cut -d' ' -f1)"
if [ "$ACTUAL" != "$ZIP_SHA256" ]; then
  echo "ERREUR: SHA256 inattendu ($ACTUAL) — téléchargement corrompu, abandon."
  rm -f "$TMP_ZIP"
  exit 1
fi

echo "Extraction dans assets/vosk-model-fr…"
rm -rf "$MODEL_DIR"
unzip -q "$TMP_ZIP" -d "$ASSETS"
# L'archive contient un dossier vosk-model-small-fr-0.22/ ; on le renomme.
mv "$ASSETS/vosk-model-small-fr-0.22" "$MODEL_DIR"
rm -f "$TMP_ZIP"

echo "OK — modèle prêt : $MODEL_DIR"
