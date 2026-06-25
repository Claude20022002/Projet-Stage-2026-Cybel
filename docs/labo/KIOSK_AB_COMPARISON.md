# Comparaison A/B — kiosques CYBEL

> **Périmètre** : branche `feature/hybrid-sentrymove-kiosk` — **non mergée dans `main`** au juin 2026.
>
> Sur `main`, seul le kiosque **coords** (port 8000) est en production.

Index labo : [README.md](README.md) · Procédure : [TERRAIN.md](TERRAIN.md)

---

## Vue d'ensemble

| | **A — Production (`main`)** | **B — Test POI (hybrid)** |
|---|---|---|
| App | `CybelVisitorKiosk` | `CybelVisitorKioskTest` |
| Package | `com.cybel.visitorkiosk` | `com.cybel.visitorkiosk.test` |
| Label | CYBEL Accueil | CYBEL Accueil POI |
| Backend | `~/cybel` : **8000** | `~/cybel-test` : **8001** |
| Navigation | Coords `/navi_goal` | POI Sentrymove (`target_point`) |

---

## Activer la variante B

```powershell
git checkout feature/hybrid-sentrymove-kiosk
python scripts/sync_poi_from_robot.py --host 192.168.20.22
python scripts/deploy_termux.py --host <IP> --lite-only --target test
adb install -r android\CybelVisitorKioskTest\out\CybelVisitorKioskTest.apk
```

Plan détaillé : [06-plan-hybride-sentrymove-kiosk.md](../cybel-conception/06-plan-hybride-sentrymove-kiosk.md)

---

## Protocole de comparaison

| Arrêt | A coords | B POI | Notes |
|-------|----------|-------|-------|
| Routeur CNC | | | |
| Station LG-10 | | | |
| … (8 arrêts) | | | |

Critères : délai 1er mouvement, précision, TTS, « parle sans bouger », localisation.

---

## Retour arrière

```bash
adb uninstall com.cybel.visitorkiosk.test
bash ~/cybel-test/scripts/termux/stop_cybel_test.sh
```

L'app A et `~/cybel` restent intacts.
