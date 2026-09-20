# ==============================================================================
# BEK-v16 — Vision / Constants
# ------------------------------------------------------------------------------
# Toutes les constantes du module vision
# v28 (2026-09-20) : Extraction depuis vision.py v27.1
# ==============================================================================
from __future__ import annotations

from typing import Dict, List

from provider_manager import provider_manager

# ==============================================================================
# VEO 3.1 (Google)
# ==============================================================================
VEO_SUPPORTED_DURATIONS: List[int] = provider_manager.VEO_SUPPORTED_DURATIONS
VEO_MAX_SINGLE_CLIP: int = provider_manager.VEO_MAX_SINGLE_CLIP
VEO_MIN_CLIP: int = provider_manager.VEO_MIN_CLIP
GEMINI_API_BASE: str = provider_manager.GEMINI_API_BASE

VEO_DEFAULT_PERSON_GENERATION: str = "allow_all"
VEO_FALLBACK_PERSON_GENERATIONS: List[str] = ["allow_all", "dont_allow"]

# ==============================================================================
# AGNES AI (V2.0 + Flash)
# ==============================================================================
AGNES_V2_MIN_FRAMES: int = 81
AGNES_V2_MAX_FRAMES: int = 441
AGNES_V2_DEFAULT_FPS: int = 24
AGNES_V2_MAX_DURATION: float = AGNES_V2_MAX_FRAMES / AGNES_V2_DEFAULT_FPS
AGNES_V2_MIN_DURATION: float = AGNES_V2_MIN_FRAMES / AGNES_V2_DEFAULT_FPS

# ==============================================================================
# AGNES — RATE LIMITING (RPM)
# ==============================================================================
AGNES_RPM: int = 1
AGNES_RPM_WAIT_SECONDS: int = 65

# ==============================================================================
# AGNES — RETRY
# ==============================================================================
AGNES_MAX_RETRIES: int = 3
AGNES_RETRY_BASE_DELAY: int = 5

# ==============================================================================
# AGNES — EXTENSION
# ==============================================================================
AGNES_EXTEND_MAX_CLIPS: int = 5

# ==============================================================================
# STYLES AUDIO
# ==============================================================================
AUDIO_STYLE_PROMPTS: Dict[str, str] = {
    "default": (
        "with synchronized audio, ambient sound effects, "
        "natural background sounds matching the scene"
    ),
    "joyful": (
        "with joyful background music, cheerful sound effects, "
        "happy ambient audio synchronized with the action"
    ),
    "children": (
        "with playful children laughter, joyful background music, "
        "cheerful ambient sounds synchronized with the animation"
    ),
    "cinematic": (
        "with cinematic soundtrack, immersive ambient audio, "
        "professional sound design synchronized with the visuals"
    ),
    "nature": (
        "with natural ambient sounds, soft background music, "
        "gentle nature sound effects synchronized with the scene"
    ),
    "music": (
        "with upbeat background music, rhythmic sound effects, "
        "dynamic audio synchronized with the action"
    ),
    "dialog": (
        "with character voices speaking clearly, synchronized lip movements, "
        "natural dialogue audio matching the scene"
    ),
}

# ==============================================================================
# CHEMINS & MEDIA
# ==============================================================================
SUPPORTED_IMAGE_EXTENSIONS: tuple = (".png", ".jpg", ".jpeg", ".webp")
SUPPORTED_VIDEO_EXTENSIONS: tuple = (".mp4", ".webm", ".mov")
SUPPORTED_MEDIA_EXTENSIONS: tuple = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS