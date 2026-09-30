# ==============================================================================
# BEK-v16 — Vision / Constants
# ------------------------------------------------------------------------------
# Toutes les constantes du module vision
# v28 (2026-09-20) : Extraction depuis vision.py v27.1
# ★ v29 (2026-10-01) : Enrichissement massif
#   - 18 styles audio (musique, effets, ambiance)
#   - 15 presets visuels (cartoon, carton, BD, film noir, animation, etc.)
#   - Combinaisons audio+visuel prêtes à l'emploi
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
# ★ v29 — STYLES AUDIO (18 styles)
# ------------------------------------------------------------------------------
# Utilisation : "audio_style": "romantic" dans le message [ACTION:generate_video]
# ==============================================================================
AUDIO_STYLE_PROMPTS: Dict[str, str] = {

    # ─────────── BASIQUES ───────────
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

    # ─────────── ÉMOTIONS / AMBIANCES ───────────
    "romantic": (
        "with soft romantic piano and light violins, warm and tender melody, "
        "like a French romantic film soundtrack. Music plays continuously "
        "under the dialogue, no sudden changes, sweet and emotional."
    ),
    "sad": (
        "with melancholic piano music, slow sad violin melody, "
        "emotional and nostalgic atmosphere, soft tearful tones, "
        "quiet and introspective."
    ),
    "dramatic": (
        "with intense orchestral music, dramatic string swells, "
        "cinematic tension, powerful emotional crescendo, "
        "epic and moving soundtrack."
    ),
    "epic": (
        "with epic orchestral music, powerful drums, triumphant horns, "
        "heroic and grand atmosphere, like a movie trailer soundtrack. "
        "Rising and inspiring."
    ),
    "mysterious": (
        "with mysterious ambient music, dark subtle drones, "
        "suspenseful atmosphere, low tension tones, "
        "enigmatic and intriguing sound design."
    ),
    "suspense": (
        "with tense suspenseful music, low pulsing bass, "
        "rising tension, thriller atmosphere, "
        "heartbeat-like rhythm, cinematic anxiety."
    ),

    # ─────────── STYLES SPÉCIFIQUES ───────────
    "comedy": (
        "with playful light-hearted music, ukulele or soft acoustic guitar, "
        "comedic timing, cheerful bouncy melody, funny sound effects "
        "synchronized with the action."
    ),
    "cartoon": (
        "with classic cartoon music, bouncy playful xylophone and brass, "
        "comedic sound effects, boing noises, upbeat whimsical animation "
        "soundtrack like old Disney or Looney Tunes."
    ),
    "vintage": (
        "with 1920s-1940s vintage music, jazz or swing band, "
        "crackling vinyl record sound, warm nostalgic atmosphere, "
        "old Hollywood charm."
    ),
    "noir": (
        "with film noir jazz music, smoky saxophone, slow piano, "
        "moody atmospheric soundtrack, 1940s detective film vibe, "
        "shadows and rain ambiance."
    ),
    "retro": (
        "with 80s synthwave music, retro synthesizers, drum machine, "
        "neon vibe, nostalgic electronic soundtrack, "
        "analog warmth and vintage feel."
    ),
    "futuristic": (
        "with futuristic sci-fi soundtrack, deep synth pads, "
        "spacious electronic reverb, cosmic atmosphere, "
        "smooth electronic sound design like Blade Runner."
    ),
    "tropical": (
        "with tropical music, ukulele, marimba, gentle ocean waves, "
        "birds singing, warm sunny beach atmosphere, "
        "island vibe and relaxed mood."
    ),
    "medieval": (
        "with medieval music, lute and harp, tavern ambiance, "
        "fantasy soundtrack, ancient mysterious atmosphere, "
        "like a Lord of the Rings tavern scene."
    ),
    "oriental": (
        "with oriental music, oud, darbuka, ney flute, "
        "Middle Eastern atmosphere, warm and exotic sound, "
        "traditional instruments and rhythmic percussion."
    ),
    "african": (
        "with African music, djembe drums, kalimba, "
        "warm rhythmic percussion, joyful tribal atmosphere, "
        "sunny and vibrant sound."
    ),
    "gospel": (
        "with gospel choir music, uplifting organ, "
        "soulful voices, spiritual and powerful atmosphere, "
        "warm and emotional sound."
    ),
    "jazz": (
        "with smooth jazz music, saxophone, piano, double bass, "
        "sophisticated evening atmosphere, like a Parisian café, "
        "warm and relaxed."
    ),
    "rock": (
        "with rock music, electric guitar riffs, drums, bass, "
        "energetic and powerful sound, driving rhythm, "
        "rebellious and intense atmosphere."
    ),
    "electronic": (
        "with electronic dance music, techno beat, synth leads, "
        "modern club atmosphere, rhythmic and dynamic, "
        "energetic electronic sound design."
    ),
    "opera": (
        "with opera music, dramatic soprano voice, orchestral accompaniment, "
        "grand and theatrical atmosphere, classic and powerful, "
        "like a Verdi opera scene."
    ),
    "silent": (
        "with subtle ambient sound only, no music, "
        "minimal foley sounds, footsteps and cloth movements, "
        "quiet intimate atmosphere."
    ),
    "no_audio": (
        "with no audio at all, silent video, mute output"
    ),
}

