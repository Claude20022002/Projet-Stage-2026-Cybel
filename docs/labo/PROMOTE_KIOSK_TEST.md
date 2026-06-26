# Promotion CybelVisitorKioskTest → application principale

> Branche : `feature/promote-kiosk-poi-main`  
> Backend actif : `~/cybel-test` port **8001** (POI laboV2)

## Pourquoi

La variante **TEST** (navigation par POI Sentrymove) est plus fiable que l'APK production (`CybelVisitorKiosk`, coords port 8000). On conserve le backend `cybel-test` et on renomme l'APK pour l'utilisateur final.

## Sur la tablette

### 1. Désinstaller l'ancienne app

```powershell
adb uninstall com.cybel.visitorkiosk
```

### 2. Réinstaller l'APK principal (ex-Test)

```powershell
cd android/CybelVisitorKioskTest
bash build.sh
adb install -r out/CybelVisitorKioskTest.apk
```

L'icône affiche **CYBEL Accueil** (plus « POI » / « TEST »).

### 3. Config kiosque

```powershell
adb push data/kiosk_config.poi.json /data/local/tmp/kiosk_config.json
adb shell "cp /data/local/tmp/kiosk_config.json /data/data/com.termux/files/home/cybel-test/data/kiosk_config.json"
```

Redémarrer le backend : voir [GUIDE_CONTROLEUR_POI.md](GUIDE_CONTROLEUR_POI.md) §4.C.

### 4. Lancer

```powershell
adb shell am start -n com.cybel.visitorkiosk.test/.MainActivity
```

## Logs récupérés (26/06/2026)

Copie locale : `out/logs/` (uvicorn + traces visite).

| Session | Résultat | Cause |
|---------|----------|-------|
| `tour_20260626_125418` | Erreur arrêt 1 | `nav_status` 601, timeout 12 s alors que le robot bougeait encore |
| `tour_20260626_134658` | Idem | Distance résiduelle 1,92 m au moment de l'échec |

**Correctifs** (branche) :
- Détection mouvement (vitesse > 0,05) = navigation active même sans 602
- Arrivée par proximité POI (≤ 0,45 m)

## Bouton « Besoin d'aide »

Comportement actuel (minimal) :
1. Appel `POST /api/reception/actions/inform_waiting/execute`
2. TTS : *« Votre interlocuteur arrive dans quelques instants… »*
3. Toast : *« Prévenir qu'un accompagnateur arrive »*

**Pas** de notification staff, MQTT, ni déplacement robot. Amélioration prévue sur cette branche (option : alerte opérateur / MQTT).
