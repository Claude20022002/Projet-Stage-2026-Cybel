#!/data/data/com.termux/files/usr/bin/bash
# Point d'entrée idempotent pour l'app Android CYBEL Accueil POI (test, port 8001).
set -euo pipefail

CYBEL_HOME="${CYBEL_HOME:-$HOME/cybel-test}"
export CYBEL_HOME
SCRIPT="$CYBEL_HOME/scripts/termux/start_cybel_test.sh"

if [ ! -f "$SCRIPT" ]; then
  echo "ERREUR: $SCRIPT introuvable — déployez avec deploy_termux.py --target test"
  exit 1
fi

exec bash "$SCRIPT"
