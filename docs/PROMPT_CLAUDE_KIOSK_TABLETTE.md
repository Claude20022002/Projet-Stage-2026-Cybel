# Prompt ingénieur — Faire fonctionner l'application kiosque sur la tablette du robot CIOT TY1251D

> **Usage** : copier-coller le bloc « Prompt à envoyer à Claude » ci-dessous dans une nouvelle conversation Claude AI (ou adapter selon le contexte). Ce document sert de brief technique complet pour obtenir une aide ciblée sur le **dernier problème non résolu** du projet CYBEL.

---

## Prompt à envoyer à Claude

```
Tu es un expert senior en Android embarqué, WebView legacy, réseau Linux/Android,
et déploiement Python sur Termux. Tu m'aides en tant qu'ingénieur logiciel et
robotique chez le constructeur du robot — je connais le hardware et l'OS du robot,
mais je bloque sur un problème de déploiement terrain.

# Contexte produit

Nous développons **CYBEL**, une plateforme de commande pour le robot de réception
mobile **CIOT modèle TY1251D-03195**. Le robot a deux « cerveaux » réseau :

1. **Châssis** (Linux embarqué, ROS) — Wi-Fi `10.42.0.0/24`, IP `10.42.0.1`,
   rosbridge WebSocket `:9090`, SSID `TY1251D-03195`.
2. **Tête Android** (upper body, écran tactile 15.6") — **Android 7.1**, SoC
   **RK3399**, **2 Go RAM**, **16 Go stockage**. Interfaces réseau observées :
   - `wlan0` : `172.16.0.0/16` (DHCP, IP variable ex. `172.16.0.128` / `.130` / `.194`)
   - `eth0` : `192.168.20.1` (tête) ↔ `192.168.20.22` (châssis, lien interne)

Sur la tête Android tournent :
- **Termux** (SSH port 8022, utilisateur `u0_a92`) — pour héberger notre backend
- **CybelVisitorKiosk** (`com.cybel.visitorkiosk`) — app native Java, WebView
  plein écran qui charge l'interface visiteur web `/kiosk/`
- **CybelTTSBridge** — synthèse vocale via `am broadcast` local (root `su` dispo)

# Objectif non atteint (bloquant)

**Faire totalement fonctionner l'application « CYBEL Accueil » installée sur la
tablette** : l'écran tactile doit afficher l'interface visiteur (gros boutons,
FAQ, FR/EN) et déclencher actions robot + TTS.

**Symptôme actuel** : écran **blanc** dans l'app, même après plusieurs
redémarrages. Le backend semble pourtant vivant.

**Preuve que le backend répond** (depuis Termux sur la même tablette) :
```bash
curl http://127.0.0.1:8000/api/health
# → HTTP 200, JSON OK

curl http://127.0.0.1:8000/kiosk/
# → HTTP 200, HTML du kiosk

