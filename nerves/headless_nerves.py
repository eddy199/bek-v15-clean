# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 11+12+13 — HEADLESS RELIÉ AU CERVEAU (nerves/headless_nerves.py)
# ★ v18.16 — Intégration LVC-Web (clean_html_to_text)
# ★ FIX #2 — Import local de clean_html_to_text (plus de couplage au boot)
# ==============================================================================

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List

from nerves._async_utils import run_async_safely

# ★ FIX #2 : Plus d'import top-level de clean_html_to_text.
# L'import se fait dans les handlers qui en ont besoin.

logger = logging.getLogger("bek.nerves.headless")

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_HEADLESS_NERVES", "true").lower() in ("true", "1", "yes")

def _publish_event(topic: str, payload: Dict[str, Any]) -> None:
    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified(topic, payload)
        return
    except Exception:
        pass
    try:
        from event_bus import EventBusKafka
        bus = EventBusKafka()
        bus.publish(topic, payload)
    except Exception:
        pass

def _run_async_safely(coro):
    return run_async_safely(coro)

# ------------------------------------------------------------------------------
# HANDLERS RÉELS
# ------------------------------------------------------------------------------

def _handler_headless_search(query: str = "", limit: int = 5, **kwargs: Any) -> Dict[str, Any]:
    if not query:
        return {"status": "error", "message": "La requête de recherche est vide."}

    try:
        from worker_headless import HeadlessWorker
        worker = HeadlessWorker(headless=True, timeout_ms=30000)
        leads = run_async_safely(worker.search_and_extract_leads(query, limit=limit))

        _publish_event("web-cleaned", {"action": "headless_search", "query": query, "results_count": len(leads) if isinstance(leads, list) else 0})

        return {
            "status": "success",
            "query": query,
            "count": len(leads) if isinstance(leads, list) else 0,
            "leads": leads or [],
        }
    except Exception as exc:
        logger.error("[Nerf 11] headless_search échoué : %s", exc)
        return {"status": "error", "message": f"headless_search échoué : {exc}"}

def _handler_headless_extract_leads(query: str = "", limit: int = 5, **kwargs: Any) -> Dict[str, Any]:
    return _handler_headless_search(query=query, limit=limit, **kwargs)

def _handler_headless_render(url: str = "", **kwargs: Any) -> Dict[str, Any]:
    if not url:
        return {"status": "error", "message": "L'URL est obligatoire pour headless_render."}

    try:
        # ★ FIX #2 : import local de clean_html_to_text
        from worker_headless import HeadlessWorker, clean_html_to_text
        worker = HeadlessWorker(headless=True, timeout_ms=30000)
        result = run_async_safely(worker.fetch_page_content(url))

        if not isinstance(result, dict):
            result = {"status": "error", "message": "Rendu invalide (non-dict)."}

        # ★ LVC-WEB : Nettoyage du HTML pour économiser les tokens
        if result.get("status") == "success" and "html" in result:
            clean_text = clean_html_to_text(result["html"], max_chars=2500)
            result["text"] = clean_text
            del result["html"]  # On supprime le HTML brut

        _publish_event("web-cleaned", {
            "action": "headless_render",
            "url": url,
            "status": result.get("status", "unknown"),
            "content_length": len(result.get("text", "")),
        })

        return result or {"status": "error", "message": "Rendu vide."}
    except Exception as exc:
        logger.error("[Nerf 11] headless_render échoué : %s", exc)
        return {"status": "error", "message": f"headless_render échoué : {exc}"}

def headless_scrape_for_web_agent(url: str) -> str:
    try:
        # ★ FIX #2 : import local de clean_html_to_text
        from worker_headless import HeadlessWorker, clean_html_to_text
        worker = HeadlessWorker(headless=True, timeout_ms=30000)
        result = run_async_safely(worker.fetch_page_content(url))
        if isinstance(result, dict) and result.get("status") == "success":
            return clean_html_to_text(result.get("html", ""), max_chars=5000)
        return ""
    except Exception as exc:
        logger.debug("[Nerf 12] headless_scrape_for_web_agent échoué : %s", exc)
        return ""

HEADLESS_NERVES_TABLE: Dict[str, tuple] = {
    "headless_search":        (_handler_headless_search,        "L2"),
    "headless_extract_leads": (_handler_headless_extract_leads, "L2"),
    "headless_render":        (_handler_headless_render,        "L2"),
}

def activate_headless_nerves() -> Dict[str, Any]:
    if not _is_enabled():
        return {"status": "disabled", "reason": "Feature-flag"}

    playwright_available = False
    try:
        from playwright.async_api import async_playwright
        playwright_available = True
    except ImportError:
        logger.warning("⚠️ [Nerf 11-13] Playwright non installé.")

    event_bus_bridge_active = False
    try:
        from nerves.event_bus_nerves import get_event_bus_bridge
        bridge = get_event_bus_bridge()
        event_bus_bridge_active = bridge.get_status().get("activated", False)
    except Exception:
        pass

    try:
        from hermes_core import hermes
    except ImportError as exc:
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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(activate_headless_nerves())