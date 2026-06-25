# Démarrage rapide — CYBEL

Commandes essentielles pour développer et tester sur **PC** (branche `main`).

Index : [docs/README.md](../README.md) · Robot : [ROBOT_CONNECTION.md](../ROBOT_CONNECTION.md)

---

## Prérequis

```powershell
python --version    # 3.11+
node --version      # 18+
pip install -r requirements.txt
cd frontend && npm install
cd ../frontend-kiosk && npm install
```

---

## Développement local (sans robot)

```powershell
# Depuis la racine du dépôt
python scripts/dev.py
```

| Service | URL |
|---------|-----|
| Backend API | http://127.0.0.1:8000 |
| Opérateur | http://127.0.0.1:5173 |
| Kiosque | http://127.0.0.1:5174/kiosk/ |

Mode simulation : `ROBOT_MOCK=true` dans `backend/.env`.

---

## Connexion robot (Wi-Fi)

```powershell
ping 10.42.0.1
ping 192.168.20.22

python scripts/robot_status.py
```

Configuration : `backend/.env` — voir [PHASE0_DEMARRAGE.md](../PHASE0_DEMARRAGE.md).

---

## Tests unitaires

```powershell
python -m pytest tests/ -q
```

---

## Déploiement kiosque (tablette Termux)

```powershell
cd frontend-kiosk && npm run build
python scripts/deploy_termux.py --host <IP_TABLETTE> --lite-only
```

Détails : [kiosque/TERMUX_DEPLOY.md](../kiosque/TERMUX_DEPLOY.md).

---

## Session labo

```powershell
.\scripts\preflight_labo.ps1 -TabletHost <IP_TABLETTE>
```

Procédure complète : [labo/TERRAIN.md](../labo/TERRAIN.md).
