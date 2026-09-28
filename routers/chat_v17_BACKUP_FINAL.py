# ==============================================================================
# BEK-v16 — Routeur Chat Streaming & Human-in-the-Loop (routers/chat.py)
# ------------------------------------------------------------------------------
# + OpenTelemetry : spans sur chat.request, smart_router, cognitive_check
# + Sanitizer tokens natifs LLM (Nemotron) + règles outil web
# + Fix: plus de CANCELED_ACTION intempestif + logs headless_scrape
# + headless_scrape : extraction texte via BeautifulSoup
#
# CORRECTIF v11 (2026-09-20) :
# - Règle anti-refus + anti-hallucination temporelle + confiance outils
#
# CORRECTIF v12 (2026-09-21) :
# - Vidéo : provider="agnes", model="agnes-v2.0", with_audio=True par défaut
#
# CORRECTIF v13 (2026-09-21) :
# - BUGFIX : ne plus écraser params["provider"]/["model"] pour multimédia
#
# CORRECTIF v14 (2026-09-21) :
# - Ajout extend_video + extend_video_multiple (Agnes continuité)
#
# CORRECTIF v15 (2026-09-22) :
# - ★ AJOUT : generate_subtitles + burn_subtitles (Whisper local)
# - Règles strictes sous-titres dans le prompt système
# - Ajout dans MULTIMEDIA_ACTIONS
# - Branche _execute_action_unified pour Whisper
#
# CORRECTIF v16 (2026-09-22) — ★ PATCH 3A/3B/3C :
# - ★ PATCH 3A : headless_search avec ≥1 lead n'est plus "poor" (stop fallback)
# - ★ PATCH 3B : auto-scrape 2 URLs après headless_search réussi
# - ★ PATCH 3C : BEK_GOLDEN_RULES renforcé (anti-traduction + anti-halluc)
#
# CORRECTIF v17 (2026-09-23) — ★ PATCH 3D :
# - ★ PATCH 3D : synthèse forcée après auto-scrape (plus seulement sur poor)
# ==============================================================================
from __future__ import annotations

import ast
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse


from bek_eval_guard import evaluate_response_quality
from fast_math import HyperLogLog, MinHashSimilarity
from hermes_core import hermes
from memory import search_memory
from provider_manager import provider_manager
from services.action_executor import execute_agent_crm_tool
from services.tasks import CURRENT_OS_NAME

# ── OpenTelemetry ──
try:
    from core.tracing import (
        span,
        set_span_attribute,
        set_span_status_ok,
        set_span_status_error,
        get_current_trace_id,
    )
    _TRACING_OK = True
except Exception:
    _TRACING_OK = False
    from contextlib import contextmanager

    @contextmanager
    def span(name, **attrs):  # type: ignore
        yield None

    def set_span_attribute(k, v): pass  # type: ignore
    def set_span_status_ok(): pass  # type: ignore
    def set_span_status_error(msg=""): pass  # type: ignore
    def get_current_trace_id(): return ""  # type: ignore


# ══════════════════════════════════════════════════════════════════
# 📋 LOGGER
# ══════════════════════════════════════════════════════════════════
logger = logging.getLogger("BEKApp")
# ══════════════════════════════════════════════════════════════════════════════
# ★ BEK-LVC — Imports du CPU Logique Virtuel
# ------------------------------------------------------------------------------
# Intégration progressive de BEK-LVC (Étape 3/3)
# Doc : docs/BEK_LVC.md
# ══════════════════════════════════════════════════════════════════════════════
try:
    from bek_core import BekCPU
    from bek_core.stair import BekStairToC
    _BEK_LVC_OK = True
    logger.info("✅ BEK-LVC chargé | briques=%s", BekCPU.list())
except Exception as _bek_lvc_err:
    _BEK_LVC_OK = False
    BekCPU = None
    BekStairToC = None
    logger.warning("⚠️ BEK-LVC non chargé : %s", _bek_lvc_err)

ACTION_REGEX = re.compile(r"\x5bACTION:(\w+)\x5d(.*?)\x5b/ACTION\x5d", re.DOTALL)

_LLM_NATIVE_TOKENS = (
    "<|tool_call_begin|>", "<|tool_call_end|>",
    "<|tool_call_argument_begin|>", "<|tool_call_argument_end|>",
    "<|tool_call|>", "<|tool_sep|>",
    "<|tool_calls_section_begin|>", "<|tool_calls_section_end|>",
)
_LLM_NATIVE_REGEX = re.compile("|".join(re.escape(t) for t in _LLM_NATIVE_TOKENS))
_LLM_XML_TOOL_REGEX = re.compile(r"<tool_call>.*?</tool_call>", re.DOTALL)


def _sanitize_llm_output(text: str) -> str:
    if not text:
        return text
    text = _LLM_NATIVE_REGEX.sub("", text)
    text = _LLM_XML_TOOL_REGEX.sub("", text)
    return text


# ══════════════════════════════════════════════════════════════════
# 🛡️ CONFIGURATION
# ══════════════════════════════════════════════════════════════════
def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


HISTORY_WINDOW = _env_int("BEK_CHAT_HISTORY_WINDOW", 6)
MAX_CHARS_PER_MESSAGE = _env_int("BEK_CHAT_MAX_CHARS_PER_MSG", 8000)
MAX_TOTAL_CHARS = _env_int("BEK_CHAT_MAX_TOTAL_CHARS", 32000)
MAX_ARCHITECTURE_CHARS = _env_int("BEK_CHAT_MAX_ARCHITECTURE_CHARS", 15000)

MAX_TOTAL_ACTIONS = _env_int("BEK_CHAT_MAX_TOTAL_ACTIONS", 2)
POOR_RESULT_THRESHOLD = _env_int("BEK_CHAT_POOR_RESULT_THRESHOLD", 200)
MAX_CHUNKS_WITHOUT_CLOSE = _env_int("BEK_CHAT_MAX_CHUNKS_NO_CLOSE", 150)
MAX_QUERY_WORDS = _env_int("BEK_CHAT_MAX_QUERY_WORDS", 8)

# ★ PATCH 3B : nombre d'URLs à auto-scraper après headless_search
AUTO_SCRAPE_MAX_URLS = _env_int("BEK_CHAT_AUTO_SCRAPE_MAX_URLS", 2)
AUTO_SCRAPE_MAX_CHARS_PER_PAGE = _env_int("BEK_CHAT_AUTO_SCRAPE_MAX_CHARS", 4000)

# ══════════════════════════════════════════════════════════════════════════════
# ★ PATCH 3.2 — BEK-REX Routing (Reflective EXecution)
# ------------------------------------------------------------------------------
# Utilise le CPU Logique Virtuel pour router les requêtes.
# Fallback vers la logique locale si BEK-LVC indisponible.
# ==============================================================================
def _bek_rex_route(query: str) -> dict:
    """
    Route une requête via BEK-REX (BEK-LVC).

    Args:
        query: La requête utilisateur

    Returns:
        dict: {
            "tier": "TIER_0..TIER_4",
            "confidence": float,
            "reasoning": str,
            "source": "bek_rex" | "fallback"
        }
    """
    if not _BEK_LVC_OK or BekCPU is None:
        return {
            "tier": "TIER_3",
            "confidence": 0.5,
            "reasoning": "Fallback : BEK-LVC non chargé",
            "source": "fallback",
        }

    try:
        result = BekCPU.execute("BEK-REX", "bek_rex_route", query=query)
        result["source"] = "bek_rex"
        return result
    except Exception as exc:
        logger.warning("[BEK-REX] Échec routing : %s", exc)
        return {
            "tier": "TIER_3",
            "confidence": 0.5,
            "reasoning": f"Fallback : {exc}",
            "source": "fallback",
        }


def _bek_rex_should_use_web_sync(query: str, routing: dict) -> bool:
    """
    Décide si on doit utiliser web_sync (WebAgent profond) au lieu de headless_search.

    Règles :
        - TIER_3 ou TIER_4 → TOUJOURS web_sync
        - TIER_2 → web_sync si requête "news/actualités/analyse"
        - TIER_1 → headless_search (rapide)
        - TIER_0 → pas de recherche

    Args:
        query: La requête
        routing: Le résultat de _bek_rex_route()

    Returns:
        bool: True si on doit utiliser web_sync
    """
    tier = routing.get("tier", "TIER_3")
    query_lower = query.lower()

    # TIER_3 et TIER_4 → toujours web_sync
    if tier in ("TIER_3", "TIER_4"):
        return True

    # TIER_2 → web_sync si mots-clés "profonds"
    if tier == "TIER_2":
        deep_keywords = [
            "news", "actualité", "actualités", "dernières",
            "analyse", "rapport", "veille", "étude", "synthèse",
        ]
        if any(kw in query_lower for kw in deep_keywords):
            return True
        # Par défaut pour TIER_2, on utilise web_sync (plus puissant)
        return True

    # TIER_1 → headless_search (rapide)
    if tier == "TIER_1":
        return False

    # TIER_0 → pas de recherche
    return False

