# Lancer une campagne de mesures sur le robot

Comment exécuter `scripts/collect_paper_data.py`, et quoi faire quand la connexion lâche.

Le plan de la campagne du 14/08 (combien d'essais, dans quel ordre, pourquoi) est dans
[../paper/icra_2027/review/COLLECTE.md](../paper/icra_2027/review/COLLECTE.md). Ce document-ci
couvre la mécanique.

---

## 1. Avant toute chose : le wake lock

**C'est la cause la plus probable des coupures observées lors des sessions précédentes.**

Android suspend les processus Termux dès que l'écran s'éteint, ou après quelques minutes
d'inactivité, au titre de l'optimisation de batterie. Le backend cesse alors de répondre, et le
script de collecte voit des délais d'attente qu'il interprète comme une perte de connexion. Rien
n'a planté : le système d'exploitation a gelé le processus.

Le remède est un *wake lock*. Sur la tablette, une fois :

```bash
pkg install termux-api
```

et installer l'application **Termux:API** depuis F-Droid (le paquet seul ne suffit pas, il lui
faut son application compagnon).

`start_cybel.sh` et `start_cybel_test.sh` acquièrent désormais le wake lock automatiquement au
démarrage, et `stop_cybel*.sh` le libèrent. Si `termux-wake-lock` est absent, le backend démarre
quand même mais affiche un avertissement — **ne l'ignorez pas avant une campagne de deux heures.**

À vérifier également sur la tablette :

- Paramètres → Batterie → l'application Termux en **« non optimisée »** ou « sans restriction »
- Paramètres → Wi-Fi → avancé → **garder le Wi-Fi actif en veille**
- Écran verrouillé mais **allumé** pendant la session, ou délai de mise en veille au maximum
- Tablette **sur secteur** : deux heures de visites vident une batterie

Contrôle rapide, une fois le backend lancé :

```bash
adb shell "curl -sf http://127.0.0.1:8001/api/health"
```

---

## 2. Les dix visites avec le script existant

Oui, le script gère les dix visites. Le nombre d'essais est un paramètre :

```bash
python scripts/collect_paper_data.py --host 192.168.20.22 --phase tour --tour-trials 10
```

Le script **s'arrête entre chaque essai** et attend une pression sur ENTRÉE, pour vous laisser
repositionner le robot. Avant chaque visite il vérifie la localisation pendant 45 s, et si le
robot n'est pas localisé il vous demande de relocaliser depuis la tablette plutôt que d'enchaîner
sur un essai voué à l'échec.

Comptez environ 130 minutes pour dix visites.

### Les résultats sont maintenant sauvegardés au fur et à mesure

`data/paper_metrics.json` est réécrit **après chaque essai**, pas seulement à la fin. Une
interruption au huitième essai conserve les sept précédents. Le fichier porte alors
`tour_trials_done` face à `tour_trials`, ce qui indique où la campagne s'est arrêtée.

`save_partial()` fusionne dans le fichier existant au lieu de l'écraser : les phases lancées
séparément se cumulent. En revanche, deux exécutions de la **même** phase se remplacent — d'où
la sauvegarde manuelle recommandée ci-dessous.

### Abandon d'un essai devenu sans espoir

Si le backend devient injoignable pendant neuf sondages consécutifs, soit trois minutes, l'essai
est abandonné et le script passe au suivant. Auparavant il attendait le délai complet de soixante
minutes. Le message d'abandon rappelle de vérifier le wake lock, parce que c'est presque toujours
la cause.

---

## 3. Ordre recommandé et sauvegardes

Les phases courtes d'abord : si la session tourne court, l'essentiel est acquis.

```bash
# 1) inventaire protocolaire (quelques secondes)
python scripts/collect_paper_data.py --host 192.168.20.22 --phase rosapi
cp data/paper_metrics.json data/paper_metrics_rosapi.json

# 2) téléopération, 10 essais (~2 min)
python scripts/collect_paper_data.py --host 192.168.20.22 --phase teleop --teleop-trials 10
cp data/paper_metrics.json data/paper_metrics_teleop.json

# 3) comparaison de banc, 10 essais par bras (~35 min) — LA mesure critique
python scripts/collect_paper_data.py --host 192.168.20.22 --phase nav --nav-trials 10
cp data/paper_metrics.json data/paper_metrics_nav.json

# 4) pont vocal, 10 essais (~2 min)
python scripts/collect_paper_data.py --phase tts --tts-trials 10 --adb-serial <IP>:5555
cp data/paper_metrics.json data/paper_metrics_tts.json

# 5) visites guidées, 10 essais (~130 min) — en dernier
python scripts/collect_paper_data.py --host 192.168.20.22 --phase tour --tour-trials 10
cp data/paper_metrics.json data/paper_metrics_tour.json
```

Puis les journaux vocaux, qui vivent sur la tablette et **ne sont pas récupérés
automatiquement** — c'est pour les avoir oubliés la dernière fois que l'anomalie à 23 secondes
reste inexpliquée :

```bash
adb pull /data/data/com.termux/files/home/cybel-test/data/logs/voice data/logs/voice
python scripts/measure_voice_latency.py
```

---

## 4. Quel `--host` utiliser

Deux chemins mènent au robot, et ils ne servent pas la même chose.

| Adresse | Ce qu'elle atteint | Quand l'utiliser |
|---|---|---|
| `192.168.20.22` | le châssis ROS par le lien Ethernet interne | phases `rosapi`, `teleop`, `nav` |
| `10.42.0.1` | le châssis via le point d'accès du robot | si le PC est sur le Wi-Fi du robot |
| `--backend-host` | le backend HTTP sur la tablette | phase `tour`, si la résolution automatique échoue |

La phase `tour` ne passe pas par rosbridge mais par l'API HTTP du backend Termux. Si `--host`
pointe le châssis, le script le signale et cherche le backend ailleurs. En cas d'échec :

```bash
python scripts/collect_paper_data.py --phase tour --tour-trials 10 \
    --host 192.168.20.22 --backend-host localhost --backend-port 8001
```

(`localhost` fonctionne parce que le port est redirigé par ADB.)

---

## 5. Diagnostic

| Symptôme | Cause probable | Remède |
|---|---|---|
| Coupures après quelques minutes, surtout écran éteint | Termux suspendu par Android | Wake lock, §1 |
| `Backend CYBEL injoignable` au démarrage | backend arrêté, ou mauvais port | `bash scripts/termux/start_cybel_test.sh`, vérifier 8001 contre 8000 |
| `[WARN] Statut illisible` par intermittence | Wi-Fi instable | Sans gravité : le script tolère 3 min avant d'abandonner |
| `Impossible de se connecter` sur rosbridge | mauvais `--host`, ou robot éteint | Essayer les deux adresses du §4 |
| Robot non localisé à chaque essai | carte perdue, ou dérive | Relocaliser depuis la tablette, attendre ≥ 60 % |
| Visite qui démarre puis reste bloquée | POI absent de la carte | Vérifier que les POI du parcours existent dans l'application constructeur |

Journal du backend, sur la tablette : `~/cybel-test-uvicorn.log`.

---

## 6. Après la campagne

```bash
python paper/icra_2027/tools/stats.py     # recalcule tous les intervalles
```

Puis reportez les valeurs dans `tables/tab-metrics.tex` **et** `figures/fig-results.tex` — la
figure prend des écarts, pas des bornes — et suivez la liste de reprise en fin de
[COLLECTE.md](../paper/icra_2027/review/COLLECTE.md).
