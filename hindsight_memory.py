# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Module d'integration HINDSIGHT — v1.3 (async + sync)
# ==============================================================================
# v1.3 (2026-09-29) :
#   - Ajout hindsight_recall_async() pour usage dans FastAPI
#   - Ajout hindsight_reflect_async() pour usage dans FastAPI
#   - Le code sync reste pour les scripts standalone
# ==============================================================================
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.hindsight")


def _env(key: str, default: str = "") -> str:
    val = os.environ.get(key, "").strip()
    if val:
        return val
    try:
        from env_loader import load_env
        load_env()
        val = os.environ.get(key, "").strip()
        if val:
            return val
    except Exception:
        pass
    return default


def _env_bool(key: str, default: bool = True) -> bool:
    v = _env(key, "").lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


HINDSIGHT_ENABLED = _env_bool("BEK_HINDSIGHT_ENABLED", True)
HINDSIGHT_BASE_URL = _env("HINDSIGHT_BASE_URL", "http://localhost:8888")
HINDSIGHT_API_KEY = _env("HINDSIGHT_API_KEY", "")
HINDSIGHT_BANK_ID = _env("HINDSIGHT_BANK_ID", "bek-agent")


_CLIENT = None
_CLIENT_INIT_DONE = False


def _get_client():
    global _CLIENT, _CLIENT_INIT_DONE
    if _CLIENT_INIT_DONE:
        return _CLIENT
    _CLIENT_INIT_DONE = True

    if not HINDSIGHT_ENABLED:
        logger.info("[Hindsight] Desactive via BEK_HINDSIGHT_ENABLED=false")
        return None

    try:
        from hindsight_client import Hindsight
        kwargs: Dict[str, Any] = {"base_url": HINDSIGHT_BASE_URL}
        if HINDSIGHT_API_KEY:
            kwargs["api_key"] = HINDSIGHT_API_KEY
        _CLIENT = Hindsight(**kwargs)
        logger.info(
            "[Hindsight] Client initialise | base_url=%s | bank_id=%s",
            HINDSIGHT_BASE_URL, HINDSIGHT_BANK_ID,
        )
        return _CLIENT
    except ImportError as exc:
        logger.warning("[Hindsight] Module non installe : %s", exc)
        return None
    except Exception as exc:
        logger.error("[Hindsight] Echec initialisation : %s", exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# VERSION SYNC (pour scripts standalone)
# ══════════════════════════════════════════════════════════════════════════════

def hindsight_retain(content: str, context: Optional[str] = None) -> bool:
    if not content or not content.strip():
        return False
    client = _get_client()
    if client is None:
        return False
    try:
        client.retain(
            bank_id=HINDSIGHT_BANK_ID,
            content=content,
            context=context or "conversation",
            retain_async=False,
        )
        logger.info("[Hindsight] retain OK | %d chars", len(content))
        return True
    except Exception as exc:
        logger.warning("[Hindsight] retain echec : %s", exc)
        return False


def hindsight_recall(query: str, max_tokens: int = 4096, budget: str = "mid") -> List[Dict[str, Any]]:
    """Version SYNC — ne pas utiliser depuis FastAPI (event loop)."""
    if not query or not query.strip():
        return []
    client = _get_client()
    if client is None:
        return []
    try:
        response = client.recall(
            bank_id=HINDSIGHT_BANK_ID,
            query=query,
            budget=budget,
            max_tokens=max_tokens,
        )
        return _parse_recall_response(response)
    except Exception as exc:
        logger.warning("[Hindsight] recall echec : %s", exc)
        return []


def hindsight_reflect(query: str, budget: str = "low") -> str:
    if not query or not query.strip():
        return ""
    client = _get_client()
    if client is None:
        return ""
    try:
        response = client.reflect(
            bank_id=HINDSIGHT_BANK_ID,
            query=query,
            budget=budget,
        )
        text = getattr(response, "text", "") or ""
        logger.info("[Hindsight] reflect OK | %d chars", len(text))
        return text
    except Exception as exc:
        logger.warning("[Hindsight] reflect echec : %s", exc)
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# VERSION ASYNC (pour FastAPI)
# ══════════════════════════════════════════════════════════════════════════════

def _parse_recall_response(response) -> List[Dict[str, Any]]:
    """Parse la réponse RecallResponse."""
    results: List[Dict[str, Any]] = []
    raw_results = getattr(response, "results", None) or []
    for r in raw_results:
        text = getattr(r, "text", "") or ""
        score = getattr(r, "score", 0.0) or 0.0
        metadata = getattr(r, "metadata", {}) or {}
        if text:
            results.append({"text": text, "score": score, "metadata": metadata})
    return results


async def hindsight_recall_async(
    query: str,
    max_tokens: int = 4096,
    budget: str = "mid",
) -> List[Dict[str, Any]]:
    """Version ASYNC — utilise arecall() pour FastAPI."""
    if not query or not query.strip():
        return []
    client = _get_client()
    if client is None:
        return []
    try:
        # arecall() retourne une coroutine
        response = await client.arecall(
            bank_id=HINDSIGHT_BANK_ID,
            query=query,
            budget=budget,
            max_tokens=max_tokens,
        )
        results = _parse_recall_response(response)
        logger.info("[Hindsight] arecall OK | %d resultats", len(results))
        return results
    except Exception as exc:
        logger.warning("[Hindsight] arecall echec : %s", exc)
        return []


async def hindsight_reflect_async(query: str, budget: str = "low") -> str:
    """Version ASYNC — utilise areflect()."""
    if not query or not query.strip():
        return ""
    client = _get_client()
    if client is None:
        return ""
    try:
        response = await client.areflect(
            bank_id=HINDSIGHT_BANK_ID,
            query=query,
            budget=budget,
        )
        text = getattr(response, "text", "") or ""
        logger.info("[Hindsight] areflect OK | %d chars", len(text))
        return text
    except Exception as exc:
        logger.warning("[Hindsight] areflect echec : %s", exc)
        return ""


async def hindsight_retain_async(
    content: str,
    context: Optional[str] = None,
) -> bool:
    """Version ASYNC de retain."""
    if not content or not content.strip():
        return False
    client = _get_client()
    if client is None:
        return False
    try:
        await client.aretain(
            bank_id=HINDSIGHT_BANK_ID,
            content=content,
            context=context or "conversation",
        )
        return True
    except Exception as exc:
        logger.warning("[Hindsight] aretain echec : %s", exc)
        return False


def hindsight_retain_conversation(
    user_message: str,
    agent_response: str,
    context: Optional[str] = None,
) -> bool:
    if not user_message and not agent_response:
        return False
    user_message = (user_message or "").strip()
    agent_response = (agent_response or "").strip()
    if not agent_response:
        content = f"L'utilisateur a dit : {user_message}"
    elif not user_message:
        content = f"L'agent a repondu : {agent_response[:500]}"
    else:
        content = (
            f"Echange : user = {user_message} | agent = {agent_response[:500]}"
        )
    return hindsight_retain(content, context=context or "conversation")


def hindsight_build_context(query: str, max_results: int = 3) -> str:
    results = hindsight_recall(query)
    if not results:
        return ""
    lines = []
    for r in results[:max_results]:
        text = r.get("text", "").strip()
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines)


