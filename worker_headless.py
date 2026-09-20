# -*- coding: utf-8 -*-
"""
BEK-v15.3 HYBRID - Worker Headless Autonome (Playwright Engine Hardened)
-----------------------------------------------------------------------
Service d'extraction et de rendu web headless non‑interactif.

CORRECTIF v14 :
- Fallback anti-zéro restauré : si le filtre _is_relevant rejette TOUT mais
  que des résultats bruts existent, on les retourne (le LLM les synthétisera
  et écartera le bruit). Évite les "0 résultats" quand le LLM reformule
  la requête (traduction, gonflage) et fait perdre les mots-clés.
- Le reste conservé : stop-list FR+EN, mot entier \b, seuil 2 lettres,
  cascade Google/DDG/Bing, Bing en-US puis fr-FR, decode base64url.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("bek.worker_headless")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [HeadlessWorker] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

WORKSPACE_DIR = Path(__file__).resolve().parent


class HeadlessWorker:
    """Moteur Playwright headless durci pour Windows & Linux."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 BEK-Agent/15.3"
    )

    BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}
    _MAX_CONCURRENT_TASKS = 3

    _USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    _STOPWORDS = {
        "le", "la", "les", "un", "une", "des", "du", "de", "d",
        "et", "ou", "en", "au", "aux", "ce", "ces", "cet", "cette",
        "il", "elle", "on", "nous", "vous", "ils", "elles",
        "je", "tu", "me", "te", "se", "lui", "leur",
        "y", "ne", "pas", "plus", "que", "qui", "quoi",
        "sur", "sous", "dans", "par", "pour", "avec", "sans",
        "est", "sont", "été", "être", "avoir", "fait",
        "the", "an", "of", "to", "in", "on", "at", "by", "for",
        "is", "are", "was", "were", "be", "been", "being",
        "it", "its", "as", "or", "and", "but", "if", "so", "no",
        "do", "does", "did", "has", "have", "had", "this", "that",
        "with", "from", "will", "would", "can", "could", "should",
        "up", "down", "out", "off", "over", "all", "any", "some",
    }

    _SEARCH_HEADERS = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
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

    def __init__(self, headless: bool = True, timeout_ms: int = 30000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._running = False
        self._semaphore = asyncio.Semaphore(self._MAX_CONCURRENT_TASKS)
        self._state_lock = asyncio.Lock()

    # ==================================================================
    # PLAYWRIGHT
    # ==================================================================
    async def _route_interceptor(self, route: Any) -> None:
        try:
            if route.request.resource_type in self.BLOCKED_RESOURCE_TYPES:
                await route.abort()
            else:
                await route.continue_()
        except Exception:
            try:
                await route.continue_()
            except Exception:
                pass

    async def _launch_browser(self):
        from playwright.async_api import async_playwright
        playwright_obj = await async_playwright().start()
        browser = await playwright_obj.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-gpu",
                "--disable-extensions", "--disable-background-networking",
                "--disable-default-apps", "--no-first-run",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=self.DEFAULT_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        return playwright_obj, browser, context

    async def fetch_page_content(self, url: str) -> Dict[str, Any]:
        async with self._semaphore:
            try:
                from playwright.async_api import async_playwright  # noqa: F401
            except ImportError:
                logger.error("Playwright non installé.")
                return {"status": "error", "error": "Playwright non installé"}

            logger.info("Démarrage de l'extraction sur : %s", url)
            start_time = asyncio.get_event_loop().time()
            playwright_obj = None
            browser = None
            context = None
            page = None

            try:
                playwright_obj, browser, context = await self._launch_browser()
                page = await context.new_page()
                await page.route("**/*", self._route_interceptor)
                response = await page.goto(
                    url, timeout=self.timeout_ms, wait_until="domcontentloaded"
                )
                status_code = response.status if response else 0
                title = await page.title()
                content = await page.content()
                duration_ms = round(
                    (asyncio.get_event_loop().time() - start_time) * 1000, 2
                )
                logger.info(
                    "Extraction réussie (%d octets) en %s ms",
                    len(content), duration_ms,
                )
                return {
                    "status": "success", "url": url,
                    "http_status": status_code, "title": title,
                    "content_length": len(content), "html": content,
                    "duration_ms": duration_ms,
                }
            except Exception as exc:
                logger.error("Erreur navigation %s : %s", url, exc)
                return {"status": "error", "url": url, "error": str(exc)}
            finally:
                if page:
                    try: await page.close()
                    except Exception: pass
                if context:
                    try: await context.close()
                    except Exception: pass
                if browser:
                    try: await browser.close()
                    except Exception: pass
                if playwright_obj:
                    try: await playwright_obj.stop()
                    except Exception: pass

    # ==================================================================
    # HELPERS
    # ==================================================================
    @staticmethod
    def _clean_ddg_url(raw: str) -> str:
        if not raw:
            return ""
        if raw.startswith("//"):
            raw = "https:" + raw
        if "uddg=" in raw:
            try:
                return unquote(raw.split("uddg=", 1)[1].split("&", 1)[0])
            except Exception:
                return raw
        return raw

    @staticmethod
    def _resolve_bing_url(raw: str) -> str:
        if not raw:
            return ""
        if "bing.com/ck/a" not in raw:
            return raw
        try:
            parsed = urlparse(raw)
            params = parse_qs(parsed.query)
            u = params.get("u", [None])[0]
            if not u:
                return raw
            if u.startswith("a1"):
                u = u[2:]
            padding = "=" * (-len(u) % 4)
            decoded = base64.urlsafe_b64decode(u + padding).decode(
                "utf-8", errors="ignore"
            )
            if decoded.startswith("http"):
                return decoded
        except Exception:
            pass
        return raw

    def _is_relevant(self, query: str, title: str, url: str) -> bool:
        keywords = [
            w.lower() for w in re.findall(r"\w+", query or "")
            if len(w) >= 2 and w.lower() not in self._STOPWORDS
        ]
        if not keywords:
            return True
        haystack = f"{title or ''} {url or ''}".lower()
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", haystack):
                return True
        return False

    # ==================================================================
    # MOTEURS PLAYWRIGHT
    # ==================================================================
    async def _dismiss_google_consent(self, page: Any) -> None:
        selectors = [
            "button:has-text('Tout accepter')",
            "button:has-text('J\\'accepte')",
            "button:has-text('Accept all')",
            "button#L2AGLb",
            "button[aria-label*='Accept']",
            "button[aria-label*='accepter']",
        ]
        for sel in selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(500)
                    return
            except Exception:
                continue

    async def _search_google_playwright(
        self, context: Any, query: str, limit: int
    ) -> List[Dict[str, str]]:
        page = await context.new_page()
        try:
            try:
                await page.goto(
                    "https://www.google.fr/", timeout=15000,
                    wait_until="domcontentloaded",
                )
                await page.wait_for_timeout(800)
                await self._dismiss_google_consent(page)
            except Exception:
                pass

            url = f"https://www.google.com/search?q={quote_plus(query)}&hl=fr&num=20"
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            try:
                await page.wait_for_selector("div.g, div[data-hveid]", timeout=8000)
            except Exception:
                pass
            await page.wait_for_timeout(1500)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            results: List[Dict[str, str]] = []
            fallback: List[Dict[str, str]] = []
            for div in soup.select("div.g, div[data-hveid]")[: limit * 5]:
                a = div.select_one("a")
                if not a:
                    continue
                href = a.get("href", "")
                if not href.startswith("http"):
                    continue
                if "google.com/url" in href:
                    try:
                        q = parse_qs(urlparse(href).query).get("q", [None])[0]
                        if q:
                            href = q
                    except Exception:
                        pass
                h3 = div.select_one("h3")
                title = h3.get_text(strip=True) if h3 else ""
                if not title:
                    continue
                sn = div.select_one("div[data-sncf], span.aCOpRe, div.VwiC3b")
                snippet = sn.get_text(strip=True) if sn else ""
                item = {"title": title, "url": href, "snippet": snippet}
                if self._is_relevant(query, title, href):
                    results.append(item)
                else:
                    fallback.append(item)
                if len(results) >= limit:
                    break

            # v14 — fallback anti-zéro
            if not results and fallback:
                logger.info("[search/pw] Google → filtre strict, fallback brut (%d)", len(fallback))
                results = fallback[:limit]

            if results:
                logger.info("[search/pw] Google → %d résultats", len(results))
            else:
                logger.warning("[search/pw] Google → 0 résultats")
            return results
        except Exception as exc:
            logger.warning("[search/pw] Google échec : %s", exc)
            return []
        finally:
            try: await page.close()
            except Exception: pass

    async def _search_ddg_lite_playwright(
        self, context: Any, query: str, limit: int
    ) -> List[Dict[str, str]]:
        page = await context.new_page()
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1800)
            html = await page.content()

            try:
                (WORKSPACE_DIR / "_debug_ddg_lite.html").write_text(html, encoding="utf-8")
            except Exception:
                pass

            html_lower = html.lower()
            if "anomaly" in html_lower or "captcha" in html_lower or "email us" in html_lower:
                logger.warning("[search/pw] DDG Lite → page anti-bot détectée")
                return []

            soup = BeautifulSoup(html, "html.parser")
            anchors = soup.select(
                "a.result__a, a.result__url, .result__title a, a.result-link"
            )

            results: List[Dict[str, str]] = []
            fallback: List[Dict[str, str]] = []
            for a in anchors[: limit * 3]:
                title = a.get_text(strip=True)
                url_clean = self._clean_ddg_url(a.get("href", ""))
                snippet = ""
                parent = a.find_parent("div", class_="result__body")
                if parent:
                    sn = parent.select_one(".result__snippet")
                    if sn:
                        snippet = sn.get_text(strip=True)
                if not snippet:
                    tr = a.find_parent("tr")
                    if tr:
                        next_tr = tr.find_next_sibling("tr")
                        if next_tr:
                            sn = next_tr.select_one("td.result-snippet")
                            if sn:
                                snippet = sn.get_text(strip=True)

                if not title or not url_clean or not url_clean.startswith("http"):
                    continue
                item = {"title": title, "url": url_clean, "snippet": snippet}
                if self._is_relevant(query, title, url_clean):
                    results.append(item)
                else:
                    fallback.append(item)
                if len(results) >= limit:
                    break

            if not results and fallback:
                logger.info("[search/pw] DDG Lite → filtre strict, fallback brut (%d)", len(fallback))
                results = fallback[:limit]

            if results:
                logger.info("[search/pw] DDG Lite → %d résultats", len(results))
            else:
                logger.warning("[search/pw] DDG Lite → 0 résultats")
            return results
        except Exception as exc:
            logger.warning("[search/pw] DDG Lite échec : %s", exc)
            return []
        finally:
            try: await page.close()
            except Exception: pass

    async def _search_bing_once(
        self, context: Any, query: str, limit: int, market: str
    ) -> List[Dict[str, str]]:
        page = await context.new_page()
        try:
            try:
                await page.goto(
                    "https://www.bing.com/", timeout=15000,
                    wait_until="domcontentloaded",
                )
                await page.wait_for_timeout(800)
            except Exception:
                pass

            lang = "en" if market.startswith("en") else "fr"
            url = (
                f"https://www.bing.com/search?q={quote_plus(query)}"
                f"&mkt={market}&setlang={lang}"
            )
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            try:
                await page.wait_for_selector("li.b_algo h2 a", timeout=8000)
            except Exception:
                pass
            await page.wait_for_timeout(1500)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            results: List[Dict[str, str]] = []
            for li in soup.select("li.b_algo")[: limit * 4]:
                a = li.select_one("h2 a")
                if not a:
                    continue
                title = a.get_text(strip=True)
                real_url = self._resolve_bing_url(a.get("href", ""))
                if not title or not real_url or not real_url.startswith("http"):
                    continue
                if not self._is_relevant(query, title, real_url):
                    continue
                sn = li.select_one(".b_caption p")
                snippet = sn.get_text(strip=True) if sn else ""
                results.append({
                    "title": title, "url": real_url, "snippet": snippet,
                })
                if len(results) >= limit:
                    break
            return results
        except Exception as exc:
            logger.debug("[search/pw] Bing (%s) échec : %s", market, exc)
            return []
        finally:
            try: await page.close()
            except Exception: pass

    async def _search_bing_playwright(
        self, context: Any, query: str, limit: int
    ) -> List[Dict[str, str]]:
        results = await self._search_bing_once(context, query, limit, "en-US")
        if results:
            logger.info("[search/pw] Bing (en-US) → %d résultats", len(results))
            return results
        results = await self._search_bing_once(context, query, limit, "fr-FR")
        if results:
            logger.info("[search/pw] Bing (fr-FR) → %d résultats", len(results))
            return results
        logger.warning("[search/pw] Bing → 0 résultats (en-US + fr-FR)")
        return []

    # ==================================================================
    # FALLBACK REQUESTS
    # ==================================================================
    def _build_session(self) -> requests.Session:
        s = requests.Session()
        retries = Retry(
            total=2, backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
        )
        s.mount("https://", HTTPAdapter(max_retries=retries))
        s.mount("http://", HTTPAdapter(max_retries=retries))
        headers = dict(self._SEARCH_HEADERS)
        headers["User-Agent"] = random.choice(self._USER_AGENTS)
        s.headers.update(headers)
        return s

    def _search_ddg_html(self, query: str, limit: int) -> List[Dict[str, str]]:
        try:
            s = self._build_session()
            try:
                s.get("https://duckduckgo.com/", timeout=8)
            except Exception:
                pass
            r = s.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "kl": "fr-fr"}, timeout=10,
            )
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            return [
                {
                    "title": a.get_text(strip=True),
                    "url": self._clean_ddg_url(a.get("href", "")),
                    "snippet": "",
                }
                for a in soup.select("a.result__a")[:limit]
                if a.get_text(strip=True) and self._clean_ddg_url(a.get("href", ""))
            ]
        except Exception:
            return []

    def _search_mojeek(self, query: str, limit: int) -> List[Dict[str, str]]:
        try:
            s = self._build_session()
            r = s.get(
                "https://www.mojeek.com/search",
                params={"q": query, "fmt": "html"}, timeout=10,
            )
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for li in soup.select("ul.results-standard li")[:limit]:
                a = li.select_one("a.title")
                if not a:
                    continue
                title = a.get_text(strip=True)
                url_clean = a.get("href", "")
                if not title or not url_clean:
                    continue
                sn = li.select_one(".s")
                snippet = sn.get_text(strip=True) if sn else ""
                results.append({"title": title, "url": url_clean, "snippet": snippet})
            return results
        except Exception:
            return []

    def _search_bing(self, query: str, limit: int) -> List[Dict[str, str]]:
        try:
            s = self._build_session()
            r = s.get(
                f"https://www.bing.com/search?q={quote_plus(query)}&mkt=fr-FR&setlang=fr",
                timeout=10,
            )
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for li in soup.select("li.b_algo")[: limit * 2]:
                a = li.select_one("h2 a")
                if not a:
                    continue
                title = a.get_text(strip=True)
                real_url = self._resolve_bing_url(a.get("href", ""))
                if not title or not real_url:
                    continue
                sn = li.select_one(".b_caption p")
                snippet = sn.get_text(strip=True) if sn else ""
                results.append({"title": title, "url": real_url, "snippet": snippet})
                if len(results) >= limit:
                    break
            return results
        except Exception:
            return []

    def _search_startpage(self, query: str, limit: int) -> List[Dict[str, str]]:
        try:
            s = self._build_session()
            r = s.get(
                "https://www.startpage.com/sp/search",
                params={"query": query, "cat": "web"}, timeout=10,
            )
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for el in soup.select("a.result-link")[: limit * 2]:
                title = el.get_text(strip=True)
                url_clean = el.get("href", "")
                if not title or not url_clean:
                    continue
                results.append({"title": title, "url": url_clean, "snippet": ""})
                if len(results) >= limit:
                    break
            return results
        except Exception:
            return []

    # ==================================================================
    # API PUBLIQUE
    # ==================================================================
    async def search_and_extract_leads(
        self, query: str, limit: int = 5
    ) -> List[Dict[str, str]]:
        if not query:
            return []

        raw: List[Dict[str, str]] = []

        try:
            from playwright.async_api import async_playwright  # noqa: F401
            playwright_ok = True
        except ImportError:
            logger.warning("[search] Playwright non installé")
            playwright_ok = False

        if playwright_ok:
            playwright_obj = None
            browser = None
            context = None
            try:
                playwright_obj, browser, context = await self._launch_browser()
                raw = await self._search_google_playwright(context, query, limit)
                if not raw:
                    raw = await self._search_ddg_lite_playwright(context, query, limit)
                if not raw:
                    raw = await self._search_bing_playwright(context, query, limit)
            except Exception as exc:
                logger.error("[search/pw] Exception globale : %s", exc)
                raw = []
            finally:
                if context:
                    try: await context.close()
                    except Exception: pass
                if browser:
                    try: await browser.close()
                    except Exception: pass
                if playwright_obj:
                    try: await playwright_obj.stop()
                    except Exception: pass

        if not raw:
            logger.info("[search] Cascade Playwright vide — tentative requests")
            loop = asyncio.get_event_loop()

            def _do_requests_search() -> List[Dict[str, str]]:
                engines = [
                    ("DDG HTML", self._search_ddg_html),
                    ("Mojeek", self._search_mojeek),
                    ("Bing", self._search_bing),
                    ("Startpage", self._search_startpage),
                ]
                for name, fn in engines:
                    try:
                        res = fn(query, limit)
                    except Exception as exc:
                        logger.debug("[search] %s exception : %s", name, exc)
                        res = []
                    if res:
                        logger.info("[search] %s → %d résultats", name, len(res))
                        return res
                return []

            try:
                raw = await loop.run_in_executor(None, _do_requests_search)
            except Exception as exc:
                logger.error("[search] Fallback requests échec : %s", exc)
                raw = []

        leads = []
        for item in raw:
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            snippet = (item.get("snippet") or "").strip()
            emails = re.findall(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", snippet)
            email = emails[0] if emails else ""
            leads.append({
                "first_name": "", "last_name": "", "email": email,
                "title": title[:120], "source_url": url, "snippet": snippet[:300],
            })

        logger.info("Extraction de leads terminée : %d résultats.", len(leads))
        return leads

    async def run_loop(self) -> None:
        async with self._state_lock:
            self._running = True
        logger.info("Worker Headless Playwright démarré.")
        while True:
            async with self._state_lock:
                if not self._running:
                    break
            try:
                await asyncio.sleep(30)
                logger.debug("Heartbeat Headless Worker : OK")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Erreur boucle worker : %s", exc)

    def stop(self) -> None:
        async def _set_stop():
            async with self._state_lock:
                self._running = False
        try:
            asyncio.create_task(_set_stop())
        except RuntimeError:
            self._running = False
        logger.info("Arrêt du worker headless demandé.")


if __name__ == "__main__":
    worker = HeadlessWorker(headless=True)
    try:
        asyncio.run(worker.run_loop())
    except KeyboardInterrupt:
        worker.stop()