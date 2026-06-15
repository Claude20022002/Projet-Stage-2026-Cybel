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

### 6.2 Configuration de `KIOSK_URL`

```java
private static final String KIOSK_URL = "http://10.42.0.155:8000/kiosk/";
```

`10.42.0.155` est l'IP actuelle du poste qui exécute `python scripts/dev.py`
sur le réseau Wi-Fi du robot (même réseau que `ROBOT_HOST=10.42.0.1`, voir
[docs/ROBOT_CONNECTION.md](ROBOT_CONNECTION.md)). Comme pour
`SPEECH_HTTP_HOST`/`SPEECH_ADB_SERIAL`, cette IP est attribuée par **DHCP** et
peut changer après un redémarrage — si l'app affiche une erreur de
chargement en boucle, vérifier l'IP du poste backend (`ipconfig` /
`ifconfig`), mettre à jour `KIOSK_URL`, puis relancer `build.sh` et
réinstaller.

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
