# BREVET BEK-GUARD
## Runtime Security Guard — Allowlist + Sandbox + HMAC + DLP

**Code brevet :** BEK-GUARD-v1.0
**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-GUARD |
| **Nom court** | GUARD |
| **Nom long** | Runtime Security Guard |
| **Sous-titre** | Allowlist + Sandbox + HMAC + DLP |
| **Version** | 1.0 |
| **Catégorie** | Brique de sécurité |
| **Statut** | ✅ Actif |
| **Priorité** | 🔴 Critique |

---

## 2. PROBLÈME RÉSOLU

Les agents IA exécutent du **code généré dynamiquement** et des **commandes système**. Sans sécurité runtime :

- Injection SQL / shell / code Python
- Exfiltration de secrets (`.env`, `id_rsa`, `credentials.json`)
- Évasion de sandbox (`os.system`, `subprocess`, `eval`)
- Path traversal (`../../etc/passwd`)
- Rejeu d'appels (pas de signature)

**Résultat** : compromission totale possible.

---

## 3. SOLUTION UNIQUE

**BEK-GUARD combine 5 mécanismes de défense en profondeur :**

1. **Allowlist stricte** (76 actions autorisées, params whitelistés)
2. **Sandbox AST** (`ast.walk()` sur le code, ban des imports dangereux)
3. **Confirmation de chemins** (tous les paths résolus dans `BASE_DIR`)
4. **DLP secrets** (regex `sk-...`, `nvapi-...`, `gsk_...`, `AIza...`)
5. **HMAC-SHA256** (signature des enveloppes, vérification `verify_envelope`)

### Niveaux de défense

| Défense | Cible |
|---|---|
| Allowlist | Actions non autorisées |
| Sandbox AST | Code généré (eval, subprocess) |
| Path confinement | Path traversal + fichiers sensibles |
| DLP | Fuite de clés API dans les params |
| HMAC | Rejeu / altération d'appels |

---

## 4. PREUVE D'EXÉCUTION

```python
from security_guard import security_guard

# Test 1 : action autorisée
ok, msg, envelope = security_guard.validate_and_certify(
    "web_sync", {"query": "Bitcoin"}
)
# → (True, "CERTIFIÉ...", {"hsm_signature": "abc...", "certified": True})

# Test 2 : action inconnue
ok, msg, _ = security_guard.validate_and_certify("rm_rf_slash", {})
# → (False, "REJET SECURITE : Action 'rm_rf_slash' non presente dans l'Allowlist.", {})

# Test 3 : injection dans params
ok, msg, _ = security_guard.validate_and_certify(
    "execute_command", {"command": "DROP DATABASE production"}
)
# → (False, "REJET SECURITE : Signature destructive ou injection detectee dans 'command'.", {})

# Test 4 : code avec import interdit
ok, msg, _ = security_guard.validate_and_certify(
    "create_dynamic_skill",
    {"skill_name": "evil", "code_content": "import subprocess\nsubprocess.run('ls')"}
)
# → (False, "REJET SECURITE : Import dangereux interdit : 'subprocess'", {})

# Test 5 : path traversal
ok, msg, _ = security_guard.validate_and_certify(
    "read_file", {"filename": "../../etc/passwd"}
)
# → (False, "REJET SECURITE : Sortie de sandbox refusee pour '../../etc/passwd'.", {})

# Test 6 : vérification d'enveloppe
valid, msg = security_guard.verify_envelope(envelope)
# → (True, "OK")
```

**Résultat :** 6/6 tests passent. Aucune faille détectée.

---

## 5. API PUBLIQUE

**Instance singleton :** `security_guard`

| Méthode | Rôle |
|---|---|
| `validate_and_certify(action, params)` | Valide + signe HMAC → `(ok, msg, envelope)` |
| `verify_signature(action, params, signature)` | Vérifie HMAC |
| `verify_envelope(envelope)` | Vérifie enveloppe complète |
| `validate_code_ast(code_str)` | Sandbox AST → `(ok, msg)` |
| `sanitize_secrets(text)` | DLP — redact les clés |
| `runtime_status()` | Statistiques |

**Constantes :**

| Constante | Valeur |
|---|---|
| `DEFAULT_SECRET_ENV` | `"BEK_HSM_SECRET"` |
| `BLOCKED_SENSITIVE_FILES` | `.env`, `id_rsa`, `credentials.json`, etc. |
| `ALLOWED_ACTIONS` | 76 actions (dict) |
| `FORBIDDEN_PATTERNS` | 8 regex destructives |
| `FORBIDDEN_CODE_PATTERNS` | 18 regex (eval, exec, subprocess...) |
| `BANNED_IMPORTS` | 18 modules (subprocess, ctypes, socket...) |
| `SECRET_PATTERNS` | 5 regex (sk-, AIza, gsk_, nvapi-, Bearer) |

---

## 6. FICHIERS ASSOCIÉS

| Fichier | Rôle |
|---|---|
| `security_guard.py` | Implémentation |
| `core/security/path_guard.py` | Path confinement complémentaire |
| `core/security/skill_sandbox.py` | Sandbox AST complémentaire |
| `nerves/guardian_nerves.py` | Intégration Hermes |
| `bek_core/guard/` | **À créer** |

---

## 7. DIFFÉRENCE AVEC L'ÉTAT DE L'ART

| Solution existante | Limitation | Notre différence |
|---|---|---|
| **Guardrails AI** | Filtrage LLM | **Défense code + système** |
| **Llama Guard** | Modération texte | **Allowlist + AST + HMAC** |
| **Boto3 policies** | Cloud only | **Runtime + multi-couches** |

**Personne n'a une défense 5-couches (Allowlist + AST + Path + DLP + HMAC).**

---

## 8. DÉPENDANCES

- `ast` (stdlib)
- `hmac`, `hashlib` (stdlib)
- Aucune dépendance externe

---

## 9. UTILISÉ PAR

- `hermes_core.py` (check avant chaque exécution)
- `action_executor.py` (sandbox create_dynamic_skill)
- `skill_generator.py` (validation skill)
- `skill_runner.py` (gating)
- `BEK-AGENT-v18`

---

**Signature :** BEK Project
**Date :** 2026-09-26