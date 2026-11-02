"""
BEK-v15.2 HYBRID - Service IA & Couche de Compression Headroom
-------------------------------------------------------------
v16.1 (2026-09-20) :
    - Ajout AGNES_MODELS (agnes-v2.0, agnes-v2.5-flash)
    - Enrichissement GEMINI_MODELS (Veo 3.1 IDs officiels)
    - ALL_MODELS inclut Agnes
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.ai_service")

# ==========================================
# IMPORTATION SÉCURISÉE HEADROOM
# ==========================================

try:
    from headroom import compress as headroom_compress
except ImportError:
    headroom_compress = None
    logger.warning("[Headroom] headroom-ai non disponible, mode bypass activé.")

# ==========================================
# REGISTRE DES MODÈLES ACTIFS
# ==========================================

GROQ_MODELS: List[str] = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
]

NVIDIA_ACTIVE_MODELS: List[str] = [
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3.2-11b-vision-instruct",
    "meta/llama-3.2-90b-vision-instruct",
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-nano-12b-v2-vl",
    "nvidia/nvidia-nemotron-nano-9b-v2",
    "openai/gpt-oss-120b",
    "google/gemma-4-31b-it",
]

GEMINI_MODELS: List[str] = [
    "gemini-3.6-flash",
    "gemini-1.5-pro-preview",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-image",
    "gemini-3.1-flash-lite-image",
    "gemini-3-pro-image",
    "gemini-3.5-live-translate-preview",
    "gemini-3.1-flash-live-preview",
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-native-audio-preview-12-2025",
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-preview-tts",
    # ----- Veo 3.1 : noms courts UI (convertis automatiquement) -----
    "veo-3.1-gene-prev",
    "veo-3.1-lite-gene-prev",
    "veo-3.1-fast-gene-prev",
    # ----- Veo 3.1 : IDs officiels API -----
    "veo-3.1-generate-preview",
    "veo-3.1-lite-generate-preview",
    "veo-3.1-fast-generate-preview",
    # ----- Audio -----
    "gemini-omni-flash",
    "lyria-3-pro-preview",
    "lyria-3-clip-preview",
    "lyria-realtime-preview",
]

OPENROUTER_MODELS: List[str] = [
    "openrouter/auto",
    "openai/gpt-oss-120b",
    "anthropic/claude-4-sonnet",
    "dots3-note-preview",
    "lfm2.5-2.6b",
    "nemotron-3.5-lightning",
    "laguna-s-2.1",
    "laguna-xs-2.1",
    "free-models-router",
]

# ★ AGNES AI — Modèles vidéo gratuits (v16.1) ★
AGNES_MODELS: List[str] = [
    "agnes-v2.0",         # 1080p, frames (règle 8n+1), max 18s
    "agnes-v2.5-flash",   # 720p, seconds, max 12s
]

ALL_MODELS: Dict[str, List[str]] = {
    "groq": GROQ_MODELS,
    "nvidia": NVIDIA_ACTIVE_MODELS,
    "gemini": GEMINI_MODELS,
    "openrouter": OPENROUTER_MODELS,
    "agnes": AGNES_MODELS,      # ← AJOUT v16.1
}

# ==========================================
# FONCTIONS DE COMPRESSION HEADROOM
# ==========================================

def is_headroom_enabled() -> bool:
    """Indique si la bibliothèque Headroom est installée et utilisable."""
    return headroom_compress is not None


def compress_messages(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Compresse la liste des messages de conversation (JSON, AST code, historique)
    avant l'envoi au provider LLM. En cas d'erreur, retourne les messages bruts.
    """
    if not messages:
        return []

    if headroom_compress is None:
        return messages

    try:
        compressed = headroom_compress(messages, model=model)
        if compressed:
            # Extraction de la liste depuis l'objet CompressResult
            if hasattr(compressed, "messages"):
                return list(compressed.messages)
            if isinstance(compressed, list):
                return compressed
    except Exception as exc:
        logger.debug("[Headroom] Erreur lors de la compression, utilisation du contexte brut : %s", exc)

    return messages


def compress_prompt_context(
    context_text: str,
    system_rules: str,
    model: Optional[str] = None,
) -> str:
    """
    Compresse les blocs de documentation et contexte de base tout en
    préservant l'intégrité absolue des règles d'or système BEK.
    """
    if not context_text:
        return system_rules

    if headroom_compress is None:
        return f"{system_rules}\n\n[CONTEXTE]\n{context_text}"

    dummy_messages = [
        {"role": "system", "content": system_rules},
        {"role": "user", "content": context_text},
    ]

    try:
        compressed_res = headroom_compress(dummy_messages, model=model)
        extracted = None
        if hasattr(compressed_res, "messages"):
            extracted = compressed_res.messages
        elif isinstance(compressed_res, list):
            extracted = compressed_res

        if extracted and len(extracted) >= 2:
            return f"{system_rules}\n\n[CONTEXTE-COMPRESSE]\n{extracted[1].get('content', context_text)}"
    except Exception as exc:
        logger.debug("[Headroom] Erreur compression prompt, conservation brute : %s", exc)

    return f"{system_rules}\n\n[CONTEXTE]\n{context_text}"