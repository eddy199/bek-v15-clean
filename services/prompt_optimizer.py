# -*- coding: utf-8 -*-
# ==============================================================================
# BEK Prompt Optimizer — Réécriture artistique haute précision
# ------------------------------------------------------------------------------
# v22 (2026-09-20) :
#   - Ajout des suffixes vidéo : style, cohérence personnages, technique
#   - Ajout de optimize_video_prompt_for_clip() pour Veo multi-clips
#   - Compatible avec l'appel existant optimize_prompt_for_media()
#   - Aucune régression sur le mode image
# ==============================================================================
from __future__ import annotations

import logging

logger = logging.getLogger("bek.prompt_optimizer")


# ==============================================================================
# SUFFIXES VIDÉO
# ------------------------------------------------------------------------------
# Ajoutés automatiquement pour améliorer la qualité et la cohérence Veo.
# ==============================================================================
VIDEO_STYLE_SUFFIX = (
    "Animation 3D colorée, style film d'animation pour enfants, "
    "mouvements fluides et naturels, caméra stable, éclairage doux, "
    "ambiance joyeuse et chaleureuse."
)

VIDEO_CONSISTENCY_SUFFIX = (
    "Cohérence stricte des personnages : mêmes visages, mêmes coiffures, "
    "mêmes vêtements, mêmes couleurs, même décor, même direction artistique "
    "du début à la fin."
)

VIDEO_TECH_SUFFIX = (
    "Haute qualité, 24 fps, pas de flou de mouvement excessif, "
    "pas d'artefacts, pas de déformation des visages ou des mains."
)

IMAGE_STYLE_SUFFIX = (
    "Rendu haute qualité, éclairage cinématographique, composition équilibrée, "
    "couleurs vives et harmonieuses."
)


# ==============================================================================
# FONCTION PRINCIPALE (compatible avec l'existant)
# ------------------------------------------------------------------------------
# Signature inchangée : optimize_prompt_for_media(raw_prompt, media_type, style_preset)
# Utilisée par :
#   - vision.py (image + vidéo single clip)
#   - action_executor.py (generate_image)
# ==============================================================================
def optimize_prompt_for_media(
    raw_prompt: str,
    media_type: str = "image",
    style_preset: str = "cardboard_3d",
) -> str:
    clean_raw = (raw_prompt or "").strip()
    if not clean_raw:
        return clean_raw

    # --------- Styles par preset ---------
    styles = {
        "cardboard_3d": (
            "3D animated movie style, vibrant colors, expressive character "
            "design, high detail, cardboard cutout craft material."
        ),
        "cinematic_video": (
            "Cinematic 4K shot, seamless motion dynamics, photorealistic "
            "lighting, smooth professional camera movement."
        ),
    }
    preset_text = styles.get(style_preset, styles["cardboard_3d"])

    # --------- IMAGE ---------
    if media_type == "image":
        return (
            f"{clean_raw}, rendered in {preset_text}, "
            f"{IMAGE_STYLE_SUFFIX}"
        )

    # --------- VIDÉO (single clip) ---------
    parts = [
        clean_raw,
        preset_text,
        VIDEO_STYLE_SUFFIX,
        VIDEO_CONSISTENCY_SUFFIX,
        VIDEO_TECH_SUFFIX,
    ]
    return " ".join(parts)


# ==============================================================================
# PROMPT PAR CLIP (Veo multi-clips)
# ------------------------------------------------------------------------------
# Utilisée par vision._veo_generate_stitched() pour garantir la continuité
# narrative et visuelle entre les clips.
# ==============================================================================
def optimize_video_prompt_for_clip(
    base_prompt: str,
    clip_index: int,
    total_clips: int,
    clip_duration: int,
    aspect_ratio: str = "16:9",
) -> str:
    """
    Génère un prompt pour un clip spécifique d'une série Veo,
    avec continuité narrative et cohérence des personnages.

    Exemple :
        optimize_video_prompt_for_clip(
            base_prompt="Trois enfants dansent sur A Ram Sam Sam.",
            clip_index=2,
            total_clips=2,
            clip_duration=7,
            aspect_ratio="16:9",
        )
    """
    base = (base_prompt or "").strip()
    if not base:
        base = "Séquence d'animation 3D pour enfants."

    header = (
        f"[Clip {clip_index}/{total_clips}] "
        f"Suite directe du clip précédent. "
    )

    continuity = (
        "Conserve EXACTEMENT les mêmes personnages (visages, coiffures, "
        "vêtements, couleurs), le même décor, le même style visuel et la "
        "même direction artistique. La caméra reprend au même endroit "
        "ou dans une continuité logique."
    )

    return (
        f"{header}{base}. {continuity} "
        f"Durée : {clip_duration} secondes, format {aspect_ratio}. "
        f"{VIDEO_TECH_SUFFIX}"
    )


# ==============================================================================
# ALIAS (compatibilité)
# ------------------------------------------------------------------------------
# Si un ancien module importe `optimize_prompt` au lieu de
# `optimize_prompt_for_media`, on garde un alias.
# ==============================================================================
optimize_prompt = optimize_prompt_for_media