#!/data/data/com.termux/files/usr/bin/bash
# Lance (ou relance) l'agent de la tête — scripts/termux/head_agent.py — dans Termux.
#
#   bash ~/cybel-test/scripts/termux/start_head_agent.sh             # normal
#   bash ~/cybel-test/scripts/termux/start_head_agent.sh --dry-run   # journalise sans exécuter
#
# Écoute par défaut sur 192.168.20.1 (lien interne tête ↔ châssis) : joignable depuis le
# réseau du robot (le Pi passe par le châssis), pas depuis le Wi-Fi de l'école.
# Le jeton est lu dans $CYBEL_HOME/.head_agent.env (CYBEL_HEAD_TOKEN=…, 600).

CYBEL_HOME="${CYBEL_HOME:-$HOME/cybel-test}"
HOST="${HEAD_AGENT_HOST:-192.168.20.1}"
PORT="${HEAD_AGENT_PORT:-8002}"
ENV_FILE="$CYBEL_HOME/.head_agent.env"
LOG="$HOME/head_agent.log"

[ -f "$ENV_FILE" ] || { echo "Jeton absent : $ENV_FILE"; exit 1; }

BIN="${PREFIX:-/data/data/com.termux/files/usr}/bin"
"$BIN/pkill" -f "scripts/termux/head_agent.py" 2>/dev/null && sleep 1

set -a
. "$ENV_FILE"
set +a
export CYBEL_HOME

# Chemin complet : lancé par l'app kiosque, le PATH peut ne pas contenir Termux.
# Si le lien interne n'est pas encore monté au démarrage, l'agent réessaie seul (2 min).
nohup "$BIN/python" "$CYBEL_HOME/scripts/termux/head_agent.py" --host "$HOST" --port "$PORT" "$@" >> "$LOG" 2>&1 &
echo "Agent de la tête lancé (pid $!) sur $HOST:$PORT — journal : $LOG"
