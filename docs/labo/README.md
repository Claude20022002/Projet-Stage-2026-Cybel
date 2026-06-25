# Session labo — CYBEL

Documentation **terrain** : procédures, commandes et tests A/B kiosque (coords vs POI Sentrymove).

## Par où commencer ?

| Étape | Document / outil |
|-------|------------------|
| **1. Vérifications auto** | [`scripts/preflight_labo.ps1`](../../scripts/preflight_labo.ps1) |
| **2. Procédure complète** | **[TERRAIN.md](TERRAIN.md)** ← guide pas à pas |
| **3. Comparaison A/B** | [KIOSK_AB_COMPARISON.md](KIOSK_AB_COMPARISON.md) |
| **4. Sync POI ROS** | [SENTRYMOVE_POI_SYNC.md](../SENTRYMOVE_POI_SYNC.md) |
| **5. Plan hybride** | [06-plan-hybride-sentrymove-kiosk.md](../cybel-conception/06-plan-hybride-sentrymove-kiosk.md) |

## Preflight (30 secondes)

```powershell
cd C:\Users\clusa\Desktop\cybel
.\scripts\preflight_labo.ps1 -TabletHost <IP_TABLETTE>
```

Codes de sortie : `0` = OK · `1` = échecs · `2` = avertissements seulement.

Variables d'environnement optionnelles : `CYBEL_TERMUX_HOST`, `CYBEL_TERMUX_PORT`, `CYBEL_TERMUX_USER`.

## Fichiers associés

| Fichier | Rôle |
|---------|------|
| `data/lab_tour.json` | 8 arrêts visite (`target_point` en branche POI) |
| `data/points.json` | POI synchronisés depuis le robot |
| `android/CybelVisitorKioskTest/out/*.apk` | APK test POI (port 8001) |
| `scripts/deploy_termux.py --target test` | Déploiement backend `~/cybel-test` |

## Voir aussi

- [Déploiement Termux](../TERMUX_DEPLOY.md)
- [Kiosque visiteur](../VISITOR_KIOSK.md)
- [Connexion robot](../ROBOT_CONNECTION.md)
