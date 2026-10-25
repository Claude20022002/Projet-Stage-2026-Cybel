# Faire évoluer le calculateur embarqué de CYBEL — étude de viabilité

> Étude d'ingénierie : comment augmenter les capacités du robot CIOT TY1251D-03195 et
> contourner l'ancienneté de la tête Android (Android 7.1 / RK3399). Analyse des options
> proposées + alternatives, classées par viabilité et fiabilité.

**TL;DR — recommandation :** ajouter un **Raspberry Pi 5 comme calculateur compagnon**
(option B ci-dessous), non destructif et réversible. Éviter tout reflashage ou remplacement
de carte interne : le robot est **prêté par HESTIM**, sans image firmware publique, donc toute
opération irréversible expose à un **bricage définitif d'un matériel qu'on ne possède pas** — et
casse la propriété « non destructive » qui fait la valeur du projet.

---

## 0. Rappel d'architecture : trois calculateurs, pas un

| Calculateur | Rôle | OS | Accès |
|---|---|---|---|
| **Châssis** | SLAM, `move_base`, moteurs, LiDAR, batterie, odométrie | Linux embarqué + ROS 1 (Noetic/Melodic) | **rosbridge `:9090` seulement** ; SSH verrouillé |
| **Tête (upper body)** | Écran tactile 15,6", caméras, HP, apps constructeur, IHM | Android 7.1, SoC RK3399, 2 Go RAM, 16 Go ROM | `adb`, root `su`, Termux |
| **MCU** | Contrôle temps réel moteurs / capteurs châssis | firmware propriétaire | pont série via `com.bjw.ComAssistant` / `com.sunbo.McuCommand` |

Conséquences pour toute évolution :

- Le **châssis** est la seule chose qui fait bouger le robot. On n'y a pas de shell. Il n'est
  pilotable que par rosbridge. **On n'y touche pas physiquement.**
- Le « vieil Android » = **la tête**. Mais son ancienneté gêne surtout deux choses déjà
  contournées : la WebView (Chrome 49 → build IIFE) et le ML dans l'app (→ apps natives TFLite
  2.9 / Vosk). Le code Python/Node de CYBEL tourne déjà en **moderne** dans Termux,
  indépendamment d'Android 7.1.
- Les apps **constructeur** (welcomepatrol, sentrymove, `ComAssistant`, moteur TTS Google)
  n'existent **que sous Android** et servent de pont vers le MCU, les caméras et le TTS.
  Quitter Android = perdre ce pont, sauf à tout réimplémenter.

---

## 1. Évaluation des options proposées

### Option 1 — Dual-boot Linux sur le robot (partitionnement)

**Sur quel calculateur ?**

- **Sur la tête (RK3399) :** techniquement, le RK3399 est très bien supporté par Linux mainline
  (Armbian/Ubuntu existent pour RockPro64, NanoPC-T4…). Mais :
  - ce n'est **pas un dual-boot x86** : pas de BIOS/GRUB, c'est U-Boot + partitions eMMC
    (+ éventuellement carte SD). Faisable mais délicat ;
  - **2 Go RAM / 16 Go ROM** déjà quasi pleins par Android → marge quasi nulle pour une 2ᵉ ROM ;
  - surtout, booter sous Linux = **perdre toute la couche Android du constructeur** : pont série
    MCU, moteur TTS, pilotes caméras, calibration du tactile. Il faudrait tout réécrire ;
  - **risque de bricage élevé** : repartitionner l'eMMC avec un U-Boot potentiellement
    verrouillé/signé, sans image de restauration vendeur, peut rendre la tête **irrécupérable**.
- **Sur le châssis :** accès shell absent, c'est le cerveau de navigation. Le repartitionner =
  risquer de perdre SLAM/`move_base`. **À proscrire.**

> **Viabilité : faible. Fiabilité : faible.** Gain réel incertain, perte de l'intégration
> constructeur certaine, risque de bricage d'un matériel prêté. **Non recommandé.**

### Option 2 — Ajouter un Raspberry Pi 5 à l'arrière (communication avec la carte interne)

C'est le patron **« calculateur compagnon »** (companion computer), standard et éprouvé en
robotique (drones PX4, TurtleBot, bras ROS…). Le Pi **n'enlève rien** : il s'ajoute.

- Le Pi 5 (4× Cortex-A76 2,4 GHz, jusqu'à 16 Go RAM) est **nettement plus puissant** que le
  RK3399 et tourne **Ubuntu 24.04 + ROS 2** nativement.
- Il dialogue avec le châssis **exactement comme le PC CYBEL aujourd'hui** : par rosbridge
  (`10.42.0.1:9090` sur le Wi-Fi du robot, ou mieux par **Ethernet** sur le segment interne
  `192.168.20.x`). Aucune modification interne.
- Il peut **héberger le backend CYBEL en permanence**, en remplacement du rôle tenu aujourd'hui
  par Termux sur la tête (2 Go RAM, 16 Go pleins) : plus de RAM, vrai Linux, dépendances
  modernes, logs, redémarrage auto.
- **Communication « carte interne » :** passer par rosbridge couvre déjà tout ce que le châssis
  expose. Un lien **série direct vers le MCU** n'est utile que pour descendre plus bas que
  rosbridge — rarement nécessaire et plus risqué ; à garder en réserve.
- **Alimentation :** batterie 24 V/20 Ah → **convertisseur DC-DC buck 24 V→5 V / 5 A** (le Pi 5
  demande ~25 W en charge). Pour un premier prototype, une **batterie USB-C PD indépendante**
  isole proprement le Pi de l'alimentation robot.
- **Montage :** platine à l'arrière, fixation non invasive, câble Ethernet ou antenne Wi-Fi.
  Entièrement **réversible**.

> **Viabilité : élevée. Fiabilité : élevée.** Non destructif, réversible, gros gain de calcul,
> prolonge naturellement l'architecture CYBEL. **Recommandé — chemin principal.**

### Option 3 — Remplacer totalement la carte par un Raspberry Pi 5

**Remplacer quelle carte ?**

- **La tête :** on perd l'écran 15,6" (le Pi ne pilote pas forcément ce panneau DSI/eDP
  spécifique sans le bon pilote/EDID), les caméras, les HP, le TTS vendeur et le pont série MCU.
  Il faut re-sourcer l'écran, les caméras, reconstruire le protocole MCU. **Des mois de travail**,
  risque élevé, sur un robot prêté.
