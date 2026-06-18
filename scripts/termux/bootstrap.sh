#!/data/data/com.termux/files/usr/bin/bash
# Première installation / mise à jour des dépendances Python sur Termux.
set -euo pipefail

CYBEL_HOME="${CYBEL_HOME:-$HOME/cybel}"
REQ="$CYBEL_HOME/backend/requirements.txt"

echo "== CYBEL bootstrap Termux =="
echo "CYBEL_HOME=$CYBEL_HOME"

if ! command -v python >/dev/null 2>&1; then
  echo "Installation de Python via pkg..."
  pkg update -y
  pkg install -y python
fi

python -m pip install --upgrade pip wheel

if [ ! -f "$REQ" ]; then
  echo "ERREUR: $REQ introuvable. Lancez deploy_termux.py depuis le PC."
  exit 1
fi

echo "Installation des dépendances backend..."
python -m pip install -r "$REQ"

mkdir -p "$HOME/.termux/boot"
BOOT_SCRIPT="$HOME/.termux/boot/00-cybel.sh"
if [ -f "$CYBEL_HOME/scripts/termux/termux-boot.sh" ]; then
  cp "$CYBEL_HOME/scripts/termux/termux-boot.sh" "$BOOT_SCRIPT"
  chmod +x "$BOOT_SCRIPT"
  echo "Boot script installé: $BOOT_SCRIPT"
fi

echo ""
echo "Bootstrap terminé. Démarrez avec:"
echo "  bash $CYBEL_HOME/scripts/termux/start_cybel.sh"
