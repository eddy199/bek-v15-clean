# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Streaming : Package (v1.6.19)
# ------------------------------------------------------------------------------
# ★ v1.6.19 : extraction du monolithe streaming.py → package modulaire
#
#   ┌─ constants.py   → regex, messages, config env
#   ├─ parsing.py     → _find_all_complete_actions, normalize, sanitize
#   ├─ guards.py      → _user_wants_image, _has_multi_intent, _llm_refused…
#   ├─ truncation.py  → _truncate_messages_for_groq
#   ├─ loop_detect.py → _LoopDetector
#   └─ core.py        → stream_chat (orchestrateur)
#
#   ⚠️ BACKWARD COMPATIBILITY 100%
#   Tous les symboles autrefois accessibles via `from streaming import X`
#   restent accessibles à l'identique.
# ==============================================================================
from __future__ import annotations

# ─── Constants ───────────────────────────────────────────────────────────────
from .constants import (
    # Regex actions
    _ACTION_FULL_RE,
    _CLOSING_ACTION_RE,
    _CLOSING_ACTION_LOOSE_RE,
    # Multi-intent
    _MULTI_INTENT_MARKERS,
    _OTHER_ACTION_KEYWORDS,
    # Intent image
    _EXPLICIT_IMAGE_PHRASES,
    _NON_GENERATION_CONVERSATIONAL_MARKERS,
    _LLM_REFUSAL_PATTERNS,
    _LLM_REFUSAL_RE,
    _VISUAL_TRIGGER_RE,
    # Vérification web
    _VERIFICATION_QUERY_RE,
    # Extraction image
    _NARRATIVE_PREFIX_RE,
    # Normalisation
    _NORMALIZE_PATTERNS,
    # Messages
    _MSG_TIMEOUT_DUR,
    _MSG_REASONING_OVERFLOW,
    _MSG_LOOP_DETECTED,
    # LLM natifs
    _LLM_NATIVE_TOKENS,
    _LLM_NATIVE_REGEX,
    _LLM_XML_TOOL_REGEX,
    _THINKING_PATTERNS,
    # Config env
    MAX_STREAM_DURATION_SEC,
    LOOP_DETECT_ENABLED,
    LOOP_WINDOW,
    LOOP_THRESHOLD,
    MAX_REASONING_CHARS,
    BEK_ECO_CACHE_ENABLED,
    BEK_MEM_ENABLED,
    BEK_LOOP_ENABLED,
    BEK_MULTI_ACTIONS_ENABLED,
    BEK_MAX_ACTIONS_PER_RESPONSE,
    BEK_ANTIHALLU_ENABLED,
    BEK_POST_ACTION_GRACE_MAX,
    BEK_MAX_TOKENS,
    BEK_FORCE_IMAGE_ON_INTENT,
    BEK_SKIP_BYPASS_ON_MULTI_INTENT,
    BEK_FOLLOWUP_AFTER_TOOL,
    _env_int,
    _env_bool,
)

# ─── Parsing ─────────────────────────────────────────────────────────────────
from .parsing import (
    _has_closing_action,
    _has_opening_action,
    _find_all_complete_actions,
    _normalize_llm_string,
    _normalize_action_params,
    _strip_reasoning,
    _sanitize_llm_output,
)

# ─── Guards ──────────────────────────────────────────────────────────────────
from .guards import (
    _has_multi_intent,
    _user_wants_image,
    _has_attached_file,
    _query_requires_verification,
    _add_verification_guard,
    _add_file_context_guard,
    _llm_refused_to_generate,
    _extract_image_subject,
)

# ─── Truncation ──────────────────────────────────────────────────────────────
from .truncation import _truncate_messages_for_groq

# ─── Loop detection ──────────────────────────────────────────────────────────
from .loop_detect import _LoopDetector

# ─── Core ────────────────────────────────────────────────────────────────────
from .core import stream_chat, get_streaming_summary


# ══════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE
# ══════════════════════════════════════════════════════════════════════════════
# Point d'entrée principal utilisé par chat.py :
#   from .chat_modules import streaming as st
#   st.stream_chat(...)        → core.py
#   st.get_streaming_summary() → core.py

__all__ = [
    # API principale
    "stream_chat",
    "get_streaming_summary",
    # Constants
    "MAX_STREAM_DURATION_SEC",
    "LOOP_DETECT_ENABLED",
    "MAX_REASONING_CHARS",
    "BEK_ECO_CACHE_ENABLED",
    "BEK_LOOP_ENABLED",
    "BEK_MULTI_ACTIONS_ENABLED",
    "BEK_MAX_ACTIONS_PER_RESPONSE",
    "BEK_ANTIHALLU_ENABLED",
    "BEK_POST_ACTION_GRACE_MAX",
    "BEK_MAX_TOKENS",
    "BEK_FORCE_IMAGE_ON_INTENT",
    "BEK_SKIP_BYPASS_ON_MULTI_INTENT",
    "BEK_FOLLOWUP_AFTER_TOOL",
    # Parsing
    "_find_all_complete_actions",
    "_has_closing_action",
    "_has_opening_action",
    "_sanitize_llm_output",
    "_normalize_action_params",
    "_normalize_llm_string",
    # Guards
    "_has_multi_intent",
    "_user_wants_image",
    "_has_attached_file",
    "_query_requires_verification",
    "_add_verification_guard",
    "_add_file_context_guard",
    "_llm_refused_to_generate",
    "_extract_image_subject",
    # Truncation / Loop
    "_truncate_messages_for_groq",
    "_LoopDetector",
]