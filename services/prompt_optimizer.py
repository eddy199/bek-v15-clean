# -*- coding: utf-8 -*-
# ==============================================================================
# BEK Prompt Optimizer — Réécriture artistique haute précision
# ------------------------------------------------------------------------------
# v26 (2026-10-06) : FIX CONTRADICTIONS + 3D DÉTECTION
# ==============================================================================
from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger("bek.prompt_optimizer")

STYLE_PRESETS = {
    "flat_vector": (
        "Flat vector logo design, minimalist, clean geometric lines, "
        "scalable icon style, professional branding quality, "
        "symmetrical composition, simple shapes, modern tech aesthetic, "
        "2D flat illustration."
    ),
    "logo_modern": (
        "Modern minimalist logo, sharp geometric shapes, elegant "
        "typography, monogram style, professional corporate branding, "
        "clean vector art, high contrast, timeless design."
    ),
    "cardboard": (
        "Physical brown cardboard cutout craft aesthetic, visible textured "
        "cardboard edges, stop-motion claymation vibe, handcrafted feel, "
        "cutout paper characters in theater-style staging, warm handmade "
        "lighting, diorama composition, tactile paper textures."
    ),
    "cardboard_3d": (
        "3D animated movie style with cardboard cutout craft material, "
        "expressive character design, visible brown cardboard texture, "
        "stop-motion aesthetic, vibrant colors, high detail."
    ),
    "cartoon_2d": (
        "Classic 2D hand-drawn cartoon animation, bold outlines, flat "
        "colors with cel shading, Disney Renaissance 90s style, expressive "
        "characters, exaggerated proportions, vibrant palette."
    ),
    "pixar_3d": (
        "Modern 3D animation like Pixar or DreamWorks, smooth surfaces, "
        "detailed lighting, soft shadows, expressive stylized characters, "
        "high-quality rendering, cinematic depth, vibrant colors, "
        "professional CGI quality."
    ),
    "anime": (
        "Japanese anime style, Studio Ghibli inspired, cel-shaded animation, "
        "expressive large eyes, vibrant pastel colors, hand-drawn quality, "
        "detailed background art, soft atmospheric lighting."
    ),
    "claymation": (
        "Stop-motion claymation in the style of Wallace & Gromit or Aardman, "
        "handcrafted plasticine characters, visible fingerprints in clay, "
        "practical lighting, miniature sets, tactile texture."
    ),
    "paper_cutout": (
        "Paper cutout animation like South Park or Monty Python, flat "
        "construction-paper characters, simple shapes, visible paper "
        "texture, layered collage composition."
    ),
    "pixel_art": (
        "8-bit or 16-bit pixel art, retro video game style, chunky visible "
        "pixels, limited color palette, sprite-based characters, NES/SNES "
        "aesthetic, nostalgic gaming vibe."
    ),
    "low_poly": (
        "Stylized low-poly 3D art, geometric faceted surfaces, minimal "
        "polygon count, flat-shaded triangles, modern indie game aesthetic, "
        "clean color blocks."
    ),
    "cinema_studio": (
        "Hollywood cinematic quality, 35mm film grain, dramatic lighting, "
        "cinematographic composition, professional studio setup, anamorphic "
        "lens flares, deep depth of field, rich color grading."
    ),
    "cinematic_video": (
        "Cinematic 4K shot, seamless motion dynamics, photorealistic "
        "lighting, smooth professional camera movement, film-grade color "
        "grading, anamorphic widescreen."
    ),
    "old_cinema": (
        "Silent film era 1920s, black and white with film grain, high "
        "contrast noir lighting, vintage sepia tones, dramatic shadows, "
        "classic Hollywood glamour, vignette edges."
    ),
    "film_noir": (
        "Film noir 1940s style, high contrast black and white, harsh "
        "directional lighting, deep shadows, cigarette smoke ambiance, "
        "moody atmospheric tension, detective aesthetic."
    ),
    "vhs_retro": (
        "VHS tape aesthetic from the 1980s, analog video artifacts, color "
        "bleeding, scanlines, tracking distortion, nostalgic home-video "
        "quality, warm retro colors."
    ),
    "watercolor": (
        "Traditional watercolor painting, soft translucent washes, visible "
        "brush strokes, paper texture, bleeding colors, artistic "
        "imperfections, delicate composition."
    ),
    "oil_painting": (
        "Classical oil painting, visible thick brush strokes, rich impasto "
        "texture, dramatic chiaroscuro lighting, Renaissance masters style, "
        "canvas texture, warm earthy palette."
    ),
    "sketch": (
        "Hand-drawn pencil sketch, visible graphite strokes, cross-hatching "
        "shading, sketchbook aesthetic, rough unfinished quality, artistic "
        "line work, monochrome."
    ),
    "comic_book": (
        "American comic book style, bold black ink outlines, dynamic action "
        "poses, halftone dots for shading, vibrant primary colors, speech "
        "bubble ready, superhero aesthetic."
    ),
    "manga_bw": (
        "Japanese manga black and white, screentone shading, expressive "
        "line art, dramatic angles, detailed backgrounds, shonen or shojo "
        "style, clean panel composition."
    ),
    "vaporwave": (
        "Vaporwave aesthetic, neon pink and cyan colors, 1980s synthwave "
        "grids, chrome surfaces, retro-futuristic vibe, geometric shapes, "
        "glowing neon lights."
    ),
    "cyberpunk": (
        "Cyberpunk style, neon-lit rainy streets, high-tech low-life, "
        "holographic advertisements, dark atmosphere with vibrant neon "
        "accents, futuristic dystopia."
    ),
    "steampunk": (
        "Steampunk aesthetic, brass and copper machinery, steam-powered "
        "technology, Victorian era design, gears and pipes, brown leather, "
        "sepia industrial tones."
    ),
    "photorealistic": (
        "Ultra-photorealistic, hyper-detailed textures, natural lighting, "
        "professional photography, sharp focus, shallow depth of field, "
        "lifelike colors."
    ),
    "studio_photo": (
        "Professional studio photography, controlled three-point lighting, "
        "seamless backdrop, sharp product focus, high-end commercial "
        "quality, magazine-grade finish."
    ),
}