MULTIMEDIA_ACTIONS = (
    "generate_video",
    "edit_video",
    "extend_video",
    "extend_video_multiple",
    "generate_image",
    "edit_image",
    "generate_subtitles",
    "burn_subtitles",
)

_STERILE_URL_PATTERNS = (
    r"google\.com/finance\?sa=X",
    r"google\.com/search\?",
    r"bing\.com/search\?",
    r"duckduckgo\.com/\?q=",
    r"duckduckgo\.com/html/\?q=",
    r"accounts\.google\.com",
    r"login\.microsoftonline\.com",
    r"signin\.",
    r"/signin",
    r"/login",
    r"/auth/",
    r"auth0\.com",
    r"okta\.com",
    r"^https?://(fr\.)?news\.yahoo\.com/?$",
    r"^https?://(www\.)?yahoo\.com/?$",
    r"^https?://(www\.)?yahoo\.fr/?$",
    r"^https?://news\.google\.com/?",
    r"^https?://(www\.)?msn\.com/?$",
    r"^https?://(www\.)?bing\.com/?$",
    r"^https?://(www\.)?google\.[a-z]{2,3}/?$",
)
_STERILE_URL_REGEX = re.compile("|".join(_STERILE_URL_PATTERNS), re.IGNORECASE)


def _is_sterile_url(url: str) -> bool:
    if not url:
        return False
    try:
        from urllib.parse import urlparse as _up
        p = _up(url)
        path = (p.path or "").strip("/")
        if not path or path in ("index.html", "index.htm", "index.php", "home"):
            return True
    except Exception:
        pass
    return bool(_STERILE_URL_REGEX.search(url))


_QUERY_STOPWORDS = {
    "cherche", "chercher", "recherche", "rechercher", "trouve", "trouver",
    "donne", "donner", "montre", "montrer", "résume", "résumer",
    "les", "le", "la", "un", "une", "des", "du", "de", "d",
    "et", "ou", "en", "au", "aux", "ce", "cette", "ces", "cet",
    "sur", "sous", "dans", "par", "pour", "avec", "sans",
    "dernières", "dernière", "dernier", "derniers",
    "chacune", "chacun", "chaque", "phrases", "phrase",
    "actualité", "actualités",
    "à", "a", "y", "ne", "pas", "plus", "que", "qui", "quoi",
    "est", "sont", "été", "être",
    "the", "of", "to", "in", "on", "at", "by", "for",
    "is", "are", "was", "were", "be", "been",
    "it", "its", "as", "or", "and", "but", "if", "so", "no",
    "do", "does", "did", "has", "have", "had", "this", "that",
    "with", "from", "will", "would", "can", "could", "should",
    "search", "find", "get", "give", "show", "summarize",
    "latest", "recent", "top", "best",
    "5", "10", "3", "2", "1",
}


def _extract_keywords(query: str, max_words: int = MAX_QUERY_WORDS) -> str:
    if not query or not query.strip():
        return query

    words = query.strip().split()
    if len(words) <= max_words:
        return query

    keywords = []
    for w in words:
        w_clean = re.sub(r"[^\w]", "", w.lower())
        if w_clean and w_clean not in _QUERY_STOPWORDS:
            keywords.append(w)

    if not keywords:
        return " ".join(words[:max_words])

    result = " ".join(keywords[:max_words])
    logger.info("[KeywordExtract] '%s' → '%s'", query[:80], result[:80])
    return result


_EN_MARKERS = {
    "latest", "news", "price", "current", "how", "what", "the",
    "today", "info", "update", "trending", "recent",
}
_FR_MARKERS = {
    "actualité", "actualités", "prix", "actuel", "actuelle", "aujourd",
    "comment", "quoi", "quel", "quelle", "dernières", "dernière",
    "nouvelles", "nouveaux", "récent", "récente",
}


def _is_translation(original_query: str, sent_query: str) -> bool:
    if not original_query or not sent_query:
        return False
    o_lower = original_query.lower()
    s_lower = sent_query.lower()
    o_fr = sum(1 for m in _FR_MARKERS if m in o_lower)
    s_en = sum(1 for m in _EN_MARKERS if m in s_lower)
    s_fr = sum(1 for m in _FR_MARKERS if m in s_lower)
    return o_fr >= 1 and s_en >= 2 and s_fr == 0


_WORKSPACE_DIR = Path(__file__).resolve().parent.parent

_ARCHITECTURE_CANDIDATES = [
    _WORKSPACE_DIR / "docs" / "ARCHITECTURE.md",
    _WORKSPACE_DIR / "ARCHITECTURE.md",
]


