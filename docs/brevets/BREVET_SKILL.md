# BREVET BEK-SKILL
## Dynamic Skill System — Registry + Generation + Sandboxed Execution

**Code brevet :** BEK-SKILL-v1.0
**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-SKILL |
| **Nom court** | SKILL |
| **Nom long** | Dynamic Skill System |
| **Sous-titre** | Registry + Generation + Sandboxed Execution |
| **Version** | 1.0 |
| **Catégorie** | Brique d'extension |
| **Statut** | ✅ Actif |
| **Priorité** | 🟠 Haute |

---

## 2. PROBLÈME RÉSOLU

Les agents IA ont des capacités **fixes** :

- Les outils sont définis au boot
- Ajouter une capacité nécessite un redéploiement
- Les skills générés par le LLM sont dangereux à exécuter

**Résultat** : l'agent ne peut pas apprendre de nouvelles compétences en runtime.

---

## 3. SOLUTION UNIQUE

**BEK-SKILL combine 4 mécanismes pour étendre dynamiquement les capacités :**

1. **Registry** (`skill_registry.py`) — Indexe les skills existants (JSON, MD, TXT)
2. **Generator** (`skill_generator.py`) — Génère un skill depuis du code LLM
3. **Sandbox** (`skill_runner.py`) — Exécute en sous-processus isolé
4. **Gating** — Skill L3+ requiert approbation humaine

### Pipeline complet

```
LLM génère code → Generator valide (nom + taille + AST) → écrit skill.py
                         ↓
                SkillRegistry.register_custom_skill
                         ↓
LLM demande exécution → Runner.load manifest → check risk_level
                         ↓
                [L3+ → ApprovalManager.submit_request]
                         ↓
                subprocess.run (isolated, timeout)
                         ↓
                EventBus.publish("skills-index")
```

### Caractéristiques

| Caractéristique | Valeur |
|---|---|
| Nom de skill | Regex `^[a-zA-Z0-9_\-]{1,64}$` |
| Taille max | 200 KB |
| Sandbox | AST + 8 imports interdits |
| Exécution | Sous-processus isolé |
| Timeout | 30s par défaut |
| Risk level | L1 (défaut), L3+ gating |
| Score | Adaptatif (0.1 → 2.0) |
| Feedback | Neon DB (success/failure) |

---

## 4. PREUVE D'EXÉCUTION

```python
from skill_generator import create_and_register_skill
from skill_runner import execute_skill_async

# 1. Générer un skill
result = create_and_register_skill(
    skill_name="hello_world",
    code_content='print("Hello from BEK-SKILL!")',
    description="Skill de démo"
)
# → {"status": "success", "path": ".../hello_world.py", "hash": "abc..."}

# 2. L'exécuter en sandbox
import asyncio
result = asyncio.run(execute_skill_async(
    skill_name="hello_world",
    payload={},
    timeout_seconds=10,
))
# → {"status": "success", "skill": "hello_world", "returncode": 0, "result": "Hello from BEK-SKILL!"}

# 3. Vérifier le refus sandbox
result = create_and_register_skill(
    skill_name="evil",
    code_content="import subprocess\nsubprocess.run(['ls'])"
)
# → {"status": "error", "message": "🛡️ [SANDBOX REJET] Import interdit : subprocess"}
```

**Résultat :** création + exécution + refus sandbox, 3 étapes validées.

---

## 5. API PUBLIQUE

### Registry (`skill_registry.py`)

**Instance singleton :** `skill_registry`

| Méthode | Rôle |
|---|---|
| `load_skills()` | Scanne les répertoires, charge + score |
| `search_skills(query, limit)` | Recherche sémantique par mots-clés |
| `get_skill(skill_id)` | Récupère un skill |
| `register_custom_skill(skill)` | Ajoute un skill à chaud |
| `list_all_skills()` | Liste complète |
| `record_feedback(skill_id, success)` | Met à jour le score |

**Dataclass `Skill` :** `skill_id, name, description, prompt, command, category, risk_level, required_tools, preconditions, effects, score, success_count, failure_count, enabled, metadata`

### Generator (`skill_generator.py`)

| Fonction | Rôle |
|---|---|
| `create_and_register_skill(skill_name, code_content, description)` | Valide + écrit + enregistre + notifie EventBus |

### Runner (`skill_runner.py`)

| Fonction | Rôle |
|---|---|
| `execute_skill_async(skill_name, payload, timeout_seconds)` | Exécute en sous-processus avec gating L3+ |

---

## 6. FICHIERS ASSOCIÉS

| Fichier | Rôle |
|---|---|
| `skill_registry.py` | Index + scoring |
| `skill_generator.py` | Génération + validation |
| `skill_runner.py` | Exécution sandbox |
| `skills.py` | Skills natifs (filesystem, codeur, memory...) |
| `core/security/skill_sandbox.py` | Sandbox AST avancé |
| `nerves/skills_nerves.py` | Intégration Hermes |
| `bek_core/skill/` | **À créer** |

---

## 7. DIFFÉRENCE AVEC L'ÉTAT DE L'ART

| Solution existante | Limitation | Notre différence |
|---|---|---|
| **LangChain Tools** | Statique | **Génération runtime** |
| **OpenAI Assistants** | Pas de code custom | **Code Python exécutable** |
| **AutoGPT Skills** | Pas de sandbox | **AST + subprocess isolé** |
| **Anthropic Skills** | Pas de scoring | **Score adaptatif + feedback** |

**Personne n'a un système de skills générés + sandbox + gating L3 + scoring.**

---

## 8. DÉPENDANCES

- `security_guard.py` (AST validation)
- `approval_manager.py` (gating L3+)
- `event_bus.py` (notifications)
- `memory.py` (Neon DB scores)

---

## 9. UTILISÉ PAR

- `nerves/skills_nerves.py`
- `hermes_core.py` (planification)
- `action_executor.py` (create_dynamic_skill)
- `BEK-AGENT-v18`

---

**Signature :** BEK Project
**Date :** 2026-09-26