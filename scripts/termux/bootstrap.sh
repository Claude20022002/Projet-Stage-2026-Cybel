#!/data/data/com.termux/files/usr/bin/bash
# Première installation / mise à jour des dépendances Python sur Termux.
set -euo pipefail

CYBEL_HOME="${CYBEL_HOME:-$HOME/cybel}"
REQ="$CYBEL_HOME/backend/requirements.txt"

echo "== CYBEL bootstrap Termux =="
echo "CYBEL_HOME=$CYBEL_HOME"

bash "$CYBEL_HOME/scripts/termux/free_disk.sh" || true

FREE_KB="$(df /data 2>/dev/null | tail -1 | awk '{print $4}')"
echo "Espace libre: ${FREE_KB} Ko"
if [ -n "$FREE_KB" ] && [ "$FREE_KB" -lt 700000 ]; then
  echo "AVERTISSEMENT: moins de ~700 Mo libres — l'installation de Rust peut échouer."
  echo "Libérez de l'espace sur la tablette (apps, fichiers) puis relancez."
fi

if ! command -v python >/dev/null 2>&1; then
  echo "Installation de Python via pkg..."
  pkg update -y
  pkg install -y python
fi

if ! command -v rustc >/dev/null 2>&1; then
  echo "Installation de Rust (requis pour pydantic-core sur Termux)..."
  if pkg install -y rust binutils; then
    echo "Rust installé."
  else
    echo "Échec installation Rust — tentative pip avec binaires précompilés uniquement..."
  fi
fi

# Ne pas upgrader pip via pip sur Termux (conflit avec python-pip du pkg).
python -m pip install wheel 2>/dev/null || true

if [ ! -f "$REQ" ]; then
  echo "ERREUR: $REQ introuvable. Lancez deploy_termux.py depuis le PC."
  exit 1
fi

echo "Installation des dépendances backend (peut prendre 5–15 min sur la tablette)..."
if ! python -m pip install --no-cache-dir -r "$REQ"; then
  echo "Premier essai échoué — retry avec --prefer-binary..."
  python -m pip install --no-cache-dir --prefer-binary -r "$REQ" || {
    echo "ERREUR pip. Libérez >700 Mo sur /data puis: bash $CYBEL_HOME/scripts/termux/bootstrap.sh"
    exit 1
  }
fi

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