def _load_architecture_context() -> str:
    for candidate in _ARCHITECTURE_CANDIDATES:
        try:
            if candidate.exists() and candidate.is_file():
                with candidate.open("r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if not content.strip():
                    continue
                if len(content) > MAX_ARCHITECTURE_CHARS:
                    content = content[:MAX_ARCHITECTURE_CHARS] + (
                        "\n\n[…architecture tronquée pour respecter la limite]"
                    )
                logger.info("[Archi] Contexte chargé : %s (%d chars)", candidate, len(content))
                return content
        except Exception as exc:
            logger.warning("[Archi] Lecture échouée %s : %s", candidate, exc)

    logger.warning("[Archi] Aucun fichier ARCHITECTURE.md trouvé.")
    return ""


_ARCHITECTURE_CONTEXT: str = _load_architecture_context()


def get_architecture_context() -> str:
    return _ARCHITECTURE_CONTEXT


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    try:
        return str(value)
    except Exception:
        return ""


def _truncate_messages(
    messages: List[Dict[str, Any]],
    window: int = HISTORY_WINDOW,
    max_per_msg: int = MAX_CHARS_PER_MESSAGE,
    max_total: int = MAX_TOTAL_CHARS,
) -> List[Dict[str, Any]]:
    if not messages or not isinstance(messages, list):
        return []

    recent = [m for m in messages[-window:] if isinstance(m, dict)]

    normalized: List[Dict[str, Any]] = []
    for m in recent:
        role = _safe_str(m.get("role", "user"))[:32] or "user"
        content = _safe_str(m.get("content", ""))
        if len(content) > max_per_msg:
            content = content[:max_per_msg] + "\n…[tronqué]"
        normalized.append({"role": role, "content": content})

    total = sum(len(m["content"]) for m in normalized)
    if total > max_total:
        overflow = total - max_total
        for m in normalized:
            if overflow <= 0:
                break
            content_len = len(m["content"])
            if content_len <= overflow:
                overflow -= content_len
                m["content"] = "[…contenu ancien tronqué…]"
            else:
                m["content"] = "[…tronqué…] " + m["content"][overflow:]
                overflow = 0

    return normalized


try:
    from bek_intelligence import (
        smart_router, auto_engine, ResponseQuality, Task
    )
    _INTEL_OK = True
except Exception as _intel_err:
    logger.warning("BekIntelligence non chargé : %s", _intel_err)
    _INTEL_OK = False
    smart_router = auto_engine = ResponseQuality = None

    class Task:
        CHAT = "chat"
        CODE = "code"
        REASONING = "reasoning"
        VISION = "vision"
        LONG_DOC = "long_doc"
        CREATIVE = "creative"

try:
    from nerves.router_nerves import route_semantic as _agi_route_semantic
    _AGI_ROUTER_OK = True
except Exception as _router_err:
    logger.debug("Nerf 7 non chargé : %s", _router_err)
    _agi_route_semantic = None
    _AGI_ROUTER_OK = False

try:
    from nerves.event_bus_nerves import publish_event_unified as _agi_publish_event
    _AGI_EVENT_BUS_OK = True
except Exception as _eb_err:
    logger.debug("Nerf 3 non chargé : %s", _eb_err)
    _agi_publish_event = None
    _AGI_EVENT_BUS_OK = False

try:
    from nerves.cognitive_nerves import run_cognitive_pipeline as _agi_cognitive_pipeline
    _AGI_COGNITIVE_OK = True
except Exception as _cog_err:
    logger.debug("Nerf 2 non chargé : %s", _cog_err)
    _agi_cognitive_pipeline = None
    _AGI_COGNITIVE_OK = False

try:
    from skills import dispatch_command as dispatch_slash_command
except ImportError:
    dispatch_slash_command = None

try:
    from event_bus import EventBusKafka
    event_bus = EventBusKafka()
except Exception:
    event_bus = None

router = APIRouter(tags=["Chat"])

minhash_engine = MinHashSimilarity(num_perm=64)
hll_counter = HyperLogLog(b=6)


# ══════════════════════════════════════════════════════════════════
# 🧠 PROMPT SYSTÈME v16 (règles renforcées + anti-traduction + anti-halluc)
# ══════════════════════════════════════════════════════════════════
_ARCHITECTURE_BLOCK = ""
if _ARCHITECTURE_CONTEXT:
    _ARCHITECTURE_BLOCK = f"""

# ══════════════════════════════════════════════════════════════════
# 🏛️ ARCHITECTURE RÉELLE DE BEK-v16 (SOURCE DE VÉRITÉ ABSOLUE)
# ══════════════════════════════════════════════════════════════════

{_ARCHITECTURE_CONTEXT}

# ══════════════════════════════════════════════════════════════════
# FIN DE L'ARCHITECTURE RÉELLE
# ══════════════════════════════════════════════════════════════════
"""


BEK_GOLDEN_RULES = f"""
# RÔLE & PERSONNALITÉ
Tu es BEK, agent technique d'exécution sur {CURRENT_OS_NAME}.
Tu raisonnes avec rigueur, tu réponds avec précision, tu ne brodes jamais.

# POUVOIRS SYSTÈME
- Accès TOTAL au système local : terminal, Git, Neon DB, Pinecone.
- INTERDICTION d'affirmer "Je n'ai pas accès à Internet".
- EXÉCUTE DIRECTEMENT via les outils dédiés les actions demandées.

# DIRECTIVES CONVERSATIONNELLES
- Parle naturellement et brièvement. Pas de bavardage.
- Salutations : une phrase courte.

# EXÉCUTION D'OUTILS (RÈGLE STRICTE)
- DÈS QUE l'utilisateur demande une action, N'ATTENDS PAS.
- INTERDICTION de demander la permission.
- Renvoie UNIQUEMENT la balise [ACTION:nom]{{"param":"v"}}[/ACTION].

# 🚫 FORMAT DES ACTIONS (RÈGLE ABSOLUE)
- N'UTILISE JAMAIS de tokens spéciaux (<|tool_call_begin|>, <tool_call>, etc.)
- Format EXCLUSIF : [ACTION:nom]{{"param":"valeur"}}[/ACTION]
- TU DOIS TOUJOURS FERMER la balise avec [/ACTION].

# ══════════════════════════════════════════════════════════════════
# 🚨 ★ PATCH 3C — RÈGLES ABSOLUES ANTI-TRADUCTION & ANTI-HALLUCINATION
# ══════════════════════════════════════════════════════════════════

## 🌐 RÈGLE ABSOLUE — LANGUE DE LA REQUÊTE
- Tu DOIS utiliser EXACTEMENT la langue de l'utilisateur pour la requête.
- Utilisateur écrit en FRANÇAIS → requête headless_search EN FRANÇAIS.
- INTERDICTION ABSOLUE de traduire la requête en anglais.
- Exemples CORRECTS :
  User : "Cherche les news sur le Bitcoin"
  ✅ Toi : [ACTION:headless_search]{{"query": "Bitcoin actualités"}}[/ACTION]

  User : "Cherche les dernières actus IA"
  ✅ Toi : [ACTION:headless_search]{{"query": "actualités IA 2026"}}[/ACTION]

- Exemples INTERDITS (tu ne dois JAMAIS faire ça) :
  ❌ User FR → Toi tu envoies "Bitcoin news" (traduction EN)
  ❌ User FR → Toi tu envoies "latest Bitcoin news" (traduction EN)

## 🚨 RÈGLE ABSOLUE — SOURCES RÉELLES UNIQUEMENT
- Tu ne dois JAMAIS citer une source (URL, nom de site, journal) que tu n'as
  pas obtenue via l'appel d'un outil DANS CETTE conversation.
- INTERDICTION STRICTE de dire "selon X" ou "d'après Y" sans que X ou Y
  provienne d'un résultat d'outil visible dans le contexte.
- INTERDICTION d'inventer des URLs qui ressemblent à "https://xxx-actu.fr/...".

## 🚨 RÈGLE ABSOLUE — APRÈS UN headless_search
- Tu DOIS analyser EXCLUSIVEMENT les URLs retournées par l'outil.
- Si les URLs retournées sont hors-sujet (page d'accueil, home portail),
  tu DOIS le dire HONNÊTEMENT et proposer de reformuler.
- INTERDICTION de présenter une home de portail (Yahoo home, Google home, etc.)
  comme si elle répondait à la question.

## 🚨 RÈGLE ABSOLUE — QUAND LES RÉSULTATS SONT INSUFFISANTS
- Si les résultats sont insuffisants → réponds EXACTEMENT :
  "Les sources retournées ne contiennent pas d'information pertinente
   sur ce sujet. Je peux reformuler ou essayer une autre source."
- INTERDICTION d'inventer pour combler le vide.

# ══════════════════════════════════════════════════════════════════
# 🎬 RÈGLES VIDÉO (CRITIQUE — À RESPECTER ABSOLUMENT)
# ══════════════════════════════════════════════════════════════════
- NOUVELLE vidéo (à partir de zéro)    → generate_video
- MODIFIER une vidéo (couper, monter)  → edit_video
- ÉTENDRE / CONTINUER une vidéo
  existante (même personnage, même
  décor, suite de la scène)            → extend_video ⚠️ OBLIGATOIRE

⚠️ RÈGLE ANTI-CONFUSION :
- Si l'utilisateur dit « étends », « continue », « ajoute X secondes »,
  « suite de la vidéo », « prolonge » → c'est TOUJOURS extend_video.
- N'utilise JAMAIS edit_video pour une extension.

- Pour toute NOUVELLE vidéo, tu DOIS appeler generate_video.
- TOUJOURS spécifier ces paramètres :
  * provider : "agnes"
  * model    : "agnes-v2.0"
  * duration : 5
  * aspect_ratio : "16:9"
  * with_audio : true
  * audio_style : "children"
- Le prompt DOIT être en ANGLAIS, descriptif.

- ⚠️ N'UTILISE PAS Veo (pas de quota disponible).
- ⚠️ N'UTILISE PAS gemini comme provider pour la vidéo.

# ══════════════════════════════════════════════════════════════════
# 🎤 RÈGLES SOUS-TITRES WHISPER (CRITIQUE)
# ══════════════════════════════════════════════════════════════════
- GÉNÉRER des sous-titres (.srt) pour une vidéo → generate_subtitles
- INCRUSTER les sous-titres dans la vidéo (hard subs) → burn_subtitles
- Ces outils utilisent Whisper (local, gratuit, illimité)

- Modèles disponibles : "tiny" (rapide), "base" (défaut), "small" (précis)
- Langue par défaut : "fr" (français) — utilise null pour auto-détection

# ══════════════════════════════════════════════════════════════════

# ACTIONS DISPONIBLES :
   - [ACTION:generate_image]{{"prompt": "detailed description in english", "provider": "pollinations", "model": "flux-3d"}}[/ACTION]
   - [ACTION:edit_image]{{"image_paths": ["filename.png"], "prompt": "exact modification directive in english"}}[/ACTION]
   - [ACTION:generate_video]{{"prompt": "...", "provider": "agnes", "model": "agnes-v2.0", "duration": 5, "aspect_ratio": "16:9", "with_audio": true, "audio_style": "children"}}[/ACTION]
   - [ACTION:edit_video]{{"video_paths": ["filename.mp4"], "prompt": "exact modification directive in english"}}[/ACTION]
   - [ACTION:extend_video]{{"video_path": "filename.mp4", "prompt": "continuation prompt in english", "duration": 9, "with_audio": true, "audio_style": "nature"}}[/ACTION]
   - [ACTION:extend_video_multiple]{{"video_path": "filename.mp4", "prompts": ["scene 1", "scene 2"], "duration": 9, "with_audio": true, "audio_style": "nature"}}[/ACTION]
   - [ACTION:generate_subtitles]{{"video_path": "filename.mp4", "language": "fr", "model": "base"}}[/ACTION]
   - [ACTION:burn_subtitles]{{"video_path": "filename.mp4", "language": "fr", "model": "base"}}[/ACTION]
   - [ACTION:create_dynamic_skill]{{"skill_name": "x", "code_content": "y"}}[/ACTION]
   - [ACTION:orchestrate]{{"goal": "..."}}[/ACTION]
   - [ACTION:web_sync]{{"query": "..."}}[/ACTION]
   - [ACTION:headless_scrape]{{"url": "https://..."}}[/ACTION]
   - [ACTION:headless_search]{{"query": "..."}}[/ACTION]
   - [ACTION:run_script]{{"script_name": "skills/x.py", "args": "--ip 127.0.0.1"}}[/ACTION]
   - [ACTION:execute_command]{{"command": "..."}}[/ACTION]
   - [ACTION:execute_tmux_headless]{{"session_name": "s", "command": "c"}}[/ACTION]
   - [ACTION:save_memory]{{"content": "..."}}[/ACTION]
   - [ACTION:search_memory]{{"query": "..."}}[/ACTION]
   - [ACTION:write_file]{{"filename": "...", "content": "..."}}[/ACTION]
   - [ACTION:read_file]{{"filename": "..."}}[/ACTION]

# 🌐 SÉLECTION D'OUTIL WEB
- URL explicite → headless_scrape
- Recherche web → headless_search
- Extraction contacts d'une page → headless_scrape
- Veille multi-sources approfondie → web_sync

# 🌐 FORMULATION DE REQUÊTE (CRITIQUE)
- NE TRADUIS JAMAIS la requête. Utilisateur FR → requête FR.
- Utilise EXACTEMENT les termes de l'utilisateur.

## 🎯 EXTRACTION DE MOTS-CLÉS
- Quand tu génères une requête pour headless_search, tu dois EXTRAIRE
  les MOTS-CLÉS essentiels au lieu d'envoyer la phrase complète.
- Maximum 8 mots. Pas de verbes, pas d'articles.
- Exemples CORRECTS :
  User : "Cherche les 5 dernières actualités sur l'IA en 2026."
  ✅ Toi : [ACTION:headless_search]{{"query": "actualités IA 2026"}}[/ACTION]

  User : "Quel est le prix actuel du Bitcoin en euros ?"
  ✅ Toi : [ACTION:headless_search]{{"query": "prix Bitcoin EUR"}}[/ACTION]

# 🎯 CADRAGE STRICT
- Réponds STRICTEMENT à la question.
- Respecte le FORMAT demandé (ex: "5 items × 2 phrases" → exactement 5×2).
- Va droit au but.

# ══════════════════════════════════════════════════════════════════
# 🚨 RÈGLES CRITIQUES v11 (À RESPECTER ABSOLUMENT)
# ══════════════════════════════════════════════════════════════════

## 📌 RÈGLE 1 — ANTI-REFUS (CRITIQUE)
Si tu as DÉJÀ la réponse à la question dans l'historique de la conversation,
tu DOIS donner cette réponse DIRECTEMENT, sans appeler d'outil.

## 📌 RÈGLE 2 — ANTI-HALLUCINATION TEMPORELLE (CRITIQUE)
- N'INVENTE JAMAIS la date actuelle.
- Ne dis JAMAIS "nous sommes en 2026" si tu n'en es pas certain.
- INTERDICTION STRICTE de dire "étude web effectuée le [DATE]" si tu n'as 
  PAS EXÉCUTÉ cette étude dans CETTE conversation.
- Si tu réutilises une source d'une conversation PRÉCÉDENTE, tu DOIS 
  préciser CLAIREMENT : "D'après une source précédemment citée..."
- INTERDICTION d'inventer la date d'exécution d'une étude.
- La date de l'étude = date de sa PUBLICATION SOURCE, pas la date 
  d'exécution d'un outil.

## 📌 RÈGLE 3 — CONFIANCE EXCLUSIVE AUX OUTILS (CRITIQUE)
- Ta source de vérité est UNIQUEMENT ce que les outils retournent.
- Si un outil retourne "70 556,46 €" pour le Bitcoin, tu DOIS répondre
  "70 556,46 €" MÊME SI tes données d'entraînement disent autre chose.

## 📌 RÈGLE 4 — RÉPONSES AUX QUESTIONS SIMPLES (CRITIQUE)
- Si l'utilisateur pose une question factuelle simple et qu'un outil a déjà
  retourné la réponse, tu DOIS la donner IMMÉDIATEMENT.

## 📌 RÈGLE 5 — INTERDICTION DES OUTILS INUTILES
- Tu appelles UN SEUL outil par réponse utilisateur.
- Une fois le résultat obtenu, tu DOIS conclure.

## 📌 RÈGLE 6 — VÉRIFICATION FACTUELLE
- Avant de dire "je ne peux pas", VÉRIFIE l'historique de la conversation.

# ══════════════════════════════════════════════════════════════════
# 🎨 RÈGLES IMAGE (CRITIQUE — À RESPECTER ABSOLUMENT)
# ══════════════════════════════════════════════════════════════════
- Pour TOUTE demande de génération d'image, tu DOIS appeler generate_image.
- TOUJOURS spécifier ces paramètres :
  * provider : "pollinations"    (gratuit, illimité, fiable)
  * model    : "flux-3d"         (style 3D Pixar parfait)
- Le prompt DOIT être en ANGLAIS, descriptif et détaillé.

# ══════════════════════════════════════════════════════════════════

# DIRECTIVE MULTIMÉDIA ABSOLUE
- Pour TOUTE demande visuelle : generate_image, edit_image,
  generate_video, edit_video, extend_video, extend_video_multiple,
  generate_subtitles, burn_subtitles.
{_ARCHITECTURE_BLOCK}
"""


# ══════════════════════════════════════════════════════════════════
# 🔍 HELPERS
# ══════════════════════════════════════════════════════════════════
def _detect_user_response(query: str) -> str:
    if not query:
        return "neutral"
    q = query.lower().strip()
    agreed = {
        "oui", "yes", "ok", "okay", "vasy", "vas-y",
        "go", "d'accord", "ouais", "y", "o", "fine",
    }
    refused = {"non", "no", "stop", "annule", "cancel", "jamais"}
    words = set(re.findall(r"\b\w+\b", q))
    if words & agreed and not (words & refused):
        return "agreed"
    if words & refused:
        return "refused"
    return "neutral"


def _execute_action_unified(act_name: str, params: dict) -> dict:
    try:
        if act_name == "generate_image":
            from services.vision import generate_image_with_provider
            prompt = params.get("prompt") or params.get("query") or ""
            provider_v = params.get("provider", "pollinations")
            model_v = params.get("model", "flux-3d")
            return generate_image_with_provider(prompt=prompt, provider=provider_v, model=model_v)

        elif act_name == "edit_image":
            from services.vision import merge_and_edit_images
            paths = params.get("image_paths") or params.get("image_path") or []
            prompt = params.get("prompt") or params.get("user_prompt") or params.get("query") or ""
            return merge_and_edit_images(image_paths=paths, user_prompt=prompt)

        elif act_name == "generate_video":
            from services.vision import generate_video_with_provider
            prompt = params.get("prompt") or params.get("query") or ""
            provider_v    = params.get("provider", "agnes")
            model_v       = params.get("model", "agnes-v2.0")
            duration_v    = params.get("duration", 5)
            aspect_ratio_v = params.get("aspect_ratio", "16:9")
            with_audio_v  = params.get("with_audio", True)
            audio_style_v = params.get("audio_style", "children")
            logger.info(
                "[generate_video] prompt=%r provider=%s model=%s duration=%s",
                prompt[:80], provider_v, model_v, duration_v,
            )
            return generate_video_with_provider(
                prompt=prompt, provider=provider_v, model=model_v,
                duration=int(duration_v), aspect_ratio=aspect_ratio_v,
                with_audio=bool(with_audio_v), audio_style=audio_style_v,
            )

        elif act_name == "edit_video":
            from services.vision import merge_and_edit_videos
            paths = params.get("video_paths") or params.get("video_path") or []
            prompt = params.get("prompt") or params.get("user_prompt") or params.get("query") or ""
            provider_v = params.get("provider", "agnes")
            model_v = params.get("model", "agnes-v2.0")
            duration_v = params.get("duration", 5)
            return merge_and_edit_videos(
                video_paths=paths, prompt=prompt,
                provider=provider_v, model=model_v, duration=int(duration_v),
            )

        elif act_name == "extend_video":
            from services.vision import extend_video_with_agnes
            video_path = params.get("video_path") or params.get("video_paths") or "LAST"
            if isinstance(video_path, list):
                video_path = video_path[0] if video_path else "LAST"
            prompt = params.get("prompt") or params.get("user_prompt") or params.get("query") or ""
            model_v = params.get("model", "agnes-v2.0")
            duration_v = params.get("duration", 9)
            with_audio_v = params.get("with_audio", True)
            audio_style_v = params.get("audio_style", "nature")
            return extend_video_with_agnes(
                video_path=video_path, new_prompt=prompt, model=model_v,
                duration=int(duration_v), with_audio=bool(with_audio_v),
                audio_style=audio_style_v,
            )

        elif act_name == "extend_video_multiple":
            from services.vision import extend_video_multiple
            video_path = params.get("video_path") or "LAST"
            prompts_list = params.get("prompts", [])
            model_v = params.get("model", "agnes-v2.0")
            duration_v = params.get("duration", 9)
            with_audio_v = params.get("with_audio", True)
            audio_style_v = params.get("audio_style", "nature")
            return extend_video_multiple(
                video_path=video_path, prompts=prompts_list, model=model_v,
                duration_per_clip=int(duration_v), with_audio=bool(with_audio_v),
                audio_style=audio_style_v,
            )

        elif act_name == "generate_subtitles":
            from services.vision.whisper_client import generate_subtitles_from_video
            video_path = params.get("video_path") or "LAST"
            language = params.get("language")
            model_name = params.get("model", "base")
            return generate_subtitles_from_video(
                video_path=video_path, language=language, model_name=model_name,
            )

        elif act_name == "burn_subtitles":
            from services.vision.whisper_client import (
                generate_subtitles_from_video, burn_subtitles_into_video,
            )
            video_path = params.get("video_path") or "LAST"
            language = params.get("language")
            model_name = params.get("model", "base")
            srt_path = params.get("srt_path")
            if not srt_path:
                srt_result = generate_subtitles_from_video(
                    video_path=video_path, language=language, model_name=model_name,
                )
                if srt_result.get("status") == "error":
                    return {"status": "error", "message": f"Échec .srt : {srt_result.get('message')}"}
                srt_path = srt_result.get("srt_path")
            return burn_subtitles_into_video(video_path=video_path, srt_path=srt_path)
    except Exception as exc:
        logger.error("Erreur Vision (%s) : %s", act_name, exc, exc_info=True)
        return {"status": "error", "message": f"Erreur multimédia : {exc}"}

    if act_name == "headless_scrape":
        url = params.get("url") or params.get("query") or ""
        if not url:
            return {"status": "error", "message": "URL manquante pour headless_scrape"}

        if _is_sterile_url(url):
            logger.warning("[headless_scrape] URL stérile rejetée : %s", url)
            return {
                "status": "error",
                "message": (
                    f"URL stérile rejetée (page de recherche, home ou login). "
                    f"Utilise une URL DIRECTE de contenu issue des résultats "
                    f"de headless_search."
                ),
            }

        try:
            from worker_headless import HeadlessWorker
            from nerves._async_utils import run_async_safely
            logger.info("[headless_scrape] Démarrage : %s", url)
            worker = HeadlessWorker(headless=True)
            result = run_async_safely(worker.fetch_page_content(url))
            if result is None:
                return {"status": "error", "message": f"headless_scrape : impossible de charger {url}."}
            preview = str(result)[:200] if result else ""
            logger.info("[headless_scrape] OK %s (%d chars) | preview=%s", url, len(str(result)), preview)
            return result
        except Exception as exc:
            logger.error("Erreur headless_scrape : %s", exc, exc_info=True)
            return {"status": "error", "message": f"headless_scrape échoué : {exc}"}

    if act_name == "headless_search":
        query = params.get("query") or ""
        if not query:
            return {"status": "error", "message": "Query manquante pour headless_search"}

        query = _extract_keywords(query)

        try:
            from nerves.headless_nerves import _handler_headless_search
            return _handler_headless_search(query=query)
        except Exception as exc:
            logger.error("Erreur headless_search : %s", exc, exc_info=True)
            return {"status": "error", "message": f"headless_search échoué : {exc}"}

    if act_name in hermes.tools:
        h_disp = hermes.dispatch(act_name, params)
        if h_disp.get("status") == "SUCCESS" and h_disp.get("results"):
            task_res = list(h_disp["results"].values())[0]
            if task_res.get("success"):
                data = task_res.get("data")
                if isinstance(data, dict):
                    return data
                return {"status": "success", "message": str(data)}

    exec_res = execute_agent_crm_tool(act_name, params)
    return exec_res or {"status": "error", "message": "Aucune réponse d'exécution"}


# ══════════════════════════════════════════════════════════════════
# ★ PATCH 3A — _is_poor_result corrigé
# ══════════════════════════════════════════════════════════════════
def _is_poor_result(exec_res: Optional[dict], act_name: str) -> bool:
    if not isinstance(exec_res, dict):
        return True
    if exec_res.get("status") != "success":
        return True

    if act_name == "headless_search":
        leads = exec_res.get("leads", []) or []
        return len(leads) == 0

    if act_name == "headless_scrape":
        html = exec_res.get("html", "") or ""
        return len(html) < POOR_RESULT_THRESHOLD

    if act_name == "web_sync":
        report = exec_res.get("report", "") or ""
        return len(str(report)) < POOR_RESULT_THRESHOLD

    return False


def _format_execution_result(act_name: str, exec_res: dict) -> str:
    if not isinstance(exec_res, dict):
        return str(exec_res)

    fn = exec_res.get("filename", "")
    srt_fn = exec_res.get("srt_filename", "")

    if act_name == "generate_subtitles" and exec_res.get("status") == "success":
        language = exec_res.get("language", "?")
        segments = exec_res.get("segments_count", 0)
        text_preview = exec_res.get("text", "")[:300]
        return (
            f"🎤 **Sous-titres générés !**\n"
            f"- Langue détectée : `{language}`\n"
            f"- Segments : **{segments}**\n"
            f"- Fichier : `{srt_fn}`\n\n"
            f"**Aperçu :**\n```\n{text_preview}\n```\n\n"
            f"[📥 Télécharger le .srt](/api/download/{srt_fn})\n"
        )

    if act_name == "burn_subtitles" and exec_res.get("status") == "success" and fn:
        size_mb = exec_res.get("size_bytes", 0) / (1024 * 1024)
        return (
            f"🎬 **Vidéo sous-titrée !**\n"
            f"- Fichier : `{fn}`\n"
            f"- Taille : **{size_mb:.1f} Mo**\n\n"
            f"[📥 Télécharger la vidéo sous-titrée](/api/download/{fn})\n\n"
            f'<video controls loop src="/api/download/{fn}" '
            f'style="max-width:100%;border-radius:8px;"></video>'
        )

    if exec_res.get("status") == "success" and fn:
        if any(fn.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]):
            return f"🎨 **Image générée !**\n\n![{fn}](/api/download/{fn})"
        elif any(fn.lower().endswith(ext) for ext in [".mp4", ".webm", ".mov", ".avi"]):
            duration = exec_res.get("actual_duration") or exec_res.get("duration") or ""
            provider = exec_res.get("provider", "")
            model = exec_res.get("model_id", "")
            with_audio = exec_res.get("with_audio", False)
            stitched = exec_res.get("stitched", False)
            clips = exec_res.get("clips", [])
            mode_used = exec_res.get("mode_used", "")
            extended_by = exec_res.get("extended_by")
            source_video = exec_res.get("source_video", "")

            is_extension = (
                bool(extended_by)
                or act_name in ("extend_video", "extend_video_multiple")
                or bool(mode_used and mode_used in ("keyframes", "multi_reference"))
            )

            if is_extension:
                info_lines = [f"🎬 **Vidéo étendue !**" + (f" (+{extended_by}s)" if extended_by else "")]
                if mode_used: info_lines.append(f"- Mode continuité : `{mode_used}`")
                if source_video: info_lines.append(f"- Source : `{source_video}`")
                if with_audio: info_lines.append(f"- Audio : ✅")
                if duration: info_lines.append(f"- Durée totale : **{duration}s**")
                if clips and len(clips) > 1: info_lines.append(f"- Multi : `{len(clips)}` clips")
            else:
                info_lines = [f"🎬 **Vidéo générée !**"]
                if duration: info_lines.append(f"- Durée : **{duration}s**")
                if provider: info_lines.append(f"- Provider : `{provider}`")
                if model: info_lines.append(f"- Modèle : `{model}`")
                if with_audio: info_lines.append(f"- Audio : ✅")
                if stitched and clips: info_lines.append(f"- Multi-clips : `{clips}`")

            info = "\n".join(info_lines)
            video_player = (
                f'\n\n<video controls autoplay loop muted '
                f'style="max-width:100%; border-radius:12px; '
                f'box-shadow:0 4px 20px rgba(0,0,0,0.3); margin:12px 0;">'
                f'<source src="/api/download/{fn}" type="video/mp4">'
                f'Votre navigateur ne supporte pas la vidéo HTML5.'
                f'</video>\n\n'
                f'[📥 Télécharger la vidéo](/api/download/{fn})\n'
            )
            return info + video_player

    if act_name == "headless_scrape":
        if exec_res.get("status") == "success":
            url = exec_res.get("url", "")
            title = exec_res.get("title", "")
            html = exec_res.get("html", "") or ""
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "noscript", "meta", "link"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
            except ImportError:
                text = html
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            text = "\n".join(lines)
            preview = text[:4000]
            return (
                f"✅ **Scraping réussi** : {url}\n"
                f"- Titre : **{title}**\n"
                f"- Contenu extrait : {len(text)} chars\n\n"
                f"**Contenu textuel** :\n```\n{preview}\n```\n"
                f"→ Analyse ce contenu et donne à l'utilisateur ce qu'il a demandé."
            )
        else:
            return exec_res.get("message", "❌ headless_scrape a échoué")

    if act_name == "headless_search":
        if not isinstance(exec_res, dict):
            return f"Résultat brut : {exec_res}"
        if exec_res.get("status") != "success":
            return f"❌ headless_search a échoué : {exec_res.get('message', 'erreur inconnue')}"
        leads = exec_res.get("leads", []) or []
        query_used = exec_res.get("query", "")
        if not leads:
            return (
                f"ℹ️ Aucun résultat trouvé pour : **{query_used}**\n\n"
                f"→ Dis à l'utilisateur qu'aucun résultat pertinent n'a été "
                f"trouvé et propose de reformuler."
            )
        lines = [f"✅ **{len(leads)} résultats** pour « {query_used} » :\n"]
        for i, lead in enumerate(leads, 1):
            title = (lead.get("title") or "")[:100]
            url = lead.get("source_url") or ""
            snippet = (lead.get("snippet") or "")[:200]
            lines.append(f"**{i}. {title}**")
            lines.append(f"   → {url}")
            if snippet:
                lines.append(f"   {snippet}")
            lines.append("")
        lines.append(
            "→ Utilise ces résultats pour répondre à la demande. "
            "Cite les sources (URLs)."
        )
        return "\n".join(lines)

    if act_name == "web_sync":
        if exec_res.get("status") != "success":
            return exec_res.get("message", "❌ web_sync a échoué")
        report = exec_res.get("report", "") or ""
        report_str = str(report).strip()
        if not report_str or len(report_str) < 100:
            return (
                "⚠️ **Veille web sans résultat exploitable**\n\n"
                "→ Le pipeline WebAgent n'a pas pu extraire de contenu.\n"
                "→ Dis HONNÊTEMENT à l'utilisateur qu'aucune source n'a été "
                "trouvée et propose de reformuler.\n"
                "→ N'INVENTE AUCUNE actualité."
            )
        return f"🌐 **Veille web approfondie** :\n\n{report_str[:5000]}"

    return exec_res.get("message", "Opération OK")


