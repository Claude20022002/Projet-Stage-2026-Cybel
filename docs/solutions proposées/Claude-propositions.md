# CYBEL — Diagnostic écran blanc WebView Android 7.1

> **Contexte** : backend Termux répond (`curl 127.0.0.1:8000` → 200), mais l'app
> `CybelVisitorKiosk` (WebView Android 7.1, RK3399) affiche un écran entièrement
> blanc. Ce document structure le diagnostic, les plans de validation, et les
> solutions selon la cause confirmée.

---

## TL;DR

**H1 (JS incompatible) et H2 (réseau Termux ↔ WebView) sont les deux seuls
suspects sérieux.** H3 est déjà mitigé, H4/H5 sont des sous-cas de H1. La
démarche ci-dessous tranche en moins de 15 minutes.

---

## 1. Page de test minimale — déployer en premier

C'est le pivot de tout le diagnostic. Créer ce fichier sur Termux :

```bash
cat > ~/cybel/frontend-kiosk/dist/test.html << 'EOF'
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Test CYBEL</title></head>
<body style="background:#222;color:#0f0;font-family:monospace;padding:20px">
<h1 id="status">Chargement...</h1>
<p id="info"></p>
<script>
// ES5 pur, zéro syntaxe moderne
document.getElementById('status').textContent = 'JS OK - page chargee';
document.getElementById('info').textContent =
  'URL: ' + window.location.href + ' | UA: ' + navigator.userAgent;

// Test fetch (absent si WebView < Chrome 42)
if (typeof fetch === 'undefined') {
  document.getElementById('info').textContent += ' | fetch=ABSENT';
} else {
  fetch('/api/health')
    .then(function(r){ return r.json(); })
    .then(function(d){
      document.getElementById('status').textContent = 'JS OK + API OK';
      document.getElementById('info').textContent += ' | health=' + JSON.stringify(d);
    })
    .catch(function(e){
      document.getElementById('status').textContent = 'JS OK + API FAIL';
      document.getElementById('info').textContent += ' | err=' + e.toString();
    });
}
</script>
</body>
</html>
EOF
```

Vérifier que Starlette le sert :

```bash
curl -I http://127.0.0.1:8000/kiosk/test.html
```

Forcer l'app à charger cette page :

```bash
echo "http://127.0.0.1:8000/kiosk/test.html" > /sdcard/Download/cybel_kiosk_url.txt
am force-stop com.cybel.visitorkiosk
am start -n com.cybel.visitorkiosk/.MainActivity
```

---

## 2. Plan de validation — du plus rapide au plus invasif

### Étape A — Observer ce que l'app charge réellement (2 min)

```bash
# Depuis Termux, pendant que l'app démarre
tail -f ~/cybel-uvicorn.log | grep -E "(GET|POST|ERROR)"
```

| Log observé | Conclusion |
|---|---|
| `GET /kiosk/test.html 200` | App atteint le backend → **H2 infirmé**, problème JS |
| `GET /kiosk/ 200` + `GET /kiosk/assets/... 200` | Assets chargés → **H1** (JS planté) |
| Aucune requête | App ne contacte pas le backend → **H2 confirmé** |
| `GET /kiosk/ 200` mais zéro asset | **H4** (ancien dist sans build legacy) |

---

### Étape B — Logcat WebView (3 min)

Depuis ADB Wi-Fi si activé :

```bash
adb connect 172.16.0.XXX:5555
adb logcat -s CybelKiosk:V chromium:V WebView:V cr_LibLoader:V 2>/dev/null | head -100
```

Ou depuis Termux avec root :

```bash
su -c "logcat -s CybelKiosk:V chromium:V WebView:V -t 200" 2>/dev/null
```

**Signaux clés :**

```
# H1 — JS cassé
I/chromium: [INFO:CONSOLE] Uncaught SyntaxError: ...
I/chromium: [INFO:CONSOLE] Uncaught ReferenceError: System is not defined

# H2 — réseau bloqué
E/chromium: net::ERR_CONNECTION_REFUSED
E/chromium: net::ERR_CLEARTEXT_NOT_PERMITTED

# H4 — 404 assets
I/chromium: [INFO:CONSOLE] 404 Not Found /kiosk/assets/...

# Succès attendu
I/CybelKiosk: Loading URL: http://127.0.0.1:8000/kiosk/
I/CybelKiosk: Console: JS OK - page chargee
```

---

### Étape C — Tester la connectivité depuis le contexte système (5 min)

La WebView tourne sous un UID différent de Termux. Vérifier si le loopback est
accessible depuis le contexte root système :

```bash
# Ping loopback depuis root
su -c "ping -c 3 127.0.0.1"

# HTTP depuis contexte root (wget souvent dispo en AOSP)
su -c "wget -q -O - http://127.0.0.1:8000/api/health" 2>&1

# Si wget absent, netcat
su -c "echo -e 'GET /api/health HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n' | nc 127.0.0.1 8000"
```

