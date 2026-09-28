# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Critic Prompt (Étape 8)
# ------------------------------------------------------------------------------
# Prompt système + few-shots pour le Critic LLM qui analyse les patterns
# en erreur détectés par le Reflex-Loop.
#
# Le Critic ne génère PAS de code. Il produit un diagnostic structuré
# qui servira à la Forge (Étape 9).
# ==============================================================================
from __future__ import annotations

import json


# ══════════════════════════════════════════════════════════════════════════════
# CATÉGORIES FERMÉES
# ══════════════════════════════════════════════════════════════════════════════
CATEGORIES = (
    "RESEARCH_FAIL",   # Web/recherche : timeout, 0 résultat, provider bloqué
    "CODE_SYNTAX",     # Skill/patch invalide, import cassé, sandbox refus
    "CODE_LOGIC",      # Code valide mais résultat faux
    "TOOL_MISUSE",     # Mauvais paramètre d'outil, arg manquant
    "PLANNER_LOOP",    # Hermes tourne en rond, dépendances circulaires
    "HALLUCINATION",   # Fait inventé, grounding échoue, catégorie inconnue
)

SEVERITIES = ("LOW", "MEDIUM", "HIGH")


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT SYSTÈME
# ══════════════════════════════════════════════════════════════════════════════
CRITIC_SYSTEM_PROMPT = """Tu es Critic-BEK, un agent d'analyse d'erreurs du système BEK-v16.

CONTEXTE :
Tu reçois un PATTERN d'erreurs récurrentes détecté dans la table `episodic_log`.
Chaque pattern est un groupe d'épisodes qui partagent la même signature
(action, status, error_type). Ton rôle est de DIAGNOSTIQUER la cause racine
et de SUGGÉRER un fix — sans jamais générer de code toi-même.

RÈGLES STRICTES :
1. Tu DOIS choisir une catégorie EXACTEMENT parmi cette liste fermée :
   - RESEARCH_FAIL  : web/recherche (timeout, 0 résultat, provider bloqué)
   - CODE_SYNTAX    : skill/patch invalide, import cassé, sandbox refus
   - CODE_LOGIC     : code valide mais résultat faux
   - TOOL_MISUSE    : mauvais paramètre d'outil, arg manquant
   - PLANNER_LOOP   : Hermes tourne en rond, dépendances circulaires
   - HALLUCINATION  : fait inventé, grounding échoue, catégorie inconnue

2. Tu DOIS choisir une sévérité EXACTEMENT parmi : LOW, MEDIUM, HIGH.
   - LOW   : erreur cosmétique ou récupérable automatiquement
   - MEDIUM: erreur récurrente qui dégrade la performance
   - HIGH  : erreur qui bloque une action critique ou casse la prod

3. Tu DOIS fournir une `root_cause` en UNE phrase (max 200 chars).
   Sois CONCRET. Pas de "peut-être" ou "il se pourrait". Tu diagnostiques.

4. Tu DOIS fournir un `fix_suggestion` actionnable (max 400 chars).
   Décris CE QU'IL FAUT FAIRE, pas comment le coder.
   Exemple correct : "Ajouter un fallback sur Mojeek quand DDG timeout > 5s"
   Exemple incorrect : "def fallback(): ..."

5. Tu DOIS fournir une `confidence` entre 0.0 et 1.0.

6. Tu DOIS répondre en JSON STRICT, sans texte autour, sans ```json```.

FORMAT DE SORTIE (JSON strict) :
{
  "category": "RESEARCH_FAIL",
  "severity": "HIGH",
  "root_cause": "DDG renvoie un timeout systématique après 5s sur les requêtes de plus de 3 mots-clés",
  "fix_suggestion": "Router vers Mojeek si DDG dépasse 3s, ajouter un cache de 5 min sur les requêtes identiques",
  "confidence": 0.85,
  "tags": ["web", "timeout", "provider-fallback"]
}
"""


