# État des fonctionnalités — Parité WelcomePatrol

Légende : ✅ Fait · ⚠️ Partiel · ❌ Non fait · 🔜 Planifié

## Interface visiteur (kiosque tablette)

| Fonctionnalité | CYBEL | WP | Statut |
|----------------|-------|-----|--------|
| Écran d'accueil visiteur | `frontend-kiosk` v0.3 | `HomeFragment` | ✅ |
| Logo entreprise | `kiosk_config.json` + SVG | CMS | ✅ |
| Message de bienvenue | Config FR/EN | CMS | ✅ |
| Sélection destination | Grille tactile | POI / annuaire | ✅ |
| Recherche destination | Filtre client | Annuaire | ✅ |
| Destinations favorites | Chips accueil | Favoris CMS | ✅ |
| Écran veille | `standby` 90s | `StandByFragment` | ✅ |
| Écran déplacement | Animation + statut | `NaviLeadTheWayFragment` | ⚠️ |
| Écran arrivée | Confirmation | Détail guidage | ⚠️ |
| État robot (barre) | Pill statut | Diagnostic | ✅ |
| Batterie | Barre header | Télémétrie | ✅ |
| État réseau | Point connecté | Ping WS | ✅ |
| Synthèse vocale | `POST /api/reception/go` | Iflytek / TTS | ✅ |
| Scénarios prédéfinis | `inform_waiting` assistance | Actions multiples | ⚠️ |
| Visite guidée | `TourEngine` | GUIDED | ✅ |
| FR / EN | Bascule header | i18n | ✅ |
| Retour base | Opérateur uniquement | Auto batterie basse | ⚠️ |
| Assistance humaine | Bouton kiosque | Réception | ⚠️ |
| Animations | CSS pulse/bob | Riches | ⚠️ |
| Reconnaissance faciale | `CybelFaceBridge` + `/api/visitors/*` | `WelcomeManager` | ⚠️ (caméra/détection validées terrain ; identification avec vrai modèle restante) |
| Météo / vidéo | — | Fragments dédiés | ❌ |

## Backend / robot

| Fonctionnalité | Statut |
|----------------|--------|
| ROSBridge navigation | ✅ |
| MQTT télémétrie | ✅ |
| TTS ADB | ✅ |
| Patrouille | ⚠️ |
| Retour charge | ⚠️ |
| Multi-étages | ❌ |

## Opérateur (`frontend/`)

| Fonctionnalité | Statut |
|----------------|--------|
| Dashboard | ✅ |
| Carte SLAM | ✅ |
| Téléopération | ✅ |
| Diagnostics | ✅ |
| Patrouille UI | ✅ |

Dernière mise à jour : refonte kiosque juin 2026.
