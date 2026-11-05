# BREVET BEK-MEM
## Methodological Evolution Memory — Evolutionary Prototype Memory

**Code brevet :** BEK-MEM-v1.0
**Version :** 1.0
**Date :** 2026-09-23
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-MEM |
| **Nom court** | MEM |
| **Nom long** | Methodological Evolution Memory |
| **Sous-titre** | Evolutionary Prototype Memory |
| **Version** | 1.0 |
| **Catégorie** | Instruction principale |
| **Statut** | ✅ Actif |
| **Priorité** | 🔴 Critique |

---

## 2. PROBLÈME RÉSOLU

Les agents IA actuels **re-cherchent à chaque requête**, même pour des questions similaires déjà traitées :
- Pas de mémoire associative
- Pas de réutilisation des méthodologies
- Gaspillage massif sur les patterns répétés

**Résultat** : chaque question similaire coûte le même prix.

---

## 3. SOLUTION UNIQUE

**BEK-MEM stocke des prototypes de résolution** (méthodologie + outils + paramètres + statistiques), pas juste des réponses.

### Différence clé

| Ce qui est stocké | Exemple |
|---|---|
| ❌ Une réponse figée | "Bitcoin = 70556€" |
| ✅ Une méthodologie | "web_sync → TIER_2 → 5 sources" |

### Caractéristiques

| Caractéristique | Valeur |
|---|---|
| Type de stockage | JSON local (fallback Pinecone) |
| Seuil de matching | 0.85 |
| Similarité | Jaccard (mots en commun) |
| Statistiques | usage_count, success_count, avg_time_ms |

---

## 4. PREUVE D'EXÉCUTION

**Sortie `demo.py` du 2026-09-26 :**
