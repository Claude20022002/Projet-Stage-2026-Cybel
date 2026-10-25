# Retrait du code temporaire — Semaine d'intégration HESTIM (Ghandi)

> Procédure de nettoyage après la semaine d'intégration. Tout le code ajouté pour
> l'événement porte le marqueur **`TEMPORAIRE-INTEGRATION-2026`**. Ce document est la
> checklist de suppression complète ; la procédure d'exploitation reste dans
> [JOURNEE_INTEGRATION.md](JOURNEE_INTEGRATION.md).

**À faire quand :** une fois la semaine d'intégration terminée, avant de rebrancher le robot
sur sa configuration labo habituelle.

---

## 0. Localiser tout le code temporaire

```bash
git grep -n "TEMPORAIRE-INTEGRATION-2026"
```

Au moment de la rédaction, le marqueur apparaît dans :

| Fichier | Nature |
|---|---|
| `sdk/integration_event.py` | **Fichier entier** — moteur de circulation |
| `tests/unit/test_integration_event.py` | **Fichier entier** — 16 tests du moteur |
| `frontend-kiosk/src/staffPanel.ts` | **Fichier entier** — panneau staff |
| `frontend-kiosk/src/staffPanel.css` | **Fichier entier** — style du panneau |
| `frontend-kiosk/src/app.ts` | Import + appel `initStaffPanel()` (lignes marquées) |
| `scripts/termux/cybel_lite.py` | Bloc délimité + routes `/api/event/*` + filtrage `staff_pin` |
| `scripts/circulation.py` | **Fichier entier** — circulation de secours depuis le PC |
| `scripts/deploy_event.sh` | **Fichier entier** — déploiement / restauration |
| `data/kiosk_config.ghandi.json` | **Fichier entier** — config de l'événement |
| `frontend-kiosk/public/event/` | **Dossier entier** — visuels des deux écrans |

---

## 1. Sur le robot — revenir à la configuration labo

Robot branché en USB, depuis le PC :

```bash
bash scripts/deploy_event.sh --restore     # restaure kiosk_config.before_event.json (config labo)
```

Puis, si l'écran du dessous n'est plus utilisé :

```bash
adb uninstall com.cybel.secondscreen
```

> `--restore` remet la config labo sauvegardée une fois sur la tablette dans
> `kiosk_config.before_event.json` et libère l'écran du dessous. Vérifier ensuite que
> CYBEL Accueil s'ouvre en mode kiosque normal (pas en mode événement).

---

## 2. Supprimer les fichiers entièrement dédiés

```bash
git rm sdk/integration_event.py \
       tests/unit/test_integration_event.py \
       frontend-kiosk/src/staffPanel.ts \
       frontend-kiosk/src/staffPanel.css \
       scripts/deploy_event.sh \
       scripts/circulation.py \
       data/kiosk_config.ghandi.json
git rm -r frontend-kiosk/public/event/
```

---

## 3. `frontend-kiosk/src/app.ts`

Retirer l'import et l'appel marqués `TEMPORAIRE-INTEGRATION-2026` :

- l'import de `initStaffPanel` (près de la ligne 13) ;
- l'appel `initStaffPanel()` et son bloc d'initialisation isolé (près de la ligne 870).

---

## 4. `scripts/termux/cybel_lite.py`

4 éléments à retirer :

1. Le **bloc principal** entre `# TEMPORAIRE-INTEGRATION-2026` (≈ l. 1771) et
   `# ---- FIN TEMPORAIRE-INTEGRATION-2026 ----` (≈ l. 2084).
2. Toutes les **routes `/api/event/*`** (circulation, mode, annonces).
3. La constante **`INTEGRATION_EVENT_MODULE`** et l'import marqué (≈ l. 39).
4. Le **filtrage de `staff_pin`** dans `kiosk_config_get` (≈ l. 1729 — le PIN ne doit jamais
   sortir du backend ; une fois l'événement retiré, il n'y a plus de PIN dans la config labo).
5. Le **démarrage automatique des annonces** dans `_lifespan` (si `announce_autostart`).

> Après édition : `git grep -n "TEMPORAIRE-INTEGRATION-2026" scripts/termux/cybel_lite.py`
> ne doit plus rien renvoyer, et `git grep -n "/api/event" scripts/termux/cybel_lite.py`
> non plus.

---

## 5. (Optionnel) Ce qui peut être conservé pour un futur événement

Réutilisables tels quels, sans rien de spécifique à Ghandi :

- le **mode événement** du kiosque (`event` dans `frontend-kiosk/src/types.ts`,
  `src/screens/home.ts`, `src/style.css`) ;
- l'app **`CybelSecondScreen`** (`android/CybelSecondScreen/`).

Les garder évite de tout reconstruire pour le prochain salon. Si on les retire aussi, enlever
le champ `event` de `types.ts` et les branches qui le lisent.

---

## 6. Documentation et changelog

- Déplacer / archiver [JOURNEE_INTEGRATION.md](JOURNEE_INTEGRATION.md) et ce fichier
  (ou les laisser dans `docs/archive/` comme trace de l'événement).
- Retirer les lignes d'index pointant vers eux dans [../README.md](../README.md).
- Ajouter une entrée au [CHANGELOG.md](../../CHANGELOG.md) : « retrait du code temporaire de
  la semaine d'intégration ».

---

## 7. Vérification finale

```bash
# plus aucun marqueur
git grep -n "TEMPORAIRE-INTEGRATION-2026"      # -> aucun résultat

# le kiosque compile toujours
cd frontend-kiosk && npm run build && cd ..

# les tests passent (test_integration_event.py doit avoir disparu)
python -m pytest tests/unit -q

# le backend Termux démarre sans les routes event
python -c "import ast; ast.parse(open('scripts/termux/cybel_lite.py', encoding='utf-8').read())"
```

Puis redéployer la configuration labo sur le robot comme d'habitude
(voir [DEMARRAGE_ET_DEPANNAGE.md](DEMARRAGE_ET_DEPANNAGE.md)).

---

## Résumé en une phrase

`--restore` sur le robot → `git rm` des 7 fichiers + dossier `event/` → nettoyer `app.ts` et
`cybel_lite.py` → `git grep` doit être vide → `npm run build` + `pytest` → redéployer.
