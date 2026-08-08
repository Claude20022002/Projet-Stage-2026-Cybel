# Réponse aux relecteurs — révision ICRA 2027

Ce document trace chaque remarque des deux rapports de relecture vers la section qui y répond
dans la version révisée de `main.tex`, et documente les deux écarts assumés vis-à-vis de la
roadmap de l'encadrant.

---

## 1. Écarts assumés par rapport à `ICRA paper roadmap.md`

### 1.1 Les sept contributions sont regroupées en trois

La roadmap demande d'énoncer C1–C7. La version révisée conserve **les sept éléments**, mais les
présente sous **trois contributions annoncées**, parce qu'un article ICRA qui en revendique sept
dilue les trois qui comptent, et parce que deux des sept (le pont TTS, la correction de
réactivité) sont des résultats d'ingénierie qui se défendent mieux comme éléments d'une
contribution que comme contributions autonomes.

| Roadmap | Où le contenu se trouve maintenant |
|---|---|
| C1 pipeline sept phases | C1 — §IV, Table II |
| C2 schéma commande/télémétrie | C2 — §V-A |
| C3 pile edge trois couches | C2 — §V-B |
| C4 canal TTS via IPC Android | C2 — §V-C |
| C5 couche d'interaction hors-ligne | C2 — §V-D, résultats en §VI-D |
| C6 court-circuit d'état | C3 — §VII-A |
| C7 validation empirique et effort | C1 et C3 — §IV (effort), §VI (mesures) |

### 1.2 H3 est reformulée

**La roadmap indique « H3 Verdict: Confirmed (Conditional) ». La version révisée ne confirme pas
H3 telle qu'énoncée.** Ce n'est pas un désaveu de l'expérience terrain, c'est le résultat de la
récupération de données de mesure perdues.

Ce que disent les données, toutes sources confondues :

| Source | Observation |
|---|---|
| Banc rosbridge nu (commit `08bfc34`, 2026-07-03) | Coordonnées 3/3 (médiane 40,9 s) ; POI 0/3, aucune transition d'état, timeout 150 s |
| Visites guidées (`data/paper_metrics.json`, 2026-07-23) | POI via pile SDK complète : 3 visites sur 3, 30 trajets |
| Événements terrain (`data/navigation_events.json`) | 10 échecs, **tous** à l'état « non localisé » ; 7 succès, **tous** à l'état « en navigation » |

Les deux schémas d'adressage échouent sans préparation et réussissent avec. Le facteur explicatif
n'est donc pas l'adressage mais **l'état des préconditions et la couche d'émission**. C'est H4
sous une seconde forme, et c'est un résultat plus général que H3.

L'article le dit explicitement, avec ses limites : Fisher exact bilatéral **p = 0,10** sur 3/3
contre 0/3, donc aucune différence n'est démontrée au niveau du banc ; et la réutilisation des
POI reste recommandée en exploitation, parce qu'elle évite la dérive de repère. Rien n'est retiré
à l'expérience terrain.

---

## 2. `Review_CYBEL_Remarques.md` — 15 remarques

