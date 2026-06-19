Le fait que curl réponde 200 depuis Termux mais que la WebView affiche un écran blanc nous indique qu'on est face à un problème de frontière : soit la WebView n'atteint pas Termux (couche réseau/OS), soit elle télécharge la page mais crash silencieusement au rendu (couche JS/moteur de rendu).

Voici un plan de bataille structuré pour identifier la cause et la pulvériser.

1. Diagnostic Structuré : Isoler la Cause
   Voici comment valider ou invalider tes hypothèses sans supposer l'existence d'outils magiques, en utilisant uniquement ADB/Termux.

Hypothèse Test depuis Termux / Shell Root Interprétation
H1 / H5 (JS/Polyfills) logcat -d | grep -iE 'chromium|CybelKiosk|WebConsole' Si tu vois Uncaught SyntaxError: Unexpected token ou System.import is not defined, le JS moderne ou le polyfill crashe.
H2 (Isolation Réseau) Servir une page statique pur HTML (voir section 3) Si la page HTML pure s'affiche mais pas l'app complète, le réseau 127.0.0.1 est hors de cause (H2 invalidée).
H3 (Cleartext HTTP) logcat -d | grep -i cleartext Si tu vois CLEARTEXT communication to 127.0.0.1 not permitted, H3 est validée. (Peu probable sur API 25, mais possible selon le constructeur).
H4 (Cache WebView) su -c pm clear com.cybel.visitorkiosk avant de lancer Si l'app marche après cette commande, le problème venait d'un cache empoisonné (H4 validée). 2. Plan de Validation Pas-à-pas (15 minutes)
Exécute ces étapes dans l'ordre pour discriminer le réseau du rendu.

Étape A : Le test de vérité réseau (5 min)

Connecte-toi en SSH sur Termux.

Crée la page de test minimale (voir code plus bas) dans le dossier servi par Starlette, disons frontend-kiosk/dist/test.html.

Force l'app à charger http://127.0.0.1:8000/kiosk/test.html (modifie ton fichier /sdcard/Download/cybel_kiosk_url.txt).

Lance l'app.

Résultat attendu : Si tu vois un écran vert avec "Réseau OK", le problème est 100% côté JS/Vite (H1/H5). Si l'écran reste blanc, le problème est réseau ou OS (H2/H3).

Étape B : Capture des logs de mort (5 min)
Si l'écran est blanc (que ce soit sur l'app complète ou le test), récupère les logs exacts :

Bash
su -c "logcat -c" # Nettoie les anciens logs

# LANCE L'APP SUR LA TABLETTE, ATTENDS 5 SECONDES

su -c "logcat -d | grep -iE 'chromium|WebView|CybelKiosk|net::'"
Étape C : Vérification du binding Termux (5 min)
Assure-toi que Starlette écoute bien en IPv4 universel et pas seulement en IPv6 loopback (un piège classique sur Termux) :

Bash
netstat -tlnp | grep 8000
Il faut que tu voies 0.0.0.0:8000. Si tu vois ::1:8000 ou 127.0.0.1:8000, modifie la commande de lancement uvicorn pour forcer --host 0.0.0.0.

3. Page de Test Minimale (test.html)
   Crée ce fichier exact pour tester. Il n'utilise aucune dépendance, aucun module, et du JS natif des années 2010.

