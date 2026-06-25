# Session labo — CYBEL

Procédures **terrain** : robot physique, validation navigation, déploiement tablette.

Index : [docs/README.md](../README.md)

---

## Par où commencer

| Étape | Ressource |
|-------|-----------|
| 1. Vérifications auto | [`scripts/preflight_labo.ps1`](../../scripts/preflight_labo.ps1) |
| 2. Procédure complète | **[TERRAIN.md](TERRAIN.md)** |
| 3. Smoke test PC | [guides/PHASE0_DEMARRAGE.md](../guides/PHASE0_DEMARRAGE.md) |

---

## Documents

| Document | Description |
|----------|-------------|
| [TERRAIN.md](TERRAIN.md) | **Étapes + commandes** (production `main`) |
| [KIOSK_AB_COMPARISON.md](KIOSK_AB_COMPARISON.md) | Comparaison coords vs POI (branche hybrid) |

---

## Branche `main` vs hybrid

| | **`main`** | `feature/hybrid-sentrymove-kiosk` |
|---|-----------|-----------------------------------|
| Navigation visite | Coordonnées `/navi_goal` | POI Sentrymove (`target_point`) |
| Kiosque | `CybelVisitorKiosk` :8000 | + `CybelVisitorKioskTest` :8001 |
| Sync POI | Non requis | `scripts/sync_poi_from_robot.py` |
