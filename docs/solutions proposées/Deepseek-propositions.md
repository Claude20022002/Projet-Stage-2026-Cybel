# Diagnostic et résolution de l'écran blanc – CYBEL Kiosk (WebView Android 7.1)

## 1. Analyse structurée des hypothèses

| Hypothèse                                                | Probabilité | Justification                                                                                                                                                                            |
| -------------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **H1 – JavaScript incompatible (ES2020 / modules)**      | **Élevée**  | Le build legacy n'a probablement pas encore été déployé correctement sur la tablette, ou le plugin legacy produit un code que la WebView 7.1 (Chrome ~51) n'exécute pas silencieusement. |
| **H2 – Isolation réseau Termux ↔ WebView sur 127.0.0.1** | Faible      | Android 7.1 partage la loopback entre applications. Le serveur écoute sur `0.0.0.0:8000`, donc accessible via `127.0.0.1` depuis n’importe quelle app.                                   |
| **H3 – Blocage cleartext HTTP**                          | Très faible | API 25 autorise le trafic HTTP par défaut ; `usesCleartextTraffic="true"` déjà présent.                                                                                                  |
| **H4 – Assets non déployés / cache WebView**             | Moyenne     | Le `dist/` sur Termux peut encore être l’ancien (sans legacy). Le cache WebView peut masquer la nouvelle version.                                                                        |
| **H5 – SystemJS / polyfills insuffisants**               | Moyenne     | SystemJS peut échouer sur WebView 7.1 ; même avec polyfills, certaines API ES6+ peuvent manquer.                                                                                         |

Hypothèse principale : **H1 + H4** (le build legacy n’est pas effectif sur la tablette, et l’ancien JS reste chargé avec des erreurs silencieuses).

## 2. Plan de validation pas à pas (15 minutes max)

Exécute les étapes dans l’ordre. Chaque commande est prévue pour Termux (SSH) ou ADB Wi-Fi.

### Étape 1 – Vérifier le HTML servi par le backend

