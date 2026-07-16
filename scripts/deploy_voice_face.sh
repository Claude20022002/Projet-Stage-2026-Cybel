#!/usr/bin/env bash
# =============================================================================
# Déploiement + validation sur site (robot connecté en USB/ADB) des chantiers
# « chatbot vocal » et « reconnaissance faciale » sur l'app kiosque de test
# (CybelVisitorKioskTest, backend Termux ~/cybel-test/ port 8001).
#
# Reprend les incantations validées le 2026-07-15 : push via /data/local/tmp
# puis cp root, redémarrage backend via Termux RUN_COMMAND (seule méthode fiable),
# validation via `adb forward` + curl/python.
#
# Usage :
#   scripts/deploy_voice_face.sh                 # backend (code + dist) + validation
#   scripts/deploy_voice_face.sh --apk           # + build/install APK kiosque + micro
#   scripts/deploy_voice_face.sh --face          # + build/install FaceBridge + caméra
#   scripts/deploy_voice_face.sh --all           # tout
#   scripts/deploy_voice_face.sh --skip-build    # ne pas relancer npm run build
# =============================================================================
set -uo pipefail

# ---- Options -----------------------------------------------------------------
DO_APK=0; DO_FACE=0; SKIP_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --apk) DO_APK=1 ;;
    --face) DO_FACE=1 ;;
    --all) DO_APK=1; DO_FACE=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    *) echo "Option inconnue: $arg"; exit 2 ;;
  esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TERMUX_HOME="/data/data/com.termux/files/home"
CYBEL_TREE="$TERMUX_HOME/cybel-test"
TERMUX_OWNER=""              # uid:gid de l'app Termux — auto-détecté en préflight
PORT_LOCAL=18001             # port PC (adb forward) → 8001 sur la tablette
PORT_DEVICE=8001

ok(){ printf '  \033[32m✓\033[0m %s\n' "$1"; }
ko(){ printf '  \033[31m✗\033[0m %s\n' "$1"; }
step(){ printf '\n\033[36m== %s ==\033[0m\n' "$1"; }
fail(){ ko "$1"; exit 1; }

# push_root <local_path> <remote_dest_dir>  — copie un fichier/dossier vers l'arbre
# cybel-test avec les bons droits (via /data/local/tmp puis cp root).
push_root() {
  local src="$1" dest="$2" name src_win
  name="$(basename "$src")"
  # MSYS_NO_PATHCONV=1 protège le chemin DEVICE mais bloque aussi la conversion
  # du chemin LOCAL : adb.exe (binaire Windows) ne comprend pas /c/Users/…,
  # d'où une conversion explicite via cygpath.
  src_win="$(cygpath -m "$src" 2>/dev/null || echo "$src")"
  MSYS_NO_PATHCONV=1 adb push "$src_win" "/data/local/tmp/_dvf_$name" >/dev/null 2>&1 \
    || fail "push $name échoué"
  MSYS_NO_PATHCONV=1 adb shell "rm -rf '$dest/$name' && cp -r /data/local/tmp/_dvf_$name '$dest/$name' && chown -R $TERMUX_OWNER '$dest/$name' && rm -rf /data/local/tmp/_dvf_$name" \
    || fail "cp root de $name échoué"
}

run_termux() {  # exécute une commande bash dans Termux via RUN_COMMAND (background)
  local cmd="$1"
  MSYS_NO_PATHCONV=1 adb shell "am startservice -n com.termux/.app.RunCommandService \
    -a com.termux.RUN_COMMAND \
    --es com.termux.RUN_COMMAND_PATH '/data/data/com.termux/files/usr/bin/bash' \
    --esa com.termux.RUN_COMMAND_ARGUMENTS '-c,$cmd' \
    --es com.termux.RUN_COMMAND_WORKDIR '$TERMUX_HOME' \
    --ez com.termux.RUN_COMMAND_BACKGROUND true" >/dev/null 2>&1
}

# ---- 0. Préflight ------------------------------------------------------------
step "0. Préflight"
command -v adb >/dev/null || fail "adb introuvable dans le PATH"
adb get-state >/dev/null 2>&1 || fail "aucun appareil ADB (branchez la tête du robot en USB)"
ok "appareil ADB détecté : $(adb devices | awk 'NR==2{print $1}')"
MSYS_NO_PATHCONV=1 adb shell "test -d '$CYBEL_TREE'" \
  || fail "$CYBEL_TREE absent — déployez d'abord avec deploy_termux.py --target test"
