# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Streaming : Constantes partagées (v1.6.19)
# ------------------------------------------------------------------------------
# ★ v1.6.19 : extraction du monolithe streaming.py → package modulaire
#   - Regex actions
#   - Marqueurs multi-intent
#   - Patterns refus LLM
#   - Config env + helpers
#   - ★ AUCUNE fonctionnalité modifiée (copie 1:1 de l'ancien streaming.py)
# ==============================================================================
from __future__ import annotations

import os
import re as _re

# ══════════════════════════════════════════════════════════════════════════════
# REGEX ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

_ACTION_FULL_RE = _re.compile(
    r"\[\s*ACTION\s*:\s*(\w+)\s*\]"
    r"(.*?)"
    r"\[\s*/\s*A\s*CTION\s*\]",
    _re.DOTALL | _re.IGNORECASE,
)

_CLOSING_ACTION_RE = _re.compile(r"\[\s*/\s*A\s*CTION\s*\]", _re.IGNORECASE)
_CLOSING_ACTION_LOOSE_RE = _re.compile(
    r"\[\s*/\s*A\s*C\s*T\s*I\s*O\s*N\s*\]", _re.IGNORECASE
)

# ══════════════════════════════════════════════════════════════════════════════
# ★ v1.6.13 — DÉTECTION MULTI-INTENT
# ══════════════════════════════════════════════════════════════════════════════

_MULTI_INTENT_MARKERS = [
    " puis ", " ensuite ", " enchaîne ", " enchaine ",
    " d'abord ", " d abord ", " premièrement ", " premierement ",
    " deuxièmement ", " deuxiemement ", " troisièmement ", " troisiemement ",
    " après ", " apres ", " enfin ", " finalement ",
    " et ", " et aussi ", " et puis ",
    " étape ", " etape ",
    ", puis,", ", ensuite,",
]

_OTHER_ACTION_KEYWORDS = [
    "cherche", "recherche", "trouve", "actualise", "actu",
    "news", "actualité", "actualite", "nouvelle",
    "scrape", "scrapper",
    "résume", "resume", "synthétise", "synthetise",
    "analyse", "résumé", "resume",
    "envoie", "envoi", "écris", "ecris", "rédige", "redige",
    "email", "mail", "message",
    "exécute", "execute", "lance", "installe",
    "souviens", "mémorise", "memorise", "rappelle",
]

# ══════════════════════════════════════════════════════════════════════════════
# ★ v1.6.15 — DÉTECTION INTENTION IMAGE + REFUS LLM
# ══════════════════════════════════════════════════════════════════════════════

_EXPLICIT_IMAGE_PHRASES = [
    "génère une image", "genere une image", "créer une image", "creer une image",
    "fais-moi une image", "fais moi une image",
    "fais-moi un logo", "fais moi un logo",
    "crée une image", "cree une image", "crée un logo", "cree un logo",
    "génère le logo", "genere le logo", "génère un logo", "genere un logo",
    "génère l'image", "genere l'image",
    "dessine-moi", "dessine moi", "dessine un", "dessine une",
    "fais un logo", "fais une image", "fais une illustration",
    "crée une illustration", "génère une illustration",
]

_NON_GENERATION_CONVERSATIONAL_MARKERS = (
    "pourquoi", "comment", "explique", "analyser", "analyse",
    "erreur", "bug", "plante", "échoue", "échoué", "probleme", "problème",
    "code", "fichier", "script", "architecture", "base de données", "database",
    "table", "logs", "log", "terminal", "console", "corrige", "répare",
    "modifie le fichier", "lis le", "ouvre le", "décris cette", "decris cette",
)

