# -*- coding: utf-8 -*-
# BEK-v18 — Prompts / Image (v2.0 OPTIMISÉ)

IMAGE_PROMPT = """
# 🎨 GÉNÉRATION D'IMAGE
Quand l'utilisateur demande une image/logo : EXÉCUTE `generate_image` IMMÉDIATEMENT.
- Ne décris pas l'image en texte. Ne demande pas de confirmation.
- Le prompt doit être en ANGLAIS, court (20-30 mots).
- Modèle par défaut : `"provider": "pollinations", "model": "flux"`.
"""

def get_image_prompt() -> str:
    return IMAGE_PROMPT.strip()