# Candidature CNIORI'26 — Projet CYBEL

**Compétition :** 2ᵉ Compétition Nationale de l'IoT et de la Robotique Intelligente (CNIORI'26)
— Laboratoire de Traitement de l'Information (LTI), FSBM, Université Hassan II de Casablanca.
**Candidate :** Claudia Lusamote Kimfuta (HESTIM).
**Thématiques visées :** 1 (Robotique autonome), 4 (Systèmes embarqués / Industrie 4.0),
5 (Communication, capteurs et cybersécurité).

---

## Résumé (≈ 500 mots)

**CYBEL — Et si un robot « fermé » pouvait rouvrir ses portes ?**

Un robot d'accueil flambant neuf arrive au laboratoire. Il sait se déplacer, guider, parler — à
une seule condition : qu'on ne lui demande rien d'autre que ce que son fabricant a prévu. Pas
d'API, pas de documentation, pas d'accès à son protocole interne. On peut le regarder
fonctionner, pas le comprendre, et encore moins le faire évoluer. Comme la plupart des robots de
service d'aujourd'hui, c'est une boîte noire pilotée par un cloud constructeur sur lequel
l'utilisateur n'a aucune prise — ni technique, ni sécuritaire, ni éthique. C'est précisément ce
mur que le projet CYBEL a choisi de franchir, sur un robot bien réel : le CIOT TY1251D-03195, un
châssis de navigation sous ROS surmonté d'une tête Android, livré sans la moindre notice.

Plutôt que de forcer la machine, nous avons adopté une démarche de détective : une
rétro-ingénierie **non destructive, guidée par hypothèses**. En sept étapes — cartographier le
réseau, interroger les services ROS, écouter passivement les échanges, analyser les applications
du constructeur, inspecter les trames, intégrer notre propre code à bord, valider sur le terrain
— nous avons reconstruit le langage interne du robot **sans jamais le modifier physiquement ni
contourner ses sécurités**. Chaque commande supposée était mise à l'épreuve avant d'être tenue
pour acquise. Cette rigueur a révélé un piège aussi contre-intuitif qu'universel : **qu'un robot
accuse réception d'un ordre ne prouve en rien qu'il l'exécute**. Le « transport » n'est pas
l'« exécution » — une leçon que nous avons retrouvée jusque dans notre propre code, et qui oblige
à vérifier le mouvement réel du robot plutôt que la simple réponse réseau.

Sur cette compréhension patiemment reconstituée, nous avons bâti une **plateforme de commande
ouverte** : un SDK Python, un backend FastAPI, une interface opérateur (carte SLAM, LiDAR,
téléopération) et un kiosque visiteur tactile bilingue. Son originalité : **tout tourne à bord
du robot, sans PC ni cloud**. L'intelligence reste locale, et la vie privée avec elle — la
reconnaissance faciale s'effectue sur l'appareil, sans qu'aucune image n'en sorte, et
l'assistant vocal fonctionne entièrement hors-ligne.

Le tout a été validé sur le robot physique : des centaines de services ROS caractérisés, une
visite guidée multi-arrêts fiable, une voix bilingue FR/EN, une reconnaissance des visages
opérationnelle en conditions réelles. Le robot a même animé un événement institutionnel —
circulation autonome et annonces vocales — entièrement piloté par notre plateforme.

Mais CYBEL dépasse son cas d'étude. Il démontre qu'on peut **rouvrir un système robotique
propriétaire de façon méthodique, sûre et reproductible** : une question de souveraineté
technologique, de cybersécurité des flottes de robots et d'intégration de ces machines dans nos
espaces intelligents — industrie, ville, lieux publics. Demain, un calculateur embarqué plus
puissant (Raspberry Pi 5) et un passage à ROS 2 porteront cette intelligence encore plus loin.

Redonner la main sur les robots qui nous entourent : voilà, en une phrase, ce que défend CYBEL.

*(≈ 500 mots)*

---

## Pourquoi CYBEL entre dans les thématiques

| Thématique CNIORI'26 | Rattachement CYBEL |
|---|---|
| **1 — Robotique autonome, collaborative et bio-inspirée** | Robot d'accueil autonome : navigation SLAM, visite guidée multi-arrêts, interaction homme-robot. |
| **4 — Systèmes embarqués pour la santé et l'industrie 4.0** | Pile logicielle *edge* déployée à bord (Termux/Android, ROS), architecture reproductible pour l'intégration de robots en milieu professionnel. |
| **5 — Communication, capteurs et cybersécurité dans les réseaux intelligents** | Rétro-ingénierie de protocole, audit d'un système fermé, maîtrise des canaux (rosbridge, MQTT, LiDAR, caméras), enjeux de souveraineté et de vie privée. |
| **3 — IoT pour l'IA** *(partiel)* | IA embarquée sur l'appareil : reconnaissance faciale *on-device* (aucune image transmise), voix hors-ligne. |

## Rappel calendrier

- **Réception des projets : 11 août → 30 octobre 2026** ← échéance imminente.
- Sélection et notifications : à partir du 31 octobre 2026.
- Jour de la compétition : 25 novembre 2026.
- Contact : Pr. Mohamed Talea — taleamohamed@yahoo.fr — #CNIORI26 — www.fsbm.ma
