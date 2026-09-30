# ==============================================================================
# BEK-v16 — Vision / Constants
# ------------------------------------------------------------------------------
# v30 (2026-10-01) : ★ Limites Agnes par résolution
#   - 1080p max 241 frames (10s)
#   - 720p  max 481 frames (20s)
#   - 480p  max 961 frames (40s)
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
AGNES_V2_MAX_FRAMES: int = 441          # limite GLOBALE (ancienne valeur)
AGNES_V2_DEFAULT_FPS: int = 24
AGNES_V2_MAX_DURATION: float = AGNES_V2_MAX_FRAMES / AGNES_V2_DEFAULT_FPS
AGNES_V2_MIN_DURATION: float = AGNES_V2_MIN_FRAMES / AGNES_V2_DEFAULT_FPS

# ★ v30 — Limites par résolution (retour API Agnes)
AGNES_V2_MAX_FRAMES_1080P: int = 241    # 1080p 16:9 → 10s
AGNES_V2_MAX_FRAMES_720P: int = 481     # 720p  16:9 → 20s
AGNES_V2_MAX_FRAMES_480P: int = 961     # 480p  16:9 → 40s

# ★ v30 — Mapping résolution → limite frames
AGNES_V2_RESOLUTION_LIMITS: Dict[str, int] = {
    "1080P": AGNES_V2_MAX_FRAMES_1080P,
    "1080p": AGNES_V2_MAX_FRAMES_1080P,
    "720P": AGNES_V2_MAX_FRAMES_720P,
    "720p": AGNES_V2_MAX_FRAMES_720P,
    "480P": AGNES_V2_MAX_FRAMES_480P,
    "480p": AGNES_V2_MAX_FRAMES_480P,
}

# Résolution par défaut
AGNES_V2_DEFAULT_RESOLUTION: str = "1080P"

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
    "romantic": (
        "with soft romantic piano and light violins, warm and tender melody, "
        "like a French romantic film soundtrack. Music plays continuously "
        "under the dialogue, no sudden changes, sweet and emotional."
    ),
    "sad": (
        "with melancholic piano music, slow sad violin melody, "
        "emotional and nostalgic atmosphere."
    ),
    "dramatic": (
        "with intense orchestral music, dramatic string swells, "
        "cinematic tension, powerful emotional crescendo."
    ),
    "epic": (
        "with epic orchestral music, powerful drums, triumphant horns, "
        "heroic and grand atmosphere, like a movie trailer soundtrack."
    ),
    "mysterious": (
        "with mysterious ambient music, dark subtle drones, "
        "suspenseful atmosphere, low tension tones."
    ),
    "suspense": (
        "with tense suspenseful music, low pulsing bass, "
        "rising tension, thriller atmosphere."
    ),
    "comedy": (
        "with playful light-hearted music, ukulele or soft acoustic guitar, "
        "comedic timing, cheerful bouncy melody."
    ),
    "cartoon": (
        "with classic cartoon music, bouncy playful xylophone and brass, "
        "comedic sound effects, upbeat whimsical animation soundtrack."
    ),
    "vintage": (
        "with 1920s-1940s vintage music, jazz or swing band, "
        "crackling vinyl record sound, warm nostalgic atmosphere."
    ),
    "noir": (
        "with film noir jazz music, smoky saxophone, slow piano, "
        "moody atmospheric soundtrack, 1940s detective film vibe."
    ),
    "retro": (
        "with 80s synthwave music, retro synthesizers, drum machine, "
        "neon vibe, nostalgic electronic soundtrack."
    ),
    "futuristic": (
        "with futuristic sci-fi soundtrack, deep synth pads, "
        "spacious electronic reverb, cosmic atmosphere."
    ),
    "tropical": (
        "with tropical music, ukulele, marimba, gentle ocean waves, "
        "birds singing, warm sunny beach atmosphere."
    ),
    "medieval": (
        "with medieval music, lute and harp, tavern ambiance, "
        "fantasy soundtrack, ancient mysterious atmosphere."
    ),
    "oriental": (
        "with oriental music, oud, darbuka, ney flute, "
        "Middle Eastern atmosphere, warm and exotic sound."
    ),
    "african": (
        "with African music, djembe drums, kalimba, "
        "warm rhythmic percussion, joyful tribal atmosphere."
    ),
    "gospel": (
        "with gospel choir music, uplifting organ, "
        "soulful voices, spiritual and powerful atmosphere."
    ),
    "jazz": (
        "with smooth jazz music, saxophone, piano, double bass, "
        "sophisticated evening atmosphere, like a Parisian café."
    ),
    "rock": (
        "with rock music, electric guitar riffs, drums, bass, "
        "energetic and powerful sound, driving rhythm."
    ),
    "electronic": (
        "with electronic dance music, techno beat, synth leads, "
        "modern club atmosphere, rhythmic and dynamic."
    ),
    "opera": (
        "with opera music, dramatic soprano voice, orchestral accompaniment, "
        "grand and theatrical atmosphere."
    ),
    "silent": (
        "with subtle ambient sound only, no music, "
        "minimal foley sounds, footsteps and cloth movements."
    ),
    "no_audio": (
        "with no audio at all, silent video, mute output"
    ),
}

# ==============================================================================
# CHEMINS & MEDIA
# ==============================================================================
SUPPORTED_IMAGE_EXTENSIONS: tuple = (".png", ".jpg", ".jpeg", ".webp")
SUPPORTED_VIDEO_EXTENSIONS: tuple = (".mp4", ".webm", ".mov")
SUPPORTED_MEDIA_EXTENSIONS: tuple = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS

# ==============================================================================
# ★ v30 — HELPERS
# ==============================================================================

def get_max_frames_for_resolution(resolution: str) -> int:
    """
    Retourne le nombre max de frames autorisé par Agnes pour une résolution.
    Fallback sur 1080P (241 frames) si la résolution est inconnue.
    """
    return AGNES_V2_RESOLUTION_LIMITS.get(resolution, AGNES_V2_MAX_FRAMES_1080P)