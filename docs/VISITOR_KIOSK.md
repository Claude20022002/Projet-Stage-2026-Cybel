# Interface visiteur (kiosque) — début d'implémentation

Documentation de la première version de l'**interface visiteur** du robot CYBEL, destinée à être affichée en plein écran sur l'écran tactile de l'upper body Android, et utilisable directement par un visiteur (sans opérateur).

---

## 1. Vue d'ensemble

Contrairement au tableau de bord opérateur (`frontend/`, port `5173`), cette interface (`frontend-kiosk/`, port `5174` en développement) est une **application web séparée**, volontairement minimaliste :

- de gros boutons tactiles pour des **actions de base** (accueil, navigation vers une salle, visite guidée, mode attente, signaler un délai, arrêt) ;
- un écran **« S'informer »** qui affiche une FAQ sur l'établissement et fait répondre le robot à voix haute (TTS) ;
- un bouton **FR / EN** qui bascule toute l'interface (textes affichés et annonces vocales) en anglais.

Elle réutilise le même backend FastAPI (`:8000`) que l'interface opérateur — aucune nouvelle infrastructure serveur n'est nécessaire.

Pour l'installation **sur le robot**, elle est packagée dans une petite
application Android (`android/CybelVisitorKiosk/`, §6) qui l'affiche en plein
écran via une `WebView` — c'est cette app que les visiteurs utilisent
directement sur l'écran de l'upper body.

## 2. Démarrage (développement)

