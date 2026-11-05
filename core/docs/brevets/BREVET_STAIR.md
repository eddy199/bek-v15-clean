# BREVET BEK-STAIR
## IBM STAIR Method — Anti-Hallucination ToC

**Code brevet :** BEK-STAIR-v1.0
**Version :** 1.0
**Date :** 2026-09-23
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-STAIR |
| **Nom court** | STAIR |
| **Nom long** | IBM STAIR Method |
| **Sous-titre** | Anti-Hallucination ToC |
| **Version** | 1.0 |
| **Catégorie** | Instruction de validation |
| **Statut** | ✅ Actif |
| **Priorité** | 🔴 Critique |

---

## 2. PROBLÈME RÉSOLU

Les LLM **hallucinent** quand ils génèrent des réponses sans ancrage factuel :
- Ils inventent des URLs
- Ils inventent des dates
- Ils inventent des chiffres
- Ils inventent des noms de sources ("selon Reuters")

**Résultat** : réponses fausses présentées comme vraies.

---

## 3. SOLUTION UNIQUE

**BEK-STAIR force le LLM à répondre UNIQUEMENT dans un ToC** (Table of Contents) construit à partir des sources réelles.

### Principe

1. **Build ToC** : on construit une table des matières à partir des pages scrapées
2. **Inject ToC** : on injecte le ToC dans le prompt du LLM
3. **Validate** : on valide la réponse du LLM contre le ToC

### Détection des hallucinations

| Type détecté | Méthode |
|---|---|
| **URLs inventées** | Comparaison avec les URLs du ToC |
| **Sources fantômes** | Regex sur les mentions ("selon X") |
| **Faits inventés** | Vérification factuelle (optionnel) |

### Scoring

- Score de départ : `1.0`
- URL invalide : `-0.3` par URL (max 3)
- Source inventée : `-0.1` par mention
- Score < 0.5 → **rejet**

---

## 4. PREUVE D'EXÉCUTION

BEK-STAIR est intégré dans le pipeline de `routers/chat_modules/streaming.py` v1.2.

**Comportement observé :**
