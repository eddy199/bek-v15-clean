# -*- coding: utf-8 -*-
# BEK-v18 — Prompts / Lang (v2.0 OPTIMISÉ)

LANG_PROMPT = """
# 🌐 LANGUE
Règle absolue : Réponds TOUJOURS dans la langue de l'utilisateur (FR, EN, etc.). 
- Ne traduis JAMAIS la réponse finale.
- Les requêtes `web_sync` doivent utiliser la même langue que l'utilisateur.
- Garde les noms propres et termes techniques (API, JSON, LLM) en anglais.
"""

def get_lang_prompt() -> str:
    return LANG_PROMPT.strip()