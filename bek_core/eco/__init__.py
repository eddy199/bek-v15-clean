# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-ECO (Economic Cognitive Optimization)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-ECO-v1.0
# 📄 Doc : docs/brevets/BREVET_ECO.md
# 🎯 Rôle : Réflexion Économique
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.1
# Date : 2026-10-04
# ==============================================================================

"""
BEK-ECO — Economic Cognitive Optimization.

Optimise chaque décision selon 7 facteurs pondérés :
    1. Conformité
    2. Sécurité
    3. Précision
    4. Efficience
    5. Rentabilité
    6. Productivité
    7. Technologie

Gère aussi le cache multi-niveaux et les limites quotidiennes.

★ v1.1 — Cache intelligent :
    - Ne cache plus les questions de clarification
    - Ne cache plus les échecs
    - TTL différencié selon le type de réponse

Usage :
    from bek_core.eco import BekEcoOptimizer

    optimizer = BekEcoOptimizer()
    decision = optimizer.optimize(tier="TIER_2", query="Cherche Bitcoin")
    # → {"decision": "proceed", "cached": False, "score": 0.85}
"""

__version__ = "1.1.0"

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS PUBLICS
# ══════════════════════════════════════════════════════════════════════════════

from .optimizer import (
    BekEcoOptimizer,
    bek_eco_optimize,
    bek_eco_cache_get,
    bek_eco_cache_set,
    bek_eco_check_limits,
    BEK_ECO_WEIGHTS,
    BEK_ECO_DEFAULT_TTL,
    BEK_ECO_CONVERSATIONAL_TTL,
    BEK_ECO_FACTUAL_TTL,
    BEK_ECO_DEFAULT_DAILY_LIMIT,
    _should_cache_response,
    _is_clarification,
    _is_failure,
    _compute_ttl,
)

__all__ = [
    "BekEcoOptimizer",
    "bek_eco_optimize",
    "bek_eco_cache_get",
    "bek_eco_cache_set",
    "bek_eco_check_limits",
    "BEK_ECO_WEIGHTS",
    "BEK_ECO_DEFAULT_TTL",
    "BEK_ECO_CONVERSATIONAL_TTL",
    "BEK_ECO_FACTUAL_TTL",
    "BEK_ECO_DEFAULT_DAILY_LIMIT",
    "_should_cache_response",
    "_is_clarification",
    "_is_failure",
    "_compute_ttl",
]