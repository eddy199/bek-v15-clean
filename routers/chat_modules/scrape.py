# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Auto-Scrape
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Auto-scrape des URLs (utile pour headless_search historique)
# 📄 Doc : docs/BEK_LVC.md
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-24
# ==============================================================================

from __future__ import annotations

import logging
from typing import Any, Dict, List

from . import config as cfg
from . import validation as val
from . import actions as act

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-SCRAPE DES RÉSULTATS DE RECHERCHE
# ══════════════════════════════════════════════════════════════════════════════

def _auto_scrape_search_results(
    exec_res: dict,
    query: str,
) -> List[Dict[str, Any]]:
    """
    Scrape les N premières URLs d'un résultat de recherche.

    Args:
        exec_res: Résultat d'une action (headless_search, web_sync, etc.)
        query: La requête utilisateur

    Returns:
        Liste de dicts {url, title, content}
    """
    scraped: List[Dict[str, Any]] = []

    if not isinstance(exec_res, dict) or exec_res.get("status") != "success":
        return scraped

    leads = exec_res.get("leads", []) or []
    if not leads:
        return scraped

    count = 0
    for lead in leads:
        if count >= cfg.AUTO_SCRAPE_MAX_URLS:
            break

        url = lead.get("source_url") or ""
        title = lead.get("title") or ""

        if not url or val._is_sterile_url(url):
            continue

        logger.info("[AutoScrape] Scraping #%d : %s", count + 1, url[:100])

        try:
            scrape_res = act._execute_action_unified(
                "headless_scrape",
                {"url": url},
            )
        except Exception as exc:
            logger.warning("[AutoScrape] Échec sur %s : %s", url, exc)
            continue

        if not isinstance(scrape_res, dict) or scrape_res.get("status") != "success":
            logger.warning("[AutoScrape] Réponse non-success pour %s", url)
            continue

        html = scrape_res.get("html", "") or ""
        if not html:
            continue

        try:
            from bs4 import BeautifulSoup as _BS
            soup = _BS(html, "html.parser")
            for tag in soup([
                "script", "style", "noscript", "meta", "link",
                "nav", "footer", "header", "aside",
            ]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 20]
            text = "\n".join(lines)
            text = text[:cfg.AUTO_SCRAPE_MAX_CHARS_PER_PAGE]

        except Exception as exc:
            logger.warning("[AutoScrape] Extraction texte échouée sur %s : %s", url, exc)
            continue

        if text and len(text) > 100:
            scraped.append({
                "url": url,
                "title": title,
                "content": text,
            })
            count += 1
            logger.info("[AutoScrape] ✓ %s (%d chars)", url[:80], len(text))

    return scraped


# ══════════════════════════════════════════════════════════════════════════════
# FORMATAGE DES PAGES AUTO-SCRAPÉES
# ══════════════════════════════════════════════════════════════════════════════

def _format_auto_scraped_block(pages: List[Dict[str, Any]]) -> str:
    """
    Formate les pages auto-scrapées pour injection dans le prompt.

    Args:
        pages: Liste de dicts {url, title, content}

    Returns:
        Bloc formaté
    """
    if not pages:
        return ""

    lines = [
        "",
        "═══════════════════════════════════════════════════════════════",
        "📄 CONTENU RÉEL DES PAGES (auto-scrapé)",
        "═══════════════════════════════════════════════════════════════",
        "",
    ]

    for i, p in enumerate(pages, 1):
        lines.append(f"### Page {i} : {p['title']}")
        lines.append(f"URL : {p['url']}")
        lines.append(f"Contenu :\n{p['content']}\n")
        lines.append("─" * 60)

    lines.append(
        "\n⚠️ UTILISE UNIQUEMENT LE CONTENU CI-DESSUS pour répondre. "
        "N'invente RIEN. Cite les URLs comme sources.\n"
    )

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ══════════════════════════════════════════════════════════════════════════════

def get_scrape_summary() -> dict:
    """Résumé du module scrape."""
    return {
        "functions": [
            "_auto_scrape_search_results",
            "_format_auto_scraped_block",
        ],
        "max_urls": cfg.AUTO_SCRAPE_MAX_URLS,
        "max_chars_per_page": cfg.AUTO_SCRAPE_MAX_CHARS_PER_PAGE,
        "status": "actif pour compatibilité (headless_search retiré)",
    }