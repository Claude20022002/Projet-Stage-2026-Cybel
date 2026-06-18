#!/data/data/com.termux/files/usr/bin/bash
# Démarre le backend CYBEL sur Termux (écoute 0.0.0.0:8000).
set -euo pipefail

CYBEL_HOME="${CYBEL_HOME:-$HOME/cybel}"
BACKEND_DIR="$CYBEL_HOME/backend"
ENV_FILE="$CYBEL_HOME/scripts/termux/cybel.env"
PID_FILE="$HOME/.cybel-uvicorn.pid"
LOG_FILE="$HOME/cybel-uvicorn.log"
LITE_FLAG="$CYBEL_HOME/scripts/termux/.use_lite"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

PORT="${BACKEND_PORT:-8000}"

if [ ! -d "$CYBEL_HOME/scripts/termux" ]; then
  echo "ERREUR: cybel non déployé dans $CYBEL_HOME"
  exit 1
fi

if [ ! -d "$CYBEL_HOME/frontend-kiosk/dist" ]; then
  echo "AVERTISSEMENT: frontend-kiosk/dist absent — /kiosk/ ne sera pas servi"
fi

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE")"
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Arrêt de l'instance précédente (pid $OLD_PID)..."
    kill "$OLD_PID" || true
    sleep 1
  fi
  rm -f "$PID_FILE"
fi

export PYTHONPATH="$CYBEL_HOME${PYTHONPATH:+:$PYTHONPATH}"

cd "$BACKEND_DIR"

if [ -f "$LITE_FLAG" ] || ! python -c "import fastapi" 2>/dev/null; then
  echo "Démarrage CYBEL lite sur 0.0.0.0:$PORT (log: $LOG_FILE)"
  nohup python "$CYBEL_HOME/scripts/termux/cybel_lite.py" >>"$LOG_FILE" 2>&1 &
else
  echo "Démarrage CYBEL complet sur 0.0.0.0:$PORT (log: $LOG_FILE)"
  nohup python -m uvicorn main:app --host 0.0.0.0 --port "$PORT" >>"$LOG_FILE" 2>&1 &
fi
echo $! >"$PID_FILE"
echo "PID $(cat "$PID_FILE")"

sleep 2
if curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null; then
  echo "OK — health check http://127.0.0.1:$PORT/api/health"
  curl -s "http://127.0.0.1:$PORT/api/health"
  echo ""
  KIOSK_URL_FILE="/sdcard/Download/cybel_kiosk_url.txt"
  WLAN_IP="$(ip -4 addr show wlan0 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1 | head -1)"
  if [ -n "$WLAN_IP" ]; then
    echo "http://${WLAN_IP}:${PORT}/kiosk/" >"$KIOSK_URL_FILE"
    echo "URL kiosk pour l'app Android : http://${WLAN_IP}:${PORT}/kiosk/"
  else
    echo "http://127.0.0.1:${PORT}/kiosk/" >"$KIOSK_URL_FILE"
    echo "URL kiosk pour l'app Android : http://127.0.0.1:${PORT}/kiosk/"
  fi
else
  echo "Échec health check — voir $LOG_FILE"
  tail -n 30 "$LOG_FILE" || true
  exit 1
fi
