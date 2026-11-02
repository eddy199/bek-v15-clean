# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Actions Package (v1.4.8)
# ------------------------------------------------------------------------------
# Package découpé de routers/chat_modules/actions.py (44 KB → 8 fichiers)
#
# Architecture :
#   - aliases.py     : _ACTION_ALIASES + _resolve_action_alias()
#   - regex.py       : ACTION_REGEX
#   - guards.py      : Garde-fou anti-orchestrate
#   - cleaning.py    : Nettoyage des espaces parasites
#   - extraction.py  : _extract_first_action() + _log_episode_safe()
#   - core.py        : _execute_action_unified() (dispatcher)
#   - summary.py     : get_actions_summary()
#
# ★ v1.4.8 (2026-10-16) — MIGRATION : découpage de actions.py en package
#   - AUCUNE fonctionnalité modifiée (100% compatible v1.4.8)
#   - Tous les imports existants (`from .chat_modules import actions as act`)
#     continuent de fonctionner grâce à la ré-exposition ci-dessous.
# ==============================================================================
from __future__ import annotations

# Ré-exposition complète (compatibilité 100% avec l'ancien actions.py)
from .aliases import _ACTION_ALIASES, _resolve_action_alias
from .regex import ACTION_REGEX
from .guards import (
    _ORCHESTRATE_META_PATTERNS,
    _ORCHESTRATE_META_REGEX,
    _ORCHESTRATE_MIN_GOAL_LENGTH,
    _is_orchestrate_misused,
    _build_orchestrate_guard_message,
)
from .cleaning import (
    _FILE_EXTENSIONS,
    _EXT_SPACE_RE,
    _SLASH_SPACE_RE,
    _BACKSLASH_SPACE_RE,
    _UUID_SPACE_RE,
    _clean_str_param,
    _clean_action_params,
)
from .extraction import (
    _RAW_PAYLOAD_DEFAULT_KEY,
    _extract_first_action,
    _log_episode_safe,
    _LOG_EPISODE_MAX_MESSAGE_CHARS,
)
from .core import (
    _execute_action_unified,
    _detect_web_sync_dag_usage,
    _normalize_agnes_model,
)
from .summary import get_actions_summary

__all__ = [
    # Aliases
    "_ACTION_ALIASES",
    "_resolve_action_alias",
    # Regex
    "ACTION_REGEX",
    # Guards
    "_ORCHESTRATE_META_PATTERNS",
    "_ORCHESTRATE_META_REGEX",
    "_ORCHESTRATE_MIN_GOAL_LENGTH",
    "_is_orchestrate_misused",
    "_build_orchestrate_guard_message",
    # Cleaning
    "_FILE_EXTENSIONS",
    "_EXT_SPACE_RE",
    "_SLASH_SPACE_RE",
    "_BACKSLASH_SPACE_RE",
    "_UUID_SPACE_RE",
    "_clean_str_param",
    "_clean_action_params",
    # Extraction
    "_RAW_PAYLOAD_DEFAULT_KEY",
    "_extract_first_action",
    "_log_episode_safe",
    "_LOG_EPISODE_MAX_MESSAGE_CHARS",
    # Core (dispatcher)
    "_execute_action_unified",
    "_detect_web_sync_dag_usage",
    "_normalize_agnes_model",
    # Summary
    "get_actions_summary",
]