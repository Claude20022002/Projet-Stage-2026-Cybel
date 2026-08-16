# Campagne de mesures — runbook

Objectif : répondre à la remarque 5 de l'encadrant (atteindre p < 0,05 sur la comparaison de
banc) et, tant qu'on a le robot, archiver les mesures qui ne l'avaient jamais été.

Durée estimée : **~2 h 50** au total. Les visites guidées représentent à elles seules 130 min ;
tout le reste tient en 40 min.

---

## 1. Combien d'essais faut-il vraiment ?

Test exact de Fisher, bilatéral, en supposant que la séparation reste parfaite (un bras réussit
tout, l'autre échoue tout) :

| essais / bras | p | verdict |
|---|---|---|
| 3 (actuel) | 0,100 | non significatif |
| **4** | **0,029** | **p < 0,05 atteint** |
| 5 | 0,008 | |
| 6 | 0,002 | |
| 10 | < 0,001 | confortable |

**Quatre essais par bras suffisent** si la séparation est nette. Mais elle peut ne pas l'être, et
dans ce cas la marge disparaît vite :

| coordonnées | annotations | p (n = 10 / bras) |
|---|---|---|
| 10/10 | 0/10 | < 0,001 |
| 9/10 | 2/10 | 0,006 |
| 8/10 | 2/10 | 0,023 |
| 8/10 | 3/10 | **0,070 — échoue** |

**Recommandation : 10 essais par bras.** C'est le seul réglage qui tienne encore si deux ou trois
essais partent de travers, ce qui est le cas normal sur le terrain.

---

## 2. Ce que la campagne apporterait

| Mesure | Aujourd'hui | Après 10 essais |
|---|---|---|
| Visites complétées | 3/3, IC95 [43,8 – 100] | 10/10, IC95 [72,2 – 100] |
| Trajets individuels | 30/30, IC95 [88,6 – 100] | 100/100, IC95 [96,3 – 100] |
| Coordonnées, banc | 3/3, IC95 [43,8 – 100] | 10/10, IC95 [72,2 – 100] |
| Comparaison de banc | p = 0,10 | p < 0,001 attendu |

Trois indicateurs de la Table III portent aujourd'hui un obèle parce qu'aucun journal n'a été
archivé. Les phases `rosapi` et `teleop` ci-dessous les suppriment, ce qui vaut la peine puisque
le robot est disponible.

---

## 3. Ordre d'exécution

Faire les phases courtes d'abord : si la session est écourtée, on garde l'essentiel.

```bash
# 0) verifier la liaison
python scripts/collect_paper_data.py --host 192.168.20.22 --phase rosapi

# 1) inventaire protocolaire — archive enfin les 455 topics / 308 services
python scripts/collect_paper_data.py --host 192.168.20.22 --phase rosapi

# 2) teleoperation, 10 essais — supprime un obele de la Table III
python scripts/collect_paper_data.py --host 192.168.20.22 --phase teleop --teleop-trials 10

# 3) LA MESURE CRITIQUE : comparaison de banc, 10 essais par bras
python scripts/collect_paper_data.py --host 192.168.20.22 --phase nav --nav-trials 10

# 4) pont vocal, 10 essais
python scripts/collect_paper_data.py --phase tts --tts-trials 10 --adb-serial <IP>:5555

# 5) visites guidees, 10 tours  (~130 min — lancer en dernier)
python scripts/collect_paper_data.py --host 192.168.20.22 --phase tour --tour-trials 10
```

`data/paper_metrics.json` est **écrasé à chaque phase**. Sauvegarder entre deux phases :

```bash
cp data/paper_metrics.json data/paper_metrics_<phase>_$(date +%Y%m%d).json
```

Puis récupérer les journaux vocaux de la tablette :

```bash
adb pull /data/data/com.termux/files/home/cybel-test/data/logs/voice data/logs/voice
python scripts/measure_voice_latency.py
```

---

## 4. Points de vigilance

**Avant la phase `nav`.** Les préconditions doivent être satisfaites, sinon les deux bras
échouent et la mesure ne vaut rien : robot localisé au-dessus de 60 %, mode automatique actif,
POI synchronisés depuis l'application constructeur, carte `laboV2` chargée. La cible par défaut
est le premier POI éligible de `data/points.json`.

**Pendant la phase `nav`.** Noter à la main tout essai perturbé par une cause extérieure — un
passant, une porte fermée, une batterie faible. Un échec dont on connaît la cause externe doit
être déclaré comme tel dans l'article, pas dilué dans le taux.

**Sur la latence vocale.** L'aberration à 23 s de juillet n'est pas diagnosticable après coup :
les journaux bruts vivaient sur la tablette et n'ont pas été récupérés. `measure_voice_latency.py`
ventile désormais la latence **par type d'échange**. L'hypothèse à vérifier est qu'un échange de
type `navigation` inclut toute la séquence de préparation, relocalisation comprise, alors qu'un
échange `faq` ne fait qu'un appariement local. Ce sont deux grandeurs différentes, et les agréger
produit une distribution bimodale dont ni la moyenne ni l'étendue ne veulent dire grand-chose.

Pour trancher, provoquer volontairement pendant la session **au moins 5 échanges de chaque
type** : questions FAQ pures, et commandes de navigation vocale. Si l'hypothèse tient, la Table III
rapportera les deux séparément et la note demandée par l'encadrant s'écrira toute seule.

**Nombre de trajets par visite.** Il est de 10 aujourd'hui : 9 arrêts résolvables plus le retour
borne, `POSTE-MACHINE` étant absent de `points.json`. Si ce POI est recréé dans l'application
constructeur avant la campagne, il passera à 11 et il faudra ajuster le décompte des trajets dans
l'article.

---

## 5. Après la campagne

1. `python paper/icra_2027/tools/stats.py` après avoir mis à jour les effectifs dans le script.
2. Reporter les valeurs dans `tables/tab-metrics.tex` **et** `figures/fig-results.tex` — la figure
   prend des écarts, pas des bornes.
3. Mettre à jour le texte de §VI-C : le `p = 0.10` et la phrase « la différence n'est pas
   statistiquement significative » deviennent caducs si p passe sous 0,05.
4. Retirer les obèles de la Table III pour les indicateurs désormais archivés, et alléger en
   conséquence le paragraphe de §IV-C sur les relevés non archivés.
5. Ajouter la note sur la latence vocale demandée par l'encadrant.
6. Mettre à jour la section 4 de `REPONSE.md` (traçabilité).
7. `.\build.ps1 check` — le budget est à 8/8, donc toute phrase ajoutée doit en remplacer une autre.
