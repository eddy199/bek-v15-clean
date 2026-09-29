# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Module d'integration HINDSIGHT (memoire long-terme) — v1.2
# ==============================================================================
# v1.2 (2026-09-29) :
#   - Ajout hindsight_close() pour fermer le client proprement
#   - Ajout hindsight_retain_conversation() : mémorise un échange user/agent
#   - Ajout hindsight_build_context() : formate le contexte pour le prompt
# ==============================================================================
from __future__ import annotations

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
        logger.warning("[Hindsight] Module 'hindsight-client' non installe : %s", exc)
        return None
    except Exception as exc:
        logger.error("[Hindsight] Echec initialisation client : %s", exc)
        return None


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
        results: List[Dict[str, Any]] = []
        raw_results = getattr(response, "results", None) or []
        for r in raw_results:
            text = getattr(r, "text", "") or ""
            score = getattr(r, "score", 0.0) or 0.0
            metadata = getattr(r, "metadata", {}) or {}
            if text:
                results.append({"text": text, "score": score, "metadata": metadata})
        logger.info("[Hindsight] recall OK | %d resultats", len(results))
        return results
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


def hindsight_retain_conversation(
    user_message: str,
    agent_response: str,
    context: Optional[str] = None,
) -> bool:
    """
    v1.2 : memorise un echange user/agent en une seule operation.
    Format : "L'utilisateur a demande: X. L'agent a repondu: Y."
    """
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
            f"Echange de conversation :\n"
            f"- L'utilisateur a demande : {user_message}\n"
            f"- L'agent a repondu : {agent_response[:500]}"
        )

    return hindsight_retain(content, context=context or "conversation")


def hindsight_build_context(query: str, max_results: int = 3) -> str:
    """
    v1.2 : rappelle les memoires et les formate en bloc texte pour le system prompt.
    Retourne "" si aucune memoire.
    """
    results = hindsight_recall(query)
    if not results:
        return ""

    lines = []
    for r in results[:max_results]:
        text = r.get("text", "").strip()
        if text:
            lines.append(f"- {text}")

    if not lines:
        return ""

    return "\n".join(lines)


def hindsight_close() -> None:
    """
    v1.2 : ferme proprement le client Hindsight (evite les warnings asyncio).
    """
    global _CLIENT, _CLIENT_INIT_DONE
    if _CLIENT is None:
        return
    try:
        close_method = getattr(_CLIENT, "close", None)
        if callable(close_method):
            close_method()
        _CLIENT = None
        _CLIENT_INIT_DONE = False
        logger.info("[Hindsight] Client ferme proprement.")
    except Exception as exc:
        logger.debug("[Hindsight] Erreur fermeture client : %s", exc)


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

    print("\n=== Etat Hindsight ===")
    for k, v in hindsight_status().items():
        print(f"   {k} = {v}")

    print("\n=== TEST 1 : retain_conversation ===")
    ok = hindsight_retain_conversation(
        "Qui suis-je ?",
        "Vous etes Eddy, un developpeur Python.",
    )
    print(f"   Retain : {'OK' if ok else 'ECHEC'}")

    print("\n=== TEST 2 : build_context ===")
    ctx = hindsight_build_context("Qui est Eddy ?")
    print(f"   Contexte : {ctx[:200] if ctx else '(vide)'}")

    print("\n=== TEST 3 : reflect ===")
    answer = hindsight_reflect("Que sais-tu de moi ?")
    print(f"   Reponse : {answer[:200] if answer else '(vide)'}")

    hindsight_close()
    print("\nTests termines.\n")