curl http://127.0.0.1:8000/kiosk/assets/index-legacy-OtdGukOW.js
# → HTTP 200 (après correctif legacy)
```

Donc : **le serveur tourne**, mais **la WebView de l'app n'affiche rien**.

# Architecture cible (validée en principe)

```
┌─────────────────────────────────────────────────────────────┐
│  TÊTE ANDROID (Android 7.1, RK3399, 2 Go RAM)               │
│                                                             │
│  CybelVisitorKiosk (WebView)                                │
│       │ charge http://<IP>:8000/kiosk/                      │
│       ▼                                                     │
│  Termux : cybel_lite.py (Starlette/uvicorn, 0.0.0.0:8000)   │
│       │ API REST + fichiers statiques frontend-kiosk/dist   │
│       │ TTS → am broadcast → CybelTTSBridge                 │
│       ▼ WebSocket rosbridge                                 │
│  eth0 → 192.168.20.22:9090 (châssis ROS)                    │
└─────────────────────────────────────────────────────────────┘
```

L'interface visiteur est une SPA TypeScript/Vite (`frontend-kiosk/`), buildée
en statique et servie sur `/kiosk/`. L'interface opérateur (dashboard) reste
sur PC ; seul le kiosque doit tourner sur la tablette.

# Ce qui fonctionne déjà (ne pas réinventer)

| Composant | Statut | Détail |
|-----------|--------|--------|
| Backend lite Termux | ✅ | `scripts/termux/cybel_lite.py` — Starlette, sans pydantic |
| Health check | ✅ | `GET /api/health` → 200 depuis Termux |
| Service `/kiosk/` | ✅ | Monte `frontend-kiosk/dist/` si présent |
| ROS depuis Termux | ✅ | `ROBOT_HOST=192.168.20.22` (pas `10.42.0.1`) |
| TTS local | ✅ | `SPEECH_LOCAL_BROADCAST=true` |
| Déploiement SSH | ✅ | `scripts/deploy_termux.py`, `termux_lite_deploy.py` |
| Installation APK | ✅ | `scripts/install_kiosk_apk.py` via SSH + `su pm install` |
| Build APK sans Gradle | ✅ | `android/CybelVisitorKiosk/build.sh` (aapt2, javac, d8) |

# Problèmes déjà résolus (historique — pour contexte)

## 1. Backend PC injoignable depuis la tablette
- **Symptôme** : `ERR_ADDRESS_UNREACHABLE` avec URL `http://10.42.0.155:8000/kiosk/`
- **Cause** : routage asymétrique — le châssis NAT le trafic PC→tête, pas tête→PC
- **Tests échoués** : `adb reverse` (adbd 7.1 ne supporte pas reverse), route
  manuelle `10.42.0.0/24 via 192.168.20.22` (ping TTL exceeded)
- **Solution retenue** : héberger le backend **sur Termux** (contournement)

## 2. FastAPI/pydantic impossible sur Termux
- **Symptôme** : `pip install pydantic` échoue, compilation Rust `pydantic-core`
- **Cause** : Python 3.13 Termux, pas de wheel `aarch64-linux-android`, disque ~90% plein
- **Solution** : backend **lite** Starlette + uvicorn + websockets uniquement

## 3. rosbridge via mauvaise IP
- **Symptôme** : robot déconnecté depuis Termux
- **Cause** : `10.42.0.1` non routé depuis Termux
- **Solution** : `ROBOT_HOST=192.168.20.22` dans `scripts/termux/cybel.env`

# Problème NON RÉSOLU — écran blanc (focus de ta réponse)

## Symptômes précis
- App « CYBEL Accueil » : **écran entièrement blanc**, pas de boutons, pas d'erreur visible
  (les correctifs récents pour afficher une page d'erreur ne sont peut-être pas encore
  déployés sur la tablette de test)
- `curl` depuis Termux vers `127.0.0.1:8000` : **OK**
- Plusieurs redémarrages app + backend : **inchangé**

## Hypothèses identifiées (par ordre de probabilité)

### H1 — Incompatibilité WebView Android 7.1 / JavaScript moderne
- WebView 7.1 ≈ Chrome 51–58
- L'ancien build Vite produisait :
  ```html
  <script type="module" src="/kiosk/assets/index-XXXX.js"></script>
  ```
  avec du JS contenant `??` (nullish coalescing, ES2020)
- **Conséquence** : le navigateur ignore silencieusement le script → page blanche
- **Correctif tenté** (dans le dépôt, déploiement à confirmer) :
  - `@vitejs/plugin-legacy` avec `targets: ["chrome >= 49", "android >= 7"]`
  - Build actuel produit :
    ```html
    <script src="/kiosk/assets/polyfills-legacy-CK_ldkzm.js"></script>
    <script data-src="/kiosk/assets/index-legacy-OtdGukOW.js">
      System.import(document.getElementById('vite-legacy-entry').getAttribute('data-src'))
    </script>
    ```
  - Dépend de **SystemJS** dans les polyfills — à valider sur WebView 7.1

