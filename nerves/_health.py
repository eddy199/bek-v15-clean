# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — HEALTH CHECK DU SYSTÈME NERVEUX (nerves/_health.py)
# ------------------------------------------------------------------------------
# Module utilitaire interne au paquet nerves/.
#
# OBJECTIF :
#   Fournir un point d'entrée unique pour connaître l'état de TOUS les nerfs
#   en une seule requête. Utile pour :
#     - Un endpoint FastAPI /health/nerves
#     - Un check de monitoring externe (Render, UptimeRobot, etc.)
#     - Un debug rapide après chaque redéploiement
#
# UTILISATION :
#   from nerves._health import get_all_nerves_status, get_nerves_summary
#
#   # Détail complet
#   report = get_all_nerves_status()
#
#   # Résumé condensé (pour monitoring)
#   summary = get_nerves_summary()
#
# ENDPOINT FASTAPI (à ajouter dans routers/admin.py ou app.py) :
#   from nerves._health import get_nerves_summary
#   @app.get("/health/nerves")
#   async def health_nerves():
#       return get_nerves_summary()
#
# RÈGLES D'OR :
#   - Stdlib uniquement (importlib, logging, os, time)
#   - Ne lève JAMAIS d'exception (chaque check isolé)
#   - Timeout court par check (max 2s)
#   - Purement additif : aucun nerf existant n'est modifié
# ==============================================================================

from __future__ import annotations

import importlib
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("bek.nerves.health")


# ------------------------------------------------------------------------------
# CARTOGRAPHIE DES NERFS
# ------------------------------------------------------------------------------
# Chaque entrée décrit :
#   - module    : nom du module Python dans nerves/
#   - flag      : variable d'environnement du feature-flag
#   - label     : description lisible
#   - has_status: True si le module expose get_status() (pont) ou équivalent
# ------------------------------------------------------------------------------

NERVES_CARTOGRAPHY: Dict[str, Dict[str, Any]] = {
    "hermes_nerves": {
        "module": "nerves.hermes_nerves",
        "flag": "BEK_ENABLE_HERMES_NERVES",
        "label": "Nerf 1 — Hermes outils réels",
        "has_status": False,
    },
    "cognitive_nerves": {
        "module": "nerves.cognitive_nerves",
        "flag": "BEK_ENABLE_COGNITIVE_NERVES",
        "label": "Nerf 2 — Cortex cognitif (Swarm + Grounding)",
        "has_status": False,
    },
    "event_bus_nerves": {
        "module": "nerves.event_bus_nerves",
        "flag": "BEK_ENABLE_EVENT_BUS_NERVES",
        "label": "Nerf 3 — Pont EventBus unifié",
        "has_status": True,   # expose get_event_bus_bridge().get_status()
    },
    "web_agent_nerves": {
        "module": "nerves.web_agent_nerves",
        "flag": "BEK_ENABLE_WEB_AGENT_NERVES",
        "label": "Nerf 4 — WebAgent tracé",
        "has_status": False,
    },
    "approval_nerves": {
        "module": "nerves.approval_nerves",
        "flag": "BEK_ENABLE_APPROVAL_NERVES",
        "label": "Nerf 5 — Approval Manager L3+",
        "has_status": False,
    },
    "mcp_nerves": {
        "module": "nerves.mcp_nerves",
        "flag": "BEK_ENABLE_MCP_NERVES",
        "label": "Nerf 6 — MCP Gateway ↔ Hermes",
        "has_status": False,
    },
    "router_nerves": {
        "module": "nerves.router_nerves",
        "flag": "BEK_ENABLE_ROUTER_NERVES",
        "label": "Nerf 7 — SmartRouter sémantique",
        "has_status": False,
    },
    "skills_nerves": {
        "module": "nerves.skills_nerves",
        "flag": "BEK_ENABLE_SKILLS_NERVES",
        "label": "Nerf 8 — Skills chargés au boot",
        "has_status": False,
    },
    "guardian_nerves": {
        "module": "nerves.guardian_nerves",
        "flag": "BEK_ENABLE_GUARDIAN_NERVES",
        "label": "Nerf 9 — Guardian tracé",
        "has_status": False,
    },
    "headless_nerves": {
        "module": "nerves.headless_nerves",
        "flag": "BEK_ENABLE_HEADLESS_NERVES",
        "label": "Nerf 11-13 — Headless Playwright",
        "has_status": False,
    },
    "tmux_nerves": {
        "module": "nerves.tmux_nerves",
        "flag": "BEK_ENABLE_TMUX_NERVES",
        "label": "Nerf 14-17 — Tmux tâches de fond",
        "has_status": False,
    },
}


