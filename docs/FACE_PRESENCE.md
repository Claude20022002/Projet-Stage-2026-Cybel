# Reconnaissance faciale et détection de présence

> **Branche :** `feature/face-presence`  
> **Référence backlog :** CYB-073 · APK constructeur : `WelcomeManager.onFindFace`

---

## Objectif

1. **Phase 1 — Présence** (en cours) : détecter qu'un visiteur s'approche du robot et réveiller le kiosque (veille → accueil + TTS).
2. **Phase 2 — Reconnaissance faciale** (à venir) : identifier un visiteur enregistré et personnaliser l'accueil.

---

## Phase 1 — Détection de présence (implémentée)

### Source

Topic ROS **`/detected_people_array`** (caméra du châssis robot), déjà exploité sur le dashboard opérateur.

### Chaîne

```
/detected_people_array  →  cybel_lite (_people_listener_loop)
       →  WebSocket /ws/telemetry  { type: "people", people: [...] }
       →  frontend-kiosk (handlePresenceWelcome)
```

### Comportement kiosque

| Condition | Action |
|-----------|--------|
| Visiteur à ≤ `presence_max_distance_m` (défaut 3 m) | Sortie veille → écran accueil |
| `presence_speak_welcome: true` | TTS message de bienvenue (`welcome_message_fr/en`) |
| Cooldown `presence_cooldown_seconds` (défaut 90 s) | Évite les annonces en boucle |

### Configuration (`data/kiosk_config.json`)

```json
{
  "presence_welcome_enabled": true,
  "presence_max_distance_m": 3.0,
  "presence_cooldown_seconds": 90,
  "presence_speak_welcome": true,
  "face_recognition_enabled": false
}
```

### API

| Endpoint | Description |
|----------|-------------|
| `GET /api/robot/people` | Liste courante des personnes détectées |
| WebSocket `type: "people"` | Flux temps réel (~1,5 s) |

### Vérification terrain

```powershell
adb forward tcp:18001 tcp:8001
curl http://127.0.0.1:18001/api/robot/people
```

Placez-vous devant le robot : le tableau `people` doit contenir au moins une entrée avec `distance` faible.

---

## Phase 2 — Reconnaissance faciale (planifiée)

### Contraintes

- WebView Android 7.1 : pas de ML dans le JS du kiosque.
- L'APK constructeur utilise **Iflytek local** (`WelcomeManager.onFindFace`) — non exposé via ROS.

### Approche retenue

| Composant | Rôle |
|-----------|------|
| App Android **`CybelFaceBridge`** (à créer) | Capture caméra tablette, détection/identification locale |
| `data/visitors.json` | Annuaire visiteurs (nom, embedding ou référence photo) |
| `POST /api/visitors/identify` | Reçoit le résultat du bridge, renvoie `{ name, confidence }` |
| Kiosque | « Bonjour M./Mme X » si `face_recognition_enabled` |

### Fichiers préparés

- `data/visitors.json` — annuaire vide (schéma v1)

### Jalons

| Jalon | Durée estimée |
|-------|----------------|
| Valider présence terrain (phase 1) | 1 j |
| Spike caméra tablette + détection visage | 2–3 j |
| Enregistrement visiteur test | 1 j |
| Intégration kiosque + TTS personnalisé | 2 j |

---

## Tests unitaires

```powershell
pytest tests/unit/test_people_utils.py -q
```

---

## Liens

- [PROMOTE_KIOSK_TEST.md](labo/PROMOTE_KIOSK_TEST.md) — app principale POI (branche précédente)
- [AUDIT_APK_CONSTRUCTEUR.md](cybel-conception/AUDIT_APK_CONSTRUCTEUR.md) — `onFindFace`
