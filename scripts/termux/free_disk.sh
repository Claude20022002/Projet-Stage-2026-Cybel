#!/data/data/com.termux/files/usr/bin/bash
# Libère de l'espace avant bootstrap (tablette souvent >90 % pleine).
set -euo pipefail

echo "== Nettoyage espace Termux =="
df -h /data | tail -1

rm -rf "$PREFIX/var/cache/apt/archives/"* 2>/dev/null || true
pkg clean -y 2>/dev/null || apt-get clean -y 2>/dev/null || true
rm -rf "$HOME/.cache/pip" 2>/dev/null || true
python -m pip cache purge 2>/dev/null || true

echo "Après nettoyage :"
df -h /data | tail -1