ok "arbre cybel-test présent sur la tablette"
# Détecte le propriétaire (uid:gid) de l'arbre Termux — plus robuste qu'un uid codé en dur.
# tr -d ' ' : le stat toybox de cette tablette padde %U/%G avec des espaces.
TERMUX_OWNER="$(MSYS_NO_PATHCONV=1 adb shell "stat -c '%U:%G' '$CYBEL_TREE'" 2>/dev/null | tr -d ' \r\n')"
[ -n "$TERMUX_OWNER" ] || fail "impossible de déterminer le propriétaire Termux (accès root ADB ?)"
ok "propriétaire Termux : $TERMUX_OWNER"

# ---- 1. Build frontend kiosque ----------------------------------------------
if [ "$SKIP_BUILD" -eq 0 ]; then
  step "1. Build frontend-kiosk (UI micro)"
  ( cd "$REPO/frontend-kiosk" && npm run build ) >/dev/null 2>&1 \
    && ok "dist/ reconstruit" || fail "npm run build échoué"
else
  step "1. Build frontend-kiosk — ignoré (--skip-build)"
fi

# ---- 2. Push code backend ----------------------------------------------------
step "2. Déploiement code backend (cybel_lite + sdk + dist)"
push_root "$REPO/scripts/termux/cybel_lite.py" "$CYBEL_TREE/scripts/termux"
ok "cybel_lite.py (routes /api/voice + /api/visitors)"
# sdk complet (petit, pur Python) — garantit voice_commands.py + visitor_utils.py
# + knowledge_engine.py à jour, absents du déploiement de juin.
push_root "$REPO/sdk" "$CYBEL_TREE"
ok "sdk/ (voice_commands, visitor_utils, knowledge_engine…)"
# Bundle vocal offline (scripts d'auto-réparation) — cohérence avec cybel/
push_root "$REPO/scripts/termux/install_offline_bootstrap.sh" "$CYBEL_TREE/scripts/termux"
push_root "$REPO/frontend-kiosk/dist" "$CYBEL_TREE/frontend-kiosk"
ok "frontend-kiosk/dist (bouton micro + overlay)"
# FAQ statique (contenu, pas d'état device)
push_root "$REPO/data/hestim_knowledge_base.json" "$CYBEL_TREE/data"
ok "base de connaissances FAQ"

# ---- 3. Redémarrage backend --------------------------------------------------
step "3. Redémarrage backend test (stop → ensure)"
# stop explicite : sinon start voit l'ancien backend « déjà actif » et ne recharge pas.
run_termux "bash $CYBEL_TREE/scripts/termux/stop_cybel_test.sh; sleep 1; bash $CYBEL_TREE/scripts/termux/ensure_cybel_backend_test.sh > $TERMUX_HOME/dvf_start.log 2>&1"
printf '  attente du health check'
HEALTHY=0
for _ in $(seq 1 20); do
  sleep 1; printf '.'
  adb forward tcp:$PORT_LOCAL tcp:$PORT_DEVICE >/dev/null 2>&1
  if curl -sf -m 2 "http://127.0.0.1:$PORT_LOCAL/api/health" >/dev/null 2>&1; then
    HEALTHY=1; break
  fi
done
printf '\n'
[ "$HEALTHY" -eq 1 ] && ok "backend healthy sur :$PORT_DEVICE" \
  || { MSYS_NO_PATHCONV=1 adb shell "tail -20 $TERMUX_HOME/dvf_start.log" 2>/dev/null; fail "backend KO — voir log ci-dessus"; }

