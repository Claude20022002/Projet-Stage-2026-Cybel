# Plan d'implémentation — Option hybride Sentrymove + Kiosque CYBEL

<<<<<<< HEAD
**Version :** 1.0  
=======
**Version :** 1.1  
>>>>>>> feature/face-presence
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
<<<<<<< HEAD
Sentrymove (tablette) ──crée POI──► marker_manager (ROS)
                                        │
                    sync_poi_from_robot.py / POST /api/navigation/sync
                                        ▼
                              data/points.json
                                        │
                    frontend-kiosk ◄── cybel_lite.py
=======
Sentrymove (tablette) ──crée POI──► marker_manager (ROS, carte courante)
                                        │
          sync auto (kiosque / visite)  │  sync manuelle
          GET /reception/destinations   │  sync_poi_from_robot.py
          POST /tour/start              │  POST /api/navigation/sync
                                        ▼
                              data/points.json (remplacement)
                                        │
                    frontend-kiosk ◄── cybel_lite.py / backend FastAPI
>>>>>>> feature/face-presence
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
<<<<<<< HEAD
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
=======
| H-014 | **Sync auto ouverture kiosque** | `GET /api/reception/destinations` → `ensure_poi_synced_from_robot` / `sync_poi_from_ros_map` |
| H-015 | **Sync auto démarrage visite** | `POST /api/tour/start` (avant prérequis navigation) |
| H-016 | **Élagage POI absents carte** | `merge_point_dicts`, `merge_robot_points` — remplace au lieu de fusionner |
| H-020 | Visite par POI | `data/lab_tour.json` → `target_point` (carte laboV2, 12 arrêts) |
| H-021 | Priorité POI > coords | `tour_service.py`, `cybel_lite.py`, `lab_tour.py` |
| H-022 | Tests élagage | `tests/unit/test_poi_sync.py` → `test_merge_point_dicts_prunes_absent_from_ros` |
| H-023 | Bootstrap backend | `backend/services/poi_bootstrap.py` |

---

## 4. Carte laboV2 — mapping arrêts

| `target_point` |
|----------------|
| `PORTE-LABO` |
| `CNC ROUTEUR` |
| `LG-10` |
| `IMPRIMANTE 3D` |
| `POINT-MACHINE` |
| `THERMOFORMAGE` |
| `EXTRUSION-SOUFFLAGE` |
| `POSTE-MACHINE` |
| `POSTE-REMPLISSAGE-BOUCHONNAGE` |
| `POSTE-ETIQUETAGE` |
| `GAMME-CONTROLE-QUALITE` |
| `SÉRIGRAPHIE` |

---

## 5. Commandes utiles
>>>>>>> feature/face-presence

```powershell
# Sync POI (PC)
python scripts/sync_poi_from_robot.py --host 192.168.20.22

# Sync via API
curl -X POST http://127.0.0.1:8000/api/navigation/sync
<<<<<<< HEAD

# Deploy tablette
python scripts/deploy_termux.py --host 172.16.0.131 --lite-only

# Validation
python scripts/phase0_robot_check.py --host 192.168.20.22 --nav-poi "Routeur CNC"
=======
curl -X POST http://127.0.0.1:8001/api/navigation/sync

# Vérifier destinations (déclenche sync auto)
adb forward tcp:18001 tcp:8001
curl http://127.0.0.1:18001/api/reception/destinations

# Deploy tablette TEST
python scripts/deploy_termux.py --host 172.16.0.132 --target test --lite-only

# Validation
python scripts/phase0_robot_check.py --host 192.168.20.22 --nav-poi "CNC ROUTEUR"
>>>>>>> feature/face-presence
pytest tests/unit/test_poi_sync.py tests/unit/test_lab_tour_poi.py -q
```

---

<<<<<<< HEAD
## 7. Critères de succès

- [ ] POI Sentrymove navigables individuellement
- [ ] Sync remplit `data/points.json`
- [ ] Kiosque affiche destinations synchronisées
- [ ] `POST /api/reception/go` → robot bouge
- [ ] Visite guidée 8 arrêts sans parole sans mouvement
- [ ] Sentrymove reste disponible comme superviseur

---

## 8. Rollback
=======
## 6. Critères de succès

- [x] POI Sentrymove navigables individuellement
- [x] Sync remplit `data/points.json` (remplacement, pas fusion)
- [x] Kiosque affiche destinations synchronisées (sync auto à l'ouverture)
- [x] POI absents de la carte ROS ne s'affichent plus
- [ ] `POST /api/reception/go` → robot bouge (terrain)
- [ ] Visite guidée 12 arrêts laboV2 sans parole sans mouvement
- [x] Sentrymove reste disponible comme superviseur

---

## 7. Rollback
>>>>>>> feature/face-presence

```powershell
git checkout main
python scripts/deploy_termux.py --host <IP> --lite-only
```

Sentrymove n'est pas modifié — il reste utilisable indépendamment.

---

## Références

- [AUDIT_APK_CONSTRUCTEUR.md](AUDIT_APK_CONSTRUCTEUR.md)
- [TOUR_NAVIGATION.md](../TOUR_NAVIGATION.md)
<<<<<<< HEAD
=======
- [GUIDE_CONTROLEUR_POI.md](../labo/GUIDE_CONTROLEUR_POI.md)
>>>>>>> feature/face-presence
- [CYBEL_GAP_ANALYSIS.md](../movement-audit/CYBEL_GAP_ANALYSIS.md)
