#!/usr/bin/env bash
# =============================================================================
# Mode événement (journée d'intégration HESTIM, bâtiment Ghandi) — robot en USB/ADB.
#
#   Écran du dessus  : kiosque CybelVisitorKioskTest en mode événement
#                      (visuel plein écran, toucher et voix sans effet).
#   Écran du dessous : CybelSecondScreen (display HDMI 1), image sur /sdcard.
#   Voix             : annonces périodiques du backend Termux (/api/event/*).
#
# Aucune commande châssis : rien ici ne fait bouger le robot.
#
# Usage :
#   scripts/deploy_event.sh                 # build kiosque + déploiement + validation
#   scripts/deploy_event.sh --apk           # + build/installation CybelSecondScreen
#   scripts/deploy_event.sh --skip-build    # sans npm run build
#   scripts/deploy_event.sh --restore       # remet la config d'avant l'événement
#
# Annonces ensuite (PC, tunnel adb forward 18001 → 8001) :
#   curl -X POST localhost:18001/api/event/announce/say      # une annonce, tout de suite
#   curl -X POST localhost:18001/api/event/announce/start    # boucle périodique
#   curl -X POST localhost:18001/api/event/announce/stop
# =============================================================================
set -uo pipefail

DO_APK=0; SKIP_BUILD=0; RESTORE=0
for arg in "$@"; do
  case "$arg" in
    --apk) DO_APK=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    --restore) RESTORE=1 ;;
    *) echo "Option inconnue: $arg"; exit 2 ;;
  esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TERMUX_HOME="/data/data/com.termux/files/home"
CYBEL_TREE="$TERMUX_HOME/cybel-test"
TERMUX_OWNER=""
PORT_LOCAL=18001
PORT_DEVICE=8001
EVENT_CONFIG="$REPO/data/kiosk_config.ghandi.json"
# Copie de la config d'avant l'événement, faite une seule fois (jamais écrasée).
BACKUP_NAME="kiosk_config.before_event.json"
BOTTOM_IMAGE="$REPO/frontend-kiosk/public/event/ecran-dessous.jpg"
BOTTOM_IMAGE_DEVICE="/sdcard/Cybel/ecran-dessous.jpg"
KIOSK_PKG="com.cybel.visitorkiosk.test"
SCREEN_PKG="com.cybel.secondscreen"
SCREEN_SERVICE="$SCREEN_PKG/.SecondScreenService"

ok(){ printf '  \033[32m✓\033[0m %s\n' "$1"; }
ko(){ printf '  \033[31m✗\033[0m %s\n' "$1"; }
step(){ printf '\n\033[36m== %s ==\033[0m\n' "$1"; }
fail(){ ko "$1"; exit 1; }

win(){ cygpath -m "$1" 2>/dev/null || echo "$1"; }

# push_root <local_path> <remote_dest_path> — copie vers l'arbre Termux avec les
# bons droits (via /data/local/tmp puis cp root, comme deploy_voice_face.sh).
push_root() {
  local src="$1" dest="$2" tmp
  tmp="/data/local/tmp/_evt_$(basename "$src")"
  MSYS_NO_PATHCONV=1 adb push "$(win "$src")" "$tmp" >/dev/null 2>&1 || fail "push $(basename "$src") échoué"
  MSYS_NO_PATHCONV=1 adb shell "rm -rf '$dest' && cp -r '$tmp' '$dest' && chown -R $TERMUX_OWNER '$dest' && rm -rf '$tmp'" \
    || fail "cp root vers $dest échoué"
}

run_termux() {
  local cmd="$1"
  MSYS_NO_PATHCONV=1 adb shell "am startservice -n com.termux/.app.RunCommandService \
    -a com.termux.RUN_COMMAND \
    --es com.termux.RUN_COMMAND_PATH '/data/data/com.termux/files/usr/bin/bash' \
    --esa com.termux.RUN_COMMAND_ARGUMENTS '-c,$cmd' \
    --es com.termux.RUN_COMMAND_WORKDIR '$TERMUX_HOME' \
    --ez com.termux.RUN_COMMAND_BACKGROUND true" >/dev/null 2>&1
}

restart_backend_and_wait() {
  run_termux "bash $CYBEL_TREE/scripts/termux/stop_cybel_test.sh; sleep 1; bash $CYBEL_TREE/scripts/termux/ensure_cybel_backend_test.sh > $TERMUX_HOME/event_start.log 2>&1"
  adb forward "tcp:$PORT_LOCAL" "tcp:$PORT_DEVICE" >/dev/null 2>&1
  for _ in $(seq 1 30); do
    sleep 2
    curl -s -m 3 "http://127.0.0.1:$PORT_LOCAL/api/health" >/dev/null 2>&1 && return 0
  done
  return 1
}

restart_kiosk_app() {
  # Force-stop : la WebView garde sinon l'ancien bundle en mémoire.
  MSYS_NO_PATHCONV=1 adb shell "am force-stop $KIOSK_PKG; am start -n $KIOSK_PKG/.MainActivity" >/dev/null 2>&1
}

# ---- 0. Préflight ------------------------------------------------------------
step "0. Préflight"
command -v adb >/dev/null || fail "adb introuvable dans le PATH"
adb get-state >/dev/null 2>&1 || fail "aucun appareil ADB (branchez la tête du robot en USB)"
ok "appareil ADB : $(adb devices | awk 'NR==2{print $1}')"
MSYS_NO_PATHCONV=1 adb shell "test -d '$CYBEL_TREE'" || fail "$CYBEL_TREE absent sur la tablette"
TERMUX_OWNER="$(MSYS_NO_PATHCONV=1 adb shell "stat -c '%U:%G' '$CYBEL_TREE'" 2>/dev/null | tr -d ' \r\n')"
[ -n "$TERMUX_OWNER" ] || fail "propriétaire Termux introuvable (accès root ADB ?)"
ok "propriétaire Termux : $TERMUX_OWNER"

