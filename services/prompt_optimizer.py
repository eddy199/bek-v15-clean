# -*- coding: utf-8 -*-
# ==============================================================================
# BEK Prompt Optimizer Skill — Réécriture artistique haute précision
# ==============================================================================
from __future__ import annotations

def optimize_prompt_for_media(raw_prompt: str, media_type: str = "image", style_preset: str = "cardboard_3d") -> str:
    clean_raw = raw_prompt.strip()
    
    styles = {
        "cardboard_3d": "3D animated movie style, vibrant colors, expressive character design, high detail.",
        "cinematic_video": "Cinematic 4K shot, seamless motion dynamics, photorealistic lighting, smooth professional camera movement."
    }
    
    preset_text = styles.get(style_preset, styles["cardboard_3d"])

    if media_type == "image":
        # On place la description exacte de l'utilisateur au premier plan pour éviter qu'elle soit coupée
        optimized = f"{clean_raw}, rendered in {preset_text}, ultra-sharp focus, cohesive lighting, perfect composition."
    else:
        optimized = f"{clean_raw}, {preset_text}, fluid physics, high temporal stability."
        
    return optimized