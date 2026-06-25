# Conception CYBEL — Documentation produit

Ce dossier centralise la documentation de conception du produit **CYBEL** : plateforme web indépendante de commande, supervision et interaction pour le robot de réception mobile **CIOT TY1251D-03195**.

Il s'appuie sur l'audit des applications constructeur (`welcomepatrol`, `sentrymove`) documenté dans [`AUDIT_APK_CONSTRUCTEUR.md`](AUDIT_APK_CONSTRUCTEUR.md).

---

## Point d'entrée agent IA

**Pour reconstruire ou améliorer les interactions robot, commencer par :**

### → [05-backlog.md](05-backlog.md)

Ce fichier est **autonome** : protocoles ROS/MQTT, tâches ordonnées, fichiers à modifier, critères d'acceptation, registre API/ROS, et références APK.

**Ordre de lecture recommandé pour un agent :**
1. [05-backlog.md](05-backlog.md) — implémentation (commencer ici)
2. [AUDIT_APK_CONSTRUCTEUR.md](AUDIT_APK_CONSTRUCTEUR.md) — protocole constructeur détaillé
3. [04-ecart-etat-actuel.md](04-ecart-etat-actuel.md) — ce qui existe déjà dans le code
4. [01-architecture-cible.md](01-architecture-cible.md) — architecture cible
5. [02-cahier-des-charges-fonctionnel.md](02-cahier-des-charges-fonctionnel.md) — exigences métier
6. [03-diagrammes.md](03-diagrammes.md) — flux et composants
7. [06-plan-hybride-sentrymove-kiosk.md](06-plan-hybride-sentrymove-kiosk.md) — option POI (hybrid)

---

## Documents

| # | Fichier | Contenu | Statut |
|---|---------|---------|--------|
| — | [AUDIT_APK_CONSTRUCTEUR.md](AUDIT_APK_CONSTRUCTEUR.md) | Audit rétro-ingénierie APK constructeur | ✅ |
| 1 | [01-architecture-cible.md](01-architecture-cible.md) | Architecture technique cible | ✅ |
| 2 | [02-cahier-des-charges-fonctionnel.md](02-cahier-des-charges-fonctionnel.md) | Cahier des charges fonctionnel | ✅ |
| 3 | [03-diagrammes.md](03-diagrammes.md) | Diagrammes UML | ✅ |
| 4 | [04-ecart-etat-actuel.md](04-ecart-etat-actuel.md) | Écart CYBEL actuel vs constructeur | ✅ |
| 5 | **[05-backlog.md](05-backlog.md)** | **Backlog agent IA — guide d'implémentation** | ✅ |
| 6 | **[06-plan-hybride-sentrymove-kiosk.md](06-plan-hybride-sentrymove-kiosk.md)** | Plan hybride Sentrymove + kiosque POI (branche hybrid) | ✅ |

---

## Documentation projet

Index général : [`../README.md`](../README.md) · Carte : [`../STRUCTURE.md`](../STRUCTURE.md) · Labo : [`../labo/TERRAIN.md`](../labo/TERRAIN.md)

## Stack cible

| Couche | Technologie | État juin 2026 |
|--------|-------------|----------------|
| Frontend opérateur | React (cible) / TS Vite (actuel) | ⚠️ vanilla TS |
| Frontend kiosque | React (cible) / TS Vite (actuel) | ⚠️ partiel |
| Backend | FastAPI | ✅ v0.2.0 |
| Robot — commandes | ROSBridge `10.42.0.1:9090` | ✅ |
| Robot — télémétrie | MQTT `10.42.0.1:1883` | ⚠️ scripts only |
| TTS | ADB → CybelTTSBridge | ✅ |
| Persistance | PostgreSQL | ❌ JSON files |

---

## Couverture actuelle

~**45 %** du périmètre v1 — détail dans [04-ecart-etat-actuel.md](04-ecart-etat-actuel.md).

**Déjà opérationnel :** parler (ADB), se déplacer (téléop + nav), ROSBridge, visite guidée, carte, LiDAR.

**Priorité immédiate (Sprint 1) :** tâches CYB-001 → CYB-006 dans [05-backlog.md](05-backlog.md).

---

## Références projet

- Connexion robot : [`../ROBOT_CONNECTION.md`](../ROBOT_CONNECTION.md)
- Interface web : [`../INTERFACE.md`](../INTERFACE.md)
- TTS : [`../TTS_BRIDGE.md`](../TTS_BRIDGE.md)
- SDK Python : `sdk/`
- Session labo : [`../labo/TERRAIN.md`](../labo/TERRAIN.md)
- APK décompilés (gitignored) : `/welcomepatrol`, `/sentrymove`
