# Diagrammes Chapitre 4 — export Overleaf

Les fichiers `.mmd` sont les **sources Mermaid** à convertir en PNG pour le dossier `diagrammes/` de votre projet Overleaf.

## Fichiers et figures LaTeX associées

| Fichier source | PNG Overleaf | Référencé dans `chap4.md` |
|----------------|--------------|---------------------------|
| `architecture_generale_cybel.mmd` | `architecture_generale_cybel.png` | Figure architecture générale |
| `architecture_couches.mmd` | `architecture_couches.png` | Figure architecture logicielle (couches) |
| `diagramme_composants.mmd` | `diagramme_composants.png` | Figure composants |
| `diagramme_classes_sdk.mmd` | `diagramme_classes_sdk.png` | Figure classes SDK |
| `cas_utilisation_cybel.mmd` | `cas_utilisation_cybel.png` | Figure cas d'utilisation |
| `sequence_navigation.mmd` | `sequence_navigation.png` | Figure séquence navigation |
| `sequence_tts.mmd` | `sequence_tts.png` | Figure séquence TTS |
| `sequence_telemetry.mmd` | `sequence_telemetry.png` | Figure séquence télémétrie |
| `sequence_kiosk_action.mmd` | `sequence_kiosk_action.png` | Figure séquence kiosque |
| `topologie_reseau.mmd` | `topologie_reseau.png` | Figure topologie réseau |

## Génération des PNG

### Option A — Mermaid Live Editor (rapide)

1. Ouvrir [https://mermaid.live](https://mermaid.live)
2. Coller le contenu d'un fichier `.mmd` (sans les lignes `%%` de commentaire si besoin)
3. **Actions → PNG** → enregistrer dans `diagrammes/` sur Overleaf

### Option B — CLI (si `@mermaid-js/mermaid-cli` installé)

```bash
cd "docs/Sujet de stage/diagrammes"
npx -p @mermaid-js/mermaid-cli mmdc -i architecture_generale_cybel.mmd -o architecture_generale_cybel.png -b white
# Répéter pour chaque .mmd
```

### Option C — Extension VS Code / Cursor

Extension « Mermaid » → export PNG depuis l'aperçu du fichier `.mmd`.

## Cohérence avec le rapport

Ces diagrammes sont alignés sur `rapport_stage_cybel.md` §8.2–8.4, enrichis pour le chapitre 4 :

- **Visiteur** ajouté au diagramme de cas d'utilisation (manquant dans la version initiale du rapport)
- **architecture_generale_cybel** : diagramme de haut niveau absent du dépôt initial
- **Séquences TTS, télémétrie, kiosque** : mentionnées dans le texte du chapitre 4 mais non diagrammées auparavant
- **Termux / cybel_lite** : intégrés dans composants et architecture générale
