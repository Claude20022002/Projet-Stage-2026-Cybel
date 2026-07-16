#!/usr/bin/env bash
# Télécharge + vérifie le modèle Vosk français dans assets/ (une seule fois).
# Modèle vosk-model-small-fr-0.22 — Apache 2.0, ~41 Mo, provenance documentée
# (corpus publics : voir README du modèle). Non committé dans git pour ne pas
# alourdir le dépôt de 41 Mo ; récupéré au build sur le PC (qui a internet).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS="$DIR/assets"
# Le modèle est livré en UN SEUL fichier zip (dézippé au premier lancement par
# VoiceRecognizer) : AssetManager.list() sur un sous-dossier d'assets ne renvoie
# rien sur cette tablette Android 7.1 avec un APK construit hors Gradle —
# constaté sur le châssis réel le 2026-07-16 (FileNotFoundException vosk-model-fr).
# L'ouverture directe d'un fichier asset, elle, fonctionne (prouvé par FaceBridge).
MODEL_ZIP="$ASSETS/vosk-model-fr.zip"
ZIP_URL="https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip"
ZIP_SHA256="cabf6180e177eb9b3a9a9d43a437bd5e549f3a7d09525e5d69a3fed787be12ad"

if [ -f "$MODEL_ZIP" ]; then
  ACTUAL="$(sha256sum "$MODEL_ZIP" | cut -d' ' -f1)"
  if [ "$ACTUAL" == "$ZIP_SHA256" ]; then
    echo "Modèle Vosk déjà présent : $MODEL_ZIP"
    exit 0
  fi
  echo "Modèle présent mais SHA256 inattendu — re-téléchargement."
  rm -f "$MODEL_ZIP"
fi

echo "Téléchargement du modèle Vosk FR (~41 Mo)…"
mkdir -p "$ASSETS"
curl -fSL -o "$MODEL_ZIP" "$ZIP_URL"

echo "Vérification d'intégrité (SHA256)…"
ACTUAL="$(sha256sum "$MODEL_ZIP" | cut -d' ' -f1)"
if [ "$ACTUAL" != "$ZIP_SHA256" ]; then
  echo "ERREUR: SHA256 inattendu ($ACTUAL) — téléchargement corrompu, abandon."
  rm -f "$MODEL_ZIP"
  exit 1
fi

# Nettoyage de l'ancien format (dossier extrait dans assets/)
rm -rf "$ASSETS/vosk-model-fr"

echo "OK — modèle prêt : $MODEL_ZIP"
