# POI carte laboV2 — référence opérationnelle

> **Carte active :** `laboV2` (Deployment Tool / Sentrymove)  
> **Backend kiosque :** `~/cybel-test`, port **8001**, APK **CYBEL Accueil** (`CybelVisitorKioskTest`)  
> **Branche :** `feature/face-presence` (POI + présence)

---

## Principe

| Règle | Détail |
|-------|--------|
| **Source de vérité** | Marqueurs ROS lus via `/marker_manager/get_markers_details` (Deployment Tool uniquement) |
| **Cache local** | `data/points.json` est **remplacé** à chaque sync — pas de fusion avec l'ancienne carte |
| **Visite guidée** | Seuls les arrêts de `data/lab_tour.json` dont le `target_point` existe sur la carte courante |
| **Kiosque visiteur** | Seuls les POI du parcours avec `kiosk_visible: true` (hors charge) |
| **Point de charge** | Présent dans ROS (`POINT-RECHARGE`) mais **exclu** visite et grille destinations |

### Déclencheurs de synchronisation

| Moment | Endpoint |
|--------|----------|
| Ouverture grille destinations | `GET /api/reception/destinations` |
| Démarrage visite guidée | `POST /api/tour/start` |
| Manuel (opérateur) | `POST /api/navigation/sync` |

---

## POI Deployment Tool (état terrain juin 2026)

### Sur la carte ROS (10 marqueurs)

| POI | Rôle | Kiosque visiteur | Visite guidée |
|-----|------|------------------|---------------|
| `PORTE-LABO` | Entrée / accueil | Oui | Oui (1) |
| `CNC ROUTEUR` | Routeur CNC | Oui | Oui (2) |
| `IMPRIMANTE 3D` | Fabrication additive | Oui | Oui (3) |
| `POINT-MACHINE` | Plateau pédagogique | Oui | Oui (4) |
| `THERMOFORMAGE` | Plasturgie | Oui | Oui (5) |
| `EXTRUSION-SOUFFLAGE` | Extrusion / soufflage | Oui | Oui (6) |
| `POSTE-REMPLISSAGE-BOUCHONNAGE` | Conditionnement | Oui | Oui (8) |
| `POSTE-ETIQUETAGE` | Étiquetage | Oui | Oui (9) |
| `SÉRIGRAPHIE` | Textile | Oui | Oui (10) |
| `POINT-RECHARGE` | Borne de charge | **Non** | **Non** |

### Configuré visite mais absent du Deployment Tool

| POI | Statut |
|-----|--------|
| `POSTE-MACHINE` | Encore dans `lab_tour.json` — **ignoré automatiquement** au démarrage si absent de ROS |

### Retirés (ancienne carte — liste noire)

Ces noms sont **rejetés** même s'ils restent dans ROS ou un ancien cache :

- `LG-10`, `LG-09`
- `GAMME-CONTROLE-QUALITE`

Module : `sdk/poi_names.py` → `OBSOLETE_POI_NAMES`, `is_visitor_poi()`, `is_charge_poi_name()`.

---

## Parcours visite (`data/lab_tour.json`)

**10 arrêts** configurés (ordre d'affichage) :

1. `PORTE-LABO` — Entrée du laboratoire  
2. `CNC ROUTEUR` — Routeur CNC  
3. `IMPRIMANTE 3D` — Imprimante 3D  
4. `POINT-MACHINE` — Point machine  
5. `THERMOFORMAGE` — Thermoformage  
6. `EXTRUSION-SOUFFLAGE` — Extrusion et soufflage  
7. `POSTE-MACHINE` — Poste machine *(ignoré si absent ROS)*  
8. `POSTE-REMPLISSAGE-BOUCHONNAGE` — Remplissage / bouchonnage  
9. `POSTE-ETIQUETAGE` — Étiquetage  
10. `SÉRIGRAPHIE` — Sérigraphie  

Au lancement, `filter_tour_by_poi()` ne conserve que les arrêts présents sur la carte et éligibles visiteur.

---

## Vérification rapide

```powershell
adb forward tcp:18001 tcp:8001

# Tous les POI ROS (Deployment Tool)
curl -s http://127.0.0.1:18001/api/navigation/points

# Destinations visiteur (sans charge)
curl -s http://127.0.0.1:18001/api/reception/destinations

# Parcours configuré
curl -s http://127.0.0.1:18001/api/tour
```

Attendu (juin 2026) : **10** POI ROS dont `POINT-RECHARGE` avec `kiosk_visible: false` ; **9** destinations kiosque.

---

## Fichiers et modules

| Fichier | Rôle |
|---------|------|
| `data/lab_tour.json` | Parcours et ordre des arrêts |
| `data/points.json` | Cache synchronisé depuis ROS |
| `data/knowledgeV2-labV2.json` | FAQ / réponses vocales par zone |
| `sdk/poi_names.py` | Filtres noms (obsolètes, charge, format) |
| `sdk/marker_utils.py` | `merge_point_dicts` — remplacement cache |
| `sdk/lab_tour.py` | `filter_tour_by_poi` |
| `sdk/poi_sync.py` | Sync PC → `points.json` |
| `scripts/termux/cybel_lite.py` | Sync tablette + kiosque |

---

## Tests unitaires

```powershell
pytest tests/unit/test_poi_sync.py tests/unit/test_poi_charge.py tests/unit/test_lab_tour_filter.py tests/unit/test_poi_names.py -q
```

---

## Documents liés

- [SENTRYMOVE_POI_SYNC.md](../SENTRYMOVE_POI_SYNC.md) — procédure sync  
- [GUIDE_CONTROLEUR_POI.md](GUIDE_CONTROLEUR_POI.md) — formation opérateur  
- [TERRAIN.md](TERRAIN.md) — session labo  
- [FACE_PRESENCE.md](../FACE_PRESENCE.md) — détection de présence (branche en cours)  
- [PROMOTE_KIOSK_TEST.md](PROMOTE_KIOSK_TEST.md) — app principale POI

_Dernière mise à jour : 27 juin 2026_
