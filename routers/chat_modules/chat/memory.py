# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat : Memory (coordination mémoire + Hindsight)
# ------------------------------------------------------------------------------
# ★ v18.10.7 (2026-10-17) — AJOUT : hindsight_build_context_async
#   - Import et ré-exposition de la version async native
#   - Évite l'erreur "Timeout context manager should be used inside a task"
# ★ v18.10.5 (2026-10-16) — Migration : extraction dans chat/memory.py
#   - AUCUNE fonctionnalité modifiée
# ==============================================================================
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# HINDSIGHT (OPTIONNEL)
# ══════════════════════════════════════════════════════════════════════════════

try:
    from hindsight_memory import (
        hindsight_build_context,
        hindsight_build_context_async,  # ★ v18.10.7
        hindsight_status as _hindsight_status,
    )
    _HINDSIGHT_AVAILABLE = True
except ImportError:
    _HINDSIGHT_AVAILABLE = False

    def hindsight_build_context(q, max_results=3):
        return ""

    async def hindsight_build_context_async(q, max_results=3):  # ★ v18.10.7
        return ""

    def _hindsight_status():
        return {"enabled": False, "connected": False}


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY COORDINATOR ASYNC (OPTIONNEL)
# ══════════════════════════════════════════════════════════════════════════════

try:
    from memory_coordinator import coordinate_memories_async
    _COORDINATOR_AVAILABLE = True
except ImportError:
    _COORDINATOR_AVAILABLE = False

    async def coordinate_memories_async(query, max_chars=4000):
        class _Dummy:
            context = ""
            facts = []
            conflicts = []
            sources_used = []
            elapsed_ms = 0.0

        return _Dummy()


# ══════════════════════════════════════════════════════════════════════════════
# EVENTBUS : PUBLICATION EN TÂCHE DE FOND
# ══════════════════════════════════════════════════════════════════════════════

async def _publish_web_cleaned(query: str) -> None:
    """Publie l'événement en tâche de fond sans masquer les erreurs silencieusement."""
    try:
        from event_bus_client import event_bus as async_bus
        await async_bus.publish("web-cleaned", {"query": query})
    except Exception as exc:
        # Ne pas enregistrer le texte complet de la requête dans le log.
        logger.debug(
            "[EventBus] Publication web-cleaned échouée (%s)",
            type(exc).__name__,
        )


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "hindsight_build_context",
    "hindsight_build_context_async",  # ★ v18.10.7
    "_hindsight_status",
    "_HINDSIGHT_AVAILABLE",
    "coordinate_memories_async",
    "_COORDINATOR_AVAILABLE",
    "_publish_web_cleaned",
]