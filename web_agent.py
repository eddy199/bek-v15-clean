# ==============================================================================
# web_agent.py — AGENT DE RECHERCHE PROFONDE (BEK-v19.3)
# ------------------------------------------------------------------------------
# v19.3 (2026-10-03) : ★ Fix limite Groq 8000 TPM
#   - scrape_url_deep : max_chars 5000 → 1500
#   - synthesize_with_swarm : corpus 6000 → 2500 chars
#   - persist_extracted_knowledge : extrait 1500 → 500 chars
#   - ddgs + Playwright + fallback snippets
# ==============================================================================

from __future__ import annotations

import asyncio
import os
import re
import time
import logging
import urllib.parse
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from memory import save_to_memory

try:
    from meta_cortex_swarm import ReflexionSwarm
except ImportError:
    ReflexionSwarm = None

try:
    from fast_math import MinHashSimilarity
except ImportError:
    MinHashSimilarity = None

try:
    from provider_manager import provider_manager
except ImportError:
    provider_manager = None

try:
    from nerves._async_utils import run_async_safely
except ImportError:
    def run_async_safely(coro):
        return asyncio.get_event_loop().run_until_complete(coro)

logger = logging.getLogger("WebAgent")


# ══════════════════════════════════════════════════════════════════════════════
# Normalisation query
# ══════════════════════════════════════════════════════════════════════════════
def _normalize_query(query: str) -> str:
    """'Bitcoinactualités' → 'Bitcoin actualités'"""
    if not query:
        return query
    normalized = re.sub(r"([a-zà-ÿ])([A-ZÀ-Ý])", r"\1 \2", query)
    normalized = re.sub(r"([A-Za-zÀ-ÿ])(\d)", r"\1 \2", normalized)
    normalized = re.sub(r"(\d)([A-Za-zÀ-ÿ])", r"\1 \2", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if normalized != query:
        logger.info("[WebAgent] Query normalisée : '%s' → '%s'", query, normalized)
    return normalized


# ══════════════════════════════════════════════════════════════════════════════
# Filtre URLs stériles
# ══════════════════════════════════════════════════════════════════════════════
try:
    from worker_headless import _is_sterile_url  # type: ignore
except ImportError:
    _STERILE_LOCAL = re.compile(
        r"^https?://(www\.)?(google|bing|duckduckgo|qwant|mojeek|startpage|yahoo|msn)\.[a-z]{2,3}/?$"
        r"|/login|/signin|/auth/|/search\?|[?&]q=|[?&]query="
        r"|news\.google\.com|news\.yahoo\.com/?$|fr\.news\.yahoo\.com",
        re.IGNORECASE,
    )

    def _is_sterile_url(url: str) -> bool:  # type: ignore
        if not url:
            return True
        try:
            parsed = urlparse(url)
        except Exception:
            return True
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return True
        path = (parsed.path or "").strip("/")
        if not path or path in ("index.html", "index.htm", "index.php", "home"):
            return True
        return bool(_STERILE_LOCAL.search(url))


class WebAgent:
    """Agent Web v19.3 — ddgs + Playwright + fallback snippets."""

    _HTTP_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    def __init__(self):
        self.minhash = MinHashSimilarity() if MinHashSimilarity else None
        self._url_cache: set = set()

    # --------------------------------------------------------------------------
    # Playwright helper
    # --------------------------------------------------------------------------
    def _fetch_with_playwright(self, url: str) -> Dict[str, Any]:
        try:
            from worker_headless import HeadlessWorker
            worker = HeadlessWorker(headless=True, timeout_ms=25000)
            result = run_async_safely(worker.fetch_page_content(url))
            return result or {"status": "error", "error": "Résultat vide"}
        except Exception as exc:
            logger.warning("[WebAgent] fetch_playwright échec %s : %s", url, exc)
            return {"status": "error", "error": str(exc)}

    # --------------------------------------------------------------------------
    # ★ v19.3 — Scraping réduit (1500 chars par page)
    # --------------------------------------------------------------------------
    def scrape_url_deep(self, url: str, max_chars: int = 1500) -> Dict[str, str]:
        if _is_sterile_url(url):
            logger.info("[WebAgent] URL stérile ignorée : %s", url[:100])
            return {"url": url, "content": "", "error": "URL stérile"}

        if url in self._url_cache:
            return {"url": url, "content": "", "error": "URL déjà visitée"}
        self._url_cache.add(url)

        # 1. requests d'abord
        try:
            import requests
            from bs4 import BeautifulSoup
            r = requests.get(
                url,
                headers=self._HTTP_HEADERS,
                timeout=10,
                allow_redirects=True,
            )

            if r.status_code == 403:
                logger.debug("[WebAgent] %s → 403 (anti-bot)", url[:80])
            elif "cloudflare" in r.text.lower()[:2000]:
                logger.debug("[WebAgent] %s → Cloudflare challenge", url[:80])
            elif r.status_code == 200 and len(r.text) > 500:
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header",
                                 "noscript", "svg", "aside", "form"]):
                    tag.decompose()
                extracted = []
                for el in soup.find_all(["h1", "h2", "h3", "p", "li"]):
                    text = el.get_text(separator=" ", strip=True)
                    if len(text) > 35:
                        extracted.append(text)
                clean_text = re.sub(r"\s+", " ", "\n\n".join(extracted)).strip()
                if len(clean_text) > 200:
                    logger.info("[WebAgent] ✅ Scraped %s (%d chars)", url[:60], len(clean_text))
                    return {"url": url, "content": clean_text[:max_chars], "error": None}
        except Exception as exc:
            logger.debug("[WebAgent] requests scraping échec : %s", exc)

        # 2. Playwright fallback
        page = self._fetch_with_playwright(url)
        if page.get("status") != "success":
            return {"url": url, "content": "", "error": page.get("error", "Échec fetch")}

        html = page.get("html", "") or ""
        if not html:
            return {"url": url, "content": "", "error": "HTML vide"}

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header",
                             "noscript", "svg", "aside", "form"]):
                tag.decompose()
            extracted_blocks = []
            for element in soup.find_all(["h1", "h2", "h3", "p", "li", "pre", "code"]):
                text = element.get_text(separator=" ", strip=True)
                if len(text) > 35:
                    extracted_blocks.append(text)
            clean_text = re.sub(r"\s+", " ", "\n\n".join(extracted_blocks)).strip()
            if len(clean_text) > 200:
                return {
                    "url": url,
                    "content": clean_text[:max_chars],
                    "error": None,
                }
            return {"url": url, "content": "", "error": "Contenu trop court"}
        except Exception as exc:
            return {"url": url, "content": "", "error": str(exc)}

    # --------------------------------------------------------------------------
    # ddgs (recherche principale — 0 clé)
    # --------------------------------------------------------------------------
    def _search_ddgs(self, query: str, limit: int) -> List[Dict[str, str]]:
        try:
            from ddgs import DDGS
            t0 = time.monotonic()
            raw = DDGS().text(query, max_results=limit * 2)
            elapsed_ms = (time.monotonic() - t0) * 1000

            if not raw:
                logger.warning("[WebAgent/ddgs] 0 résultat (%.0fms)", elapsed_ms)
                return []

            results = []
            for item in raw:
                url = item.get("href", "") or item.get("url", "")
                title = item.get("title", "")
                snippet = item.get("body", "") or item.get("snippet", "")
                if not url or not title:
                    continue
                if _is_sterile_url(url):
                    continue
                results.append({"title": title, "url": url, "snippet": snippet})
                if len(results) >= limit:
                    break

            logger.info("[WebAgent/ddgs] ✅ %d résultats (%.0fms)", len(results), elapsed_ms)
            return results
        except Exception as exc:
            logger.warning("[WebAgent/ddgs] échec : %s", exc)
            return []

    # --------------------------------------------------------------------------
    # Playwright search (dernier recours)
    # --------------------------------------------------------------------------
    def _search_playwright(self, query: str, limit: int) -> List[Dict[str, str]]:
        try:
            from worker_headless import HeadlessWorker
            worker = HeadlessWorker(headless=True, timeout_ms=15000)
            leads = run_async_safely(
                worker.search_and_extract_leads(query, limit=limit * 2)
            )
            if not leads:
                return []
            results = []
            for lead in leads:
                url = lead.get("source_url", "")
                title = lead.get("title", "")
                snippet = lead.get("snippet", "")
                if url and title and not _is_sterile_url(url):
                    results.append({"title": title, "url": url, "snippet": snippet})
                    if len(results) >= limit:
                        break
            logger.info("[WebAgent/Playwright] %d résultats", len(results))
            return results
        except Exception as exc:
            logger.warning("[WebAgent/Playwright] échec : %s", exc)
            return []

    # --------------------------------------------------------------------------
    # CASCADE : ddgs → Playwright
    # --------------------------------------------------------------------------
    def search_candidate_links(self, query: str, limit: int = 4) -> List[Dict[str, str]]:
        normalized = _normalize_query(query)
        logger.info("[WebAgent] Recherche pour : '%s'", normalized)

        all_results: List[Dict[str, str]] = []
        seen_urls: set = set()

        partial = self._search_ddgs(normalized, limit)
        for r in partial:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)

        if len(all_results) < 2:
            logger.info("[WebAgent] ddgs insuffisant (%d) → Playwright", len(all_results))
            partial2 = self._search_playwright(normalized, limit)
            for r in partial2:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)

        final = all_results[:limit]
        logger.info("[WebAgent] ✅ TOTAL : %d résultats uniques", len(final))
        return final

    # --------------------------------------------------------------------------
    # Wikipedia fallback
    # --------------------------------------------------------------------------
    def _search_wikipedia_fallback(self, query: str, limit: int = 3) -> List[Dict[str, str]]:
        try:
            import requests
            url = (
                f"https://fr.wikipedia.org/w/api.php?action=opensearch"
                f"&search={urllib.parse.quote(query)}&limit={limit}"
                f"&namespace=0&format=json"
            )
            headers = {
                "User-Agent": "BEK-WebAgent/1.9 (https://bek.local; contact@bek.local)",
                "Accept": "application/json",
            }
            res = requests.get(url, timeout=8, headers=headers)
            if res.status_code == 200:
                data = res.json()
                titles = data[1] if len(data) > 1 else []
                snippets = data[2] if len(data) > 2 else []
                urls = data[3] if len(data) > 3 else []
                results = [
                    {"title": t, "snippet": s, "url": u}
                    for t, s, u in zip(titles, snippets, urls)
                ]
                return [r for r in results if not _is_sterile_url(r["url"])]
        except Exception as exc:
            logger.debug("[WebAgent] Wikipedia fallback échec : %s", exc)
        return []

    # --------------------------------------------------------------------------
    # ★ v19.3 — Swarm avec corpus réduit (2500 chars)
    # --------------------------------------------------------------------------
    def synthesize_with_swarm(self, query: str, deep_corpus: str) -> str:
        if not deep_corpus.strip():
            return "Aucun contenu textuel suffisant pour alimenter ReflexionSwarm."

        # ★ v19.3 — Corpus réduit à 2500 chars pour Groq 8000 TPM
        corpus_short = deep_corpus[:2500]

        prompt_debate = [
            {
                "role": "system",
                "content": (
                    "Tu es un analyste d'actualités. "
                    "Résume les informations clés du corpus ci-dessous en français, "
                    "en citant les sources et les dates. Sois concis et factuel."
                ),
            },
            {
                "role": "user",
                "content": f"Sujet : {query}\n\nCorpus :\n{corpus_short}",
            },
        ]

        if provider_manager:
            try:
                chunks = []
                for chunk_item in provider_manager.execute_chat_stream(
                    messages=prompt_debate,
                    provider="groq",
                    model="openai/gpt-oss-120b",
                    temperature=0.3,
                    max_tokens=1200,
                ):
                    if "chunk" in chunk_item:
                        chunks.append(chunk_item["chunk"])
                result = "".join(chunks)
                if result.strip():
                    return result
            except Exception as e:
                logger.warning("Échec synthèse provider_manager : %s", e)

        # Fallback : retourner le corpus tronqué
        return f"**Corpus brut (extraits)** :\n\n{corpus_short}"

    # --------------------------------------------------------------------------
    # ★ v19.3 — Persistance avec extrait réduit (500 chars)
    # --------------------------------------------------------------------------
    def persist_extracted_knowledge(self, pages: List[Dict[str, Any]], query: str):
        for page in pages:
            if not page.get("content"):
                continue
            # ★ v19.3 — Extrait réduit à 500 chars
            vector_payload = (
                f"Étude Web sur '{query}' | {page['title']} ({page['url']})\n"
                f"Extrait : {page['content'][:500]}"
            )
            try:
                save_to_memory(vector_payload)
            except Exception as err:
                logger.warning("Erreur indexation vectorielle : %s", err)

        logger.debug("[WebAgent] Persistance Pinecone OK (%d pages)", len(pages))

    # --------------------------------------------------------------------------
    # Pipeline
    # --------------------------------------------------------------------------
    def run_pipeline(self, query: str = "Architectures multi-agents 2026") -> str:
        logger.info("[WebAgent] Pipeline démarré pour : '%s'", query)

        self._url_cache = set()

        candidates = self.search_candidate_links(query, limit=3)

        if len(candidates) < 2:
            logger.info("[WebAgent] Peu de candidats → Wikipedia fallback")
            wiki = self._search_wikipedia_fallback(query, limit=3)
            existing = {c["url"] for c in candidates}
            for wc in wiki:
                if wc["url"] not in existing:
                    candidates.append(wc)
                    existing.add(wc["url"])

        if not candidates:
            return (
                f"ℹ️ Aucune source éditoriale fiable trouvée pour : '{query}'.\n"
                f"→ Essayez une requête plus spécifique."
            )

        # Scraping parallèle
        scraped_pages = []
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {
                executor.submit(self.scrape_url_deep, item["url"]): item
                for item in candidates if item.get("url")
            }
            for future in as_completed(future_to_url):
                meta = future_to_url[future]
                try:
                    res = future.result()
                    if res.get("content"):
                        scraped_pages.append({
                            "title": meta["title"],
                            "url": meta["url"],
                            "snippet": meta.get("snippet", ""),
                            "content": res["content"],
                        })
                except Exception as exc:
                    logger.warning("Erreur scraping : %s", exc)

        # Fallback snippets si scraping échoue
        if not scraped_pages:
            logger.warning(
                "[WebAgent] Scraping échoué (%d URLs) → fallback snippets",
                len(candidates),
            )
            report_sections = [
                f"## 🌐 Résultats de recherche : *{query}*",
                f"*{len(candidates)} source(s) trouvée(s) (extraits rapides)*\n",
                "### 📑 Sources",
            ]
            for idx, c in enumerate(candidates, 1):
                title = c.get("title", "Sans titre")
                url = c.get("url", "")
                snippet = c.get("snippet", "")
                report_sections.append(f"**{idx}. {title}**")
                report_sections.append(f"- **URL :** <{url}>")
                if snippet:
                    report_sections.append(f"- **Résumé :** {snippet}\n")
                else:
                    report_sections.append("")

            report_sections.append(
                "### ⚠️ Note\n"
                "Extraction complète impossible (protection anti-bot).\n"
                "Voici les résultats de recherche avec leurs résumés."
            )
            return "\n".join(report_sections)

        # Persistance
        self.persist_extracted_knowledge(scraped_pages, query)

        # ★ v19.3 — Corpus compact pour le LLM (limite Groq 8000 TPM)
        corpus_builder = []
        for page in scraped_pages:
            # Chaque source contribue ~800 chars max
            corpus_builder.append(
                f"[{page['title']}] ({page['url']})\n{page['content'][:800]}"
            )

        full_corpus = "\n\n---\n\n".join(corpus_builder)

        report_sections = [
            f"## 🌐 Rapport de Veille : *{query}*",
            f"*{len(scraped_pages)} source(s) analysée(s)*\n",
            "### 📑 Sources",
        ]

        for idx, page in enumerate(scraped_pages, 1):
            report_sections.append(f"**{idx}. {page['title']}**")
            report_sections.append(f"- **URL :** <{page['url']}>")
            report_sections.append(f"- **Extrait :** {page['content'][:300]}...\n")

        report_sections.append("### ⚔️ Synthèse")
        swarm_verdict = self.synthesize_with_swarm(query, full_corpus)
        report_sections.append(swarm_verdict)

        return "\n".join(report_sections)


web_agent_instance = WebAgent()