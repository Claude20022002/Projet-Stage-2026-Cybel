# Analyse des écarts — SentryMove vs CYBEL / Accueil Visite

> Objectif : expliquer pourquoi le robot bouge dans Deployment Tool mais plus (ou mal) dans CYBEL, et proposer des corrections.

---

## Synthèse exécutive

| Canal | Deployment Tool | CYBEL | Compatible ? |
|-------|-----------------|-------|--------------|
| Transport | WebSocket `:9090` | WebSocket `:9090` | ✅ |
| Téléop topic | `/cmd_vel_mux/input/teleop` | Idem | ✅ |
| Téléop prérequis | Aucun mode explicite | Mode manuel si `control_state==30` | ⚠️ **Écart bloquant** |
| Nav coordonnées | `/navi_goal` | `/navi_goal` | ✅ |
| Nav POI | `/tag_manager/navi` → `/poi` | Idem (SDK) ; `/poi` seul (lite) | ⚠️ |
| Nav prérequis | Localisation implicite | `nav_status` 601 + loc ≥ 60 % | ⚠️ **Écart bloquant** |
| MQTT mouvement | Aucun | Aucun | ✅ |
| Annulation | Chaîne complète | SDK OK ; lite partiel | ⚠️ |

**Cause probable « ça marchait avant » :** CYBEL a migré vers le bon topic (`cmd_vel_mux`) mais a ajouté des **garde-fous plus stricts** (mode manuel, localisation, confirmation mode) et certains chemins legacy (`cybel_lite`, scripts) utilisent encore d’**anciens topics**.

---

## Tableau des écarts détaillé

### E1 — Mode manuel requis pour téléop (🔴 bloquant téléop)

| | Deployment Tool | CYBEL |
|---|-----------------|-------|
| Comportement | Joystick actif dès connexion | `RealRobot.move()` refuse si `control_state==30` sans mode manuel |
| Fichier | `MainPresenter` — pas d’appel `change_mode` avant téléop | `sdk/real_robot.py` L691–704 |
| UI | — | Toggle « Mode manuel » `frontend/src/robotUi.ts` |

**Impact :** Le panneau contrôleur CYBEL **ne déplace pas** tant que l’utilisateur n’active pas le mode manuel — Deployment Tool n’a pas cette étape.

**Correction proposée :**

```python
# Option A — parité constructeur : autoriser téléop sans change_mode
# Dans move(), ne pas bloquer si control_state==30 pour publish cmd_vel_mux

# Option B — garder garde-fou mais auto-activer mode manuel au 1er move()
async def move(...):
    if self.status.control_state == 30:
        await self.set_manual_mode(True)
    await self._publish_velocity(...)
```

---

### E2 — Topic téléop legacy dans scripts / lite (🔴 si utilisé)

| | Ancien | Actuel constructeur |
|---|--------|---------------------|
| Topic | `/mobile_base/commands/velocity` | `/cmd_vel_mux/input/teleop` |
| Fichiers | `robot_move.py`, `teleop_test.py`, `cybel_lite.py` (stop) | `sdk/constants.py`, `real_robot.py` |

**Impact :** Scripts de test ou annulation lite n’atteignent pas le mux → robot immobile.

**Correction :** Remplacer toutes les occurrences par `ROS_TOPICS["teleop"]` ; supprimer alias legacy.

---

### E3 — `advertise` avant `publish` (🟠 bloquant si absent)

| | Deployment Tool | CYBEL SDK |
|---|-----------------|-----------|
| Séquence | `initVelocity()` → advertise puis publish | `advertise` au 1er `move()` ✅ |
| Scripts legacy | Pas d’advertise | ❌ |

**Correction :** Déjà OK dans SDK ; vérifier que le 1er `move()` passe bien par `RealRobot`.

---

### E4 — Échelle vitesse et rampe (🟡 ressenti, pas blocage total)

| Paramètre | Deployment Tool | CYBEL frontend |
|-----------|-----------------|----------------|
| Linear max | 0.3 / 0.5 / 0.8 m/s | 0.2 m/s fixe |
| Angular | `wz × 0.8`, max 0.64 | ±0.5 direct |
| Fréquence | 10 Hz + rampe | ~5 Hz, pas de rampe |

**Impact :** Mouvement plus lent ou saccadé dans CYBEL, mais **pas zéro**.

**Correction :** Aligner `MOVE_SPEED` sur `getChassisSpeed()` ; timer 100 ms ; `angular_z *= 0.8`.

---

### E5 — Navigation autonome : localisation (🔴 bloquant nav)

| | Deployment Tool | CYBEL |
|---|-----------------|-------|
| Check explicite | Implicite côté stack ROS | `nav_status==600` → refus |
| Relocalisation auto | `global_locate` manuel UI | `ensure_localization()` au démarrage nav |
| Seuil | — | 60 % (`matching_degree`) |

**Impact :** Kiosque / réception : TTS puis erreur « robot non localisé » — **corrigé récemment** en appelant relocalisation **avant** TTS (`reception_service`, `cybel_lite`).

**Correction restante :** Vérifier que `matching_degree` est bien lu (fix `tour_navigation.parse_localization_percent`).

---

### E6 — `change_location_mode` mode 1 + confirmation (🟠 nav auto)

| | Deployment Tool | CYBEL SDK | cybel_lite |
|---|-----------------|-----------|------------|
| Avant nav | Variable | `ensure_automatic_navigation()` + wait | `sleep(0.5)` sans confirmation |
| Échec silencieux | — | Retourne `False` | Retourne `True` toujours |

**Impact :** Nav peut échouer si le robot reste en mode manuel ou en 602/604.

**Correction lite :** Réutiliser logique `_wait_control_mode` du SDK.

