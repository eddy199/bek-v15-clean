# BREVET BEK-REX
## Reflective EXecution — Tiered Cognitive Routing

**Code brevet :** BEK-REX-v1.0
**Version :** 1.0
**Date :** 2026-09-23
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-REX |
| **Nom court** | REX |
| **Nom long** | Reflective EXecution |
| **Sous-titre** | Tiered Cognitive Routing |
| **Version** | 1.0 |
| **Catégorie** | Instruction principale |
| **Statut** | ✅ Actif |
| **Priorité** | 🔴 Critique |

---

## 2. PROBLÈME RÉSOLU

Les agents IA actuels utilisent **un seul pipeline** pour toutes les requêtes :
- "Bonjour" → même traitement qu'une analyse complexe
- Résultat : soit **trop lent**, soit **trop superficiel**
- Gaspillage massif de ressources

---

## 3. SOLUTION UNIQUE

**BEK-REX introduit un routing à 5 niveaux** qui détecte la complexité d'une requête et choisit le tier optimal.

### Les 5 tiers

| Tier | Nom | Utilisé pour | Temps |
|---|---|---|---|
| **TIER_0** | LOCAL | Salutations, conversations | < 0.5s |
| **TIER_1** | FAST | Questions factuelles simples | ~12s |
| **TIER_2** | DEEP | News, analyses moyennes | ~35s |
| **TIER_3** | EXPERT | Analyses complexes | ~75s |
| **TIER_4** | SPECIALIZED | Recherche spécialisée | ~90s |

### Détection automatique

- Nombre de mots
- Mots-clés (news, analyse, prix, etc.)
- Domaine (médecine, droit, science, etc.)
- Complexité syntaxique

---

## 4. PREUVE D'EXÉCUTION

**Sortie `demo.py` du 2026-09-26 :**
