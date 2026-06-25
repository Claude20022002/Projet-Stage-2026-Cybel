# Architecture de la documentation CYBEL

Ce document décrit l'organisation du dossier `docs/` : rôles, conventions et règles de maintenance.

---

## Principes

1. **Un seul index** — [README.md](README.md) est le point d'entrée GitHub.
2. **Guides opérationnels** séparés de la **conception produit** et du **rapport académique**.
3. **Pas de duplication** — les guides longs restent dans un fichier ; les README de section ne font que indexer et orienter.
4. **Liens relatifs** — préférer `../robot/ROBOT_CONNECTION.md` aux chemins absolus.
5. **Archive explicite** — documents constructeur et brouillons IA dans [archive/](archive/), pas mélangés aux guides actifs.

---

## Arborescence cible

```
docs/
├── README.md                 # Index principal (GitHub)
├── STRUCTURE.md              # Ce fichier
│
├── guides/                   # How-to : dev, smoke test, prompts
│   ├── README.md
│   ├── DEMARRAGE-RAPIDE.md
│   └── PHASE0_DEMARRAGE.md   # (lien ou copie — voir ci-dessous)
│
├── labo/                     # Terrain : robot physique, validation
│   ├── README.md
│   ├── TERRAIN.md            # Procédure labo + commandes
│   └── KIOSK_AB_COMPARISON.md # Comparaison coords vs POI (hybrid)
│
├── kiosque/                  # Interface visiteur + Termux
│   ├── README.md
│   ├── VISITOR_KIOSK.md      # → fichiers à la racine docs/ (compat)
│   ├── TERMUX_DEPLOY.md
│   ├── TOUR_NAVIGATION.md
│   └── TTS_BRIDGE.md
│
├── robot/                    # Protocole, réseau, audit mouvement
│   ├── README.md
│   ├── ROBOT_CONNECTION.md
│   └── movement-audit/
│
├── cybel-conception/         # Produit : CDC, backlog, plans
│   ├── README.md
│   ├── 01 … 05 …
│   ├── 06-plan-hybride-sentrymove-kiosk.md
│   └── AUDIT_APK_CONSTRUCTEUR.md
│
├── stage/                    # Rapport HESTIM (redirect)
│   └── README.md
│
├── archive/                  # Non opérationnel : constructeur, idées IA
│   └── README.md
│
└── [racine docs/ — compat]   # Fichiers historiques conservés
    ├── INTERFACE.md
    ├── PHASE0_DEMARRAGE.md
    ├── VISITOR_KIOSK.md
    └── …
```

---

## Compatibilité (fichiers à la racine `docs/`)

Les fichiers suivants restent à **`docs/*.md`** pour ne pas casser les liens existants (README racine, commits, bookmarks). Chaque section `docs/<theme>/README.md` pointe vers eux.

| Fichier racine | Section logique |
|----------------|-----------------|
| `INTERFACE.md` | guides / opérateur |
| `PHASE0_DEMARRAGE.md` | guides / labo |
| `ROBOT_CONNECTION.md` | robot |
| `VISITOR_KIOSK.md` | kiosque |
| `TERMUX_DEPLOY.md` | kiosque |
| `TOUR_NAVIGATION.md` | kiosque |
| `TTS_BRIDGE.md` | kiosque |
| `PROMPT_CLAUDE_KIOSK_TABLETTE.md` | guides |

**Migration future** (optionnelle) : déplacer physiquement les fichiers dans les sous-dossiers et laisser un stub redirect de 5 lignes à l'ancien emplacement.

---

## Public cible par section

| Section | Lecteur | Fréquence de mise à jour |
|---------|---------|--------------------------|
| `guides/` | Développeur | À chaque changement de stack / dev.py |
| `labo/` | Stagiaire / opérateur terrain | Avant chaque session robot |
| `kiosque/` | Dev frontend + déploiement Termux | À chaque release kiosque / APK |
| `robot/` | Dev SDK, reverse engineering | Après découverte protocole |
| `cybel-conception/` | Architecte, agent IA | Sprint / décision produit |
| `stage/` | Encadrant académique | Fin de stage |
| `archive/` | Référence | Rarement |

---

## Ajouter un nouveau document

1. Choisir la section (`guides`, `labo`, `kiosque`, `robot`, `cybel-conception`).
2. Créer le fichier en **français**, titres en sentence case ou titre FR.
3. Ajouter une ligne dans le `README.md` de la section.
4. Ajouter une entrée dans [docs/README.md](README.md) si le doc est majeur.
5. Lier depuis le code (`scripts/*.py` docstring) si le script est l'entrée opérationnelle.

---

## Documents hors périmètre `docs/`

| Emplacement | Rôle |
|-------------|------|
| `README.md` (racine) | Protocole ROS détaillé + vue projet — reste la référence technique rapide |
| `PARITY_CHECKLIST.md` | Suivi parité WelcomePatrol |
| `tests/README.md` | Tests automatisés |
| `sentrymove/` | Code source APK constructeur (référence JADX) |

---

## Maintenance

- **Après session labo** : mettre à jour [labo/TERRAIN.md](labo/TERRAIN.md) (symptômes, IPs, commandes validées).
- **Après merge hybrid → main** : fusionner les sections POI dans `labo/` et retirer les mentions « branche expérimentale ».
- **Avant release** : vérifier que `docs/README.md` et les README de section n'ont pas de liens morts.
