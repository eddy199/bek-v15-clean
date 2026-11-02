# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Actions : Guards (anti-orchestrate)
# ------------------------------------------------------------------------------
# ★ v1.4.4 (2026-10-10) — GARDE-FOU ANTI-ORCHESTRATE
# ★ v1.4.7 (2026-10-12) — FIX ORCHESTRATE GOAL VIDE
# ★ v1.4.8 (2026-10-16) — Migration : extraction dans actions/guards.py
#   - AUCUNE fonctionnalité modifiée
# ==============================================================================
from __future__ import annotations

import re
from typing import Any


# ══════════════════════════════════════════════════════════════════════════════
# GARDE-FOU ANTI-ORCHESTRATE (v1.4.4 + fix v1.4.7)
# ══════════════════════════════════════════════════════════════════════════════

_ORCHESTRATE_META_PATTERNS = [
    r"\bplan\s+d[\'\s]?action",
    r"\broadmap\b",
    r"\bétapes?\s+clés?\b",
    r"\bphases?\b.*\bdéveloppement\b",
    r"\bconseil",
    r"\bconseille",
    r"\brecommandation",
    r"\bton\s+avis\b",
    r"\btu\s+penses\b",
    r"\bque\s+penses[- ]tu\b",
    r"\bexplique",
    r"\bexplication",
    r"\bdétaille",
    r"\bsynthèse\b",
    r"\brésumé\b",
    r"\bbilan\b",
    r"\bpourquoi\b",
    r"\bcomment\s+faire\b",
    r"\bprésente[- ]moi\b",
    r"\bfournir\s+une?\s+réponse\b",
    r"\bfournir\s+un\s+plan\b",
    r"\bprésenter\s+un\s+plan\b",
    r"\bje\s+veux\s+une\s+réponse",
    r"\bréponds[- ]moi\b",
    r"\btu\s+peux\s+créer\s+ça",
    r"\bpossible\s*\?",
    r"\banalyser\s+les\s+fichiers",
    r"\bconstruire\s+une\s+interface",
    r"\bcréer\s+une\s+application",
]

_ORCHESTRATE_META_REGEX = re.compile(
    "|".join(_ORCHESTRATE_META_PATTERNS),
    re.IGNORECASE,
)

# ★ v1.4.7 — Seuil minimum pour un goal valide
_ORCHESTRATE_MIN_GOAL_LENGTH = 5


def _is_orchestrate_misused(goal: Any) -> bool:
    """
    ★ v1.4.7 — Détecte un usage invalide d'orchestrate.
    """
    if goal is None:
        return True
    if not isinstance(goal, str):
        return True

    stripped = goal.strip()
    if not stripped:
        return True
    if len(stripped) < _ORCHESTRATE_MIN_GOAL_LENGTH:
        return True

    return bool(_ORCHESTRATE_META_REGEX.search(stripped))


def _build_orchestrate_guard_message(goal: Any) -> str:
    """
    ★ v1.4.7 — Message de garde-fou adapté au type d'usage invalide.
    """
    if goal is None or not isinstance(goal, str):
        goal_str = ""
    else:
        goal_str = goal.strip()

    if not goal_str or len(goal_str) < _ORCHESTRATE_MIN_GOAL_LENGTH:
        return (
            "⚠️ **L'outil `orchestrate` a été appelé sans objectif valide.**\n\n"
            "**Objectif reçu :** "
            f"`{goal_str if goal_str else '(vide)'}`\n\n"
            "**Que faire maintenant ?**\n"
            "- Ne PAS rappeler `orchestrate`\n"
            "- Réponds directement en **TEXTE NATUREL** à la question de "
            "l'utilisateur\n"
            "- Si la question nécessite plusieurs étapes, explique-les en "
            "texte structuré (listes, étapes numérotées)\n\n"
            "_(Note technique : goal vide ou trop court pour orchestrate.)_"
        )

    return (
        "⚠️ **L'outil `orchestrate` n'est pas adapté à cette demande.**\n\n"
        "Cette question est **conversationnelle** et nécessite une "
        "**réponse en texte**, pas une action multi-étapes.\n\n"
        "**Reformulez votre réponse sans action** : donnez directement "
        "l'explication, le plan, le conseil ou la synthèse que l'utilisateur "
        "attend, en texte naturel structuré.\n\n"
        f"_(Note technique : goal détecté comme meta = "
        f"`{goal_str[:80]}{'...' if len(goal_str) > 80 else ''}`)_"
    )