# ==============================================================================
# ★ v29 — PRESETS VISUELS (15 styles prêts à l'emploi)
# ------------------------------------------------------------------------------
# Utilisation : "style_preset": "cartoon_cartoon" dans [ACTION:generate_video]
# ==============================================================================
VISUAL_STYLE_PRESETS: Dict[str, str] = {

    "cartoon_flat": (
        "flat 2D cartoon animation style, bold black outlines, "
        "bright flat colors, no shading, comic book style, "
        "clean sharp edges, vibrant palette."
    ),
    "cartoon_3d": (
        "Pixar-style 3D animated cartoon, smooth rounded shapes, "
        "expressive big eyes, soft lighting, vibrant colors, "
        "high-quality 3D rendering."
    ),
    "cardboard_cutout": (
        "handcrafted cardboard cutout puppet style, EVERYTHING made of "
        "corrugated cardboard, visible paper edges, matte textures, "
        "diorama box frame, warm handmade studio lighting, "
        "stop-motion puppet vibe."
    ),
    "bd_francaise": (
        "French comic book style (bande dessinée), bold black ink lines, "
        "vibrant colors, halftone shading, expressive characters, "
        "speech bubble ready, like Tintin or Astérix."
    ),
    "manga": (
        "Japanese manga style, black and white line art, "
        "screentone shading, expressive large eyes, "
        "dynamic action poses, detailed backgrounds."
    ),
    "film_noir": (
        "film noir 1940s style, high contrast black and white, "
        "harsh directional shadows, cigarette smoke, "
        "rainy street atmosphere, detective noir aesthetic."
    ),
    "old_cinema": (
        "vintage 1920s silent film style, sepia tones, "
        "film grain and scratches, dramatic lighting, "
        "classic Hollywood glamour, vignette edges."
    ),
    "static_painting": (
        "static classical oil painting style, visible brushstrokes, "
        "rich impasto texture, Renaissance masters style, "
        "chiaroscuro lighting, canvas texture."
    ),
    "watercolor": (
        "soft watercolor painting style, translucent washes, "
        "visible brush strokes, paper texture, "
        "delicate artistic composition, bleeding colors."
    ),
    "claymation": (
        "stop-motion claymation style like Aardman studio, "
        "handcrafted plasticine characters, visible fingerprint marks, "
        "miniature sets, practical lighting, Wallace and Gromit vibe."
    ),
    "pixel_art": (
        "retro pixel art style, 8-bit or 16-bit video game aesthetic, "
        "chunky visible pixels, limited color palette, "
        "sprite-based characters, nostalgic vibe."
    ),
    "anime_ghibli": (
        "Studio Ghibli anime style, hand-painted backgrounds, "
        "soft atmospheric lighting, expressive characters, "
        "warm nostalgic vibe, detailed nature scenes."
    ),
    "steampunk": (
        "steampunk aesthetic, brass and copper machinery, "
        "Victorian era design, gears and pipes, "
        "warm sepia tones, industrial atmosphere."
    ),
    "cyberpunk": (
        "cyberpunk style, neon-lit rainy streets, "
        "high-tech low-life aesthetic, holographic ads, "
        "dark with vibrant neon accents, futuristic dystopia."
    ),
    "vaporwave": (
        "vaporwave aesthetic, neon pink and cyan colors, "
        "1980s synthwave grids, chrome surfaces, "
        "retro-futuristic vibe, glowing geometric shapes."
    ),
}

# ==============================================================================
# ★ v29 — PRESETS COMBINÉS (audio + visuel) prêts à l'emploi
# ------------------------------------------------------------------------------
# Utilisation rapide : un seul mot-clé pour tout un univers
# ==============================================================================
COMBINED_PRESETS: Dict[str, Dict[str, str]] = {
    "mini_film_carton": {
        "visual": "cardboard_cutout",
        "audio": "romantic",
        "description": "Mini-film carton avec musique romantique",
    },
    "comedie_cartoon": {
        "visual": "cartoon_flat",
        "audio": "cartoon",
        "description": "Animation cartoon comique",
    },
    "bd_aventure": {
        "visual": "bd_francaise",
        "audio": "epic",
        "description": "Bande dessinée d'aventure épique",
    },
    "polar_noir": {
        "visual": "film_noir",
        "audio": "noir",
        "description": "Polar en noir et blanc",
    },
    "cinema_muet": {
        "visual": "old_cinema",
        "audio": "vintage",
        "description": "Cinéma muet vintage",
    },
    "peinture_vivante": {
        "visual": "static_painting",
        "audio": "opera",
        "description": "Peinture classique animée",
    },
    "pate_a_modeler": {
        "visual": "claymation",
        "audio": "children",
        "description": "Stop-motion claymation jeunesse",
    },
    "retro_gaming": {
        "visual": "pixel_art",
        "audio": "retro",
        "description": "Jeu vidéo rétro pixel art",
    },
    "anime_poetique": {
        "visual": "anime_ghibli",
        "audio": "nature",
        "description": "Anime poétique Ghibli",
    },
    "cyber_aventure": {
        "visual": "cyberpunk",
        "audio": "futuristic",
        "description": "Aventure cyberpunk futuriste",
    },
    "manga_action": {
        "visual": "manga",
        "audio": "rock",
        "description": "Manga d'action intense",
    },
    "voyage_oriental": {
        "visual": "watercolor",
        "audio": "oriental",
        "description": "Voyage poétique oriental",
    },
}

# ==============================================================================
# ★ v29 — EFFETS SPÉCIAUX VISUELS (à ajouter au prompt)
# ------------------------------------------------------------------------------
# Utilisation : "special_effect": "slow_motion" dans [ACTION:generate_video]
# ==============================================================================
SPECIAL_EFFECTS: Dict[str, str] = {
    "slow_motion": "slow motion effect, smooth gentle movements",
    "fast_motion": "fast motion, sped up dynamic action",
    "time_lapse": "time lapse effect, accelerated natural changes",
    "freeze_frame": "freeze frame at climactic moment, static pose",
    "zoom_in": "smooth zoom in, camera pushing closer",
    "zoom_out": "smooth zoom out, camera pulling away",
    "pan_left": "camera panning left smoothly",
    "pan_right": "camera panning right smoothly",
    "shake": "subtle camera shake, dynamic handheld feel",
    "vignette": "vignette edges, darkened corners, cinematic focus",
    "grain": "film grain overlay, vintage texture",
    "vhs_glitch": "VHS glitch effects, tracking distortion, retro analog",
    "glitch": "digital glitch effects, RGB split, cyberpunk distortion",
    "lens_flare": "cinematic lens flare, warm light streak",
    "bokeh": "shallow depth of field, soft bokeh background",
    "fog": "atmospheric fog, misty environment",
    "rain": "rain falling, wet surfaces, reflections",
    "snow": "snow falling gently, winter atmosphere",
    "sparkles": "magical sparkles, glitter particles floating",
    "smoke": "wisps of smoke, atmospheric haze",
    "flashback": "flashback effect, sepia desaturated, memory vibe",
}

# ==============================================================================
# CHEMINS & MEDIA
# ==============================================================================
SUPPORTED_IMAGE_EXTENSIONS: tuple = (".png", ".jpg", ".jpeg", ".webp")
SUPPORTED_VIDEO_EXTENSIONS: tuple = (".mp4", ".webm", ".mov")
SUPPORTED_MEDIA_EXTENSIONS: tuple = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS

# ==============================================================================
# ★ v29 — HELPERS DE RÉSOLUTION (pour usage rapide)
# ==============================================================================

def resolve_audio_prompt(audio_style: str) -> str:
    """
    Retourne la description audio pour un style donné.
    Fallback sur "default" si le style n'existe pas.
    """
    return AUDIO_STYLE_PROMPTS.get(audio_style, AUDIO_STYLE_PROMPTS["default"])


def resolve_visual_preset(preset_name: str) -> str:
    """
    Retourne la description visuelle pour un preset donné.
    Fallback sur chaîne vide si le preset n'existe pas.
    """
    return VISUAL_STYLE_PRESETS.get(preset_name, "")


def resolve_combined_preset(preset_name: str) -> Dict[str, str]:
    """
    Retourne {visual, audio, description} pour un preset combiné.
    Fallback sur "mini_film_carton" si inconnu.
    """
    return COMBINED_PRESETS.get(preset_name, COMBINED_PRESETS["mini_film_carton"])


def resolve_special_effect(effect_name: str) -> str:
    """
    Retourne la description d'un effet spécial.
    Fallback sur chaîne vide si inconnu.
    """
    return SPECIAL_EFFECTS.get(effect_name, "")


def list_all_audio_styles() -> List[str]:
    """Retourne la liste triée des styles audio disponibles."""
    return sorted(AUDIO_STYLE_PROMPTS.keys())


def list_all_visual_presets() -> List[str]:
    """Retourne la liste triée des presets visuels disponibles."""
    return sorted(VISUAL_STYLE_PRESETS.keys())


def list_all_combined_presets() -> List[str]:
    """Retourne la liste triée des presets combinés disponibles."""
    return sorted(COMBINED_PRESETS.keys())


def list_all_special_effects() -> List[str]:
    """Retourne la liste triée des effets spéciaux disponibles."""
    return sorted(SPECIAL_EFFECTS.keys())