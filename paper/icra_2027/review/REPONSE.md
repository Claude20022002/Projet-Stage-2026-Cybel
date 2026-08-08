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

## 4. Traçabilité des chiffres

Chaque valeur de l'article provient d'un fichier du dépôt ou d'un commit git.

| Valeur | Source |
|---|---|
| Coordonnées 3/3, 40,0/40,9/46,5 s ; POI 0/3, 150 s | `git show 08bfc34:data/paper_metrics.json` |
| Visites 3/3 ; 667,6/670,4/822,3 s | `data/paper_metrics.json` |
| 30 trajets (9 arrêts résolvables + retour) × 3 | `data/lab_tour.json` croisé avec `data/points.json` (`POSTE-MACHINE` absent) |
| 17 commandes : 10 échecs à 600, 7 succès à 602 | `data/navigation_events.json` |
| Question answering 27/48 = 56,2 % | `data/faq_repeat_rate.json` |
| Latence TTS 651/923/1555 ms, N=5 | `git show 68812b9:data/paper_metrics.json` |
| 169 tests unitaires | `python -m pytest tests/unit -q` |
| Surface cartographiée 1235 m² | Lisible sur la Fig. 5 (application constructeur) |
| Seuil de localisation 60 % | `sdk/real_robot.py` (`_localization_min_percent`) |
| 455 topics, 308 services ; 2 APK ; 2+1 semaines ; 8 sessions | Mesures de campagne rapportées par l'auteure |

Intervalles de Wilson et test exact de Fisher recalculés à partir de ces effectifs.

---

## 5. Reste à fournir avant soumission

1. **Adresse e-mail institutionnelle** des deux auteurs — le bloc auteur n'en porte aucune
   actuellement.
2. **URL publique du dépôt** — §IV affirme que les artefacts sont « released with this paper »
   (référence `cybel2026`). Cette affirmation doit être rendue vraie, ou reformulée.
3. **Capture propre de l'interface opérateur**, si une septième figure est souhaitée : l'article
   tient en 7 pages sur 8, il reste de la place. La capture existante montre l'interface
   déconnectée, avec la barre d'onglets du navigateur visible.
4. **Validation de l'encadrant** sur les deux écarts de la section 1.
