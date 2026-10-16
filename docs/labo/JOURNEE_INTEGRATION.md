# Journée d'intégration HESTIM — bâtiment Ghandi

Mode « événement » : les deux écrans affichent les visuels de l'école et le robot fait des
annonces vocales. **Le mode événement seul ne fait pas bouger le robot** ; la circulation au
rez-de-chaussée est un script séparé, lancé depuis le PC (voir [Circulation](#circulation)).

## Réseau : ce qui passe par le câble, ce qui passe par le Wi-Fi

| Besoin | Lien | Adresse |
|---|---|---|
| Déployer (code, visuels, APK), logs, captures d'écran | **USB** (`adb`), robot à l'arrêt | — |
| Circulation (mouvement) | Wi-Fi du robot `TY1251D-03195` | rosbridge `10.42.0.1:9090` |
| État, POI, annonces vocales | Wi-Fi du robot (routé par le châssis) | tête `172.16.2.138:8001` |

Le backend tourne sur la tête : le robot n'a besoin ni du PC ni du câble pour afficher et
parler. `adb` par Wi-Fi est refusé par la tête (port 5555 fermé, constaté le 2026-10-16) ;
l'activer demande le câble (`adb tcpip 5555`). L'adresse Wi-Fi de la tête vient du DHCP
et peut changer : la relever en début de journée (`adb shell ip -4 addr show wlan0`, ou dans
les paramètres Wi-Fi Android de la tête).

| Élément | Où | Source |
|---|---|---|
| Écran du dessus (tactile) | Kiosque `CybelVisitorKioskTest`, mode événement | `frontend-kiosk/public/event/ecran-dessus.jpg` |
| Écran du dessous | App `CybelSecondScreen` (écran HDMI, display 1) | `/sdcard/Cybel/ecran-dessous.jpg` sur la tablette |
| Annonces vocales | Backend Termux, `/api/event/*` | `data/kiosk_config.ghandi.json` → `event.announcements` |

Visuels d'origine (4075×2303) : `docs/capture_jrn_integration/`, recadrés en 1920×1080. Le QR
code du visuel du dessus reste lisible à cette résolution (vérifié par décodage sur la capture
de l'écran réel).

## Activer / désactiver

Depuis le PC, robot branché en USB :

```bash
bash scripts/deploy_event.sh            # active le mode événement (sauvegarde la config labo)
bash scripts/deploy_event.sh --apk      # idem + (ré)installe CybelSecondScreen
bash scripts/deploy_event.sh --restore  # revient à la config d'avant l'événement
```

## Annonces vocales

Par le Wi-Fi (ou `localhost:18001` avec le câble, tunnel ouvert par le script) :

```bash
TETE=http://172.16.2.138:8001
curl -X POST $TETE/api/event/announce/say                  # annonce suivante, tout de suite
curl -X POST $TETE/api/event/announce/say -d '{"index":2}' # une annonce précise
curl -X POST $TETE/api/event/announce/start                # boucle (toutes les 90 s)
curl -X POST $TETE/api/event/announce/stop
curl $TETE/api/event/status
```

Ne pas lancer la boucle `announce/start` en même temps que `circulation.py --announce` :
le robot parlerait deux fois plus. Choisir l'un ou l'autre.

- La boucle saute son tour si le robot parle déjà ; intervalle minimal 20 s.
- `announce_autostart: true` dans la config relance la boucle à chaque démarrage du backend.
  Laissé à `false` tant que le robot est au labo, pour ne pas parler toute la journée à vide.
- **Ne pas écrire « Cybel » dans les annonces** : c'est un déclencheur du mot d'éveil, le
  robot rouvrirait son propre micro en s'entendant.

## Kiosque verrouillé

En mode événement, le toucher et les commandes vocales sont ignorés côté kiosque : un visiteur
ne peut pas lancer la visite du labo ni une navigation. L'accueil sur détection de présence est
coupé (il propose la visite du labo, hors sujet à Ghandi).

## Changer un visuel

- Dessus : remplacer `frontend-kiosk/public/event/ecran-dessus.jpg` (1920×1080) puis
  `bash scripts/deploy_event.sh`.
- Dessous : `adb push nouvelle.jpg /sdcard/Cybel/ecran-dessous.jpg` puis
  `adb shell am startservice -n com.cybel.secondscreen/.SecondScreenService`.

## Circulation

[`scripts/circulation.py`](../../scripts/circulation.py), lancé depuis le PC connecté au Wi-Fi
du robot. Boucle sur une liste de POI de la carte active, pause à chaque arrêt, annonce vocale
optionnelle à l'arrivée.

```bash
python scripts/circulation.py --dry-run                     # vérifie tout, ne bouge pas
python scripts/circulation.py --cycles 1                    # un seul tour, pour tester
python scripts/circulation.py --announce                    # boucle jusqu'à l'arrêt, avec annonces
python scripts/circulation.py --stops POINT-ECRAN,POINT-HALL,POINT-ENTREE --dwell 30 --announce
```

| Option | Défaut | Rôle |
|---|---|---|
| `--stops` | `POINT-CHARGE,POINT-ECRAN` | POI visités dans l'ordre |
| `--dwell` | 20 s | pause à chaque arrêt |
| `--cycles` | 0 (sans fin) | nombre de tours |
| `--battery-min` | 25 % | en dessous : retour à `--return-point` puis fin |
| `--min-localization` | 60 % | en dessous : fin (relocaliser avec Deployment Tool) |
| `--announce` | non | une annonce du mode événement à chaque arrivée |
| `--backend` | `http://172.16.2.138:8001` | adresse Wi-Fi de la tête |

**Arrêter** : bouton d'arrêt d'urgence du robot (toujours prioritaire), Ctrl+C, ou créer le
fichier `data/logs/circulation.stop` (le script s'arrête à la vérification suivante, au plus
tard en fin de trajet). En sortie, le robot reçoit toujours une annulation.

**Comment un trajet est jugé.** Comme lors de la campagne d'ablation : annulation, attente d'un
état prêt, appel `/poi`, puis succès **seulement si la position du robot arrive à moins de
0,8 m du POI**. Un but acquitté sans que le robot ne progresse de 0,3 m en 20 s compte comme
non exécuté (le piège H4) : une nouvelle tentative, puis le trajet est déclaré raté. Deux
trajets ratés d'affilée arrêtent la circulation.

**Avant chaque trajet**, le script relit l'état du robot et s'arrête si l'arrêt d'urgence est
enclenché, si la localisation est faible ou si le châssis est déconnecté. Il ne relocalise
jamais lui-même : la relocalisation fait tourner le robot sur place, c'est à l'opérateur de la
lancer depuis Deployment Tool.

**Si le Wi-Fi tombe**, le robot termine au plus le trajet en cours puis reste sur place : le
PC ne peut plus lui envoyer de nouveau but. Garder le PC à portée du Wi-Fi du robot.

**Journal** : `data/logs/circulation_AAAAMMJJ.jsonl`, une ligne par événement (départ,
arrivée, échec avec sa raison, annonce, fin).

## Carte Ghandi

Carte « bâtiment ghandi » active sur le robot, POI au 2026-10-16 : `POINT-CHARGE` (≈ 0, 0) et
`POINT-ECRAN` (8,11 ; −13,59), environ 16 m d'écart. Le point de charge y est de type `common`
et s'appelle `POINT-CHARGE`, alors que le retour borne du backend (`go_home`) attend
`POINT-RECHARGE` ; `circulation.py` prend son point de retour en option et n'est pas concerné.

Pour la journée, ajouter dans Deployment Tool les POI du parcours (MAJUSCULES et tirets, au
moins 2–3 m de dégagement autour), puis les passer à `--stops`.