def hindsight_close() -> None:
    global _CLIENT, _CLIENT_INIT_DONE
    if _CLIENT is None:
        return
    try:
        close_method = getattr(_CLIENT, "close", None)
        if callable(close_method):
            close_method()
        _CLIENT = None
        _CLIENT_INIT_DONE = False
    except Exception:
        pass


def hindsight_status() -> Dict[str, Any]:
    client = _get_client()
    return {
        "enabled": HINDSIGHT_ENABLED,
        "connected": client is not None,
        "base_url": HINDSIGHT_BASE_URL,
        "bank_id": HINDSIGHT_BANK_ID,
        "api_key_set": bool(HINDSIGHT_API_KEY),
    }


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    async def _test_async():
        print("\n=== TEST ASYNC ===")
        results = await hindsight_recall_async("Qui est Eddy ?")
        print(f"recall_async : {len(results)} resultats")

    print("\n=== Etat Hindsight ===")
    for k, v in hindsight_status().items():
        print(f"   {k} = {v}")

    # Test sync
    print("\n=== TEST SYNC (retain) ===")
    ok = hindsight_retain("Test sync BEK", context="test")
    print(f"retain sync : {'OK' if ok else 'ECHEC'}")

    # Test async
    asyncio.run(_test_async())

    hindsight_close()
    print("\nTests termines.\n")