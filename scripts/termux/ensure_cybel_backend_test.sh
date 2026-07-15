#!/data/data/com.termux/files/usr/bin/bash
# Point d'entrée idempotent pour l'app Android CYBEL Accueil POI (test, port 8001).
set -euo pipefail

CYBEL_HOME="${CYBEL_HOME:-$HOME/cybel-test}"
export CYBEL_HOME
SCRIPT="$CYBEL_HOME/scripts/termux/start_cybel_test.sh"
OFFLINE_BOOTSTRAP="$CYBEL_HOME/scripts/termux/install_offline_bootstrap.sh"

if [ ! -f "$SCRIPT" ]; then
  echo "ERREUR: $SCRIPT introuvable — déployez avec deploy_termux.py --target test"
  exit 1
fi

# Préflight : réparation offline si python/uvicorn manquent (voir panne 2026-07-15,
# détail dans offline_bootstrap/README.md).
if ! python -c "import uvicorn, starlette, websockets" >/dev/null 2>&1; then
  echo "Dépendances backend manquantes — tentative de réparation offline..."
  if [ -f "$OFFLINE_BOOTSTRAP" ]; then
    bash "$OFFLINE_BOOTSTRAP"
  else
    echo "ERREUR: $OFFLINE_BOOTSTRAP introuvable — redéployez (deploy_termux.py --target test)"
    exit 1
  fi
fi

exec bash "$SCRIPT"