STYLE_KEYWORDS = {
    "flat_vector": ["logo", "logotype", "logomark", "icône", "icone", "icon", "symbole", "symbol", "monogramme", "monogram", "marque", "brand", "vectoriel", "vector", "flat", "plat", "minimaliste", "minimalist", "épuré", "epure", "mobile app", "mobileapp", "mobile", "app", "ios", "android"],
    "logo_modern": ["logo moderne", "modern logo", "logo tech", "tech logo", "logo entreprise", "company logo"],
    "pixar_3d": ["3d animated", "3danimated", "3d animation", "3d scene", "3d render", "pixar", "dreamworks", "3d cartoon", "3d style", "3d movie", "3d character", "3d personnage", "scène 3d", "scene 3d", "render 3d"],
    "cardboard": ["carton", "cardboard", "cutout", "artisanal", "diorama"],
    "cardboard_3d": ["carton 3d", "cardboard 3d"],
    "cartoon_2d": ["dessin animé", "cartoon", "2d", "disney 90"],
    "anime": ["anime", "manga", "japonais", "ghibli", "otaku"],
    "claymation": ["pâte à modeler", "claymation", "plasticine", "aardman"],
    "paper_cutout": ["papier découpé", "paper cutout", "south park"],
    "pixel_art": ["pixel", "8bit", "16bit", "retro game", "sprite"],
    "low_poly": ["low poly", "lowpoly", "low-poly", "géométrique"],
    "cinema_studio": ["cinéma", "cinema", "hollywood", "35mm"],
    "cinematic_video": ["vidéo cinéma", "cinematic"],
    "old_cinema": ["vieux cinéma", "cinéma muet", "années 20", "noir et blanc"],
    "film_noir": ["film noir", "polar", "années 40", "ambiance sombre"],
    "vhs_retro": ["vhs", "cassette", "années 80", "analogique"],
    "watercolor": ["aquarelle", "watercolor", "peinture douce"],
    "oil_painting": ["huile", "peinture à l'huile", "renaissance", "classique"],
    "sketch": ["croquis", "esquisse", "crayon", "sketch"],
    "comic_book": ["bd", "comic", "bande dessinée", "superhéros"],
    "manga_bw": ["japonais bd", "shonen"],
    "vaporwave": ["vaporwave", "synthwave", "néon 80"],
    "cyberpunk": ["cyberpunk", "futuriste", "néon", "high-tech"],
    "steampunk": ["steampunk", "vapeur", "victorien", "engrenages"],
    "photorealistic": ["photoréaliste", "réaliste", "photo", "réel"],
    "studio_photo": ["studio", "photo pro", "commercial"],
}

def detect_style_from_prompt(prompt: str) -> Optional[str]:
    if not prompt: return None
    prompt_lower = prompt.lower()
    logo_keywords = ["logo", "icône", "icone", "icon", "symbole", "symbol", "monogramme", "monogram", "marque", "brand", "mobile app", "mobileapp", "app", "ios", "android"]
    if any(kw in prompt_lower for kw in logo_keywords):
        if "moderne" in prompt_lower or "modern" in prompt_lower:
            return "logo_modern"
        return "flat_vector"
    keywords_3d = ["3d animated", "3danimated", "3d animation", "3d scene", "3d render", "pixar", "dreamworks", "3d cartoon", "3d style", "3d movie", "3d character", "3d personnage", "scène 3d", "scene 3d", "render 3d"]
    if any(kw in prompt_lower for kw in keywords_3d):
        return "pixar_3d"
    for style, keywords in STYLE_KEYWORDS.items():
        if style in ("flat_vector", "logo_modern", "pixar_3d"): continue
        if any(kw in prompt_lower for kw in keywords):
            return style
    return None

def _resolve_style_signature(style_preset: str) -> str:
    if not style_preset: return ""
    if "+" in style_preset:
        parts = [p.strip() for p in style_preset.split("+") if p.strip()]
        signatures = [STYLE_PRESETS.get(p, "") for p in parts]
        return " ".join(s for s in signatures if s)
    return STYLE_PRESETS.get(style_preset, "")

FACE_PRESERVATION_SUFFIX = (
    "FACE LOCK — CRITICAL: The reference images show REAL people. "
    "You MUST preserve their EXACT facial identity. Same face shape, same "
    "eyes (color and shape), same nose, same mouth, same hair (color, length, "
    "style), same skin tone, same age. The characters in the output MUST be "
    "IMMEDIATELY RECOGNIZABLE as the same people from the reference images. "
    "This is a STYLIZED CARICATURE of the SAME PERSON — not a new character. "
    "DO NOT invent a new face. DO NOT change ethnic features. DO NOT age or "
    "rejuvenate. DO NOT idealize. Preserve every distinctive feature."
)

IDENTITY_LOCK_SUFFIX = (
    "IDENTITY LOCK: same person, same face, same identity, same ethnicity. "
    "Verify that the output face matches the input reference face."
)

VIDEO_STYLE_SUFFIX = "Animation fluide, mouvements naturels, caméra stable, éclairage doux, ambiance chaleureuse."
VIDEO_CONSISTENCY_SUFFIX = "Cohérence stricte des personnages : mêmes visages, mêmes coiffures, mêmes vêtements, mêmes couleurs, même décor du début à la fin."
VIDEO_TECH_SUFFIX = "Haute qualité, 24 fps, pas de flou excessif, pas d'artefacts, pas de déformation des visages ou des mains."
IMAGE_STYLE_SUFFIX = "Rendu haute qualité, éclairage cinématographique, composition équilibrée."

def suggest_agnes_mode(num_images: int) -> str:
    if num_images <= 0: return "ti2vid"
    if num_images == 1: return "keyframes"
    return "multi_reference"

def optimize_prompt_for_media(raw_prompt: str, media_type: str = "image", style_preset: str = "auto", preserve_faces: bool = False, image_count: int = 0) -> str:
    clean_raw = (raw_prompt or "").strip()
    if not clean_raw: return clean_raw

    if style_preset in (None, "", "auto"):
        detected = detect_style_from_prompt(clean_raw)
        if detected:
            style_preset = detected
            logger.info("[PromptOptimizer] Style auto-détecté : %s", style_preset)
        else:
            style_preset = "flat_vector" if media_type == "image" else "pixar_3d"
            logger.info("[PromptOptimizer] Aucun style détecté → défaut %s", style_preset)

    preset_text = _resolve_style_signature(style_preset)
    if not preset_text: preset_text = STYLE_PRESETS["flat_vector"]

    face_suffix = ""
    if preserve_faces and image_count > 0:
        face_suffix = f" {FACE_PRESERVATION_SUFFIX} {IDENTITY_LOCK_SUFFIX}"

    if media_type == "image":
        return f"{clean_raw}. {preset_text}{face_suffix} {IMAGE_STYLE_SUFFIX}"

    parts = [clean_raw, preset_text, face_suffix.strip(), VIDEO_STYLE_SUFFIX, VIDEO_CONSISTENCY_SUFFIX, VIDEO_TECH_SUFFIX]
    return " ".join(p for p in parts if p)

def optimize_video_prompt_for_clip(base_prompt: str, clip_index: int, total_clips: int, clip_duration: int, aspect_ratio: str = "16:9", preserve_faces: bool = False) -> str:
    base = (base_prompt or "").strip() or "Séquence d'animation."
    header = f"[Clip {clip_index}/{total_clips}] Suite directe du clip précédent. "
    continuity = "Conserve EXACTEMENT les mêmes personnages (visages, coiffures, vêtements, couleurs), le même décor, le même style visuel."
    face = f" {FACE_PRESERVATION_SUFFIX}" if preserve_faces else ""
    return f"{header}{base}. {continuity}{face} Durée : {clip_duration} secondes, format {aspect_ratio}. {VIDEO_TECH_SUFFIX}"

def list_styles() -> List[str]:
    return sorted(STYLE_PRESETS.keys())

def get_style_signature(style_name: str) -> str:
    return STYLE_PRESETS.get(style_name, "")

def build_agnes_reference_prompt(base_prompt: str, num_images: int, character_names: Optional[List[str]] = None) -> str:
    if num_images <= 0: return base_prompt
    if character_names and len(character_names) >= num_images:
        refs = ", ".join(f"<Picture {i+1}> as {character_names[i]}" for i in range(num_images))
        prefix = f"Refer to {refs}. Use their EXACT facial features, hair, and appearance. DO NOT invent new faces. "
    else:
        refs = ", ".join(f"<Picture {i+1}>" for i in range(num_images))
        prefix = f"Refer to the provided images as {refs}. Use their EXACT facial features. DO NOT invent new faces. "
    return prefix + base_prompt

def suggest_agnes_mode_v2(model_id: str, num_images: int) -> str:
    if num_images <= 0: return "ti2vid"
    if num_images == 1: return "keyframes"
    if "2.5" in model_id or "3.0" in model_id or "3.5" in model_id: return "reference"
    return "multi_reference"

optimize_prompt = optimize_prompt_for_media