```bash
curl -s http://127.0.0.1:8000/kiosk/ | grep -E '<script'
Résultat attendu : on doit voir uniquement des <script src="..."> classiques (pas de type="module", pas de import), avec index-legacy-... et polyfills-legacy-....

❌ Si on voit <script type="module"> → le build legacy n’est pas déployé.

Étape 2 – Vérifier le contenu du fichier JS legacy
bash
curl -s http://127.0.0.1:8000/kiosk/assets/index-legacy-*.js | head -c 200
Résultat attendu : du JavaScript lisible, pas de ??, ?., ni import/export dans les premières lignes.

Étape 3 – Déployer une page test minimale (réseau + JS basique)
Crée ce fichier test.html sur le PC, puis copie-le dans le répertoire frontend-kiosk/dist/ que tu uploaderas ensuite, ou directement sur Termux à la main.

bash
# Sur Termux, après avoir copié test.html dans ~/cybel/frontend-kiosk/dist/
# (ou via deploy_termux.py, puis restart backend)
curl http://127.0.0.1:8000/kiosk/test.html
Le contenu de test.html :

html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Test Kiosk</title>
</head>
<body>
  <h1 id="status">Chargement...</h1>
  <script>
    // ES5 strict, aucun sucre moderne
    document.getElementById('status').textContent = 'JS OK - Reseau OK';
    console.log('Test JS executed');
  </script>
</body>
</html>
Interprétation :

Si la WebView affiche "JS OK - Reseau OK" : H1 est confirmée (le réseau fonctionne, le JS simple s'exécute, c’est le JS complexe de l’app qui bloque).

Si la page reste blanche ou affiche "Chargement..." sans JS : problème réseau (H2) ou blocage des scripts.

Si erreur de chargement (page introuvable) : le backend ne sert pas le fichier → H4.

Étape 4 – Capturer les logs WebView (console JavaScript)
Activer ADB Wi-Fi (depuis le PC, si possible) ou utiliser logcat directement sur Termux avec su.

bash
# Depuis le PC (si ADB connecté)
adb logcat -v time -s CybelKiosk:* chromium:* WebView:* | tee cybel_webview.log

# Depuis Termux (root requis)
su -c 'logcat -v time -s CybelKiosk:* chromium:* WebView:*' | tee cybel_webview.log
Lance l’application et observe les logs. Recherche :

CybelKiosk : URL chargée, message "onPageStarted", erreurs "onReceivedError"

chromium : erreurs de parsing JS (ex: "Uncaught SyntaxError: Unexpected token '?'")

WebView : chargement de ressources

Interprétation : une erreur Unexpected token '?' confirme H1.

Étape 5 – Vérifier l’URL réellement utilisée par l’application
Regarde dans logcat le tag CybelKiosk pour le message "Loading URL: ...". Vérifie que c’est bien http://127.0.0.1:8000/kiosk/ ou l’IP Wi-Fi.

bash
logcat -s CybelKiosk | grep "Loading URL"
Si c’est une adresse injoignable (ex. 10.42.0.155), l’app ne trouve pas le fichier cybel_kiosk_url.txt.

Étape 6 – Purger cache et données de l’application
bash
# Via ADB (ou su dans Termux)
adb shell pm clear com.cybel.visitorkiosk
Cela supprime le cache WebView et les fichiers internes, forçant une relecture du fichier URL.

Synthèse rapide
Si test.html s’affiche correctement : problème JS (H1/H5).

Si test.html ne s’affiche pas : problème réseau (H2) ou chargement de page.

Si le HTML servi contient type="module" : déploiement legacy manquant.

3. Solutions concrètes par cause
Cas A – Build legacy non déployé (H4)
Symptôme : curl montre type="module" ou les fichiers JS absents.
Action :

Sur le PC, dans frontend-kiosk/ :

bash
npm run build   # assure que vite.config.ts utilise @vitejs/plugin-legacy
Vérifier que dist/index.html ne contient plus type="module".

Déployer avec scripts/deploy_termux.py (qui copie dist/ dans ~/cybel/frontend-kiosk/dist/).

Redémarrer le backend : pkill -f cybel_lite.py && start_cybel.sh.

Cas B – JavaScript legacy toujours incompatible (H1/H5)
Même avec le plugin legacy, SystemJS peut ne pas fonctionner. Alternative :

Option 1 – Bundle ES5 simple sans SystemJS
Configurer Vite pour générer un seul fichier IIFE ciblant es2015 (ce qui donne ES5-like) sans modules. Exemple de config minimale :

ts
// vite.config.ts
export default defineConfig({
  build: {
    target: 'es2015',   // pas de modules natifs
    polyfillDynamicImport: false,
    cssTarget: 'chrome61',
    rollupOptions: {
      output: {
        format: 'iife',
        entryFileNames: 'assets/app.js',
      }
    }
  }
})
Le HTML doit charger ce script avec une simple balise <script src="..."></script>, pas de SystemJS.

Tester avec la page test.html d’abord, puis avec le vrai kiosk.

Option 2 – Page de fallback complète
Si l’interface utilisateur est simple (gros boutons, FAQ), on peut la recoder en HTML/JS vanilla ultra compatible (ES5 + DOM APIs de base) sans outil de build. Cette version serait servie à côté de l’app legacy.

Cas C – Problème réseau (H2)
Si test.html ne charge pas en utilisant 127.0.0.1, mais charge en utilisant l’IP de l’interface eth0 (192.168.20.1) ou wlan0.

Action :

Forcer l’application à utiliser http://192.168.20.1:8000/kiosk/ comme fallback.

Vérifier que le backend écoute bien sur cette interface :

bash
netstat -tlnp | grep 8000   # doit afficher 0.0.0.0:8000
Si nécessaire, lancer le serveur explicitement sur 192.168.20.1.

Cas D – Cache WebView coriace
Après pm clear, si le problème persiste, ajouter des en-têtes HTTP anti-cache dans le backend (Starlette) :

python
from starlette.middleware.base import BaseHTTPMiddleware

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
Ou simplement forcer un paramètre ?v=... dans l’URL chargée par l’app.

4. Page de test minimale (test.html)
À placer dans frontend-kiosk/dist/test.html (ou directement sur Termux sous ~/cybel/frontend-kiosk/dist/).

html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>CYBEL Kiosk Test</title>
  <style>
    body { font-family: sans-serif; margin: 20px; background: white; }
    .ok { color: green; } .err { color: red; }
  </style>
</head>
<body>
  <h1>Test de connectivité WebView</h1>
  <p id="network">Vérification réseau...</p>
  <p id="js">Vérification JavaScript...</p>
  <script>
    (function() {
      document.getElementById('network').innerHTML = '<span class="ok">✔ Réseau OK (HTML chargé)</span>';

      try {
        // Test ES5 simple
        var test = [1, 2, 3].map(function(x) { return x * 2; });
        if (test[1] === 4) {
          document.getElementById('js').innerHTML = '<span class="ok">✔ JavaScript ES5 exécuté</span>';
          console.log('CYBEL_TEST: JS OK');
        }
      } catch(e) {
        document.getElementById('js').innerHTML = '<span class="err">✖ Erreur JS: ' + e.message + '</span>';
      }
    })();
  </script>
</body>
</html>
Utilisation : après déploiement, charger http://<IP>:8000/kiosk/test.html dans l’application. Le résultat montre immédiatement si le réseau et le JS de base fonctionnent.

5. Checklist de redéploiement complet
Après tout correctif, suivre cet ordre strict :

Build frontend (PC)

bash
cd frontend-kiosk
npm run build
ls dist/index.html   # doit exister
grep 'script src' dist/index.html   # pas de type="module"
Copier le dist/ sur Termux

bash
python scripts/deploy_termux.py   # assure de copier tout dist/
# ou manuellement :
scp -P 8022 -r frontend-kiosk/dist u0_a92@<IP>:/data/data/com.termux/files/home/cybel/frontend-kiosk/dist
Vérifier les fichiers sur Termux

bash
ssh -p 8022 u0_a92@<IP> 'ls -l ~/cybel/frontend-kiosk/dist/assets/index-legacy-*.js'
Redémarrer le backend

bash
ssh -p 8022 u0_a92@<IP> 'pkill -f cybel_lite.py; sleep 1; cd ~/cybel && bash start_cybel.sh'
Vérifier le endpoint santé

bash
curl http://<IP>:8000/api/health
Vérifier le service kiosk

bash
curl -s http://<IP>:8000/kiosk/ | head -20
curl -s http://<IP>:8000/kiosk/test.html
Mettre à jour le fichier URL (si nécessaire)

bash
ssh -p 8022 u0_a92@<IP> 'cat /sdcard/Download/cybel_kiosk_url.txt'
Il doit contenir http://<IP_locale>:8000/kiosk/ (ex. http://172.16.0.130:8000/kiosk/). Sinon, relancer start_cybel.sh ou écrire manuellement.

Réinstaller l’APK (si des modifications du code Android ont été faites)

bash
python scripts/install_kiosk_apk.py
Purger les données de l’application

bash
adb shell pm clear com.cybel.visitorkiosk
Lancer l’application et observer logcat (cf. étape 4)

6. Signaux d’échec dans logcat et interprétation
Active la surveillance avec :

bash
logcat -v time -s CybelKiosk:* chromium:* WebView:* AndroidRuntime:*
Log	Signification
CybelKiosk: Loading URL: http://...	L’app charge l’URL, vérifie qu’elle est correcte.
chromium: Uncaught SyntaxError: Unexpected token '?'	JS moderne (nullish coalescing) non supporté, H1.
chromium: Uncaught TypeError: System.import is not a function	SystemJS non chargé ou échoué, H5.
CybelKiosk: onReceivedError: ... ERR_ADDRESS_UNREACHABLE	L’URL n’est pas accessible depuis la WebView, H2.
CybelKiosk: onPageStarted: about:blank puis aucun autre chargement	L’application n’a pas réussi à déterminer l’URL, fichier txt manquant.
WebView: ... block ...	Ressource bloquée (CORS ou cleartext), rare.
Si aucun log n’apparaît, vérifie que WebChromeClient.onConsoleMessage est bien implémenté dans le nouvel APK (sinon les erreurs JS ne remontent pas dans logcat). Dans ce cas, utilise la télécommande Chrome (chrome://inspect) si un debug USB est possible, mais limité avec Android 7.1 et WebView.

7. Commandes de diagnostic supplémentaires (avant de conclure)
Si le plan ci-dessus ne suffit pas, exécute ces trois commandes et transmets les sorties :

État du service backend et versions fichiers

bash
ssh -p 8022 u0_a92@<IP> 'cd ~/cybel/frontend-kiosk/dist && md5sum index.html && cat index.html'
Test réseau depuis le contexte de l’application (via su)

bash
ssh -p 8022 u0_a92@<IP> 'su -c "curl -I http://127.0.0.1:8000/kiosk/test.html 2>&1"'
Cela permettra de voir si un shell root peut atteindre le serveur (même namespace réseau que les apps ? Oui).

Capture précise des logs au lancement de l’app

bash
ssh -p 8022 u0_a92@<IP> 'su -c "logcat -c; logcat -v time -s CybelKiosk:* chromium:* WebView:*" > /sdcard/logcat_cybel.txt'
Récupère le fichier via adb pull ou scp après quelques secondes d’exécution de l’app.

Conclusion
Le problème d’écran blanc est presque certainement dû à un mélange de :

Build legacy non effectif sur la tablette (le dist/ contient encore des modules),

Incompatibilité du JavaScript moderne avec WebView 7.1.

Le plan ci-dessus vous permettra de confirmer en moins de 15 minutes et d’y remédier avec des solutions progressives, tout en respectant les contraintes du terrain.
```
