# Plan d'implémentation — Option hybride Sentrymove + Kiosque CYBEL

**Version :** 1.0  
**Date :** juin 2026  
**Branche :** `feature/hybrid-sentrymove-kiosk`  
**Procédure opérateur :** [SENTRYMOVE_POI_SYNC.md](../SENTRYMOVE_POI_SYNC.md)

---

## 1. Objectif

| Rôle | Application | Rôle |
|------|-------------|------|
| **Superviseur / technicien** | Sentrymove (`com.ciot.sentrymove`) | Carte SLAM, POI, joystick, diagnostic |
| **Visiteur** | Kiosque CYBEL (`frontend-kiosk` + `CybelVisitorKiosk`) | Accueil, destinations, visite guidée |
| **Pont** | Sync POI ROS → `data/points.json` | Même navigation que Sentrymove (`/tag_manager/navi`) |

**Principe :** les POI sont créés dans Sentrymove (source de vérité sur le châssis), synchronisés vers CYBEL, et le kiosque navigue **par nom de POI**, pas par coordonnées estimées.

---

## 2. Architecture

```
Sentrymove (tablette) ──crée POI──► marker_manager (ROS)
                                        │
                    sync_poi_from_robot.py / POST /api/navigation/sync
                                        ▼
                              data/points.json
                                        │
                    frontend-kiosk ◄── cybel_lite.py
                         │
              /tag_manager/navi (comme Sentrymove)
```

---

## 3. Implémenté sur la branche

| ID | Tâche | Fichiers |
|----|-------|----------|
| H-001 | Branche Git | `feature/hybrid-sentrymove-kiosk` |
| H-002 | Plan + procédure | Ce fichier, `docs/SENTRYMOVE_POI_SYNC.md` |
| H-010 | Script sync CLI | `scripts/sync_poi_from_robot.py` |
| H-011 | Module sync | `sdk/poi_sync.py`, `sdk/marker_utils.py` |
| H-012 | API sync PC | `POST /api/navigation/sync` |
| H-013 | API sync tablette | `POST /api/navigation/sync`, `GET /api/navigation/points` (cybel_lite) |
| H-020 | Visite par POI | `data/lab_tour.json` → `target_point` (sans x/y/theta) |
| H-021 | Priorité POI > coords | `tour_service.py`, `cybel_lite.py`, `lab_tour.py` |
| H-015 | Tests | `tests/unit/test_poi_sync.py`, `test_lab_tour_poi.py` |

---

## 4. Travail sans robot (fait)

- Script sync + API (testables en `--dry-run` ou mock)
- `lab_tour.json` migré vers `target_point`
- Tests unitaires

## 5. Travail sur robot (demain)

1. Créer les 8 POI dans Sentrymove (noms exacts du tableau ci-dessous)
2. `python scripts/sync_poi_from_robot.py --host 192.168.20.22`
3. `python scripts/deploy_termux.py --host <IP> --lite-only`
4. Tester kiosque + visite guidée
5. Ajuster noms POI si différents dans Sentrymove

### Mapping arrêts → POI Sentrymove

| `target_point` dans lab_tour.json |
|-----------------------------------|
| Routeur CNC |
| Station LG-10 |
| Station LG-09 |
| Extraction et soufflage |
| Poste remplissage et bouchonnage |
| Thermoformage |
| Imprimante DTF C31 XP600 |
| Sérigraphie |

---

## 6. Commandes utiles

```powershell
# Sync POI (PC)
python scripts/sync_poi_from_robot.py --host 192.168.20.22

# Sync via API
curl -X POST http://127.0.0.1:8000/api/navigation/sync

# Deploy tablette
python scripts/deploy_termux.py --host 172.16.0.131 --lite-only

# Validation
python scripts/phase0_robot_check.py --host 192.168.20.22 --nav-poi "Routeur CNC"
pytest tests/unit/test_poi_sync.py tests/unit/test_lab_tour_poi.py -q
```

---

## 7. Critères de succès

- [ ] POI Sentrymove navigables individuellement
- [ ] Sync remplit `data/points.json`
- [ ] Kiosque affiche destinations synchronisées
- [ ] `POST /api/reception/go` → robot bouge
- [ ] Visite guidée 8 arrêts sans parole sans mouvement
- [ ] Sentrymove reste disponible comme superviseur

---

## 8. Rollback

```powershell
git checkout main
python scripts/deploy_termux.py --host <IP> --lite-only
```

Sentrymove n'est pas modifié — il reste utilisable indépendamment.

---

## Références

- [AUDIT_APK_CONSTRUCTEUR.md](AUDIT_APK_CONSTRUCTEUR.md)
- [TOUR_NAVIGATION.md](../TOUR_NAVIGATION.md)
- [CYBEL_GAP_ANALYSIS.md](../movement-audit/CYBEL_GAP_ANALYSIS.md)
