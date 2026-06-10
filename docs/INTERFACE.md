# Documentation de l'interface opérateur CYBEL

Guide complet du fonctionnement de l'interface web CYBEL (v0.2.0) — plateforme de commande du robot de réception CIOT **TY1251D-03195**.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Démarrage et accès](#2-démarrage-et-accès)
3. [Architecture technique](#3-architecture-technique)
4. [Navigation dans l'application](#4-navigation-dans-lapplication)
5. [Page Contrôle (dashboard)](#5-page-contrôle-dashboard)
6. [Page Paramètres](#6-page-paramètres)
7. [Carte SLAM](#7-carte-slam)
8. [Accueil et synthèse vocale](#8-accueil-et-synthèse-vocale)
9. [Téléopération et sécurité](#9-téléopération-et-sécurité)
10. [API REST](#10-api-rest)
11. [WebSocket télémétrie](#11-websocket-télémétrie)
12. [Mode simulation vs robot réel](#12-mode-simulation-vs-robot-réel)
13. [Erreurs, limites connues](#13-erreurs-limites-connues)
14. [Annexes](#14-annexes)

---

## 1. Vue d'ensemble

L'interface CYBEL est une **application web opérateur** conçue pour piloter le robot sans passer par l'UI usine du constructeur (`:8082`). Elle permet :

- de **surveiller** l'état du robot en temps réel (batterie, localisation, navigation) ;
- de **visualiser** la carte SLAM, le LiDAR live et les visiteurs détectés ;
- de **naviguer** vers des points prédéfinis ;
- de **téléopérer** le robot en mode manuel ;
- d'exécuter des **actions d'accueil** prédéfinies (annonce + déplacement) ;
- de faire **parler le robot** (synthèse vocale TTS) ;
- de donner des **commandes vocales** à l'opérateur via le micro du navigateur.

### Principe de fonctionnement

```
┌─────────────────────────────────────────────────────────────┐
│  Navigateur (http://localhost:5173)                         │
│  ┌─────────────┐    REST (actions)    ┌──────────────────┐  │
│  │ Interface   │ ───────────────────► │ Backend FastAPI  │  │
│  │ opérateur   │                      │ :8000            │  │
│  │             │ ◄── WebSocket ────── │ /ws/telemetry    │  │
│  └─────────────┘    (état temps réel) └────────┬─────────┘  │
└──────────────────────────────────────────────────┼──────────┘
                                                   │
                                    ┌──────────────▼──────────────┐
                                    │ SDK (MockRobot / RealRobot) │
                                    └──────────────┬──────────────┘
                                                   │
                              ┌────────────────────┴────────────────────┐
                              │ Simulation locale  │  rosbridge :9090     │
                              │ (ROBOT_MOCK=true)  │  (robot physique)    │
                              └───────────────────────────────────────────┘
```

**Règle importante** : l'état du robot (position, capteurs, statut) transite **quasi exclusivement par WebSocket**. Les actions de l'opérateur (navigation, téléop, TTS, actions d'accueil) passent par **REST** et déclenchent des événements WebSocket en retour.

---

## 2. Démarrage et accès

### Lancer l'application en développement

```bash
# Terminal 1 — Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Ouvrir **http://localhost:5173** dans un navigateur moderne (Chrome ou Edge recommandé pour la commande vocale).

### Connexion au robot physique

1. Se connecter au WiFi du robot : `TY1251D-03195` (mot de passe : `123456789`)
2. Vérifier la connectivité : `ping 10.42.0.1`
3. Dans `backend/.env`, définir `ROBOT_MOCK=false`
4. Redémarrer le backend

### Proxy de développement

En mode dev, Vite redirige automatiquement :

| Chemin navigateur | Cible réelle |
|-------------------|--------------|
| `/api/*` | `http://127.0.0.1:8000/api/*` |
| `/ws/telemetry` | `ws://127.0.0.1:8000/ws/telemetry` |

---

## 3. Architecture technique

### Stack frontend

| Élément | Technologie |
|---------|-------------|
| Build | Vite 8 + TypeScript |
| UI | Vanilla TS (pas de React/Vue) |
| Rendu | Templates HTML en chaînes (`innerHTML`) |
| État | Store central `state.ts` + pub/sub |
| Icônes | SVG inline (`icons/index.ts`) |
| Styles | CSS custom properties (`style.css`) |

### Fichiers clés

| Fichier | Rôle |
|---------|------|
| `main.ts` | Point d'entrée → `initApp()` |
| `app.ts` | Orchestration : rendu, événements, boucle téléop |
| `state.ts` | État global + abonnements |
| `api.ts` | Client REST |
| `telemetry.ts` | WebSocket télémétrie |
| `voice.ts` | Web Speech API (micro opérateur) |
| `components/layout.ts` | Sidebar + structure |
| `components/statusBar.ts` | Barre de statut |
| `components/pointsList.ts` | Liste des points |
| `components/mapView.ts` | Carte canvas |
| `components/receptionPanel.ts` | Accueil + TTS |
| `components/controls.ts` | Téléop + journal |
| `pages/settings.ts` | Page paramètres |

### État global (`AppState`)

```typescript
{
  page: "dashboard" | "settings",
  status: RobotStatus | null,      // État robot
  pose: Pose | null,               // Position {x, y, theta}
  map: MapData | null,             // Carte SLAM
  lidar: LidarPoint[],             // Obstacles LiDAR live
  people: DetectedPerson[],        // Visiteurs détectés
  actions: ReceptionAction[],      // Actions d'accueil
  points: Point[],                 // Points de navigation
  selectedPoint: string | null,    // Point sélectionné
  settings: RobotSettings | null,
  events: string[],                // Journal (max 8 entrées)
  wsConnected: boolean,            // WebSocket actif
  voiceListening: boolean,         // Micro opérateur actif
  speech: SpeechStatus | null      // Synthèse vocale robot
}
```

Chaque modification d'état appelle `notify()` → tous les abonnés (`subscribe`) reçoivent `onStateChange()` qui met à jour les panneaux concernés.

---

## 4. Navigation dans l'application

### Sidebar (toujours visible)

| Bouton | Page | Description |
|--------|------|-------------|
| **Contrôle** | Dashboard | Vue principale opérateur |
| **Paramètres** | Settings | Configuration déplacement / connexion |

Le pied de sidebar affiche la version **v0.2**.

---

## 5. Page Contrôle (dashboard)

Layout en **quatre zones** :

```
┌──────────────────────────────────────────────────────────────────┐
│  BARRE DE STATUT (pleine largeur)                                │
├──────────────┬─────────────────────────────┬─────────────────────┤
│  POINTS      │                             │  TÉLÉOPÉRATION      │
│  (liste)     │         CARTE SLAM          │  D-pad + E-Stop     │
│              │         (canvas)            │  Journal événements │
│  ACCUEIL     │                             │                     │
│  (actions)   │                             │                     │
└──────────────┴─────────────────────────────┴─────────────────────┘
```

---

### 5.1 Barre de statut

Affiche l'état temps réel du robot. Mise à jour via WebSocket `status`, `speech` et compteur `people`.

#### Zone gauche

| Élément | Source | Description |
|---------|--------|-------------|
| Identifiant châssis | `status.chassis_id` | Ex. `TY1251D-03195` |
| Badge **Mode simulation** | `status.mock === true` | Visible uniquement en mock |
| Badge **Connecté / Déconnecté** | `wsConnected` | État du WebSocket télémétrie |

#### Zone centrale (métriques)

| Métrique | Champ | Valeurs typiques |
|----------|-------|------------------|
| **État** | `nav_status_label` | En initialisation, Prêt, En navigation, Arrivé, Erreur |
| **Mode** | `nav_mode_label` | Automatique, Manuel, Téléopération |
| **Localisation** | `localization_label (XX%)` | Faible / Moyenne / Bonne — code couleur vert/orange/rouge |
| **Destination** | `navigating_to` | Nom du point cible (si navigation active) |

#### Zone droite (badges)

| Badge | Condition | Signification |
|-------|-----------|---------------|
| Batterie `XX%` | Toujours | Vert >50 %, orange ≤50 %, rouge ≤20 % |
| **En charge** | `status.charger` | Robot sur la pile |
| **N visiteur(s)** | `people.length > 0` | Personnes détectées par caméra/LiDAR |
| **Parle** | `speech.speaking` | Robot en train d'annoncer (TTS) |
| **E-STOP ACTIF** | `status.soft_estop` | Arrêt d'urgence logiciel actif (clignotant) |

> **Note** : `hard_estop` (arrêt matériel) est reçu du robot mais **non affiché** dans l'interface actuelle.

---

### 5.2 Panneau Points (colonne gauche, haut)

Liste les **points de navigation** disponibles sur la carte du robot.

#### Interaction

| Action | Comportement |
|--------|--------------|
| Clic sur un point | Sélectionne le point (surlignage sur carte + liste) |
| **Aller vers {point}** | `POST /api/navigation/goto` — désactivé si aucun point sélectionné |
| **Annuler navigation** | `POST /api/navigation/cancel` (équivalent à un arrêt) |

#### Types de points et couleurs carte

| Type | Libellé affiché | Couleur carte |
|------|-----------------|---------------|
| `charging` | Pile | Vert `#22c55e` |
| `common` | Point | Bleu `#3b82f6` |
| `gate` | Porte | Orange `#f97316` |
| `access` | Accès | Violet `#a855f7` |
| `ride` | Ascenseur | Rose `#ec4899` |
| `wait` | Attente | Cyan `#06b6d4` |
| `label` | Étiquette | Jaune `#eab308` |
| `stop` | Stop | Jaune clair `#facc15` |

#### État vide

Si aucun point n'est chargé : message « Aucun point disponible ».

---

### 5.3 Panneau Accueil (colonne gauche, bas)

Regroupe les **actions d'accueil prédéfinies**, la **commande vocale opérateur** et le **test TTS**.

#### Bouton Vocal

| État | Apparence | Action |
|------|-----------|--------|
| Inactif | Bouton micro normal | Démarre l'écoute Web Speech API (`fr-FR`) |
| Actif | Bouton rouge clignotant | Arrête l'écoute |

Flux : micro navigateur → transcription → `POST /api/reception/voice` → exécution de l'action correspondante.

> Nécessite Chrome/Edge et l'autorisation microphone. Non supporté sur Firefox (pas de Web Speech API).

#### Actions prédéfinies (8)

Groupées en trois sections :

**Réception**

| ID | Bouton | Annonce TTS | Navigation |
|----|--------|-------------|------------|
| `welcome_guest` | Accueillir un visiteur | « Bienvenue ! Je suis votre robot d'accueil. Suivez-moi. » | → Accueil |
| `wait_mode` | Mode attente | « Je reste à votre disposition. » | → Attente |
| `guided_tour` | Visite guidée | « Bienvenue pour la visite guidée… » | Parcours GUIDED* |
| `inform_waiting` | Informer d'un délai | « Votre interlocuteur arrive… » | Aucune |

**Navigation**

| ID | Bouton | Annonce TTS | Navigation |
|----|--------|-------------|------------|
| `go_reception` | Aller à l'accueil | — | → Accueil |
| `go_meeting_room` | Conduire en salle | « Je vous accompagne en salle… » | → Salle A |

**Autres**

| ID | Bouton | Annonce TTS | Navigation |
|----|--------|-------------|------------|
| `return_charge` | Retour à la pile | — | → Pile |
| `stop_all` | Arrêter l'action | — | Stop robot |

\* La visite guidée enregistre un événement journal ; la synchronisation avec le module GUIDED cloud n'est pas encore implémentée.

#### Séquence d'exécution d'une action

```
Clic action
    │
    ├─► Si speech défini → POST /api/speech/say (TTS robot)
    │       └─► Événement WS speech (badge « Parle »)
    │
    ├─► Si target_point défini → POST /api/navigation/goto
    │       └─► Événements WS status/pose/event
    │
    └─► Retour REST { events: [...] } → journal interface
```

#### Synthèse vocale (test manuel)

| Élément | Description |
|---------|-------------|
| Textarea | Message à faire dire au robot (prérempli) |
| **Faire parler** | `POST /api/speech/say` — désactivé pendant une annonce en cours |
| **Stop parole** | `POST /api/speech/stop` |
| Statut | « Dernier : « … » · {méthode} » (ex. `mock`, `publish:/play_tts`) |

---

### 5.4 Panneau Téléopération (colonne droite)

#### Mode manuel

| Élément | Action |
|---------|--------|
| Toggle **Mode manuel** | `POST /api/robot/mode/manual` avec `{ enabled: true/false }` |

Le D-pad n'est actif que si `nav_mode === "manual"`. Sinon, il apparaît grisé (`controls-panel__dpad--disabled`).

En mode simulation, tenter de bouger sans mode manuel génère l'événement WS : « Activez le mode manuel pour piloter ».

#### D-pad directionnel

Maintenir un bouton envoie des commandes de vitesse toutes les **100 ms** :

| Direction | `linear_x` | `angular_z` |
|-----------|------------|-------------|
| ↑ Avancer | `0.2` | `0` |
| ↓ Reculer | `-0.2` | `0` |
| ← Gauche | `0` | `0.5` |
| → Droite | `0` | `-0.5` |

Relâcher le bouton envoie `move(0, 0)` et arrête la boucle.

> **Limitation** : le bouton central (carré « stop ») du D-pad a `data-move="stop"` mais ne déclenche aucune commande au maintien. Utiliser le bouton **Arrêt** en dessous.

#### Boutons de sécurité

| Bouton | Endpoint | Effet |
|--------|----------|-------|
| **Arrêt** | `POST /api/robot/stop` | Arrêt immédiat, vitesse nulle |
| **E-STOP** | `POST /api/robot/emergency-stop` | Arrêt d'urgence logiciel |
| **Relâcher E-Stop** | `POST /api/robot/release-emergency-stop` | Visible uniquement si E-Stop actif |

#### Journal d'événements

- Affiche les **8 derniers événements** horodatés (`HH:MM:SS — message`)
- Alimenté par : WebSocket `event` et `speech`, retours API, erreurs locales
- Vide : « Aucun événement récent »

---

## 6. Page Paramètres

Accessible via la sidebar. Deux cartes de configuration.

### Carte Déplacement

| Champ | Options | Effet |
|-------|---------|-------|
| **Vitesse de navigation** | Lente (0.3 m/s), Moyenne (0.5 m/s), Rapide (0.8 m/s) | `speed_gear` |
| **Mode de déplacement** | Sécurité, Équilibre, Efficacité | `travel_mode` |
| **Contrôle directionnel** | Flèches / Joystick | `directional_mode` |

**Enregistrer** → `PUT /api/settings`

> **Limitation** : le choix « Joystick vs Flèches » est sauvegardé mais **non appliqué** dans l'UI — le D-pad reste toujours en mode flèches.

### Carte Connexion (lecture seule)

| Champ | Valeur |
|-------|--------|
| Hôte robot | `10.42.0.1` |
| Mode | Simulation ou Robot réel (selon backend) |
| Interface usine | Lien vers `http://10.42.0.1:8082` (nouvel onglet) |

> **Limitation** : l'enregistrement des paramètres envoie `mock_mode: true` et `robot_host: "10.42.0.1"` en dur. Le basculement simulation/réel se fait uniquement via `backend/.env` (`ROBOT_MOCK`).

---

## 7. Carte SLAM

Canvas HTML 2D **640 × 480 px**, redessiné à chaque changement de `pose`, `lidar`, `people`, `points` ou objectif.

### Couches de rendu (ordre d'empilement)

| Couche | Donnée | Rendu |
|--------|--------|-------|
| 1. Grille d'occupation | `map.data` | Cellules grises (libre) / bleu foncé (obstacle) |
| 2. Ligne objectif | `pose` → `status.current_goal` | Trait pointillé bleu |
| 3. LiDAR live | `lidar[]` | Points rouges semi-transparents |
| 4. Visiteurs | `people[]` | Cercles violets + distance en mètres |
| 5. Points navigation | `points[]` | Disques colorés par type + nom |
| 6. Robot | `pose` | Triangle bleu orienté selon `theta` |

### Légende (coin carte)

| Couleur | Signification |
|---------|---------------|
| Rouge | LiDAR live |
| Bleu foncé | Obstacle carte |
| Vert | Pile |
| Bleu | Point |
| Orange | Porte |
| Violet | Visiteur |

### En-tête carte

- Nom de la carte (`metadata.name`)
- Étage (`metadata.floor`)
- Surface (`metadata.area_sqm` m² si disponible)

### Fallback sans carte

Si `GET /api/map/current` échoue : grille quadrillée grise à la place de la carte d'occupation. Le robot et les points restent affichables.

### Interaction

La carte est **en lecture seule** — pas de clic pour naviguer ou sélectionner un point.

---

## 8. Accueil et synthèse vocale

### Deux systèmes vocaux distincts

| Système | Qui parle | Technologie | Usage |
|---------|-----------|-------------|-------|
| **Commande vocale** | L'opérateur → le robot agit | Web Speech API (navigateur) | Bouton « Vocal » |
| **Synthèse vocale (TTS)** | Le robot parle | ROS / HTTP Android | Actions d'accueil + textarea TTS |

### Commandes vocales reconnues

Correspondance par **sous-chaîne** insensible à la casse (phrase la plus longue prioritaire) :

| Mots-clés | Action déclenchée |
|-----------|-------------------|
| accueil, accueillir, visiteur, bienvenue | Accueillir un visiteur |
| va à l'accueil, aller accueil, accueil point | Aller à l'accueil |
| salle, salle a, réunion | Conduire en salle |
| attente, attendre | Mode attente |
| pile, charge, recharge | Retour à la pile |
| visite, visite guidée | Visite guidée |
| arrête, stop, arrêter | Arrêter l'action |

Phrase non reconnue → HTTP 400 → journal « Commande non reconnue ».

### Chaîne TTS robot (backend)

Ordre de tentative sur robot réel :

1. Topic/service ROS configuré (`SPEECH_TOPIC` / `SPEECH_SERVICE` dans `.env`)
2. Candidats ROS automatiques (`/play_tts`, `/tts`, `/yutong_assistance/tts`, etc.)
3. HTTP upper body Android (`172.16.0.88` — ports et chemins courants)

En simulation : délai simulé proportionnel à la longueur du texte (méthode `mock`).

---

## 9. Téléopération et sécurité

### Prérequis téléopération

1. Activer le **mode manuel** (toggle)
2. Vérifier que l'**E-Stop n'est pas actif**
3. Maintenir une direction sur le D-pad

### Vitesses téléop (constantes frontend)

```typescript
MOVE_SPEED = 0.2 m/s    // linéaire
ROTATE_SPEED = 0.5 rad/s  // rotation
```

Ces valeurs sont **indépendantes** du réglage « Vitesse de navigation » dans les paramètres (qui concerne la navigation autonome).

### Protocole robot (réel)

Les commandes REST `POST /api/robot/move` sont traduites en publication ROS :

```
Topic : /mobile_base/commands/velocity
Format : { linear: { x, y: 0, z: 0 }, angular: { x: 0, y: 0, z } }
```

### Contrôles clavier

**Aucun** — l'interface ne gère pas de raccourcis clavier. Téléopération souris/touch uniquement.

---

## 10. API REST

Base URL : `/api` (proxifié vers `:8000` en dev).

### Appelés au démarrage (`initApp`)

| Méthode | Endpoint | Réponse | Usage UI |
|---------|----------|---------|----------|
| GET | `/api/health` | `{ status, mock, robot_host, version }` | Message journal simulation/réel |
| GET | `/api/navigation/points` | `Point[]` | Liste points, sélection du 1er |
| GET | `/api/map/current` | `MapData` | Carte (erreur silencieuse si indisponible) |
| GET | `/api/settings` | `RobotSettings` | Page paramètres |
| GET | `/api/reception/actions` | `ReceptionAction[]` | Boutons accueil |

### Robot

| Méthode | Endpoint | Body | Description |
|---------|----------|------|-------------|
| GET | `/api/robot/status` | — | Statut (non utilisé par UI — remplacé par WS) |
| GET | `/api/robot/pose` | — | Pose (non utilisé par UI — remplacé par WS) |
| POST | `/api/robot/move` | `{ linear_x, angular_z }` | Commande vitesse |
| POST | `/api/robot/stop` | — | Arrêt |
| POST | `/api/robot/emergency-stop` | — | E-Stop |
| POST | `/api/robot/release-emergency-stop` | — | Relâcher E-Stop |
| POST | `/api/robot/mode/manual` | `{ enabled: bool }` | Mode manuel |

### Navigation

| Méthode | Endpoint | Body | Description |
|---------|----------|------|-------------|
| GET | `/api/navigation/points` | — | Liste des points |
| POST | `/api/navigation/goto` | `{ point_name: string }` | Naviguer vers un point |
| POST | `/api/navigation/cancel` | — | Annuler (stop) |

### Carte

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/map/current` | Carte SLAM complète |
| GET | `/api/map/metadata` | Métadonnées seules (non utilisé par UI) |

### Paramètres

| Méthode | Endpoint | Body | Description |
|---------|----------|------|-------------|
| GET | `/api/settings` | — | Lire paramètres |
| PUT | `/api/settings` | `RobotSettings` | Sauvegarder |

### Accueil

| Méthode | Endpoint | Body | Description |
|---------|----------|------|-------------|
| GET | `/api/reception/actions` | — | Catalogue actions |
| POST | `/api/reception/actions/{id}/execute` | — | Exécuter une action |
| POST | `/api/reception/voice` | `{ text: string }` | Commande vocale texte |

### Synthèse vocale

| Méthode | Endpoint | Body | Description |
|---------|----------|------|-------------|
| GET | `/api/speech/status` | — | Statut TTS (non utilisé par UI — remplacé par WS) |
| POST | `/api/speech/say` | `{ text, interrupt: true }` | Faire parler le robot |
| POST | `/api/speech/stop` | — | Interrompre la parole |

---

## 11. WebSocket télémétrie

**Endpoint** : `ws://{host}/ws/telemetry`

### Connexion

1. Le client ouvre le WebSocket
2. Le serveur envoie immédiatement un **snapshot** : `status`, `pose`, `map` (si disponible)
3. Ensuite : broadcast de tous les événements `on_telemetry` du robot

### Reconnexion

- Déconnexion → badge « Déconnecté », journal « Télémétrie déconnectée — reconnexion… »
- Nouvelle tentative automatique toutes les **2 secondes**

### Format des messages

```json
{ "type": "<event_type>", ...payload }
```

### Types d'événements

| type | Payload | Handler frontend | Effet UI |
|------|---------|------------------|----------|
| `status` | Objet `RobotStatus` complet | `setStatus()` | Barre statut, toggle manuel, E-Stop, destination |
| `pose` | `{ x, y, theta }` | `setPose()` | Triangle robot, ligne objectif |
| `map` | `MapData` | `setMap()` | Grille occupation |
| `points` | `{ points: Point[] }` | `setPoints()` | Liste points (robot réel, chargement markers) |
| `lidar` | `{ points: LidarPoint[] }` | `setLidar()` | Points rouges carte |
| `people` | `{ people: DetectedPerson[] }` | `setPeople()` | Visiteurs + badge compteur |
| `speech` | `{ text, status, method, speaking }` | `setSpeech()` | Badge « Parle », bouton TTS |
| `event` | `{ message: string }` | `pushEvent()` | Journal événements |

### Statuts `speech.status`

| status | Effet journal |
|--------|---------------|
| `speaking` | « Robot parle : « … » » |
| `done` | « Annonce terminée » |
| `stopped` / `cancelled` / `failed` | Pas d'entrée journal dédiée |

### Événements `event` typiques

| Contexte | Message exemple |
|----------|-----------------|
| Connexion | « Connecté au robot », « Robot inaccessible — vérifiez le WiFi » |
| Mode | « Mode manuel activé », « Mode automatique activé » |
| Navigation | « Navigation vers Accueil », « Arrivé à Accueil » |
| Sécurité | « Arrêt », « E-Stop activé », « E-Stop relâché » |
| Téléop mock | « Activez le mode manuel pour piloter » |

### Fréquences (indicatif)

| Source | Fréquence |
|--------|-----------|
| Mock — boucle simulation | ~2 Hz (status/pose), LiDAR ~1 Hz, visiteurs ~0.5 Hz |
| Réel — topics ROS | Pose ~10 Hz, status ~2 Hz, LiDAR ~5 Hz (throttle 200 ms), people ~2 Hz |

---

## 12. Mode simulation vs robot réel

Configuration : `ROBOT_MOCK=true/false` dans `backend/.env`.

| Aspect | Simulation (`mock`) | Robot réel |
|--------|---------------------|------------|
| Badge barre statut | **Mode simulation** | Absent |
| Message démarrage | « mode simulation actif » | « mode robot réel » |
| Points | 5 points fixes (Accueil, Salle A, Pile, Porte principale, Attente) | Points ROS dynamiques (`/marker_manager/get_markers_details`) |
| Carte | Carte générée 130 m² | Carte ROS occupancy grid |
| LiDAR | Points simulés autour du robot | `/scan_filter` réel |
| Visiteurs | 2 visiteurs simulés proches du robot | `/detected_people_array` réel |
| TTS | Délai simulé, méthode `mock` | ROS puis HTTP Android |
| Batterie | Décrémente lentement (~1 % / 5 s) | Valeur robot |
| Connexion robot | Toujours `connected: true` | Dépend du WiFi / rosbridge |
| Téléop sans mode manuel | Événement d'avertissement | Commandes publiées sur ROS |

### Points mock (simulation)

| Nom | Type | Position approximative |
|-----|------|------------------------|
| Accueil | common | (2.1, 1.0) |
| Salle A | common | (5.5, 3.2) |
| Pile | charging | (-3.0, 0.2) |
| Porte principale | gate | (0.5, -2.0) |
| Attente | wait | (1.8, 4.5) |

---

## 13. Erreurs, limites connues

### Messages d'erreur interface

| Situation | Comportement |
|-----------|--------------|
| Backend injoignable au démarrage | Journal : « Impossible de joindre le backend : … » |
| Carte indisponible | Journal + grille fallback |
| Actions non chargées | Journal : « Actions d'accueil non chargées » |
| WebSocket déconnecté | Badge « Déconnecté », reconnexion auto |
| Erreur API (nav, TTS, action) | Journal avec détail HTTP |
| Commande vocale non reconnue | HTTP 400 → journal |
| Micro non supporté / refusé | Journal dédié |
| TTS échoué (robot réel) | Journal via events d'action |
| Navigation sans point sélectionné | Bouton « Aller vers » désactivé |
| TTS en cours | Bouton « Faire parler » désactivé (« En cours… ») |
| Mode non manuel | D-pad grisé |

### Limitations actuelles

1. **Pas de raccourcis clavier** pour la téléopération
2. **Bouton stop central du D-pad** inactif au maintien
3. **Paramètre directional_mode** sauvegardé mais non appliqué à l'UI
4. **mock_mode** non modifiable depuis l'interface (uniquement `.env`)
5. **hard_estop** non affiché (seul `soft_estop` visible)
6. **Carte non interactive** (pas de navigation par clic)
7. **Visite guidée GUIDED** : événement journal seulement, pas de sync cloud
8. **Paramètres vitesse/travel_mode** : stockés côté backend mais pas encore transmis au robot ROS

---

## 14. Annexes

### Séquence de démarrage complète

```
1. Utilisateur ouvre http://localhost:5173
2. initApp() rend le dashboard
3. subscribe(onStateChange) + connectTelemetry()
4. REST séquentiel :
   health → points → map → settings → actions
5. Journal : « Backend connecté — mode simulation/réel »
6. Sélection auto du premier point
7. WS connect → snapshot status/pose/map
8. Boucle WS → mises à jour temps réel
```

### Schéma flux opérateur (navigation)

```
Sélectionner point dans la liste
        │
        ▼
Clic « Aller vers {point} »
        │
        ▼
POST /api/navigation/goto
        │
        ▼
Backend → service ROS /poi (réel) ou simulation (mock)
        │
        ▼
WS events : status.navigating_to, pose (mouvement), event « Navigation vers… »
        │
        ▼
Arrivée → event « Arrivé à {point} », nav_status_label « Arrivé »
```

### Variables d'environnement liées à l'interface

```env
# backend/.env
ROBOT_MOCK=true              # Simulation ou robot réel
ROBOT_HOST=10.42.0.1         # IP châssis
ROBOT_WS_PORT=9090           # rosbridge
SPEECH_TOPIC=                # Topic TTS ROS (optionnel)
SPEECH_SERVICE=              # Service TTS ROS (optionnel)
SPEECH_HTTP_HOST=172.16.0.88 # Upper body Android (fallback TTS)
```

### Scripts utiles (hors interface)

| Script | Usage |
|--------|-------|
| `scripts/speech_explore.py` | Découvrir le canal TTS ROS sur le robot |
| `scripts/http_speech_explore.py` | Découvrir le canal TTS HTTP Android |
| `scripts/ros_explore2.py` | Écouter les topics ROS en live |

---

_Documentation interface CYBEL v0.2.0 — mise à jour juin 2026_
