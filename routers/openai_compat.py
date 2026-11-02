# -*- coding: utf-8 -*-
"""
BEK v16 Hybrid — Adaptateur OpenAI-compatible
-----------------------------------------------------------------
Expose /v1/chat/completions et /v1/models au format OpenAI.
★ v18.10.10 (2026-10-24) : Fix I/O Overhead (lru_cache sur env.txt)
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import AsyncIterator, List, Optional

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("BEKApp.OpenAICompat")
router = APIRouter(tags=["OpenAI Compat"])

_ENV_TXT_PATH = Path(__file__).resolve().parent.parent / "env.txt"

@lru_cache(maxsize=1)
def _read_env_txt() -> dict:
    """Lit env.txt une seule fois et met en cache."""
    values = {}
    if not _ENV_TXT_PATH.exists():
        return values
    try:
        with open(_ENV_TXT_PATH, "r", encoding="utf-8-sig", errors="replace") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    except Exception as exc:
        logger.warning("[OpenAI Compat] Lecture env.txt échouée : %s", exc)
    return values

def _get_env(key: str, default: str = "") -> str:
    if key in os.environ and os.environ[key]:
        return os.environ[key]
    return _read_env_txt().get(key, default)

def _verify_api_key(request: Request) -> Optional[JSONResponse]:
    expected_token = _get_env("BEK_OPENAI_API_KEY", "").strip()
    if not expected_token:
        logger.warning("[OpenAI Compat] ⚠️ BEK_OPENAI_API_KEY non configuré → route NON protégée")
        return None
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": {"message": "Missing Authorization", "type": "invalid_request_error"}})
    token = auth_header.split(" ", 1)[1].strip()
    if token != expected_token:
        return JSONResponse(status_code=401, content={"error": {"message": "Invalid API key", "type": "invalid_request_error"}})
    return None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "bek-v16-hybrid"
    messages: List[ChatMessage]
    stream: Optional[bool] = True
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None

def _openai_chunk(content: str, model: str, finish_reason=None) -> str:
    payload = {
        "id": "chatcmpl-bek", "object": "chat.completion.chunk", "created": 0, "model": model,
        "choices": [{"index": 0, "delta": {"content": content} if content else {}, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

@router.get("/v1/models")
async def list_models(request: Request):
    auth_error = _verify_api_key(request)
    if auth_error: return auth_error
    return {"object": "list", "data": [{"id": "bek-v16-hybrid", "object": "model", "created": 0, "owned_by": "bek"}]}

@router.post("/v1/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest):
    auth_error = _verify_api_key(request)
    if auth_error: return auth_error
    
    base_url = str(request.base_url).rstrip("/")
    internal_url = f"{base_url}/api/chat"
    formatted_messages = [{"role": m.role, "content": m.content} for m in body.messages]

    async def stream_openai() -> AsyncIterator[str]:
        yield _openai_chunk("", body.model)
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST", internal_url,
                    json={"messages": formatted_messages, "provider": "nvidia", "model": "nvidia/nemotron-3.5-super-vl-120b-a12b"},
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status_code != 200:
                        yield _openai_chunk(f"[Erreur BEK {response.status_code}]", body.model)
                        yield _openai_chunk("", body.model, finish_reason="stop")
                        yield "data: [DONE]\n\n"
                        return
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"): continue
                        try: payload = json.loads(line[len("data:"):].strip())
                        except json.JSONDecodeError: continue
                        if "chunk" in payload: yield _openai_chunk(payload["chunk"], body.model)
                        elif payload.get("done") is True:
                            yield _openai_chunk("", body.model, finish_reason="stop")
                            yield "data: [DONE]\n\n"
                            return
        except httpx.RequestError as exc:
            yield _openai_chunk(f"[Erreur réseau : {exc}]", body.model)
            yield _openai_chunk("", body.model, finish_reason="stop")
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_openai(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})