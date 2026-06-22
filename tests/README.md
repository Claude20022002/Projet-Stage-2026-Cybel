# Tests Cybel

Tests unitaires par module du projet. Exécution depuis la racine du dépôt :

```bash
pip install -r tests/requirements.txt
python -m pytest tests/ -v
```

## Structure

| Dossier / fichier | Couvre |
|-------------------|--------|
| `unit/test_map_utils.py` | Grille d'occupation, cellules navigables |
| `unit/test_localization.py` | Normalisation du pourcentage de localisation |
| `unit/test_lab_tour.py` | Moteur de visite (ordre nav → parole) |
| `unit/test_navigation_wait.py` | Attente d'arrivée navigation (anti faux positif 603) |
| `unit/test_speech.py` | Estimation durée TTS |

## Mode mock vs robot réel

Ces tests n'ont pas besoin du robot physique ni d'ADB. Pour valider sur le terrain :

1. Backend `ROBOT_MOCK=false`, robot connecté
2. `POST /api/tour/start?lang=fr` depuis le contrôleur
3. Vérifier déplacement puis discours à chaque arrêt
