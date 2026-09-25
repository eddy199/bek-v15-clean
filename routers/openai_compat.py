# -*- coding: utf-8 -*-
"""
BEK v16 Hybrid — Adaptateur OpenAI-compatible
-----------------------------------------------------------------
Expose /v1/chat/completions et /v1/models au format OpenAI,
en traduisant vers le routeur /api/chat interne de BEK.

Permet à DeepSeek Harness (DSH), LangChain, Cursor, etc.
de parler à BEK comme à n'importe quelle API OpenAI.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator, List, Optional

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("BEKApp.OpenAICompat")

router = APIRouter(tags=["OpenAI Compat"])


# ═══════════════════════════════════════════════════════════════
# MODÈLES PYDANTIC (format OpenAI)
# ═══════════════════════════════════════════════════════════════
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "bek-v16-hybrid"
    messages: List[ChatMessage]
    stream: Optional[bool] = True
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def _extract_last_user_message(messages: List[ChatMessage]) -> str:
    """Prend le dernier message utilisateur et le renvoie comme string."""
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    # Fallback : concatène tout
    return "\n".join(m.content for m in messages if m.role == "user")


def _openai_chunk(content: str, model: str, finish_reason=None) -> str:
    """Construit un chunk SSE au format OpenAI."""
    payload = {
        "id": "chatcmpl-bek",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ═══════════════════════════════════════════════════════════════
# ROUTE : /v1/models
# ═══════════════════════════════════════════════════════════════
@router.get("/v1/models")
async def list_models():
    """Liste les modèles exposés par BEK au format OpenAI."""
    return {
        "object": "list",
        "data": [
            {
                "id": "bek-v16-hybrid",
                "object": "model",
                "created": 0,
                "owned_by": "bek",
            },
            {
                "id": "deepseek-v4.1-flash",
                "object": "model",
                "created": 0,
                "owned_by": "bek",
            },
        ],
    }


# ═══════════════════════════════════════════════════════════════
# ROUTE : /v1/chat/completions
# ═══════════════════════════════════════════════════════════════
@router.post("/v1/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest):
    """
    Endpoint OpenAI-compatible.
    Traduit la requête en appel interne vers /api/chat de BEK,
    puis convertit le flux SSE BEK vers le format OpenAI.
    """
    user_message = _extract_last_user_message(body.messages)
    logger.info(
        "[OpenAI Compat] model=%s, user_message=%r, stream=%s",
        body.model, user_message[:80], body.stream,
    )

    # Construction de l'URL interne — on appelle notre propre /api/chat
    # via HTTP loopback pour ne pas dupliquer la logique du routeur chat.
    base_url = str(request.base_url).rstrip("/")
    internal_url = f"{base_url}/api/chat"

    async def stream_openai() -> AsyncIterator[str]:
        # 1. Chunk initial vide (OpenAI en envoie souvent un)
        yield _openai_chunk("", body.model)

        try:
            # 2. Appel au routeur /api/chat interne en streaming
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    internal_url,
                    json={"message": user_message},
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status_code != 200:
                        err_body = await response.aread()
                        logger.error(
                            "[OpenAI Compat] /api/chat a renvoyé %s : %s",
                            response.status_code, err_body[:200],
                        )
                        yield _openai_chunk(
                            f"[Erreur BEK {response.status_code}]", body.model
                        )
                        yield _openai_chunk("", body.model, finish_reason="stop")
                        yield "data: [DONE]\n\n"
                        return

                    # 3. Lecture ligne par ligne du flux SSE BEK
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        payload_str = line[len("data:"):].strip()
                        if not payload_str:
                            continue
                        try:
                            payload = json.loads(payload_str)
                        except json.JSONDecodeError:
                            continue

                        # Format BEK : {"chunk": "..."} → on relaie le texte
                        if "chunk" in payload:
                            yield _openai_chunk(payload["chunk"], body.model)

                        # Format BEK : {"done": true} → on termine proprement
                        elif payload.get("done") is True:
                            yield _openai_chunk("", body.model, finish_reason="stop")
                            yield "data: [DONE]\n\n"
                            return

                        # Format BEK : {"meta": ...} → on ignore (pas standard OpenAI)
                        # Sinon on ignore silencieusement

        except httpx.RequestError as exc:
            logger.error("[OpenAI Compat] Erreur réseau vers /api/chat : %s", exc)
            yield _openai_chunk(f"[Erreur réseau : {exc}]", body.model)
            yield _openai_chunk("", body.model, finish_reason="stop")
            yield "data: [DONE]\n\n"

    # Si stream=False, on pourrait agréger, mais DSH utilise stream=True
    return StreamingResponse(
        stream_openai(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )