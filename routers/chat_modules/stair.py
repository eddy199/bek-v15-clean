# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : BEK-STAIR (Anti-Hallucination)
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Validation des réponses via ToC (IBM STAIR method)
# 📄 Doc : docs/brevets/BREVET_STAIR.md
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-24
# ==============================================================================

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from . import config as cfg

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTRUCTION DU TOC
# ══════════════════════════════════════════════════════════════════════════════

def _stair_build_toc(
    pages: List[Dict[str, Any]],
    query: str,
) -> str:
    """
    Construit un ToC (Table of Contents) à partir des pages scrapées.

    Le ToC force le LLM à répondre UNIQUEMENT dans le périmètre des sources.

    Args:
        pages: Liste de dicts {url, title, content}
        query: La requête utilisateur

    Returns:
        str: ToC formaté
    """
    if not cfg.BEK_LVC_OK or cfg.BekStairToC is None:
        logger.warning("[STAIR] BEK-STAIR non chargé — fallback sans ToC")
        return ""

    if not pages:
        return ""

    try:
        toc = cfg.BekStairToC()
        return toc.build(pages=pages, query=query)
    except Exception as exc:
        logger.warning("[STAIR] Échec build ToC : %s", exc)
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION DE RÉPONSE
# ══════════════════════════════════════════════════════════════════════════════

def _stair_validate_response(
    llm_response: str,
    toc_context: str,
    pages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Valide la réponse du LLM contre le ToC.

    Détecte :
        - URLs inventées (non présentes dans les sources)
        - Noms de sources fantômes
        - Hallucinations temporelles

    Args:
        llm_response: La réponse du LLM
        toc_context: Le ToC construit
        pages: Les pages sources

    Returns:
        dict: {
            "valid": True/False,
            "hallucinations": [...],
            "score": 0.0-1.0
        }
    """
    if not cfg.BEK_LVC_OK or cfg.BekStairToC is None:
        # Fallback : pas de validation
        return {
            "valid": True,
            "hallucinations": [],
            "score": 1.0,
            "source": "fallback",
        }

    try:
        toc = cfg.BekStairToC()
        result = toc.validate(
            llm_response=llm_response,
            toc_context=toc_context,
            pages=pages,
        )
        result["source"] = "bek_stair"
        return result
    except Exception as exc:
        logger.warning("[STAIR] Échec validation : %s", exc)
        return {
            "valid": True,
            "hallucinations": [],
            "score": 1.0,
            "source": f"fallback (erreur: {exc})",
        }


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _stair_is_available() -> bool:
    """Vérifie si BEK-STAIR est disponible."""
    return cfg.BEK_LVC_OK and cfg.BekStairToC is not None


def _stair_should_validate(act_name: str) -> bool:
    """
    Décide si on doit valider la réponse avec STAIR.

    Validation utile pour :
        - web_sync (rapport WebAgent)
        - headless_scrape (contenu scrapé)
        - headless_search (résultats de recherche)
    """
    return act_name in ("web_sync", "headless_scrape", "headless_search")


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ══════════════════════════════════════════════════════════════════════════════

def get_stair_summary() -> dict:
    """Résumé du module STAIR."""
    return {
        "functions": [
            "_stair_build_toc",
            "_stair_validate_response",
            "_stair_is_available",
            "_stair_should_validate",
        ],
        "bek_stair_available": _stair_is_available(),
        "validated_actions": ["web_sync", "headless_scrape", "headless_search"],
    }