# ==============================================================================
# BEK-v16 — Vision Package (FINAL v32.4)
# ------------------------------------------------------------------------------
# v32.4 (2026-10-24) : FIX sys.path (sécurisation des imports)
# ==============================================================================
from __future__ import annotations

# ==============================================================================
# ★ BLOC DE SÉCURITÉ SYS.PATH
# ==============================================================================
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "core" / "llm"))

# ==============================================================================
# 1. CONSTANTES
# ==============================================================================
from services.vision.constants import (
    VEO_SUPPORTED_DURATIONS,
    VEO_MAX_SINGLE_CLIP,
    VEO_MIN_CLIP,
    GEMINI_API_BASE,
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
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    SUPPORTED_MEDIA_EXTENSIONS,
)

# ==============================================================================
# 2. FFMPEG UTILS
# ==============================================================================
from services.vision.ffmpeg_utils import (
    _ffmpeg_run,
    _get_video_duration,
    _detect_video_codec,
    _extract_last_frame,
    _ffmpeg_concat,
    _ffmpeg_concat_crossfade,
    _ffmpeg_trim,
    _ffmpeg_trim_exact,
)

# ==============================================================================
# 3. IMAGE ANALYSIS
# ==============================================================================
from services.vision.image_analysis import (
    analyze_image_with_vision,
)

# ==============================================================================
# 4. IMAGE GENERATION
# ==============================================================================
from services.vision.image_generation import (
    generate_image_with_provider,
    merge_and_edit_images,
)

# ==============================================================================
# 4bis. POLLINATIONS CLIENT
# ==============================================================================
from services.vision.pollinations_client import (
    generate_image_with_pollinations,
    list_pollinations_models,
    POLLINATIONS_MODELS,
)

# ==============================================================================
# 4ter. HUGGING FACE CLIENT
# ==============================================================================
from services.vision.huggingface_client import (
    generate_image_with_huggingface,
    edit_image_with_huggingface,
)

# ==============================================================================
# 4quater. WHISPER CLIENT
# ==============================================================================
from services.vision.whisper_client import (
    generate_subtitles_from_video,
    burn_subtitles_into_video,
)

# ==============================================================================
# 5. VEO CLIENT
# ==============================================================================
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
# 6. AGNES CLIENT
# ==============================================================================
from services.vision.agnes_client import (
    _agnes_seconds_to_frames_optimal,
    _enrich_prompt_with_audio,
    _agnes_wait_rate_limit,
    _agnes_post_with_retry,
    _agnes_create_task,
    _agnes_poll_task,
    _agnes_download_video,
    _agnes_generate_single_clip,
)

# ==============================================================================
# 7. VIDEO GENERATION (public)
# ==============================================================================
from services.vision.video_generation import (
    generate_video_with_provider,
)

# ==============================================================================
# 8. VIDEO EXTENSION
# ==============================================================================
from services.vision.video_extension import (
    _extract_first_frame,
    _extract_last_frame as _extract_last_frame_ext,
    _agnes_extend_video_with_agnes,
    extend_video_with_agnes,
    extend_video_multiple,
)

# ==============================================================================
# 9. VIDEO CONCAT
# ==============================================================================
from services.vision.video_concat import (
    concat_videos,
    merge_and_edit_videos,
)

# ==============================================================================
# HELPERS PUBLICS
# ==============================================================================
def resolve_model_id(model_name: str, is_video: bool = False) -> str:
    from provider_manager import provider_manager
    return provider_manager.resolve_model_id(model_name)


def get_api_key(key_name: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.get_api_key(key_name)


# ==============================================================================
# __all__ — Exposition publique
# ==============================================================================
__all__ = [
    "resolve_model_id", "get_api_key",
    "analyze_image_with_vision", "generate_image_with_provider", "merge_and_edit_images",
    "generate_image_with_pollinations", "list_pollinations_models", "POLLINATIONS_MODELS",
    "generate_image_with_huggingface", "edit_image_with_huggingface",
    "generate_subtitles_from_video", "burn_subtitles_into_video",
    "generate_video_with_provider", "extend_video_with_agnes", "extend_video_multiple",
    "concat_videos", "merge_and_edit_videos",
    "VEO_SUPPORTED_DURATIONS", "VEO_MAX_SINGLE_CLIP", "VEO_MIN_CLIP", "GEMINI_API_BASE",
    "VEO_DEFAULT_PERSON_GENERATION", "VEO_FALLBACK_PERSON_GENERATIONS",
    "AGNES_V2_MIN_FRAMES", "AGNES_V2_MAX_FRAMES", "AGNES_V2_DEFAULT_FPS",
    "AGNES_V2_MAX_DURATION", "AGNES_V2_MIN_DURATION", "AGNES_RPM",
    "AGNES_RPM_WAIT_SECONDS", "AGNES_MAX_RETRIES", "AGNES_RETRY_BASE_DELAY",
    "AGNES_EXTEND_MAX_CLIPS", "AUDIO_STYLE_PROMPTS",
    "SUPPORTED_IMAGE_EXTENSIONS", "SUPPORTED_VIDEO_EXTENSIONS", "SUPPORTED_MEDIA_EXTENSIONS",
]