# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Configuration (v1.6.0)
# ★ v1.6.0 : Force l'augmentation des limites (ignore env.txt trop bas)
# ==============================================================================
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("BEKApp")

def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try: return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError): return default

def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try: return max(minimum, float(os.getenv(name, str(default))))
    except (TypeError, ValueError): return default

def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v: return default
    return v in ("1", "true", "yes", "on")

HISTORY_WINDOW = _env_int("BEK_CHAT_HISTORY_WINDOW", 6)

# ★ v1.6.0 : Force 120K minimum, même si env.txt dit 20K
MAX_CHARS_PER_MESSAGE = max(120_000, _env_int("BEK_CHAT_MAX_CHARS_PER_MSG", 120_000))
MAX_TOTAL_CHARS = max(200_000, _env_int("BEK_CHAT_MAX_TOTAL_CHARS", 200_000))

GROQ_MAX_CHARS_PER_MESSAGE = _env_int("BEK_GROQ_MAX_CHARS_PER_MSG", 6000)
GROQ_MAX_TOTAL_CHARS = _env_int("BEK_GROQ_MAX_TOTAL_CHARS", 18000)
MAX_ARCHITECTURE_CHARS = _env_int("BEK_CHAT_MAX_ARCHITECTURE_CHARS", 2000)

MAX_TOTAL_ACTIONS = _env_int("BEK_CHAT_MAX_TOTAL_ACTIONS", 2)
POOR_RESULT_THRESHOLD = _env_int("BEK_CHAT_POOR_RESULT_THRESHOLD", 200)
MAX_CHUNKS_WITHOUT_CLOSE = _env_int("BEK_CHAT_MAX_CHUNKS_NO_CLOSE", 500)
MAX_QUERY_WORDS = _env_int("BEK_CHAT_MAX_QUERY_WORDS", 8)

AUTO_SCRAPE_MAX_URLS = _env_int("BEK_CHAT_AUTO_SCRAPE_MAX_URLS", 2)
AUTO_SCRAPE_MAX_CHARS_PER_PAGE = _env_int("BEK_CHAT_AUTO_SCRAPE_MAX_CHARS", 4000)

BEK_HEADLESS_SEARCH_ENABLED = _env_bool("BEK_HEADLESS_SEARCH_ENABLED", False)
BEK_WEB_SYNC_AS_PRIMARY = _env_bool("BEK_WEB_SYNC_AS_PRIMARY", True)

MULTIMEDIA_ACTIONS = (
    "generate_video", "edit_video", "extend_video", "extend_video_multiple",
    "generate_image", "edit_image", "generate_subtitles", "burn_subtitles",
)

ANALYSIS_ACTIONS = (
    "read_file", "analyze_image", "analyze_zip_content",
    "search_memory", "hindsight_query", "hindsight_recall",
    "headless_scrape", "execute_command", "run_script", "neon_audit",
)

BEK_LVC_OK: bool = False
BekCPU: Optional[Any] = None
BekStairToC: Optional[Any] = None

def init_bek_lvc() -> bool:
    global BEK_LVC_OK, BekCPU, BekStairToC
    try:
        from bek_core import BekCPU as _CPU
        from bek_core.stair import BekStairToC as _STAIR
        BekCPU = _CPU
        BekStairToC = _STAIR
        BEK_LVC_OK = True
        logger.info("✅ BEK-LVC chargé | briques=%s", BekCPU.list())
        return True
    except Exception as exc:
        BEK_LVC_OK = False
        BekCPU = None
        BekStairToC = None
        logger.warning("⚠️ BEK-LVC non chargé : %s", exc)
        return False

BEK_REX_TIER_TO_SOURCES = {
    "TIER_0": 0, "TIER_1": 3, "TIER_2": 5, "TIER_3": 10, "TIER_4": 15,
}

def get_config_summary() -> dict:
    return {
        "version": "1.6.0",
        "history_window": HISTORY_WINDOW,
        "max_chars_per_message": MAX_CHARS_PER_MESSAGE,
        "max_total_chars": MAX_TOTAL_CHARS,
        "groq_max_chars_per_message": GROQ_MAX_CHARS_PER_MESSAGE,
        "groq_max_total_chars": GROQ_MAX_TOTAL_CHARS,
        "max_architecture_chars": MAX_ARCHITECTURE_CHARS,
        "max_total_actions": MAX_TOTAL_ACTIONS,
        "max_chunks_without_close": MAX_CHUNKS_WITHOUT_CLOSE,
        "headless_search_enabled": BEK_HEADLESS_SEARCH_ENABLED,
        "web_sync_primary": BEK_WEB_SYNC_AS_PRIMARY,
        "bek_lvc_ok": BEK_LVC_OK,
    }