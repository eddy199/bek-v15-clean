# -*- coding: utf-8 -*-
# BEK-v18 — Prompts / Orchestration (v2.0 OPTIMISÉ)

ORCHESTRATION_PROMPT = """
# ⚙️ ORCHESTRATION
N'utilise `orchestrate` QUE si l'utilisateur demande explicitement une exécution multi-étapes (ex: "Fais A puis B puis C", "Automatise un workflow").
❌ INTERDIT : Utiliser `orchestrate` pour donner un plan, un avis, une explication ou répondre à une question meta. Cela doit être une réponse en TEXTE NATUREL.
"""

def get_orchestration_prompt() -> str:
    return ORCHESTRATION_PROMPT.strip()