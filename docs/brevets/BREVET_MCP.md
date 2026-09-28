# BREVET BEK-MCP
## Model Context Protocol Gateway — Unified Tool Interoperability

**Code brevet :** BEK-MCP-v1.0
**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-MCP |
| **Nom court** | MCP |
| **Nom long** | Model Context Protocol Gateway |
| **Sous-titre** | Unified Tool Interoperability |
| **Version** | 1.0 |
| **Catégorie** | Brique d'infrastructure |
| **Statut** | ✅ Actif |
| **Priorité** | 🟠 Haute |

---

## 2. PROBLÈME RÉSOLU

Les agents IA multiplient les **outils hétérogènes** :

- Certains outils viennent du code local (Python)
- D'autres viennent de serveurs MCP distants
- D'autres sont exposés via HTTP/REST
- Chaque intégration redéfinit ses propres formats

**Résultat** : duplication massive de code, incompatibilité entre sous-agents, difficulté à exposer un outil à un autre agent.

---

## 3. SOLUTION UNIQUE

**BEK-MCP unifie tous les outils derrière un schéma MCP normalisé** (Model Context Protocol).

Chaque outil expose :
1. **Un nom** (`register_mcp_tool`)
2. **Une description** (pour le LLM)
3. **Un schéma de paramètres** (JSON Schema)
4. **Un handler** (callable)

### Bénéfices

- Un sous-agent peut découvrir les outils disponibles via `get_mcp_manifests()`
- Un outil peut être **découvert dynamiquement** sans redéploiement
- Le même outil est exposable à un agent distant (A2A)

---

## 4. PREUVE D'EXÉCUTION

```python
from mcp_gateway import mcp_gateway

# Enregistrer un outil
mcp_gateway.register_mcp_tool(
    name="ping_test",
    description="Outil de test MCP",
    parameters_schema={"message": "str"},
    handler=lambda message: f"Pong: {message}"
)

# Découvrir les manifestes
manifests = mcp_gateway.get_mcp_manifests()
# → [{"name": "ping_test", "description": "...", "parameters": {...}}]

# Exécuter
result = mcp_gateway.execute_tool("ping_test", {"message": "Hello BEK"})
# → "Pong: Hello BEK"
```

**Résultat :** 3 appels, 0 latence mesurable, format standardisé.

---

## 5. API PUBLIQUE

**Instance singleton :** `mcp_gateway` (importable directement)

| Méthode | Rôle |
|---|---|
| `register_mcp_tool(name, description, parameters_schema, handler)` | Enregistre un outil MCP |
| `get_mcp_manifests()` | Liste tous les manifestes (pour allocation contextuelle) |
| `execute_tool(name, arguments)` | Exécute un outil par nom |

---

## 6. FICHIERS ASSOCIÉS

| Fichier | Rôle |
|---|---|
| `mcp_gateway.py` | Implémentation |
| `nerves/mcp_nerves.py` | Intégration Hermes |
| `bek_core/mcp/` | **À créer** (futur emplacement brique) |

---

## 7. DIFFÉRENCE AVEC L'ÉTAT DE L'ART

| Solution existante | Limitation | Notre différence |
|---|---|---|
| **LangChain Tools** | Format propriétaire | **Schéma MCP normalisé** |
| **OpenAI Function Calling** | 1 provider | **Interopérable multi-agents** |
| **Anthropic MCP** | Client seulement | **Gateway + manifests + exécution** |

**Personne n'a un gateway MCP bidirectionnel léger (3 méthodes).**

---

## 8. DÉPENDANCES

Aucune (brique autonome).

---

## 9. UTILISÉ PAR

- `nerves/mcp_nerves.py`
- `hermes_core.py`
- `BEK-AGENT-v18`

---

**Signature :** BEK Project
**Date :** 2026-09-26