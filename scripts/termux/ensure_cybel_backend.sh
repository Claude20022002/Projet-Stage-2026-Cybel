#!/data/data/com.termux/files/usr/bin/bash
# Point d'entrée idempotent pour l'app Android CYBEL Accueil (RUN_COMMAND / su).
set -euo pipefail

CYBEL_HOME="${CYBEL_HOME:-$HOME/cybel}"
SCRIPT="$CYBEL_HOME/scripts/termux/start_cybel.sh"

if [ ! -f "$SCRIPT" ]; then
  echo "ERREUR: $SCRIPT introuvable — déployez CYBEL sur la tablette (deploy_termux.py)"
  exit 1
fi

exec bash "$SCRIPT"
