# -*- coding: utf-8 -*-
# ==============================================================================
# web_agent.py — AGENT DE RECHERCHE PROFONDE (BEK-v22.5 — LVC-Web Smart)
# ★ FIX #4 — provider Groq au lieu de nvidia/llama-4-scout (404)
# ★ FIX #5 — Intégration de lvc_smart.py (smart_truncate + clean_boilerplate)
# ==============================================================================

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from memory import save_to_memory

# ★ FIX #5 : Import du module d'optimisation généré par Codex
try:
    from lvc_smart import smart_truncate, clean_boilerplate
except ImportError:
    # Fallback si le fichier n'est pas encore là
    def smart_truncate(texte: str, length: int = 4000) -> str:
        return texte[:length] if len(texte) > length else texte
    def clean_boilerplate(texte: str) -> str:
        return texte

try:
    from provider_manager import provider_manager
except ImportError:
    provider_manager = None

try:
    from nerves._async_utils import run_async_safely
except ImportError:
    def run_async_safely(coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, coro).result(timeout=20)
            return loop.run_until_complete(coro)
        except Exception:
            return asyncio.run(coro)

logger = logging.getLogger("WebAgent")

_PERTINENCE_STOPWORDS = {
    "cherche", "chercher", "recherche", "rechercher", "trouve", "trouver",
    "donne", "donner", "montre", "montrer", "résume", "résumer",
    "news", "actualité", "actualités", "nouvelle", "nouvelles",
    "aujourd'hui", "aujourd", "hui", "maintenant", "actuel", "actuelle",
    "récent", "récente", "dernière", "dernier", "dernières", "derniers",
    "les", "le", "la", "un", "une", "des", "du", "de", "d",
    "et", "ou", "en", "au", "aux", "ce", "cette", "ces", "cet",
    "sur", "sous", "dans", "par", "pour", "avec", "sans",
    "est", "sont", "été", "être", "a", "à", "y",
    "the", "of", "to", "in", "on", "at", "by", "for",
    "brain", "active", "mode", "orchestrateur", "suprême", "mission",
    "utilise", "utiliser", "outil", "briques", "étape", "étapes",
}

def _normalize_query(query: str) -> str:
    if not query:
        return query
    normalized = re.sub(r"([a-zà-ÿ])([A-ZÀ-Ý])", r"\1 \2", query)
    return re.sub(r"\s+", " ", normalized).strip()

def _to_search_engine_query(query: str, max_words: int = 8) -> str:
    clean = _normalize_query(query)
    if len(clean) <= 80 and len(clean.split()) <= max_words:
        return clean
    words = re.findall(r"\b[a-zà-ÿA-ZÀ-Ý0-9]{3,}\b", clean.lower())
    keywords = [w for w in words if w not in _PERTINENCE_STOPWORDS]
    return " ".join(keywords[:max_words]) or clean[:80]

try:
    from worker_headless import _is_sterile_url  # type: ignore
except ImportError:
    _STERILE_LOCAL = re.compile(
        r"^https?://(www\.)?(google|bing|duckduckgo|qwant|mojeek|startpage|yahoo|msn)\.[a-z]{2,3}/?$"
        r"|/login|/signin|/auth/|/search\?|[?&]q=|[?&]query=",
        re.IGNORECASE,
    )
    def _is_sterile_url(url: str) -> bool:
        if not url:
            return True
        try:
            parsed = urlparse(url)
        except Exception:
            return True
        return parsed.scheme not in ("http", "https") or not parsed.netloc or bool(_STERILE_LOCAL.search(url))