_LLM_REFUSAL_PATTERNS = [
    r"<svg[\s>]",
    r"```\s*(svg|xml|html)",
    r"je\s+ne\s+peux\s+pas\s+générer",
    r"je\s+ne\s+peux\s+pas\s+creer",
    r"en\s+tant\s+qu.intelligence\s+textuelle",
    r"je\s+suis\s+une\s+ia\s+textuelle",
    r"je\s+ne\s+suis\s+pas\s+capable\s+de\s+générer",
    r"prompt\s+de\s+génération",
    r"prompt\s+pour\s+générateur",
    r"délégation\s*:",
    r"délégation\s+à\s+",
    r"direction\s+artistique",
    r"protocole\s+de\s+conception",
    r"souhaites[- ]tu\s+affiner",
    r"souhaitez[- ]vous\s+affiner",
    r"souhaites[- ]tu\s+préciser",
    r"voici\s+un\s+code\s+svg",
    r"copiez\s+ce\s+code",
    r"collez\s+ce\s+code",
    r"copier\s+ce\s+code",
    r"voici\s+le\s+brief",
    r"voici\s+les\s+spécifications",
    r"```text",
    r"```\s*prompt",
    r"midjourney",
    r"dall-?e\s*3",
    r"stable\s+diffusion\s+prompt",
]

_LLM_REFUSAL_RE = _re.compile("|".join(_LLM_REFUSAL_PATTERNS), _re.IGNORECASE)

_VISUAL_TRIGGER_RE = _re.compile(
    r"\b(génère|genere|crée|cree|créer|creer|fais[- ]moi|fais\s+moi|fais|dessine|"
    r"conçois|concois|illustre)\s+"
    r"(moi\s+)?"
    r"(un|une|le|la|les|des|l[''])?\s*"
    r"(nouveau\s+|nouvelle\s+|beau\s+|belle\s+|joli\s+|jolie\s+)?"
    r"(logo|image|illustration|visuel|icône|icone|portrait|dessin|affiche)\b",
    _re.IGNORECASE,
)

# ══════════════════════════════════════════════════════════════════════════════
# VÉRIFICATION WEB
# ══════════════════════════════════════════════════════════════════════════════

_VERIFICATION_QUERY_RE = _re.compile(
    r"\b(aujourd'hui|aujourd hui|actuellement|dernier(?:e|s)?|récent(?:e|s)?|"
    r"actualité|news|latest|today|currently|recent|official(?:ly)?|officiel(?:le|s)?|"
    r"annonce(?:r|e|es)?|confirm(?:e|ed|ation)?|launch(?:ed)?|lancement|sortie|"
    r"prix actuel|date de sortie|disponible|leak|rumeur|source officielle|"
    r"selon le site|vérifie|verifie|recherche sur le web|cherche sur internet|"
    r"sur internet|sur le web|sources?|citation|preuve|fact-check|factuel)\b",
    _re.IGNORECASE,
)

# ══════════════════════════════════════════════════════════════════════════════
# ★ v1.6.13 — EXTRACTION SUJET IMAGE
# ══════════════════════════════════════════════════════════════════════════════

_NARRATIVE_PREFIX_RE = _re.compile(
    r"^\s*(enchaîne|enchaine|ensuite|puis|d'abord|d abord|"
    r"premièrement|premierement|deuxièmement|deuxiemement|"
    r"cherche\s+les\s+news|cherche\s+les\s+actualités|cherche\s+les\s+actualites|"
    r"résume[- ]les|resume[- ]les|résume[- ]le|resume[- ]le|"
    r"analyse[- ]les|analyse[- ]le)\s*[:,]?\s*",
    _re.IGNORECASE,
)

# ══════════════════════════════════════════════════════════════════════════════
# NORMALISATION
# ══════════════════════════════════════════════════════════════════════════════

_NORMALIZE_PATTERNS = [
    (r'\baistartup\b', 'AI startup'), (r'\baimodel\b', 'AI model'),
    (r'\baicompany\b', 'AI company'), (r'\baiassistant\b', 'AI assistant'),
    (r'\bdécriscette\b', 'décris cette'), (r'\bdecriscette\b', 'decris cette'),
    (r'\bdécriscetteimage\b', 'décris cette image'),
    (r'\bdecriscetteimage\b', 'decris cette image'),
    (r'\bsleeklogo\b', 'sleek logo'), (r'\bmodernlogo\b', 'modern logo'),
    (r'\bminimalistlogo\b', 'minimalist logo'), (r'\bsimplelogo\b', 'simple logo'),
    (r'\blogofora\b', 'logo for a'), (r'\btechstartup\b', 'tech startup'),
    (r'\belectricblue\b', 'electric blue'), (r'\bneongreen\b', 'neon green'),
    (r'\bcleanlines\b', 'clean lines'),
]

