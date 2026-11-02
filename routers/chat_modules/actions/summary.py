# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Actions : Summary
# ------------------------------------------------------------------------------
# ★ v1.4.8 (2026-10-16) — Migration : extraction dans actions/summary.py
#   - AUCUNE fonctionnalité modifiée
# ==============================================================================
from __future__ import annotations

from .guards import _ORCHESTRATE_MIN_GOAL_LENGTH


def get_actions_summary() -> dict:
    return {
        "version": "1.4.8",
        "features": {
            "aliases_anti_hallucination_v145": True,
            "extra_aliases_v146": True,
            "orchestrate_guard_v144": True,
            "★ orchestrate_empty_goal_fix_v147": True,
            "★ unified_action_executor_bridge_v148": True,
            "★ agnes_2_5_flash_default_v148": True,
            "min_goal_length": _ORCHESTRATE_MIN_GOAL_LENGTH,
        },
    }