HTML

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Test Kiosk</title>
    <style>
        body { background-color: #2e7d32; color: white; font-family: sans-serif; padding: 2rem; }
        #log { background: black; padding: 1rem; font-family: monospace; }
    </style>
</head>
<body>
    <h1>Réseau OK</h1>
    <p>Si tu vois cet écran, la WebView accède bien au backend Termux.</p>
    <div id="log">JS Execution: </div>
    <script>
        // Test ES5 pur
        try {
            var logDiv = document.getElementById('log');
            logDiv.innerHTML += "SUCCESS (ES5 fonctionne). ";
            
            // Test d'appel API
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/health', true);
            xhr.onload = function() {
                if (xhr.status === 200) {
                    logDiv.innerHTML += "API HEALTH: 200 OK.";
                } else {
                    logDiv.innerHTML += "API ERROR: " + xhr.status;
                }
            };
            xhr.send();
        } catch (e) {
            document.body.style.backgroundColor = "red";
            document.getElementById('log').innerHTML += "ERROR: " + e.message;
        }
    </script>
</body>
</html>
4. Solutions Concrètes selon la Cause
Si la cause est JS/Vite (H1/H5 - Très probable sur Rockchip RK3399 / Android 7.1)
Le System.import généré par @vitejs/plugin-legacy est parfois instable sur les vieux Chromium embarqués (Chrome 51).
Solution : Abandonner totalement la notion de "modules" au build.
Configure ton vite.config.ts pour qu'il compile tout dans un seul gros fichier en format IIFE ou UMD, sans code asynchrone pour le chargement des chunks.
Sinon, le plus robuste pour les vieilles WebViews est de forcer les cibles ES dans Vite :

TypeScript
build: {
target: 'chrome51', // Force la transpilation
cssTarget: 'chrome51',
rollupOptions: {
output: {
format: 'iife' // Évite les problématiques de modules
}
}
}
Si la cause est l'Isolation Réseau (H2)
Sur certains Android rootés/modifiés, les applications n'ont pas accès au loopback partagé.
Solution : Tu as déjà amorcé la solution avec le fallback IP LAN. Force l'URL à http://172.16.0.XXX:8000/kiosk/ ou l'IP de l'interface eth0 http://192.168.20.1:8000/kiosk/ dans ton cybel_kiosk_url.txt. Assure-toi qu'uvicorn tourne sur 0.0.0.0.

Option de contournement robuste en Java (Précaution)
Dans MainActivity.java, ajoute ces paramètres à ta WebView pour forcer la compatibilité maximale et désactiver les sécurités modernes inutiles en mode kiosque local :

Java
WebSettings settings = myWebView.getSettings();
settings.setJavaScriptEnabled(true);
settings.setDomStorageEnabled(true);
settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
// Essentiel pour purger le cache à chaque lancement en phase de debug
myWebView.clearCache(true); 5. Checklist de Redéploiement (Ordre Exact)
Pour éviter les faux positifs lors du prochain test, suis strictement cet ordre :

Build : npm run build du frontend (idéalement vers le fichier test pur d'abord).

Upload : Pousse dist/ sur Termux via ton script.

Backend : Redémarre cybel_lite.py sur Termux et vérifie la santé (curl http://127.0.0.1:8000/kiosk/test.html).

Purge Cache App : su -c pm clear com.cybel.visitorkiosk. C'est crucial.

Config URL : Mets à jour /sdcard/Download/cybel_kiosk_url.txt.

Lancement & Logs : Démarre l'app et surveille le logcat.

6. Signaux d'échec dans le Logcat (Tags à surveiller)
   [INFO:CONSOLE(X)] "Uncaught SyntaxError... (Tag chromium) : C'est le JS moderne qui plante. Il faut revoir la transpilation Babel/Vite.

net::ERR_CONNECTION_REFUSED (Tag chromium) : Le serveur uvicorn n'écoute pas sur la bonne interface (ex: écoute sur ::1 au lieu de 127.0.0.1 ou 0.0.0.0).

net::ERR_CLEARTEXT_NOT_PERMITTED : H3 validée. Vérifie l'application du Manifest.

net::ERR_ADDRESS_UNREACHABLE : Si tu utilises l'IP LAN (172.16...), la WebView est bloquée par un pare-feu interne ou un namespace réseau strict de l'OS Rockchip.

Si tu pouvais créer la page test.html, l'afficher via l'app, et extraire le logcat filtré sur chromium et CybelKiosk ?
