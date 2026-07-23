# Changelog CYBEL

## [0.5.0] — 2026-07-23

### Session de validation terrain complète (branche `feature/nav-performance`) — bugs "commande acquittée mais robot immobile", TTS anglais, données papier, UI kiosque

Journée complète de test en direct sur le châssis CIOT TY1251D-03195 (Wi-Fi
robot, tunnel `adb forward tcp:18001 tcp:8001` vers le backend Termux).
Plusieurs bugs réels trouvés et corrigés, tous du même type : rosbridge
acquitte un appel avec `"result": true` sans que le robot exécute quoi que ce
soit — le piège "transport ≠ exécution" déjà documenté dans l'article H4,
retrouvé cette fois dans notre **propre** code, pas seulement chez le
constructeur.

#### Relocalisation et retour borne — arguments de service manquants

- **`/global_locate`** (`sdk/ros_ops.py`, `scripts/termux/cybel_lite.py`) est
  un service **typé** `yutong_assistance/GlobalLocate` (champ `cmd` requis,
  `GLOBAL=0`), pas un service vide. Nos appels envoyaient `args={}` → aucune
  réponse (timeout), et le code basculait silencieusement sur
  `/global_localization` (`std_srvs/Empty`, un service de repli qui accuse
  "succès" sans provoquer de rotation réelle). Découvert via
  `/rosapi/service_request_details` (méthodologie de triangulation de
  l'article, appliquée à notre propre stack). Fix : arguments typés corrects
  envoyés en priorité à `/global_locate`.
- **`/start_recharge`** est le même genre de service typé
  (`yutong_assistance/cmd`, énumération générique `Start=1`/`Stop=2` réutilisée
  par le constructeur sur plusieurs services différents avec un sens propre à
  chacun). Notre code appelait ce service avec des arguments vides puis, après
  correction, avec `cmd=1` en supposant que "Start" déclenchait le retour à la
  borne — **testé en direct : ça fait au contraire quitter la borne**
  (probablement un service d'enregistrement de trajet de charge, pas un
  déclencheur de navigation). `go_home()`/`return_charge` utilisent maintenant
  la **navigation POI standard** vers `return_point` (`data/lab_tour.json`,
  "POINT-RECHARGE"), déjà validée à 100 % (3/3 essais) par la visite guidée
  (`scripts/termux/cybel_lite.py`, `sdk/real_robot.py`).
- **Gap de déploiement corrigé** : `data/lab_tour.json` n'était jamais poussé
  par `scripts/deploy_voice_face.sh` — la tablette gardait un exemplaire
  périmé sans `return_point`, faisant échouer silencieusement le retour
  borne même après le fix ci-dessus. Ajouté au script + repli défensif sur
  "POINT-RECHARGE" si le champ est absent.
- `nav_status` inhabituels rencontrés en direct (600 après redémarrage
  backend, 914 après l'essai `/start_recharge` cmd=1) : notre code de
  récupération automatique ne les couvre pas encore. **Méthode fiable
  confirmée en direct : utiliser l'app constructeur Deployment Tool**
  (relocaliser / déplacer manuellement) plutôt que nos appels ROS
  reconstruits, le temps d'investiguer plus avant.

#### TTS anglais — bug de locale de bout en bout

- `android/CybelTTSBridge` fixait `tts.setLanguage(Locale.FRENCH)` une seule
  fois à l'init, sans lien avec la langue du texte reçu — l'anglais était lu
  avec des règles phonétiques françaises. Le paramètre `lang` (déjà bien geré
  pour le choix du texte `speech_en`/`reponse_en`) n'était simplement jamais
  transmis jusqu'au bridge Android. Fix de bout en bout : intent `SPEAK`
  (`SpeakReceiver`/`SpeakService.applyLocale()`, repli français si la voix
  anglaise n'est pas installée) ← `speak_local(text, lang)`
  (`cybel_lite.py`) ← `RobotSpeech.speak(text, lang=...)` (`sdk/speech.py`,
  `sdk/real_robot.py`, `sdk/mock_robot.py`) ← `POST /api/speech/say`
  (`lang` ajouté à `SpeechRequest`). Validé en direct : anglais nettement
  mieux prononcé.

#### Reconnaissance faciale — garde-fou de distance manquant

- Le déclenchement du salut par présence châssis (`onPeople`) filtrait déjà
  par distance (`presence_max_distance_m`), mais le déclenchement par
  reconnaissance faciale (`onVisitorIdentified`) saluait dès qu'un visage
  était reconnu, **sans notion de distance** — un visiteur juste de passage
  pouvait déclencher le salut à tort. `frontend-kiosk/src/app.ts` exige
  maintenant que le capteur de présence châssis confirme aussi quelqu'un à
  portée (`isSomeoneNearby()`) avant de saluer sur reconnaissance faciale.

#### Interface kiosque

- `frontend-kiosk/src/icons.ts` (nouveau) : 13 émojis-icônes remplacés par du
  SVG inline, cohérent avec `frontend/src/icons/index.ts` (interface
  opérateur). Effet d'appui tactile générique sur tous les boutons,
  `prefers-reduced-motion` ajouté. Logo HESTIM + titre "Fablab" dans le
  header persistant.
- `GET`/`DELETE /api/visitors` (interface opérateur) lisaient un magasin
  local jamais synchronisé avec le robot — la liste "Visiteurs enrôlés"
  pouvait afficher 0 alors que des visiteurs étaient bien reconnus en direct.
  Relayé vers le backend Termux (même schéma que `enroll-trigger`).
  `backend/config.py` : bug de résolution `.env` relatif au répertoire de
  travail (jamais le bon avec `cwd=BACKEND_DIR` dans `scripts/dev.py`) —
  chemin maintenant ancré sur `ROOT`. `kiosk_backend_url` par défaut corrigé
  (pointait vers une IP/port périmés).

#### Données terrain pour l'article (`paper/icra_2027/main.tex`)

Les 7 `\ph{}` restants remplacés par des mesures réelles : visite guidée
100 % (3 essais), uptime Termux 0,6 h, FAQ 56,2 % (48 essais de
reformulation, `scripts/measure_faq_repeat_rate.py`, nouveau), latence voix
979–23046 ms/12 essais et faux déclenchements mot d'éveil 0/10 sur 0,3 h
(`sdk/voice_trace.py` + `scripts/measure_voice_latency.py`, nouveaux,
instrumentation bout-en-bout). Recompilé : toujours 8 pages, dépassements de
marge corrigés.

- Bug corrigé dans `scripts/collect_paper_data.py` (`phase_tour`) :
  `if "error" in st` testait la présence de la clé (toujours vraie, le champ
  vaut `null` en fonctionnement normal) au lieu de sa valeur — le script
  bouclait indéfiniment en pensant que chaque sondage de statut échouait,
  alors que la visite se déroulait normalement.

## [0.4.1] — 2026-07-19

### Réactivité navigation + salutations vocales (branche `feature/nav-performance`)

- **Court-circuit navigation** : `ensure_auto_navigation()` et
  `recover_navigation_state()` (`cybel_lite.py`) annulaient systématiquement
  toute navigation et redemandaient le mode automatique à *chaque* commande,
  même quand le robot était déjà prêt (601/603) et déjà en mode auto — deux
  aller-retours ROS + 0,5 s payés pour rien dans le cas majoritaire. Les deux
  fonctions court-circuitent maintenant si le robot est déjà prêt **et** déjà
  en mode auto (dérivé de `control_state`, pas seulement du champ `nav_mode`
  brut, pour ne pas rater un passage en manuel/téléop). Confirmé plus rapide
  en test réel.
- **Réponse aux salutations** : nouvelle action `greeting` (parlée
  uniquement, sans `target_point`) déclenchée par « bonjour », « salut »,
  « coucou », « bonsoir », « hello » après le mot d'éveil ou le bouton micro.
- **`/velocity_control` câblé** (service constructeur documenté mais jamais
  exposé — voir `docs/movement-audit/CYBEL_GAP_ANALYSIS.md`, item P2) :
  `GET`/`POST /api/settings/velocity` pour lire et changer le profil de
  vitesse max du châssis (sécurité/équilibre/efficacité, 0.3/0.5/0.8 m/s).
  Lecture validée en direct (confirme le réglage usine « équilibre ») ;
  écriture implémentée, validation terrain en direct restante.
- **Bug de déploiement corrigé** : `actions.json` n'était jamais poussé par
  `scripts/deploy_voice_face.sh`, faisant échouer silencieusement toute
  nouvelle action ajoutée à `VOICE_COMMAND_MAP` (« Action inconnue »).
- Article scientifique (`paper/`) retargeté de ROSCon Korea 2027 vers
  **IEEE ICRA 2027** (Séoul, deadline 2026-09-15) ; titre raccourci, sections
  chatbot vocal/reconnaissance faciale mises à jour pour refléter la
  validation terrain — voir `paper/icra_2027/`.

## [0.4.0] — 2026-07-17

### Validation terrain complète — chatbot vocal + reconnaissance faciale (branche `feature/face-presence`)

Première session de validation en conditions réelles sur le châssis CIOT
TY1251D-03195, avec correctifs trouvés et appliqués en direct.

#### STT — grammaire fermée dynamique + mot d'éveil

- **Vocabulaire fermé pour Vosk** : `sdk/voice_commands.build_vocabulary()`
  (actions connues + POI actuellement déployés + questions/mots-clés FAQ) au
  lieu de la dictée libre, qui confondait systématiquement les noms propres du
  site (« HESTIM », noms de salles). Servi par `GET /api/voice/vocabulary`
  (`cybel_lite.py`), recalculé à la volée — pas de rebuild APK au changement
  de POI/FAQ.
- **Mot d'éveil « Hé Cybel »** : échec total constaté sur le robot réel — le
  modèle Vosk « small » n'a pas de repli phonétique (G2P) pour les mots hors
  dictionnaire, et « Cybel » n'existe dans aucun lexique français. Contourné
  avec **« Hé si belle »** (`/si bɛl/`), composé de deux mots réels déjà connus
  du modèle, phonétiquement très proche.
- **Filet de secours navigation** : le STT contraint tronque souvent le verbe
  et la préposition (« va jusqu'à Stendhal » → « jusqu stendhal ») ;
  `_NAV_FALLBACK_PATTERN` reconnaît une destination après le seul mot « jusqu »
  quand le motif verbe+préposition complet ne matche pas.
- **Encodage javac** : `-encoding UTF-8` ajouté aux trois `build.sh` Android
  (`CybelVisitorKioskTest`, `CybelFaceBridge`, `CybelTTSBridge`) — sans elle,
  javac lisait les sources en Cp1252 sous Windows et corrompait tout littéral
  accentué (grammaire du mot d'éveil illisible en mémoire).

#### Corrections terrain

- **TTS épelait les majuscules** : les runs de 2+ majuscules (POI type
  `PORTE-LABO`, sigles comme `HESTIM`) déclenchaient l'épellation lettre par
  lettre du moteur TTS Android. Corrigé par `_tts_friendly()` (titre-casse
  avant synthèse, jamais à l'affichage écran).
- **Faux positifs FAQ** : seuil `score < 2.0` de `backend/services/
  knowledge_service.py` absent du portage `cybel_lite.py` — un mot générique
  suffisait à matcher n'importe quelle question. Aligné.
- **Chevauchement TTS/écoute** : le mot d'éveil se réarmait immédiatement
  après transcription, avant même que la réponse (potentiellement longue —
  une FAQ) commence à être prononcée ; sans annulation d'écho sur ce matériel,
  le micro captait sa propre voix, écrasant parfois un affichage FAQ correct
  par un « non compris » pendant que la réponse finissait de se lire.
  `CybelVoiceBridge.resumeWakeListening()` : le JS relance l'écoute
  explicitement une fois la durée de parole estimée écoulée (filet natif à
  6 s si jamais appelé).

#### Dialogue proactif — proposition de visite

- Après l'accueil (reconnaissance faciale **ou** détection de présence
  châssis — un seul déclencheur suffit désormais, cooldown partagé), le
  robot demande « Voulez-vous faire une visite ? », puis « un point précis ou
  la visite complète ? » selon la réponse — dialogue enchaîné sans repasser
  par le bouton micro entre chaque tour de parole (`speakAndListen()`,
  estimation de durée de parole avant réouverture du micro).
- Fonctionne pour n'importe quel visiteur, identifié ou non.

#### Reconnaissance faciale — modèle réel vendorisé

- **FaceNet** (davidsandberg/facenet, code MIT), poids CASIA-WebFace/VGGFace2
  — **pas** MS-Celeb-1M. Provenance documentée dans
  `android/CybelFaceBridge/README.md` après recherche des alternatives
  (aucune option prête à l'emploi avec provenance irréprochable trouvée).
  Extrait et vérifié (SHA256) depuis une release Android open-source publique
  via `fetch_face_model.sh`, dans le même esprit que `fetch_vosk_model.sh`.
  Prétraitement `(pixel − 127.5) / 128.0`, entrée 160×160, vérifié dans la
  source amont.
- **Validé terrain** : enrôlement + identification continue fonctionnels de
  bout en bout sur le châssis réel (premier test réussi avec un modèle réel,
  après plusieurs sessions bloquées sur l'absence de modèle).

#### Interface opérateur — gestion des visiteurs

- Nouvel onglet **Visiteurs** (`frontend/`) : enrôlement à distance (relais
  `backend/` → `cybel_lite.py` via `kiosk_backend_url`, `am broadcast` local
  côté tablette), statut de détection en direct sans transmission d'image
  (WebSocket direct vers le kiosque, `{type: "face_status"}`), liste des
  visiteurs enrôlés avec suppression.

#### Tests

- 154 → 159 tests unitaires (vocabulaire STT, filet de secours navigation,
  relais d'enrôlement à distance) ; `tsc`/`npm run build` verts sur
  `frontend/` et `frontend-kiosk/`.

## [0.3.6] — 2026-07-15

### Chatbot vocal — parler au robot (branche `feature/face-presence`)

- **STT hors-ligne Vosk** intégré à l'app kiosque `CybelVisitorKioskTest` :
  pont `window.CybelVoice` (`@JavascriptInterface`) + `VoiceRecognizer.java`
  (modèle `vosk-model-small-fr-0.22`, Apache 2.0, récupéré/vérifié au build via
  `fetch_vosk_model.sh`) ; runtime vosk-android 0.3.47 + JNA vendorisés
- **Moteur NLU partagé** : nouveau `sdk/voice_commands.py` (sans pydantic —
  extraction depuis `reception_actions.py`, rétrocompat totale) ; réutilisé par
  le backend PC et le backend Termux
- **Backend robot** : `POST /api/voice` dans `cybel_lite.py`
  (`handle_voice_command` : action → navigation POI → FAQ), diffusion WebSocket
  `{type:"voice"}` ; alias `/api/voice` côté backend PC (contrat unique)
- **UI kiosque** : bouton « Parler au robot » 🎤 + overlay écoute/traitement/
  réponse (`frontend-kiosk`), `api.voice()`, handler télémétrie `onVoice`
- **Reconnaissance faciale** : `CybelFaceBridge` cible désormais un port
  auto-adaptatif (8001 kiosque test puis 8000 prod) au lieu de 8000 codé en dur
- **Tests** : `test_voice_commands.py` (11 tests) ; suite complète 147 verts ;
  `/api/voice` vérifié en live (visite guidée, POI, FAQ, non compris) ; APK
  kiosque test build+signé validé (modèle + libs natives + RECORD_AUDIO)
- **Non validé** : STT sur le micro réel de la tablette (nécessite le robot)
- Note : la branche `chatbot-cybel-projet-2026` du collègue (TTS) était déjà
  entièrement fusionnée dans main — rien à récupérer ; le vrai manque était le
  STT + le NLU embarqué, désormais comblé
- Doc : [docs/VOICE_CHATBOT.md](docs/VOICE_CHATBOT.md)

## [0.3.5] — 2026-07-15

### Auto-réparation Termux offline (incident tablette)

- **Incident** : bootstrap Termux réextrait sans le paquet `python` → backend
  kiosque mort au démarrage (notification « bash not found », puis
  `ModuleNotFoundError: uvicorn`) ; pas d'internet sur le réseau du robot pour
  réinstaller. Diagnostic et réparation via ADB/USB.
- **Bundle offline vendoré** : `scripts/termux/offline_bootstrap/` (.deb Termux
  aarch64 : python 3.14.6, python-pip + 8 dépendances ; wheels PyPI purs
  Python : uvicorn 0.51.0, starlette 1.3.1, websockets 16.1 ; `SHA256SUMS`
  vérifiées contre les dépôts d'origine)
- **`install_offline_bootstrap.sh`** (nouveau) : réparation idempotente sans
  réseau — intégrité du bundle, `dpkg -i` si python absent,
  `pip install --no-index` pour les modules
- **Préflight** dans `ensure_cybel_backend.sh` / `ensure_cybel_backend_test.sh` :
  teste `import uvicorn, starlette, websockets` à chaque lancement et déclenche
  la réparation automatiquement
- **Migration starlette ≥ 1.x** : `cybel_lite.py` passe de
  `@app.on_event("startup")` (API supprimée) au paramètre `lifespan` ;
  `requirements-lite.txt` aligné sur les versions du bundle
- **Validé sur le châssis réel** : suppression volontaire de `starlette` →
  relance kiosque → réparation auto en ~10 s → backend healthy (8000 + 8001)
- Doc : [docs/TERMUX_DEPLOY.md §6.1](docs/TERMUX_DEPLOY.md) et
  [scripts/termux/offline_bootstrap/README.md](scripts/termux/offline_bootstrap/README.md)

## [0.3.4] — 2026-07-14

### Reconnaissance faciale — scaffolding (branche `feature/face-presence`, phase 2)

- **App Android `CybelFaceBridge`** (nouvelle, `android/CybelFaceBridge/`) : headless
  (aucune Activity/icône), Camera2 sans preview → `android.media.FaceDetector` →
  embedding TensorFlow Lite → `POST /api/visitors/identify` (vecteur uniquement,
  jamais d'image envoyée)
- **Backend** : `sdk/visitor_utils.py` (cosine similarity, sans pydantic),
  `backend/routers/visitors.py` + `services/visitor_service.py`
  (`identify`/`enroll`/liste/suppression), persistance `data/visitors.json`
  (`sdk/persistence.py`)
- **Backend embarqué** : routes miroir dans `scripts/termux/cybel_lite.py` +
  diffusion WebSocket `{type: "visitor"}`
- **Kiosque** : accueil personnalisé (« Bonjour M./Mme X ») dans
  `frontend-kiosk`, se greffant sur le déclencheur de présence Phase 1
- **Config** : `face_recognition_threshold` (défaut 0.82, réglable via
  `PUT /api/kiosk/config` sans rebuild APK) ; correctif cohérence
  `backend/routers/kiosk.py` vs `cybel_lite.py` (clés `presence_*`/
  `face_recognition_*` manquantes côté PC)
- **Enrôlement** : `scripts/termux/enroll_visitor.sh`, déclenché par le
  personnel uniquement (jamais de capture automatique d'un visiteur non
  consentant)
- **Tests** : `test_visitor_utils.py`, `test_visitors_router.py` (+ extension
  `test_persistence.py`, `test_kiosk_config.py`) — matching backend vérifié
  par tests unitaires et par un test manuel HTTP réel
- **Non validé initialement** : pipeline caméra/détection/embedding sur
  tablette physique (pas d'accès terrain depuis l'environnement de dev) —
  aucun modèle `.tflite` n'est fourni (provenance de licence/dataset des
  modèles publics souvent floue)

### Validation terrain caméra/détection (même jour, châssis CIOT réel)

Tablette branchée en USB/ADB, cinq bugs réels trouvés et corrigés (invisibles
sans le matériel) : sélection caméra (une seule caméra `BACK`, pas `FRONT`),
plage FPS codée en dur incompatible, crash TensorFlow Lite 2.14.0
(`UnsatisfiedLinkError: strtod_l`, symbole API26+ absent sur Android
7.1/API25 → passage à TFLite 2.9.0), crash non rattrapé (`Throwable` vs
`Exception`), boucle `CAMERA_IN_USE` (fuite de callbacks de réouverture).
**Caméra, conversion NV21→RGB565 et détection de visage confirmées
fonctionnelles** (confiance ~0.51, visiteur à 2-3 m). Identification réelle
toujours non testée (nécessite un vrai modèle `.tflite`). Détail :
[docs/FACE_PRESENCE.md](docs/FACE_PRESENCE.md) et
[android/CybelFaceBridge/README.md](android/CybelFaceBridge/README.md).

## [0.3.3] — 2026-06-27

### POI laboV2 — alignement Deployment Tool

- **Élagage POI obsolètes** : `LG-10`, `LG-09`, `GAMME-CONTROLE-QUALITE` (liste noire `OBSOLETE_POI_NAMES`)
- **Point de charge** : `POINT-RECHARGE` synchronisé depuis ROS mais exclu visite et kiosque (`is_charge_poi_name`, `kiosk_visible: false`)
- **Sync stricte** : seuls les marqueurs Deployment Tool remplacent `points.json` ; destinations kiosque limitées aux arrêts `lab_tour.json`
- **Visite guidée** : `filter_tour_by_poi()` au démarrage — ignore POI absents, obsolètes ou charge
- **Parcours** : 10 arrêts laboV2 (retrait LG-10, GAMME-CONTROLE-QUALITE)
- **Actions accueil** : noms POI laboV2 (`PORTE-LABO`, `POSTE-REMPLISSAGE-BOUCHONNAGE`)
- Doc : [docs/labo/POI_LABOV2.md](docs/labo/POI_LABOV2.md)
- Tests : `test_poi_charge.py`, `test_lab_tour_filter.py` (+28 tests POI/tour)

### Détection de présence (branche `feature/face-presence`)

- Écoute ROS `/detected_people_array` → WebSocket kiosque
- Réveil veille + TTS accueil (`presence_*` dans `kiosk_config.json`)
- Doc : [FACE_PRESENCE.md](docs/FACE_PRESENCE.md)

## [0.3.2] — 2026-06-25

### Sync POI automatique + élagage carte

- **Sync au démarrage kiosque** : `GET /api/reception/destinations` lit ROS avant d'afficher la grille
- **Sync au démarrage visite** : `POST /api/tour/start` synchronise les POI avant les prérequis navigation
- **Élagage POI fantômes** : `merge_point_dicts` / `merge_robot_points` remplacent le cache (suppression des POI absents de la carte ROS courante)
- **Tablette** : `sync_poi_from_ros_map()` dans `cybel_lite.py`
- **Backend PC** : `backend/services/poi_bootstrap.py` → `ensure_poi_synced_from_robot()`
- **Carte laboV2** : parcours 12 arrêts documenté
- Doc : [SENTRYMOVE_POI_SYNC.md](docs/SENTRYMOVE_POI_SYNC.md), [GUIDE_CONTROLEUR_POI.md](docs/labo/GUIDE_CONTROLEUR_POI.md)

## [0.3.1] — 2026-06-24

### Démarrage automatique tablette

- **CybelVisitorKiosk v1.3** : lance `ensure_cybel_backend.sh` via Termux RUN_COMMAND (repli `su`) à l'ouverture
- Écran « Démarrage du service d'accueil… » pendant l'attente health check
- `start_cybel.sh` idempotent si backend déjà actif
- `setup_termux_kiosk.sh` : `allow-external-apps` + hook Termux:Boot
- **cybel_lite** : routes kiosque v0.3 (`/api/kiosk/config`, destinations, go, robot/speech status)

## [0.3.0] — 2026-06-24

### Kiosque visiteur — refonte accueil tablette

- Nouveau design clair professionnel (lisibilité tablette, touch targets 56px+)
- Écran **veille** avec timeout configurable (`standby_timeout_seconds`)
- Barre d'état : batterie, réseau, état robot, horloge, FR/EN
- **Destinations populaires** sur l'accueil (config `featured_destinations`)
- **Recherche** de destination en temps réel
- Bouton **Assistance** (scénario `inform_waiting` + TTS)
- Écrans déplacement et arrivée avec animations CSS
- Configuration branding : `data/kiosk_config.json` + `GET /api/kiosk/config`
- Logo SVG par défaut : `frontend-kiosk/public/logo.svg`
- Documentation : `UI_AUDIT.md`, `FEATURES_STATUS.md`, `MIGRATION_PLAN.md`

### Navigation / robustesse (session précédente)

- Repli coordonnées si POI ROS indisponible
- Messages d'erreur HTTP explicites (mode manuel, E-Stop, localisation)
- Patrouille : 400 pour prérequis, 409 seulement si déjà en cours
- ADB : `SPEECH_ADB_SERIAL` vide = USB uniquement (plus de timeout Wi-Fi)

## [0.2.0] — Phases 4–6

- Kiosque destinations, knowledge, patrouille, diagnostics, TTS prioritaire
