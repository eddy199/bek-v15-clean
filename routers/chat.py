# ==============================================================================
# BEK-v16 — Routeur Chat Streaming & Human-in-the-Loop (routers/chat.py)
# ------------------------------------------------------------------------------
# CORRECTIF v9 (2026-09-20) :
# - Détection affinée du web_sync (report présent mais court)
# - Le v8 est conservé (extraction mots-clés, cascade, anti-blocage)
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


logger = logging.getLogger("BEKApp")

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
)
_STERILE_URL_REGEX = re.compile("|".join(_STERILE_URL_PATTERNS), re.IGNORECASE)


def _is_sterile_url(url: str) -> bool:
    if not url:
        return False
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

# ACTIONS DISPONIBLES :
   - [ACTION:generate_image]{{"prompt": "detailed description in english"}}[/ACTION]
   - [ACTION:edit_image]{{"image_paths": ["filename.png"], "prompt": "exact modification directive in english"}}[/ACTION]
   - [ACTION:generate_video]{{"prompt": "detailed video description in english"}}[/ACTION]
   - [ACTION:edit_video]{{"video_paths": ["filename.mp4"], "prompt": "exact modification directive in english"}}[/ACTION]
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

## 🎯 EXTRACTION DE MOTS-CLÉS (RÈGLE V8 CRITIQUE)
- Quand tu génères une requête pour headless_search, tu dois EXTRAIRE
  les MOTS-CLÉS essentiels au lieu d'envoyer la phrase complète.
- Maximum 8 mots. Pas de verbes, pas d'articles.
- Exemples CORRECTS :
  User : "Cherche les 5 dernières actualités sur l'IA en 2026 et résume chacune en 2 phrases."
  ✅ Toi : [ACTION:headless_search]{{"query": "actualités IA 2026"}}[/ACTION]

  User : "Peux-tu me trouver les dernières nouvelles concernant OpenAI ?"
  ✅ Toi : [ACTION:headless_search]{{"query": "OpenAI news"}}[/ACTION]

  User : "Quel est le prix actuel du Bitcoin en euros ?"
  ✅ Toi : [ACTION:headless_search]{{"query": "prix Bitcoin EUR"}}[/ACTION]

- Exemples INTERDITS (phrases complètes) :
  ❌ [ACTION:headless_search]{{"query": "Cherche les 5 dernières actualités sur l'IA en 2026 et résume chacune en 2 phrases."}}[/ACTION]

## ❌ EXEMPLES DE TRADUCTION INTERDITS
  User: "Quel est le prix actuel du Bitcoin en euros ?"
  ❌ [ACTION:headless_search]{{"query": "Bitcoin price EUR"}}[/ACTION]

# 🎯 CADRAGE STRICT
- Réponds STRICTEMENT à la question.
- Respecte le FORMAT demandé (ex: "5 items × 2 phrases" → exactement 5×2).
- Va droit au but.

# HONNÊTETÉ RADICALE
- Si tu n'as PAS l'info → dis-le CLAIREMENT.
- INTERDICTION ABSOLUE d'inventer faits, dates, chiffres, URLs.

# 🚨 RÈGLE FINALE CRITIQUE
- Tu appelles UN SEUL outil par réponse utilisateur.
- Une fois le résultat obtenu, tu DOIS conclure.
- INTERDICTION d'appeler un 2ᵉ outil. Sauf si le 1ᵉʳ a retourné 0 résultat
  ou un résultat vide, auquel cas tu peux essayer web_sync UNE SEULE FOIS.
- INTERDICTION ABSOLUE d'inventer une URL.
- INTERDICTION d'utiliser des URLs de LOGIN (accounts.google.com, /login, etc.).

