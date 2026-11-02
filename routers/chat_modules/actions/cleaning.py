# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Actions : Cleaning (nettoyage des espaces parasites)
# ------------------------------------------------------------------------------
# ★ v1.3 — Regex tolérante aux espaces parasites
# ★ v1.4 — Nettoyage des espaces parasites
# ★ v1.4.1 — Fix _clean_str_param ciblé
# ★ v1.4.8 (2026-10-16) — Migration : extraction dans actions/cleaning.py
#   - AUCUNE fonctionnalité modifiée
# ==============================================================================
from __future__ import annotations

import re
from typing import Any


# ══════════════════════════════════════════════════════════════════════════════
# NETTOYAGE DES ESPACES PARASITES (ciblé)
# ══════════════════════════════════════════════════════════════════════════════

_FILE_EXTENSIONS = (
    "jpg|jpeg|png|gif|webp|bmp|svg|"
    "mp4|mov|webm|avi|mkv|"
    "srt|vtt|txt|json|md|csv|pdf|"
    "py|js|ts|html|css|xml|yaml|yml"
)

_EXT_SPACE_RE = re.compile(
    r"\s*\.\s*(" + _FILE_EXTENSIONS + r")\b",
    re.IGNORECASE,
)
_SLASH_SPACE_RE = re.compile(r"(/\s+)([A-Za-z0-9_\-\.])")
_BACKSLASH_SPACE_RE = re.compile(r"(\\\s+)([A-Za-z0-9_\-\.])")
_UUID_SPACE_RE = re.compile(
    r"([a-f0-9])\s+(-)\s*([a-f0-9])",
    re.IGNORECASE,
)


def _clean_str_param(s: str) -> str:
    if not isinstance(s, str):
        return s
    s = _EXT_SPACE_RE.sub(r".\1", s)
    s = _SLASH_SPACE_RE.sub(r"/\2", s)
    s = _BACKSLASH_SPACE_RE.sub(r"\\\2", s)
    s = _UUID_SPACE_RE.sub(r"\1\2\3", s)
    return s.strip()


def _clean_action_params(params: Any) -> Any:
    if isinstance(params, str):
        return _clean_str_param(params)
    if isinstance(params, list):
        return [_clean_action_params(item) for item in params]
    if isinstance(params, dict):
        return {k: _clean_action_params(v) for k, v in params.items()}
    return params