#!/data/data/com.termux/files/usr/bin/bash
# Déclenche l'enrôlement d'un visiteur (CybelFaceBridge) — à lancer par le personnel
# uniquement, jamais automatiquement. Ouvre une fenêtre de 15s pendant laquelle le
# premier visage détecté par la tablette est enrôlé avec le nom fourni.
#
# Usage : enroll_visitor.sh "Nom" ["M."|"Mme"|""]

set -euo pipefail

NAME="${1:-}"
CIVILITY="${2:-}"

if [ -z "$NAME" ]; then
  echo "Usage: enroll_visitor.sh \"Nom\" [\"M.\"|\"Mme\"|\"\"]"
  exit 1
fi

am broadcast -n com.cybel.facebridge/.EnrollReceiver \
  -a com.cybel.facebridge.ENROLL \
  --es name "$NAME" \
  --es civility "$CIVILITY"

echo "Fenêtre d'enrôlement ouverte pour « $NAME » (15s) — placez le visiteur face à la caméra."
