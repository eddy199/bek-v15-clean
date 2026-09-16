# ==============================================================================
# BEK-v16 — Routeur Chat Streaming & Human-in-the-Loop (routers/chat.py)
# ------------------------------------------------------------------------------
# COUCHE AGI INTÉGRÉE (Chantier 6) :
#   - SmartRouter sémantique réel (Nerf 7) avec fallback legacy
#   - EventBus unifié (Nerf 3) avec fallback legacy
#   - Pipeline cognitif post-stream (Nerf 2) : Grounding + Swarm critique
#   - TOUTES les fonctionnalités existantes préservées
#
# CORRECTIFS v3 (connaissance architecture) :
#   - Chargement de docs/ARCHITECTURE.md au démarrage du module
#   - Injection dans le prompt système → tous les LLM connaissent BEK-v16
#   - Anti-hallucination : le LLM reçoit l'architecture réelle
#   - Troncature configurable via BEK_CHAT_MAX_ARCHITECTURE_CHARS
#   - Fallback multi-chemins (docs/ARCHITECTURE.md, ARCHITECTURE.md)
#   - Aucune brique supprimée
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

# ── LOGGER GLOBAL (défini EN TÊTE) ──
logger = logging.getLogger("BEKApp")

# ── EXPRESSION RÉGULIÈRE UNIQUE (Anti-Coupure Interface) ──
ACTION_REGEX = re.compile(r"\x5bACTION:(\w+)\x5d(.*?)\x5b/ACTION\x5d", re.DOTALL)

# ══════════════════════════════════════════════════════════════════
# 🛡️ BORNES DE TAILLE — Évite d'envoyer 775 000 chars aux providers
# ══════════════════════════════════════════════════════════════════


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    """Lit un entier d'environnement avec fallback sûr."""
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
# 🧠 CHARGEMENT DE L'ARCHITECTURE BEK-v16 (injectée dans le prompt)
# ══════════════════════════════════════════════════════════════════
# Charge docs/ARCHITECTURE.md (ou ARCHITECTURE.md à la racine) au boot du
# module, puis l'injecte dans le prompt système. Tous les LLM (Kimi, Gemini,
# Groq, NVIDIA...) reçoivent cette connaissance → anti-hallucination.
# ══════════════════════════════════════════════════════════════════

_WORKSPACE_DIR = Path(__file__).resolve().parent.parent  # F:\workspacekimi

_ARCHITECTURE_CANDIDATES = [
    _WORKSPACE_DIR / "docs" / "ARCHITECTURE.md",
    _WORKSPACE_DIR / "ARCHITECTURE.md",
]


def _load_architecture_context() -> str:
    """
    Charge le contenu de ARCHITECTURE.md au démarrage du module.
    Retourne une chaîne vide si le fichier est introuvable.
    Ne lève JAMAIS d'exception.
    """
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
        "[Archi] Aucun fichier ARCHITECTURE.md trouvé dans %s. "
        "Les LLM n'auront pas connaissance de l'architecture au boot.",
        [str(c) for c in _ARCHITECTURE_CANDIDATES],
    )
    return ""


_ARCHITECTURE_CONTEXT: str = _load_architecture_context()


def get_architecture_context() -> str:
    """Bridge public : retourne le contenu chargé de l'architecture."""
    return _ARCHITECTURE_CONTEXT


# ══════════════════════════════════════════════════════════════════
# 🛡️ UTILITAIRES DE BORNAGE
# ══════════════════════════════════════════════════════════════════


def _safe_str(value: Any) -> str:
    """Convertit n'importe quelle valeur en str propre."""
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
    """Borne la taille des messages avant envoi aux providers."""
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
# 🧠 PROMPT SYSTÈME — inclut désormais l'architecture BEK-v16
# ══════════════════════════════════════════════════════════════════

