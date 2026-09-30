# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Configuration
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Centraliser constantes, env, init BEK-LVC
# 📄 Doc : docs/BEK_LVC.md
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.2
# Date : 2026-09-29
# ------------------------------------------------------------------------------
# ★ v1.1 : MAX_ARCHITECTURE_CHARS 15000 → 25000 (accueillir plan d'action)
# ★ v1.2 : MAX_CHUNKS_WITHOUT_CLOSE 150 → 500 (fix Kimi/Gemini lent)
# ==============================================================================

from __future__ import annotations

import logging
import os
from typing import Any, Optional

# ══════════════════════════════════════════════════════════════════════════════
# LOGGER
# ══════════════════════════════════════════════════════════════════════════════

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS ENV
# ══════════════════════════════════════════════════════════════════════════════

def _env_int(name: str, default: int, minimum: int = 1) -> int:
    """Lit une variable d'environnement entière."""
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    """Lit une variable d'environnement flottante."""
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    """Lit une variable d'environnement booléenne."""
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES — HISTORIQUE
# ══════════════════════════════════════════════════════════════════════════════

HISTORY_WINDOW = _env_int("BEK_CHAT_HISTORY_WINDOW", 6)
MAX_CHARS_PER_MESSAGE = _env_int("BEK_CHAT_MAX_CHARS_PER_MSG", 8000)
MAX_TOTAL_CHARS = _env_int("BEK_CHAT_MAX_TOTAL_CHARS", 32000)

# ★ v18 — Augmenté pour accueillir le plan d'action complet (~10000 chars)
MAX_ARCHITECTURE_CHARS = _env_int("BEK_CHAT_MAX_ARCHITECTURE_CHARS", 25000)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES — ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

MAX_TOTAL_ACTIONS = _env_int("BEK_CHAT_MAX_TOTAL_ACTIONS", 2)
POOR_RESULT_THRESHOLD = _env_int("BEK_CHAT_POOR_RESULT_THRESHOLD", 200)

# ★ v1.2 — 150 → 500
# Certains LLMs (Kimi, Gemini) mettent du temps à générer la balise [/ACTION]
# finale sur les longs JSON (vidéo avec image_paths). 500 chunks = marge de
# sécurité suffisante pour ne plus abandonner une action en cours d'écriture.
MAX_CHUNKS_WITHOUT_CLOSE = _env_int("BEK_CHAT_MAX_CHUNKS_NO_CLOSE", 500)

MAX_QUERY_WORDS = _env_int("BEK_CHAT_MAX_QUERY_WORDS", 8)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES — AUTO-SCRAPE
# ══════════════════════════════════════════════════════════════════════════════

AUTO_SCRAPE_MAX_URLS = _env_int("BEK_CHAT_AUTO_SCRAPE_MAX_URLS", 2)
AUTO_SCRAPE_MAX_CHARS_PER_PAGE = _env_int("BEK_CHAT_AUTO_SCRAPE_MAX_CHARS", 4000)


# ══════════════════════════════════════════════════════════════════════════════
# ★ DÉCISION ARCHITECTURALE — HEADLESS DÉSACTIVÉ
# ------------------------------------------------------------------------------
# `headless_search` est RETIRÉ. Toutes les recherches passent par `web_sync`.
# Seul `headless_scrape` reste (pour scraper une URL unique).
# ==============================================================================

BEK_HEADLESS_SEARCH_ENABLED = _env_bool("BEK_HEADLESS_SEARCH_ENABLED", False)
BEK_WEB_SYNC_AS_PRIMARY = _env_bool("BEK_WEB_SYNC_AS_PRIMARY", True)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES — MULTIMÉDIA
# ══════════════════════════════════════════════════════════════════════════════

MULTIMEDIA_ACTIONS = (
    "generate_video",
    "edit_video",
    "extend_video",
    "extend_video_multiple",
    "generate_image",
    "edit_image",
    "generate_subtitles",
    "burn_subtitles",
)


# ══════════════════════════════════════════════════════════════════════════════
# INITIALISATION BEK-LVC
# ------------------------------------------------------------------------------
# État global partagé entre tous les modules.
# ══════════════════════════════════════════════════════════════════════════════

BEK_LVC_OK: bool = False
BekCPU: Optional[Any] = None
BekStairToC: Optional[Any] = None


def init_bek_lvc() -> bool:
    """
    Initialise BEK-LVC (CPU + STAIR).

    Returns:
        bool: True si BEK-LVC est chargé, False sinon
    """
    global BEK_LVC_OK, BekCPU, BekStairToC

    try:
        from bek_core import BekCPU as _CPU
        from bek_core.stair import BekStairToC as _STAIR

        BekCPU = _CPU
        BekStairToC = _STAIR
        BEK_LVC_OK = True

        logger.info(
            "✅ BEK-LVC chargé | briques=%s",
            BekCPU.list(),
        )
        return True

    except Exception as exc:
        BEK_LVC_OK = False
        BekCPU = None
        BekStairToC = None
        logger.warning("⚠️ BEK-LVC non chargé : %s", exc)
        return False


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — BEK-REX TIERS
# ══════════════════════════════════════════════════════════════════════════════

# Mapping TIER → Nombre de sources web_sync
BEK_REX_TIER_TO_SOURCES = {
    "TIER_0": 0,   # Pas de recherche
    "TIER_1": 3,   # Léger
    "TIER_2": 5,   # Moyen
    "TIER_3": 10,  # Profond
    "TIER_4": 15,  # Expert
}


# ══════════════════════════════════════════════════════════════════════════════
# FONCTION D'INFO
# ══════════════════════════════════════════════════════════════════════════════

def get_config_summary() -> dict:
    """Retourne un résumé de la config pour debug."""
    return {
        "version": "1.2",
        "history_window": HISTORY_WINDOW,
        "max_total_actions": MAX_TOTAL_ACTIONS,
        "auto_scrape_urls": AUTO_SCRAPE_MAX_URLS,
        "max_architecture_chars": MAX_ARCHITECTURE_CHARS,
        "max_chunks_without_close": MAX_CHUNKS_WITHOUT_CLOSE,
        "headless_search_enabled": BEK_HEADLESS_SEARCH_ENABLED,
        "web_sync_primary": BEK_WEB_SYNC_AS_PRIMARY,
        "bek_lvc_ok": BEK_LVC_OK,
        "tier_to_sources": BEK_REX_TIER_TO_SOURCES,
    }