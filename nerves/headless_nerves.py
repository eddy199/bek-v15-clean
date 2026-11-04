# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 11+12+13 — HEADLESS RELIÉ AU CERVEAU (nerves/headless_nerves.py)
# ------------------------------------------------------------------------------
# Ce nerf enrichit le système nerveux BEK en branchant worker_headless.py
# (Playwright) sur :
#
#   NERF 11 : Hermes        → 3 nouveaux outils headless_* enregistrés
#   NERF 12 : WebAgent      → pont pour scraper les sites JS-lourd (via bridge)
#   NERF 13 : EventBus      → traçabilité A2A de chaque scrape (via Nerf 3)
#
# NOUVEAUX OUTILS HERMES (additifs) :
#   - headless_search           → recherche DuckDuckGo Lite + extraction HTML rendu
#   - headless_extract_leads    → extraction de prospects (noms, emails) via headless
#   - headless_render           → rendu JS complet d'une page (alternative à headless_scrape)
#
# RÈGLES D'OR :
#   - Aucune modification de worker_headless.py
#   - Aucune modification de web_agent.py
#   - Aucune modification de hermes_core.py
#   - On utilise UNIQUEMENT les API publiques existantes
#   - Feature-flag : BEK_ENABLE_HEADLESS_NERVES (défaut true)
#   - Fallback silencieux si Playwright indisponible
#
# CORRECTIFS v3 (factorisation async) :
#   - Utilise nerves._async_utils.run_async_safely() (module partagé)
#   - _run_async_safely() conservée en dépréciation douce (compat imports)
#   - Utilise publish_event_unified (pont Nerf 3) au lieu de EventBusKafka direct
#   - Fallback legacy EventBusKafka si le pont Nerf 3 est indisponible
#   - Garde-fou sur result non-dict dans headless_render
#   - Regex HTML plus robuste dans headless_scrape_for_web_agent
#   - Aucune signature modifiée : compatibilité totale avec les autres nerfs
# ==============================================================================

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List

# ── Utilitaire async partagé (module nerves/_async_utils.py) ──
from nerves._async_utils import run_async_safely