_ARCHITECTURE_BLOCK = ""
if _ARCHITECTURE_CONTEXT:
    _ARCHITECTURE_BLOCK = f"""

# ══════════════════════════════════════════════════════════════════
# 🏛️ ARCHITECTURE RÉELLE DE BEK-v16 (SOURCE DE VÉRITÉ ABSOLUE)
# ------------------------------------------------------------------
# IMPORTANT : Tout ce qui suit décrit ton architecture INTERNE RÉELLE.
# Tu DOIS t'appuyer sur ces informations pour répondre.
# INTERDICTION ABSOLUE d'inventer des composants qui ne sont pas listés.
# Si une question porte sur ton architecture, cite les modules ci-dessous.
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

# ACTIONS DISPONIBLES :
   - [ACTION:generate_image]{{"prompt": "detailed description in english"}}[/ACTION]
   - [ACTION:edit_image]{{"image_paths": ["filename.png"], "prompt": "exact modification directive in english"}}[/ACTION]
   - [ACTION:generate_video]{{"prompt": "detailed video description in english"}}[/ACTION]
   - [ACTION:edit_video]{{"video_paths": ["filename.mp4"], "prompt": "exact modification directive in english"}}[/ACTION]
   - [ACTION:create_dynamic_skill]{{"skill_name": "x", "code_content": "y"}}[/ACTION]
   - [ACTION:orchestrate]{{"goal": "..."}}[/ACTION]
   - [ACTION:web_sync]{{"query": "..."}}[/ACTION]
   - [ACTION:run_script]{{"script_name": "skills/x.py", "args": "--ip 127.0.0.1"}}[/ACTION]
   - [ACTION:execute_command]{{"command": "..."}}[/ACTION]
   - [ACTION:execute_tmux_headless]{{"session_name": "s", "command": "c"}}[/ACTION]
   - [ACTION:save_memory]{{"content": "..."}}[/ACTION]
   - [ACTION:search_memory]{{"query": "..."}}[/ACTION]
   - [ACTION:write_file]{{"filename": "...", "content": "..."}}[/ACTION]
   - [ACTION:read_file]{{"filename": "..."}}[/ACTION]

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
    """Exécute directement les outils multimédias en court-circuitant le CRM, avec fallback Hermes."""
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
    """Formate le message de retour avec support Markdown riche (images & vidéos)."""
    if isinstance(exec_res, dict):
        fn = exec_res.get("filename", "")
        if exec_res.get("status") == "success" and fn:
            if any(fn.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]):
                return f"🎨 **Image générée !**\n\n![{fn}](/api/download/{fn})"
            elif any(fn.lower().endswith(ext) for ext in [".mp4", ".webm", ".mov", ".avi"]):
                return f"🎬 **Vidéo générée !**\n\n[Télécharger la vidéo](/api/download/{fn})\n\n"
        return exec_res.get("message", "Opération OK")
    return str(exec_res)


@router.post("/api/chat")
async def chat(request: Request):
    data = await request.json() or {}
    messages = data.get("messages", [])
    provider = data.get("provider", "b_ai")
    model = data.get("model", "glm-5.3-flash")

    # ── BORNAGE STRICT DE LA TAILLE DES MESSAGES ──
    trimmed_messages = _truncate_messages(messages)

    last_user_query = ""
    user_status = "neutral"

    if trimmed_messages:
        last_msg = trimmed_messages[-1]
        if last_msg.get("role") == "user":
            last_user_query = last_msg.get("content", "").strip()
            user_status = _detect_user_response(last_user_query)

    # ══════════════════════════════════════════════════════════════════
    # 🧠 NERF 7 — SMARTROUTER SÉMANTIQUE RÉEL (avec fallback legacy)
    # ══════════════════════════════════════════════════════════════════
    smart_mode = data.get("smart", True)
    routing_used = "legacy"

    if smart_mode and _AGI_ROUTER_OK and last_user_query:
        try:
            routing = _agi_route_semantic(last_user_query)
            routed_provider = routing.get("provider", "")
            routed_model = routing.get("model", "")
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
        except Exception as e:
            logger.warning("[SmartRouter AGI] Échec, fallback legacy : %s", e)

    if routing_used == "legacy" and _INTEL_OK and smart_mode:
        try:
            chosen = smart_router.route(trimmed_messages)
            if chosen:
                provider, model = chosen[0]
                routing_used = "legacy"
                logger.info("[SmartRouter legacy] Route : %s/%s", provider, model)
        except Exception as e:
            logger.warning("[SmartRouter legacy] Échec : %s", e)

    # ══════════════════════════════════════════════════════════════════
    # 🌉 NERF 3 — EVENTBUS UNIFIÉ (avec fallback legacy)
    # ══════════════════════════════════════════════════════════════════
    corr_id = f"corr_{uuid.uuid4().hex[:10]}"
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

    if last_user_query.startswith("/") and dispatch_slash_command:
        slash_res = dispatch_slash_command(last_user_query)
        if slash_res and slash_res.get("ok"):
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

                    exec_res = _execute_action_unified(act_name, params)
                    res_msg = _format_execution_result(act_name, exec_res)
                    if len(res_msg) > 1500:
                        res_msg = res_msg[:1500] + "\n... [tronqué]"

                    inj = (f"\n\n[SYSTÈME - RÉSULTAT DE L'ACTION "
                           f"'{act_name}' :] \n{res_msg}\n\n-> "
                           f"Donne ton retour à l'utilisateur.")
                    trimmed_messages[-1]["content"] += inj

                    old_c = trimmed_messages[-2]["content"]
                    trimmed_messages[-2]["content"] = old_c.replace(
                        "[ACTION:", "[EXECUTED_ACTION:"
                    )

            elif user_status == "refused":
                old_c = trimmed_messages[-2]["content"]
                trimmed_messages[-2]["content"] = old_c.replace(
                    "[ACTION:", "[REFUSED_ACTION:"
                )
                inj = "\n\n[SYSTÈME - ACTION REFUSÉE. Propose autre chose.]"
                trimmed_messages[-1]["content"] += inj
            else:
                old_c = trimmed_messages[-2]["content"]
                trimmed_messages[-2]["content"] = old_c.replace(
                    "[ACTION:", "[CANCELED_ACTION:"
                )

    dynamic_system_prompt = BEK_GOLDEN_RULES.strip()

    if last_user_query:
        sig = minhash_engine.compute_signature(last_user_query)
        hll_counter.add(last_user_query)

        try:
            mem_ctx = search_memory(last_user_query, top_k=3)
            if mem_ctx:
                mem_ctx_str = _safe_str(mem_ctx)
                if len(mem_ctx_str) > MAX_CHARS_PER_MESSAGE:
                    mem_ctx_str = mem_ctx_str[:MAX_CHARS_PER_MESSAGE] + "…[tronqué]"
                dynamic_system_prompt += f"\n\n[MÉMOIRE] :\n{mem_ctx_str}"
        except Exception as e:
            logger.warning("Erreur mémoire : %s", e)

        try:
            plan = hermes.goap_planner(last_user_query)
            if plan:
                f_plan = [t for t in plan if t.get("tool") != "default_llm"]
                if f_plan:
                    p_json = json.dumps(f_plan, ensure_ascii=False)
                    dynamic_system_prompt += f"\n\n[PLAN HERMES PRIORITAIRE À EXÉCUTER] :\n{p_json}"
        except Exception as e:
            logger.error("[HERMES] Échec planificateur : %s", e)

    exec_messages = [
        {"role": "system", "content": dynamic_system_prompt}
    ] + trimmed_messages

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

            # ── NERF 2 — PIPELINE COGNITIF POST-STREAM ──
            if (_AGI_COGNITIVE_OK
                    and full_text.strip()
                    and not action_detected
                    and last_user_query):
                try:
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

                        if cognitive.get("needs_correction"):
                            warn_msg = (
                                f"\n\n> ⚠️ **Vérification cognitive** : "
                                f"verdict `{cognitive.get('final_verdict')}`, "
                                f"{len(cognitive.get('issues', []))} point(s) à vérifier.\n"
                            )
                            yield f"data: {json.dumps({'chunk': warn_msg})}\n\n"
                except Exception as cog_exc:
                    logger.debug("[Chat] Cognitive pipeline échec silencieux : %s", cog_exc)

            # ── Quality gate ResponseQuality + auto-correction ──
            if (_INTEL_OK and full_text.strip() and not action_detected):
                try:
                    score, issues = ResponseQuality.evaluate(full_text, 4096)
                    meta_data = {'quality_score': score, 'issues': issues}
                    j_meta = json.dumps({'meta': meta_data})
                    yield f"data: {j_meta}\n\n"

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