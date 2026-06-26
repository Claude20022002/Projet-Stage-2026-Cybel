# Guide contrôleur — POI Deployment Tool → Kiosque CYBEL (TEST)

Formation opérateur : créer les points sur le robot, les synchroniser vers le kiosque visiteur **CybelVisitorKioskTest**, et maintenir le parcours guidé.

> **Public** : contrôleur / technicien labo HESTIM  
> **Application cible** : `CybelVisitorKioskTest` (backend `~/cybel-test`, port **8001**, variante **POI**)  
> **Documents liés** : [SENTRYMOVE_POI_SYNC.md](../SENTRYMOVE_POI_SYNC.md) · [TERRAIN.md](TERRAIN.md) · [TERMUX_DEPLOY.md](../TERMUX_DEPLOY.md)

---

## 1. Règle de nommage (obligatoire)

Les seuls POI reconnus par le robot et le kiosque sont ceux créés dans l'application **Deployment Tool** (Sentrymove) avec le format officiel :

| Règle | Exemple valide | Exemple obsolète (à ne plus utiliser) |
|-------|----------------|----------------------------------------|
| **MAJUSCULES** uniquement | `THERMOFORMAGE` | `Thermoformage` |
| Mots séparés par **tirets** `-` | `EXTRUSION-SOUFFLAGE` | `Extraction et soufflage` |
| Espace autorisé entre mots courts | `CNC ROUTEUR`, `IMPRIMANTE 3D` | `Routeur CNC` |
| Accents conservés | `SÉRIGRAPHIE` | `Sérigraphie` |

**Le nom saisi dans Deployment Tool doit être identique** au champ `target_point` dans `data/lab_tour.json` et au champ `name` dans `data/points.json`.

Les anciens libellés en minuscules / français (`Routeur CNC`, `Station LG-09`, etc.) sont **supprimés** du système : ils ne déclenchent plus la navigation.

---

## 2. Parcours visite actuel — carte **laboV2** (10 arrêts)

Fichier : `data/lab_tour.json` (`id: labo_v2`, `map_name: laboV2`).

> **Référence complète** : [POI_LABOV2.md](POI_LABOV2.md)

| Ordre | Équipement (affichage visiteur) | `target_point` (nom robot) |
|-------|----------------------------------|----------------------------|
| 1 | Porte laboratoire | `PORTE-LABO` |
| 2 | Routeur CNC | `CNC ROUTEUR` |
| 3 | Imprimante 3D | `IMPRIMANTE 3D` |
| 4 | Point machine | `POINT-MACHINE` |
| 5 | Thermoformage | `THERMOFORMAGE` |
| 6 | Extrusion et soufflage | `EXTRUSION-SOUFFLAGE` |
| 7 | Poste machine | `POSTE-MACHINE` *(ignoré si absent ROS)* |
| 8 | Poste remplissage et bouchonnage | `POSTE-REMPLISSAGE-BOUCHONNAGE` |
| 9 | Poste étiquetage | `POSTE-ETIQUETAGE` |
| 10 | Sérigraphie | `SÉRIGRAPHIE` |

**Point de charge** (`POINT-RECHARGE`) : créé dans Deployment Tool pour le retour pile — **pas** dans la visite guidée ni la grille destinations visiteur.

**Noms retirés** (ancienne carte, rejetés automatiquement) : `LG-10`, `LG-09`, `GAMME-CONTROLE-QUALITE`.

La carte active dans Deployment Tool doit être **laboV2**.

---

## 3. Créer ou modifier un POI sur le robot

### 3.1 Prérequis

- Robot allumé, tablette sur le même réseau (`192.168.20.22` ou hotspot `10.42.0.1`)
- Application **Sentrymove** / **Deployment Tool** installée
- Carte **laboV2** sélectionnée, robot **relocalisé**

### 3.2 Procédure

1. Ouvrir Sentrymove :
   ```powershell
   adb shell am start -n com.ciot.sentrymove/mc.csst.com.selfchassis.ui.activity.main.MainActivity
   ```