---

### E7 — Chaîne POI `/tag_manager/navi` (🟠 certains POI)

| | SDK CYBEL | cybel_lite |
|---|-----------|------------|
| Ordre | `/tag_manager/navi` puis `/poi` | `/poi` seul |

**Impact :** POI « Extraction et soufflage » peut nécessiter `tag_manager` sur firmware récent.

**Correction lite :** Importer `build_poi_nav_chain` de `sdk/ros_ops.py`.

---

### E8 — Annulation incomplète (🟠 état 604 persistant)

| Action | SDK | cybel_lite |
|--------|-----|------------|
| `/move_base/cancel` | ✅ | ❌ |
| Vitesse zéro sur cmd_vel_mux | ✅ | ❌ (mobile_base) |

**Impact :** Robot bloqué en 604 après échec → nav suivante impossible.

---

### E9 — Ordre TTS puis navigation (🔴 UX kiosque)

| | Avant fix | Après fix |
|---|-----------|-----------|
| `go_destination` | Parle puis nav | Prérequis loc **avant** TTS |

**Fichiers :** `reception_service.py`, `cybel_lite.go_destination`.

---

### E10 — Accueil Visite (CybelVisitorKiosk)

| Fonction | Mécanisme | Mouvement direct ? |
|----------|-----------|-------------------|
| Kiosque tablette | HTTP → `cybel_lite` / backend | Via `/api/reception/go`, `/api/tour/start` |
| Téléop | **Non exposé** | — |
| Backend auto-start | `BackendStarter.java` → Termux | — |

**Impact :** Le kiosque ne pilote pas le joystick ; tout passe par **navigation autonome** → écarts **E5, E6, E7** s’appliquent.

---

## Matrice impact / correction

| ID | Empêche téléop ? | Empêche nav auto ? | Priorité | Effort |
|----|------------------|-------------------|----------|--------|
| E1 | ✅ Oui | Non | P0 | 1–2 h |
| E2 | Si legacy | Si lite stop | P0 | 1 h |
| E5 | Non | ✅ Oui | P0 | Fait partiellement |
| E6 | Non | ✅ Souvent | P1 | 2 h |
| E7 | Non | ✅ Parfois | P1 | 1 h |
| E8 | Non | ✅ Après erreur | P1 | 1 h |
| E4 | Non (lent) | Non | P2 | 2 h |

---

## Plan de correction CYBEL (ordre recommandé)

### P0 — Déblocage immédiat ✅ (implémenté)

1. **Téléop panneau contrôleur** : `RealRobot.move()` active le mode manuel automatiquement au premier déplacement (visites inchangées : `set_manual_mode(False)` au démarrage).
2. **cybel_lite** : `cmd_vel_mux` pour arrêt, chaîne POI `/tag_manager/navi` → `/poi`, `ensure_auto_navigation` avec attente `nav_status` 601/603, annulation complète (`move_base/cancel`).
3. **Scripts** : `robot_move.py`, `teleop_test.py` alignés sur `/cmd_vel_mux/input/teleop`.

### P1 — Parité navigation

4. Relocalisation systématique avant nav (déjà en cours).
5. Annulation complète alignée SDK dans lite.
6. Tests `phase0_robot_check.py` sur robot réel.

### P2 — Finesse constructeur

7. Rampe 10 Hz + échelle angular ×0.8.
8. Exposer `/velocity_control` dans Paramètres opérateur.

---

## Tests de validation

| Test | Commande / action | Succès |
|------|-------------------|--------|
| Téléop SDK | Mode manuel ON → flèches panneau | `nav_status` inchangé, pose change |
| Téléop parité | Flèches sans mode manuel (après fix E1) | Idem Deployment Tool |
| Nav POI | Kiosque → « Extraction et soufflage » | `nav_status` 602 puis 603 |
| Capture APK | `python scripts/joystick_capture.py` | Voir publishes sur cmd_vel_mux |
| Phase 0 | `python scripts/phase0_robot_check.py --host <IP>` | Tous checks verts |

---

## Réponse finale à la question mission

> *Quelles instructions exactes lorsque le robot avance, recule, tourne, et comment reproduire dans CYBEL ?*

| Action | Deployment Tool envoie | CYBEL doit envoyer (identique) |
|--------|------------------------|--------------------------------|
| Avancer | `publish /cmd_vel_mux/input/teleop` — `linear.x` +0.5 (rampe), `angular.z=0` | Idem via `RealRobot._publish_velocity(0.5, 0)` |
| Reculer | `linear.x` -0.5 | `_publish_velocity(-0.5, 0)` |
| Gauche | `angular.z` +0.64, `linear.x=0` | `_publish_velocity(0, 0.64)` ou `0.8→×0.8` |
| Droite | `angular.z` -0.64 | `_publish_velocity(0, -0.64)` |
| Stop | `linear.x=0`, `angular.z=0` | Idem |

**Plus :** `advertise` Twist une fois ; **ne pas** exiger `/change_location_mode` mode 0 pour téléop (différence actuelle CYBEL).

Pour **navigation autonome** (kiosque) : après prérequis loc + mode auto, `publish /navi_goal` ou `call_service /tag_manager/navi` — déjà implémenté dans SDK, à renforcer dans lite.

---

## Documents liés

- `MOVEMENT_ARCHITECTURE.md` — graphe composants
- `ROS_COMMUNICATION.md` — topics, services, payloads
- `MQTT_COMMUNICATION.md` — MQTT hors mouvement
- `JOYSTICK_FLOW.md` — flux joystick détaillé
- `docs/cybel-conception/AUDIT_APK_CONSTRUCTEUR.md` — audit APK complet
