# ==============================================================================
# BEK-v16 — Vision Package
# ------------------------------------------------------------------------------
# Point d'entrée du package services.vision
# v28 (2026-09-20) : Structure modulaire
#
# Rôle : réexporter TOUT (legacy + modules) pour que les imports existants
# `from services.vision import X` continuent de fonctionner.
# ==============================================================================
from __future__ import annotations

# ==============================================================================
# 1. RÉEXPORT DU LEGACY (v27.1 complet)
# ------------------------------------------------------------------------------
# Toutes les fonctions principales vivent encore dans vision_legacy.py.
# Elles seront migrées progressivement dans les modules du package (Lots 2-4).
# ==============================================================================
from services.vision_legacy import (
    # Public API — fonctions
    resolve_model_id,
    get_api_key,
    analyze_image_with_vision,
    generate_image_with_provider,
    merge_and_edit_images,
    generate_video_with_provider,
    extend_video_with_agnes,
    extend_video_multiple,
    concat_videos,
    merge_and_edit_videos,
    # Constantes legacy (déjà présentes dans le legacy)
    VEO_SUPPORTED_DURATIONS,
    VEO_MAX_SINGLE_CLIP,
    VEO_MIN_CLIP,
    VEO_DEFAULT_PERSON_GENERATION,
    VEO_FALLBACK_PERSON_GENERATIONS,
    AGNES_V2_MIN_FRAMES,
    AGNES_V2_MAX_FRAMES,
    AGNES_V2_DEFAULT_FPS,
    AGNES_V2_MAX_DURATION,
    AGNES_V2_MIN_DURATION,
    AGNES_RPM,
    AGNES_RPM_WAIT_SECONDS,
    AGNES_MAX_RETRIES,
    AGNES_RETRY_BASE_DELAY,
    AGNES_EXTEND_MAX_CLIPS,
    AUDIO_STYLE_PROMPTS,
)

# ==============================================================================
# 2. CONSTANTES & UTILS DU PACKAGE (Lot 1)
# ------------------------------------------------------------------------------
# Les modules du package vont remplacer progressivement le legacy.
# Pour l'instant ils coexistent, mais on n'importe QUE le legacy pour
# éviter les conflits (le legacy est complet et fonctionne).
# ==============================================================================
# NOTE : Les imports ci-dessous sont volontairement commentés pour éviter
# les conflits entre constants.py et vision_legacy.py.
# On les activera au fur et à mesure de la migration (Lots 2-4).
#
# from services.vision.constants import (...)
# from services.vision.ffmpeg_utils import (...)

# ==============================================================================
# __all__ — Exposition publique
# ==============================================================================
__all__ = [
    # Public API — fonctions
    "resolve_model_id",
    "get_api_key",
    "analyze_image_with_vision",
    "generate_image_with_provider",
    "merge_and_edit_images",
    "generate_video_with_provider",
    "extend_video_with_agnes",
    "extend_video_multiple",
    "concat_videos",
    "merge_and_edit_videos",
    # Constantes
    "VEO_SUPPORTED_DURATIONS",
    "VEO_MAX_SINGLE_CLIP",
    "VEO_MIN_CLIP",
    "VEO_DEFAULT_PERSON_GENERATION",
    "VEO_FALLBACK_PERSON_GENERATIONS",
    "AGNES_V2_MIN_FRAMES",
    "AGNES_V2_MAX_FRAMES",
    "AGNES_V2_DEFAULT_FPS",
    "AGNES_V2_MAX_DURATION",
    "AGNES_V2_MIN_DURATION",
    "AGNES_RPM",
    "AGNES_RPM_WAIT_SECONDS",
    "AGNES_MAX_RETRIES",
    "AGNES_RETRY_BASE_DELAY",
    "AGNES_EXTEND_MAX_CLIPS",
    "AUDIO_STYLE_PROMPTS",
]