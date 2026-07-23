# Démarrer le kiosque visiteur — guide simple (contrôleur)

> **Pour qui ?** Contrôleur / technicien labo HESTIM, **sans être développeur**.  
> **Application :** CYBEL Accueil **TEST** (`CybelVisitorKioskTest`) — port **8001**.  
> **Guide POI détaillé :** [GUIDE_CONTROLEUR_POI.md](GUIDE_CONTROLEUR_POI.md) (noms, parcours, sync).

---

## En résumé

| Situation | Commande à lancer |
|-----------|-------------------|
| **Lundi matin / avant une démo** | `.\scripts\kiosk_test.ps1 demarrer` |
| L'app affiche une erreur backend | `.\scripts\kiosk_test.ps1 redemarrer` |
| Ça ne marche toujours pas | `.\scripts\kiosk_test.ps1 reparer` puis `demarrer` |
| Voir ce qui se passe | `.\scripts\kiosk_test.ps1 logs` |
| Juste vérifier l'état | `.\scripts\kiosk_test.ps1 status` |

**Prérequis :** PC Windows, câble USB tablette↔PC, projet CYBEL ouvert dans PowerShell :

```powershell
cd C:\Users\clusa\Desktop\cybel
```

---

## Checklist avant de commencer (1 minute)

Cochez mentalement — pas besoin de tout comprendre :

- [ ] Robot **allumé** (voyants OK, pas d'arrêt d'urgence enfoncé)
- [ ] Tablette **allumée** et **déverrouillée**
- [ ] Câble **USB** branché entre tablette et PC
- [ ] Sur la tablette : message « Autoriser le débogage USB » → **Autoriser**

Si une case manque, le script affichera « Aucune tablette détectée » — c'est normal, corrigez d'abord le câble.

---

## Procédure normale — chaque session

### Étape unique (recommandée)

```powershell
.\scripts\kiosk_test.ps1 demarrer
```

Le script fait tout seul :

1. Vérifie que la tablette est connectée
2. Démarre le **backend** (le « moteur » web sur la tablette, port 8001)
3. Lance l'**application** CYBEL Accueil TEST

**Résultat attendu :** l'écran d'accueil visiteur s'affiche sur la tablette.

---

## Si quelque chose ne va pas — restez calme

Suivez **une étape à la fois**. Ne copiez pas de longues commandes `adb` à la main — utilisez le script.

```
L'app ne s'ouvre pas ou écran blanc ?
        │
        ▼
   .\scripts\kiosk_test.ps1 redemarrer
        │
        ├─ OK → relancer l'app : .\scripts\kiosk_test.ps1 lancer
        │
        └─ Toujours KO ?
                │
                ▼
           .\scripts\kiosk_test.ps1 reparer
                │
                ▼
           .\scripts\kiosk_test.ps1 demarrer
                │
                └─ Toujours KO ?
                        │
                        ▼
                   .\scripts\kiosk_test.ps1 logs
                   → envoyer la sortie au référent technique
```

---

## Messages d'erreur fréquents (et quoi faire)

| Ce que vous voyez | Ce que ça veut dire | Action |
|-------------------|---------------------|--------|
| « Backend ne répond pas » / écran d'erreur dans l'app | Le moteur web (port 8001) est arrêté | `.\scripts\kiosk_test.ps1 redemarrer` |
| `No module named 'uvicorn'` (dans les logs) | Dépendances Python manquantes sur la tablette | `.\scripts\kiosk_test.ps1 reparer` |
| `tar: exec gunzip: No such file or directory` | Mauvaise commande de déploiement (tar Android) | **Ne pas** utiliser `su -c tar xzf` — voir § déploiement ci-dessous |
| `Error: Argument expected after "--es"` | Commande `adb` coupée en deux dans PowerShell | Utiliser `kiosk_test.ps1` à la place |
| « Synchronisation POI impossible » | Robot éteint ou pas joignable | Allumer le robot, vérifier Sentrymove |
| « Point inconnu » pendant la visite | Nom POI différent entre robot et CYBEL | Voir [GUIDE_CONTROLEUR_POI.md](GUIDE_CONTROLEUR_POI.md) §1 et §7 |
| Aucune tablette ADB | USB ou autorisation débogage | Rebrancher câble, accepter débogage USB |
| Le robot ne bouge pas après "aller à…"/"visite guidée"/"stop" alors que l'app dit que ça a marché | `nav_status` bloqué sur un code inhabituel (600 après redémarrage backend, ou autre) — le robot n'exécute pas alors que le service ROS répond "succès" | **Ouvrir l'app constructeur Deployment Tool** et relocaliser/déplacer manuellement depuis là — méthode fiable confirmée en direct le 2026-07-23, plus sûre que de réessayer depuis l'app CYBEL |
| Le kiosque affiche encore l'ancienne interface après une mise à jour | La WebView garde l'ancien code en mémoire ; pousser `dist/` ne suffit pas | Forcer l'arrêt et relancer l'app (`am force-stop com.cybel.visitorkiosk.test` puis relancer), pas juste redémarrer le backend |
| `adb forward` ne répond plus après avoir débranché/rebranché l'USB | Le tunnel ne survit pas à une reconnexion USB | Relancer `adb forward tcp:18001 tcp:8001` (le script `kiosk_test.ps1` le refait automatiquement) |

