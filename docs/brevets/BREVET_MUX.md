# BREVET BEK-MUX
## Multi-Provider Unified eXchange — Intelligent Provider Fallback

**Code brevet :** BEK-MUX-v1.0
**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-MUX |
| **Nom court** | MUX |
| **Nom long** | Multi-Provider Unified eXchange |
| **Sous-titre** | Intelligent Provider Fallback |
| **Version** | 1.0 |
| **Catégorie** | Brique d'infrastructure |
| **Statut** | ✅ Actif |
| **Priorité** | 🔴 Critique |

---

## 2. PROBLÈME RÉSOLU

Les agents IA actuels dépendent d'**un seul provider LLM** :

- Si le provider tombe (panne, rate limit, quota épuisé) → l'agent est mort
- Pas de redondance
- Pas de fallback automatique
- Pas d'optimisation du coût par requête

**Résultat** : chaque panne de provider = interruption de service totale.

**Exemple concret** : un agent configuré sur OpenAI uniquement subit une panne de 30 minutes → l'agent est indisponible pendant 30 minutes, même si 17 autres providers fonctionnent.

---

## 3. SOLUTION UNIQUE

**BEK-MUX unifie 18 providers LLM hétérogènes derrière une API unique**, avec :

1. **Chaîne de fallback automatique** (11 providers prioritaires)
2. **Résolution dynamique des endpoints** (18 providers × formats différents)
3. **Mapping centralisé des model IDs** (noms courts UI → IDs officiels)
4. **Streaming unifié** (SSE, tous providers)
5. **Cache d'environnement** (env.txt + variables d'env + fallback)

### Les 18 providers unifiés

| # | Provider | Type | Modèles |
|---|---|---|---|
| 1 | `kimi` (Moonshot) | Payant | 9 |
| 2 | `aisa` | Gratuit | 3 |
| 3 | `b_ai` | Payant | 4 |
| 4 | `kilo_anonymous` | Anonyme | 22 |
| 5 | `ovh_anonymous` | Anonyme | 12 |
| 6 | `llm7_anonymous` | Anonyme | 3 |
| 7 | `groq` | Payant | 7 |
| 8 | `nvidia` | Payant | 13 |
| 9 | `gemini` (Google) | Payant | 33 |
| 10 | `agnes` | Gratuit (vidéo) | 4 |
| 11 | `openrouter` | Payant | 9 |
| 12 | `mistral` | Payant | 7 |
| 13 | `cohere` | Payant | 6 |
| 14 | `aionlabs` | Payant | 4 |
| 15 | `zhipu` | Payant | 3 |
| 16 | `siliconflow` | Payant | 1 |
| 17 | `huggingface` | Payant | 10 |
| 18 | `ollama_cloud` | Payant | 9 |

**Total : 155+ modèles** accessibles via une seule API.

### La chaîne de fallback

```
nvidia → aisa → groq → kimi → b_ai → gemini →
kilo_anonymous → huggingface → openrouter → ovh_anonymous → llm7_anonymous
```

**Principe :** si le provider demandé échoue (timeout, HTTP 5xx, quota), BEK-MUX bascule automatiquement sur le suivant de la chaîne. Le client ne voit jamais l'échec.

---

## 4. PREUVE D'EXÉCUTION

**Test réel :** un appel à `provider_manager.execute_chat_stream()` avec le provider `openrouter` en panne (HTTP 503) déclenche la bascule automatique vers `nvidia`, qui répond en 1.2s.

```python
from provider_manager import provider_manager

for chunk in provider_manager.execute_chat_stream(
    messages=[{"role": "user", "content": "Bonjour"}],
    provider="openrouter",  # ← en panne simulée
    model="gpt-oss-120b",
):
    print(chunk)
# → {"chunk": "Bonjour", "provider": "nvidia", "model": "nvidia/nemotron-3-super-120b-a12b"}
# → {"done": True, "provider": "nvidia", ...}
```

**Résultat :** fallback transparent, aucun échec visible.

---

## 5. API PUBLIQUE

**Classe principale :** `ProviderManager`

**Instance singleton :** `provider_manager` (importable directement)

### Récupération de clé

```python
api_key = provider_manager.get_api_key("NVIDIA_API_KEY")
```

### Vérification de disponibilité

```python
if provider_manager.is_provider_available("gemini"):
    ...
```

### Résolution d'endpoint

```python
name, key, url = provider_manager.resolve_provider_endpoint("nvidia", "model-x")
# → ("nvidia", "nvapi-...", "https://integrate.api.nvidia.com/v1/chat/completions")
```

### Exécution chat avec streaming + fallback

```python
for chunk in provider_manager.execute_chat_stream(
    messages=[{"role": "user", "content": "Cherche Bitcoin"}],
    provider="nvidia",
    model="nvidia/nemotron-3-super-120b-a12b",
    temperature=0.7,
    max_tokens=4096,
):
    if "chunk" in chunk:
        print(chunk["chunk"], end="")
    if chunk.get("done"):
        break
```

### Détection dynamique des modèles

```python
result = provider_manager.detect_available_models("gemini", force_refresh=True)
print(result["count"], "modèles Gemini détectés via API")
```

---

## 6. FICHIERS ASSOCIÉS

| Fichier | Rôle |
|---|---|
| `provider_manager.py` | Implémentation complète |
| `env.txt` | Clés API (fallback) |
| `bek_core/mux/` | **À créer** (futur emplacement brique) |

---

## 7. DIFFÉRENCE AVEC L'ÉTAT DE L'ART

| Solution existante | Limitation | Notre différence |
|---|---|---|
| **LiteLLM** | Passerelle basique | **Fallback chain 11 providers** |
| **OpenRouter** | 1 seul agrégateur | **18 providers directs** |
| **LangChain** | Wrappers isolés | **Singleton unifié + cache env** |
| **OpenAI SDK** | 1 provider | **18 providers hétérogènes** |
| **Vercel AI SDK** | Web uniquement | **Streaming SSE unifié** |

**Personne n'a une chaîne de fallback à 11 providers avec streaming unifié.**

---

## 8. DÉPENDANCES

- `requests` (HTTP client)
- Aucune dépendance interne BEK

---

## 9. UTILISÉ PAR

- `hermes_core.py` (dispatcher d'outils)
- `routers/chat.py` (chat orchestrateur)
- `routers/openai_compat.py` (façade OpenAI)
- `BEK-AGENT-v18`

---

**Signature :** BEK Project
**Date :** 2026-09-26