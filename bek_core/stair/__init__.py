# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-STAIR (IBM STAIR Method)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-STAIR-v1.0
# 📄 Doc : docs/brevets/BREVET_STAIR.md
# 🎯 Rôle : Anti-hallucination via ToC (Table of Contents)
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

"""
BEK-STAIR — Méthode IBM STAIR (Summarize, Transform, Answer, Integrate, Refine).

Élimine les hallucinations en forçant le LLM à répondre UNIQUEMENT
dans un ToC (Table of Contents) construit à partir des sources réelles.

Usage :
    from bek_core.stair import BekStairToC
    
    toc = BekStairToC()
    context = toc.build(pages=pages, query="Cherche Bitcoin")
    validation = toc.validate(llm_response, context)
"""

__version__ = "1.0.0"

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS PUBLICS
# ══════════════════════════════════════════════════════════════════════════════

from .toc_builder import (
    BekStairToC,
    bek_stair_build_toc,
    bek_stair_validate,
    BEK_STAIR_VERSION,
)

__all__ = [
    "BekStairToC",
    "bek_stair_build_toc",
    "bek_stair_validate",
    "BEK_STAIR_VERSION",
]