class WebAgent:
    _HTTP_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def __init__(self):
        self._url_cache: set = set()
        self._firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
        self._ddgs_module = None
        self._nodriver_module = None

    def _get_ddgs(self):
        if self._ddgs_module is None:
            from ddgs import DDGS
            self._ddgs_module = DDGS
        return self._ddgs_module

    def _get_nodriver(self):
        if self._nodriver_module is None:
            import nodriver as uc
            self._nodriver_module = uc
        return self._nodriver_module

    def _search_firecrawl(self, query: str, limit: int) -> List[Dict[str, str]]:
        if not self._firecrawl_key:
            return []
        try:
            import requests
            r = requests.post(
                "https://api.firecrawl.dev/v1/search",
                headers={"Authorization": f"Bearer {self._firecrawl_key}", "Content-Type": "application/json"},
                json={"query": query, "limit": limit}, timeout=6,
            )
            if r.status_code == 200:
                data = r.json().get("data", [])
                results = []
                for item in data:
                    url = item.get("url", "")
                    title = item.get("title", "") or url
                    snippet = item.get("description", "") or item.get("markdown", "")[:300]
                    if url and not _is_sterile_url(url):
                        results.append({"title": title, "url": url, "snippet": snippet, "markdown": item.get("markdown", "")})
                if results:
                    logger.info("[WebAgent/Firecrawl] 🔥 %d résultats trouvés", len(results))
                    return results[:limit]
        except Exception as exc:
            logger.debug("[WebAgent/Firecrawl] Ignoré : %s", exc)
        return []

    def _search_ddgs(self, query: str, limit: int) -> List[Dict[str, str]]:
        try:
            DDGS = self._get_ddgs()
            raw = DDGS().text(query, max_results=limit * 2)
            if not raw: return []
            results = []
            for item in raw:
                url = item.get("href", "") or item.get("url", "")
                title = item.get("title", "")
                snippet = item.get("body", "") or item.get("snippet", "")
                if url and title and not _is_sterile_url(url):
                    results.append({"title": title, "url": url, "snippet": snippet})
                    if len(results) >= limit: break
            return results
        except Exception:
            return []

    def search_candidate_links(self, query: str, limit: int = 5) -> List[Dict[str, str]]:
        search_q = _to_search_engine_query(query)
        all_results: List[Dict[str, str]] = []
        seen_urls: set = set()

        def _add_items(items):
            for r in items:
                u = r.get("url", "")
                if u and u not in seen_urls:
                    seen_urls.add(u); all_results.append(r)

        _add_items(self._search_firecrawl(search_q, limit))
        if len(all_results) < limit:
            _add_items(self._search_ddgs(search_q, limit))
        return all_results[:limit]

    def _scrape_with_firecrawl(self, url: str, max_chars: int = 1500) -> Optional[str]:
        if not self._firecrawl_key: return None
        try:
            import requests
            r = requests.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={"Authorization": f"Bearer {self._firecrawl_key}", "Content-Type": "application/json"},
                json={"url": url, "formats": ["markdown"]}, timeout=8,
            )
            if r.status_code == 200:
                md = r.json().get("data", {}).get("markdown", "")
                if md and len(md) > 150: return md[:max_chars]
        except Exception: pass
        return None

    def _fetch_with_nodriver(self, url: str) -> Optional[str]:
        try:
            uc = self._get_nodriver()
            async def _run():
                browser = await uc.start(headless=True)
                try:
                    page = await browser.get(url)
                    await page.sleep(1.5)
                    return await page.get_content()
                finally:
                    browser.stop()
            return run_async_safely(_run())
        except Exception:
            return None

    def scrape_url_deep(self, url: str, max_chars: int = 1200) -> Dict[str, str]:
        if _is_sterile_url(url) or url in self._url_cache:
            return {"url": url, "content": "", "error": "URL ignorée"}
        self._url_cache.add(url)

        fc_md = self._scrape_with_firecrawl(url, max_chars=max_chars)
        if fc_md:
            return {"url": url, "content": fc_md, "error": None}

        try:
            import requests
            from bs4 import BeautifulSoup
            r = requests.get(url, headers=self._HTTP_HEADERS, timeout=5, allow_redirects=True)
            if r.status_code == 200 and len(r.text) > 400:
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "aside", "form", "iframe"]):
                    tag.decompose()
                main_content = soup.find("main") or soup.find("article") or soup.body
                if main_content:
                    extracted = [el.get_text(separator=" ", strip=True) for el in main_content.find_all(["h1", "h2", "h3", "p", "li"]) if len(el.get_text(strip=True)) > 30]
                    clean_text = re.sub(r"\s+", " ", "\n\n".join(extracted)).strip()
                    if len(clean_text) > 150:
                        return {"url": url, "content": clean_text[:max_chars], "error": None}
        except Exception: pass

        nodriver_html = self._fetch_with_nodriver(url)
        if nodriver_html:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(nodriver_html, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                clean_text = re.sub(r"\s+", " ", soup.get_text()).strip()
                if len(clean_text) > 150:
                    return {"url": url, "content": clean_text[:max_chars], "error": None}
            except Exception: pass
        return {"url": url, "content": "", "error": "Échec extraction"}

    def synthesize_with_swarm(self, query: str, deep_corpus: str, source_pages: Optional[List] = None) -> str:
        if not deep_corpus.strip():
            return "Aucun contenu textuel pertinent n'a pu être extrait du web."

        tools_list = """
=== OUTILS DISPONIBLES (à utiliser si nécessaire) ===
Tu peux invoquer ces outils en utilisant [ACTION:nom_outil]{json}[/ACTION] :
- web_search : recherche web
- headless_scrape : scrape une URL
- codex_loop : génère du code
- save_memory : enregistre en mémoire
- cognitive_critique : critique ton propre travail
- ga_get_best : récupère le meilleur gène GA
- ga_record_result : enregistre un feedback
- ga_evolve : fait muter le GA

INSTRUCTION : Si l'utilisateur te demande d'exécuter plusieurs étapes complexes, tu es autorisé à invoquer ces outils pour les accomplir.
"""

        prompt = (
            f"Tu es l'analyste de recherche expert de BEK v22.\n"
            f"{tools_list}\n"
            f"QUESTION : {query}\n\n"
            f"CORPUS DE SOURCES VÉRIFIÉES :\n{deep_corpus}\n\n"
            f"INSTRUCTIONS STRICTES :\n"
            f"1. Rédige une réponse claire, structurée, professionnelle et factuelle en français.\n"
            f"2. Appuie-toi EXCLUSIVEMENT sur les sources ci-dessus.\n"
            f"3. Intègre des tableaux ou des listes à puces si cela rend l'information plus lisible.\n"
            f"4. Cite rigoureusement chaque source avec son URL exacte sous forme de lien markdown."
        )

        if provider_manager:
            try:
                chunks = []
                for item in provider_manager.execute_chat_stream(
                    messages=[{"role": "user", "content": prompt}],
                    provider="groq", model="openai/gpt-oss-20b",
                ):
                    if "chunk" in item: chunks.append(item["chunk"])
                res = "".join(chunks).strip()
                if res: return res
            except Exception: pass

        return f"### Synthèse des sources extraites :\n\n{deep_corpus[:3500]}"

    def run_pipeline(self, query: str, max_sources: int = 4) -> str:
        self._url_cache.clear()
        candidates = self.search_candidate_links(query, limit=max_sources)
        if not candidates:
            return f"⚠️ Aucun résultat pertinent trouvé pour « {_to_search_engine_query(query)} »."

        scraped_map: Dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_cand = {
                executor.submit(self.scrape_url_deep, c["url"], 1200): c
                for c in candidates if not c.get("markdown")
            }
            for future in as_completed(future_to_cand):
                cand = future_to_cand[future]
                try:
                    res = future.result(timeout=8)
                    if res and res.get("content"):
                        scraped_map[cand["url"]] = res["content"]
                except Exception: pass

        corpus_parts = []
        source_pages = []
        for idx, c in enumerate(candidates, start=1):
            url = c.get("url", "")
            title = c.get("title", "Source Web")
            snippet = c.get("snippet", "")
            deep_text = c.get("markdown") or scraped_map.get(url, "")
            # ★ LVC-WEB : On limite chaque bloc à 800 chars
            content_block = deep_text[:800] if deep_text else snippet[:800]
            if not content_block: continue
            corpus_parts.append(f"[Source {idx}] Titre : {title}\nURL : {url}\nDétails : {content_block}\n")
            source_pages.append({"index": idx, "title": title, "url": url})

        deep_corpus = "\n---\n".join(corpus_parts)
        
        # ★ FIX #5 : Nettoyage et troncature intelligente (LVC-Smart)
        total_chars_brut = sum(len(c.get("markdown", "")) or len(scraped_map.get(c["url"], "")) for c in candidates)
        
        # 1. On nettoie les cookies/menus (clean_boilerplate)
        deep_corpus_clean = clean_boilerplate(deep_corpus)
        
        # 2. On tronque intelligemment au dernier point (smart_truncate)
        if len(deep_corpus_clean) > 4000:
            logger.info("[WebAgent] ✂️ LVC-Smart : Nettoyage et troncature intelligente activée.")
            deep_corpus_final = smart_truncate(deep_corpus_clean, length=4000)
        else:
            deep_corpus_final = deep_corpus_clean
            
        # 3. Facture
        tok_brut = total_chars_brut // 3
        tok_final = len(deep_corpus_final) // 3
        economie = tok_brut - tok_final
        if economie > 0:
            logger.info("[💰 FACTURE] WebAgent : %d tokens -> %d tokens | Économie : -%d tokens (-%d%%)", 
                        tok_brut, tok_final, economie, int((economie / max(1, tok_brut)) * 100))

        synthesis = self.synthesize_with_swarm(query, deep_corpus_final, source_pages=source_pages)

        try: save_to_memory(query, synthesis)
        except Exception: pass
        return synthesis

    def quick_search(self, query: str, max_results: int = 3) -> str:
        try:
            candidates = self.search_candidate_links(query, limit=max_results)
            if not candidates:
                return f"Aucun résultat pour : {query}"
            parts = []
            for i, c in enumerate(candidates, 1):
                url = c.get("url", "")
                title = c.get("title", "")
                snippet = c.get("snippet", "")
                scraped = self.scrape_url_deep(url, max_chars=500)
                content = scraped.get("content", "") or snippet
                if content:
                    parts.append(f"[{i}] {title}\nURL: {url}\n{content[:400]}")
            return "\n\n---\n\n".join(parts) if parts else f"Aucun contenu pour : {query}"
        except Exception as e:
            return f"Erreur recherche : {e}"

    def search_documentation(self, topic: str, max_results: int = 4) -> str:
        enhanced = f"{topic} documentation API reference example"
        return self.quick_search(enhanced, max_results=max_results)

    def find_code_example(self, language: str, task: str) -> str:
        query = f"{language} {task} example code snippet"
        return self.quick_search(query, max_results=3)

web_agent_instance = WebAgent()

def web_sync(query: str, **kwargs: Any) -> Dict[str, Any]:
    try:
        synthesis = web_agent_instance.run_pipeline(query)
        if synthesis and "Aucun résultat" not in synthesis and "⚠️" not in synthesis[:5]:
            return {"status": "success", "content": synthesis, "error": None}
        else:
            return {"status": "error", "content": synthesis, "error": "Aucun contenu pertinent trouvé"}
    except Exception as e:
        logger.error("[WebAgent] Erreur critique pipeline : %s", e)
        return {"status": "error", "content": "", "error": str(e)}