Si ces commandes échouent alors que `curl` Termux réussit → **H2 confirmé**.

---

### Étape D — Version exacte de la WebView (2 min)

```bash
su -c "dumpsys package com.android.webview | grep versionName"
# ou
su -c "pm list packages -v | grep webview"
```

| Version Chrome/WebView | Support JS |
|---|---|
| < 55 | Pas d'`async/await`, pas de `??` (nullish coalescing) |
| 55–65 | `async/await` OK, pas de modules ES natifs |
| 66+ | `type="module"` supporté en WebView |

---

## 3. Solutions selon la cause confirmée

### Si H2 — Réseau Termux ↔ WebView

Utiliser l'IP LAN plutôt que le loopback dans `start_cybel.sh` :

```bash
IP=$(ip addr show wlan0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
echo "http://${IP}:8000/kiosk/" > /sdcard/Download/cybel_kiosk_url.txt
```

Vérifier aussi qu'il n'y a pas de **race condition** : l'app peut démarrer avant
que `start_cybel.sh` ait écrit le fichier. Ajouter un polling dans
`MainActivity.java` si le fichier est absent au boot.

---

### Si H1 — JS incompatible : 3 alternatives au plugin-legacy SystemJS

#### Option 1 — esbuild IIFE (plus simple, plus compatible) ✅ recommandée

```bash
npx esbuild src/main.ts \
  --bundle \
  --platform=browser \
  --target=chrome49 \
  --format=iife \
  --global-name=CybelKiosk \
  --outfile=dist/assets/bundle.js \
  --loader:.ts=ts
```

```html
<!-- dist/index.html -->
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CYBEL Accueil</title>
  <link rel="stylesheet" href="/kiosk/assets/bundle.css">
</head>
<body>
  <div id="root"></div>
  <script src="/kiosk/assets/bundle.js"></script>
</body>
</html>
```

Avantages : pas de SystemJS, un seul fichier, ciblage chrome49 explicite.

---

#### Option 2 — Vite legacy sans import dynamique (`vite.config.ts`)

```typescript
import legacy from '@vitejs/plugin-legacy'

export default defineConfig({
  plugins: [
    legacy({
      targets: ['chrome >= 49'],
      renderLegacyChunks: true,
      modernPolyfills: false,
      additionalLegacyPolyfills: ['regenerator-runtime/runtime'],
    })
  ],
  build: {
    target: 'es2015',
    rollupOptions: {
      output: {
        // Désactive le code splitting — évite les imports dynamiques
        manualChunks: undefined,
      }
    }
  }
})
```

---

#### Option 3 — Page kiosque statique ES5 (contournement complet du build)

Pour valider que le problème est dans le bundle React/TypeScript et non dans la
WebView elle-même :

```html
<!-- dist/kiosk-static.html -->
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CYBEL Accueil</title>
<style>
body { margin:0; background:#1a1a2e; color:#eee; font-family:Arial,sans-serif; }
.btn { display:block; width:80%; margin:20px auto; padding:30px;
       background:#0f3460; border:none; color:#e94560; font-size:24px;
       border-radius:8px; cursor:pointer; text-align:center; }
.btn:active { background:#e94560; color:#fff; }
#status { text-align:center; padding:10px; font-size:14px; color:#888; }
</style>
</head>
<body>
<div id="status">Connexion...</div>
<button class="btn" onclick="callAction('GREET_FR')">🇫🇷 Bonjour</button>
<button class="btn" onclick="callAction('GREET_EN')">🇬🇧 Hello</button>
<button class="btn" onclick="callAction('FAQ')">❓ FAQ</button>

<script>
var BASE = window.location.origin;

function callAction(action) {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', BASE + '/api/action', true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4) {
      document.getElementById('status').textContent =
        action + ' → ' + xhr.status + ' ' + xhr.responseText.substring(0, 60);
    }
  };
  xhr.send(JSON.stringify({action: action}));
}

// Health check au démarrage
var h = new XMLHttpRequest();
h.open('GET', BASE + '/api/health', true);
h.onreadystatechange = function() {
  if (h.readyState === 4) {
    document.getElementById('status').textContent =
      h.status === 200 ? 'Backend OK' : 'Backend FAIL ' + h.status;
  }
};
h.send();
</script>
</body>
</html>
```

Si cette page fonctionne et que `test.html` fonctionne → le problème est
confirmé dans le bundle JS/React, pas dans la WebView elle-même.

---

## 4. Checklist de redéploiement — ordre exact

