# bek_routing_config.py
# ==============================================================================
# BEK-v16 — Configuration de routage par type de tâche
# ------------------------------------------------------------------------------
# CORRECTIF v16 :
#   - "complex" route vers "kimi" (fallback Gemini)
#
# CORRECTIF v17 (2026-09-16) :
#   - NVIDIA promu provider PRINCIPAL pour chat/social/complex/code.
#     * 13 modèles gratuits illimités sur build.nvidia.com
#     * Groq est saturé (TPD 200k atteint → 429 permanent)
#     * Kimi est suspendu (compte non rechargé)
#   - Vision reste sur Gemini (meilleur pour images).
#   - Fallback NVIDIA → groq → gemini → openrouter.
# ==============================================================================

from __future__ import annotations

from typing import Dict, List


def get_routing_strategy(task_type: str) -> str:
    """
    Retourne le provider recommandé pour un type de tâche.

    v17 : NVIDIA par défaut (gratuit illimité), Gemini pour vision.
    """
    if task_type == "vision":
        return "gemini"
    # code, complex, chat, social, long, creative → nvidia
    return "nvidia"


# ──────────────────────────────────────────────────────────────────────────────
# MODÈLE RECOMMANDÉ PAR TYPE DE TÂCHE
# ──────────────────────────────────────────────────────────────────────────────
# v17 : modèles NVIDIA adaptés à chaque type de tâche.
_ROUTING_MODELS: Dict[str, str] = {
    # Complex : gros modèle de raisonnement
    "complex": "nvidia/nemotron-3-ultra-550b-a55b",
    # Code : bon compromis performance/taille
    "code": "nvidia/nemotron-3-super-120b-a12b",
    # Chat / social / long / creative : modèle équilibré
    "chat": "nvidia/nemotron-3-super-120b-a12b",
    "social": "nvidia/nemotron-3-super-120b-a12b",
    "long": "nvidia/nemotron-3-super-120b-a12b",
    "creative": "nvidia/nemotron-3-super-120b-a12b",
    # Vision : Gemini (meilleur multimodal)
    "vision": "gemini-3.8-flash",
}


def get_routing_model(task_type: str) -> str:
    """Retourne un modèle spécifique pour un type de tâche, ou ""."""
    try:
        return _ROUTING_MODELS.get(task_type, "")
    except Exception:
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# FALLBACK DOCUMENTÉ
# ──────────────────────────────────────────────────────────────────────────────
# v17 : NVIDIA en tête pour tous les types sauf vision.
_ROUTING_FALLBACKS: Dict[str, List[str]] = {
    "complex":  ["nvidia", "groq", "gemini", "openrouter"],
    "code":     ["nvidia", "groq", "gemini", "openrouter"],
    "chat":     ["nvidia", "groq", "gemini", "openrouter"],
    "social":   ["nvidia", "groq", "gemini", "openrouter"],
    "long":     ["nvidia", "groq", "gemini", "openrouter"],
    "creative": ["nvidia", "groq", "gemini", "openrouter"],
    "vision":   ["gemini", "nvidia", "groq", "openrouter"],
}


def get_routing_fallback(task_type: str) -> List[str]:
    """Retourne la chaîne de fallback documentée pour un type de tâche."""
    try:
        return list(_ROUTING_FALLBACKS.get(task_type, []))
    except Exception:
        return []


def list_routing_config() -> Dict[str, Dict[str, str]]:
    """Retourne toute la config de routage pour debug."""
    try:
        result = {}
        for task_type in ("code", "vision", "complex", "long", "creative", "chat", "social"):
            result[task_type] = {
                "provider": get_routing_strategy(task_type),
                "model": get_routing_model(task_type) or "(default)",
                "fallback_chain": " → ".join(get_routing_fallback(task_type)),
            }
        return result
    except Exception:
        return {}