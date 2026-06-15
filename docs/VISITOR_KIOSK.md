# Interface visiteur (kiosque) — début d'implémentation

Documentation de la première version de l'**interface visiteur** du robot CYBEL, destinée à être affichée en plein écran sur l'écran tactile de l'upper body Android, et utilisable directement par un visiteur (sans opérateur).

---

## 1. Vue d'ensemble

Contrairement au tableau de bord opérateur (`frontend/`, port `5173`), cette interface (`frontend-kiosk/`, port `5174`) est une **application web séparée**, volontairement minimaliste :

- de gros boutons tactiles pour des **actions de base** (accueil, navigation vers une salle, visite guidée, mode attente, signaler un délai, arrêt) ;
- un écran **« S'informer »** qui affiche une FAQ sur l'établissement et fait répondre le robot à voix haute (TTS) ;
- un bouton **FR / EN** qui bascule toute l'interface (textes affichés et annonces vocales) en anglais.

Elle réutilise le même backend FastAPI (`:8000`) que l'interface opérateur — aucune nouvelle infrastructure serveur n'est nécessaire.

## 2. Démarrage

`python scripts/dev.py` lance désormais trois processus : backend (`:8000`), interface opérateur (`:5173`) et interface visiteur (`:5174`).

Pour un déploiement sur la tablette du robot, ouvrir `http://<adresse-du-poste-backend>:5174` dans un navigateur en mode plein écran/kiosque.

## 3. Actions disponibles

Les actions affichées proviennent de `GET /api/reception/actions` (définies dans `sdk/reception_actions.py`), filtrées pour exclure la catégorie `maintenance` (ex. retour à la pile, réservé à l'opérateur).

Chaque action peut désormais porter des champs optionnels `label_en`, `description_en` et `speech_en` en plus des champs français existants (`label`, `description`, `speech`).

Le kiosque appelle :

```http
POST /api/reception/actions/{action_id}/execute?lang=fr|en
```

Le paramètre `lang` (par défaut `fr`) sélectionne, côté `ReceptionService.execute()`, le texte prononcé par le robot (`speech_en` si disponible et `lang=en`, sinon `speech`). Le comportement de navigation/route reste identique quelle que soit la langue.

## 4. Écran « S'informer » (FAQ)

Le contenu de la FAQ provient de :

```http
GET /api/knowledge/faq
```

qui sert le tableau `faq` de [data/hestim_knowledge_base.json](../data/hestim_knowledge_base.json) — une base de connaissances de démarrage sur HESTIM (présentation, écoles, filières, gouvernance, contact, valeurs...), collectée depuis [hestim.ma](https://www.hestim.ma/) et ses sous-domaines.

Chaque entrée FAQ contient `question_fr` / `question_en` et `reponse_fr` / `reponse_en`. Toucher une question affiche la réponse dans la langue courante et la fait prononcer par le robot via `POST /api/speech/say`.

Ce fichier JSON est aussi le point de départ de la base de connaissances utilisée par le module de questions/réponses vocales développé en parallèle ; sa section `_meta.todo` liste les informations encore à compléter (gouvernance nominative, chiffres clés, e-mail de contact, vie associative).

## 5. Limites connues / suite

- Pas de reconnaissance vocale côté visiteur dans cette première version (uniquement tactile) — le micro opérateur existant (`voice.ts`) n'est pas repris ici.
- La FAQ est statique (lecture du JSON à chaque requête) ; pas encore connectée au module conversationnel en préparation.
- Le bouton FR/EN ne couvre que cette interface visiteur ; le tableau de bord opérateur reste en français.