logger = logging.getLogger("bek.nerves.headless")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    """Vérifie si le Nerf 11-13 est activé (par défaut : oui)."""
    return os.getenv("BEK_ENABLE_HEADLESS_NERVES", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# PONT EVENTBUS — publication silencieuse via le pont unifié du Nerf 3
# ------------------------------------------------------------------------------

def _publish_event(topic: str, payload: Dict[str, Any]) -> None:
    """
    Publie un événement sur l'EventBus unifié (Kafka + Async simultanés).

    - Priorité : pont unifié du Nerf 3 (évite les doublons).
    - Fallback : EventBusKafka direct (mode dégradé legacy).
    - Ne lève JAMAIS d'exception.
    """
    # 1. Tentative via le pont unifié du Nerf 3
    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified(topic, payload)
        logger.debug("[Nerf 13] Événement publié (pont unifié) : %s", topic)
        return
    except Exception as exc:
        logger.debug("[Nerf 13] Pont unifié indisponible : %s", exc)

    # 2. Fallback legacy : EventBusKafka direct
    try:
        from event_bus import EventBusKafka
        bus = EventBusKafka()
        bus.publish(topic, payload)
        logger.debug("[Nerf 13] Événement publié (legacy Kafka) : %s", topic)
    except Exception as exc:
        logger.debug("[Nerf 13] EventBus indisponible (mode dégradé) : %s", exc)


# ------------------------------------------------------------------------------
# COMPAT — Ancienne fonction conservée (dépréciation douce)
# ------------------------------------------------------------------------------

def _run_async_safely(coro):
    """
    DÉPRÉCIÉ : utilise désormais nerves._async_utils.run_async_safely().

    Conservée uniquement pour compatibilité avec d'éventuels imports externes.
    Délègue directement au module partagé.
    """
    return run_async_safely(coro)


# ------------------------------------------------------------------------------
# HANDLERS RÉELS — appellent worker_headless.HeadlessWorker
# ------------------------------------------------------------------------------

def _handler_headless_search(query: str = "", limit: int = 5, **kwargs: Any) -> Dict[str, Any]:
    """
    Nerf 11 : Recherche via HeadlessWorker (DuckDuckGo Lite rendu en JS).
    Retourne une liste de leads structurés (nom, email, source_url, snippet).
    """
    if not query:
        return {"status": "error", "message": "La requête de recherche est vide."}

    try:
        from worker_headless import HeadlessWorker

        worker = HeadlessWorker(headless=True, timeout_ms=30000)
        leads = run_async_safely(worker.search_and_extract_leads(query, limit=limit))

        # Traçabilité A2A
        _publish_event(
            "web-cleaned",
            {
                "action": "headless_search",
                "query": query,
                "results_count": len(leads) if isinstance(leads, list) else 0,
            },
        )

        return {
            "status": "success",
            "query": query,
            "count": len(leads) if isinstance(leads, list) else 0,
            "leads": leads or [],
        }
    except Exception as exc:
        logger.error("[Nerf 11] headless_search échoué : %s", exc)
        return {"status": "error", "message": f"headless_search échoué : {exc}"}


def _handler_headless_extract_leads(
    query: str = "",
    limit: int = 5,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Nerf 11 : Extraction de prospects via headless (noms, emails).
    Alias sémantique de headless_search pour usage CRM.
    """
    return _handler_headless_search(query=query, limit=limit, **kwargs)


def _handler_headless_render(url: str = "", **kwargs: Any) -> Dict[str, Any]:
    """
    Nerf 11 : Rendu JS complet d'une page (alternative à headless_scrape).
    Retourne le HTML complet rendu + statut HTTP + durée.
    """
    if not url:
        return {"status": "error", "message": "L'URL est obligatoire pour headless_render."}

    try:
        from worker_headless import HeadlessWorker

        worker = HeadlessWorker(headless=True, timeout_ms=30000)
        result = run_async_safely(worker.fetch_page_content(url))

        # Garde-fou : si le résultat n'est pas un dict, on renvoie un statut propre
        if not isinstance(result, dict):
            result = {"status": "error", "message": "Rendu invalide (non-dict)."}

        # Traçabilité A2A
        _publish_event(
            "web-cleaned",
            {
                "action": "headless_render",
                "url": url,
                "status": result.get("status", "unknown"),
                "content_length": result.get("content_length", 0),
            },
        )

        return result or {"status": "error", "message": "Rendu vide."}
    except Exception as exc:
        logger.error("[Nerf 11] headless_render échoué : %s", exc)
        return {"status": "error", "message": f"headless_render échoué : {exc}"}


# ------------------------------------------------------------------------------
# BRIDGE WEBAGENT (Nerf 12) — API exposable pour WebAgent
# ------------------------------------------------------------------------------

def headless_scrape_for_web_agent(url: str) -> str:
    """
    Nerf 12 : Fonction bridge que WebAgent (ou tout autre brique) peut appeler
    pour obtenir le texte d'une page rendue en JS.

    Retourne un texte plat (utile pour alimenter un LLM).
    Ne lève jamais d'exception.
    """
    try:
        from worker_headless import HeadlessWorker
        worker = HeadlessWorker(headless=True, timeout_ms=30000)
        result = run_async_safely(worker.fetch_page_content(url))

        if isinstance(result, dict) and result.get("status") == "success":
            html = result.get("html", "")
            # Extraction texte simple (sans dépendance BS4)
            # Regex plus robustes : exclut correctement script/style complets
            text = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", html,
                          flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style\b[^>]*>.*?</style\s*>", "", text,
                          flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:5000]
        return ""
    except Exception as exc:
        logger.debug("[Nerf 12] headless_scrape_for_web_agent échoué : %s", exc)
        return ""


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE
# ------------------------------------------------------------------------------

HEADLESS_NERVES_TABLE: Dict[str, tuple] = {
    "headless_search":        (_handler_headless_search,        "L2"),
    "headless_extract_leads": (_handler_headless_extract_leads, "L2"),
    "headless_render":        (_handler_headless_render,        "L2"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_headless_nerves() -> Dict[str, Any]:
    """
    Active les nerfs Headless en ré-enregistrant 3 outils enrichis dans Hermes.

    Idempotent : peut être appelé plusieurs fois sans effet de bord
    (l'enregistrement écrase simplement l'outil par lui-même).

    Retourne un rapport d'activation structuré.
    """
    if not _is_enabled():
        logger.warning("[Nerf 11-13] Désactivé via BEK_ENABLE_HEADLESS_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_HEADLESS_NERVES=false",
        }

    # Vérification de la disponibilité de Playwright
    playwright_available = False
    try:
        from playwright.async_api import async_playwright  # noqa: F401
        playwright_available = True
    except ImportError:
        logger.warning(
            "⚠️ [Nerf 11-13] Playwright non installé. Les outils headless_* "
            "seront enregistrés mais échoueront à l'exécution. "
            "Installez avec : pip install playwright && playwright install chromium"
        )

    # Vérification de la disponibilité du pont EventBus (Nerf 3)
    event_bus_bridge_active = False
    try:
        from nerves.event_bus_nerves import get_event_bus_bridge
        bridge = get_event_bus_bridge()
        event_bus_bridge_active = bridge.get_status().get("activated", False)
    except Exception:
        event_bus_bridge_active = False

    try:
        from hermes_core import hermes
    except ImportError as exc:
        logger.error("[Nerf 11-13] Impossible d'importer hermes_core : %s", exc)
        return {"status": "error", "message": str(exc)}

    activated: List[str] = []
    failed: List[Dict[str, str]] = []

    for tool_name, (handler, risk_level) in HEADLESS_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("🧠 [Nerf 11] Outil headless branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 11] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 11-13] Activation terminée : %d outils headless branchés, %d échecs. "
        "Playwright disponible : %s | EventBus pont actif : %s",
        len(activated), len(failed), playwright_available, event_bus_bridge_active,
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "playwright_available": playwright_available,
        "event_bus_bridge_active": event_bus_bridge_active,
        "web_agent_bridge": "headless_scrape_for_web_agent",
        "async_utils_module": "nerves._async_utils",
    }


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_headless_nerves()
    print("Résultat activation Nerf 11-13 :", result)