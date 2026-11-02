# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK Core (Le Cœur du CPU Logique Virtuel)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-CORE-v1.0
# 📄 Doc : docs/BEK_CPU.md
# 🎯 Rôle : Initialisation du référentiel BEK-LVC
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

"""
BEK Core — Le cœur du CPU Logique Virtuel.

Point d'entrée unique pour toutes les briques BEK.

Usage :
    from bek_core import BekCPU
    
    result = BekCPU.execute("BEK-REX", "route", query="Analyse Bitcoin")
    briques = BekCPU.list()
    BekCPU.doc("BEK-REX")
"""

__version__ = "1.0.0"
__author__ = "BEK Project"
__license__ = "BEK-LVC-v1.0"

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS PUBLICS
# ══════════════════════════════════════════════════════════════════════════════

from .cpu import BekCPU
from .translator import BekTranslator
from .registry import BekRegistry

__all__ = [
    "BekCPU",
    "BekTranslator",
    "BekRegistry",
]