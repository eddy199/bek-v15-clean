# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Routeur Chat (Orchestrateur)
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Orchestrer les modules chat_modules/*
# 📄 Doc : docs/BEK_LVC.md
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 18.1
# Date : 2026-09-28
# ------------------------------------------------------------------------------
# v18.1 : Désactivation SmartRouter AGI (remplacé par BEK-REX dans streaming.py)
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

# ─── Import des modules chat ───
from .chat_modules import config as cfg
from .chat_modules import prompts as pr
from .chat_modules import validation as val
from .chat_modules import formatters as fmt
from .chat_modules import routing as rt
from .chat_modules import streaming as st

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# INITIALISATION BEK-LVC AU BOOT
# ══════════════════════════════════════════════════════════════════════════════

cfg.init_bek_lvc()


# ══════════════════════════════════════════════════════════════════════════════
# OPENTELEMETRY (optionnel)
# ══════════════════════════════════════════════════════════════════════════════

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
    def span(name, **attrs):
        yield None

    def set_span_attribute(k, v): pass
    def set_span_status_ok(): pass
    def set_span_status_error(msg=""): pass
    def get_current_trace_id(): return ""


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════

router = APIRouter(tags=["Chat"])


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/api/chat")
async def chat(request: Request):
    with span("chat.request") as chat_span:
        return await _chat_impl(request, chat_span)


async def _chat_impl(request: Request, chat_span):
    """Implémentation du chat avec orchestration modulaire (v18.1)."""

    # ─── 1. LECTURE DE LA REQUÊTE ───
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

    # ─── 2. TRONCATURE DES MESSAGES ───
    trimmed_messages = val._truncate_messages(messages)
    set_span_attribute("chat.trimmed_count", len(trimmed_messages))

    # ─── 3. EXTRACTION DE LA DERNIÈRE REQUÊTE ───
    last_user_query = ""
    user_status = "neutral"

    if trimmed_messages:
        last_msg = trimmed_messages[-1]
        if last_msg.get("role") == "user":
            last_user_query = last_msg.get("content", "").strip()
            user_status = val._detect_user_response(last_user_query)
            set_span_attribute("chat.user_query_len", len(last_user_query))

    # ─── 4. ROUTING : géré par BEK-REX dans streaming.py (v18.1) ───
    # Le SmartRouter AGI a été désactivé car redondant avec BEK-REX.
    # Le routage fin (TIER_0 → TIER_4) se fait maintenant automatiquement
    # dans st.stream_chat() via BEK-REX.
    routing_used = "bek_rex"
    set_span_attribute("chat.routing_used", routing_used)

    # ─── 5. EVENTBUS (optionnel) ───
    if last_user_query:
        try:
            from event_bus import EventBusKafka
            event_bus = EventBusKafka()
            event_bus.publish("web-cleaned", {"query": last_user_query})
        except Exception:
            pass

    # ─── 6. COMMANDES SLASH ───
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

    # ─── 7. MÉMOIRE + PLAN HERMES ───
    dynamic_system_prompt = pr.BEK_GOLDEN_RULES.strip()

    if last_user_query:
        # Mémoire Pinecone
        try:
            mem_ctx = search_memory(last_user_query, top_k=3)
            if mem_ctx:
                mem_ctx_str = val._safe_str(mem_ctx)
                if len(mem_ctx_str) > cfg.MAX_CHARS_PER_MESSAGE:
                    mem_ctx_str = mem_ctx_str[:cfg.MAX_CHARS_PER_MESSAGE] + "…[tronqué]"
                dynamic_system_prompt += f"\n\n[MÉMOIRE] :\n{mem_ctx_str}"
        except Exception as e:
            logger.warning("Erreur mémoire : %s", e)

        # Plan Hermes
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

    # ─── 8. CONSTRUCTION DES MESSAGES ───
    exec_messages = [
        {"role": "system", "content": dynamic_system_prompt},
    ] + trimmed_messages

    # ─── 9. STREAMING (pipeline v1.3 avec les 4 leviers) ───
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


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE DEBUG
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/api/chat/debug")
async def chat_debug():
    """Endpoint de debug pour vérifier la configuration."""
    return {
        "status": "ok",
        "version": "18.1",
        "config": cfg.get_config_summary(),
        "prompts": pr.get_prompt_summary(),
        "validation": val.get_validation_summary(),
        "formatters": fmt.get_formatters_summary(),
        "routing": rt.get_routing_summary(),
        "stair": st.get_stair_summary(),
        "streaming": st.get_streaming_summary(),
    }