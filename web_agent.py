# ==============================================================================
# web_agent.py — AGENT DE RECHERCHE PROFONDE & D'ORCHESTRATION COGNITIVE (BEK-v15)
# DEEP CRAWLING, DÉDUPLICATION MINHASH, PERSISTANCE VECTORIELLE & SYNTHÈSE SWARM
# ------------------------------------------------------------------------------
# CORRECTIF v2 (2026-09-20) :
#   - Remplacement de requests par HeadlessWorker (Playwright) pour le scraping
#
# CORRECTIF v3 (2026-09-22) :
#   - ★ FIX : filtre URLs stériles en sortie de search_candidate_links
#   - ★ FIX : fallback Wikipedia PRIORITAIRE (avant tout autre fallback)
#   - ★ FIX : log explicite quand 0 résultat après filtre
#
# CORRECTIF v17 (2026-09-24) :
#   - ★ FIX : User-Agent Wikipedia (évite 403)
#   - ★ FIX : skip fallback Wikipedia pour requêtes news
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

# --- MODULES SYSTÈME & PERSISTANCE ---
from memory import get_db_connection, save_to_memory

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
# ★ FIX v3 — FILTRE URLs STÉRILES (importé depuis worker_headless si dispo)
# ══════════════════════════════════════════════════════════════════════════════
try:
    from worker_headless import _is_sterile_url  # type: ignore
except ImportError:
    # Fallback local si worker_headless n'est pas importable
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
# ══════════════════════════════════════════════════════════════════════════════
# FIN FIX v3
# ══════════════════════════════════════════════════════════════════════════════