# ---- 4. Validation du moteur vocal ------------------------------------------
step "4. Validation /api/voice (moteur NLU)"
PYTHON_BIN="$(command -v python || command -v py || echo python)"
"$PYTHON_BIN" - "$PORT_LOCAL" <<'PYEOF'
import json, sys, urllib.request
port = sys.argv[1]
cases = [
    ("va a l'accueil", ("navigation", "faq")),   # POI ou FAQ selon contenu carte
    ("lance la visite guidee", ("action",)),      # → guided_tour (substring "visite")
    ("stop", ("action",)),                         # → stop_all
    ("quelle est la meteo", ("unknown",)),         # non reconnu
]
allok = True
for text, expected_kinds in cases:
    body = json.dumps({"text": text, "lang": "fr"}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/voice", body,
                                 {"Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=6))
        kind, ok_flag = r.get("kind"), r.get("ok")
        good = kind in expected_kinds
        allok = allok and good
        mark = "\033[32m✓\033[0m" if good else "\033[31m✗\033[0m"
        print(f"  {mark} {text!r:28} → kind={kind} ok={ok_flag}")
    except Exception as e:
        allok = False
        print(f"  \033[31m✗\033[0m {text!r:28} → erreur: {e}")
sys.exit(0 if allok else 1)
PYEOF
[ $? -eq 0 ] && ok "moteur vocal opérationnel" || ko "certains cas vocaux ont échoué (voir ci-dessus)"

# ---- 5. APK kiosque (optionnel) ---------------------------------------------
if [ "$DO_APK" -eq 1 ]; then
  step "5. Build + install APK kiosque (Vosk STT)"
  [ -n "${ANDROID_HOME:-}" ] || fail "ANDROID_HOME requis pour --apk"
  ( cd "$REPO/android/CybelVisitorKioskTest" && bash build.sh ) 2>&1 | tail -3
  APK="$REPO/android/CybelVisitorKioskTest/out/CybelVisitorKioskTest.apk"
  [ -f "$APK" ] || fail "APK non produit"
  APK_WIN="$(cygpath -m "$APK" 2>/dev/null || echo "$APK")"
  MSYS_NO_PATHCONV=1 adb install -r "$APK_WIN" >/dev/null 2>&1 || {
    MSYS_NO_PATHCONV=1 adb uninstall com.cybel.visitorkiosk.test >/dev/null 2>&1
    MSYS_NO_PATHCONV=1 adb install "$APK_WIN" >/dev/null 2>&1 || fail "install APK échouée"
  }
  ok "APK installé"
  MSYS_NO_PATHCONV=1 adb shell "pm grant com.cybel.visitorkiosk.test android.permission.RECORD_AUDIO" >/dev/null 2>&1
  ok "permission micro accordée"
  MSYS_NO_PATHCONV=1 adb shell "am force-stop com.cybel.visitorkiosk.test; monkey -p com.cybel.visitorkiosk.test -c android.intent.category.LAUNCHER 1" >/dev/null 2>&1
  ok "kiosque relancé"
  echo "  → testez : touchez 🎤 à l'écran et parlez ; observez avec :"
  echo "     adb logcat -s CybelVoice:* CybelKioskTest:*"
fi

# ---- 6. FaceBridge (optionnel) ----------------------------------------------
if [ "$DO_FACE" -eq 1 ]; then
  step "6. Build + install CybelFaceBridge (reconnaissance faciale)"
  [ -n "${ANDROID_HOME:-}" ] || fail "ANDROID_HOME requis pour --face"
  if [ ! -f "$REPO/android/CybelFaceBridge/assets/face_embedding.tflite" ]; then
    ko "modèle facial absent (android/CybelFaceBridge/assets/face_embedding.tflite)"
    echo "  → fournissez un modèle .tflite licencié avant --face (voir CybelFaceBridge/README.md)"
  else
    ( cd "$REPO/android/CybelFaceBridge" && bash build.sh ) 2>&1 | tail -3
    APKF="$REPO/android/CybelFaceBridge/out/CybelFaceBridge.apk"
    [ -f "$APKF" ] || fail "APK FaceBridge non produit"
    APKF_WIN="$(cygpath -m "$APKF" 2>/dev/null || echo "$APKF")"
    MSYS_NO_PATHCONV=1 adb install -r "$APKF_WIN" >/dev/null 2>&1 || {
      MSYS_NO_PATHCONV=1 adb uninstall com.cybel.facebridge >/dev/null 2>&1
      MSYS_NO_PATHCONV=1 adb install "$APKF_WIN" >/dev/null 2>&1 || fail "install FaceBridge échouée"
    }
    MSYS_NO_PATHCONV=1 adb shell "pm grant com.cybel.facebridge android.permission.CAMERA" >/dev/null 2>&1
    MSYS_NO_PATHCONV=1 adb shell "am startservice -n com.cybel.facebridge/.FaceRecognitionService" >/dev/null 2>&1
    ok "FaceBridge installé + caméra accordée + service lancé (port backend auto 8001/8000)"
    echo "  → observez : adb logcat -s CybelFaceService:* CybelBackendClient:*"
  fi
fi

# ---- Résumé ------------------------------------------------------------------
step "Terminé"
echo "  Backend test : http://127.0.0.1:$PORT_DEVICE (kiosque com.cybel.visitorkiosk.test)"
echo "  Forward PC actif : http://127.0.0.1:$PORT_LOCAL"
[ "$DO_APK" -eq 0 ] && echo "  (relancez avec --apk pour déployer le STT vocal sur la tablette)"
[ "$DO_FACE" -eq 0 ] && echo "  (relancez avec --face pour la reconnaissance faciale — modèle .tflite requis)"
