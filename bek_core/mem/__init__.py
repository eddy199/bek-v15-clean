# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-MEM (Methodological Evolution Memory)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-MEM-v1.0
# 📄 Doc : docs/brevets/BREVET_MEM.md
# 🎯 Rôle : Evolutionary Prototype Memory
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

"""
BEK-MEM — Methodological Evolution Memory.

Mémoire associative par prototypes évolutifs.
Stocke des méthodologies de résolution, pas juste des réponses.

Usage :
    from bek_core.mem import BekMemMatcher
    
    matcher = BekMemMatcher()
    result = matcher.match("Cherche Bitcoin")
    # → {"prototype_id": "proto_xxx", "score": 0.92, ...}
"""

__version__ = "1.0.0"

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS PUBLICS
# ══════════════════════════════════════════════════════════════════════════════

from .matcher import (
    BekMemMatcher,
    bek_mem_match,
    bek_mem_store,
    bek_mem_update,
    BEK_MEM_DEFAULT_THRESHOLD,
)

__all__ = [
    "BekMemMatcher",
    "bek_mem_match",
    "bek_mem_store",
    "bek_mem_update",
    "BEK_MEM_DEFAULT_THRESHOLD",
]