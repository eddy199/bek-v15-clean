# BREVET BEK-HERMES
## Hybrid Execution Runtime with Meta-Orchestration — GOAP + DAG + Security

**Code brevet :** BEK-HERMES-v1.0
**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-HERMES |
| **Nom court** | HERMES |
| **Nom long** | Hybrid Execution Runtime with Meta-Orchestration |
| **Sous-titre** | GOAP + DAG + Security |
| **Version** | 1.0 |
| **Catégorie** | Brique d'orchestration |
| **Statut** | ✅ Actif |
| **Priorité** | 🔴 Critique |

---

## 2. PROBLÈME RÉSOLU

Les orchestrateurs d'agents actuels ont **3 limitations majeures** :

1. **Planification rigide** — les plans sont hardcodés, pas générés dynamiquement
2. **Exécution séquentielle** — pas de parallélisme intelligent par vagues
3. **Sécurité faible** — pas de validation cryptographique avant exécution

**Résultat** : un agent lent, vulnérable aux injections, incapable de s'adapter à de nouveaux outils.

---

## 3. SOLUTION UNIQUE

**BEK-HERMES combine 4 mécanismes en un seul runtime :**

1. **Planification dynamique par mots-clés** (au lieu de GOAP hardcodé)
2. **Dispatcher DAG parallèle** (10 workers, isolation par branche)
3. **Sécurité HMAC + niveaux de risque** (L1 → L5)
4. **Hooks d'orchestration** (pre_plan, step, post_plan)

### Caractéristiques

| Caractéristique | Valeur |
|---|---|
| Workers par défaut | 10 (max 64) |
| Timeout par tâche | 15s (max 3600s) |
| Niveaux de risque | L1, L2, L3, L4, L5 |
| Approval humain requis | L3, L4, L5 |
| Sécurité | HMAC (via `SecurityGuard`) |
| Threading | `ThreadPoolExecutor` + `HermesDAGOrchestrator` |
| Hooks | 3 types (pre_plan, step, post_plan) |
| Guardian | Thread daemon (audit + replay vectoriel) |

---

## 4. PREUVE D'EXÉCUTION

**Test réel :** dispatch parallèle de 3 tâches avec filtres de sécurité actifs.

```python
from hermes_core import dispatch_parallel

result = dispatch_parallel([
    {"tool": "default_llm", "args": {"query": "Bonjour"}},
    {"tool": "neon_audit", "args": {}},
    {"tool": "web_sync", "args": {"query": "Bitcoin"}},  # L3 → approval
])
# → {
#     "status": "PARTIAL_SUCCESS",
#     "success_count": 2,
#     "failure_count": 1,
#     "results": {
#         "BEK-TASK-...": {"success": True, ...},
#         "BEK-TASK-...": {"success": True, ...},
#         "BEK-TASK-...": {"success": False, "error_type": "SECURITY_APPROVAL_REQUIRED"},
#     }
# }
```

**Résultat :** 2 outils exécutés, 1 bloqué (L3 requiert humain). Sécurité active.

---

## 5. API PUBLIQUE

### Enregistrer un outil

```python
from hermes_core import register_tool

register_tool("my_tool", ma_fonction, risk_level="L2")
```

### Planification par mots-clés

```python
from hermes_core import plan_from_keywords

tasks = plan_from_keywords("Génère une image de chat")
# → [{"tool": "generate_image", "args": {"prompt": "..."}, ...}]
```

### Dispatch parallèle

```python
from hermes_core import dispatch_parallel

result = dispatch_parallel(tasks)
```

### Dispatch DAG

```python
from hermes_core import dispatch_dag_plan

result = dispatch_dag_plan({
    "plan_id": "PLAN-001",
    "steps": [
        {"id": "s1", "action": "web_sync", "params": {"query": "Bitcoin"}, "depends_on": []},
        {"id": "s2", "action": "default_llm", "params": {"query": "Résume"}, "depends_on": ["s1"]},
    ]
})
```

### Statut runtime

```python
from hermes_core import runtime_status

status = runtime_status()
# → {"status": "operational", "tool_count": 51, "max_workers": 10, ...}
```

---

## 6. FICHIERS ASSOCIÉS

| Fichier | Rôle |
|---|---|
| `hermes_core.py` | Implémentation complète |
| `core/hermes_dag_adapter.py` | Orchestrateur DAG (ADR-001) |
| `security_guard.py` | HMAC + Allowlist |
| `skill_registry.py` | Source des skills |
| `memory.py` | Persistance (Guardian) |
| `bek_core/hermes/` | **À créer** (futur emplacement brique) |

---

## 7. DIFFÉRENCE AVEC L'ÉTAT DE L'ART

| Solution existante | Limitation | Notre différence |
|---|---|---|
| **LangChain Agents** | Planification hardcodée | **Planification par mots-clés dynamique** |
| **AutoGen** | Pas de DAG parallèle | **DAG Engine 10 workers** |
| **CrewAI** | Pas de sécurité HMAC | **HMAC + niveaux L1-L5** |
| **GOAP classique** | Mono-chemin | **Multi-outils + hooks** |

**Personne n'a un orchestrateur qui combine GOAP + DAG + HMAC + hooks.**

---

## 8. DÉPENDANCES

- `security_guard.py` (HMAC)
- `skill_registry.py` (skills)
- `core/hermes_dag_adapter.py` (DAG)
- `memory.py` (Guardian persistence)

---

## 9. UTILISÉ PAR

- `app.py` (orchestrateur principal)
- `routers/chat.py` (chat)
- `meta_cortex_swarm.py` (débat)
- `BEK-AGENT-v18`

---

**Signature :** BEK Project
**Date :** 2026-09-26