def _extract_first_action(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    matches = list(ACTION_REGEX.finditer(text))
    if not matches:
        return None
    match = matches[0]
    act_name = match.group(1)
    raw_payload = match.group(2).strip()

    params: Dict[str, Any] = {}
    try:
        p_json = json.loads(raw_payload)
        if isinstance(p_json, dict):
            params = p_json
    except Exception:
        try:
            p_ast = ast.literal_eval(raw_payload)
            if isinstance(p_ast, dict):
                params = p_ast
        except Exception:
            pass

    if act_name == "headless_scrape":
        url = params.get("url") or ""
        if _is_sterile_url(url):
            logger.info("[ActionFilter] Action stérile rejetée : %s", url)
            return None

    return {"name": act_name, "params": params}


# ══════════════════════════════════════════════════════════════════
# ★ PATCH 3B — AUTO-SCRAPE APRÈS headless_search
# ══════════════════════════════════════════════════════════════════
def _auto_scrape_search_results(exec_res: dict, query: str) -> List[Dict[str, Any]]:
    """
    Scrape les 2 premières URLs d'un résultat headless_search.
    Retourne une liste de dicts {url, title, content}.
    """
    scraped: List[Dict[str, Any]] = []
    if not isinstance(exec_res, dict) or exec_res.get("status") != "success":
        return scraped

    leads = exec_res.get("leads", []) or []
    if not leads:
        return scraped

    count = 0
    for lead in leads:
        if count >= AUTO_SCRAPE_MAX_URLS:
            break
        url = lead.get("source_url") or ""
        title = lead.get("title") or ""
        if not url or _is_sterile_url(url):
            continue

        logger.info("[AutoScrape] Scraping #%d : %s", count + 1, url[:100])
        try:
            scrape_res = _execute_action_unified("headless_scrape", {"url": url})
        except Exception as exc:
            logger.warning("[AutoScrape] Échec sur %s : %s", url, exc)
            continue

        if not isinstance(scrape_res, dict) or scrape_res.get("status") != "success":
            logger.warning("[AutoScrape] Réponse non-success pour %s", url)
            continue

        html = scrape_res.get("html", "") or ""
        if not html:
            continue

        try:
            from bs4 import BeautifulSoup as _BS
            soup = _BS(html, "html.parser")
            for tag in soup(["script", "style", "noscript", "meta", "link", "nav", "footer", "header", "aside"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 20]
            text = "\n".join(lines)
            text = text[:AUTO_SCRAPE_MAX_CHARS_PER_PAGE]
        except Exception as exc:
            logger.warning("[AutoScrape] Extraction texte échouée sur %s : %s", url, exc)
            continue

        if text and len(text) > 100:
            scraped.append({
                "url": url,
                "title": title,
                "content": text,
            })
            count += 1
            logger.info("[AutoScrape] ✓ %s (%d chars)", url[:80], len(text))

    return scraped


def _format_auto_scraped_block(pages: List[Dict[str, Any]]) -> str:
    """Formate les pages auto-scrapées pour injection dans le prompt."""
    if not pages:
        return ""
    lines = [
        "\n\n═══════════════════════════════════════════════════════════════",
        "📄 CONTENU RÉEL DES PAGES (auto-scrapé après headless_search)",
        "═══════════════════════════════════════════════════════════════\n",
    ]
    for i, p in enumerate(pages, 1):
        lines.append(f"### Page {i} : {p['title']}")
        lines.append(f"URL : {p['url']}")
        lines.append(f"Contenu :\n{p['content']}\n")
        lines.append("─" * 60)
    lines.append(
        "\n⚠️ UTILISE UNIQUEMENT LE CONTENU CI-DESSUS pour répondre. "
        "N'invente RIEN. Cite les URLs comme sources.\n"
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# 🚀 ROUTE PRINCIPALE
# ══════════════════════════════════════════════════════════════════
@router.post("/api/chat")
async def chat(request: Request):
    with span("chat.request") as chat_span:
        return await _chat_impl(request, chat_span)


async def _chat_impl(request: Request, chat_span):
    data = await request.json() or {}
    messages = data.get("messages", [])
    provider = data.get("provider", "b_ai")
    model = data.get("model", "glm-5.3-flash")

    set_span_attribute("chat.messages_count", len(messages) if isinstance(messages, list) else 0)
    set_span_attribute("chat.provider", provider)
    set_span_attribute("chat.model", model)
    trace_id = get_current_trace_id()
    if trace_id:
        logger.info("[Chat] trace_id=%s provider=%s model=%s", trace_id, provider, model)

    trimmed_messages = _truncate_messages(messages)
    set_span_attribute("chat.trimmed_count", len(trimmed_messages))

    last_user_query = ""
    user_status = "neutral"

    if trimmed_messages:
        last_msg = trimmed_messages[-1]
        if last_msg.get("role") == "user":
            last_user_query = last_msg.get("content", "").strip()
            user_status = _detect_user_response(last_user_query)
            set_span_attribute("chat.user_query_len", len(last_user_query))

    smart_mode = data.get("smart", True)
    routing_used = "legacy"

    if smart_mode and _AGI_ROUTER_OK and last_user_query:
        try:
            with span("chat.smart_router.agi",
                      **{"router.engine": "agi",
                         "router.query_len": len(last_user_query)}):
                routing = _agi_route_semantic(last_user_query)
                routed_provider = routing.get("provider", "")
                routed_model = routing.get("model", "")
                set_span_attribute("router.provider", routed_provider)
                set_span_attribute("router.model", routed_model)
                set_span_attribute("router.task_type", routing.get("task_type", "?"))
                if routed_provider:
                    provider = routed_provider
                    if routed_model:
                        model = routed_model
                    routing_used = f"agi:{routing.get('task_type', 'chat')}"
                    logger.info(
                        "[SmartRouter AGI] Route : %s/%s (type=%s, fallback=%s)",
                        provider, model,
                        routing.get("task_type", "?"),
                        routing.get("fallback_used", False),
                    )
                set_span_status_ok()
        except Exception as e:
            set_span_status_error(str(e))
            logger.warning("[SmartRouter AGI] Échec, fallback legacy : %s", e)

    if routing_used == "legacy" and _INTEL_OK and smart_mode:
        try:
            with span("chat.smart_router.legacy"):
                chosen = smart_router.route(trimmed_messages)
                if chosen:
                    provider, model = chosen[0]
                    routing_used = "legacy"
                    set_span_attribute("router.provider", provider)
                    set_span_attribute("router.model", model)
                    set_span_status_ok()
                    logger.info("[SmartRouter legacy] Route : %s/%s", provider, model)
        except Exception as e:
            set_span_status_error(str(e))
            logger.warning("[SmartRouter legacy] Échec : %s", e)

    set_span_attribute("chat.routing_used", routing_used)

    corr_id = f"corr_{uuid.uuid4().hex[:10]}"
    set_span_attribute("chat.correlation_id", corr_id)

    if last_user_query:
        published = False
        if _AGI_EVENT_BUS_OK:
            try:
                _agi_publish_event(
                    "web-cleaned",
                    {
                        "query": last_user_query,
                        "correlation_id": corr_id,
                        "source": "chat",
                        "routing": routing_used,
                    },
                )
                published = True
            except Exception as e:
                logger.debug("[EventBus AGI] Échec : %s", e)

        if not published and event_bus:
            try:
                event_bus.publish("web-cleaned", {"query": last_user_query})
            except Exception:
                pass

    if last_user_query.startswith("/") and dispatch_slash_command:
        slash_res = dispatch_slash_command(last_user_query)
        if slash_res and slash_res.get("ok"):
            set_span_attribute("chat.slash_command", True)
            async def generate_slash():
                j_out = json.dumps({'chunk': slash_res['output']})
                yield f"data: {j_out}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            return StreamingResponse(
                generate_slash(), media_type="text/event-stream"
            )

    if len(trimmed_messages) >= 2:
        prev_msg = trimmed_messages[-2]
        is_ast = prev_msg.get("role") == "assistant"
        has_act = "[ACTION:" in prev_msg.get("content", "")

        if is_ast and has_act:
            if user_status == "agreed":
                act_content = prev_msg.get("content", "")
                action_matches = list(ACTION_REGEX.finditer(act_content))

                if action_matches:
                    match = action_matches[-1]
                    act_name = match.group(1)
                    raw_payload = match.group(2).strip()

                    params = {}
                    try:
                        p_json = json.loads(raw_payload)
                        if isinstance(p_json, dict):
                            params = p_json
                    except Exception:
                        try:
                            p_ast = ast.literal_eval(raw_payload)
                            if isinstance(p_ast, dict):
                                params = p_ast
                        except Exception:
                            pass

                    if act_name not in MULTIMEDIA_ACTIONS:
                        params["provider"] = provider
                        params["model"] = model

                    with span("chat.action_execute", **{"action.name": act_name}):
                        exec_res = _execute_action_unified(act_name, params)
                        res_msg = _format_execution_result(act_name, exec_res)
                        if len(res_msg) > 3000:
                            res_msg = res_msg[:3000] + "\n... [tronqué]"
                        set_span_attribute("action.result_len", len(res_msg))
                        set_span_status_ok()

                    inj = (f"\n\n[SYSTÈME - RÉSULTAT DE L'ACTION "
                           f"'{act_name}' :] \n{res_msg}\n\n-> "
                           f"Donne ton retour à l'utilisateur.")
                    trimmed_messages[-1]["content"] += inj

            elif user_status == "refused":
                old_c = trimmed_messages[-2]["content"]
                trimmed_messages[-2]["content"] = old_c.replace(
                    "[ACTION:", "[REFUSED_ACTION:"
                )
                inj = "\n\n[SYSTÈME - ACTION REFUSÉE. Propose autre chose.]"
                trimmed_messages[-1]["content"] += inj

    dynamic_system_prompt = BEK_GOLDEN_RULES.strip()

    if last_user_query:
        sig = minhash_engine.compute_signature(last_user_query)
        hll_counter.add(last_user_query)

        try:
            with span("chat.memory_search"):
                mem_ctx = search_memory(last_user_query, top_k=3)
                if mem_ctx:
                    mem_ctx_str = _safe_str(mem_ctx)
                    if len(mem_ctx_str) > MAX_CHARS_PER_MESSAGE:
                        mem_ctx_str = mem_ctx_str[:MAX_CHARS_PER_MESSAGE] + "…[tronqué]"
                    dynamic_system_prompt += f"\n\n[MÉMOIRE] :\n{mem_ctx_str}"
                    set_span_attribute("memory.context_len", len(mem_ctx_str))
                set_span_status_ok()
        except Exception as e:
            logger.warning("Erreur mémoire : %s", e)

        try:
            with span("chat.hermes_planner"):
                plan = hermes.goap_planner(last_user_query)
                if plan:
                    f_plan = [t for t in plan if t.get("tool") != "default_llm"]
                    if f_plan:
                        p_json = json.dumps(f_plan, ensure_ascii=False)
                        dynamic_system_prompt += f"\n\n[PLAN HERMES PRIORITAIRE À EXÉCUTER] :\n{p_json}"
                        set_span_attribute("hermes.plan_count", len(f_plan))
                set_span_status_ok()
        except Exception as e:
            set_span_status_error(str(e))
            logger.error("[HERMES] Échec planificateur : %s", e)

    exec_messages = [
        {"role": "system", "content": dynamic_system_prompt}
    ] + trimmed_messages

    async def generate_proxy():
        act_name: str = ""
        params: Dict[str, Any] = {}
        res_msg: str = ""
        exec_res: Optional[Dict[str, Any]] = None

        full_text_accumulated: List[str] = []
        action_detected = False
        total_actions_executed = 0
        action_was_executed = False
        last_result_poor = False
        chunks_without_close = 0

        # ★ PATCH 3D : déclaré au niveau de la fonction pour être accessible après le for
        auto_scraped_pages: List[Dict[str, Any]] = []

        try:
            for item in provider_manager.execute_chat_stream(
                messages=exec_messages,
                provider=provider,
                model=model,
                temperature=0.7,
                max_tokens=4096,
            ):
                if "error" in item:
                    error_msg = item.get("error", "Erreur inconnue")
                    logger.error("[ProviderManager] Erreur : %s", error_msg)
                    err_chunk = "\n\n⚠️ **Erreur provider** : " + str(error_msg) + "\n\n"
                    yield f"data: {json.dumps({'chunk': err_chunk})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return

                if "chunk" not in item:
                    continue

                chunk = item["chunk"]
                chunk = _sanitize_llm_output(chunk)
                if not chunk.strip():
                    continue

                full_text_accumulated.append(chunk)
                current_text = "".join(full_text_accumulated)

                if "[ACTION:" in current_text:
                    action_detected = True

                if action_detected and "[/ACTION]" not in current_text:
                    chunks_without_close += 1
                    if chunks_without_close > MAX_CHUNKS_WITHOUT_CLOSE:
                        logger.warning(
                            "[Stream] Action incomplète détectée après %d chunks — abandon.",
                            chunks_without_close,
                        )
                        warn_incomplete = "\n\n⚠️ **Action incomplète** détectée. Reformulez la demande.\n\n"
                        yield f"data: {json.dumps({'chunk': warn_incomplete})}\n\n"
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        return

                j_chunk = json.dumps({'chunk': chunk}, ensure_ascii=False)
                yield f"data: {j_chunk}\n\n"

                if action_detected and not action_was_executed and "[/ACTION]" in current_text:
                    action_match = _extract_first_action(current_text)
                    if action_match:
                        act_name = action_match["name"]
                        params = action_match["params"]

                        if act_name == "headless_search":
                            sent_query = params.get("query", "")
                            if _is_translation(last_user_query, sent_query):
                                logger.warning(
                                    "[QueryCorrect] Traduction détectée : '%s' → '%s'",
                                    sent_query, last_user_query,
                                )
                                params["query"] = last_user_query
                        # ★ PATCH 3.2.b — Routing intelligent via BEK-REX
                        # Si BEK-REX route vers TIER_2/TIER_3/TIER_4,
                        # on remplace headless_search par web_sync (WebAgent profond)
                        if act_name == "headless_search":
                            try:
                                _routing = _bek_rex_route(last_user_query)
                                _should_use_ws = _bek_rex_should_use_web_sync(
                                    last_user_query, _routing
                                )
                                logger.info(
                                    "[PATCH 3.2.b] BEK-REX routing : tier=%s | web_sync=%s | source=%s",
                                    _routing.get("tier"),
                                    _should_use_ws,
                                    _routing.get("source"),
                                )
                                if _should_use_ws:
                                    logger.info(
                                        "[PATCH 3.2.b] Redirection : headless_search → web_sync"
                                    )
                                    act_name = "web_sync"
                                    # web_sync utilise "query" comme paramètre
                                    params = {
                                        "query": params.get("query", last_user_query),
                                    }
                            except Exception as _rex_err:
                                logger.warning(
                                    "[PATCH 3.2.b] BEK-REX échec, on garde headless_search : %s",
                                    _rex_err,
                                )

                        if act_name not in MULTIMEDIA_ACTIONS:
                            params["provider"] = provider
                            params["model"] = model

                        msg_imm = '\n\n⚙️ *Exécution...*\n'
                        yield f"data: {json.dumps({'chunk': msg_imm})}\n\n"

                        exec_res = _execute_action_unified(act_name, params)
                        res_msg = _format_execution_result(act_name, exec_res)

                        # ★ PATCH 3B : auto-scrape après headless_search réussi
                        if act_name == "headless_search" and isinstance(exec_res, dict):
                            if exec_res.get("status") == "success":
                                leads = exec_res.get("leads", []) or []
                                if leads:
                                    auto_scrape_msg = "\n\n📄 *Extraction du contenu des pages...*\n\n"
                                    yield f"data: {json.dumps({'chunk': auto_scrape_msg})}\n\n"
                                    try:
                                        auto_scraped_pages = _auto_scrape_search_results(
                                            exec_res, last_user_query or params.get("query", "")
                                        )
                                    except Exception as exc:
                                        logger.warning("[PATCH 3B] Auto-scrape échoué : %s", exc)
                                        auto_scraped_pages = []

                                    if auto_scraped_pages:
                                        pages_msg = f"✅ **{len(auto_scraped_pages)} page(s) extraite(s)**\n\n"
                                        yield f"data: {json.dumps({'chunk': pages_msg})}\n\n"

                        eval_r = evaluate_response_quality(last_user_query, res_msg)
                        if not eval_r["passed"]:
                            res_msg = f"⚠️ [BEK Guard] Filtré : {eval_r['reason']}"

                        res_chunk = "\n\n" + str(res_msg) + "\n\n"

                        # ★ PATCH 3B : injecter le contenu auto-scrapé
                        if auto_scraped_pages:
                            scraped_block = _format_auto_scraped_block(auto_scraped_pages)
                            res_chunk += scraped_block

                        yield f"data: {json.dumps({'chunk': res_chunk})}\n\n"

                        total_actions_executed += 1
                        action_was_executed = True
                        last_result_poor = _is_poor_result(exec_res, act_name)

                    break

            relance_done = False

            # ══════════════════════════════════════════════════════════════════
            # ★ PATCH 3D — SYNTHÈSE FORCÉE APRÈS AUTO-SCRAPE
            # ------------------------------------------------------------------
            # Avant : la synthèse ne tournait QUE si last_result_poor=True
            # Après : elle tourne aussi si headless_search a produit des pages
            #         auto-scrapées (même si last_result_poor=False)
            # ══════════════════════════════════════════════════════════════════
            _has_auto_scraped = bool(auto_scraped_pages)
            _needs_synthesis = last_result_poor or _has_auto_scraped

            if _has_auto_scraped:
                logger.info(
                    "[PATCH 3D] Synthèse forcée car %d page(s) auto-scrapée(s)",
                    len(auto_scraped_pages),
                )

            while (
                _needs_synthesis
                and action_was_executed
                and not relance_done
                and total_actions_executed < MAX_TOTAL_ACTIONS
            ):
                relance_done = True

                # Fallback web_sync UNIQUEMENT si résultat vraiment pauvre
                # ET pas de contenu auto-scrapé disponible
                if act_name == "headless_search" and last_result_poor and not _has_auto_scraped:
                    fallback_query = last_user_query or params.get("query", "")
                    fallback_query = _extract_keywords(fallback_query)
                    logger.info(
                        "[Fallback] headless_search pauvre → web_sync('%s')",
                        fallback_query,
                    )
                    fallback_msg = "\n\n🌐 *Fallback : veille multi-sources...*\n\n"
                    yield f"data: {json.dumps({'chunk': fallback_msg})}\n\n"

                    exec_res = _execute_action_unified(
                        "web_sync",
                        {"query": fallback_query, "provider": provider, "model": model},
                    )
                    res_msg = _format_execution_result("web_sync", exec_res)
                    ws_chunk = "\n\n" + str(res_msg) + "\n\n"
                    yield f"data: {json.dumps({'chunk': ws_chunk})}\n\n"

                    act_name = "web_sync"
                    total_actions_executed += 1
                    last_result_poor = _is_poor_result(exec_res, act_name)

                # Construction du message de synthèse
                # Note : si auto_scraped_pages, le contenu est DÉJÀ dans res_msg
                # (injecté plus haut via _format_auto_scraped_block)
                synthesis_messages = list(exec_messages) + [
                    {
                        "role": "assistant",
                        "content": "".join(full_text_accumulated),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"[RÉSULTAT DE L'ACTION '{act_name}'] :\n\n"
                            f"{res_msg}\n\n"
                            f"→ Analyse les informations ci-dessus et réponds à ma "
                            f"demande initiale :\n« {last_user_query} »\n\n"
                            f"RÈGLES STRICTES :\n"
                            f"  1. Utilise UNIQUEMENT les informations ci-dessus.\n"
                            f"  2. Si elles sont SUFFISANTES → conclus directement.\n"
                            f"  3. Si elles sont INSUFFISANTES → dis-le honnêtement.\n"
                            f"  4. N'appelle AUCUN outil supplémentaire.\n"
                            f"  5. N'invente RIEN (pas d'URLs, pas de chiffres, pas de dates).\n"
                            f"  6. Cite tes sources (URLs) si tu en as.\n"
                            f"  7. Respecte le format demandé.\n"
                            f"  8. Si tu as la réponse, DONNE-LA.\n"
                        ),
                    },
                ]

                synth_msg = "\n\n💭 *Synthèse en cours...*\n\n"
                yield f"data: {json.dumps({'chunk': synth_msg})}\n\n"

                for item2 in provider_manager.execute_chat_stream(
                    messages=synthesis_messages,
                    provider=provider,
                    model=model,
                    temperature=0.5,
                    max_tokens=2048,
                ):
                    if "error" in item2:
                        error_msg = item2.get("error", "Erreur inconnue")
                        synth_err = "\n\n⚠️ Erreur synthèse : " + str(error_msg) + "\n"
                        yield f"data: {json.dumps({'chunk': synth_err})}\n\n"
                        break

                    if "chunk" in item2:
                        chunk2 = _sanitize_llm_output(item2["chunk"])
                        if chunk2.strip():
                            if "[ACTION:" in chunk2:
                                logger.warning(
                                    "[Synthèse] Action détectée malgré interdiction — ignorée."
                                )
                            else:
                                yield f"data: {json.dumps({'chunk': chunk2}, ensure_ascii=False)}\n\n"

                break

            if action_detected and not action_was_executed:
                logger.warning(
                    "[Stream] Action détectée mais non exécutée (incomplète)."
                )
                final_incomplete = (
                    "\n\n⚠️ **Action incomplète** : le LLM n'a pas fermé sa "
                    "balise [/ACTION]. Reformulez la demande.\n\n"
                )
                yield f"data: {json.dumps({'chunk': final_incomplete})}\n\n"

            full_text = "".join(full_text_accumulated)
            set_span_attribute("chat.response_len", len(full_text))
            set_span_attribute("chat.total_actions", total_actions_executed)
            set_span_attribute("chat.last_result_poor", last_result_poor)

            if (_AGI_COGNITIVE_OK
                    and full_text.strip()
                    and not action_detected
                    and last_user_query):
                try:
                    with span("chat.cognitive_check",
                              **{"cognitive.draft_len": len(full_text)}):
                        cognitive = _agi_cognitive_pipeline(
                            draft=full_text,
                            original_query=last_user_query,
                            provider=provider,
                            model=model,
                        )
                        if cognitive.get("status") == "success":
                            meta_cognitive = {
                                "cognitive_verdict": cognitive.get("final_verdict", "GOOD"),
                                "cognitive_needs_correction": cognitive.get("needs_correction", False),
                                "cognitive_issues_count": len(cognitive.get("issues", [])),
                                "routing_used": routing_used,
                            }
                            j_meta_cog = json.dumps({'meta': meta_cognitive})
                            yield f"data: {j_meta_cog}\n\n"

                            set_span_attribute("cognitive.verdict", cognitive.get("final_verdict", "?"))
                            if cognitive.get("needs_correction"):
                                set_span_status_error("needs_correction")
                                warn_msg = (
                                    f"\n\n> ⚠️ **Vérification cognitive** : "
                                    f"verdict `{cognitive.get('final_verdict')}`, "
                                    f"{len(cognitive.get('issues', []))} point(s) à vérifier.\n"
                                )
                                yield f"data: {json.dumps({'chunk': warn_msg})}\n\n"
                            else:
                                set_span_status_ok()
                except Exception as cog_exc:
                    set_span_status_error(str(cog_exc))
                    logger.debug("[Chat] Cognitive échec silencieux : %s", cog_exc)

            if (_INTEL_OK and full_text.strip() and not action_detected):
                try:
                    score, issues = ResponseQuality.evaluate(full_text, 4096)
                    meta_data = {'quality_score': score, 'issues': issues}
                    j_meta = json.dumps({'meta': meta_data})
                    yield f"data: {j_meta}\n\n"
                    set_span_attribute("chat.quality_score", score)

                    if score < 60:
                        corrective = list(exec_messages) + [
                            {"role": "assistant", "content": full_text},
                            {"role": "user", "content":
                                "[STEERING CORRECTIF] Répare cette erreur : "
                                + ("; ".join(issues) or "mauvaise qualité")}
                        ]
                        corr_stream = auto_engine._run_once(
                            corrective, provider, model, 4096)
                        corrected_text = corr_stream[0]
                        if corrected_text.strip() != full_text.strip():
                            msg_corr = '\n\n--- ✨ Version corrigée ---\n\n'
                            yield f"data: {json.dumps({'chunk': msg_corr})}\n\n"

                            for i in range(0, len(corrected_text), 24):
                                c_part = corrected_text[i:i + 24]
                                yield f"data: {json.dumps({'chunk': c_part})}\n\n"
                except Exception as qe:
                    logger.warning("[QualityGate] Échec : %s", qe)

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as stream_err:
            logger.error("[Stream Error] %s", stream_err, exc_info=True)
            err_msg = "\n\n⚠️ Flux Error : " + str(stream_err)
            j_serr = json.dumps({'chunk': err_msg})
            yield f"data: {j_serr}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate_proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )