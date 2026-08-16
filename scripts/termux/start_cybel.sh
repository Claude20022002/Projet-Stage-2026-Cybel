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

# Android suspend les processus Termux (Doze / optimisation batterie) dès que
# l'écran s'éteint ou après une période d'inactivité : le backend cesse de
# répondre et les sessions longues perdent la connexion. Le wake lock empêche
# cette suspension. Il faut le paquet termux-api ; sans lui on démarre quand
# même, mais une campagne de plusieurs heures échouera très probablement.
acquire_wake_lock() {
  if command -v termux-wake-lock >/dev/null 2>&1; then
    if termux-wake-lock 2>/dev/null; then
      echo "Wake lock acquis — Termux ne sera pas suspendu par Android"
      return 0
    fi
    echo "AVERTISSEMENT: termux-wake-lock a échoué (application Termux:API installée ?)"
  else
    echo "AVERTISSEMENT: termux-wake-lock introuvable."
    echo "               Installez-le :  pkg install termux-api"
    echo "               puis l'application Termux:API depuis F-Droid."
  fi
  echo "               Sans wake lock, Android coupera le backend en session longue."
  return 0
}

write_kiosk_url() {
  KIOSK_URL_FILE="/sdcard/Download/cybel_kiosk_url.txt"
  FALLBACK_FILE="$HOME/cybel_kiosk_url.txt"
  WLAN_IP=""

  for iface in wlan0 eth0; do
    if ip -4 addr show "$iface" >/dev/null 2>&1; then
      WLAN_IP="$(ip -4 addr show "$iface" 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1 | head -1 || true)"
      if [ -n "$WLAN_IP" ]; then
        break
      fi
    fi
  done

  if [ -n "$WLAN_IP" ]; then
    URL="http://${WLAN_IP}:${PORT}/kiosk/"
  else
    URL="http://127.0.0.1:${PORT}/kiosk/"
  fi

  if mkdir -p "$(dirname "$KIOSK_URL_FILE")" 2>/dev/null && echo "$URL" >"$KIOSK_URL_FILE" 2>/dev/null; then
    echo "URL kiosk pour l'app Android : $URL"
    return 0
  fi

  if command -v su >/dev/null 2>&1; then
    if su -c "mkdir -p /sdcard/Download && printf '%s\n' '$URL' > /sdcard/Download/cybel_kiosk_url.txt" 2>/dev/null; then
      echo "URL kiosk pour l'app Android (via su) : $URL"
      return 0
    fi
  fi

  echo "$URL" >"$FALLBACK_FILE"
  echo "AVERTISSEMENT: écriture SD impossible — URL copiée dans $FALLBACK_FILE"
  echo "URL kiosk pour l'app Android : $URL"
  return 0
}

if curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
  echo "CYBEL déjà actif — mise à jour URL kiosk uniquement"
  write_kiosk_url
  exit 0
fi

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
PYTHON="${PYTHON:-/data/data/com.termux/files/usr/bin/python}"

acquire_wake_lock

cd "$BACKEND_DIR"

if [ -f "$LITE_FLAG" ] || ! "$PYTHON" -c "import fastapi" 2>/dev/null; then
  echo "Démarrage CYBEL lite sur 0.0.0.0:$PORT (log: $LOG_FILE)"
  nohup env CYBEL_HOME="$CYBEL_HOME" BACKEND_PORT="$PORT" "$PYTHON" "$CYBEL_HOME/scripts/termux/cybel_lite.py" >>"$LOG_FILE" 2>&1 &
else
  echo "Démarrage CYBEL complet sur 0.0.0.0:$PORT (log: $LOG_FILE)"
  nohup env CYBEL_HOME="$CYBEL_HOME" "$PYTHON" -m uvicorn main:app --host 0.0.0.0 --port "$PORT" >>"$LOG_FILE" 2>&1 &
fi
echo $! >"$PID_FILE"
echo "PID $(cat "$PID_FILE")"

sleep 2
if curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null; then
  echo "OK — health check http://127.0.0.1:$PORT/api/health"
  curl -s "http://127.0.0.1:$PORT/api/health"
  echo ""
  write_kiosk_url
  exit 0
else
  echo "Échec health check — voir $LOG_FILE"
  tail -n 30 "$LOG_FILE" || true
  exit 1
fi
