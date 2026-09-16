# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 4 — WEB AGENT RELIÉ À L'EVENTBUS (nerves/web_agent_nerves.py)
# ------------------------------------------------------------------------------
# Ce nerf branche web_agent.py (WebAgent) sur l'EventBus unifié (Nerf 3) :
#
#   NERF 4 : WebAgent → EventBus (traçabilité A2A de chaque scrape)
#
# NOUVEAUX OUTILS HERMES (additifs) :
#   - web_agent_traced   → run_pipeline() AVEC traçabilité EventBus
#   - web_agent_scrape   → scrape une URL spécifique AVEC traçabilité
#
# BRIDGES EXPOSÉS :
#   - scrape_and_trace(url)   → utilisable par d'autres briques
#   - pipeline_and_trace(q)   → wrapper public tracé
#
# CORRECTIONS vs VERSION INITIALE :
#   - Utilise publish_event_unified (Kafka + Async simultanés, Nerf 3)
#   - Aucun thread manuel (le pool borné du Nerf 3 gère)
#   - correlation_id propagé de bout en bout
#   - Fallback silencieux si WebAgent ou EventBus indisponible
#   - Préserve la signature originale de run_pipeline()
#
# RÈGLES D'OR :
#   - Aucune modification de web_agent.py
#   - Aucune modification de hermes_core.py
#   - Feature-flag : BEK_ENABLE_WEB_AGENT_NERVES (défaut true)
#   - Ne bloque JAMAIS le flux principal
# ==============================================================================

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger("bek.nerves.web_agent")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_WEB_AGENT_NERVES", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# PUBLICATION EVENTBUS — utilise le pont unifié du Nerf 3
# ------------------------------------------------------------------------------

