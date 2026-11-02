# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-FLUX (Fast Layered Unified eXecution)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-FLUX-v1.0
# 📄 Doc : docs/brevets/BREVET_FLUX.md
# 🎯 Rôle : DAG-Based Web Orchestration
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

"""
BEK-FLUX — Fast Layered Unified eXecution.

Exécute des tâches en parallèle via le DAG Engine.
Gain : 3x plus rapide que ThreadPoolExecutor(max_workers=3).

Usage :
    from bek_core.flux import BekFluxExecutor
    
    executor = BekFluxExecutor()
    results = executor.run(tasks, workers=10)
"""

__version__ = "1.0.0"

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS PUBLICS
# ══════════════════════════════════════════════════════════════════════════════

from .executor import (
    BekFluxExecutor,
    bek_flux_run,
    bek_flux_run_parallel,
    BEK_FLUX_DEFAULT_WORKERS,
    BEK_FLUX_DEFAULT_TIMEOUT,
)

__all__ = [
    "BekFluxExecutor",
    "bek_flux_run",
    "bek_flux_run_parallel",
    "BEK_FLUX_DEFAULT_WORKERS",
    "BEK_FLUX_DEFAULT_TIMEOUT",
]