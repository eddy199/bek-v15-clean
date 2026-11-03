# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat : Slash commands
# ------------------------------------------------------------------------------
# ★ v18.10.5 (2026-10-16) — Migration : extraction dans chat/slash.py
#   - AUCUNE fonctionnalité modifiée
# ==============================================================================
from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# COMMANDES SLASH
# ══════════════════════════════════════════════════════════════════════════════

async def _dispatch_slash(query: str):
    """Exécute une commande slash sans bloquer directement la boucle async."""
    from skill_runner import dispatch_command

    if inspect.iscoroutinefunction(dispatch_command):
        result = await dispatch_command(query)
    else:
        result = await asyncio.to_thread(dispatch_command, query)

    # Certaines fonctions synchrones peuvent retourner un awaitable.
    if inspect.isawaitable(result):
        result = await result

    return result


async def _stream_slash_output(output: Any):
    """Produit une réponse SSE compatible avec le format existant."""
    if not isinstance(output, str):
        try:
            output = json.dumps(output, ensure_ascii=False)
        except (TypeError, ValueError):
            output = str(output)

    yield f"data: {json.dumps({'chunk': output}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'done': True})}\n\n"