# DIRECTIVE MULTIMÉDIA ABSOLUE
- Pour TOUTE demande visuelle : generate_image, edit_image,
  generate_video, ou edit_video.
{_ARCHITECTURE_BLOCK}
"""


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
            return generate_image_with_provider(prompt=prompt)

        elif act_name == "edit_image":
            from services.vision import merge_and_edit_images
            paths = params.get("image_paths") or params.get("image_path") or []
            prompt = params.get("prompt") or params.get("user_prompt") or params.get("query") or ""
            return merge_and_edit_images(image_paths=paths, user_prompt=prompt)

        elif act_name == "generate_video":
            from services.vision import generate_video_with_provider
            prompt = params.get("prompt") or params.get("query") or ""
            return generate_video_with_provider(prompt=prompt)

        elif act_name == "edit_video":
            from services.vision import merge_and_edit_videos
            paths = params.get("video_paths") or params.get("video_path") or []
            prompt = params.get("prompt") or params.get("user_prompt") or params.get("query") or ""
            return merge_and_edit_videos(video_paths=paths, user_prompt=prompt)
    except Exception as exc:
        logger.error("Erreur Vision (%s) : %s", act_name, exc)
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
                    f"URL stérile rejetée (page de recherche ou de login). "
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
                return {
                    "status": "error",
                    "message": f"headless_scrape : impossible de charger {url}.",
                }
            preview = str(result)[:200] if result else ""
            logger.info(
                "[headless_scrape] OK %s (%d chars) | preview=%s",
                url, len(str(result)), preview,
            )
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
    if exec_res.get("status") == "success" and fn:
        if any(fn.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]):
            return f"🎨 **Image générée !**\n\n![{fn}](/api/download/{fn})"
        elif any(fn.lower().endswith(ext) for ext in [".mp4", ".webm", ".mov", ".avi"]):
            return f"🎬 **Vidéo générée !**\n\n[Télécharger la vidéo](/api/download/{fn})\n\n"

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
            return (
                f"❌ headless_search a échoué : "
                f"{exec_res.get('message', 'erreur inconnue')}"
            )
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

    # ── web_sync v9 : détection affinée ──
    if act_name == "web_sync":
        if exec_res.get("status") != "success":
            return exec_res.get("message", "❌ web_sync a échoué")

        report = exec_res.get("report", "") or ""
        report_str = str(report).strip()

        if not report_str or len(report_str) < 100:
            return (
                "⚠️ **Veille web sans résultat exploitable**\n\n"
                "→ Le pipeline WebAgent n'a pas pu extraire de contenu.\n"
                "→ Causes possibles : sources bloquées, réseau, timeout.\n"
                "→ Dis HONNÊTEMENT à l'utilisateur qu'aucune source n'a été "
                "trouvée et propose de reformuler la demande.\n"
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
                    yield f"data: {json.dumps({'chunk': f'\n\n⚠️ **Erreur provider** : {error_msg}\n\n'})}\n\n"
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
                        yield f"data: {json.dumps({'chunk': '\n\n⚠️ **Action incomplète** détectée. Reformulez la demande.\n\n'})}\n\n"
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

                        params["provider"] = provider
                        params["model"] = model

                        msg_imm = '\n\n⚙️ *Exécution...*\n'
                        yield f"data: {json.dumps({'chunk': msg_imm})}\n\n"

                        exec_res = _execute_action_unified(act_name, params)
                        res_msg = _format_execution_result(act_name, exec_res)

                        eval_r = evaluate_response_quality(last_user_query, res_msg)
                        if not eval_r["passed"]:
                            res_msg = f"⚠️ [BEK Guard] Filtré : {eval_r['reason']}"

                        yield f"data: {json.dumps({'chunk': f'\n\n{res_msg}\n\n'})}\n\n"

                        total_actions_executed += 1
                        action_was_executed = True
                        last_result_poor = _is_poor_result(exec_res, act_name)

                    break

            relance_done = False

            while (
                action_was_executed
                and last_result_poor
                and not relance_done
                and total_actions_executed < MAX_TOTAL_ACTIONS
            ):
                relance_done = True

                if act_name == "headless_search":
                    fallback_query = last_user_query or params.get("query", "")
                    fallback_query = _extract_keywords(fallback_query)
                    logger.info(
                        "[Fallback] headless_search pauvre → web_sync('%s')",
                        fallback_query,
                    )
                    yield f"data: {json.dumps({'chunk': '\n\n🌐 *Fallback : veille multi-sources...*\n\n'})}\n\n"

                    exec_res = _execute_action_unified(
                        "web_sync",
                        {"query": fallback_query, "provider": provider, "model": model},
                    )
                    res_msg = _format_execution_result("web_sync", exec_res)
                    yield f"data: {json.dumps({'chunk': f'\n\n{res_msg}\n\n'})}\n\n"

                    act_name = "web_sync"
                    total_actions_executed += 1
                    last_result_poor = _is_poor_result(exec_res, act_name)

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
                            f"RÈGLES SIMPLES :\n"
                            f"  1. Utilise UNIQUEMENT les informations ci-dessus.\n"
                            f"  2. Si elles sont SUFFISANTES → conclus directement.\n"
                            f"  3. Si elles sont INSUFFISANTES → dis-le honnêtement.\n"
                            f"  4. N'appelle AUCUN outil supplémentaire.\n"
                            f"  5. N'invente RIEN (pas d'URLs, pas de chiffres).\n"
                            f"  6. Cite tes sources (URLs) si tu en as.\n"
                            f"  7. Respecte le format demandé.\n"
                        ),
                    },
                ]

                yield f"data: {json.dumps({'chunk': '\n\n💭 *Synthèse en cours...*\n\n'})}\n\n"

                for item2 in provider_manager.execute_chat_stream(
                    messages=synthesis_messages,
                    provider=provider,
                    model=model,
                    temperature=0.5,
                    max_tokens=2048,
                ):
                    if "error" in item2:
                        error_msg = item2.get("error", "Erreur inconnue")
                        yield f"data: {json.dumps({'chunk': f'\n\n⚠️ Erreur synthèse : {error_msg}\n'})}\n\n"
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
                yield f"data: {json.dumps({'chunk': '\n\n⚠️ **Action incomplète** : le LLM n’a pas fermé sa balise [/ACTION]. Reformulez la demande.\n\n'})}\n\n"

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
            j_serr = json.dumps({'chunk': f'\n\n⚠️ Flux Error : {stream_err}'})
            yield f"data: {j_serr}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate_proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )