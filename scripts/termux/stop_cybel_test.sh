#!/data/data/com.termux/files/usr/bin/bash
PID_FILE="$HOME/.cybel-test-uvicorn.pid"
if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "CYBEL test arrêté (pid $PID)"
  else
    echo "Processus test $PID déjà arrêté"
  fi
  rm -f "$PID_FILE"
else
  echo "Aucun PID CYBEL test enregistré"
fi
