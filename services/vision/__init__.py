# ==============================================================================
# BEK-v16 — Vision Package
# ------------------------------------------------------------------------------
# v28 (2026-09-20) : Lot 2/4 — Migration progressive
#   - image_analysis / image_generation / veo_client → modules
#   - Le reste (agnes, video_generation, extension, concat) reste dans legacy
# ==============================================================================
from __future__ import annotations

# ==============================================================================
# 1. NOUVEAUX MODULES (Lot 2)
# ==============================================================================
from services.vision.image_analysis import (
    analyze_image_with_vision,
)
from services.vision.image_generation import (
    generate_image_with_provider,
    merge_and_edit_images,
)
from services.vision.veo_client import (
    _veo_headers,
    _veo_raise_for_status,
    _veo_extract_video,
    _veo_download,
    _veo_poll_operation,
    _veo_generate_single_clip,
    _veo_generate_stitched,
)

# ==============================================================================
# 2. LEGACY (fonctions pas encore migrées)
# ------------------------------------------------------------------------------
# Agnès, video_generation, extension, concat sont encore dans legacy
# ==============================================================================
from services.vision_legacy import (
    # Public API — fonctions encore dans legacy
    resolve_model_id,
    get_api_key,
    generate_video_with_provider,
    extend_video_with_agnes,
    extend_video_multiple,
    concat_videos,
    merge_and_edit_videos,
    # Constantes
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
# __all__ — Exposition publique
# ==============================================================================
__all__ = [
    # Public API
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