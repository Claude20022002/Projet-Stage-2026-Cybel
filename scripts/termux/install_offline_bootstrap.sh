#!/data/data/com.termux/files/usr/bin/bash
# Répare python + dépendances backend depuis le bundle offline embarqué
# (offline_bootstrap/ — voir son README.md pour la panne d'origine, 2026-07-15).
# AUCUN accès internet requis. Idempotent : sort immédiatement si tout marche.
#
# Pas de `set -e` : dpkg peut retourner une erreur non fatale (le postinst
# py3compile échoue dans certains contextes d'exécution, constaté sur le
# châssis CIOT) alors que python fonctionne parfaitement ensuite — le seul
# verdict fiable est le test d'import final.
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="$DIR/offline_bootstrap"

deps_ok() {
  python -c "import uvicorn, starlette, websockets" >/dev/null 2>&1
}

if deps_ok; then
  echo "Bootstrap offline : python + dépendances déjà fonctionnels — rien à faire."
  exit 0
fi

echo "Dépendances backend manquantes — réparation depuis $BUNDLE"

if [ ! -f "$BUNDLE/SHA256SUMS" ]; then
  echo "ERREUR: $BUNDLE/SHA256SUMS introuvable — bundle non déployé (deploy_termux.py)"
  exit 1
fi

echo "== 1/3 Vérification d'intégrité du bundle =="
if ! (cd "$BUNDLE" && sha256sum -c SHA256SUMS --quiet); then
  echo "ERREUR: bundle corrompu — redéployez depuis le PC (deploy_termux.py)"
  exit 1
fi

if ! python -c "import sys" >/dev/null 2>&1; then
  echo "== 2/3 Installation des paquets Termux (dpkg, offline) =="
  # Tous les .deb en une invocation : dpkg dépaquette tout puis configure tout,
  # ce qui résout l'ordre des dépendances entre eux.
  dpkg -i "$BUNDLE"/debs/*.deb || true
  dpkg --configure -a >/dev/null 2>&1 || true
  if ! python -c "import sys" >/dev/null 2>&1; then
    echo "ERREUR: python toujours inutilisable après dpkg — voir sortie ci-dessus"
    exit 1
  fi
else
  echo "== 2/3 python déjà fonctionnel — .deb ignorés =="
  # python-pip peut manquer même si python marche (paquets séparés depuis 3.14)
  if ! python -m pip --version >/dev/null 2>&1; then
    dpkg -i "$BUNDLE"/debs/python-pip_*.deb || true
    dpkg --configure -a >/dev/null 2>&1 || true
  fi
fi

echo "== 3/3 Installation des modules Python (pip, offline) =="
python -m pip install --no-index --find-links="$BUNDLE/wheels" \
  uvicorn starlette websockets

if deps_ok; then
  echo "OK — réparation offline terminée (python + uvicorn/starlette/websockets)."
  exit 0
fi
echo "ERREUR: les imports échouent encore après réparation — voir sortie ci-dessus"
exit 1
