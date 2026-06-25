#!/data/data/com.termux/files/usr/bin/bash
# Configure Termux pour le démarrage auto du backend CYBEL (app Accueil + boot).
set -euo pipefail

CYBEL_HOME="${CYBEL_HOME:-$HOME/cybel}"
TERMUX_PROPS="$HOME/.termux/termux.properties"
BOOT_DIR="$HOME/.termux/boot"
BOOT_LINK="$BOOT_DIR/00-cybel.sh"

mkdir -p "$HOME/.termux" "$BOOT_DIR"

touch "$TERMUX_PROPS"
if ! grep -q '^allow-external-apps=true' "$TERMUX_PROPS" 2>/dev/null; then
  echo "allow-external-apps=true" >>"$TERMUX_PROPS"
  echo "Ajouté allow-external-apps=true dans $TERMUX_PROPS"
else
  echo "allow-external-apps=true déjà présent"
fi

if [ -f "$CYBEL_HOME/scripts/termux/termux-boot.sh" ]; then
  cp "$CYBEL_HOME/scripts/termux/termux-boot.sh" "$BOOT_LINK"
  chmod +x "$BOOT_LINK"
  echo "Hook boot Termux : $BOOT_LINK"
fi

chmod +x "$CYBEL_HOME/scripts/termux/"*.sh 2>/dev/null || true

echo ""
echo "Étapes manuelles sur la tablette :"
echo "  1. Installer Termux:Boot (F-Droid) pour le démarrage au boot Android"
echo "  2. Ouvrir Termux une fois après mise à jour pour valider RUN_COMMAND"
echo "  3. Lancer CYBEL Accueil — le backend démarre automatiquement"
echo ""
echo "Test : bash $CYBEL_HOME/scripts/termux/ensure_cybel_backend.sh"
