# ==============================================================================
# BEK-v16 — Vision Package (FINAL v31)
# ------------------------------------------------------------------------------
# Refactoring complet terminé (Lot 1 + 2 + 3 + 4) :
#   - constants.py          : toutes les constantes
#   - ffmpeg_utils.py       : helpers FFmpeg (+ crossfade v30)
#   - image_analysis.py     : analyze_image_with_vision
#   - image_generation.py   : generate_image_with_provider + merge_and_edit_images
#   - pollinations_client.py: ★ v26 — client Pollinations (gratuit, illimité)
#   - huggingface_client.py : ★ v25 — client Hugging Face (image + img2img)
#   - veo_client.py         : client Veo 3.1 complet
#   - agnes_client.py       : client Agnes complet
#   - video_generation.py   : generate_video_with_provider
#   - video_extension.py    : extend_video_with_agnes + extend_video_multiple
#                            (+ crossfade visuel v31)
#   - video_concat.py       : concat_videos + merge_and_edit_videos
#
# Plus aucune dépendance à vision_legacy.py ✅
# v25 (2026-09-21) : Ajout Hugging Face client (image + edit)
# v26 (2026-09-21) : Ajout Pollinations client (image par défaut)
# v30 (2026-09-21) : Ajout _ffmpeg_concat_crossfade (transition douce)
# v31 (2026-09-21) : Crossfade activé dans video_extension
# ==============================================================================
from __future__ import annotations

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
# 4. IMAGE GENERATION (Gemini + Pollinations + HF routing)
# ==============================================================================
from services.vision.image_generation import (
    generate_image_with_provider,
    merge_and_edit_images,
)

# ==============================================================================
# 4bis. POLLINATIONS CLIENT (★ v26 — par défaut)
# ==============================================================================
from services.vision.pollinations_client import (
    generate_image_with_pollinations,
    list_pollinations_models,
    POLLINATIONS_MODELS,
)

# ==============================================================================
# 4ter. HUGGING FACE CLIENT (★ v25 — optionnel)
# ==============================================================================
from services.vision.huggingface_client import (
    generate_image_with_huggingface,
    edit_image_with_huggingface,
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
    _extract_last_frame as _extract_last_frame_ext,  # alias pour éviter doublon
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
# HELPERS PUBLICS (compat avec l'existant)
# ==============================================================================
def resolve_model_id(model_name: str, is_video: bool = False) -> str:
    """Convertit un nom court UI vers le model ID officiel."""
    from provider_manager import provider_manager
    return provider_manager.resolve_model_id(model_name)


def get_api_key(key_name: str) -> str:
    """Récupère une clé API via le provider_manager."""
    from provider_manager import provider_manager
    return provider_manager.get_api_key(key_name)


# ==============================================================================
# __all__ — Exposition publique
# ==============================================================================
__all__ = [
    # Helpers
    "resolve_model_id",
    "get_api_key",
    # Image — Gemini + routing
    "analyze_image_with_vision",
    "generate_image_with_provider",
    "merge_and_edit_images",
    # Image — Pollinations ★ v26
    "generate_image_with_pollinations",
    "list_pollinations_models",
    "POLLINATIONS_MODELS",
    # Image — Hugging Face ★ v25
    "generate_image_with_huggingface",
    "edit_image_with_huggingface",
    # Vidéo — génération
    "generate_video_with_provider",
    # Vidéo — extension
    "extend_video_with_agnes",
    "extend_video_multiple",
    # Vidéo — concat
    "concat_videos",
    "merge_and_edit_videos",
    # Constantes
    "VEO_SUPPORTED_DURATIONS",
    "VEO_MAX_SINGLE_CLIP",
    "VEO_MIN_CLIP",
    "GEMINI_API_BASE",
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
    "SUPPORTED_IMAGE_EXTENSIONS",
    "SUPPORTED_VIDEO_EXTENSIONS",
    "SUPPORTED_MEDIA_EXTENSIONS",
]