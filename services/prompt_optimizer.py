# -*- coding: utf-8 -*-
# ==============================================================================
# BEK Prompt Optimizer — Réécriture artistique haute précision
# ------------------------------------------------------------------------------
# v22 (2026-09-20) :
#   - Suffixes vidéo (style, cohérence personnages, technique)
#   - optimize_video_prompt_for_clip() pour Veo multi-clips
#
# v23 (2026-09-29) :
#   - 25+ styles visuels prêts à l'emploi
#   - Détection automatique du style depuis le prompt
#   - Composition multi-styles (ex: "cardboard+old_cinema")
#   - Préservation faciale renforcée (FACE LOCK) pour Agnes
#   - Compatible Agnes 2.0, 2.5 et 3.0
#
# v24 (2026-09-30) :
#   - ★ Helpers Agnes V2.5 (syntaxe <Picture N>)
#   - build_agnes_reference_prompt() : prompt avec références
#   - suggest_agnes_mode_v2() : détection auto du mode selon modèle
#   - Retrait des noms hardcodés dans les docstrings
# ==============================================================================
from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger("bek.prompt_optimizer")


# ==============================================================================
# ★ v23 — DICTIONNAIRE DES STYLES VISUELS (25 styles)
# ------------------------------------------------------------------------------
# Pour composer : "style1+style2" (ex: "cardboard+cinema_studio")
# ==============================================================================
STYLE_PRESETS = {
    # ─────────────── CARTOON / ANIMATION ───────────────
    "cardboard": (
        "Physical brown cardboard cutout craft aesthetic, visible textured "
        "cardboard edges, stop-motion claymation vibe, handcrafted feel, "
        "cutout paper characters in theater-style staging, warm handmade "
        "lighting, diorama composition, tactile paper textures, visible "
        "corrugated cardboard material."
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
        "high-quality rendering, cinematic depth."
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

    # ─────────────── CINÉMA / FILM ───────────────
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

    # ─────────────── ART / PEINTURE ───────────────
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

    # ─────────────── RÉTRO / FUTURISTE ───────────────
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

    # ─────────────── RÉALISTE ───────────────
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


# ==============================================================================
# ★ v23 — DÉTECTION AUTOMATIQUE DU STYLE
# ==============================================================================
STYLE_KEYWORDS = {
    "cardboard":      ["carton", "cardboard", "cutout", "artisanal", "diorama"],
    "cardboard_3d":   ["carton 3d", "cardboard 3d"],
    "cartoon_2d":     ["dessin animé", "cartoon", "2d", "disney 90"],
    "pixar_3d":       ["pixar", "dreamworks", "3d lisse", "3d movie"],
    "anime":          ["anime", "manga", "japonais", "ghibli", "otaku"],
    "claymation":     ["pâte à modeler", "claymation", "plasticine", "aardman"],
    "paper_cutout":   ["papier découpé", "paper cutout", "south park"],
    "pixel_art":      ["pixel", "8bit", "16bit", "retro game", "sprite"],
    "low_poly":       ["low poly", "lowpoly", "low-poly", "géométrique"],
    "cinema_studio":  ["cinéma", "cinema", "hollywood", "35mm"],
    "cinematic_video":["vidéo cinéma", "cinematic"],
    "old_cinema":     ["vieux cinéma", "cinéma muet", "années 20", "noir et blanc"],
    "film_noir":      ["film noir", "polar", "années 40", "ambiance sombre"],
    "vhs_retro":      ["vhs", "cassette", "années 80", "analogique"],
    "watercolor":     ["aquarelle", "watercolor", "peinture douce"],
    "oil_painting":   ["huile", "peinture à l'huile", "renaissance", "classique"],
    "sketch":         ["croquis", "esquisse", "crayon", "sketch"],
    "comic_book":     ["bd", "comic", "bande dessinée", "superhéros"],
    "manga_bw":       ["manga", "japonais bd", "shonen"],
    "vaporwave":      ["vaporwave", "synthwave", "néon 80"],
    "cyberpunk":      ["cyberpunk", "futuriste", "néon", "high-tech"],
    "steampunk":      ["steampunk", "vapeur", "victorien", "engrenages"],
    "photorealistic": ["photoréaliste", "réaliste", "photo", "réel"],
    "studio_photo":   ["studio", "photo pro", "commercial"],
}


def detect_style_from_prompt(prompt: str) -> Optional[str]:
    """Détecte automatiquement le style depuis le prompt utilisateur."""
    if not prompt:
        return None
    prompt_lower = prompt.lower()
    for style, keywords in STYLE_KEYWORDS.items():
        if any(kw in prompt_lower for kw in keywords):
            logger.info("[PromptOptimizer] Style détecté : %s", style)
            return style
    return None


def _resolve_style_signature(style_preset: str) -> str:
    """Résout la signature d'un style (supporte "s1+s2")."""
    if not style_preset:
        return ""
    if "+" in style_preset:
        parts = [p.strip() for p in style_preset.split("+") if p.strip()]
        signatures = [STYLE_PRESETS.get(p, "") for p in parts]
        return " ".join(s for s in signatures if s)
    return STYLE_PRESETS.get(style_preset, "")


# ==============================================================================
# ★ v23 — PRÉSERVATION FACIALE RENFORCÉE (FACE LOCK)
# ------------------------------------------------------------------------------
# Ces phrases DOIVENT être ajoutées au prompt Agnes pour forcer la
# préservation des visages. À utiliser QUAND des images de référence sont
# fournies dans image_paths.
# ==============================================================================
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


# ==============================================================================
# SUFFIXES VIDÉO
# ==============================================================================
VIDEO_STYLE_SUFFIX = (
    "Animation fluide, mouvements naturels, caméra stable, "
    "éclairage doux, ambiance chaleureuse."
)

VIDEO_CONSISTENCY_SUFFIX = (
    "Cohérence stricte des personnages : mêmes visages, mêmes coiffures, "
    "mêmes vêtements, mêmes couleurs, même décor du début à la fin."
)

VIDEO_TECH_SUFFIX = (
    "Haute qualité, 24 fps, pas de flou excessif, "
    "pas d'artefacts, pas de déformation des visages ou des mains."
)

IMAGE_STYLE_SUFFIX = (
    "Rendu haute qualité, éclairage cinématographique, composition équilibrée."
)


# ==============================================================================
# ★ v23 — DÉTECTION DU MODE DE GÉNÉRATION (selon nombre d'images)
# ==============================================================================
def suggest_agnes_mode(num_images: int) -> str:
    """
    Suggère le meilleur mode Agnes selon le nombre d'images.

    1 image → "keyframes" (MAX préservation — l'image devient la 1ère frame)
    2+ images → "multi_reference" (composition multi-personnages)
    0 image → "ti2vid" (text-to-video pur)
    """
    if num_images <= 0:
        return "ti2vid"
    if num_images == 1:
        return "keyframes"
    return "multi_reference"


# ==============================================================================
# FONCTION PRINCIPALE — optimize_prompt_for_media
# ==============================================================================
def optimize_prompt_for_media(
    raw_prompt: str,
    media_type: str = "image",
    style_preset: str = "cardboard_3d",
    preserve_faces: bool = False,
    image_count: int = 0,
) -> str:
    """
    Optimise un prompt pour image ou vidéo.

    Args:
        raw_prompt: prompt brut utilisateur
        media_type: "image" ou "video"
        style_preset: nom du style ("cardboard", "cinema_studio", ...)
                      ou composition ("cardboard+old_cinema")
        preserve_faces: si True, ajoute les suffixes FACE LOCK
        image_count: nombre d'images de référence (0, 1, 2...)

    Returns:
        prompt enrichi
    """
    clean_raw = (raw_prompt or "").strip()
    if not clean_raw:
        return clean_raw

    # 1. Détection auto du style si non spécifié
    if style_preset in (None, "", "auto"):
        detected = detect_style_from_prompt(clean_raw)
        style_preset = detected or "cardboard_3d"

    # 2. Signature du style
    preset_text = _resolve_style_signature(style_preset)
    if not preset_text:
        preset_text = STYLE_PRESETS["cardboard_3d"]

    # 3. Suffixe FACE LOCK (uniquement si demandé)
    face_suffix = ""
    if preserve_faces and image_count > 0:
        face_suffix = f" {FACE_PRESERVATION_SUFFIX} {IDENTITY_LOCK_SUFFIX}"

    # 4. IMAGE
    if media_type == "image":
        return (
            f"{clean_raw}. {preset_text}"
            f"{face_suffix} {IMAGE_STYLE_SUFFIX}"
        )

    # 5. VIDÉO
    parts = [
        clean_raw,
        preset_text,
        face_suffix.strip(),
        VIDEO_STYLE_SUFFIX,
        VIDEO_CONSISTENCY_SUFFIX,
        VIDEO_TECH_SUFFIX,
    ]
    return " ".join(p for p in parts if p)


# ==============================================================================
# PROMPT PAR CLIP (Veo / Agnes multi-clips)
# ==============================================================================
def optimize_video_prompt_for_clip(
    base_prompt: str,
    clip_index: int,
    total_clips: int,
    clip_duration: int,
    aspect_ratio: str = "16:9",
    preserve_faces: bool = False,
) -> str:
    """Génère un prompt pour un clip spécifique d'une série."""
    base = (base_prompt or "").strip() or "Séquence d'animation."

    header = f"[Clip {clip_index}/{total_clips}] Suite directe du clip précédent. "

    continuity = (
        "Conserve EXACTEMENT les mêmes personnages (visages, coiffures, "
        "vêtements, couleurs), le même décor, le même style visuel."
    )

    face = f" {FACE_PRESERVATION_SUFFIX}" if preserve_faces else ""

    return (
        f"{header}{base}. {continuity}{face} "
        f"Durée : {clip_duration} secondes, format {aspect_ratio}. "
        f"{VIDEO_TECH_SUFFIX}"
    )


# ==============================================================================
# HELPER PUBLIC — Liste des styles disponibles
# ==============================================================================
def list_styles() -> List[str]:
    """Retourne la liste de tous les styles disponibles."""
    return sorted(STYLE_PRESETS.keys())


def get_style_signature(style_name: str) -> str:
    """Retourne la signature d'un style (ou chaîne vide)."""
    return STYLE_PRESETS.get(style_name, "")


# ==============================================================================
# ★ v24 — HELPERS POUR AGNES V2.5 (syntaxe <Picture N>)
# ==============================================================================
def build_agnes_reference_prompt(
    base_prompt: str,
    num_images: int,
    character_names: Optional[List[str]] = None,
) -> str:
    """
    Construit un prompt Agnes V2.5 avec références <Picture N>.

    Agnes V2.5 utilise la syntaxe <Picture 1>, <Picture 2> pour référencer
    les images fournies dans le paramètre "images". Cette fonction ajoute
    automatiquement les instructions de référence au début du prompt.

    Args:
        base_prompt : prompt de base décrivant la scène
        num_images : nombre d'images de référence
        character_names : (optionnel) liste de noms à associer à chaque image
                         Ex: ["Person A", "Person B"] pour 2 images.
                         Si None ou liste trop courte, utilise juste <Picture N>.

    Returns:
        Prompt formaté avec références <Picture N>.

    Exemples :
        # Sans noms
        build_agnes_reference_prompt(
            "They discuss in a cardboard house",
            2
        )
        → "Refer to the provided images as <Picture 1>, <Picture 2>.
           Use their EXACT facial features.
           They discuss in a cardboard house"

        # Avec noms génériques
        build_agnes_reference_prompt(
            "They discuss in a cardboard house",
            2,
            ["Person A", "Person B"]
        )
        → "Refer to <Picture 1> as Person A, <Picture 2> as Person B.
           Use their EXACT facial features, hair, and appearance.
           DO NOT invent new faces.
           They discuss in a cardboard house"
    """
    if num_images <= 0:
        return base_prompt

    if character_names and len(character_names) >= num_images:
        # Avec noms explicites
        refs = ", ".join(
            f"<Picture {i+1}> as {character_names[i]}"
            for i in range(num_images)
        )
        prefix = (
            f"Refer to {refs}. "
            f"Use their EXACT facial features, hair, and appearance. "
            f"DO NOT invent new faces. "
        )
    else:
        # Sans noms — références génériques
        refs = ", ".join(f"<Picture {i+1}>" for i in range(num_images))
        prefix = (
            f"Refer to the provided images as {refs}. "
            f"Use their EXACT facial features. "
            f"DO NOT invent new faces. "
        )

    return prefix + base_prompt


def suggest_agnes_mode_v2(model_id: str, num_images: int) -> str:
    """
    Suggère le mode Agnes correct selon le modèle et le nombre d'images.

    Règles :
        - 0 image → "ti2vid" (text-to-video)
        - 1 image → "keyframes" (image = première frame)
        - 2+ images + Agnes V2.5+ → "reference" (syntaxe <Picture N>)
        - 2+ images + Agnes V2.0  → "multi_reference" (param reference_images)

    Args:
        model_id : identifiant du modèle (ex: "agnes-video-2.5-flash")
        num_images : nombre d'images de référence

    Returns:
        Nom du mode à utiliser pour l'API Agnes.
    """
    if num_images <= 0:
        return "ti2vid"

    if num_images == 1:
        return "keyframes"

    # Plusieurs images → dépend de la version du modèle
    if "2.5" in model_id or "3.0" in model_id or "3.5" in model_id:
        return "reference"  # Agnes V2.5+ (gratuit, syntaxe <Picture N>)
    return "multi_reference"  # Agnes V2.0 (fallback)


# ==============================================================================
# ALIAS (compatibilité avec l'ancien code)
# ==============================================================================
optimize_prompt = optimize_prompt_for_media