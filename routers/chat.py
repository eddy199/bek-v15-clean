# ==============================================================================
# BEK-v16 — Routeur Chat Streaming & Human-in-the-Loop (routers/chat.py)
# ------------------------------------------------------------------------------
# + OpenTelemetry : spans sur chat.request, smart_router, cognitive_check
# + Sanitizer tokens natifs LLM (Nemotron) + règles outil web
# + Fix: plus de CANCELED_ACTION intempestif + logs headless_scrape
# + headless_scrape : extraction texte via BeautifulSoup
# ==============================================================================
from __future__ import annotations

import ast
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

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


# ── LOGGER GLOBAL ──
logger = logging.getLogger("BEKApp")

# ── EXPRESSION RÉGULIÈRE UNIQUE (Anti-Coupure Interface) ──
ACTION_REGEX = re.compile(r"\x5bACTION:(\w+)\x5d(.*?)\x5b/ACTION\x5d", re.DOTALL)

# ── SANITIZER : tokens natifs de tool-calling LLM (Nemotron, Hermes format) ──
_LLM_NATIVE_TOKENS = (
    "<|tool_call_begin|>",
    "<|tool_call_end|>",
    "<|tool_call_argument_begin|>",
    "<|tool_call_argument_end|>",
    "<|tool_call|>",
    "<|tool_sep|>",
    "<|tool_calls_section_begin|>",
    "<|tool_calls_section_end|>",
)
_LLM_NATIVE_REGEX = re.compile(
    "|".join(re.escape(tok) for tok in _LLM_NATIVE_TOKENS)
)
_LLM_XML_TOOL_REGEX = re.compile(
    r"<tool_call>.*?</tool_call>", re.DOTALL
)


def _sanitize_llm_output(text: str) -> str:
    if not text:
        return text
    text = _LLM_NATIVE_REGEX.sub("", text)
    text = _LLM_XML_TOOL_REGEX.sub("", text)
    return text


# ══════════════════════════════════════════════════════════════════
# 🛡️ BORNES DE TAILLE
# ══════════════════════════════════════════════════════════════════
def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        val = int(os.getenv(name, str(default)))
        return max(minimum, val)
    except (TypeError, ValueError):
        return default


HISTORY_WINDOW = _env_int("BEK_CHAT_HISTORY_WINDOW", 6, minimum=1)
MAX_CHARS_PER_MESSAGE = _env_int("BEK_CHAT_MAX_CHARS_PER_MSG", 8000, minimum=200)
MAX_TOTAL_CHARS = _env_int("BEK_CHAT_MAX_TOTAL_CHARS", 32000, minimum=1000)
MAX_ARCHITECTURE_CHARS = _env_int("BEK_CHAT_MAX_ARCHITECTURE_CHARS", 15000, minimum=500)


# ══════════════════════════════════════════════════════════════════
# 🧠 CHARGEMENT DE L'ARCHITECTURE BEK-v16
# ══════════════════════════════════════════════════════════════════
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
                logger.info(
                    "[Archi] Contexte chargé : %s (%d chars)",
                    candidate, len(content),
                )
                return content
        except Exception as exc:
            logger.warning("[Archi] Lecture échouée %s : %s", candidate, exc)

    logger.warning(
        "[Archi] Aucun fichier ARCHITECTURE.md trouvé dans %s.",
        [str(c) for c in _ARCHITECTURE_CANDIDATES],
    )
    return ""


_ARCHITECTURE_CONTEXT: str = _load_architecture_context()


def get_architecture_context() -> str:
    return _ARCHITECTURE_CONTEXT


# ══════════════════════════════════════════════════════════════════
# 🛡️ UTILITAIRES DE BORNAGE
# ══════════════════════════════════════════════════════════════════
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


# ── COUCHE INTELLIGENCE ADDITIVE (legacy) ──
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

# ── COUCHE AGI (nerfs du Chantier 6) ──
try:
    from nerves.router_nerves import route_semantic as _agi_route_semantic
    _AGI_ROUTER_OK = True
except Exception as _router_err:
    logger.debug("Nerf 7 (SmartRouter AGI) non chargé : %s", _router_err)
    _agi_route_semantic = None
    _AGI_ROUTER_OK = False

try:
    from nerves.event_bus_nerves import publish_event_unified as _agi_publish_event
    _AGI_EVENT_BUS_OK = True
except Exception as _eb_err:
    logger.debug("Nerf 3 (EventBus unifié) non chargé : %s", _eb_err)
    _agi_publish_event = None
    _AGI_EVENT_BUS_OK = False

try:
    from nerves.cognitive_nerves import run_cognitive_pipeline as _agi_cognitive_pipeline
    _AGI_COGNITIVE_OK = True
except Exception as _cog_err:
    logger.debug("Nerf 2 (Pipeline cognitif) non chargé : %s", _cog_err)
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
# 🧠 PROMPT SYSTÈME
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

# POUVOIRS SYSTÈME ET ACCÈS TERMINAL
- Tu disposes d'un accès TOTAL au système local.
- Accès au terminal, Git, Neon DB, Pinecone.
- INTERDICTION d'affirmer "Je n'ai pas accès à Internet".
- EXÉCUTE DIRECTEMENT via les outils dédiés les actions demandées.

