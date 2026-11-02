# BREVET BEK-HEAD
## Headless Extraction with Multi-Engine Cascade — Playwright + 6 Search Engines

**Code brevet :** BEK-HEAD-v1.0
**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-HEAD |
| **Nom court** | HEAD |
| **Nom long** | Headless Extraction with Multi-Engine Cascade |
| **Sous-titre** | Playwright + 6 Search Engines |
| **Version** | 1.0 |
| **Catégorie** | Brique de scraping |
| **Statut** | ✅ Actif |
| **Priorité** | 🔴 Critique |

---

## 2. PROBLÈME RÉSOLU

Les scrapers headless classiques ont **3 limitations** :

1. **1 seul moteur de recherche** — si Google bloque, tout s'arrête
2. **Pages stériles en résultats** — homes, logins, recherches génériques
3. **Pas de filtre de pertinence** — 0 match mots-clés = 0 résultat exploitable

**Résultat** : scraping fragile, bruit massif, 0 résultat utile.

---

## 3. SOLUTION UNIQUE

**BEK-HEAD combine 5 mécanismes :**

1. **Cascade 6 moteurs** (Google → Bing → DDG → Qwant → Mojeek → Startpage)
2. **Cumul multi-moteurs** (ne s'arrête plus au 1er moteur, seuil = 3 résultats)
3. **Filtre URLs stériles** (regex 20+ patterns)
4. **Filtre de pertinence** (mots-clés match)
5. **Anti-bot** (4 User-Agents rotatifs + script stealth)

### Caractéristiques

| Caractéristique | Valeur |
|---|---|
| Moteurs | 6 (Google, Bing, DDG, Qwant, Mojeek, Startpage) |
| Seuil cumul | 3 résultats minimum |
| Concurrence | 3 workers max |
| Timeout | 30s par défaut |
| Blocked | image, media, font |
| User-Agents | 4 rotatifs |
| Stealth | `navigator.webdriver` masqué |

---

## 4. PREUVE D'EXÉCUTION

```python
from worker_headless import HeadlessWorker
from nerves._async_utils import run_async_safely

worker = HeadlessWorker(headless=True, timeout_ms=25000)
leads = run_async_safely(worker.search_and_extract_leads("Bitcoin 2026", limit=5))

# Logs :
# [search/pw] Google → 0 résultat, on continue
# [search/pw] Bing → 2 résultats (cumul : 2)
# [search/pw] DDG Lite → 3 résultats (cumul : 5)
# [search/pw] Seuil 3 atteint sur DDG Lite
# [search/pw] Total cumulé : 5 résultats uniques (sur 6 moteurs testés)
```

**Résultat :** 5 résultats uniques, filtrés (0 home, 0 login), pertinents.

---

## 5. API PUBLIQUE

### Classe

```python
from worker_headless import HeadlessWorker

worker = HeadlessWorker(headless=True, timeout_ms=30000)
```

### Recherche + leads

```python
leads = await worker.search_and_extract_leads("Bitcoin", limit=5)
# → [{"title": "...", "source_url": "...", "snippet": "...", "email": "..."}]
```

### Fetch d'une page

```python
page = await worker.fetch_page_content("https://example.com")
# → {"status": "success", "html": "...", "title": "...", ...}
```

### Filtre stérile (module-level)

```python
from worker_headless import _is_sterile_url

_is_sterile_url("https://google.com/")         # → True
_is_sterile_url("https://example.com/article") # → False
```

---

## 6. FICHIERS ASSOCIÉS

| Fichier | Rôle |
|---|---|
| `worker_headless.py` | Implémentation |
| `bek_core/head/` | **À créer** |

---

## 7. DIFFÉRENCE AVEC L'ÉTAT DE L'ART

| Solution existante | Limitation | Notre différence |
|---|---|---|
| **Playwright brut** | 1 moteur | **6 moteurs en cascade** |
| **Selenium** | Pas de filtre stérile | **Regex 20+ patterns** |
| **Scrapy** | Pas de cascade | **Cumul + seuil** |
| **Crawl4AI** | 1 moteur | **6 moteurs + stealth** |

**Personne n'a une cascade à 6 moteurs avec cumul et filtre stérile.**

---

## 8. DÉPENDANCES

- `playwright` (browser automation)
- `beautifulsoup4` (HTML parsing)
- `requests` (fallback HTTP)

---

## 9. UTILISÉ PAR

- `web_agent.py` (BEK-WEB)
- `hermes_core.py` (outil `headless_scrape`)
- `BEK-AGENT-v18`

---

**Signature :** BEK Project
**Date :** 2026-09-26