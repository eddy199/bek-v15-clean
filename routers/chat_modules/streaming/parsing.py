# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Streaming : Parsing (v1.6.19)
# ------------------------------------------------------------------------------
# ★ v1.6.19 : extraction du monolithe streaming.py → package modulaire
#   - Parsing des blocs [ACTION:...]
#   - Normalisation des params (camelCase, accents)
#   - Sanitization LLM output (tokens natifs, thinking tags)
# ==============================================================================
from __future__ import annotations

import ast as _ast
import json
import re as _re
from typing import Any, Dict, List

from .. import actions as act
from .constants import (
    _ACTION_FULL_RE,
    _CLOSING_ACTION_RE,
    _CLOSING_ACTION_LOOSE_RE,
    _NORMALIZE_PATTERNS,
    _LLM_NATIVE_REGEX,
    _LLM_XML_TOOL_REGEX,
    _THINKING_PATTERNS,
)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS OPENING / CLOSING
# ══════════════════════════════════════════════════════════════════════════════

def _has_closing_action(text: str) -> bool:
    if not text:
        return False
    return bool(_CLOSING_ACTION_RE.search(text) or _CLOSING_ACTION_LOOSE_RE.search(text))


def _has_opening_action(text: str) -> bool:
    if not text:
        return False
    return bool(_re.search(r"\[\s*ACTION\s*:", text, _re.IGNORECASE))


# ══════════════════════════════════════════════════════════════════════════════
# PARSING DES ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _find_all_complete_actions(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    results = []
    for match in _ACTION_FULL_RE.finditer(text):
        act_name = act._resolve_action_alias(match.group(1))
        raw_payload = match.group(2).strip()
        end_pos = match.end()
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
                    p_ast = _ast.literal_eval(raw_payload)
                    if isinstance(p_ast, dict):
                        params = p_ast
                        parsed_ok = True
                except Exception:
                    pass
            if not parsed_ok and not raw_payload.startswith("{"):
                default_key = act._RAW_PAYLOAD_DEFAULT_KEY.get(act_name, "query")
                params = {default_key: raw_payload.strip('"\'')}
        params = act._clean_action_params(params)
        results.append({"name": act_name, "params": params, "end_pos": end_pos})
    return results


# ══════════════════════════════════════════════════════════════════════════════
# NORMALISATION
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_llm_string(text: str) -> str:
    if not text or not isinstance(text, str):
        return text
    if text.startswith(("http://", "https://", "/", "./", "data:")):
        return text
    if text.startswith("{") and text.endswith("}"):
        return text
    result = text
    for pattern, replacement in _NORMALIZE_PATTERNS:
        result = _re.sub(pattern, replacement, result, flags=_re.IGNORECASE)
    result = _re.sub(r',([^\s])', r', \1', result)
    result = _re.sub(r'([a-zà-ÿ])([A-ZÀ-Ý])', r'\1 \2', result)
    result = _re.sub(r'\s+', ' ', result).strip()
    return result


def _normalize_action_params(params: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(params, dict):
        return params
    skip_keys = {"provider", "model", "url", "endpoint", "image_path",
                 "video_path", "file_path", "path", "filename", "zip_path",
                 "output_filename", "output_path", "id", "record_id", "seed"}
    normalized: Dict[str, Any] = {}
    for k, v in params.items():
        if k in skip_keys:
            normalized[k] = v
        elif isinstance(v, str):
            normalized[k] = _normalize_llm_string(v)
        elif isinstance(v, dict):
            normalized[k] = _normalize_action_params(v)
        elif isinstance(v, list):
            normalized[k] = [_normalize_llm_string(i) if isinstance(i, str) else i for i in v]
        else:
            normalized[k] = v
    return normalized


# ══════════════════════════════════════════════════════════════════════════════
# SANITIZATION LLM OUTPUT
# ══════════════════════════════════════════════════════════════════════════════

def _strip_reasoning(text: str) -> str:
    if not text:
        return text
    if text.strip() == "":
        return text
    for pattern in _THINKING_PATTERNS:
        text = pattern.sub("", text)
    text = _re.sub(r"\n{3,}", "\n\n", text)
    return text


def _sanitize_llm_output(text: str, strip_reasoning: bool = True) -> str:
    if not text:
        return text
    text = _LLM_NATIVE_REGEX.sub("", text)
    text = _LLM_XML_TOOL_REGEX.sub("", text)
    if strip_reasoning:
        text = _strip_reasoning(text)
    return text