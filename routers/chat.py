# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Routeur Chat (Façade de compatibilité) — v18.10.5
# ------------------------------------------------------------------------------
# ★ v18.10.5 (2026-10-16) : DÉCOUPAGE EN PACKAGE
#   - Le code a été déplacé dans routers/chat_modules/chat/
#   - Ce fichier est une FAÇADE qui réexpose tout
#   - Compatibilité 100% : `from routers import chat; chat.router` continue
#     de fonctionner.
#
# Architecture du package :
#   routers/chat_modules/chat/
#   ├── __init__.py       : réexposition complète
#   ├── constants.py      : constantes + regex
#   ├── helpers.py        : helpers HTTP + validation
#   ├── files.py          : injection fichiers joints
#   ├── slash.py          : commandes slash
#   ├── memory.py         : coordination mémoire + Hindsight
#   ├── debug.py          : route /api/chat/debug
#   └── core.py           : route /api/chat + _chat_impl
# ==============================================================================
from __future__ import annotations

# ★ Ré-exposition du package chat/
from .chat_modules.chat import (
    router,
    # Constantes
    MAX_REQUEST_BYTES,
    MAX_INPUT_MESSAGES,
    MAX_PROVIDER_LENGTH,
    MAX_MODEL_LENGTH,
    MAX_MEMORY_CHARS,
    MAX_FILE_CHARS,
    MAX_TOTAL_FILE_CHARS,
    # Regex
    _PROVIDER_RE,
    _MODEL_RE,
    _FILES_ATTACHED_RE,
    _STRUCTURAL_LINE_RE,
    # Helpers
    _error_response,
    _bounded_text,
    _validate_provider_model,
    _untrusted_context,
    # Fichiers
    _smart_truncate_file,
    _find_uploaded_file,
    _read_text_file_safe,
    _extract_attached_files,
    _inject_file_contents,
    # Slash
    _dispatch_slash,
    _stream_slash_output,
    # Mémoire
    _publish_web_cleaned,
    _HINDSIGHT_AVAILABLE,
    _COORDINATOR_AVAILABLE,
    coordinate_memories_async,
    hindsight_build_context,
    # Debug
    chat_debug,
    _safe_call,
)

__all__ = [
    "router",
    "MAX_REQUEST_BYTES",
    "MAX_INPUT_MESSAGES",
    "MAX_PROVIDER_LENGTH",
    "MAX_MODEL_LENGTH",
    "MAX_MEMORY_CHARS",
    "MAX_FILE_CHARS",
    "MAX_TOTAL_FILE_CHARS",
    "_PROVIDER_RE",
    "_MODEL_RE",
    "_FILES_ATTACHED_RE",
    "_STRUCTURAL_LINE_RE",
    "_error_response",
    "_bounded_text",
    "_validate_provider_model",
    "_untrusted_context",
    "_smart_truncate_file",
    "_find_uploaded_file",
    "_read_text_file_safe",
    "_extract_attached_files",
    "_inject_file_contents",
    "_dispatch_slash",
    "_stream_slash_output",
    "_publish_web_cleaned",
    "_HINDSIGHT_AVAILABLE",
    "_COORDINATOR_AVAILABLE",
    "coordinate_memories_async",
    "hindsight_build_context",
    "chat_debug",
    "_safe_call",
]