`python scripts/dev.py` lance trois processus : backend (`:8000`), interface
opérateur (`:5173`) et interface visiteur (`:5174`, serveur Vite avec
rechargement à chaud — pratique pour itérer sur l'UI).

Pour tester rapidement dans un navigateur de bureau, ouvrir
`http://127.0.0.1:5174`.

## 3. Actions disponibles

Les actions affichées proviennent de `GET /api/reception/actions` (définies dans `sdk/reception_actions.py`), filtrées pour exclure la catégorie `maintenance` (ex. retour à la pile, réservé à l'opérateur).

Chaque action peut désormais porter des champs optionnels `label_en`, `description_en` et `speech_en` en plus des champs français existants (`label`, `description`, `speech`).

Le kiosque appelle :

```http
POST /api/reception/actions/{action_id}/execute?lang=fr|en
```

Le paramètre `lang` (par défaut `fr`) sélectionne, côté `ReceptionService.execute()`, le texte prononcé par le robot (`speech_en` si disponible et `lang=en`, sinon `speech`). Le comportement de navigation/route reste identique quelle que soit la langue.

## 4. Écran « S'informer » (FAQ)

Le contenu de la FAQ provient de :

```http
GET /api/knowledge/faq
```

qui sert le tableau `faq` de [data/hestim_knowledge_base.json](../data/hestim_knowledge_base.json) — une base de connaissances de démarrage sur HESTIM (présentation, écoles, filières, gouvernance, contact, valeurs...), collectée depuis [hestim.ma](https://www.hestim.ma/) et ses sous-domaines.

Chaque entrée FAQ contient `question_fr` / `question_en` et `reponse_fr` / `reponse_en`. Toucher une question affiche la réponse dans la langue courante et la fait prononcer par le robot via `POST /api/speech/say`.

Ce fichier JSON est aussi le point de départ de la base de connaissances utilisée par le module de questions/réponses vocales développé en parallèle ; sa section `_meta.todo` liste les informations encore à compléter (gouvernance nominative, chiffres clés, e-mail de contact, vie associative).

## 5. Build de production et service par le backend

Pour un déploiement réel (et pour l'app Android, §6), l'interface visiteur
est **compilée en fichiers statiques** et servie directement par le backend
FastAPI — pas besoin de garder le serveur Vite (`:5174`) actif :

```bash
cd frontend-kiosk
npm run build        # génère frontend-kiosk/dist/
```

`backend/main.py` monte automatiquement ce dossier (s'il existe) sur
`/kiosk` :

```python
KIOSK_DIST = ROOT / "frontend-kiosk" / "dist"
if KIOSK_DIST.is_dir():
    app.mount("/kiosk", StaticFiles(directory=str(KIOSK_DIST), html=True), name="kiosk")
```

➡️ Une fois le build fait, `http://<adresse-du-poste-backend>:8000/kiosk/`
sert l'interface visiteur complète (même origine que l'API, donc pas de
souci CORS). **Penser à relancer `npm run build` après toute modification de
`frontend-kiosk/src/`** — contrairement au dashboard opérateur, ce build n'est
pas régénéré automatiquement par `scripts/dev.py`.

## 6. Application Android installée sur le robot (`CybelVisitorKiosk`)

Pour que les visiteurs interagissent **uniquement via l'écran du robot**,
l'interface visiteur est packagée dans une petite application Android native
(`android/CybelVisitorKiosk/`), construite **sans Gradle/Android Studio** avec
les mêmes outils en ligne de commande du SDK que
[`CybelTTSBridge`](TTS_BRIDGE.md#62-build-sans-gradleandroid-studio)
(`aapt2`, `javac`, `d8`, `zipalign`, `apksigner`).

> ℹ️ L'app est écrite en **Java** (et non Kotlin) : `kotlinc` n'est pas
> disponible dans la toolchain du poste de dev, alors que `javac` (utilisé par
> `CybelTTSBridge`) l'est. Le résultat est équivalent pour l'utilisateur —
> une petite app native, légère pour les 2 Go de RAM de la tablette.

### 6.1 Principe

`MainActivity` affiche une `WebView` plein écran (mode immersif, barre de
navigation Android masquée, écran toujours allumé) qui charge l'URL
`KIOSK_URL` définie dans
[`MainActivity.java`](../android/CybelVisitorKiosk/src/com/cybel/visitorkiosk/MainActivity.java) —
c'est-à-dire `/kiosk/` servi par le backend (§5). Le bouton retour Android est
désactivé (mode kiosque : le visiteur ne peut pas quitter l'app). En cas
d'erreur de chargement (backend indisponible), la page est rechargée
automatiquement toutes les 5 secondes. Un `BootReceiver` relance l'app au
démarrage de la tablette (`BOOT_COMPLETED`).

### 6.2 Configuration de `KIOSK_URL` — ⚠️ problème de topologie réseau non résolu

```java
private static final String KIOSK_URL = "http://127.0.0.1:8000/kiosk/";
```

Le backend tourne **sur la tablette** (Termux, mode lite). L'ancienne URL
`http://10.42.0.155:8000/kiosk/` (PC dev) n'est **pas joignable** depuis la
tête Android — d'où `ERR_ADDRESS_UNREACHABLE` si l'APK n'a pas été réinstallé.

Après modification de `KIOSK_URL`, reconstruire et réinstaller :

```bash
# Build (PowerShell, depuis android/CybelVisitorKiosk)
# … voir build.sh ou scripts/install_kiosk_apk.py

python scripts/install_kiosk_apk.py   # via SSH + pm install
# ou : adb install -r android/CybelVisitorKiosk/out/CybelVisitorKiosk.apk
```

Vérifier que Termux exécute le backend : `curl http://127.0.0.1:8000/api/health`
(passerelle `10.42.0.1`, châssis — voir [docs/ROBOT_CONNECTION.md](ROBOT_CONNECTION.md)).

**Cette valeur n'a pas pu être validée et est probablement injoignable depuis
la tablette.** En inspectant la configuration réseau de la tête Android
(`adb shell ip addr show wlan0` / `ip route`), elle est en fait sur un
**second réseau Wi-Fi distinct, `172.16.0.0/16`** (IP `172.16.0.194`), sans
route vers `10.42.0.0/24` ni route par défaut. Un `ping` de la tête Android
vers `10.42.0.155` ne reste pas local : il ressort sur Internet (réponse
« Time to live exceeded » d'une IP publique), donc il n'y a **pas de route
retour** vers le poste de dev.

➡️ La connexion `adb connect 172.16.0.194:5555` fonctionne malgré tout depuis
le poste de dev — probablement via une translation d'adresse (NAT) côté
châssis (`10.42.0.1`) qui a une patte sur les deux réseaux — mais ce mécanisme
ne semble pas bidirectionnel pour un nouveau port (8000) initié depuis la tête
Android.

### 6.2.1 Pistes investiguées (2026-06-15)

- **`adb reverse tcp:8000 tcp:8000`** (tunnel via la connexion ADB existante,
  qui elle fonctionne dans les deux sens) — semblait la solution la plus
  simple, mais échoue systématiquement avec `error: more than one
  device/emulator`, même avec un seul appareil connecté et `-s` explicite.
  Cause identifiée : `adb -s 172.16.0.194:5555 features` ne liste que `cmd` et
  `shell_v2` — l'`adbd` de cette tête Android (Android 7.1, ancien) **ne
  supporte pas le protocole `reverse:forward`** attendu par le client adb
  35.0.2. **Abandonné.**

- **Ajout d'une route IP sur la tête Android** (root disponible via
  `adb shell` → `su`, `uid=0`). Inspection de `ip route` côté tête :

  ```text
  172.16.0.0/16  dev wlan0  src 172.16.0.194   (Wi-Fi, réseau "TY1251D-03195")
  192.168.10.0/24 dev eth0  src 192.168.10.138
  192.168.20.0/24 dev eth0  src 192.168.20.1   (tête = .1, châssis = .22)
  ```

  La connexion ADB existante (PC → tête) arrive via `eth0` depuis
  `192.168.20.22` (le châssis), confirmant que le châssis NAT déjà le trafic
  `10.42.0.0/24 → tête` vers ce lien interne `192.168.20.0/24`.
  Test : `ip route add 10.42.0.0/24 via 192.168.20.22 dev eth0` puis
  `ping 10.42.0.155` **et** `ping 10.42.0.1` (le châssis lui-même) — les deux
  échouent toujours (« Time to live exceeded » depuis une IP publique). Le
  châssis ne route/NAT que dans le sens **PC/`10.42.0.x` → tête**, pas
  l'inverse (pas de règle `FORWARD`/`MASQUERADE` `192.168.20.0/24 →
  10.42.0.0/24` côté châssis). Route retirée après test (état du robot
  inchangé).

➡️ **Conclusion** : sans accès SSH/root au châssis (`10.42.0.1` — déjà tenté
et infructueux, voir [docs/TTS_BRIDGE.md §2](TTS_BRIDGE.md#2-pistes-explorées-et-écartées))
pour y ajouter une règle de routage retour, **aucune connexion initiée depuis
la tête Android vers le poste de dev (quel que soit le port) n'aboutit**. Ce
n'est donc pas spécifique à `adb reverse` ni au port 8000 : c'est une
limitation réseau du robot lui-même.

### 6.2.2 Pistes restantes (non implémentées)

1. **Connecter le poste de dev au Wi-Fi `172.16.0.0/16`** si ce réseau est
   diffusé comme SSID séparé (à vérifier sur site — depuis le poste actuel,
   seul `TY1251D-03195` est visible, qui correspond au `10.42.0.0/24` du
   châssis).
2. **Héberger `/kiosk` + le backend directement sur la tête Android** via
   Termux (déjà installé, voir [docs/TTS_BRIDGE.md §4](TTS_BRIDGE.md#4-exploration-des-applications-android-candidates)) :
   la `WebView` chargerait alors `http://127.0.0.1:8000/kiosk/` (aucun
   problème réseau), et le TTS se ferait par `am broadcast` **local** (`su -c`,
   sans ADB). Reste à valider que Termux peut faire tourner FastAPI/uvicorn
   sur cet appareil (Android 7.1, RK3399, 2 Go RAM) et que la tête a un accès
   réseau à `10.42.0.1:9090` (rosbridge) — non vérifié, et le test §6.2.1
   suggère que non via ce chemin.
3. **Demander à l'administrateur réseau** (côté établissement) une règle de
   routage/forward retour `192.168.20.0/24 → 10.42.0.0/24` sur le châssis, ou
   un accès SSH au châssis pour l'ajouter soi-même.

En attendant, `KIOSK_URL` reste une constante à adapter manuellement une fois
une solution réseau trouvée — comme pour `SPEECH_HTTP_HOST`/`SPEECH_ADB_SERIAL`
(IP DHCP instable, voir [docs/TTS_BRIDGE.md §9](TTS_BRIDGE.md#9-limites-connues-et-points-dattention)).
Après modification, relancer `build.sh` et réinstaller l'APK
(`adb install -r out/CybelVisitorKiosk.apk` — déjà installée une première fois,
§6.3).

### 6.3 Build et installation

```bash
cd android/CybelVisitorKiosk
./build.sh                            # -> out/CybelVisitorKiosk.apk
adb -s 172.16.0.194:5555 install -r out/CybelVisitorKiosk.apk
```

(remplacer `172.16.0.194:5555` par le serial ADB actuel de la tête Android,
voir [docs/ROBOT_CONNECTION.md §4](ROBOT_CONNECTION.md#4-procédure-de-reconnexion-adb-à-la-tête-android)).

Lancer ensuite l'app « CYBEL Accueil » depuis le lanceur Android de la
tablette (ou `adb shell am start -n com.cybel.visitorkiosk/.MainActivity`).
S'assurer au préalable que `python scripts/dev.py` tourne et que
`frontend-kiosk/dist/` est à jour (§5) — sinon `/kiosk/` répond `404` et l'app
restera en boucle de rechargement.

### 6.4 Limites connues

- `KIOSK_URL` est une constante codée en dur, à modifier et reconstruire si
  l'IP du poste backend change (pas de découverte automatique).
- Pas d'écran de configuration dans l'app — toute modification (URL,
  comportement du bouton retour, etc.) nécessite de reconstruire l'APK.
- Le mode immersif/plein écran dépend des flags `View.SYSTEM_UI_FLAG_*`
  (API 23-25, conformes à l'Android 7.1 de la tablette) ; non testé sur
  d'autres versions d'Android.

## 7. Limites connues / suite

- Pas de reconnaissance vocale côté visiteur dans cette première version (uniquement tactile) — le micro opérateur existant (`voice.ts`) n'est pas repris ici.
- La FAQ est statique (lecture du JSON à chaque requête) ; pas encore connectée au module conversationnel en préparation.
- Le bouton FR/EN ne couvre que cette interface visiteur ; le tableau de bord opérateur reste en français.