- **Le châssis :** c'est le couple calculateur + contrôleurs moteurs + encodeurs + LiDAR + IMU,
  avec la calibration et le firmware du constructeur. Le remplacer = **réécrire toute la commande
  bas niveau et le SLAM** et interfacer le Pi directement aux drivers moteurs. C'est
  **construire un nouveau robot.**

> **Viabilité : très faible.** N'a de sens que si l'on **possède** le robot, avec un horizon
> long et une pièce de rechange. **Non recommandé dans le cadre du stage.**

---

## 2. Alternatives (propositions d'expert)

### A. Pi 5 compagnon + tête réduite à un terminal d'affichage *(recommandé, variante aboutie de l'option 2)*

Le Pi 5 porte **tout** : backend CYBEL, navigation, et l'IA lourde
(reconnaissance faciale avec de meilleurs modèles, STT moderne type `whisper.cpp`, dialogue).
La **tête Android ne sert plus que d'écran tactile** : son navigateur/WebView affiche l'UI
servie par le Pi, et le TTS/caméras restent utilisables via `adb`/broadcast si on les garde.
Résultat : **pile logicielle moderne, zéro modification interne**, l'« ancienneté d'Android »
devient sans objet puisque l'intelligence a migré sur le Pi.

### B. Pont ROS 1 → ROS 2 sur le Pi

Lancer `ros1_bridge` (ou un pont rosbridge→ROS 2) sur le Pi pour **exposer les topics ROS 1 du
châssis dans un graphe ROS 2 moderne**. On accède alors à l'outillage actuel (Nav2, rviz2,
visualisation, enregistrement rosbag2) **sans toucher au châssis**. Très bon rapport
gain/risque, complète A.

### C. Garder Android, ne moderniser que le logiciel (sans reflash)

L'essentiel du frein « Android 7.1 » est déjà neutralisé : code serveur moderne dans Termux,
apps natives pour le ML. Flasher une ROM custom (LineageOS/Android plus récent) sur ce RK3399
précis n'a **pas d'image publique** → risque de bricage et perte des blobs pilotes
(caméra, tactile, pont MCU). **Mauvais rapport risque/bénéfice** face à A.

### D. Second écran déjà récupéré

L'écran du dessous s'est révélé être un **affichage HDMI** (display 1) piloté par
`CybelSecondScreen`. Un Pi compagnon pourrait aussi alimenter un écran additionnel si besoin.

---

## 3. Synthèse — classement viabilité / fiabilité

| # | Option | Destructif ? | Risque bricage | Gain capacité | Effort | Note |
|---|---|---|---|---|---|---|
| 1 | **Pi 5 compagnon (option 2)** | Non | Nul | Élevé | Moyen | ★★★★★ |
| 2 | **Pi 5 + tête en terminal (alt. A) + pont ROS 2 (alt. B)** | Non | Nul | Très élevé | Moyen+ | ★★★★☆ |
| 3 | Dual-boot / ROM custom sur la tête (option 1 / alt. C) | Oui | **Élevé** | Moyen | Élevé | ★★☆☆☆ |
| 4 | Remplacer la carte de la tête (option 3a) | Oui | Élevé | Variable | Très élevé | ★☆☆☆☆ |
| 5 | Remplacer la carte du châssis (option 3b) | Oui | **Critique** | — | Extrême | ★☆☆☆☆ |

**Règle de décision :** tant que le robot est **prêté** et **sans firmware de restauration**,
on reste sur du **réversible** (options 1 et 2). Les reflashages/remplacements ne deviennent
raisonnables que sur un robot **possédé**, avec sauvegarde firmware et pièce de rechange.

---

## 4. Plan concret recommandé (si on part sur le Pi 5 compagnon)

1. **Pi 5 (8 ou 16 Go) + SSD NVMe via HAT** ou microSD A2 ; Ubuntu 24.04 + ROS 2 Jazzy.
2. **Alim** : d'abord batterie USB-C PD (isolée, sûr pour prototyper), puis buck 24 V→5 V/5 A
   sur la batterie robot pour l'intégration finale.
3. **Liaison châssis** : Ethernet sur le segment `192.168.20.x` si accessible, sinon Wi-Fi
   `10.42.0.1`. Valider `rosbridge` depuis le Pi (réutiliser le SDK CYBEL tel quel).
4. **Portage du backend CYBEL** sur le Pi (il tourne déjà sous Python/FastAPI — direct).
5. **Tête** : la laisser en kiosque, pointer sa WebView vers le Pi au lieu de Termux local.
6. **IA lourde** sur le Pi (reconnaissance faciale, STT) ; la tête garde TTS + caméras si utile.
7. **Mesurer** : latence rosbridge Pi vs PC, autonomie avec le Pi alimenté par la batterie,
   charge CPU/thermique du Pi sous charge IA.

> Avantage transversal : ce plan **prolonge** la thèse du projet (reconstruction non
> destructive d'un robot fermé) au lieu de la contredire — argument fort pour l'article et le
> rapport.