### H2 — Isolation réseau Termux ↔ WebView sur 127.0.0.1
- Termux (UID propre) écoute sur `0.0.0.0:8000`
- `curl` depuis Termux vers `127.0.0.1:8000` réussit
- La WebView (UID `com.cybel.visitorkiosk`) pourrait **ne pas** atteindre le même
  `127.0.0.1:8000` (namespaces réseau Android / politique Termux)
- **Correctif tenté** :
  - `start_cybel.sh` écrit `/sdcard/Download/cybel_kiosk_url.txt` avec l'IP Wi-Fi
    (ex. `http://172.16.0.128:8000/kiosk/`)
  - `MainActivity.java` lit ce fichier + fallbacks (`127.0.0.1`, `192.168.20.1`)
- **Test partiel** : `kiosk_network_probe.py` — curl Termux OK sur IP LAN ;
  `su -c curl` échoue (curl absent en contexte système)

### H3 — Cleartext HTTP bloqué
- App charge `http://` (pas HTTPS)
- **Correctif tenté** : `android:usesCleartextTraffic="true"` dans le manifest
  (targetSdk 25 — normalement permis par défaut, ajouté par précaution)

### H4 — Assets non déployés / cache WebView
- Ancien `dist/` sans build legacy encore sur la tablette
- WebView cache une réponse vide ou une erreur

### H5 — System.import / polyfills legacy insuffisants
- Même avec plugin-legacy, `System.import()` peut échouer sur WebView très ancienne
- Pas encore de `logcat` WebView console capturé sur tablette

# État actuel du code (dépôt cybel/)

## Fichiers clés
```
android/CybelVisitorKiosk/
  src/.../MainActivity.java     # WebView, URL dynamique, WebChromeClient logs
  AndroidManifest.xml           # usesCleartextTraffic, INTERNET, READ_EXTERNAL_STORAGE
  out/CybelVisitorKiosk.apk     # APK reconstruit (à réinstaller)

frontend-kiosk/
  vite.config.ts                # @vitejs/plugin-legacy, target es2015
  dist/index.html               # scripts legacy (pas type="module")

scripts/termux/
  cybel_lite.py                 # Backend Starlette, mount /kiosk/
  start_cybel.sh                # Écrit cybel_kiosk_url.txt, lance backend
  cybel.env                     # ROBOT_HOST=192.168.20.22, SPEECH_LOCAL_BROADCAST=true

scripts/
  deploy_termux.py              # Upload archive + bootstrap + restart
  install_kiosk_apk.py          # Push APK + pm install via SSH
  kiosk_network_probe.py        # Diagnostic réseau Termux vs système
```

## MainActivity — logique URL actuelle
1. Lit `/sdcard/Download/cybel_kiosk_url.txt` (écrit par `start_cybel.sh`)
2. Fallbacks : `http://127.0.0.1:8000/kiosk/`, `http://192.168.20.1:8000/kiosk/`
3. Rotation toutes les 5 s en cas d'erreur main frame
4. `WebChromeClient.onConsoleMessage` → logcat tag `CybelKiosk`

## Contraintes que tu dois respecter
- **Pas de Gradle/Android Studio** sur le poste de dev — build APK via SDK CLI uniquement
- **2 Go RAM, disque limité** — pas de backend FastAPI complet sur Termux
- **Android 7.1** — pas de mise à jour OS possible sur le terrain
- **Root disponible** (`su`) pour install APK et TTS broadcast
- **SSH Termux** accessible depuis PC (`ssh -p 8022 u0_a92@172.16.0.XXX`)
- **Pas d'accès SSH châssis** (`10.42.0.1:22` verrouillé)
- L'app doit rester en **mode kiosque** (plein écran, pas de sortie facile)

# Ma démarche d'ingénieur (ce que j'ai fait, dans l'ordre)

1. **Reverse engineering réseau** (`ip addr`, `ip route`, ping, curl) — compris
   la topologie dual-stack et le NAT asymétrique châssis↔tête↔PC.

2. **Abandon du backend distant** — confirmé que la tête ne peut pas joindre le PC ;
   pivot vers Termux comme serveur local.

3. **Tentative backend complet** — échec pydantic-core ; pivot **backend lite**
   Starlette, validation health 200.