# ══════════════════════════════════════════════════════════════════════════════
# MESSAGES
# ══════════════════════════════════════════════════════════════════════════════

_MSG_TIMEOUT_DUR = "\n\n⏱️ **Délai dépassé** — réponse interrompue."
_MSG_REASONING_OVERFLOW = "\n\n🧠 **Réflexion excessive** — arrêt automatique."
_MSG_LOOP_DETECTED = "\n\n🔁 **Boucle détectée** — arrêt automatique."

# ══════════════════════════════════════════════════════════════════════════════
# LLM NATIVE TOKENS
# ══════════════════════════════════════════════════════════════════════════════

_LLM_NATIVE_TOKENS = (
    "<|tool_call_begin|>", "<|tool_call_end|>",
    "<|tool_call_argument_begin|>", "<|tool_call_argument_end|>",
    "<|tool_call|>", "<|tool_sep|>",
    "<|tool_calls_section_begin|>", "<|tool_calls_section_end|>",
)
_LLM_NATIVE_REGEX = _re.compile("|".join(_re.escape(t) for t in _LLM_NATIVE_TOKENS))
_LLM_XML_TOOL_REGEX = _re.compile(r"<tool_call>.*?</tool_call>", _re.DOTALL)

_THINKING_PATTERNS = (
    _re.compile(r"<think>.*?</think>", _re.DOTALL | _re.IGNORECASE),
    _re.compile(r"<thinking>.*?</thinking>", _re.DOTALL | _re.IGNORECASE),
    _re.compile(r"<reasoning>.*?</reasoning>", _re.DOTALL | _re.IGNORECASE),
)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG ENV
# ══════════════════════════════════════════════════════════════════════════════

def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = True) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


MAX_STREAM_DURATION_SEC = _env_int("BEK_STREAM_TIMEOUT_SEC", 300, minimum=60)
LOOP_DETECT_ENABLED = _env_bool("BEK_LOOP_DETECT_ENABLED", True)
LOOP_WINDOW = _env_int("BEK_LOOP_WINDOW", 15, minimum=5)
LOOP_THRESHOLD = _env_int("BEK_LOOP_THRESHOLD", 4, minimum=2)
MAX_REASONING_CHARS = _env_int("BEK_MAX_REASONING_CHARS", 6000, minimum=500)

BEK_ECO_CACHE_ENABLED = _env_bool("BEK_ECO_CACHE_ENABLED", True)
BEK_MEM_ENABLED = _env_bool("BEK_MEM_ENABLED", True)
BEK_LOOP_ENABLED = _env_bool("BEK_LOOP_ENABLED", True)
BEK_MULTI_ACTIONS_ENABLED = _env_bool("BEK_MULTI_ACTIONS_ENABLED", True)
BEK_MAX_ACTIONS_PER_RESPONSE = _env_int("BEK_MAX_ACTIONS_PER_RESPONSE", 5)
BEK_ANTIHALLU_ENABLED = _env_bool("BEK_ANTIHALLU_ENABLED", True)
BEK_POST_ACTION_GRACE_MAX = _env_int("BEK_POST_ACTION_GRACE_MAX", 50, minimum=10)
BEK_MAX_TOKENS = _env_int("BEK_MAX_TOKENS", 2048, minimum=256)

BEK_FORCE_IMAGE_ON_INTENT = _env_bool("BEK_FORCE_IMAGE_ON_INTENT", True)
BEK_SKIP_BYPASS_ON_MULTI_INTENT = _env_bool("BEK_SKIP_BYPASS_ON_MULTI_INTENT", True)
BEK_FOLLOWUP_AFTER_TOOL = _env_bool("BEK_FOLLOWUP_AFTER_TOOL", True)