---

## Les adresses IP — ne pas paniquer si ça change

Le réseau labo attribue des adresses **automatiquement (DHCP)**. C'est **normal** que l'IP change.

| Adresse | C'est quoi ? | À retenir |
|---------|--------------|-----------|
| `172.16.0.xxx` | **Tablette** sur le Wi-Fi labo | Change souvent — pour SSH depuis le PC |
| `192.168.20.22` | **Robot** vu depuis la tablette (lien interne) | **Fixe** — ne pas remplacer par l'IP Wi-Fi |
| `10.42.0.1` | Hotspot du robot | Pour Sentrymove depuis un PC externe |

**Erreur fréquente :** confondre l'IP de la **tablette** (`172.16.0.145` par exemple) avec celle du **robot**. Pour la sync POI depuis Termux, le robot reste en général sur **`192.168.20.22`**.

Pour connaître l'IP actuelle de la tablette :

```powershell
.\scripts\kiosk_test.ps1 ip
```

---

## Commandes du script (référence)

| Commande | Effet |
|----------|-------|
| `demarrer` | Tout-en-un : vérifie, démarre backend, lance l'app |
| `status` | État connexion + backend sans rien modifier |
| `redemarrer` | Arrête et relance le backend (port 8001) |
| `reparer` | Réinstalle les dépendances Python + redémarre |
| `lancer` | Ouvre uniquement l'application sur la tablette |
| `logs` | Affiche les 40 dernières lignes du journal d'erreur |
| `ip` | Affiche l'IP Wi-Fi actuelle de la tablette |

---

## Déploiement d'une mise à jour (occasionnel)

**En principe, le contrôleur n'a pas besoin de déployer du code.**  
Si un développeur vous demande de mettre à jour la tablette :

**Option facile (SSH configuré) :**

```powershell
python scripts/deploy_termux.py --host <IP_TABLETTE> --target test --lite-only
```

Remplacez `<IP_TABLETTE>` par le résultat de `.\scripts\kiosk_test.ps1 ip`.

**Option USB (sans SSH) :** suivre [GUIDE_CONTROLEUR_POI.md](GUIDE_CONTROLEUR_POI.md) §4.B — **ne jamais** utiliser `su -c 'tar xzf …'`.

Après tout déploiement :

```powershell
.\scripts\kiosk_test.ps1 demarrer
```

---

## Quand contacter le référent technique

Contactez l'équipe dev **seulement si** :

1. `.\scripts\kiosk_test.ps1 reparer` puis `demarrer` **échouent encore**
2. Les **logs** (`.\scripts\kiosk_test.ps1 logs`) montrent une erreur que vous ne reconnaissez pas
3. Le **robot ne bouge pas** alors que Sentrymove fonctionne (problème navigation, pas backend)
4. Vous devez **créer ou renommer un POI** — voir le guide POI complet

**À joindre au message :** sortie de `.\scripts\kiosk_test.ps1 status` et `.\scripts\kiosk_test.ps1 logs`.

---

## Rappel : créer un POI ou modifier le parcours

Ce guide couvre **le démarrage et le dépannage**. Pour le travail POI (Deployment Tool, noms, parcours visite), ouvrez :

→ **[GUIDE_CONTROLEUR_POI.md](GUIDE_CONTROLEUR_POI.md)**

---

_Dernière mise à jour : juin 2026_
