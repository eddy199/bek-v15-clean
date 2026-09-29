# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Routeur Chat (Orchestrateur) — v18.2
# ------------------------------------------------------------------------------
# v18.2 (2026-09-29) : Integration HINDSIGHT (memoire long-terme structuree)
#   - Ajout hindsight_build_context() en parallele de Pinecone
#   - Le contexte Hindsight est fusionne dans le prompt systeme
# ==============================================================================

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from hermes_core import hermes
from memory import search_memory
from services.tasks import CURRENT_OS_NAME

from .chat_modules import config as cfg
from .chat_modules import prompts as pr
from .chat_modules import validation as val
from .chat_modules import formatters as fmt
from .chat_modules import routing as rt
from .chat_modules import streaming as st

# ★ v18.2 — HINDSIGHT
try:
    from hindsight_memory import (
        hindsight_build_context,
        hindsight_status as _hindsight_status,
    )
    _HINDSIGHT_AVAILABLE = True
except ImportError as _e:
    _HINDSIGHT_AVAILABLE = False
    def hindsight_build_context(q, max_results=3): return ""
    def _hindsight_status(): return {"enabled": False, "connected": False}

logger = logging.getLogger("BEKApp")

cfg.init_bek_lvc()

# OPENTELEMETRY (optionnel)
try:
    from core.tracing import (
        span, set_span_attribute, set_span_status_ok,
        set_span_status_error, get_current_trace_id,
    )
    _TRACING_OK = True
except Exception:
    _TRACING_OK = False
    from contextlib import contextmanager

    @contextmanager
    def span(name, **attrs): yield None
    def set_span_attribute(k, v): pass
    def set_span_status_ok(): pass
    def set_span_status_error(msg=""): pass
    def get_current_trace_id(): return ""


router = APIRouter(tags=["Chat"])


@router.post("/api/chat")
async def chat(request: Request):
    with span("chat.request") as chat_span:
        return await _chat_impl(request, chat_span)


async def _chat_impl(request: Request, chat_span):
    # ─── 1. LECTURE ───
    data = await request.json() or {}
    messages = data.get("messages", [])
    provider = data.get("provider", "nvidia")
    model = data.get("model", "nvidia/nemotron-3-super-120b-a12b")

    set_span_attribute("chat.messages_count", len(messages) if isinstance(messages, list) else 0)
    set_span_attribute("chat.provider", provider)
    set_span_attribute("chat.model", model)

    trace_id = get_current_trace_id()
    if trace_id:
        logger.info("[Chat] trace_id=%s provider=%s model=%s", trace_id, provider, model)

    # ─── 2. TRONCATURE ───
    trimmed_messages = val._truncate_messages(messages)
    set_span_attribute("chat.trimmed_count", len(trimmed_messages))

    # ─── 3. DERNIÈRE REQUÊTE ───
    last_user_query = ""
    user_status = "neutral"

    if trimmed_messages:
        last_msg = trimmed_messages[-1]
        if last_msg.get("role") == "user":
            last_user_query = last_msg.get("content", "").strip()
            user_status = val._detect_user_response(last_user_query)
            set_span_attribute("chat.user_query_len", len(last_user_query))

    # ─── 4. ROUTING ───
    routing_used = "bek_rex"
    set_span_attribute("chat.routing_used", routing_used)

    # ─── 5. EVENTBUS ───
    if last_user_query:
        try:
            from event_bus import EventBusKafka
            event_bus = EventBusKafka()
            event_bus.publish("web-cleaned", {"query": last_user_query})
        except Exception:
            pass

    # ─── 6. SLASH ───
    if last_user_query.startswith("/"):
        try:
            from skills import dispatch_command as dispatch_slash_command
            slash_res = dispatch_slash_command(last_user_query)
            if slash_res and slash_res.get("ok"):
                async def generate_slash():
                    j_out = json.dumps({'chunk': slash_res['output']})
                    yield f"data: {j_out}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                return StreamingResponse(
                    generate_slash(), media_type="text/event-stream",
                )
        except Exception as e:
            logger.debug("[SlashCommand] Échec : %s", e)

    # ─── 7. MÉMOIRE (Pinecone + Hindsight en parallèle) ───
    dynamic_system_prompt = pr.BEK_GOLDEN_RULES.strip()

    if last_user_query:
        # 7a. Pinecone (mémoire vectorielle classique)
        try:
            mem_ctx = search_memory(last_user_query, top_k=3)
            if mem_ctx:
                mem_ctx_str = val._safe_str(mem_ctx)
                if len(mem_ctx_str) > cfg.MAX_CHARS_PER_MESSAGE:
                    mem_ctx_str = mem_ctx_str[:cfg.MAX_CHARS_PER_MESSAGE] + "…[tronqué]"
                dynamic_system_prompt += f"\n\n[MÉMOIRE PINECONE] :\n{mem_ctx_str}"
        except Exception as e:
            logger.warning("Erreur mémoire Pinecone : %s", e)

        # ★ 7b. Hindsight (mémoire long-terme structurée)
        if _HINDSIGHT_AVAILABLE:
            try:
                hindsight_ctx = hindsight_build_context(last_user_query, max_results=3)
                if hindsight_ctx:
                    if len(hindsight_ctx) > cfg.MAX_CHARS_PER_MESSAGE:
                        hindsight_ctx = hindsight_ctx[:cfg.MAX_CHARS_PER_MESSAGE] + "…[tronqué]"
                    dynamic_system_prompt += f"\n\n[MÉMOIRE HINDSIGHT] :\n{hindsight_ctx}"
                    logger.info("[Chat] Contexte Hindsight fusionné (%d chars)", len(hindsight_ctx))
                else:
                    logger.debug("[Chat] Hindsight : aucun contexte trouvé")
            except Exception as e:
                logger.warning("Erreur mémoire Hindsight : %s", e)

        # 7c. Plan Hermes
        try:
            plan = hermes.goap_planner(last_user_query)
            if plan:
                f_plan = [t for t in plan if t.get("tool") != "default_llm"]
                if f_plan:
                    p_json = json.dumps(f_plan, ensure_ascii=False)
                    dynamic_system_prompt += (
                        f"\n\n[PLAN HERMES PRIORITAIRE À EXÉCUTER] :\n{p_json}"
                    )
        except Exception as e:
            logger.error("[HERMES] Échec planificateur : %s", e)

    # ─── 8. MESSAGES ───
    exec_messages = [
        {"role": "system", "content": dynamic_system_prompt},
    ] + trimmed_messages

    # ─── 9. STREAMING ───
    return StreamingResponse(
        st.stream_chat(
            exec_messages=exec_messages,
            trimmed_messages=trimmed_messages,
            last_user_query=last_user_query,
            provider=provider,
            model=model,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/chat/debug")
async def chat_debug():
    return {
        "status": "ok",
        "version": "18.2",
        "config": cfg.get_config_summary(),
        "prompts": pr.get_prompt_summary(),
        "validation": val.get_validation_summary(),
        "formatters": fmt.get_formatters_summary(),
        "routing": rt.get_routing_summary(),
        "stair": st.get_stair_summary(),
        "streaming": st.get_streaming_summary(),
        "hindsight": _hindsight_status(),
    }