# Revue critique de l'article CYBEL

## Impression générale

-   Sujet très original et techniquement ambitieux.
-   Travail de reverse engineering réel, avec une architecture
    cohérente.
-   Le potentiel de publication est élevé, mais plusieurs points
    scientifiques doivent être renforcés.

## Points forts

1.  Sujet original : rétroconception d'un robot Android propriétaire.
2.  Histoire scientifique cohérente (analyse → reconstruction →
    architecture ouverte).
3.  Figures claires et professionnelles.
4.  Méthodologie en sept phases convaincante.
5.  Contributions clairement identifiées.

## Remarques majeures

### 1. Le titre promet plus que ce qui est démontré

-   Les affirmations « replacing the vendor application » ou « match or
    exceed » ne sont pas validées par une comparaison expérimentale.

**À faire :** - Ajouter une comparaison quantitative avec l'application
constructeur.

### 2. Il manque une figure principale

La première figure devrait illustrer le processus complet :

Vendor Robot → Android → Reverse Engineering → ROSBridge → CYBEL →
Chatbot

### 3. La problématique scientifique est insuffisamment développée

-   Expliquer pourquoi le problème est difficile.
-   Montrer les limites des approches existantes.

### 4. Absence d'une section Related Work

Ajouter une revue de littérature sur : - Reverse Engineering Android -
ROSBridge - Service Robotics - Vendor Lock-in - Interoperability - Edge
Robotics - LLM for Robotics

### 5. Validation expérimentale trop faible

Ajouter des mesures quantitatives : - nombre de tests - taux de succès -
temps de réponse - distance parcourue - taux d'échec - latence
ROSBridge - durée du reverse engineering - nombre de topics/services
découverts

### 6. Trop de résultats qualitatifs

Transformer les affirmations en résultats mesurables.

### 7. Tableaux trop simples

Ajouter des tableaux comparatifs riches : - succès navigation - durée -
causes d'échec - temps de récupération

### 8. Les difficultés sont sous-exploitées

Développer : - pourquoi H4 ? - pourquoi ROSBridge répond sans mouvement
? - pourquoi MQTT était une fausse piste ? - pourquoi plusieurs IP ? -
pourquoi TTS est inaccessible ?

### 9. Le chatbot est peu développé

Le titre lui donne beaucoup d'importance mais peu de contenu lui est
consacré.

### 10. Les contributions sont parfois des implémentations

Transformer les réalisations techniques en contributions scientifiques
plus générales.

### 11. Une seule hypothèse est formulée

Définir H1, H2, H3, H4.

### 12. Style parfois trop orienté développement

Remplacer les noms de scripts par des modules conceptuels.

### 13. Le reverse engineering devrait être le cœur de l'article

Lui consacrer une part beaucoup plus importante.

### 14. Comparaison avec l'application constructeur absente

Ajouter un tableau comparatif fonctionnel.

### 15. La contribution scientifique centrale doit être clarifiée

Le véritable sujet est la méthodologie de rétroconception de robots
Android fermés. CYBEL doit devenir la validation expérimentale de cette
méthodologie.

# Évaluation type reviewer

  Critère                       Évaluation
  ----------------------------- ------------
  Originalité                   ⭐⭐⭐⭐⭐
  Difficulté technique          ⭐⭐⭐⭐⭐
  Qualité de rédaction          ⭐⭐⭐⭐☆
  Validation expérimentale      ⭐⭐⭐☆☆
  Positionnement scientifique   ⭐⭐☆☆☆
  Impact potentiel              ⭐⭐⭐⭐☆

## Verdict

-   ICRA : Reject
-   IROS : Borderline Reject
-   ROSCon : Borderline Accept

## Recommandation principale

Recentrer l'article sur la **méthodologie de rétroconception** plutôt
que sur CYBEL. Faire de CYBEL la validation expérimentale de cette
méthodologie, renforcer l'état de l'art, ajouter des comparaisons
quantitatives avec la solution propriétaire et développer davantage les
résultats expérimentaux.
