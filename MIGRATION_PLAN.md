# Plan de migration — Parité WelcomePatrol

## Vision

Reconstruire l'expérience visiteur WelcomePatrol dans CYBEL avec une stack web moderne (FastAPI + SPA légère), sans dépendance au cloud constructeur.

## Stack actuelle (réelle)

| Couche | Technologie | Note |
|--------|-------------|------|
| Kiosque visiteur | TypeScript + Vite (vanilla) | Pas React — bundle léger WebView |
| Opérateur | TypeScript + Vite (vanilla) | Cohérence avec kiosque |
| API | FastAPI | |
| Robot | ROSBridge + SDK Python | |

> Migration React (.jsx) possible en phase ultérieure si besoin de composants partagés avec un autre front. Pour l'instant, vanilla TS minimise la taille du bundle tablette.

## Phases

### Phase A — Accueil tablette ✅

- [x] Refonte kiosque v0.3
- [x] Démarrage auto backend à l'ouverture de CYBEL Accueil (v1.3)
- [x] Routes kiosque dans cybel_lite (validation tablette)

### Phase B — Guidage enrichi ✅ (v0.4)

- [x] WebSocket télémétrie sur kiosque (batterie, parole, nav)
- [x] Écran arrivée avec TTS synchronisé affiché
- [x] Scénarios réception exposés au kiosque (accueil, salle, attente)
- [x] Édition logo / messages via page Paramètres opérateur

### Phase C — Parité avancée 🔜

- [ ] Mode annuaire / knowledge intégré au kiosque
- [ ] Retour base visiteur (avec garde-fous)
- [ ] Patrouille déclenchable depuis kiosque (réservé staff ?)
- [ ] Animations Lottie ou canvas (carte mini)

### Phase D — Opérateur & terrain

- [ ] Aligner checklist `PARITY_CHECKLIST.md` item par item
- [ ] Tests E2E tablette WebView
- [ ] Validation terrain multi-arrêts

## Fichiers de configuration kiosque

```json
// data/kiosk_config.json
{
  "organization_name_fr": "...",
  "welcome_message_fr": "...",
  "logo_url": "/kiosk/logo.svg",
  "standby_timeout_seconds": 90,
  "featured_destinations": ["Accueil", "Salle A"]
}
```

Rebuild après modification :

```bash
cd frontend-kiosk && npm run build
```

## Critères de succès Phase A

- [x] Lisible à 2–3 m sur tablette 10"
- [x] Parcours visiteur sans formation technique
- [x] État robot visible en permanence (hors veille)
- [x] Aucune régression visite guidée / destinations
