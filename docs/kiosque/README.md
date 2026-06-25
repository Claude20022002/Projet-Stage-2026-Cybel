# Kiosque visiteur — CYBEL

Documentation de l'**interface visiteur** : web kiosque, déploiement Termux, app Android, visite guidée, TTS.

Index : [docs/README.md](../README.md)

---

## Documents

| Document | Description |
|----------|-------------|
| [VISITOR_KIOSK.md](../VISITOR_KIOSK.md) | Architecture kiosque, parcours labo, app `CybelVisitorKiosk` |
| [TERMUX_DEPLOY.md](../TERMUX_DEPLOY.md) | Backend lite Starlette sur tablette Android |
| [TOUR_NAVIGATION.md](../TOUR_NAVIGATION.md) | Moteur visite, diagnostic « parle sans bouger » |
| [TTS_BRIDGE.md](../TTS_BRIDGE.md) | Pont synthèse vocale `CybelTTSBridge` |

---

## Stack kiosque (production `main`)

```
CybelVisitorKiosk (APK WebView)
        │
        ▼
Termux : cybel_lite.py :8000
        │
        ├── frontend-kiosk/dist  (/kiosk/)
        ├── data/lab_tour.json (8 arrêts, coords)
        └── rosbridge → 192.168.20.22:9090
```

---

## Variante expérimentale POI

Sur la branche `feature/hybrid-sentrymove-kiosk` :

- Second APK `CybelVisitorKioskTest` (port **8001**)
- Navigation par `target_point` / POI Sentrymove
- Voir [labo/KIOSK_AB_COMPARISON.md](../labo/KIOSK_AB_COMPARISON.md)

---

## Scripts

| Script | Rôle |
|--------|------|
| `scripts/deploy_termux.py` | Déploiement SSH/SFTP |
| `scripts/install_kiosk_apk.py` | Installation APK Accueil |
| `android/CybelVisitorKiosk/build.sh` | Build APK production |