# ------------------------------------------------------------------------------
# HELPERS INTERNES
# ------------------------------------------------------------------------------

def _read_flag(flag_name: str, default: str = "true") -> bool:
    """Lit un feature-flag et retourne True si activé."""
    return os.getenv(flag_name, default).lower() in ("true", "1", "yes")


def _check_event_bus_bridge_status() -> Dict[str, Any]:
    """
    Interroge spécifiquement le pont EventBus (Nerf 3) pour son statut complet.
    Ne lève jamais d'exception.
    """
    try:
        from nerves.event_bus_nerves import get_event_bus_bridge
        bridge = get_event_bus_bridge()
        status = bridge.get_status()
        return {
            "status": "ok" if status.get("activated") else "inactive",
            "detail": status,
        }
    except Exception as exc:
        return {
            "status": "error",
            "detail": {"error": str(exc)[:300]},
        }


def _check_one_nerve(nerve_key: str, info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Vérifie l'état d'un nerf donné.

    Étapes :
      1. Vérifie le feature-flag → si désactivé, on retourne "disabled"
      2. Tente d'importer le module → si échec, "error"
      3. Si le nerf expose un statut complet, on l'interroge
      4. Sinon, on se contente du "module importable = ok"

    Ne lève JAMAIS d'exception. Timeout implicite : import + status ≤ 2s.
    """
    started = time.monotonic()
    result: Dict[str, Any] = {
        "label": info["label"],
        "module": info["module"],
        "flag": info["flag"],
        "enabled": False,
        "status": "unknown",
        "detail": {},
        "duration_ms": 0,
    }

    # Étape 1 : feature-flag
    enabled = _read_flag(info["flag"], "true")
    result["enabled"] = enabled
    if not enabled:
        result["status"] = "disabled"
        result["duration_ms"] = int((time.monotonic() - started) * 1000)
        return result

    # Étape 2 : import du module
    try:
        mod = importlib.import_module(info["module"])
    except Exception as exc:
        result["status"] = "error"
        result["detail"] = {"import_error": str(exc)[:300]}
        result["duration_ms"] = int((time.monotonic() - started) * 1000)
        return result

    # Étape 3 : statut spécifique si disponible
    if nerve_key == "event_bus_nerves":
        result["detail"] = _check_event_bus_bridge_status()
        result["status"] = result["detail"].get("status", "unknown")
        result["duration_ms"] = int((time.monotonic() - started) * 1000)
        return result

    # Nerfs sans get_status() : on considère que l'import réussi = "ok"
    # (on ne peut pas savoir s'ils ont été activés sans les rappeler,
    #  ce qui aurait des effets de bord — on reste conservateur)
    result["status"] = "ok"
    result["detail"] = {"note": "Module importable, activation non re-testée."}
    result["duration_ms"] = int((time.monotonic() - started) * 1000)
    return result


# ------------------------------------------------------------------------------
# API PUBLIQUE 1 : RAPPORT DÉTAILLÉ
# ------------------------------------------------------------------------------

def get_all_nerves_status() -> Dict[str, Any]:
    """
    Retourne un rapport détaillé sur tous les nerfs.

    Format :
      {
        "global_status": "ok" | "degraded" | "error",
        "timestamp": float,
        "summary": {"ok": N, "disabled": N, "error": N, "inactive": N},
        "event_bus_bridge": {...},   # raccourci pratique
        "nerves": {
            "hermes_nerves": { ... },
            ...
        }
      }

    Ne lève JAMAIS d'exception.
    """
    started = time.monotonic()
    report: Dict[str, Any] = {
        "global_status": "ok",
        "timestamp": time.time(),
        "summary": {"ok": 0, "disabled": 0, "error": 0, "inactive": 0, "unknown": 0},
        "event_bus_bridge": {},
        "nerves": {},
    }

    # 1. Check du pont EventBus (fondation Nerf 3)
    try:
        report["event_bus_bridge"] = _check_event_bus_bridge_status()
    except Exception as exc:
        report["event_bus_bridge"] = {"status": "error", "detail": {"error": str(exc)[:300]}}

    # 2. Check de chaque nerf
    for nerve_key, info in NERVES_CARTOGRAPHY.items():
        try:
            nerve_status = _check_one_nerve(nerve_key, info)
        except Exception as exc:
            nerve_status = {
                "label": info.get("label", nerve_key),
                "module": info.get("module", ""),
                "flag": info.get("flag", ""),
                "enabled": False,
                "status": "error",
                "detail": {"unexpected_error": str(exc)[:300]},
                "duration_ms": 0,
            }
        report["nerves"][nerve_key] = nerve_status

        # Compteur
        st = nerve_status.get("status", "unknown")
        if st in report["summary"]:
            report["summary"][st] += 1
        else:
            report["summary"]["unknown"] += 1

    # 3. Statut global
    if report["summary"]["error"] > 0:
        report["global_status"] = "error"
    elif report["summary"]["inactive"] > 0 or report["summary"]["unknown"] > 0:
        report["global_status"] = "degraded"
    elif report["event_bus_bridge"].get("status") == "error":
        report["global_status"] = "degraded"
    else:
        report["global_status"] = "ok"

    report["total_duration_ms"] = int((time.monotonic() - started) * 1000)
    return report


# ------------------------------------------------------------------------------
# API PUBLIQUE 2 : RÉSUMÉ CONDENSÉ (pour monitoring)
# ------------------------------------------------------------------------------

def get_nerves_summary() -> Dict[str, Any]:
    """
    Retourne un résumé ultra-condensé pour les checks de monitoring.

    Format :
      {
        "status": "ok" | "degraded" | "error",
        "ok": N,
        "disabled": N,
        "error": N,
        "inactive": N,
        "unknown": N,
        "event_bus_bridge_active": bool,
        "duration_ms": int
      }

    Ne lève JAMAIS d'exception.
    """
    try:
        full = get_all_nerves_status()
        return {
            "status": full["global_status"],
            "ok": full["summary"].get("ok", 0),
            "disabled": full["summary"].get("disabled", 0),
            "error": full["summary"].get("error", 0),
            "inactive": full["summary"].get("inactive", 0),
            "unknown": full["summary"].get("unknown", 0),
            "event_bus_bridge_active": bool(
                full.get("event_bus_bridge", {}).get("status") == "ok"
            ),
            "duration_ms": full.get("total_duration_ms", 0),
        }
    except Exception as exc:
        logger.error("[health] get_nerves_summary échoué : %s", exc)
        return {
            "status": "error",
            "ok": 0,
            "disabled": 0,
            "error": 1,
            "inactive": 0,
            "unknown": 0,
            "event_bus_bridge_active": False,
            "duration_ms": 0,
            "error_message": str(exc)[:300],
        }


# ------------------------------------------------------------------------------
# EXEMPLE D'INTÉGRATION FASTAPI (à copier dans routers/admin.py ou app.py)
# ------------------------------------------------------------------------------
# from nerves._health import get_nerves_summary, get_all_nerves_status
#
# @app.get("/health/nerves")
# async def health_nerves():
#     """Résumé condensé pour monitoring externe."""
#     return get_nerves_summary()
#
# @app.get("/health/nerves/detail")
# async def health_nerves_detail():
#     """Rapport détaillé pour debug humain."""
#     return get_all_nerves_status()
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    print("=" * 70)
    print("RÉSUMÉ (monitoring)")
    print("=" * 70)
    print(json.dumps(get_nerves_summary(), indent=2, ensure_ascii=False))

    print()
    print("=" * 70)
    print("DÉTAIL COMPLET (debug)")
    print("=" * 70)
    print(json.dumps(get_all_nerves_status(), indent=2, ensure_ascii=False))