# DIRECTIVES CONVERSATIONNELLES
- Parle naturellement et brièvement. Pas de bavardage.
- Salutations : réponds en une seule phrase courte.

# EXÉCUTION D'OUTILS & ACTIONS (RÈGLE STRICTE)
- DÈS QUE l'utilisateur demande une action, N'ATTENDS PAS.
- INTERDICTION de demander la permission.
- Renvoie UNIQUEMENT la balise [ACTION:nom]{{"param":"v"}}[/ACTION].

# 🚫 FORMAT DE SORTIE DES ACTIONS (RÈGLE ABSOLUE)
- N'UTILISE JAMAIS de tokens spéciaux comme <|tool_call_begin|>,
  <|tool_call_end|>, <|tool_call|>, <tool_call> ou tout autre format
  natif de LLM.
- TU DOIS utiliser EXCLUSIVEMENT le format :
      [ACTION:nom]{{"param":"valeur"}}[/ACTION]
- Aucun autre format ne sera reconnu par le runtime.
- Si tu ne peux pas utiliser ce format exact, réponds en texte normal
  sans tenter d'appeler un outil.

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

# 🌐 RÈGLE DE SÉLECTION D'OUTIL WEB (CRITIQUE) :
- URL explicite dans la demande (ex. "scrape https://...") → utiliser :
      [ACTION:headless_scrape]{{"url": "https://..."}}[/ACTION]
- Recherche Google/Bing (ex. "cherche X sur le web") → utiliser :
      [ACTION:headless_search]{{"query": "..."}}[/ACTION]
- Extraction d'emails/contacts d'une page → utiliser :
      [ACTION:headless_scrape]{{"url": "https://..."}}[/ACTION]
- Veille approfondie multi-sources avec rapport (ex. "fais une veille sur X") → utiliser :
      [ACTION:web_sync]{{"query": "..."}}[/ACTION]
