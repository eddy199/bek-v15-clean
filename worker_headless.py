# -*- coding: utf-8 -*-
# worker_headless.py — v18.15 (FIX: LVC-Web Text Extraction)
# ★ FIX #3 — Suppression du singleton global (code mort + risque Python < 3.10)
from __future__ import annotations
import asyncio, base64, logging, random, re, sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from core.lazy import is_lazy_enabled
except ImportError:
    def is_lazy_enabled() -> bool: return True

logger = logging.getLogger("bek.worker_headless")
WORKSPACE_DIR = Path(__file__).resolve().parent

# ══════════════════════════════════════════════════════════════════════════════
# ★ LVC-WEB : NETTOYAGE HTML
# ══════════════════════════════════════════════════════════════════════════════
def clean_html_to_text(html: str, max_chars: int = 2000) -> str:
    """LVC-Web : Extrait le texte utile du HTML et coupe à max_chars."""
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "aside", "form", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars] + "..." if len(text) > max_chars else text
    except Exception as e:
        logger.warning("[LVC-Web] Erreur nettoyage HTML : %s", e)
        return str(html)[:max_chars]

# ══════════════════════════════════════════════════════════════════════════════
# LAZY LOADING PLAYWRIGHT
# ══════════════════════════════════════════════════════════════════════════════
_playwright_module = None
_playwright_loaded = False
_playwright_lock = None

def _load_playwright():
    global _playwright_module, _playwright_loaded, _playwright_lock
    if _playwright_loaded: return _playwright_module
    if _playwright_lock is None:
        import threading
        _playwright_lock = threading.Lock()
    with _playwright_lock:
        if _playwright_loaded: return _playwright_module
        logger.info("[worker_headless] Chargement Playwright (lazy)...")
        try:
            from playwright.async_api import async_playwright
            _playwright_module = async_playwright
            _playwright_loaded = True
            logger.info("[worker_headless] ✅ Playwright chargé")
            return _playwright_module
        except ImportError as exc:
            logger.warning("[worker_headless] Playwright indisponible : %s", exc)
            _playwright_module = None
            _playwright_loaded = True
            return None

def is_playwright_available() -> bool:
    return _load_playwright() is not None

