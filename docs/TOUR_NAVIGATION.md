# Visite guidée — diagnostic navigation et solutions

Document de référence pour les problèmes observés sur le robot **CIOT TY1251D** en conditions réelles (laboratoire HESTIM, juin 2026).

---

## 1. Symptôme rapporté

- Coordonnées modifiées dans `data/lab_tour.json` mais le robot **ne se rend pas** aux machines.
- Parole parfois décalée par rapport au mouvement.

---

## 2. Analyse du journal `tour_20260623_142601` (tablette)

Session récupérée via `GET /api/tour/trace` sur `172.16.0.131:8000`.

### Constat principal

| Indicateur | Valeur observée | Interprétation |
|------------|-----------------|----------------|
| Cibles chargées | 8 arrêts, coords OK | **Pas** un problème de fichier JSON |
| Pose au démarrage | (-6.00, 3.73), `nav_status: 604` | Robot déjà en **erreur navigation** |
| Après `/navi_goal` | `nav_status` → 601 (Prêt) | Goal publié mais **jamais accepté** |
| Pendant 14 s | Pose inchangée, distance 3.30 m | **Aucun mouvement** |
| `nav_status` | Jamais 602 (En navigation) | Le planificateur **n'a pas démarré** |
| Message affiché | « Échec 604 / obstacle » | **Trompeur** — vrai échec : objectif ignoré (601) |

### Conclusion

Le blocage n'est **pas** lié aux nouvelles coordonnées mais à l'**état du châssis** (604 au départ, puis 601 sans passage à 602). Causes probables :

1. Localisation insuffisante ou non lue sur la tablette.
2. Erreur navigation précédente non effacée.
3. Mode automatique incomplet au moment de l'envoi du goal.

---

## 3. Solutions implémentées dans CYBEL

### 3.1 Blocage du démarrage de visite

**Tablette (`cybel_lite.py`)** et **PC (`tour_service.py`)** refusent `POST /api/tour/start` si :

- `nav_status == 604` (erreur), `600` (non localisé) ou **`602` (navigation fantôme)** ;
- localisation &lt; **60 %** (`LOCALIZATION_MIN_PERCENT` dans `scripts/termux/cybel.env`).

Le kiosque affiche désormais le **message d'erreur exact** (toast) au lieu d'un échec silencieux.

Symptôme « rien ne se passe » : souvent HTTP **409** (visite refusée) ou attente longue avant relocalisation — le bouton reste grisé (`busy`) sans parole ni mouvement.

### 3.2 Récupération avant chaque objectif

Avant chaque `/navi_goal` ou `/poi go` :

1. Annulation : `/path_follower/cancel`, `/poi stop`, `/marker_manager/control stop` ;
2. Vitesse nulle ;
3. Mode auto : `/change_location_mode` mode `1` ;
4. Attente d'un état **601** ou **603** (max 8 s).

Module partagé : `sdk/tour_navigation.py`.

### 3.3 Relocalisation automatique (tablette)

Si la localisation est connue et &lt; 60 % :

1. Appel `/global_localization` ;
2. Attente sur `/localization_confidence` (jusqu'à 45 s).

### 3.4 Messages d'erreur corrigés

Fonction `navigation_wait_failure_message()` — distingue :

- **Objectif ignoré** (`nav_status` reste 601, jamais 602) ;
- **Erreur en cours** (`nav_status` 604) ;
- **Non localisé** (600).

Inclut la **distance résiduelle** à la cible quand disponible.

### 3.5 Journal de visite (`sdk/tour_trace.py`)

Pendant la visite :

- Fichier : `data/logs/tour/tour_YYYYMMDD_HHMMSS.log` ;
- API : `GET /api/tour/trace` ;
- Événements : pose, cible, `nav_status`, distance, progression toutes les 3 s.

### 3.6 Synchronisation parole (tablette)

Attente de la fin réelle du service `CybelTTSBridge` (pas seulement une estimation de durée).

---

## 4. Procédure opérateur recommandée

```
1. Placer le robot dans une zone connue de la carte SLAM
2. Interface opérateur (PC) → Relocaliser → attendre ≥ 60 %
3. Vérifier nav_status = 601 (Prêt), pas 604
4. Lancer la visite depuis le kiosque
5. Si échec → consulter GET /api/tour/trace ou le fichier .log
```

En cas d'échec persistant :

- Tester **Naviguer vers coordonnées** depuis le PC vers un point du parcours ;
- Si le PC ne bouge pas non plus → problème robot / ROS / carte, pas CYBEL ;
- Si le PC fonctionne mais pas la tablette → vérifier `ROBOT_HOST=192.168.20.22` sur Termux.

---

## 5. Déploiement après mise à jour

```powershell
# Depuis le PC (pas en SSH Termux)
cd C:\Users\clusa\Desktop\cybel
python scripts/deploy_termux.py --skip-kiosk-build --lite-only --host 172.16.0.131
```

```bash
# Sur la tablette
bash ~/cybel/scripts/termux/start_cybel.sh
```

Redémarrer aussi `python scripts/dev.py` sur le PC pour le backend opérateur.

---

## 6. Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `sdk/tour_navigation.py` | Prérequis visite, messages d'erreur |
| `sdk/tour_trace.py` | Journal structuré |
| `scripts/termux/cybel_lite.py` | Backend kiosque + garde-fous |
| `backend/services/tour_service.py` | Visite côté PC |
| `sdk/real_robot.py` | Récupération 604/600 avant nav |
| `data/lab_tour.json` | Parcours (coords à calibrer sur carte SLAM) |

---

## 7. Codes `nav_status`

| Code | Libellé | Action |
|------|---------|--------|
| 600 | En initialisation | Relocaliser |
| 601 | Prêt | OK pour envoyer un goal |
| 602 | En navigation | Normal pendant trajet |
| 603 | Arrivé | OK en fin de segment |
| 604 | Erreur | Annuler, relocaliser, réessayer |

---

## 8. Références

- Déploiement tablette : [TERMUX_DEPLOY.md](TERMUX_DEPLOY.md)
- Connexion robot : [ROBOT_CONNECTION.md](ROBOT_CONNECTION.md)
- TTS : [TTS_BRIDGE.md](TTS_BRIDGE.md)