- INTERDICTION ABSOLUE d'utiliser [ACTION:web_sync] quand une URL explicite
  (http:// ou https://) est fournie dans la demande. Utilise headless_scrape.

# DIRECTIVE MULTIMÉDIA ABSOLUE (PRIORITÉ MAXIMALE) :
- Pour TOUTE demande de création, génération ou modification visuelle (photo, image, portrait, caricature, dessin, illustration, vidéo, animation) :
- INTERDICTION ABSOLUE d'utiliser [ACTION:orchestrate] ou [ACTION:web_sync].
- Ne fais AUCUNE recherche Web et ne rédige AUCUN rapport d'ingénierie.
- Déclenche IMMÉDIATEMENT l'action directe correspondante : generate_image, edit_image, generate_video ou edit_video.
{_ARCHITECTURE_BLOCK}
"""


def _detect_user_response(query: str) -> str:
    if not query:
        return "neutral"
    q = query.lower().strip()
    agreed = {
        "oui", "yes", "ok", "okay", "vasy", "vas-y",
        "go", "d'accord", "ouais", "y", "o", "fine"
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
        logger.error("Erreur directe Vision (%s) : %s", act_name, exc)
        return {"status": "error", "message": f"Erreur multimédia : {exc}"}

    # ── Outils web : headless_scrape / headless_search ──
    if act_name == "headless_scrape":
        url = params.get("url") or params.get("query") or ""
        if not url:
            return {"status": "error", "message": "URL manquante pour headless_scrape"}
        try:
            from worker_headless import HeadlessWorker
            from nerves._async_utils import run_async_safely
            logger.info("[headless_scrape] Démarrage : %s", url)
            worker = HeadlessWorker(headless=True)
            result = run_async_safely(worker.fetch_page_content(url))
            if result is None:
                logger.warning(
                    "[headless_scrape] fetch_page_content → None pour %s",
                    url,
                )
                return {
                    "status": "error",
                    "message": (
                        f"headless_scrape : impossible de charger {url}. "
                        f"Vérifie que Playwright est bien installé "
                        f"(`playwright install chromium`)."
                    ),
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
        try:
            from nerves.headless_nerves import _handler_headless_search
            return _handler_headless_search(query=query)
        except Exception as exc:
            logger.error("Erreur headless_search : %s", exc, exc_info=True)
            return {"status": "error", "message": f"headless_search échoué : {exc}"}

    # ── Fallback : Hermes / CRM executor ──
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


def _format_execution_result(act_name: str, exec_res: dict) -> str:
    if not isinstance(exec_res, dict):
        return str(exec_res)

    # ── Images / Vidéos ──
    fn = exec_res.get("filename", "")
    if exec_res.get("status") == "success" and fn:
        if any(fn.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]):
            return f"🎨 **Image générée !**\n\n![{fn}](/api/download/{fn})"
        elif any(fn.lower().endswith(ext) for ext in [".mp4", ".webm", ".mov", ".avi"]):
            return f"🎬 **Vidéo générée !**\n\n[Télécharger la vidéo](/api/download/{fn})\n\n"

    # ── headless_scrape : extraction texte via BeautifulSoup ──
    if act_name == "headless_scrape":
        if exec_res.get("status") == "success":
            url = exec_res.get("url", "")
            title = exec_res.get("title", "")
            html = exec_res.get("html", "") or ""

            # Extraire le texte brut via BeautifulSoup
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "noscript", "meta", "link"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
            except ImportError:
                logger.warning("bs4 non installé → fallback HTML brut")
                text = html  # fallback si bs4 absent

            # Nettoie les lignes vides multiples
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            text = "\n".join(lines)

            preview = text[:4000]
            return (
                f"✅ **Scraping réussi** : {url}\n"
                f"- Titre : **{title}**\n"
                f"- Contenu extrait : {len(text)} chars\n\n"
                f"**Contenu textuel** :\n```\n{preview}\n```\n"
                f"→ Analyse ce contenu et donne à l'utilisateur "
                f"ce qu'il a demandé (titres, liens, emails, etc.)."
            )
        else:
            return exec_res.get("message", "❌ headless_scrape a échoué")

    # ── headless_search ──
    if act_name == "headless_search":
        return exec_res.get("message") or str(exec_res)

    # ── Fallback ──
    return exec_res.get("message", "Opération OK")


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

    # ══════════════════════════════════════════════════════════════════
    # 🧠 NERF 7 — SMARTROUTER SÉMANTIQUE RÉEL
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # 🌉 NERF 3 — EVENTBUS UNIFIÉ
    # ══════════════════════════════════════════════════════════════════
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
                logger.debug("[EventBus AGI] Échec, fallback legacy : %s", e)

        if not published and event_bus:
            try:
                event_bus.publish("web-cleaned", {"query": last_user_query})
            except Exception:
                pass

    # ── Slash command ──
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

    # ── Human-in-the-Loop (agreed / refused uniquement) ──
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
                        if len(res_msg) > 1500:
                            res_msg = res_msg[:1500] + "\n... [tronqué]"
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

            # Sinon (user_status == "neutral") :
            # Ne rien faire. L'utilisateur fait une nouvelle requête,
            # on n'annule PAS l'action précédente et on traite
            # normalement le nouveau message.

    # ── Prompt système dynamique ──
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

    # ══════════════════════════════════════════════════════════════════
    # 🌊 STREAMING
    # ══════════════════════════════════════════════════════════════════
    async def generate_proxy():
        full_text_accumulated = []
        action_detected = False

        try:
            for item in provider_manager.execute_chat_stream(
                messages=exec_messages,
                provider=provider,
                model=model,
                temperature=0.7,
                max_tokens=4096,
            ):
                if "chunk" in item:
                    chunk = item["chunk"]

                    # ── Sanitizer : retire les tokens natifs LLM ──
                    chunk = _sanitize_llm_output(chunk)

                    if not chunk.strip():
                        continue

                    full_text_accumulated.append(chunk)
                    current_text = "".join(full_text_accumulated)

                    if "[ACTION:" in current_text:
                        action_detected = True

                    j_chunk = json.dumps({'chunk': chunk}, ensure_ascii=False)
                    yield f"data: {j_chunk}\n\n"

                    if action_detected and "[/ACTION]" in current_text:
                        try:
                            action_matches = list(ACTION_REGEX.finditer(current_text))

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

                                msg_imm = '\n\n⚙️ *Exécution...*\n'
                                j_imm = json.dumps({'chunk': msg_imm})
                                yield f"data: {j_imm}\n\n"

                                exec_res = _execute_action_unified(act_name, params)
                                res_msg = _format_execution_result(act_name, exec_res)

                                eval_r = evaluate_response_quality(last_user_query, res_msg)
                                if not eval_r["passed"]:
                                    res_msg = f"⚠️ [BEK Guard] Filtré : {eval_r['reason']}"

                                j_res = json.dumps({'chunk': f'\n\n{res_msg}\n'})
                                yield f"data: {j_res}\n\n"
                        except Exception as e:
                            logger.error("Erreur exécution : %s", e)
                            j_err = json.dumps({'chunk': f'\n⚠️ Erreur : {e}\n'})
                            yield f"data: {j_err}\n\n"
                        break

            full_text = "".join(full_text_accumulated)
            set_span_attribute("chat.response_len", len(full_text))

            # ── NERF 2 — PIPELINE COGNITIF POST-STREAM ──
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
                    logger.debug("[Chat] Cognitive pipeline échec silencieux : %s", cog_exc)

            # ── Quality gate ResponseQuality + auto-correction ──
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
                            j_msg = json.dumps({'chunk': msg_corr})
                            yield f"data: {j_msg}\n\n"

                            for i in range(0, len(corrected_text), 24):
                                c_part = corrected_text[i:i + 24]
                                yield f"data: {json.dumps({'chunk': c_part})}\n\n"
                except Exception as qe:
                    logger.warning("[QualityGate] Échec : %s", qe)

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as stream_err:
            logger.error("[Stream Error] %s", stream_err)
            j_serr = json.dumps({'chunk': f'\n\n⚠️ Flux Error : {stream_err}'})
            yield f"data: {j_serr}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate_proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )