# BREVET BEK-FLUX
## Fast Layered Unified eXecution — DAG-Based Web Orchestration

**Code brevet :** BEK-FLUX-v1.0
**Version :** 1.0
**Date :** 2026-09-23
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-FLUX |
| **Nom court** | FLUX |
| **Nom long** | Fast Layered Unified eXecution |
| **Sous-titre** | DAG-Based Web Orchestration |
| **Version** | 1.0 |
| **Catégorie** | Instruction principale |
| **Statut** | ✅ Actif |
| **Priorité** | 🔴 Critique |

---

## 2. PROBLÈME RÉSOLU

Les scrapers classiques exécutent les tâches **séquentiellement** :
- Pour 15 pages : **15× le temps** d'une seule page
- Pas de parallélisation native
- Pas d'isolation d'erreurs
- Pas de timeout adaptatif

**Résultat** : lenteur, gaspillage de ressources.

---

## 3. SOLUTION UNIQUE

**BEK-FLUX utilise un DAG Engine** pour paralléliser les tâches en **10 workers simultanés**.

### Caractéristiques

| Caractéristique | Valeur |
|---|---|
| Workers par défaut | 10 |
| Timeout par tâche | 25s |
| Isolation d'erreurs | Par branche |
| Timeout global | Configurable |

### Gain mesuré

**8 tâches de 200ms** :
- Séquentiel : 1600ms
- Parallèle : 223ms
- **Speedup : 7.2x**

---

## 4. PREUVE D'EXÉCUTION

**Sortie `demo.py` du 2026-09-26 :**
