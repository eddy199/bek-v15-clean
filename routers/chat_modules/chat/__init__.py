# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Package (v18.10.5)
# ------------------------------------------------------------------------------
# Package découpé de routers/chat.py (30 KB → 9 fichiers)
#
# Architecture :
#   - constants.py   : Constantes (MAX_REQUEST_BYTES, regex, extensions)
#   - helpers.py     : Helpers (_error_response, _validate_provider_model...)
#   - files.py       : Injection fichiers joints (_smart_truncate_file...)
#   - slash.py       : Commandes slash
#   - memory.py      : Coordination mémoire + Hindsight
#   - debug.py       : Route /api/chat/debug
#   - core.py        : Route /api/chat + _chat_impl
#
# ★ v18.10.5 (2026-10-16) — MIGRATION : découpage de chat.py en package
#   - AUCUNE fonctionnalité modifiée (100% compatible v18.10.4)
#   - Tous les imports existants (`from routers import chat`) continuent
#     de fonctionner grâce à la ré-exposition ci-dessous.
# ==============================================================================
from __future__ import annotations

# ★ Ré-exposition du router FastAPI (pour `app.include_router(chat.router)`)
from .core import router

# ★ Ré-exposition des constantes (pour les tests / debug)
from .constants import (
    MAX_REQUEST_BYTES,
    MAX_INPUT_MESSAGES,
    MAX_PROVIDER_LENGTH,
    MAX_MODEL_LENGTH,
    MAX_MEMORY_CHARS,
    MAX_FILE_CHARS,
    MAX_TOTAL_FILE_CHARS,
    _TEXT_EXTENSIONS,
    _IMAGE_EXTENSIONS,
    _VIDEO_EXTENSIONS,
    _AUDIO_EXTENSIONS,
    _UPLOAD_DIRS,
    _PROVIDER_RE,
    _MODEL_RE,
    _FILES_ATTACHED_RE,
    _STRUCTURAL_LINE_RE,
    _WORKSPACE_ROOT,
)

# ★ Ré-exposition des helpers (pour compatibilité avec l'ancien chat.py)
from .helpers import (
    _error_response,
    _bounded_text,
    _validate_provider_model,
    _untrusted_context,
)

# ★ Ré-exposition des helpers fichiers joints
from .files import (
    _smart_truncate_file,
    _find_uploaded_file,
    _read_text_file_safe,
    _extract_attached_files,
    _inject_file_contents,
)

# ★ Ré-exposition des helpers slash
from .slash import (
    _dispatch_slash,
    _stream_slash_output,
)

# ★ Ré-exposition des helpers mémoire
from .memory import (
    _publish_web_cleaned,
    _HINDSIGHT_AVAILABLE,
    _COORDINATOR_AVAILABLE,
    coordinate_memories_async,
    hindsight_build_context,
)

# ★ Ré-exposition du debug
from .debug import (
    chat_debug,
    _safe_call,
)

__all__ = [
    # Router FastAPI
    "router",
    # Constantes
    "MAX_REQUEST_BYTES",
    "MAX_INPUT_MESSAGES",
    "MAX_PROVIDER_LENGTH",
    "MAX_MODEL_LENGTH",
    "MAX_MEMORY_CHARS",
    "MAX_FILE_CHARS",
    "MAX_TOTAL_FILE_CHARS",
    "_TEXT_EXTENSIONS",
    "_IMAGE_EXTENSIONS",
    "_VIDEO_EXTENSIONS",
    "_AUDIO_EXTENSIONS",
    "_UPLOAD_DIRS",
    "_PROVIDER_RE",
    "_MODEL_RE",
    "_FILES_ATTACHED_RE",
    "_STRUCTURAL_LINE_RE",
    "_WORKSPACE_ROOT",
    # Helpers
    "_error_response",
    "_bounded_text",
    "_validate_provider_model",
    "_untrusted_context",
    # Fichiers
    "_smart_truncate_file",
    "_find_uploaded_file",
    "_read_text_file_safe",
    "_extract_attached_files",
    "_inject_file_contents",
    # Slash
    "_dispatch_slash",
    "_stream_slash_output",
    # Mémoire
    "_publish_web_cleaned",
    "_HINDSIGHT_AVAILABLE",
    "_COORDINATOR_AVAILABLE",
    "coordinate_memories_async",
    "hindsight_build_context",
    # Debug
    "chat_debug",
    "_safe_call",
]