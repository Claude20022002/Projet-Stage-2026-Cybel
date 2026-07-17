#!/data/data/com.termux/files/usr/bin/bash
# Point d'entrée idempotent pour l'app Android CYBEL Accueil (RUN_COMMAND / su).
set -euo pipefail

CYBEL_HOME="${CYBEL_HOME:-$HOME/cybel}"
SCRIPT="$CYBEL_HOME/scripts/termux/start_cybel.sh"
OFFLINE_BOOTSTRAP="$CYBEL_HOME/scripts/termux/install_offline_bootstrap.sh"

if [ ! -f "$SCRIPT" ]; then
  echo "ERREUR: $SCRIPT introuvable — déployez CYBEL sur la tablette (deploy_termux.py)"
  exit 1
fi

# Préflight : après une réinstallation du bootstrap Termux, python et/ou les
# modules du backend peuvent avoir disparu (panne du 2026-07-15 : bootstrap
# réextrait sans python → backend mort, et pas d'internet sur le réseau du
# robot pour `pkg install`). Réparation automatique depuis le bundle embarqué.
if ! python -c "import uvicorn, starlette, websockets" >/dev/null 2>&1; then
  echo "Dépendances backend manquantes — tentative de réparation offline..."
  if [ -f "$OFFLINE_BOOTSTRAP" ]; then
    bash "$OFFLINE_BOOTSTRAP"
  else
    echo "ERREUR: $OFFLINE_BOOTSTRAP introuvable — redéployez CYBEL (deploy_termux.py)"
    exit 1
  fi
fi

exec bash "$SCRIPT"
