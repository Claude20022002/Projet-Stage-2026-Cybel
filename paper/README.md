# Dossier article scientifique — CYBEL

Articles et supports pour publication académique (robotique de service, rétro-ingénierie, HRI).

## Fichiers

| Fichier | Description |
|---------|-------------|
| **[icra_2027/](icra_2027/)** | **LaTeX IEEE 8 pages — cible actuelle : IEEE ICRA 2027 (Séoul)** |
| [article_cybel_retroconception.md](article_cybel_retroconception.md) | Brouillon markdown (juin 2026) — supplanté par `icra_2027/`, conservé pour historique |
| [references.bib](references.bib) | Bibliographie BibTeX (brouillon markdown ; `icra_2027/references.bib` est la version à jour) |
| [exemple/wincom_paper.pdf](exemple/wincom_paper.pdf) | Article HESTIM (WINCOM/IEEE) utilisé comme référence de style (titre concis, hedging des affirmations) |

## IEEE ICRA 2027 (LaTeX, cible actuelle)

**Conférence :** 2027 IEEE International Conference on Robotics and Automation, Coex Convention & Exhibition Center, Séoul, Corée du Sud.
**Format confirmé le 2026-07-19** (<https://2027.ieee-icra.org/contribute/>) : 8 pages tout compris (références incluses), soumission via PaperPlaza.
**Deadline de soumission initiale :** 2026-09-15, 23:59 PST.

```bash
cd paper/icra_2027
make
```

Voir [icra_2027/README.md](icra_2027/README.md).

## Angle de l'article

**Titre actuel :** *A Reverse-Engineered Open Architecture for Closed Service Robots with Voice and Face Interaction*

**Cas d'étude :** CIOT TY1251D-03195, projet CYBEL (HESTIM).

**Contributions scientifiques :**
1. Méthodologie RE non destructive (7 phases), quatre hypothèses falsifiables H1–H4
2. Reconstruction protocole rosbridge validée terrain (téléop, navigation, télémétrie)
3. Architecture edge mock/réel + kiosque Termux autonome
4. Pont TTS Android quand ROS/HTTP échouent
5. Interface vocale hors-ligne (vocabulaire fermé, mot d'éveil, dialogue proactif) et reconnaissance faciale sur device — **validées terrain de bout en bout**
6. Correction de réactivité navigation (court-circuit d'appels ROS redondants)
7. Navigation hybride POI Sentrymove

## Pistes de conférences / revues

| Piste | Track suggéré | Statut |
|-------|---------------|--------|
| **IEEE ICRA 2027** | Toutes thématiques robotique | **Ciblée — deadline 2026-09-15** |
| CFP CITS | Track II (IT/HCI) ou Track I (Embedded) | Piste de repli |
| RO-MAN | Human-robot interaction, service robots | Piste de repli |
| Revue | JRSI, Robotics and Autonomous Systems (short paper) | Piste de repli |

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