4. **Configuration ROS** — `192.168.20.22:9090` depuis Termux (pas `10.42.0.1`).

5. **APK WebView** — d'abord URL PC (échec), puis `127.0.0.1:8000` (écran blanc
   malgré curl OK).

6. **Diagnostic écran blanc** — identification build Vite `type="module"` +
   syntaxe ES2020 incompatible WebView 7.1.

7. **Correctif build legacy** — `@vitejs/plugin-legacy`, suppression Google Fonts
   (offline).

8. **Correctif réseau app** — `cybel_kiosk_url.txt` + fallbacks IP + cleartext +
   page d'erreur + logs console.

9. **Scripts déploiement** — `deploy_termux.py`, `install_kiosk_apk.py`,
   `kiosk_network_probe.py`.

10. **Blocage actuel** — correctifs dans le dépôt mais **pas encore validés sur
    tablette** (SSH parfois timeout, IP DHCP change). L'utilisateur rapporte
    toujours écran blanc avec health 200.

# Ce que j'attends de toi

1. **Diagnostic structuré** : parmi H1–H5 (et autres si tu en vois), comment
   confirmer ou infirmer chaque hypothèse avec des commandes **exécutables**
   depuis Termux, ADB, ou `logcat` — sans supposer un outil absent.

2. **Plan de validation pas à pas** ordonné (du plus rapide au plus invasif),
   pour qu'on sache en 15 minutes quelle est la vraie cause.

3. **Solutions concrètes** selon la cause :
   - Si JS/WebView : alternatives au plugin-legacy (IIFE pur, esbuild target
     chrome49, WebViewAssetLoader, page HTML statique minimale de test, etc.)
   - Si réseau Termux↔WebView : patterns connus (port forwarding Termux,
     `termux-chroot`, proxy local, binder, etc.)
   - Si autre : proposition adaptée aux contraintes ci-dessus

4. **Page de test minimale** : un `test.html` + JS ES5 à servir sur `/kiosk/test.html`
   pour isoler « réseau WebView » vs « JS incompatible » en une requête.

5. **Checklist de redéploiement** : ordre exact build → upload dist → restart
   backend → install APK → purge cache WebView → vérification.

6. **Signaux d'échec à surveiller** dans `logcat` (tags `CybelKiosk`, `chromium`,
   `WebView`) et interprétation.

Ne propose pas de solutions qui nécessitent :
- Mettre à jour Android au-delà de 7.1
- Installer Gradle/Android Studio sur le robot
- Accéder en SSH au châssis
- Héberger le backend sur le PC sans résoudre le routage asymétrique

Priorise les solutions **testables sur le terrain aujourd'hui** avec Termux +
SSH + root + ADB Wi-Fi.

Si une information te manque, liste les **3 commandes de diagnostic** les plus
informatives à lancer avant de conclure — je les exécuterai et te collerai la sortie.
```

---

## Notes pour l'utilisateur du dépôt

| Élément | Valeur typique |
|---------|----------------|
| SSH Termux | `ssh -p 8022 u0_a92@172.16.0.XXX` |
| Backend health | `http://127.0.0.1:8000/api/health` |
| Kiosk | `http://127.0.0.1:8000/kiosk/` |
| Fichier URL app | `/sdcard/Download/cybel_kiosk_url.txt` |
| Logs backend | `~/cybel-uvicorn.log` |
| Package app | `com.cybel.visitorkiosk` |

**Documents complémentaires dans le dépôt** :
- [VISITOR_KIOSK.md](VISITOR_KIOSK.md) — architecture kiosque + historique problèmes
- [TERMUX_DEPLOY.md](TERMUX_DEPLOY.md) — procédure déploiement + dépannage
- [ROBOT_CONNECTION.md](ROBOT_CONNECTION.md) — topologie réseau robot
- [TTS_BRIDGE.md](TTS_BRIDGE.md) — synthèse vocale Android

**Après la réponse de Claude** : mettre à jour `VISITOR_KIOSK.md` §6.5 avec la
cause confirmée et la solution validée.
