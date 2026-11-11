#!/usr/bin/env bash
# =============================================================================
# Déploie le backend embarqué CYBEL (cybel_lite) sur le Raspberry Pi compagnon,
# depuis le PC (Git Bash), par SSH. Voir docs/cybel-conception/08-architecture-pi5-compagnon.md.
#
#   1. build du kiosque (frontend-kiosk/dist, servi par cybel_lite)
#   2. copie du code de l'arbre de travail (modifications non commitées comprises)
#   3. dépendances Python, réinstallées seulement si les requirements changent
#   4. service systemd utilisateur « cybel » installé/redémarré, puis contrôle de santé
#
# Conservé sur le Pi : .venv, cybel-pi.env (config), et les fichiers existants de
# data/ (visiteurs, POI synchronisés, config modifiée par le panneau staff) —
# seuls les fichiers de data/ absents du Pi sont ajoutés.
#
# Usage :
#   scripts/deploy_pi.sh                  # déploiement complet
#   scripts/deploy_pi.sh --skip-build     # sans npm run build
#   scripts/deploy_pi.sh --tests          # + tests unitaires sur le Pi
#   scripts/deploy_pi.sh --no-restart     # copie sans redémarrer le service
#
# Cible : CYBEL_PI_HOST (défaut 192.168.11.113), CYBEL_PI_USER (cybel),
#         CYBEL_PI_KEY (~/.ssh/cybel_pi). Depuis PowerShell :
#   & "C:\Program Files\Git\bin\bash.exe" scripts/deploy_pi.sh
# =============================================================================
set -uo pipefail

SKIP_BUILD=0; RUN_TESTS=0; RESTART=1
for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=1 ;;
    --tests) RUN_TESTS=1 ;;
    --no-restart) RESTART=0 ;;
    *) echo "Option inconnue: $arg"; exit 2 ;;
  esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_HOST="${CYBEL_PI_HOST:-192.168.11.113}"
PI_USER="${CYBEL_PI_USER:-cybel}"
PI_KEY="${CYBEL_PI_KEY:-$HOME/.ssh/cybel_pi}"
CODE_DIRS=(sdk backend scripts tests frontend frontend-kiosk pytest.ini)

ok(){ printf '  \033[32m✓\033[0m %s\n' "$1"; }
ko(){ printf '  \033[31m✗\033[0m %s\n' "$1"; }
step(){ printf '\n\033[36m== %s ==\033[0m\n' "$1"; }
fail(){ ko "$1"; exit 1; }

pi(){ ssh -o BatchMode=yes -o ConnectTimeout=10 -o IdentitiesOnly=yes -i "$PI_KEY" "$PI_USER@$PI_HOST" "$@"; }

# ---- 0. Préflight ------------------------------------------------------------
step "0. Préflight ($PI_USER@$PI_HOST)"
[ -f "$PI_KEY" ] || fail "clé SSH absente : $PI_KEY"
pi true 2>/dev/null || fail "SSH impossible vers $PI_USER@$PI_HOST (adresse ? clé installée ?)"
ok "connexion SSH"
TOKEN="$(grep -E '^CYBEL_HEAD_TOKEN=' "$REPO/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r')"
[ -n "$TOKEN" ] && ok "jeton de l'agent de la tête trouvé dans .env" \
  || ko "CYBEL_HEAD_TOKEN absent de .env : l'agent de la tête refusera les requêtes"

# ---- 1. Build kiosque ----------------------------------------------------------
if [ "$SKIP_BUILD" -eq 0 ]; then
  step "1. Build frontend-kiosk"
  ( cd "$REPO/frontend-kiosk" && npm run build ) >/dev/null 2>&1 \
    && ok "dist/ reconstruit" || fail "npm run build échoué"
else
  step "1. Build frontend-kiosk — ignoré (--skip-build)"
fi
[ -d "$REPO/frontend-kiosk/dist" ] || fail "frontend-kiosk/dist absent : relancer sans --skip-build"

