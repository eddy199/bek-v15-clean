# -*- coding: utf-8 -*-
# BEK-v18 — Prompts / Video (v2.0 OPTIMISÉ)

VIDEO_PROMPT = """
# 🎬 GÉNÉRATION VIDÉO
Quand l'utilisateur demande une vidéo : EXÉCUTE `generate_video` IMMÉDIATEMENT.
- Ne décris pas la vidéo en texte. Ne demande pas de confirmation.
- Le prompt doit être en ANGLAIS, court (20-30 mots).
- Paramètres OBLIGATOIRES : `"provider": "agnes", "model": "agnes-v2.5-flash"`.
- ❌ N'utilise JAMAIS `agnes-v2.0` (il n'existe plus).
"""

def get_video_prompt() -> str:
    return VIDEO_PROMPT.strip()