def _publish_traced_event(
    topic: str,
    action: str,
    correlation_id: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Publie un événement sur l'EventBus unifié (Kafka + Async simultanés).
    Ne lève JAMAIS d'exception.
    """
    payload: Dict[str, Any] = {
        "action": action,
        "correlation_id": correlation_id,
        "source": "web_agent_nerves",
    }
    if extra:
        payload.update(extra)

    try:
        # Essayer le pont unifié du Nerf 3
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified(topic, payload)
        logger.debug("[Nerf 4] Événement publié : %s / %s", topic, action)
    except Exception as exc:
        logger.debug("[Nerf 4] Publication EventBus échouée (mode dégradé) : %s", exc)


# ------------------------------------------------------------------------------
# WRAPPERS TRACÉS
# ------------------------------------------------------------------------------

def pipeline_and_trace(query: str = "", **kwargs: Any) -> Dict[str, Any]:
    """
    Wrapper tracé de web_agent_instance.run_pipeline().
    Publie un événement 'web-cleaned' avec corrélation_id à chaque appel.

    Retourne TOUJOURS un dict (jamais d'exception).
    """
    correlation_id = f"web_{uuid.uuid4().hex[:12]}"

    # Trace de départ
    _publish_traced_event(
        topic="web-cleaned",
        action="pipeline_start",
        correlation_id=correlation_id,
        extra={"query": query[:200]},
    )

    try:
        from web_agent import web_agent_instance

        if web_agent_instance is None:
            _publish_traced_event(
                topic="error-signals",
                action="web_agent_unavailable",
                correlation_id=correlation_id,
                extra={"query": query[:200]},
            )
            return {
                "status": "error",
                "correlation_id": correlation_id,
                "message": "WebAgent indisponible.",
            }

        # Appel réel au WebAgent (signature originale préservée)
        report = web_agent_instance.run_pipeline(query)

        # Trace de succès
        _publish_traced_event(
            topic="web-cleaned",
            action="pipeline_done",
            correlation_id=correlation_id,
            extra={
                "query": query[:200],
                "report_length": len(str(report)) if report else 0,
            },
        )

        return {
            "status": "success",
            "correlation_id": correlation_id,
            "report": report,
        }

    except Exception as exc:
        logger.error("[Nerf 4] pipeline_and_trace échoué : %s", exc)
        _publish_traced_event(
            topic="error-signals",
            action="pipeline_error",
            correlation_id=correlation_id,
            extra={"query": query[:200], "error": str(exc)[:300]},
        )
        return {
            "status": "error",
            "correlation_id": correlation_id,
            "message": f"WebAgent échoué : {exc}",
        }


def scrape_and_trace(url: str = "", max_chars: int = 5000, **kwargs: Any) -> Dict[str, Any]:
    """
    Wrapper tracé de WebAgent.scrape_url_deep().
    Publie un événement 'web-cleaned' avec corrélation_id à chaque scrape.

    Retourne TOUJOURS un dict (jamais d'exception).
    """
    correlation_id = f"scrape_{uuid.uuid4().hex[:12]}"

    if not url:
        return {
            "status": "error",
            "correlation_id": correlation_id,
            "message": "L'URL est obligatoire.",
        }

    # Trace de départ
    _publish_traced_event(
        topic="web-cleaned",
        action="scrape_start",
        correlation_id=correlation_id,
        extra={"url": url[:300]},
    )

    try:
        from web_agent import web_agent_instance

        if web_agent_instance is None:
            return {
                "status": "error",
                "correlation_id": correlation_id,
                "message": "WebAgent indisponible.",
            }

        # Appel réel au WebAgent (méthode existante)
        result = web_agent_instance.scrape_url_deep(url, max_chars=max_chars)

        # Trace de succès
        _publish_traced_event(
            topic="web-cleaned",
            action="scrape_done",
            correlation_id=correlation_id,
            extra={
                "url": url[:300],
                "content_length": len(result.get("content", "")) if isinstance(result, dict) else 0,
                "error": result.get("error") if isinstance(result, dict) else None,
            },
        )

        return {
            "status": "success",
            "correlation_id": correlation_id,
            "result": result,
        }

    except Exception as exc:
        logger.error("[Nerf 4] scrape_and_trace échoué : %s", exc)
        _publish_traced_event(
            topic="error-signals",
            action="scrape_error",
            correlation_id=correlation_id,
            extra={"url": url[:300], "error": str(exc)[:300]},
        )
        return {
            "status": "error",
            "correlation_id": correlation_id,
            "message": f"Scrape échoué : {exc}",
        }


# ------------------------------------------------------------------------------
# HANDLERS HERMES — wrappers fins autour des fonctions tracées
# ------------------------------------------------------------------------------

def _handler_web_agent_traced(query: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : web_agent_traced → pipeline_and_trace()."""
    if not query:
        return {"status": "error", "message": "La requête est vide."}
    return pipeline_and_trace(query=query, **kwargs)


def _handler_web_agent_scrape(url: str = "", max_chars: int = 5000, **kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : web_agent_scrape → scrape_and_trace()."""
    if not url:
        return {"status": "error", "message": "L'URL est vide."}
    return scrape_and_trace(url=url, max_chars=max_chars, **kwargs)


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE
# ------------------------------------------------------------------------------

WEB_AGENT_NERVES_TABLE: Dict[str, tuple] = {
    "web_agent_traced": (_handler_web_agent_traced, "L3"),
    "web_agent_scrape": (_handler_web_agent_scrape, "L2"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_web_agent_nerves() -> Dict[str, Any]:
    """
    Active les nerfs WebAgent en enregistrant 2 nouveaux outils tracés dans Hermes.

    Idempotent. Feature-flag BEK_ENABLE_WEB_AGENT_NERVES.

    Retourne un rapport d'activation structuré.
    """
    if not _is_enabled():
        logger.warning("[Nerf 4] Désactivé via BEK_ENABLE_WEB_AGENT_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_WEB_AGENT_NERVES=false",
        }

    # Vérification de la disponibilité du WebAgent
    web_agent_available = False
    try:
        from web_agent import web_agent_instance
        web_agent_available = web_agent_instance is not None
    except ImportError as exc:
        logger.warning(
            "⚠️ [Nerf 4] web_agent.py indisponible (%s). "
            "Les outils seront enregistrés mais échoueront à l'exécution.",
            exc,
        )

    # Vérification de la disponibilité du pont EventBus (Nerf 3)
    event_bus_available = False
    try:
        from nerves.event_bus_nerves import get_event_bus_bridge
        bridge = get_event_bus_bridge()
        event_bus_available = bridge.get_status().get("activated", False)
    except Exception:
        event_bus_available = False

    try:
        from hermes_core import hermes
    except ImportError as exc:
        logger.error("[Nerf 4] Impossible d'importer hermes_core : %s", exc)
        return {"status": "error", "message": str(exc)}

    activated = []
    failed = []

    for tool_name, (handler, risk_level) in WEB_AGENT_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("🧠 [Nerf 4] Outil WebAgent tracé branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 4] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 4] Activation terminée : %d outils tracés branchés, %d échecs. "
        "WebAgent disponible : %s | EventBus pont actif : %s",
        len(activated), len(failed), web_agent_available, event_bus_available,
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "web_agent_available": web_agent_available,
        "event_bus_bridge_active": event_bus_available,
        "bridges_exposed": ["pipeline_and_trace", "scrape_and_trace"],
    }


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_web_agent_nerves()
    print("Résultat activation Nerf 4 :", result)