# ══════════════════════════════════════════════════════════════════════════════
# FEW-SHOTS (ancrés sur ton contexte BEK)
# ══════════════════════════════════════════════════════════════════════════════
FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": (
            "PATTERN À ANALYSER :\n"
            "- action       : web_sync\n"
            "- status       : error\n"
            "- error_type   : TimeoutError\n"
            "- count        : 12 occurrences sur 24h\n"
            "- avg_latency  : 5025 ms\n"
            "- sample_msgs  : ['Timeout DDG', 'DDG timeout après 5s', ...]\n"
            "- sample_params: [{'query': 'actualités IA 2026'}, ...]"
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "category": "RESEARCH_FAIL",
            "severity": "HIGH",
            "root_cause": "Le provider DuckDuckGo timeout systématiquement à 5s sur les requêtes web_sync, probablement à cause de son anti-bot.",
            "fix_suggestion": "Router vers un provider de secours (Mojeek ou Qwant) si DDG dépasse 3s, et mettre en cache les requêtes identiques pendant 10 minutes.",
            "confidence": 0.9,
            "tags": ["web", "timeout", "provider-fallback"],
        }, ensure_ascii=False),
    },
    {
        "role": "user",
        "content": (
            "PATTERN À ANALYSER :\n"
            "- action       : create_dynamic_skill\n"
            "- status       : error\n"
            "- error_type   : SandboxRejection\n"
            "- count        : 6 occurrences sur 24h\n"
            "- avg_latency  : 8 ms\n"
            "- sample_msgs  : [\"Import interdit : 'subprocess'\", ...]\n"
            "- sample_params: [{'skill_name': 'evil_0'}, ...]"
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "category": "CODE_SYNTAX",
            "severity": "LOW",
            "root_cause": "Le générateur de skills produit du code avec des imports interdits (subprocess), rejetés par le sandbox AST.",
            "fix_suggestion": "Renforcer le prompt du générateur pour interdire explicitement les modules blacklistés (subprocess, ctypes, socket, requests) AVANT la génération.",
            "confidence": 0.95,
            "tags": ["skill-generator", "sandbox", "prompt-hardening"],
        }, ensure_ascii=False),
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER DE MESSAGE
# ══════════════════════════════════════════════════════════════════════════════
def build_critic_messages(pattern: dict) -> list[dict]:
    """
    Construit la liste de messages pour provider_manager.execute_chat_stream().

    Args:
        pattern: un dict issu de ReflexLoop.run_cycle()["top_patterns"][i]
                 avec les clés 'signature', 'count', 'avg_latency_ms',
                 'sample_messages', 'sample_parameters'.

    Returns:
        [{"role": "system", "content": ...}, *few_shots, {"role": "user", "content": ...}]
    """
    sig = pattern.get("signature", {}) or {}
    action = sig.get("action", "unknown")
    status = sig.get("status", "unknown")
    error_type = sig.get("error_type") or "(none)"

    sample_msgs = pattern.get("sample_messages", [])[:3]
    sample_params = pattern.get("sample_parameters", [])[:3]

    user_content = (
        "PATTERN À ANALYSER :\n"
        f"- action       : {action}\n"
        f"- status       : {status}\n"
        f"- error_type   : {error_type}\n"
        f"- count        : {pattern.get('count', 0)} occurrences sur la fenêtre analysée\n"
        f"- avg_latency  : {pattern.get('avg_latency_ms', 0)} ms\n"
        f"- min_latency  : {pattern.get('min_latency_ms', 0)} ms\n"
        f"- max_latency  : {pattern.get('max_latency_ms', 0)} ms\n"
        f"- sample_msgs  : {sample_msgs}\n"
        f"- sample_params: {sample_params}\n"
    )

    messages = [{"role": "system", "content": CRITIC_SYSTEM_PROMPT}]
    messages.extend(FEW_SHOT_EXAMPLES)
    messages.append({"role": "user", "content": user_content})
    return messages