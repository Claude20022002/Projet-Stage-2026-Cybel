# Bundle de réparation offline — Termux (tête Android)

Paquets vendorés pour réinstaller **python + les dépendances du backend lite**
sur la tablette **sans aucun accès internet** (le Wi-Fi du robot est un réseau
isolé, sans DNS ni route vers l'extérieur).

## Pourquoi ce bundle existe (panne du 2026-07-15)

Le bootstrap Termux s'est retrouvé réextrait (bash/coreutils réinstallés, datés
du jour) **sans le paquet `python`** : l'app kiosque a affiché la notification
*« Termux Plugin Execution Command Error — bash not found »*, puis, une fois
bash revenu, le backend ne pouvait plus démarrer (`python: No such file or
directory`, puis `ModuleNotFoundError: uvicorn`). Sans internet sur place,
`pkg install python` était impossible — la réparation a dû passer par un
transfert manuel de ces .deb/.whl via ADB depuis le PC.

Ce bundle rend cette réparation **automatique** : `ensure_cybel_backend.sh`
détecte les dépendances manquantes au démarrage et lance
[`../install_offline_bootstrap.sh`](../install_offline_bootstrap.sh).

## Contenu

| Dossier | Source | Contenu |
|---------|--------|---------|
| `debs/` | packages.termux.dev (dépôt officiel Termux, aarch64) | `python` 3.14.6, `python-pip`, et leurs dépendances absentes du bootstrap de base (gdbm, libexpat, libffi, libsqlite, libcrypt, libandroid-posix-semaphore, ncurses + ncurses-ui-libs) |
| `wheels/` | PyPI (wheels purs Python, `py3-none-any`) | `uvicorn` 0.51.0, `starlette` 1.3.1, `websockets` 16.1 + dépendances (anyio, click, h11, idna) |
| `SHA256SUMS` | — | Empreintes vérifiées à la récupération (correspondent aux valeurs publiées par les dépôts d'origine) |

> **starlette ≥ 1.x** a supprimé l'API `@app.on_event(...)` — `cybel_lite.py`
> utilise désormais le paramètre `lifespan` (corrigé le 2026-07-15). Si vous
> remplacez les wheels par d'autres versions, gardez cette contrainte en tête.

## Mise à jour du bundle (depuis un PC connecté)

```bash
# .deb : https://packages.termux.dev/apt/termux-main/ (architecture aarch64)
# wheels : pip download <pkg> --only-binary=:all: --platform any \
#            --python-version 314 --implementation py --abi none
# Puis régénérer les empreintes :
cd scripts/termux/offline_bootstrap && sha256sum debs/*.deb wheels/*.whl > SHA256SUMS
```

Vérifiez les SHA256 contre ceux publiés par les dépôts d'origine avant de
committer, et testez `install_offline_bootstrap.sh` sur la tablette.
