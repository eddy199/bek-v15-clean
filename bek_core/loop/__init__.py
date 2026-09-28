# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-LOOP (LOOp-adaptive Protocol)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-LOOP-v1.0
# 📄 Doc : docs/brevets/BREVET_LOOP.md
# 🎯 Rôle : Closed-Loop Reflexive Adaptation
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

"""
BEK-LOOP — LOOp-adaptive Protocol.

Enregistre les épisodes d'exécution et ferme la boucle d'apprentissage.
Chaque épisode alimente le Reflex-Loop, qui analyse les patterns et
propose des règles d'amélioration.

Usage :
    from bek_core.loop import BekLoopRecorder
    
    recorder = BekLoopRecorder()
    recorder.record({"query": "...", "tier": "TIER_2", "success": True})
"""

__version__ = "1.0.0"

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS PUBLICS
# ══════════════════════════════════════════════════════════════════════════════

from .recorder import (
    BekLoopRecorder,
    bek_loop_record,
    bek_loop_analyze,
    bek_loop_count,
    BEK_LOOP_DEFAULT_HOURS,
)

__all__ = [
    "BekLoopRecorder",
    "bek_loop_record",
    "bek_loop_analyze",
    "bek_loop_count",
    "BEK_LOOP_DEFAULT_HOURS",
]