class WebAgent:
    """Agent Web autonome à haute intensité combinant scraping multi-sources
    via Playwright, extraction de texte intégral, déduplication et arbitrage
    ReflexionSwarm.
    """

    def __init__(self):
        self.minhash = MinHashSimilarity() if MinHashSimilarity else None
        self._url_cache: set = set()

    # --------------------------------------------------------------------------
    # Helper Playwright (utilise HeadlessWorker)
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
    # 1. SCRAPING
    # --------------------------------------------------------------------------
    def scrape_url_deep(self, url: str, max_chars: int = 5000) -> Dict[str, str]:
        # ★ FIX v3 : on ne scrape JAMAIS une URL stérile
        if _is_sterile_url(url):
            logger.info("[WebAgent] URL stérile ignorée : %s", url[:100])
            return {"url": url, "content": "", "error": "URL stérile"}

        if url in self._url_cache:
            return {"url": url, "content": "", "error": "URL déjà visitée (cache)"}
        self._url_cache.add(url)

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

            full_text = "\n\n".join(extracted_blocks)
            clean_text = re.sub(r"\s+", " ", full_text).strip()

            return {
                "url": url,
                "content": clean_text[:max_chars] if clean_text else "",
                "error": None if clean_text else "Page vide ou protégée",
            }
        except Exception as exc:
            return {"url": url, "content": "", "error": str(exc)}

    # --------------------------------------------------------------------------
    # 2. RECHERCHE
    # --------------------------------------------------------------------------
    def search_candidate_links(self, query: str, limit: int = 4) -> List[Dict[str, str]]:
        try:
            from worker_headless import HeadlessWorker
            worker = HeadlessWorker(headless=True, timeout_ms=25000)
            leads = run_async_safely(
                worker.search_and_extract_leads(query, limit=limit * 2)
            )
            if not leads:
                logger.info("[WebAgent] search_candidate_links → 0 résultats pour '%s'", query)
                return []

            results = []
            for lead in leads:
                url = lead.get("source_url", "")
                title = lead.get("title", "")
                snippet = lead.get("snippet", "")
                if not url or not title:
                    continue

                # ★ FIX v4 : filtre stérile ASSOUPLI
                if _is_sterile_url(url):
                    from urllib.parse import urlparse as _up
                    try:
                        parsed = _up(url)
                        path = (parsed.path or "").strip("/")
                        if path and not any(
                            x in path.lower()
                            for x in ["search", "login", "signin", "consent"]
                        ):
                            logger.debug("[WebAgent] URL gardée malgré stérile : %s", url[:100])
                        else:
                            logger.debug("[WebAgent] stérile ignoré : %s", url[:100])
                            continue
                    except Exception:
                        continue

                results.append({"title": title, "url": url, "snippet": snippet})
                if len(results) >= limit:
                    break

            logger.info("[WebAgent] search_candidate_links → %d résultats (filtrés)", len(results))
            return results
        except Exception as exc:
            logger.warning("[WebAgent] search_candidate_links exception : %s", exc)
            return []

    # --------------------------------------------------------------------------
    # FALLBACK WIKIPEDIA (v17)
    # --------------------------------------------------------------------------
    def _search_wikipedia_fallback(self, query: str, limit: int = 3) -> List[Dict[str, str]]:
        """
        Fallback Wikipedia — v17 :
        - User-Agent explicite (Wikipedia bloque sinon)
        - Ne déclenche PAS pour les requêtes "news" (Wikipedia n'a pas d'actu)
        """
        # ★ v17 — Skip si c'est une requête de news
        _NEWS_KEYWORDS = (
            "actualité", "actualités", "news", "récent", "récente",
            "dernières", "aujourd'hui", "actuel", "actuelle", "2025", "2026"
        )
        query_lower = (query or "").lower()
        if any(kw in query_lower for kw in _NEWS_KEYWORDS):
            logger.info(
                "[WebAgent] Wikipedia fallback SKIP (requête news : '%s')",
                query[:60]
            )
            return []

        try:
            import requests
            url = (
                f"https://fr.wikipedia.org/w/api.php?action=opensearch"
                f"&search={urllib.parse.quote(query)}&limit={limit}"
                f"&namespace=0&format=json"
            )
            # ★ v17 — User-Agent explicite (sinon 403)
            headers = {
                "User-Agent": "BEK-WebAgent/1.7 (https://bek.local; contact@bek.local)",
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
    # 3. SWARM
    # --------------------------------------------------------------------------
    def synthesize_with_swarm(self, query: str, deep_corpus: str) -> str:
        if not deep_corpus.strip():
            return "Aucun contenu textuel suffisant pour alimenter ReflexionSwarm."

        prompt_debate = [
            {
                "role": "system",
                "content": (
                    "Tu es le superviseur ReflexionSwarm. Analyse le corpus documentaire ci-dessous "
                    "et orchestre un débat contradictoire technique entre :\n"
                    "1. L'Agent Critique (analyse des limites, risques, complexité, failles de sécurité)\n"
                    "2. L'Agent Architecte (mise en avant des gains de scalabilité, protocoles A2A/MCP, résilience)\n"
                    "Conclus par la recommandation concrète de l'architecture hybride la plus optimale."
                ),
            },
            {
                "role": "user",
                "content": f"SUJET DE VEILLE : {query}\n\nCORPUS SCRAPPÉ DU WEB :\n{deep_corpus[:6000]}",
            },
        ]

        if provider_manager:
            try:
                chunks = []
                for chunk_item in provider_manager.execute_chat_stream(
                    messages=prompt_debate,
                    provider="nvidia",
                    model="nvidia/nemotron-3-super-120b-a12b",
                    temperature=0.3,
                    max_tokens=1800,
                ):
                    if "chunk" in chunk_item:
                        chunks.append(chunk_item["chunk"])
                return "".join(chunks)
            except Exception as e:
                logger.warning("Échec de la synthèse via provider_manager : %s", e)

        if ReflexionSwarm:
            try:
                swarm = ReflexionSwarm()
                if hasattr(swarm, "solve"):
                    return str(swarm.solve(query, deep_corpus[:4000]))
            except Exception as exc:
                logger.warning("Échec ReflexionSwarm natif : %s", exc)

        return "Corpus indexé en mémoire. Débat non disponible en mode hors-ligne."

    # --------------------------------------------------------------------------
    # 4. PERSISTANCE
    # --------------------------------------------------------------------------
    def persist_extracted_knowledge(self, pages: List[Dict[str, Any]], query: str):
        for page in pages:
            if not page.get("content"):
                continue

            vector_payload = (
                f"Étude Web approfondie sur '{query}' | Source: {page['title']} ({page['url']})\n"
                f"Extrait condensé : {page['content'][:1500]}"
            )
            try:
                save_to_memory(vector_payload)
            except Exception as err:
                logger.warning("Erreur indexation vectorielle : %s", err)

        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                for page in pages:
                    email_fake = f"source_{abs(hash(page['title'])) % 10000}@bek-intelligence.local"
                    cur.execute(
                        """
                        INSERT INTO contacts (name, email, phone)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING;
                        """,
                        (f"Source: {page['title'][:40]}", email_fake, ""),
                    )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as db_err:
                if conn:
                    conn.rollback()
                    conn.close()
                logger.warning("Erreur écriture Neon DB : %s", db_err)

    # --------------------------------------------------------------------------
    # 5. PIPELINE
    # --------------------------------------------------------------------------
    def run_pipeline(self, query: str = "Architectures multi-agents 2026") -> str:
        logger.info("[WebAgent] Pipeline démarré pour : '%s'", query)

        self._url_cache = set()

        candidates = self.search_candidate_links(query, limit=3)

        # ★ v17 — Politique assouplie
        _NEWS_KEYWORDS = (
            "actualité", "actualités", "news", "récent", "récente",
            "dernières", "aujourd'hui", "actuel", "actuelle"
        )
        _is_news_query = any(kw in (query or "").lower() for kw in _NEWS_KEYWORDS)

        if len(candidates) < 2 and not _is_news_query:
            logger.info("[WebAgent] Peu/pas de candidats valides → fallback Wikipedia")
            wiki_candidates = self._search_wikipedia_fallback(query, limit=3)
            existing_urls = {c["url"] for c in candidates}
            for wc in wiki_candidates:
                if wc["url"] not in existing_urls:
                    candidates.append(wc)
                    existing_urls.add(wc["url"])
        elif _is_news_query and len(candidates) < 2:
            logger.warning(
                "[WebAgent] Requête news : peu de candidats (%d), PAS de fallback Wikipedia",
                len(candidates)
            )

        if not candidates:
            return (
                f"ℹ️ Aucune source éditoriale fiable trouvée pour : '{query}'.\n"
                f"→ Les moteurs de recherche ont tous retourné des pages de navigation "
                f"(homes, recherche, login) qui ont été filtrées.\n"
                f"→ Essayez une requête plus spécifique."
            )

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
                    logger.warning("Erreur scraping worker : %s", exc)

        if not scraped_pages:
            return (
                f"ℹ️ Échec d'extraction du contenu des pages cibles pour '{query}'.\n"
                f"→ {len(candidates)} URLs testées, aucune n'a retourné de contenu.\n"
                f"→ Causes : pages JS-lourdes, protection anti-bot, timeout."
            )

        self.persist_extracted_knowledge(scraped_pages, query)

        corpus_builder = []
        report_sections = [
            f"## 🌐 Rapport d'Ingénierie & Veille Web Approfondie : *{query}*",
            f"*{len(scraped_pages)} sources analysées en profondeur et indexées dans Pinecone & Neon DB*\n",
            "### 📑 Sources Décortiquées",
        ]

        for idx, page in enumerate(scraped_pages, 1):
            report_sections.append(f"**{idx}. {page['title']}**")
            report_sections.append(f"- **URL Source :** <{page['url']}>")
            report_sections.append(f"- **Extrait Principal :** {page['content'][:350]}...\n")
            corpus_builder.append(f"SOURCE [{page['title']}] ({page['url']}) :\n{page['content']}")

        report_sections.append("### ⚔️ Synthèse Arbitrée par ReflexionSwarm")
        swarm_verdict = self.synthesize_with_swarm(query, "\n\n---\n\n".join(corpus_builder))
        report_sections.append(swarm_verdict)

        return "\n".join(report_sections)


web_agent_instance = WebAgent()