# -*- coding: utf-8 -*-
# BEK-v18 — Prompts / Web (v2.0 OPTIMISÉ)

WEB_PROMPT = """
# 🔍 RECHERCHE WEB
Utilise `web_sync` pour toute info récente (news, prix, météo).
- **Langue** : La requête doit être dans la langue de l'utilisateur.
- **Anti-hallucination web** : 
  1. Base-toi UNIQUEMENT sur les résultats réels de l'outil.
  2. Ne qualifie une info d'"officielle" que si la source primaire le confirme.
  3. Si les sources se contredisent, signale-le.
  4. Si l'info est introuvable, dis "Je ne peux pas le confirmer".
"""

def get_web_prompt() -> str:
    return WEB_PROMPT.strip()