```bash
# ── SUR PC DE DEV ──────────────────────────────────────────────────────────

# 1. Rebuild frontend avec correction JS
cd frontend-kiosk
npm run build
# Vérifier l'absence de type="module"
grep 'type="module"' dist/index.html   # doit être vide
ls dist/assets/                         # doit contenir polyfills-legacy-*.js

# 2. Copier les fichiers de diagnostic dans dist/
cp test.html dist/
cp kiosk-static.html dist/

# 3. Upload via script de déploiement
python scripts/deploy_termux.py   # ou termux_lite_deploy.py


# ── SUR TERMUX (via SSH) ───────────────────────────────────────────────────

# 4. Redémarrer le backend
pkill -f "uvicorn\|cybel_lite" 2>/dev/null
sleep 1
cd ~/cybel && bash scripts/termux/start_cybel.sh &
sleep 3

# 5. Valider que les fichiers sont servis
curl -s http://127.0.0.1:8000/kiosk/test.html | head -5
POLYFILL=$(ls ~/cybel/frontend-kiosk/dist/assets/ | grep polyfills | head -1)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/kiosk/assets/${POLYFILL}

# 6. Vérifier l'URL écrite pour l'app
cat /sdcard/Download/cybel_kiosk_url.txt


# ── SUR TABLETTE (ADB ou Termux root) ──────────────────────────────────────

# 7. Vider le cache WebView
su -c "rm -rf /data/data/com.cybel.visitorkiosk/cache/*"
su -c "rm -rf /data/data/com.cybel.visitorkiosk/app_webview/Cache/*"

# 8. Réinstaller l'APK si rebuild Java
# (depuis PC) python scripts/install_kiosk_apk.py

# 9. Lancer et observer
su -c "am force-stop com.cybel.visitorkiosk"
su -c "logcat -c"
su -c "am start -n com.cybel.visitorkiosk/.MainActivity"

# 10. Capturer les logs au démarrage
su -c "logcat -s CybelKiosk:V chromium:V WebView:V -t 300 -d"
```

---

## 5. Signaux logcat et interprétation

```
# ✅ Succès attendus
I/CybelKiosk: Loading URL: http://172.16.0.XXX:8000/kiosk/
I/CybelKiosk: Page loaded: http://...
I/CybelKiosk: Console: JS OK - page chargee

# ❌ H2 — réseau bloqué
E/CybelKiosk: onReceivedError: -6 (net::ERR_CONNECTION_REFUSED)
E/CybelKiosk: onReceivedError: -105 (net::ERR_NAME_NOT_RESOLVED)
E/chromium: ERR_CLEARTEXT_NOT_PERMITTED

# ❌ H1 — JS cassé / H5 — SystemJS manquant
I/chromium: [INFO:CONSOLE(1)] Uncaught ReferenceError: System is not defined
I/chromium: [INFO:CONSOLE] Uncaught SyntaxError: Unexpected token ?
I/chromium: [INFO:CONSOLE] Uncaught TypeError: Promise.allSettled is not a function

# ❌ H4 — assets manquants (ancien dist)
I/chromium: [INFO:CONSOLE] GET http://127.0.0.1:8000/kiosk/assets/xxx.js net::ERR_ABORTED 404

# ❌ APK non mis à jour (ancienne URL PC)
I/CybelKiosk: Loading URL: http://10.42.0.155:8000/kiosk/
```

---

## 6. Commandes de diagnostic prioritaires (si blocage persistant)

Lancer ces 3 commandes et coller la sortie pour affiner le diagnostic :

```bash
# CMD 1 — État réel de ce que charge l'app
tail -50 ~/cybel-uvicorn.log && cat /sdcard/Download/cybel_kiosk_url.txt

# CMD 2 — Logcat WebView au démarrage
su -c "am force-stop com.cybel.visitorkiosk && logcat -c && \
  am start -n com.cybel.visitorkiosk/.MainActivity"
sleep 8
su -c "logcat -s CybelKiosk:V chromium:V WebView:V -t 200 -d"

# CMD 3 — Version WebView + connectivité système
su -c "dumpsys package com.android.webview | grep versionName"
su -c "wget -q -O - http://127.0.0.1:8000/api/health 2>&1 || echo 'WGET_FAILED'"
```

---

## Résumé des hypothèses

| # | Hypothèse | Probabilité | Test clé | Solution |
|---|---|---|---|---|
| H1 | JS ES2020+ incompatible WebView 7.1 | ★★★★★ | logcat `SyntaxError` | esbuild IIFE chrome49 |
| H2 | Isolation réseau Termux ↔ WebView | ★★★☆☆ | wget root vers 127.0.0.1 | URL IP LAN wlan0 |
| H3 | Cleartext HTTP bloqué | ★☆☆☆☆ | déjà mitigé (targetSdk 25) | manifest OK |
| H4 | Ancien dist sans build legacy | ★★★☆☆ | logs 404 assets | redéployer dist/ |
| H5 | SystemJS introuvable dans polyfills | ★★★☆☆ | logcat `System is not defined` | option 1 esbuild |

---

*Document généré pour le projet CYBEL — à intégrer dans `VISITOR_KIOSK.md` §6.5
une fois la cause confirmée et la solution validée sur tablette.*
