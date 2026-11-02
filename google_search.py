# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18.1 — Google Custom Search API Client
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Recherche web via Google Custom Search API (gratuit 100 req/jour)
# 📄 Doc : https://developers.google.com/custom-search/v1/overview
# ------------------------------------------------------------------------------
# Version : 1.0
# Date : 2026-09-24
# ==============================================================================

from __future__ import annotations

import logging
import os
from typing import Dict, List
from urllib.parse import urlparse

import requests

# ══════════════════════════════════════════════════════════════════════════════
# ★ v18.1 — Chargement AUTOMATIQUE de env.txt au moment de l'import
# ------------------------------------------------------------------------------
# Sans ce bloc, os.environ ne contient PAS GOOGLE_CSE_API_KEY ni GOOGLE_CSE_CX
# quand le module est importé. On force le chargement AVANT toute lecture.
# ══════════════════════════════════════════════════════════════════════════════
try:
    from env_loader import load_env as _load_env
    _load_env()
except ImportError:
    # env_loader.py absent → on ne bloque pas
    pass
except Exception as _env_err:
    # Erreur silencieuse, on continue
    pass

logger = logging.getLogger("BEKApp")

# ─── Configuration (lue APRÈS le chargement de env.txt) ───
_GOOGLE_API_KEY = os.environ.get("GOOGLE_CSE_API_KEY", "").strip()
_GOOGLE_CX = os.environ.get("GOOGLE_CSE_CX", "").strip()
_GOOGLE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
_GOOGLE_TIMEOUT = 10


def is_available() -> bool:
    """Vérifie si Google CSE est configurée."""
    return bool(_GOOGLE_API_KEY) and bool(_GOOGLE_CX)


def search_web(query: str, limit: int = 10) -> List[Dict[str, str]]:
    """
    Recherche web via Google Custom Search API.

    Args:
        query: La requête
        limit: Nombre max de résultats (1-20, par pages de 10)

    Returns:
        Liste de dicts {title, url, snippet, source, domain}
    """
    if not is_available():
        logger.warning("[GoogleCSE] Clés API/CX non configurées")
        return []

    if not query or not query.strip():
        return []

    limit = max(1, min(20, limit))

    headers = {"Accept": "application/json"}

    results: List[Dict[str, str]] = []
    start_index = 1

    try:
        while len(results) < limit and start_index <= 91:
            num = min(10, limit - len(results))

            params = {
                "key": _GOOGLE_API_KEY,
                "cx": _GOOGLE_CX,
                "q": query.strip(),
                "num": num,
                "start": start_index,
                "hl": "fr",
                "lr": "lang_fr",
                "safe": "off",
            }

            logger.info(
                "[GoogleCSE] Recherche : '%s' (start=%d, num=%d)",
                query[:80], start_index, num,
            )

            resp = requests.get(
                _GOOGLE_ENDPOINT,
                headers=headers,
                params=params,
                timeout=_GOOGLE_TIMEOUT,
            )

            if resp.status_code == 400:
                logger.error("[GoogleCSE] 400 — Requête invalide : %s", resp.text[:200])
                break
            if resp.status_code == 403:
                logger.error("[GoogleCSE] 403 — Clé API invalide ou quota dépassé")
                break
            if resp.status_code == 429:
                logger.warning("[GoogleCSE] 429 — Rate limit atteint")
                break
            if resp.status_code != 200:
                logger.warning("[GoogleCSE] HTTP %d : %s", resp.status_code, resp.text[:200])
                break

            data = resp.json()
            items = data.get("items", [])

            if not items:
                logger.info("[GoogleCSE] Aucun résultat pour '%s'", query[:60])
                break

            for item in items:
                url = item.get("link", "")
                title = item.get("title", "")
                snippet = item.get("snippet", "")

                if not url or not title:
                    continue

                try:
                    domain = urlparse(url).netloc
                except Exception:
                    domain = ""

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "source": "google_cse",
                    "domain": domain,
                })

                if len(results) >= limit:
                    break

            if len(results) < limit and len(items) == num:
                start_index += num
            else:
                break

        logger.info("[GoogleCSE] → %d résultats pour '%s'", len(results), query[:60])
        return results

    except requests.Timeout:
        logger.warning("[GoogleCSE] Timeout après %ds pour '%s'", _GOOGLE_TIMEOUT, query[:60])
        return []
    except Exception as exc:
        logger.error("[GoogleCSE] Erreur : %s", exc)
        return []


def _test():
    """Test rapide en CLI."""
    logging.basicConfig(level=logging.INFO)
    if not is_available():
        print("❌ GOOGLE_CSE_API_KEY ou GOOGLE_CSE_CX non configurée dans env.txt")
        print(f"   GOOGLE_CSE_API_KEY = {_GOOGLE_API_KEY[:20]}..." if _GOOGLE_API_KEY else "   GOOGLE_CSE_API_KEY = (vide)")
        print(f"   GOOGLE_CSE_CX      = {_GOOGLE_CX}" if _GOOGLE_CX else "   GOOGLE_CSE_CX      = (vide)")
        return
    print("✅ Google Custom Search disponible")
    results = search_web("actualités Bitcoin", limit=5)
    print(f"→ {len(results)} résultats :")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['title'][:80]}")
        print(f"     {r['url']}")
        print(f"     {r['snippet'][:100]}")
        print()


if __name__ == "__main__":
    _test()