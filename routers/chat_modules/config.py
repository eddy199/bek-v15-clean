# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Configuration (v1.3)
# ------------------------------------------------------------------------------
# ★ v1.3 (2026-10-07) : RÉDUCTION POUR RESPECTER GROQ FREE (8000 TPM)
#   - MAX_ARCHITECTURE_CHARS : 25000 → 3000 (réduction critique)
#   - MAX_TOTAL_CHARS        : 32000 → 10000
#   - MAX_CHARS_PER_MESSAGE  : 8000  → 3000
#   - HISTORY_WINDOW         : 6     → 3
#   - Cause : Groq Free tier refuse les requêtes > 8000 tokens/minute
# ★ v1.2 : MAX_CHUNKS_WITHOUT_CLOSE 150 → 500
# ★ v1.1 : MAX_ARCHITECTURE_CHARS 15000 → 25000
# ==============================================================================

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS ENV
# ══════════════════════════════════════════════════════════════════════════════

def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


# ══════════════════════════════════════════════════════════════════════════════
# ★ v1.3 — CONSTANTES HISTORIQUE (RÉDUITES POUR GROQ FREE)
# ==============================================================================

# Réduit de 6 → 3 : moins d'historique injecté
HISTORY_WINDOW = _env_int("BEK_CHAT_HISTORY_WINDOW", 3)

# Réduit de 8000 → 3000 : chaque message max 3000 chars (~1000 tokens)
MAX_CHARS_PER_MESSAGE = _env_int("BEK_CHAT_MAX_CHARS_PER_MSG", 3000)

# Réduit de 32000 → 10000 : total conversation max 10000 chars (~3300 tokens)
MAX_TOTAL_CHARS = _env_int("BEK_CHAT_MAX_TOTAL_CHARS", 10000)

# ★ CRITIQUE : Réduit de 25000 → 3000
# 3000 chars ≈ 1000 tokens — laisse de la place pour user + historique
MAX_ARCHITECTURE_CHARS = _env_int("BEK_CHAT_MAX_ARCHITECTURE_CHARS", 3000)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES — ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

MAX_TOTAL_ACTIONS = _env_int("BEK_CHAT_MAX_TOTAL_ACTIONS", 2)
POOR_RESULT_THRESHOLD = _env_int("BEK_CHAT_POOR_RESULT_THRESHOLD", 200)

MAX_CHUNKS_WITHOUT_CLOSE = _env_int("BEK_CHAT_MAX_CHUNKS_NO_CLOSE", 500)

MAX_QUERY_WORDS = _env_int("BEK_CHAT_MAX_QUERY_WORDS", 8)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES — AUTO-SCRAPE
# ══════════════════════════════════════════════════════════════════════════════

AUTO_SCRAPE_MAX_URLS = _env_int("BEK_CHAT_AUTO_SCRAPE_MAX_URLS", 2)
AUTO_SCRAPE_MAX_CHARS_PER_PAGE = _env_int("BEK_CHAT_AUTO_SCRAPE_MAX_CHARS", 4000)


# ══════════════════════════════════════════════════════════════════════════════
# HEADLESS
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
# ==============================================================================

BEK_LVC_OK: bool = False
BekCPU: Optional[Any] = None
BekStairToC: Optional[Any] = None


def init_bek_lvc() -> bool:
    """Initialise BEK-LVC (CPU + STAIR)."""
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
# BEK-REX TIERS
# ==============================================================================

BEK_REX_TIER_TO_SOURCES = {
    "TIER_0": 0,
    "TIER_1": 3,
    "TIER_2": 5,
    "TIER_3": 10,
    "TIER_4": 15,
}


# ══════════════════════════════════════════════════════════════════════════════
# INFO
# ==============================================================================

def get_config_summary() -> dict:
    """Retourne un résumé de la config pour debug."""
    return {
        "version": "1.3",
        "history_window": HISTORY_WINDOW,
        "max_chars_per_message": MAX_CHARS_PER_MESSAGE,
        "max_total_chars": MAX_TOTAL_CHARS,
        "max_architecture_chars": MAX_ARCHITECTURE_CHARS,
        "max_total_actions": MAX_TOTAL_ACTIONS,
        "max_chunks_without_close": MAX_CHUNKS_WITHOUT_CLOSE,
        "headless_search_enabled": BEK_HEADLESS_SEARCH_ENABLED,
        "web_sync_primary": BEK_WEB_SYNC_AS_PRIMARY,
        "bek_lvc_ok": BEK_LVC_OK,
        "★ groq_free_optimized": True,
    }