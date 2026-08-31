"""
BEK-v15.2 HYBRID - Worker Headless Autonome (Playwright Engine)
--------------------------------------------------------------
Service d'extraction et de rendu web headless non-interactif.
- Navigation DOM dynamique et rendu JavaScript complet
- Extraction sécurisée de texte, snippets et leads pour le WebAgent
- Communication locale et exécution isolée sans bloquer le serveur Flask
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.worker_headless")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [HeadlessWorker] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

WORKSPACE_DIR = Path(__file__).resolve().parent


class HeadlessWorker:
    """
    Moteur Playwright headless pour le scraping asynchrone et l'extraction de leads.
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 BEK-Agent/15.2"
    )

    def __init__(self, headless: bool = True, timeout_ms: int = 30000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._running = False

    async def fetch_page_content(self, url: str) -> Dict[str, Any]:
        """Charge une URL et retourne son HTML rendu et ses métadonnées."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright non installé. Exécutez: pip install playwright && playwright install chromium")
            return {"status": "error", "error": "Playwright non installé"}

        logger.info("Démarrage de l'extraction sur : %s", url)
        start_time = asyncio.get_event_loop().time()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            context = await browser.new_context(
                user_agent=self.DEFAULT_USER_AGENT,
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            try:
                response = await page.goto(
                    url,
                    timeout=self.timeout_ms,
                    wait_until="domcontentloaded",
                )
                status_code = response.status if response else 0
                title = await page.title()
                content = await page.content()
                duration_ms = round((asyncio.get_event_loop().time() - start_time) * 1000, 2)

                logger.info("Extraction réussie (%d octets) en %s ms", len(content), duration_ms)
                return {
                    "status": "success",
                    "url": url,
                    "http_status": status_code,
                    "title": title,
                    "content_length": len(content),
                    "html": content,
                    "duration_ms": duration_ms,
                }
            except Exception as exc:
                logger.error("Erreur lors de la navigation sur %s : %s", url, exc)
                return {
                    "status": "error",
                    "url": url,
                    "error": str(exc),
                }
            finally:
                await browser.close()

    async def search_and_extract_leads(self, query: str, limit: int = 5) -> List[Dict[str, str]]:
        """Effectue une recherche DuckDuckGo et extrait les contacts détectés."""
        search_url = f"https://lite.duckduckgo.com/lite/?q={query.replace(' ', '+')}"
        res = await self.fetch_page_content(search_url)

        if res.get("status") != "success":
            return []

        html = res.get("html", "")
        leads: List[Dict[str, str]] = []

        # Extraction regex ciblée des liens et snippets
        link_matches = re.findall(r'<a class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html)
        snippet_matches = re.findall(r'<td class="result-snippet"[^>]*>(.*?)</td>', html, re.DOTALL)

        for i, (link, raw_title) in enumerate(link_matches[:limit]):
            clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()
            snippet = ""
            if i < len(snippet_matches):
                snippet = re.sub(r"<[^>]+>", "", snippet_matches[i]).strip()

            emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", snippet)
            email = emails[0] if emails else f"lead_{abs(hash(clean_title)) % 10000}@bek-web.local"

            name_parts = clean_title.split()
            first_name = name_parts[0] if name_parts else "Prospect"
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Web"

            leads.append({
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "title": clean_title[:80],
                "source_url": link,
                "snippet": snippet[:200],
            })

        logger.info("Extraction de leads terminée : %d prospects trouvés.", len(leads))
        return leads

    async def run_loop(self) -> None:
        """Boucle de service autonome pour maintenir le worker actif en arrière-plan."""
        self._running = True
        logger.info("Worker Headless Playwright démarré et prêt.")
        
        while self._running:
            try:
                # Heartbeat de surveillance toutes les 30 secondes
                await asyncio.sleep(30)
                logger.debug("Heartbeat Headless Worker : OK")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Erreur dans la boucle du worker : %s", exc)

    def stop(self) -> None:
        self._running = False
        logger.info("Arrêt du worker headless demandé.")


if __name__ == "__main__":
    worker = HeadlessWorker(headless=True)
    try:
        asyncio.run(worker.run_loop())
    except KeyboardInterrupt:
        worker.stop()
        