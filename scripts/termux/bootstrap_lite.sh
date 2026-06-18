#!/data/data/com.termux/files/usr/bin/bash
# Bootstrap léger — starlette/uvicorn sans pydantic (pas de Rust).
set -euo pipefail

CYBEL_HOME="${CYBEL_HOME:-$HOME/cybel}"
REQ="$CYBEL_HOME/scripts/termux/requirements-lite.txt"

bash "$CYBEL_HOME/scripts/termux/free_disk.sh" || true

if ! command -v python >/dev/null 2>&1; then
  pkg update -y
  pkg install -y python
fi

echo "Installation dépendances lite (starlette, uvicorn, websockets)..."
python -m pip install --no-cache-dir -r "$REQ"

touch "$CYBEL_HOME/scripts/termux/.use_lite"
echo "Mode lite activé — $(python -c 'import starlette,uvicorn,websockets; print(\"OK\")')"