2. Connexion rosbridge : `ws://192.168.20.22:9090`
3. Placer le robot devant l'équipement (orientation finale = orientation du POI).
4. **Ajouter un marqueur** avec le nom au format **MAJUSCULES-TIRETS** (voir tableau §1).
5. Tester **« Naviguer vers ce marqueur »** depuis Sentrymove avant de passer à CYBEL.

---

## 4. Synchronisation POI vers CybelVisitorKioskTest

Chaîne : **Robot (ROS, carte courante)** → **`data/points.json`** → **tablette `~/cybel-test`** → **app TEST**.

### 4.0 Automatique (comportement par défaut)

| Moment | Action système |
|--------|----------------|
| Ouverture du kiosque | Sync ROS avant affichage de la grille destinations |
| Démarrage visite guidée | Sync ROS avant le premier déplacement |
| Changement de carte | POI absents de la nouvelle carte **supprimés** du cache local |

Si le robot est hors ligne : message d'erreur, pas d'affichage de POI fantômes (ancienne carte).

### 4.A — Sync manuelle depuis le PC (recommandé pour préparer le déploiement)

```powershell
cd C:\Users\clusa\Desktop\cybel
python scripts/sync_poi_from_robot.py --host 192.168.20.22
```

- Lit les marqueurs ROS (même source que Deployment Tool).
- **Remplace** `data/points.json` (ne fusionne plus avec l'ancien cache).
- Ignore les noms obsolètes (minuscules, brouillons).
- Marque les POI du parcours comme visibles sur le kiosque.

Simulation sans écriture :

```powershell
python scripts/sync_poi_from_robot.py --host 192.168.20.22 --dry-run
```

### 4.B — Déployer sur la tablette

**Option 1 — SSH Termux** (si mot de passe configuré) :

```powershell
python scripts/deploy_termux.py --host <IP_TABLETTE> --target test --lite-only
```

**Option 2 — ADB USB** (sans SSH) :

```powershell
python scripts/deploy_termux.py --bundle-only
adb push out/cybel-deploy.tar.gz /data/local/tmp/
adb shell "su -c 'cd /data/data/com.termux/files/home/cybel-test && tar xzf /data/local/tmp/cybel-deploy.tar.gz'"

adb push data/points.json /data/local/tmp/points.json
adb push data/lab_tour.json /data/local/tmp/lab_tour.json
adb push data/kiosk_config.poi.json /data/local/tmp/kiosk_config.poi.json
adb shell "su -c 'cp /data/local/tmp/points.json /data/data/com.termux/files/home/cybel-test/data/ && cp /data/local/tmp/lab_tour.json /data/data/com.termux/files/home/cybel-test/data/ && cp /data/local/tmp/kiosk_config.poi.json /data/data/com.termux/files/home/cybel-test/data/kiosk_config.json'"
```

Après mise à jour du code sync, pousser au minimum :

```powershell
adb push scripts/termux/cybel_lite.py /data/local/tmp/
adb push sdk/marker_utils.py /data/local/tmp/
adb shell "su -c 'cp /data/local/tmp/cybel_lite.py /data/data/com.termux/files/home/cybel-test/scripts/termux/ && cp /data/local/tmp/marker_utils.py /data/data/com.termux/files/home/cybel-test/sdk/'"
```

### 4.C — Redémarrer le backend TEST (port 8001)

Via **Termux RUN_COMMAND** (ne pas utiliser `su` seul — Python introuvable) :

```powershell
adb shell am startservice -n com.termux/com.termux.app.RunCommandService -a com.termux.RUN_COMMAND --es com.termux.RUN_COMMAND_PATH /data/data/com.termux/files/usr/bin/bash --esa com.termux.RUN_COMMAND_ARGUMENTS "-lc","bash ~/cybel-test/scripts/termux/stop_cybel_test.sh; CYBEL_HOME=~/cybel-test bash ~/cybel-test/scripts/termux/start_cybel_test.sh" --es com.termux.RUN_COMMAND_WORKDIR /data/data/com.termux/files/home --ez com.termux.RUN_COMMAND_BACKGROUND true
```

### 4.D — Sync API depuis la tablette (sans PC)

```bash
curl -X POST http://127.0.0.1:8001/api/navigation/sync
curl http://127.0.0.1:8001/api/navigation/points
curl http://127.0.0.1:8001/api/reception/destinations
```

`GET /api/reception/destinations` déclenche aussi la sync automatique et renvoie un **tableau** JSON.

### 4.E — Lancer l'application TEST

```powershell
adb install -r android/CybelVisitorKioskTest/out/CybelVisitorKioskTest.apk
adb shell am start -n com.cybel.visitorkiosk.test/.MainActivity
```

URL kiosque : `http://127.0.0.1:8001/kiosk/` (fichier `/sdcard/Download/cybel_kiosk_test_url.txt`).

---

## 5. Vérifications après mise à jour

| Contrôle | Commande / action | Résultat attendu |
|----------|-------------------|------------------|
| Santé backend | `curl http://127.0.0.1:8001/api/health` (via `adb forward`) | `"status":"ok"` |
| Liste POI | `GET /api/reception/destinations` | 12 POI laboV2, noms MAJUSCULES uniquement |
| Config kiosque | `GET /api/kiosk/config` | `"kiosk_variant":"poi"` |
| Parcours | `GET /api/tour` | 12 arrêts, `map_name: laboV2` |
| Navigation | Toucher `CNC ROUTEUR` sur la tablette | Robot se déplace |
| Visite guidée | Démarrer la visite | 12 arrêts, pas d'erreur « point inconnu » |
| Pas de fantômes | Après changement de carte | Anciens POI absents de la grille |

Smoke test robot depuis le PC :

```powershell
python scripts/phase0_robot_check.py --host 192.168.20.22 --nav-poi "CNC ROUTEUR"
```

---

## 6. Modifier le parcours guidé

Fichier : `data/lab_tour.json`

Pour ajouter un arrêt :

1. Créer le POI sur le robot (§3) avec le nom définitif.
2. Lancer la sync (§4.A) ou ouvrir le kiosque (sync auto §4.0).
3. Ajouter un bloc dans `stops` avec `"target_point": "NOM-EXACT-POI"`.
4. Redéployer `lab_tour.json` sur la tablette (§4.B).

**Ne jamais** mettre de libellé français en minuscules dans `target_point`.

---

## 7. Dépannage

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| « Point inconnu » | Nom différent robot / CYBEL | Vérifier nom exact dans Sentrymove, resync |
| POI fantômes (ancienne carte) | Backend pas à jour | Déployer `cybel_lite.py` + redémarrer :8001 |
| « Synchronisation POI impossible » | Robot hors ligne | Vérifier rosbridge, même réseau |
| POI en minuscules dans la liste | Marqueurs brouillon Sentrymove | Resync — filtre automatique |
| Robot ne bouge pas | Pas relocalisé / E-stop | Relocaliser via Sentrymove |
| Backend TEST down | Redémarrage via `su` | Utiliser RUN_COMMAND (§4.C) |
| Arrêt visite sauté | POI absent du robot | Créer le POI ou retirer l'arrêt du parcours |

---

## 8. Récapitulatif une page

```
Deployment Tool (carte laboV2)  →  nom MAJUSCULES-TIRETS
       ↓
ROS marker_manager  →  sync auto (kiosque / visite) ou sync_poi_from_robot.py
       ↓
data/points.json (remplacement, pas fusion)
       ↓
tablette ~/cybel-test :8001  →  CybelVisitorKioskTest
```

**Règle d'or** : le texte tapé dans Deployment Tool = le texte dans `target_point` = le texte affiché dans la liste des destinations du kiosque.

---

_Dernière mise à jour : juin 2026 — carte laboV2 (12 POI), sync automatique au démarrage kiosque / visite, élagage POI absents de la carte ROS_
