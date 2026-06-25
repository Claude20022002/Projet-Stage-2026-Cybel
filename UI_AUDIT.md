# Audit UI — Écran d'accueil tablette (CYBEL vs WelcomePatrol)

Date : juin 2026  
Périmètre : `frontend-kiosk/` (WebView tablette robot)

## Références WelcomePatrol

D'après `docs/cybel-conception/AUDIT_APK_CONSTRUCTEUR.md` :

| Écran WP | Rôle |
|----------|------|
| `HomeFragment` | Accueil CMS (logo, contenu, actions) |
| `StandByFragment` | Veille attract |
| `VisitorFragment` | Accueil visiteur + TTS |
| `AskWayFragment` / `CompanyListFragment` | Orientation, annuaire |
| `NaviLeadTheWayFragment` | Guidage actif |
| `NavGuideDetailFragment` | Détail parcours |

## État CYBEL avant refonte (v0.2)

| Élément | CYBEL | WelcomePatrol | Écart |
|---------|-------|---------------|-------|
| Thème visuel | Sombre, compact | Clair, CMS riche | Lisibilité distance |
| Logo entreprise | Texte « CYBEL » | Image CMS | Manquant |
| Message bienvenue | Sous-titre tour labo | Message accueil dédié | Générique |
| Barre d'état | Absente | Batterie, réseau, état | Manquant |
| Veille / attract | Absente | `StandByFragment` | Manquant |
| Destinations rapides | Non | Tuiles favorites | Manquant |
| Recherche destination | Non | Filtre annuaire | Manquant |
| Assistance | Non | Scénarios vocaux | Partiel backend |
| Écran déplacement | Texte statique | Animation guidage | Faible |
| Écran arrivée | Basique | Feedback riche | Faible |
| Horloge | Non | Souvent présente | Manquant |
| FR/EN | Oui | Oui | OK |
| Visite guidée | Oui | Oui (GUIDED) | OK |
| TTS accueil | Via API go | `RobotSpeechManager` | OK |

## Conception CYBEL v0.3 (implémentée)

### Principes UX

- **Lisibilité à distance** : typo Plus Jakarta Sans, titres ≥ 28px, boutons ≥ 56px
- **Thème clair professionnel** : fond `#eef2f8`, surfaces blanches, accent bleu CYBEL
- **Parcours visiteur en 5 écrans** : veille → accueil → destinations → déplacement → arrivée
- **Identité CYBEL** : logo SVG, config JSON locale (pas de dépendance cloud CMS)

### Architecture

```
frontend-kiosk/src/
  app.ts              # Orchestration, polling, veille
  api.ts              # REST kiosk + réception + robot
  components/statusBar.ts
  screens/home.ts     # Rendu écrans
  style.css           # Design system kiosque
data/kiosk_config.json
backend/routers/kiosk.py  → GET /api/kiosk/config
```

### Écrans

1. **Veille** (`standby`) — logo, organisation, « Touchez l'écran » (timeout configurable)
2. **Accueil** (`welcome`) — message, destinations populaires, 3 actions principales
3. **Destinations** — grille + recherche temps réel
4. **Déplacement** — animation robot, statut, progression visite
5. **Arrivée** — confirmation avec animation

### Barre d'état permanente

- Pill état robot (prêt / nav / parole / E-Stop / hors ligne)
- Indicateur réseau (rosbridge)
- Batterie % + charge
- Horloge
- Bascule FR/EN

## Reste à faire (parité WP)

| Fonctionnalité | Priorité | Notes |
|----------------|----------|-------|
| Reconnaissance faciale | Basse | `WelcomeManager.onFindFace` — hors scope web |
| Annuaire entreprises | Moyenne | Équivalent = destinations + knowledge |
| Météo / média | Basse | `WeatherFragment`, `VideoFragment` |
| Retour base visiteur | Basse | Action opérateur `return_charge` |
| WebSocket temps réel | Moyenne | Remplacer polling 5s |
| Upload logo via Paramètres | Moyenne | Actuellement `data/kiosk_config.json` |
