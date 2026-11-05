# BREVET BEK-WEB
## Web Extraction & Bayesian Synthesis — Deep Crawling + Swarm Debate

**Code brevet :** BEK-WEB-v1.0
**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-WEB |
| **Nom court** | WEB |
| **Nom long** | Web Extraction & Bayesian Synthesis |
| **Sous-titre** | Deep Crawling + Swarm Debate |
| **Version** | 1.0 |
| **Catégorie** | Brique de recherche |
| **Statut** | ✅ Actif |
| **Priorité** | 🔴 Critique |

---

## 2. PROBLÈME RÉSOLU

Les agents de recherche web actuels ont **3 limitations** :

1. **Extraction superficielle** — ils retournent des snippets, pas le contenu intégral
2. **Pas de synthèse contradictoire** — une seule réponse, pas de débat
3. **Pas de persistance** — chaque recherche repart de zéro

**Résultat** : recherche pauvre, hallucination fréquente, gaspillage de requêtes.

---

## 3. SOLUTION UNIQUE

**BEK-WEB combine 4 mécanismes :**

1. **Deep crawling Playwright** (extraction du HTML complet + nettoyage BS4)
2. **Déduplication MinHash** (évite de scraper 2x la même page)
3. **Débat Swarm** (2 agents : Critique + Architecte)
4. **Persistance vectorielle** (Pinecone + Neon DB)

### Caractéristiques

| Caractéristique | Valeur |
|---|---|
| Scraping | Playwright (via BEK-HEAD) |
| Extraction | BeautifulSoup (h1-h3, p, li, pre, code) |
| Déduplication | MinHashSimilarity |
| Fallback | Wikipedia (sauf requêtes news) |
| Débat | ReflexionSwarm (2 agents) |
| Persistance | Pinecone + Neon DB |
| Concurrence | 3 workers |

---

## 4. PREUVE D'EXÉCUTION

```python
from web_agent import web_agent_instance

report = web_agent_instance.run_pipeline("Architectures multi-agents 2026")
# → Rapport structuré :
#     - ## 🌐 Rapport d'Ingénierie
#     - ### 📑 Sources Décortiquées
#     - ### ⚔️ Synthèse Arbitrée par ReflexionSwarm
```

**Résultat :** 3 sources scrapées, dédupliquées, persistées, débat Swarm généré.

---

## 5. API PUBLIQUE

### Pipeline complet

```python
from web_agent import web_agent_instance

report = web_agent_instance.run_pipeline("Bitcoin news 2026")
```

### Scraping d'une URL

```python
page = web_agent_instance.scrape_url_deep("https://example.com", max_chars=5000)
# → {"url": "...", "content": "...", "error": None}
```

### Recherche de liens

```python
links = web_agent_instance.search_candidate_links("Bitcoin", limit=4)
# → [{"title": "...", "url": "...", "snippet": "..."}]
```

### Débat Swarm

```python
verdict = web_agent_instance.synthesize_with_swarm("Bitcoin", corpus)
# → Texte de synthèse contradictoire
```

---

## 6. FICHIERS ASSOCIÉS

| Fichier | Rôle |
|---|---|
| `web_agent.py` | Implémentation |
| `worker_headless.py` | Playwright (BEK-HEAD) |
| `meta_cortex_swarm.py` | ReflexionSwarm |
| `fast_math.py` | MinHashSimilarity |
| `memory.py` | Pinecone + Neon |
| `bek_core/web/` | **À créer** |

---

## 7. DIFFÉRENCE AVEC L'ÉTAT DE L'ART

| Solution existante | Limitation | Notre différence |
|---|---|---|
| **Perplexity** | Snippets + 1 réponse | **Deep crawl + débat 2 agents** |
| **SearchGPT** | 1 réponse unifiée | **Synthèse contradictoire** |
| **Scrapy** | Pas de synthèse | **Pipeline complet** |
| **Haystack** | Pas de swarm | **ReflexionSwarm intégré** |

**Personne n'a un agent web avec débat contradictoire automatique.**

---

## 8. DÉPENDANCES

- `worker_headless.py` (BEK-HEAD)
- `provider_manager.py` (BEK-MUX)
- `meta_cortex_swarm.py` (Swarm)
- `fast_math.py` (MinHash)
- `memory.py` (Pinecone + Neon)

---

## 9. UTILISÉ PAR

- `hermes_core.py` (outil `web_sync`)
- `BEK-AGENT-v18`

---

**Signature :** BEK Project
**Date :** 2026-09-26