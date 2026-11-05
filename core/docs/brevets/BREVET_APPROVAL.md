# BREVET BEK-APPROVAL
## Human Approval Manager — L3+ Risk Gating with Auto-Execution

**Code brevet :** BEK-APPROVAL-v1.0
**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-APPROVAL |
| **Nom court** | APPROVAL |
| **Nom long** | Human Approval Manager |
| **Sous-titre** | L3+ Risk Gating with Auto-Execution |
| **Version** | 1.0 |
| **Catégorie** | Brique de gouvernance |
| **Statut** | ✅ Actif |
| **Priorité** | 🔴 Critique |

---

## 2. PROBLÈME RÉSOLU

Les agents IA autonomes peuvent exécuter des **actions à risque élevé** (L3, L4, L5) :

- Écriture en base de données de production
- Exécution de commandes shell destructives
- Appels d'API externes coûteux
- Modification de fichiers critiques

**Sans validation humaine, c'est inacceptable en production.**

Mais bloquer toutes les actions rend l'agent inutilisable.

---

## 3. SOLUTION UNIQUE

**BEK-APPROVAL introduit un système d'approbation à 2 niveaux** :

1. **Auto-approbation** pour L1, L2, L3 (configurable via `AUTO_APPROVE_ACTIONS`)
2. **Validation humaine obligatoire** pour L4, L5

Chaque demande passe par une **file thread-safe** avec :
- ID unique (`BEK-APPR-XXXXXXXXXX`)
- TTL (1h par défaut)
- Statut (PENDING → APPROVED / REJECTED / EXPIRED / EXECUTED / FAILED)
- Notification EventBus sur topic `error-signals` pour L4/L5
- **Exécution automatique** post-approbation via Hermes

### Cycle de vie

```
submit_request → [auto-approve?] → approve_and_execute → EXECUTED
                    ↓ non
                [humain requis L4/L5] → Notification EventBus
                    ↓
                approve_and_execute OU reject_request
```

---

## 4. PREUVE D'EXÉCUTION

```python
from approval_manager import approval_manager

# Soumission (L2 → auto-approuvé si AUTO_APPROVE_ACTIONS=True)
req = approval_manager.submit_request(
    task_id="BEK-TASK-001",
    trace_id="BEK-TRC-001",
    tool="web_sync",
    args={"query": "Bitcoin"},
    risk_level="L3",
    reason="Recherche web profonde",
)
# → Auto-approuvé et exécuté immédiatement

# Soumission L4 (nécessite humain)
req = approval_manager.submit_request(
    task_id="BEK-TASK-002",
    trace_id="BEK-TRC-002",
    tool="execute_command",
    args={"command": "rm -rf /tmp/cache"},
    risk_level="L4",
    reason="Nettoyage cache",
)
# → Statut PENDING, notification EventBus

# Validation humaine
result = approval_manager.approve_and_execute("BEK-APPR-XXXXXXXXXX", admin_user="admin")
# → {"status": "success", "execution": {...}}
```

**Résultat :** 3 appels, L3 auto-exécuté, L4 en attente, cycle complet validé.

---

## 5. API PUBLIQUE

**Instance singleton :** `approval_manager`

| Méthode | Rôle |
|---|---|
| `submit_request(task_id, trace_id, tool, args, risk_level, reason, ttl_seconds)` | Crée une demande |
| `get_request(approval_id)` | Récupère une demande (avec expiration auto) |
| `list_requests(status=None)` | Liste toutes les demandes (filtre optionnel) |
| `approve_and_execute(approval_id, admin_user)` | Approuve + exécute via Hermes |
| `reject_request(approval_id, admin_user, reason)` | Rejette |

**Dataclass `ApprovalRequest` :**

| Champ | Type |
|---|---|
| `approval_id` | `str` |
| `task_id` | `str` |
| `trace_id` | `str` |
| `tool` | `str` |
| `args` | `Dict` |
| `risk_level` | `str` (L1-L5) |
| `status` | `str` (PENDING, APPROVED, REJECTED, EXPIRED, EXECUTED, FAILED) |
| `created_at` / `expires_at` | `float` |
| `decision_by` / `decision_at` | `Optional` |
| `execution_result` | `Optional[Dict]` |

---

## 6. FICHIERS ASSOCIÉS

| Fichier | Rôle |
|---|---|
| `approval_manager.py` | Implémentation |
| `nerves/approval_nerves.py` | Intégration Hermes |
| `config.py` | Flag `AUTO_APPROVE_ACTIONS` |
| `event_bus.py` | Notification Kafka |
| `bek_core/approval/` | **À créer** |

---

## 7. DIFFÉRENCE AVEC L'ÉTAT DE L'ART

| Solution existante | Limitation | Notre différence |
|---|---|---|
| **Human-in-the-loop** | Bloque tout | **Auto-approve L1-L3** |
| **Audit logs passifs** | Rien n'est bloqué | **Gating actif L4-L5** |
| **Permissions statiques** | Pas d'humain | **Approbation dynamique + EventBus** |

**Personne n'a un système d'approbation avec auto-exécution post-approbation.**

---

## 8. DÉPENDANCES

- `hermes_core.py` (pour l'exécution post-approbation)
- `event_bus.py` (notification L4/L5)
- `config.py` (flag AUTO_APPROVE_ACTIONS)

---

## 9. UTILISÉ PAR

- `nerves/approval_nerves.py`
- `hermes_core.py`
- `skill_runner.py` (gating L3+)
- `BEK-AGENT-v18`

---

**Signature :** BEK Project
**Date :** 2026-09-26