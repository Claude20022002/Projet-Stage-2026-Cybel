# Candidature CNIORI'26 — Projet CYBEL

**Compétition :** 2ᵉ Compétition Nationale de l'IoT et de la Robotique Intelligente (CNIORI'26)
— Laboratoire de Traitement de l'Information (LTI), FSBM, Université Hassan II de Casablanca.
**Candidate :** Claudia Lusamote Kimfuta (HESTIM).
**Thématiques visées :** 1 (Robotique autonome), 4 (Systèmes embarqués / Industrie 4.0),
5 (Communication, capteurs et cybersécurité).

---

## Résumé (≈ 500 mots)

**CYBEL — Reconquérir un robot de service fermé : rétro-ingénierie non destructive et
plateforme de commande ouverte.**

Les robots de service mobiles — accueil, guidage, télépresence — se généralisent, mais ils
arrivent presque toujours sous la forme d'une **boîte noire** : application propriétaire,
protocole non documenté, aucune API publique. L'utilisateur ne peut ni adapter le comportement
du robot, ni l'auditer, ni le faire dialoguer avec son propre système d'information. Il reste
dépendant d'un cloud constructeur, avec les risques de sécurité et de confidentialité que cela
implique. **CYBEL** répond directement à ce verrou sur un robot de réception réel, le CIOT
TY1251D-03195, composé d'un châssis de navigation sous ROS et d'une tête Android, et dont aucune
documentation n'était disponible.

Notre contribution est une **méthodologie de rétro-ingénierie non destructive, guidée par
hypothèses**, pensée pour être généralisable à d'autres plateformes fermées. En sept phases
(cartographie réseau, introspection ROS via rosbridge/rosapi, observation passive MQTT, analyse
statique des APK constructeur, inspection de trames, intégration *edge*, validation terrain),
nous reconstruisons le protocole interne du robot **sans jamais le modifier physiquement ni
contourner ses sécurités matérielles**. Chaque commande découverte est validée par falsification
de quatre hypothèses. L'une d'elles livre un résultat central : **un accusé de réception au
niveau transport ne garantit pas l'exécution physique** (« transport ≠ exécution ») — un piège
que l'on retrouve aussi bien dans la pile du constructeur que, de façon instructive, dans notre
propre code, et qui impose de vérifier le mouvement réel du robot (deltas de pose, codes d'état)
plutôt que la seule réponse réseau.

Sur cette compréhension reconstruite, nous avons bâti une **plateforme de commande ouverte et
modulaire** : un SDK Python (implémentations simulée et réelle interchangeables), un backend
FastAPI (REST + WebSocket), une interface opérateur web (carte SLAM, LiDAR, téléopération,
diagnostics), et un kiosque visiteur tactile bilingue. L'ensemble se déploie **de façon
autonome et embarquée sur la tête Android du robot** (Termux), sans PC ni cloud : l'intelligence
reste **à bord**, en cohérence avec une approche *edge* et respectueuse de la vie privée — la
reconnaissance faciale fonctionne **sur l'appareil, sans qu'aucune image ne quitte le robot**,
et le chatbot vocal (reconnaissance à vocabulaire fermé, mot d'éveil) fonctionne **hors-ligne**.

Les résultats ont été **validés sur le robot physique** : des centaines de topics et services
ROS caractérisés, une navigation guidée multi-arrêts fiable, une synthèse vocale bilingue FR/EN
via un pont Android natif, et une reconnaissance faciale opérationnelle en conditions réelles.
Le robot a d'ailleurs assuré l'animation d'un événement institutionnel (circulation autonome et
annonces vocales) piloté par notre plateforme.

Au-delà du cas d'étude, CYBEL démontre qu'il est possible de **rouvrir un système robotique
propriétaire de manière méthodique, sûre et reproductible**, question clé pour la souveraineté
technologique, la cybersécurité des réseaux de robots et l'intégration de ces machines dans des
environnements intelligents (Industrie 4.0, ville, établissements recevant du public). Nos
perspectives — extension à un calculateur compagnon embarqué (Raspberry Pi 5) pour une IA de
bord plus puissante, et passage à un graphe ROS 2 — prolongent cette démarche vers des robots de
service **réellement ouverts, interopérables et maîtrisés de bout en bout**.

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