| # | Remarque | Traitement |
|---|---|---|
| 1 | Le titre promet plus que ce qui est démontré | Titre de la roadmap, centré méthode. « Match or exceed » supprimé partout ; §VI-E annonce explicitement que ce n'est pas une étude utilisateur contrôlée, et Table IV liste 4 lignes où le constructeur gagne |
| 2 | Il manque une figure principale | Fig. 1 = photo du robot exécutant l'interface reconstruite. Fig. 3 = points d'observation et angles morts, qui porte l'argument méthodologique |
| 3 | Problématique insuffisamment développée | §I « Why this is hard » : trois obstacles structurels, chacun avec son mécanisme |
| 4 | Absence de Related Work | §II, six sous-sections, 22 références externes (contre 11), plus Table I de positionnement |
| 5 | Validation expérimentale trop faible | §VI refondue : intervalles de Wilson partout, N déclaré partout, test de Fisher, Fig. 6 |
| 6 | Trop de résultats qualitatifs | La table qualitative de navigation est supprimée ; tout est chiffré ou retiré |
| 7 | Tableaux trop simples | Table I positionnement, Table II pipeline (preuve/hypothèse/critère d'arrêt), Table III mesures avec IC, Table IV comparaison bidirectionnelle |
| 8 | Difficultés sous-exploitées | Mécanisme donné pour chaque hypothèse : §VI-A (H1, H2), §VI-B (H4), §VI-C (H3), §V-C (TTS), §III (IP multiples) |
| 9 | Chatbot peu développé | Retiré du titre. Traité en §V-D, résultats chiffrés en §VI-D (48 essais) |
| 10 | Contributions parfois des implémentations | Trois contributions ; voir §1.1 ci-dessus |
| 11 | Une seule hypothèse formulée | H1–H4 énoncées en §I, résolues en §VI |
| 12 | Style trop orienté développement | Aucun nom de fichier ni de méthode dans la prose. Seul code conservé : le listing `am broadcast`, qui est la contribution elle-même |
| 13 | Le reverse engineering devrait être le cœur | §III + §IV + §VI-A/B/C, soit la majorité de l'article |
| 14 | Comparaison constructeur absente | Table IV |
| 15 | Contribution scientifique centrale à clarifier | Titre, résumé et C1 portent tous la méthodologie ; la plateforme est présentée comme son support de validation |

---

## 3. `Reviewer_Report_CYBEL.md` — faiblesses majeures et questions

| Point | Traitement |
|---|---|
| Contribution scientifique insuffisamment mise en avant | Voir §1.1 et remarque 15 |
| Related Work manquante | §II + Table I |
| Validation expérimentale insuffisante | §VI ; les indicateurs non instrumentés (fiabilité de session) sont **retirés** plutôt qu'affirmés sans preuve |
| Pas de comparaison constructeur | Table IV, avec les lignes défavorables |
| Trop de détails d'implémentation | Voir remarque 12 |
| Le RE devrait dominer | Voir remarque 13 |
| Couche conversationnelle | Retirée du titre, résultats chiffrés conservés |

**Questions des relecteurs :** topics reconstruits → 455 topics, 308 services (§IV) ; durée →
2 semaines phases 1–6, 1 semaine phase 7, 8 sessions (§IV) ; APK analysées → 2 (§IV) ;
généralisation → §VII-B, avec la limite explicite « une seule plateforme » ; parties spécifiques
au constructeur → §VII-B ; choix de rosbridge → §III (c'est l'un des deux seuls canaux
atteignables) ; reproductibilité → artefacts cités en §IV.

---

## 4. Traçabilité et justification des chiffres

### 4.1 Valeurs calculées — toutes re-dérivées

| Valeur | Méthode | Vérifié |
|---|---|---|
| [72,2 ; 100] pour 10/10 | Score de Wilson, z=1,96 | ✅ |
| [43,8 ; 100] pour 3/3 | idem | ✅ |
| [88,6 ; 100] pour 30/30 | idem | ✅ |
| [0 ; 56,2] pour 0/3 | idem | ✅ |
| [42,3 ; 69,3] pour 27/48 | idem | ✅ |
| p = 0,10 | Test exact de Fisher, bilatéral, table 2×2 (3,0 / 0,3) | ✅ |
| Médiane 40,9 s | {40,0 ; 40,9 ; 46,5} | ✅ |
| Médiane 670 s, étendue 668–822 s | {667,6 ; 670,4 ; 822,3} | ✅ |

**Pourquoi Wilson et non l'approximation normale.** L'intervalle de Wald donne [100 % ; 100 %]
pour 3/3, un intervalle de largeur nulle dénué de sens, et des bornes négatives près de zéro.
Wilson reste correct aux proportions extrêmes et à petit effectif, ce qui est notre situation
sur toutes les lignes.

**Pourquoi le test de Fisher.** 3/3 contre 0/3 paraît spectaculaire et ne l'est pas. Sans le
test, l'article affirmerait une différence que six essais ne portent pas. Khi-deux serait invalide
à ces effectifs.

**Pourquoi deux niveaux pour les visites.** 3/3 seul donne [43,8 ; 100], presque inexploitable.
30/30 seul donne [88,6 ; 100] mais surestime, les trajets d'une même visite n'étant pas
indépendants. Donner les deux avec la dépendance énoncée est le maximum défendable.

### 4.2 Valeurs lues dans une source du dépôt

| Valeur | Source |
|---|---|
| Coordonnées 3/3, 40,0/40,9/46,5 s ; annotations 0/3, 150 s | `git show 08bfc34:data/paper_metrics.json` |
| Visites 3/3 ; 667,6/670,4/822,3 s | `data/paper_metrics.json` |
| 30 trajets (9 arrêts résolvables + retour) × 3 | `data/lab_tour.json` × `data/points.json` (`POSTE-MACHINE` absent) |
| 17 commandes : 10 échecs à 600, 7 succès à 602 | `data/navigation_events.json` |
| 27/48 = 56,2 % | `data/faq_repeat_rate.json` |
| TTS 651/923/1555 ms, n=5 | `git show 68812b9:data/paper_metrics.json` |
| 169 tests unitaires | `python -m pytest tests/unit -q` |
| Seuil de localisation 60 % | `backend/config.py:22` |
| Surface cartographiée 1235 m² | Lisible sur la Fig. 5 |

### 4.3 Relevés de campagne sans journal archivé

Vérification faite sur tout l'historique git : **seules les phases `nav`, `tour` et `tts` ont
été enregistrées.** Les phases `teleop` et `rosapi` ne l'ont jamais été.

Concernées : téléopération 10/10, 455 topics, 308 services, latence REST, RTT Wi-Fi, boucle
vocale n=12, 10 déclenchements de mot d'éveil, 2 APK, 2+1 semaines, 8 sessions.

**Traitement appliqué.** §IV restreint désormais l'affirmation de reproductibilité aux résultats
effectivement archivés (navigation, visites, pont vocal, appariement de questions), et précise
que les 455/308 proviennent des journaux de session et non d'un inventaire archivé. Dans la
Table III, les lignes concernées portent un obèle avec la mention explicite en légende. Aucune
valeur n'est retirée, aucune n'est présentée comme archivée alors qu'elle ne l'est pas.

### 4.4 Justification de chaque mesure

La Table III porte une colonne « What it establishes ». Aucune mesure n'y figure sans rôle
argumentatif ; le texte introductif le dit explicitement, et les indicateurs qui n'établissaient
rien ont été retirés (tests unitaires sortis de la table des résultats, uptime Termux supprimé,
fiabilité de session supprimée faute d'instrumentation).

| Mesure | Ce qu'elle sert à établir |
|---|---|
| Téléopération 10/10 | Que la précondition de mode manuel issue de l'APK (H1) est la bonne |
| Visites 3/3 et 30 trajets | Que la séquence de préparation complète fonctionne en service réel |
| Durée de visite | L'enveloppe opérationnelle d'une session visiteur |
| Coordonnées 3/3 / annotations 0/3 | Les deux bras de H3, et la bascule vers H4 |
| 27/48 | Le plafond de l'appariement à vocabulaire fermé — principal résultat négatif |
| TTS n=5 | Le coût du passage par l'IPC du système hôte |
| Latence REST | Que la pile reconstruite n'ajoute pas de délai perceptible |
| RTT Wi-Fi | Pourquoi la télémétrie est throttlée et pourquoi les aller-retours supprimés comptaient |
| 455 / 308 | La taille de l'espace de recherche, qui justifie les critères d'arrêt |
| 2 APK, 2+1 semaines, 8 sessions | Le coût de la méthode — question explicite des relecteurs |
| Boucle vocale n=12 | Ce qui décide qu'un échange ressemble ou non à une conversation |

---

## 5. Anonymisation appliquée

Sur demande de l'auteure, l'article ne nomme ni l'établissement, ni le modèle du robot.

| Élément | Traitement |
|---|---|
| Bloc auteur | Les deux noms seuls, sans affiliation ni adresse |
| Établissement | Supprimé du bloc auteur, des remerciements et de la bibliographie |
| Modèle du robot | Remplacé par « the study platform », introduit en §III comme « a mass-produced indoor reception robot ». §III précise que rien dans la méthode ne dépend du modèle |
| Noms de paquets constructeur | Déjà génériques : « a welcome application and a deployment tool » |
| Fig. 1 (photo) | Bandeau logo, nom de l'établissement à l'écran et QR code floutés ; la légende le signale |
| Fig. 5 (application constructeur) | Vérifiée : ne porte aucune marque identifiable |

Contrôle automatisé : `grep -ni "hestim\|casablanca\|morocco\|ciot\|ty1251\|welcomepatrol\|sentrymove\|cerim" main.tex references.bib` ne renvoie rien.

**Point à confirmer.** ICRA impose la soumission en double aveugle certaines années. Si c'est le
cas pour l'édition 2027, il faudra également retirer les noms d'auteurs et l'URL du dépôt de la
version soumise, puis les rétablir pour la version définitive. À vérifier sur l'appel à
communications avant dépôt.

---

## 6. Reste à fournir avant soumission

1. **Capture propre de l'interface opérateur**, si une septième figure est souhaitée : l'article
   tient en 7 pages sur 8, il reste de la place. La capture existante montre l'interface
   déconnectée, avec la barre d'onglets du navigateur visible.
2. **Validation de l'encadrant** sur les deux écarts de la section 1.

*Résolu :* l'URL du dépôt est désormais dans `references.bib`
(`https://github.com/Claude20022002/Projet-Stage-2026-Cybel`). Le dépôt doit être public, et
contenir les journaux de terrain cités en §IV, pour que l'affirmation de reproductibilité tienne.