def _resolve_local_to_url(path: str) -> Optional[str]:
    if not path: return None
    path_str = str(path).strip().strip("\"'`")
    if path_str.lower().startswith(("http://", "https://", "file://", "data:")):
        return path_str
    try:
        from core.paths import CODE_WORKSPACE
        workspace = Path(CODE_WORKSPACE).resolve()
    except ImportError:
        workspace = (WORKSPACE_DIR / "workspace").resolve()

    candidate = Path(path_str)
    if not candidate.is_absolute():
        parts = candidate.parts
        if parts and parts[0].lower() == "workspace":
            candidate = Path(*parts[1:])
        candidate = (workspace / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not candidate.exists():
        logger.warning("[worker_headless] Fichier introuvable : %s", candidate)
        return None

    as_uri = candidate.as_uri()
    logger.info("[worker_headless] Chemin résolu → %s", as_uri)
    return as_uri

_STERILE_URL_PATTERNS = (
    r"^https?://(www\.)?google\.[a-z]{2,3}/?$",
    r"^https?://(www\.)?bing\.com/?$",
    r"^https?://(www\.)?duckduckgo\.com/?$",
    r"^https?://(www\.)?yahoo\.com/?$",
    r"^https?://(www\.)?msn\.com/?.*",
    r"[?&]q=", r"/search\?", r"/login", r"/signin", r"/auth/", r"/consent",
    r"accounts\.google\.com", r"login\.microsoftonline\.com",
    r"google\.com/url\?", r"bing\.com/ck/a",
)
_STERILE_URL_REGEX = re.compile("|".join(_STERILE_URL_PATTERNS), re.IGNORECASE)

def _is_sterile_url(url: str) -> bool:
    if not url: return True
    try: parsed = urlparse(url)
    except Exception: return True
    if parsed.scheme not in ("http", "https"): return True
    if not parsed.netloc: return True
    path = (parsed.path or "").strip("/")
    if not path or path in ("index.html", "index.htm", "index.php", "home", "home.html"):
        return True
    if _STERILE_URL_REGEX.search(url): return True
    return False

def _filter_sterile_results(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not results: return []
    kept = []
    for item in results:
        url = item.get("url") or item.get("source_url") or ""
        if _is_sterile_url(url): continue
        kept.append(item)
    return kept

class HeadlessWorker:
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 BEK-Agent/15.3"
    BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}
    _MAX_CONCURRENT_TASKS = 3

    _USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]

    _STOPWORDS = {
        "le","la","les","un","une","des","du","de","d","et","ou","en","au","aux","ce","ces","cet","cette",
        "il","elle","on","nous","vous","ils","elles","je","tu","me","te","se","lui","leur",
        "y","ne","pas","plus","que","qui","quoi","sur","sous","dans","par","pour","avec","sans",
        "est","sont","été","être","avoir","fait","the","an","of","to","in","on","at","by","for",
        "is","are","was","were","be","been","being","it","its","as","or","and","but","if","so","no",
        "do","does","did","has","have","had","this","that","with","from","will","would","can","could","should",
        "up","down","out","off","over","all","any","some",
    }

    _SEARCH_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1", "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    _NOISE_MARKERS = (
        "arrow_upward", "arrow_downward",
        "SIXB", "SIXC", "SIXE", "SIXI", "SIXM", "SIXR",
        "Nikkei 225", "S&P 500", "Dow Jones",
        "playlist_add", "expand_content", "keyboard_arrow",
    )

    def __init__(self, headless: bool = True, timeout_ms: int = 30000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._running = False
        self._semaphore = asyncio.Semaphore(self._MAX_CONCURRENT_TASKS)
        self._state_lock = asyncio.Lock()

    async def _route_interceptor(self, route: Any) -> None:
        try:
            if route.request.resource_type in self.BLOCKED_RESOURCE_TYPES:
                await route.abort()
            else:
                await route.continue_()
        except Exception:
            try: await route.continue_()
            except Exception: pass

    async def _launch_browser(self):
        pw = _load_playwright()
        if pw is None: raise RuntimeError("Playwright indisponible")
        playwright_obj = await pw().start()
        browser = await playwright_obj.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                  "--disable-extensions", "--disable-background-networking", "--disable-default-apps",
                  "--no-first-run", "--disable-blink-features=AutomationControlled"],
        )
        ua = random.choice(self._USER_AGENTS)
        context = await browser.new_context(user_agent=ua, viewport={"width": 1280, "height": 800},
                                            locale="fr-FR", timezone_id="Europe/Paris")
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        return playwright_obj, browser, context

    async def fetch_page_content(self, url: str) -> Dict[str, Any]:
        async with self._semaphore:
            pw = _load_playwright()
            if pw is None:
                return {"status": "error", "error": "Playwright non installé"}
            resolved_url = _resolve_local_to_url(url)
            if not resolved_url:
                return {"status": "error", "url": url, "error": f"URL/chemin invalide : {url}"}
            logger.info("Démarrage de l'extraction sur : %s", resolved_url)
            start_time = asyncio.get_event_loop().time()
            playwright_obj = browser = context = page = None
            try:
                playwright_obj, browser, context = await self._launch_browser()
                page = await context.new_page()
                await page.route("**/*", self._route_interceptor)
                response = await page.goto(resolved_url, timeout=self.timeout_ms, wait_until="domcontentloaded")
                status_code = response.status if response else 0
                title = await page.title()
                content = await page.content()
                duration_ms = round((asyncio.get_event_loop().time() - start_time) * 1000, 2)
                logger.info("Extraction réussie (%d octets) en %s ms", len(content), duration_ms)
                return {"status": "success", "url": resolved_url, "http_status": status_code,
                        "title": title, "content_length": len(content), "html": content, "duration_ms": duration_ms}
            except Exception as exc:
                logger.error("Erreur navigation %s : %s", resolved_url, exc)
                return {"status": "error", "url": resolved_url, "error": str(exc)}
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

    async def render_local_file(self, path: str, wait_ms: int = 1500) -> Dict[str, Any]:
        resolved = _resolve_local_to_url(path)
        if not resolved:
            return {"status": "error", "path": path, "error": f"Fichier introuvable : {path}"}

        async with self._semaphore:
            pw = _load_playwright()
            if pw is None:
                return {"status": "error", "error": "Playwright non installé"}
            playwright_obj = browser = context = page = None
            errors: List[str] = []
            console_errors: List[str] = []
            try:
                playwright_obj, browser, context = await self._launch_browser()
                page = await context.new_page()

                def _on_console(msg):
                    if msg.type == "error":
                        console_errors.append(msg.text)
                def _on_pageerror(err):
                    errors.append(str(err))

                page.on("console", _on_console)
                page.on("pageerror", _on_pageerror)

                await page.route("**/*", self._route_interceptor)
                response = await page.goto(resolved, timeout=self.timeout_ms, wait_until="networkidle")
                await page.wait_for_timeout(wait_ms)
                title = await page.title()
                html = await page.content()
                return {
                    "status": "success", "path": path, "url": resolved,
                    "title": title, "content_length": len(html), "html": html,
                    "console_errors": console_errors[:20],
                    "page_errors": errors[:20],
                    "ok": len(errors) == 0 and len(console_errors) == 0,
                }
            except Exception as exc:
                return {"status": "error", "path": path, "error": str(exc),
                        "console_errors": console_errors, "page_errors": errors}
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

    async def test_html_file(self, path: str) -> Dict[str, Any]:
        result = await self.render_local_file(path, wait_ms=1000)
        if result.get("status") == "error":
            return {"ok": False, "errors": [result.get("error", "unknown")], "path": path}
        all_errors = result.get("console_errors", []) + result.get("page_errors", [])
        html = result.get("html", "")
        body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
        body = body_match.group(1) if body_match else html
        body = re.sub(r"<[^>]+>", "", body)
        body = re.sub(r"\s+", " ", body).strip()[:1000]
        return {
            "ok": len(all_errors) == 0,
            "errors": all_errors,
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "content_length": result.get("content_length", 0),
            "body_preview": body,
        }

    async def screenshot_page(self, path_or_url: str, output: Optional[str] = None) -> Dict[str, Any]:
        resolved = _resolve_local_to_url(path_or_url)
        if not resolved:
            return {"status": "error", "error": f"Chemin invalide : {path_or_url}"}

        async with self._semaphore:
            pw = _load_playwright()
            if pw is None: return {"status": "error", "error": "Playwright non installé"}
            playwright_obj = browser = context = page = None
            try:
                playwright_obj, browser, context = await self._launch_browser()
                page = await context.new_page()
                await page.goto(resolved, timeout=self.timeout_ms, wait_until="networkidle")
                await page.wait_for_timeout(1000)
                if output:
                    out_path = Path(output) if Path(output).is_absolute() else WORKSPACE_DIR / output
                else:
                    out_path = WORKSPACE_DIR / "workspace" / f"screenshot_{int(asyncio.get_event_loop().time())}.png"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(out_path), full_page=True)
                return {"status": "success", "path": str(out_path), "url": resolved,
                        "size": out_path.stat().st_size}
            except Exception as exc:
                return {"status": "error", "error": str(exc)}
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

    async def extract_links(self, url: str, max_links: int = 50) -> Dict[str, Any]:
        async with self._semaphore:
            pw = _load_playwright()
            if pw is None: return {"status": "error", "error": "Playwright non installé"}
            playwright_obj = browser = context = page = None
            try:
                playwright_obj, browser, context = await self._launch_browser()
                page = await context.new_page()
                await page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
                links = await page.eval_on_selector_all("a[href]", "els => els.map(e => ({href: e.href, text: e.textContent.trim()}))")
                return {"status": "success", "url": url, "links": links[:max_links], "count": len(links)}
            except Exception as exc:
                return {"status": "error", "error": str(exc)}
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

    @staticmethod
    def _clean_ddg_url(raw: str) -> str:
        if not raw: return ""
        if raw.startswith("//"): raw = "https:" + raw
        if "uddg=" in raw:
            try: return unquote(raw.split("uddg=", 1)[1].split("&", 1)[0])
            except Exception: return raw
        return raw

    @staticmethod
    def _resolve_bing_url(raw: str) -> str:
        if not raw: return ""
        if "bing.com/ck/a" not in raw: return raw
        try:
            parsed = urlparse(raw)
            params = parse_qs(parsed.query)
            u = params.get("u", [None])[0]
            if not u: return raw
            if u.startswith("a1"): u = u[2:]
            padding = "=" * (-len(u) % 4)
            decoded = base64.urlsafe_b64decode(u + padding).decode("utf-8", errors="ignore")
            if decoded.startswith("http"): return decoded
        except Exception: pass
        return raw

    @staticmethod
    def _resolve_qwant_url(raw: str) -> str:
        if not raw: return ""
        if "qwant.com" in raw and "url=" in raw:
            try:
                parsed = urlparse(raw)
                params = parse_qs(parsed.query)
                u = params.get("url", [None])[0]
                if u: return unquote(u)
            except Exception: pass
        return raw

    @staticmethod
    def _resolve_startpage_url(raw: str) -> str:
        if not raw: return ""
        if "startpage.com" in raw and ("url=" in raw or "/do/" in raw):
            try:
                parsed = urlparse(raw)
                params = parse_qs(parsed.query)
                u = params.get("url", [None])[0]
                if u: return unquote(u)
            except Exception: pass
        return raw

    def _is_relevant(self, query: str, title: str, url: str) -> bool:
        raw_query = query or ""
        spaced_query = re.sub(r"([a-zà-ÿ])([A-ZÀ-Ý])", r"\1 \2", raw_query)
        spaced_query = re.sub(r"([A-Za-zÀ-ÿ])(\d)", r"\1 \2", spaced_query)
        keywords = [w.lower() for w in re.findall(r"\w+", spaced_query)
                    if len(w) >= 2 and w.lower() not in self._STOPWORDS]
        if not keywords: return True
        haystack = f"{title or ''} {url or ''}".lower()
        STRONG_KEYWORDS = {
            "bitcoin", "btc", "crypto", "cryptomonnaie", "blockchain",
            "news", "actualité", "actualités", "récent", "dernières",
            "prix", "price", "market", "marché", "cours", "ethereum", "eth",
            "bourse", "stock", "action", "finance", "economie", "économie",
        }
        title_lower = (title or "").lower()
        if any(kw in title_lower for kw in STRONG_KEYWORDS):
            return True
        matched = 0
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", haystack):
                matched += 1
        if matched >= 1: return True
        if len(keywords) <= 2 and len(title or "") > 15: return True
        return False

    @staticmethod
    def _is_noisy_content(text: str) -> bool:
        if not text or len(text) < 200: return False
        hits = sum(1 for m in HeadlessWorker._NOISE_MARKERS if m in text)
        return hits >= 3

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
            except Exception: continue

    async def _search_google_playwright(self, context: Any, query: str, limit: int) -> List[Dict[str, str]]:
        page = await context.new_page()
        try:
            try:
                await page.goto("https://www.google.fr/", timeout=15000, wait_until="domcontentloaded")
                await page.wait_for_timeout(800)
                await self._dismiss_google_consent(page)
            except Exception: pass

            url = f"https://www.google.com/search?q={quote_plus(query)}&hl=fr&num=20"
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            try: await page.wait_for_selector("div.g, div[data-hveid]", timeout=8000)
            except Exception: pass
            await page.wait_for_timeout(1500)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            results: List[Dict[str, str]] = []
            for div in soup.select("div.g, div[data-hveid]")[: limit * 5]:
                a = div.select_one("a")
                if not a: continue
                href = a.get("href", "")
                if not href.startswith("http"): continue
                if "google.com/url" in href:
                    try:
                        q = parse_qs(urlparse(href).query).get("q", [None])[0]
                        if q: href = q
                    except Exception: pass
                h3 = div.select_one("h3")
                title = h3.get_text(strip=True) if h3 else ""
                if not title: continue
                sn = div.select_one("div[data-sncf], span.aCOpRe, div.VwiC3b")
                snippet = sn.get_text(strip=True) if sn else ""
                if _is_sterile_url(href): continue
                if not self._is_relevant(query, title, href): continue
                results.append({"title": title, "url": href, "snippet": snippet})
                if len(results) >= limit: break
            return results
        except Exception:
            return []
        finally:
            try: await page.close()
            except Exception: pass

    async def _search_ddg_lite_playwright(self, context: Any, query: str, limit: int) -> List[Dict[str, str]]:
        page = await context.new_page()
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1800)
            html = await page.content()
            html_lower = html.lower()
            if "anomaly" in html_lower or "captcha" in html_lower or "email us" in html_lower:
                return []
            soup = BeautifulSoup(html, "html.parser")
            anchors = soup.select("a.result__a, a.result__url, .result__title a, a.result-link")
            results: List[Dict[str, str]] = []
            for a in anchors[: limit * 3]:
                title = a.get_text(strip=True)
                url_clean = self._clean_ddg_url(a.get("href", ""))
                snippet = ""
                parent = a.find_parent("div", class_="result__body")
                if parent:
                    sn = parent.select_one(".result__snippet")
                    if sn: snippet = sn.get_text(strip=True)
                if not snippet:
                    tr = a.find_parent("tr")
                    if tr:
                        next_tr = tr.find_next_sibling("tr")
                        if next_tr:
                            sn = next_tr.select_one("td.result-snippet")
                            if sn: snippet = sn.get_text(strip=True)
                if not title or not url_clean or not url_clean.startswith("http"): continue
                if _is_sterile_url(url_clean): continue
                if not self._is_relevant(query, title, url_clean): continue
                results.append({"title": title, "url": url_clean, "snippet": snippet})
                if len(results) >= limit: break
            return results
        except Exception:
            return []
        finally:
            try: await page.close()
            except Exception: pass

    async def _search_bing_once(self, context: Any, query: str, limit: int, market: str) -> List[Dict[str, str]]:
        page = await context.new_page()
        try:
            try:
                await page.goto("https://www.bing.com/", timeout=15000, wait_until="domcontentloaded")
                await page.wait_for_timeout(800)
            except Exception: pass
            lang = "en" if market.startswith("en") else "fr"
            url = f"https://www.bing.com/search?q={quote_plus(query)}&mkt={market}&setlang={lang}"
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            try: await page.wait_for_selector("li.b_algo h2 a", timeout=8000)
            except Exception: pass
            await page.wait_for_timeout(1500)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            results: List[Dict[str, str]] = []
            for li in soup.select("li.b_algo")[: limit * 4]:
                a = li.select_one("h2 a")
                if not a: continue
                title = a.get_text(strip=True)
                real_url = self._resolve_bing_url(a.get("href", ""))
                if not title or not real_url or not real_url.startswith("http"): continue
                if _is_sterile_url(real_url): continue
                if not self._is_relevant(query, title, real_url): continue
                sn = li.select_one(".b_caption p")
                snippet = sn.get_text(strip=True) if sn else ""
                results.append({"title": title, "url": real_url, "snippet": snippet})
                if len(results) >= limit: break
            return results
        except Exception:
            return []
        finally:
            try: await page.close()
            except Exception: pass

    async def _search_bing_playwright(self, context: Any, query: str, limit: int) -> List[Dict[str, str]]:
        results = await self._search_bing_once(context, query, limit, "en-US")
        if results: return results
        results = await self._search_bing_once(context, query, limit, "fr-FR")
        if results: return results
        return []

    async def _search_qwant_playwright(self, context: Any, query: str, limit: int) -> List[Dict[str, str]]:
        page = await context.new_page()
        try:
            url = f"https://www.qwant.com/?q={quote_plus(query)}&t=web"
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            try: await page.wait_for_selector("a[data-testid='result-link'], article", timeout=8000)
            except Exception: pass
            await page.wait_for_timeout(2500)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            results: List[Dict[str, str]] = []
            selectors = ["a[data-testid='result-link']", "article a[href^='http']",
                         "div[data-testid='web-result'] a[href^='http']"]
            anchors = []
            for sel in selectors:
                found = soup.select(sel)
                if found: anchors = found; break
            for a in anchors[: limit * 4]:
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if not href.startswith("http"): continue
                real_url = self._resolve_qwant_url(href)
                if not title or len(title) < 10: continue
                if _is_sterile_url(real_url): continue
                if not self._is_relevant(query, title, real_url): continue
                results.append({"title": title[:120], "url": real_url, "snippet": ""})
                if len(results) >= limit: break
            return results
        except Exception:
            return []
        finally:
            try: await page.close()
            except Exception: pass

    async def _search_mojeek_playwright(self, context: Any, query: str, limit: int) -> List[Dict[str, str]]:
        page = await context.new_page()
        try:
            url = f"https://www.mojeek.com/search?q={quote_plus(query)}"
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            try: await page.wait_for_selector("ul.results-standard li, a.title", timeout=8000)
            except Exception: pass
            await page.wait_for_timeout(1500)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            results: List[Dict[str, str]] = []
            for li in soup.select("ul.results-standard li")[: limit * 4]:
                a = li.select_one("a.title")
                if not a: continue
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if not href.startswith("http"): continue
                if _is_sterile_url(href): continue
                if not self._is_relevant(query, title, href): continue
                sn = li.select_one(".s")
                snippet = sn.get_text(strip=True) if sn else ""
                results.append({"title": title, "url": href, "snippet": snippet})
                if len(results) >= limit: break
            return results
        except Exception:
            return []
        finally:
            try: await page.close()
            except Exception: pass

    async def _search_startpage_playwright(self, context: Any, query: str, limit: int) -> List[Dict[str, str]]:
        page = await context.new_page()
        try:
            url = f"https://www.startpage.com/sp/search?query={quote_plus(query)}"
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            try: await page.wait_for_selector("a.result-link, .w-gl__result", timeout=8000)
            except Exception: pass
            await page.wait_for_timeout(2000)
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            results: List[Dict[str, str]] = []
            for el in soup.select("a.result-link, .w-gl__result-title a")[: limit * 4]:
                title = el.get_text(strip=True)
                href = el.get("href", "")
                if not href.startswith("http"): continue
                real_url = self._resolve_startpage_url(href)
                if not title: continue
                if _is_sterile_url(real_url): continue
                if not self._is_relevant(query, title, real_url): continue
                results.append({"title": title, "url": real_url, "snippet": ""})
                if len(results) >= limit: break
            return results
        except Exception:
            return []
        finally:
            try: await page.close()
            except Exception: pass

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        retries = Retry(total=2, backoff_factor=0.5,
                        status_forcelist=(429, 500, 502, 503, 504),
                        allowed_methods=frozenset(["GET", "POST"]))
        s.mount("https://", HTTPAdapter(max_retries=retries))
        s.mount("http://", HTTPAdapter(max_retries=retries))
        headers = dict(self._SEARCH_HEADERS)
        headers["User-Agent"] = random.choice(self._USER_AGENTS)
        s.headers.update(headers)
        return s

    def _search_ddg_html(self, query: str, limit: int) -> List[Dict[str, str]]:
        try:
            s = self._build_session()
            try: s.get("https://duckduckgo.com/", timeout=8)
            except Exception: pass
            r = s.post("https://html.duckduckgo.com/html/", data={"q": query, "kl": "fr-fr"}, timeout=10)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for a in soup.select("a.result__a")[:limit * 2]:
                title = a.get_text(strip=True)
                url_clean = self._clean_ddg_url(a.get("href", ""))
                if not title or not url_clean: continue
                if _is_sterile_url(url_clean): continue
                if not self._is_relevant(query, title, url_clean): continue
                results.append({"title": title, "url": url_clean, "snippet": ""})
                if len(results) >= limit: break
            return results
        except Exception:
            return []

    def _search_mojeek(self, query: str, limit: int) -> List[Dict[str, str]]:
        try:
            s = self._build_session()
            r = s.get("https://www.mojeek.com/search", params={"q": query, "fmt": "html"}, timeout=10)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for li in soup.select("ul.results-standard li")[:limit * 2]:
                a = li.select_one("a.title")
                if not a: continue
                title = a.get_text(strip=True)
                url_clean = a.get("href", "")
                if not title or not url_clean: continue
                if _is_sterile_url(url_clean): continue
                if not self._is_relevant(query, title, url_clean): continue
                sn = li.select_one(".s")
                snippet = sn.get_text(strip=True) if sn else ""
                results.append({"title": title, "url": url_clean, "snippet": snippet})
                if len(results) >= limit: break
            return results
        except Exception:
            return []

    def _search_bing(self, query: str, limit: int) -> List[Dict[str, str]]:
        try:
            s = self._build_session()
            r = s.get(f"https://www.bing.com/search?q={quote_plus(query)}&mkt=fr-FR&setlang=fr", timeout=10)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for li in soup.select("li.b_algo")[: limit * 2]:
                a = li.select_one("h2 a")
                if not a: continue
                title = a.get_text(strip=True)
                real_url = self._resolve_bing_url(a.get("href", ""))
                if not title or not real_url: continue
                if _is_sterile_url(real_url): continue
                if not self._is_relevant(query, title, real_url): continue
                sn = li.select_one(".b_caption p")
                snippet = sn.get_text(strip=True) if sn else ""
                results.append({"title": title, "url": real_url, "snippet": snippet})
                if len(results) >= limit: break
            return results
        except Exception:
            return []

    def _search_startpage(self, query: str, limit: int) -> List[Dict[str, str]]:
        try:
            s = self._build_session()
            r = s.get("https://www.startpage.com/sp/search", params={"query": query, "cat": "web"}, timeout=10)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for el in soup.select("a.result-link")[: limit * 2]:
                title = el.get_text(strip=True)
                url_clean = el.get("href", "")
                if not title or not url_clean: continue
                if _is_sterile_url(url_clean): continue
                if not self._is_relevant(query, title, url_clean): continue
                results.append({"title": title, "url": url_clean, "snippet": ""})
                if len(results) >= limit: break
            return results
        except Exception:
            return []

    async def search_and_extract_leads(self, query: str, limit: int = 5) -> List[Dict[str, str]]:
        if not query: return []
        raw: List[Dict[str, str]] = []
        playwright_ok = _load_playwright() is not None

        if playwright_ok:
            playwright_obj = browser = context = None
            try:
                playwright_obj, browser, context = await self._launch_browser()
                engines = [
                    ("Google", self._search_google_playwright),
                    ("Bing", self._search_bing_playwright),
                    ("DDG Lite", self._search_ddg_lite_playwright),
                    ("Qwant", self._search_qwant_playwright),
                    ("Mojeek", self._search_mojeek_playwright),
                    ("Startpage", self._search_startpage_playwright),
                ]
                _MIN_RESULTS_THRESHOLD = 3
                _all_results: List[Dict[str, str]] = []
                for name, engine_fn in engines:
                    try: partial = await engine_fn(context, query, limit)
                    except Exception: partial = []
                    if partial:
                        _all_results.extend(partial)
                        if len(_all_results) >= _MIN_RESULTS_THRESHOLD: break
                _seen_urls: set = set()
                for r in _all_results:
                    u = r.get("url", "")
                    if u and u not in _seen_urls:
                        _seen_urls.add(u); raw.append(r)
            except Exception:
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
            loop = asyncio.get_event_loop()
            def _do_requests_search() -> List[Dict[str, str]]:
                engines = [
                    ("DDG HTML", self._search_ddg_html),
                    ("Mojeek", self._search_mojeek),
                    ("Bing", self._search_bing),
                    ("Startpage", self._search_startpage),
                ]
                for name, fn in engines:
                    try: res = fn(query, limit)
                    except Exception: res = []
                    if res: return res
                return []
            try:
                raw = await loop.run_in_executor(None, _do_requests_search)
            except Exception:
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
        return leads

    async def run_loop(self) -> None:
        async with self._state_lock:
            self._running = True
        logger.info("Worker Headless Playwright démarré.")
        while True:
            async with self._state_lock:
                if not self._running: break
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError: break
            except Exception: pass

    def stop(self) -> None:
        async def _set_stop():
            async with self._state_lock:
                self._running = False
        try: asyncio.create_task(_set_stop())
        except RuntimeError: self._running = False
        logger.info("Arrêt du worker headless demandé.")


if __name__ == "__main__":
    worker = HeadlessWorker(headless=True)
    try:
        asyncio.run(worker.run_loop())
    except KeyboardInterrupt:
        worker.stop()