# ---- Restauration ------------------------------------------------------------
if [ "$RESTORE" -eq 1 ]; then
  step "Restauration de la config d'avant l'événement"
  MSYS_NO_PATHCONV=1 adb shell "test -f '$CYBEL_TREE/data/$BACKUP_NAME'" \
    || fail "$BACKUP_NAME absent — rien à restaurer"
  MSYS_NO_PATHCONV=1 adb shell "cp '$CYBEL_TREE/data/$BACKUP_NAME' '$CYBEL_TREE/data/kiosk_config.json' && chown $TERMUX_OWNER '$CYBEL_TREE/data/kiosk_config.json'" \
    || fail "copie échouée"
  ok "kiosk_config.json restauré"
  MSYS_NO_PATHCONV=1 adb shell "am startservice -n $SCREEN_SERVICE -a com.cybel.secondscreen.HIDE" >/dev/null 2>&1
  ok "écran du dessous libéré"
  restart_backend_and_wait && ok "backend redémarré" || ko "backend ne répond pas"
  restart_kiosk_app && ok "kiosque relancé"
  exit 0
fi

# ---- 1. Build kiosque --------------------------------------------------------
if [ "$SKIP_BUILD" -eq 0 ]; then
  step "1. Build frontend-kiosk"
  ( cd "$REPO/frontend-kiosk" && npm run build ) >/dev/null 2>&1 \
    && ok "dist/ reconstruit (visuels inclus)" || fail "npm run build échoué"
else
  step "1. Build frontend-kiosk — ignoré (--skip-build)"
fi

# ---- 2. Backend + config -----------------------------------------------------
step "2. Déploiement backend + config événement"
MSYS_NO_PATHCONV=1 adb shell "test -f '$CYBEL_TREE/data/$BACKUP_NAME' || cp '$CYBEL_TREE/data/kiosk_config.json' '$CYBEL_TREE/data/$BACKUP_NAME'"
ok "config d'avant l'événement sauvegardée ($BACKUP_NAME)"
push_root "$REPO/scripts/termux/cybel_lite.py" "$CYBEL_TREE/scripts/termux/cybel_lite.py"
ok "cybel_lite.py (routes /api/event/*)"
push_root "$REPO/sdk/integration_event.py" "$CYBEL_TREE/sdk/integration_event.py"
ok "sdk/integration_event.py (moteur de circulation)"
push_root "$REPO/frontend-kiosk/dist" "$CYBEL_TREE/frontend-kiosk/dist"
ok "frontend-kiosk/dist"
push_root "$EVENT_CONFIG" "$CYBEL_TREE/data/kiosk_config.json"
ok "kiosk_config.json ← $(basename "$EVENT_CONFIG")"

step "3. Redémarrage backend"
restart_backend_and_wait && ok "backend répond" || fail "backend ne répond pas — voir ~/event_start.log (Termux)"

# ---- 4. Écran du dessous -----------------------------------------------------
step "4. Écran du dessous"
if [ "$DO_APK" -eq 1 ]; then
  ( cd "$REPO/android/CybelSecondScreen" && bash build.sh ) >/dev/null 2>&1 || fail "build CybelSecondScreen échoué"
  adb install -r "$(win "$REPO/android/CybelSecondScreen/out/CybelSecondScreen.apk")" >/dev/null 2>&1 \
    || fail "installation CybelSecondScreen échouée"
  ok "CybelSecondScreen installé"
fi
MSYS_NO_PATHCONV=1 adb shell "pm path $SCREEN_PKG" >/dev/null 2>&1 || fail "$SCREEN_PKG absent — relancez avec --apk"
MSYS_NO_PATHCONV=1 adb shell "mkdir -p /sdcard/Cybel" >/dev/null 2>&1
MSYS_NO_PATHCONV=1 adb push "$(win "$BOTTOM_IMAGE")" "$BOTTOM_IMAGE_DEVICE" >/dev/null 2>&1 || fail "push image écran du dessous échoué"
MSYS_NO_PATHCONV=1 adb shell "appops set $SCREEN_PKG SYSTEM_ALERT_WINDOW allow; pm grant $SCREEN_PKG android.permission.READ_EXTERNAL_STORAGE; am startservice -n $SCREEN_SERVICE --es path $BOTTOM_IMAGE_DEVICE" >/dev/null 2>&1
sleep 2
if MSYS_NO_PATHCONV=1 adb shell "dumpsys window windows" | grep -A1 "u0 $SCREEN_PKG" | grep -q "mDisplayId=1"; then
  ok "visuel affiché sur l'écran du dessous (display 1)"
else
  ko "pas de fenêtre sur le display 1 — adb logcat -s CybelSecondScreen"
fi

# ---- 5. Kiosque + validation -------------------------------------------------
step "5. Kiosque (écran du dessus) + validation"
restart_kiosk_app && ok "kiosque relancé"
EVENT_STATUS="$(curl -s -m 5 "http://127.0.0.1:$PORT_LOCAL/api/event/status")"
echo "$EVENT_STATUS" | grep -q '"enabled": *true' \
  && ok "mode événement actif ($(echo "$EVENT_STATUS" | grep -o '"announcements": *\[[^]]*\]' | grep -o '"text"' | wc -l) annonces)" \
  || ko "mode événement inactif : $EVENT_STATUS"

echo ""
echo "Tester une annonce : curl -X POST http://127.0.0.1:$PORT_LOCAL/api/event/announce/say"
