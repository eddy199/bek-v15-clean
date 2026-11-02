# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-REX (Reflective EXecution)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-REX-v1.0
# 📄 Doc : docs/brevets/BREVET_REX.md
# 🎯 Rôle : Tiered Cognitive Routing
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

"""
BEK-REX — Reflective EXecution.

Route une requête vers le tier optimal (LOCAL, FAST, DEEP, EXPERT, SPECIALIZED).

Usage :
    from bek_core.rex import BekRexRouter
    
    router = BekRexRouter()
    result = router.route("Analyse Bitcoin")
    # → {"tier": "TIER_3", "confidence": 0.85, ...}
"""

__version__ = "1.0.0"

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS PUBLICS
# ══════════════════════════════════════════════════════════════════════════════

from .router import (
    BekRexRouter,
    bek_rex_route,
    bek_rex_list_tiers,
    BEK_REX_TIERS,
)

__all__ = [
    "BekRexRouter",
    "bek_rex_route",
    "bek_rex_list_tiers",
    "BEK_REX_TIERS",
]