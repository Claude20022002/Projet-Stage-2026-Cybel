# Dossier article scientifique — CYBEL

Articles et supports pour publication académique (robotique de service, rétro-ingénierie, HRI).

## Fichiers

| Fichier | Description |
|---------|-------------|
| [article_cybel_retroconception.md](article_cybel_retroconception.md) | Article complet (FR + abstract EN) |
| [references.bib](references.bib) | Bibliographie BibTeX |
| **[roscon_korea_2027/](roscon_korea_2027/)** | **LaTeX IEEE 8 pages (ROSCon Korea 2027)** |

## ROSCon Korea 2027 (LaTeX)

```bash
cd paper/roscon_korea_2027
make
```

Voir [roscon_korea_2027/README.md](roscon_korea_2027/README.md).

## Angle de l'article

**Titre proposé :** *Rétro-conception d'un robot de service Android fermé : intégration rosbridge et couche conversationnelle ouverte sans support constructeur*

**Cas d'étude :** CIOT TY1251D-03195, projet CYBEL (HESTIM).

**Contributions scientifiques :**
1. Méthodologie RE non destructive (7 phases)
2. Reconstruction protocole rosbridge validée terrain
3. Architecture edge mock/réel + kiosque Termux autonome
4. Pont TTS Android quand ROS/HTTP échouent
5. Couche conversationnelle ouverte (FAQ → extensible LLM)
6. Navigation hybride POI Sentrymove

## Pistes de conférences / revues

| Piste | Track suggéré |
|-------|---------------|
| CFP CITS | Track II (IT/HCI) ou Track I (Embedded) |
| RO-MAN | Human-robot interaction, service robots |
| IROS/ICRA Workshop | Open-source robotics, reverse engineering |
| Revue | JRSI, Robotics and Autonomous Systems (short paper) |

## Diagrammes sources (repo)

- `docs/Sujet de stage/diagrammes/architecture_generale_cybel.mmd`
- `docs/Sujet de stage/diagrammes/architecture_couches.mmd`
- `docs/ARCHITECTURE_LOGICIELLE.md` (Mermaid §2.1–2.2, §9.9)

## Conversion LaTeX

```bash
pandoc paper/article_cybel_retroconception.md -o paper/article_cybel.tex --bibliography=paper/references.bib
```

## Documents projet associés

- [ARCHITECTURE_LOGICIELLE.md](../docs/ARCHITECTURE_LOGICIELLE.md)
- [TTS_BRIDGE.md](../docs/TTS_BRIDGE.md)
- [CYBEL_GAP_ANALYSIS.md](../docs/movement-audit/CYBEL_GAP_ANALYSIS.md)
- [rapport_stage_cybel.md](../docs/Sujet%20de%20stage/rapport_stage_cybel.md)
