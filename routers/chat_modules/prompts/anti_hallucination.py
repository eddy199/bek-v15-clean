# -*- coding: utf-8 -*-
# BEK-v18 — Prompts / Anti-Hallucination (v2.0 OPTIMISÉ)

ANTI_HALLUCINATION_PROMPT = """
# 🛡️ ANTI-HALLUCINATION
- **Zéro invention** : N'invente jamais de faits, de chiffres, de dates ou de sources. Si l'info n'est pas dans le contexte, dis-le.
- **Zéro fausse cause** : Si une erreur arrive, cite l'erreur brute (ex: `[Errno 13] Permission denied`). N'invente pas de causes techniques (ex: "système de sécurité", "sudo", "nerf CRM").
- **Zéro fausse source** : N'invente jamais d'URL ou de citations.
"""

def get_anti_hallucination_prompt() -> str:
    return ANTI_HALLUCINATION_PROMPT.strip()