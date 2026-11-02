# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Actions : Extraction (parsing + episode logger)
# ------------------------------------------------------------------------------
# ★ v1.4.8 (2026-10-16) — Migration : extraction dans actions/extraction.py
#   - Inclut _extract_first_action() + _log_episode_safe()
#   - AUCUNE fonctionnalité modifiée
# ★ v1.4.9 (2026-10-16) — FIX IMPORT : `from .. import validation as val`
#   - validation.py est dans chat_modules/, pas dans actions/
# ==============================================================================
from __future__ import annotations

import ast
import json
import logging
import time
from typing import Any, Dict, Optional

# ★ v1.4.9 — FIX : `..` remonte d'un niveau (chat_modules.validation)
from .. import validation as val

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# EPISODE LOGGER
# ══════════════════════════════════════════════════════════════════════════════

_LOG_EPISODE_MAX_MESSAGE_CHARS = 500


def _log_episode_safe(
    action: str,
    status: str,
    latency_ms: int,
    error_type: Optional[str] = None,
    source: str = "chat",
    extra: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
) -> None:
    _msg_truncated = None
    if message:
        _msg_str = str(message)
        if len(_msg_str) > _LOG_EPISODE_MAX_MESSAGE_CHARS:
            _msg_truncated = _msg_str[:_LOG_EPISODE_MAX_MESSAGE_CHARS] + "…[tronqué]"
        else:
            _msg_truncated = _msg_str

    try:
        from services.episode_logger import log_episode
        try:
            log_episode(
                action=action, status=status, latency_ms=latency_ms,
                error_type=error_type, source=source,
                extra=extra or {}, message=_msg_truncated,
            )
        except TypeError:
            log_episode(
                action=action, status=status, latency_ms=latency_ms,
                error_type=error_type, source=source, extra=extra or {},
            )
        logger.debug(
            "[EpisodeLogger] ✓ %s | %s | %dms",
            action, status, latency_ms,
        )
    except ImportError:
        logger.debug("[EpisodeLogger] Module non disponible — skip")
    except Exception as _e:
        logger.debug("[EpisodeLogger] Échec silencieux : %s", _e)


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION D'ACTION (avec fallback payload brut v1.4.8)
# ══════════════════════════════════════════════════════════════════════════════

_RAW_PAYLOAD_DEFAULT_KEY: Dict[str, str] = {
    "web_sync": "query",
    "generate_image": "prompt",
    "generate_video": "prompt",
    "headless_scrape": "url",
    "headless_extract_leads": "url",
    "headless_render": "url",
    "read_file": "filename",
    "delete_file": "filename",
    "execute_command": "command",
    "run_script": "command",
    "save_memory": "content",
    "search_memory": "query",
    "hindsight_query": "query",
    "hindsight_recall": "query",
    "orchestrate": "goal",
}


def _extract_first_action(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    # Imports locaux pour éviter la circularité
    from .regex import ACTION_REGEX
    from .aliases import _resolve_action_alias
    from .cleaning import _clean_action_params

    matches = list(ACTION_REGEX.finditer(text))
    if not matches:
        return None

    match = matches[0]
    act_name = match.group(1)
    raw_payload = match.group(2).strip()

    # ★ v1.4.5 — Résoudre les alias d'actions
    act_name = _resolve_action_alias(act_name)

    params: Dict[str, Any] = {}
    parsed_ok = False

    if raw_payload:
        try:
            p_json = json.loads(raw_payload)
            if isinstance(p_json, dict):
                params = p_json
                parsed_ok = True
        except Exception:
            try:
                p_ast = ast.literal_eval(raw_payload)
                if isinstance(p_ast, dict):
                    params = p_ast
                    parsed_ok = True
            except Exception:
                pass

        # ★ v1.4.8 — Si le LLM a écrit une chaîne simple sans accolades JSON
        if not parsed_ok and not raw_payload.startswith("{"):
            default_key = _RAW_PAYLOAD_DEFAULT_KEY.get(act_name, "query")
            params = {default_key: raw_payload.strip('"\'')}
            logger.info(
                "[ActionExtract] Payload brut converti en {'%s': %r} pour %s",
                default_key, params[default_key][:80], act_name,
            )

    params = _clean_action_params(params)

    if act_name == "headless_scrape":
        url = params.get("url") or ""
        if val._is_sterile_url(url):
            logger.info("[ActionFilter] Action stérile rejetée : %s", url)
            return None

    return {"name": act_name, "params": params}