# ---- 2. Copie du code ----------------------------------------------------------
step "2. Copie du code"
VERSION="$(git -C "$REPO" rev-parse --short HEAD)$(git -C "$REPO" diff --quiet HEAD -- "${CODE_DIRS[@]}" data || echo '+modifs')"
# Fichiers suivis + non suivis non ignorés, plus le kiosque construit (ignoré par git).
( cd "$REPO" && { git ls-files -co --exclude-standard "${CODE_DIRS[@]}" data; find frontend-kiosk/dist -type f; } \
    | sort -u | tar -cf - -T - ) \
  | pi "set -e
        cd ~/cybel 2>/dev/null || { mkdir -p ~/cybel && cd ~/cybel; }
        rm -rf .incoming && mkdir .incoming && tar -xf - -C .incoming
        rm -rf ${CODE_DIRS[*]}
        for d in ${CODE_DIRS[*]}; do [ -e .incoming/\$d ] && mv .incoming/\$d .; done
        mkdir -p data && tar -C .incoming -cf - data | tar -C . -xf - --skip-old-files
        rm -rf .incoming
        echo '$VERSION' > .deploye" \
  && ok "code copié (version $VERSION) ; data/ existant conservé" || fail "copie échouée"

pi 'umask 077; cat > ~/cybel/.secrets.env' <<< "CYBEL_HEAD_TOKEN=$TOKEN" && ok "jeton écrit (~/cybel/.secrets.env, 600)"
pi '[ -f ~/cybel/cybel-pi.env ] && echo present || { cp ~/cybel/scripts/pi/cybel-pi.env.example ~/cybel/cybel-pi.env && echo cree; }' \
  | grep -q cree && ok "cybel-pi.env créé depuis le modèle" || ok "cybel-pi.env existant conservé"

# ---- 3. Dépendances Python -------------------------------------------------------
step "3. Dépendances Python"
pi 'set -e; cd ~/cybel
    [ -x .venv/bin/python ] || python3 -m venv .venv
    HASH="$(cat backend/requirements.txt tests/requirements.txt | sha256sum | cut -c1-16)"
    if [ "$(cat .venv/.req-hash 2>/dev/null)" = "$HASH" ]; then echo inchangees; exit 0; fi
    .venv/bin/pip install -q --upgrade pip
    .venv/bin/pip install -q -r backend/requirements.txt -r tests/requirements.txt
    echo "$HASH" > .venv/.req-hash; echo installees' \
  | tail -1 | while read -r r; do ok "dépendances $r"; done
[ "${PIPESTATUS[0]}" -eq 0 ] || fail "installation des dépendances échouée"

if [ "$RUN_TESTS" -eq 1 ]; then
  step "3b. Tests unitaires sur le Pi"
  pi 'cd ~/cybel && .venv/bin/python -m pytest tests/unit -q -p no:cacheprovider 2>&1 | tail -1' \
    | while read -r r; do ok "$r"; done
fi

# ---- 4. Service systemd utilisateur ----------------------------------------------
step "4. Service « cybel »"
pi 'mkdir -p ~/.config/systemd/user && cp ~/cybel/scripts/pi/cybel.service ~/.config/systemd/user/cybel.service \
    && systemctl --user daemon-reload && systemctl --user enable cybel >/dev/null 2>&1' \
  && ok "service installé et activé au démarrage" || fail "installation du service échouée"
if [ "$(pi 'loginctl show-user "$USER" -p Linger --value' 2>/dev/null)" != "yes" ]; then
  ko "démarrage au boot sans session : à activer une fois sur le Pi → sudo loginctl enable-linger $PI_USER"
fi

if [ "$RESTART" -eq 0 ]; then
  step "5. Redémarrage — ignoré (--no-restart)"
  exit 0
fi
pi 'systemctl --user restart cybel' && ok "service redémarré" || fail "redémarrage échoué"

# ---- 5. Contrôle de santé ---------------------------------------------------------
step "5. Contrôle"
HEALTH="$(pi 'PORT=$(grep -E "^BACKEND_PORT=" ~/cybel/cybel-pi.env | cut -d= -f2); PORT=${PORT:-8001}
  for i in $(seq 1 30); do curl -s -m 2 "localhost:$PORT/api/health" && exit 0; sleep 1; done; exit 1')" \
  || { ko "le backend ne répond pas"; pi 'journalctl --user -u cybel -n 20 --no-pager'; exit 1; }
ok "backend répond : $HEALTH"
echo "$HEALTH" | grep -q '"android_bridge":"remote"' \
  || ko "actions Android en mode local : renseigner CYBEL_HEAD_AGENT_URL dans ~/cybel/cybel-pi.env (au labo)"
echo ""
echo "Journal : ssh -i $PI_KEY $PI_USER@$PI_HOST journalctl --user -u cybel -f"
