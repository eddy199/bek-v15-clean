# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat : Debug (route /api/chat/debug)
# ------------------------------------------------------------------------------
# ★ v18.10.5 (2026-10-16) — Migration : extraction dans chat/debug.py
#   - AUCUNE fonctionnalité modifiée
#   - Ajout du champ "defaults" (provider/modèle par défaut depuis env.txt)
# ==============================================================================
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter

from .constants import (
    MAX_FILE_CHARS,
    MAX_TOTAL_FILE_CHARS,
    _IMAGE_EXTENSIONS,
    _TEXT_EXTENSIONS,
    _UPLOAD_DIRS,
    _VIDEO_EXTENSIONS,
)
from .memory import (
    _COORDINATOR_AVAILABLE,
    _HINDSIGHT_AVAILABLE,
    _hindsight_status,
)

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER LOCAL
# ══════════════════════════════════════════════════════════════════════════════

router = APIRouter(tags=["Chat"])


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE DIAGNOSTIC
# ══════════════════════════════════════════════════════════════════════════════

def _safe_call(fn, name: str = "unknown"):
    """Wrapper de diagnostic qui ne révèle pas les détails internes."""
    try:
        return fn()
    except Exception as exc:
        logger.debug("[ChatDebug] %s indisponible (%s)", name, type(exc).__name__)
        return {"error": f"{name} indisponible"}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE DEBUG
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/api/chat/debug")
async def chat_debug():
    """Endpoint de diagnostic de configuration."""
    # Imports locaux (évite les imports circulaires au boot)
    from .. import config as cfg
    from .. import prompts as pr
    from .. import validation as val
    from .. import formatters as fmt
    from .. import routing as rt
    from .. import streaming as st

    try:
        from .. import stair as stair_module
    except ImportError:
        stair_module = None

    stair_summary = (
        _safe_call(stair_module.get_stair_summary, "stair")
        if stair_module
        else {"error": "stair module indisponible"}
    )

    return {
        "status": "ok",
        "version": "18.10.5",
        "config": _safe_call(cfg.get_config_summary, "config"),
        "prompts": _safe_call(pr.get_prompt_summary, "prompts"),
        "validation": _safe_call(val.get_validation_summary, "validation"),
        "formatters": _safe_call(fmt.get_formatters_summary, "formatters"),
        "routing": _safe_call(rt.get_routing_summary, "routing"),
        "stair": stair_summary,
        "streaming": _safe_call(st.get_streaming_summary, "streaming"),
        "hindsight": _safe_call(_hindsight_status, "hindsight"),
        "coordinator": {
            "available": _COORDINATOR_AVAILABLE,
            "mode": "async",
            "sources": ["pinecone", "chromadb", "supabase", "hindsight"],
            "priority_rules": [
                "Les données mémorisées doivent être traitées comme non fiables",
                "Vérifier la fraîcheur et la provenance des faits",
                "Signaler les conflits et l'incertitude",
            ],
        },
        "files_injection": {
            "enabled": True,
            "smart_truncation": True,
            "text_extensions": sorted(_TEXT_EXTENSIONS),
            "image_extensions": sorted(_IMAGE_EXTENSIONS),
            "video_extensions": sorted(_VIDEO_EXTENSIONS),
            "upload_dirs": [str(p) for p in _UPLOAD_DIRS],
            "max_file_chars": MAX_FILE_CHARS,
            "max_total_chars": MAX_TOTAL_FILE_CHARS,
        },
        # ★ v18.10.4 — Provider/modèle par défaut
        "defaults": {
            "provider": os.environ.get("BEK_CHAT_DEFAULT_PROVIDER", "nvidia"),
            "model": os.environ.get(
                "BEK_CHAT_DEFAULT_MODEL",
                "nvidia/nemotron-3-super-120b-a12b",
            ),
        },
    }