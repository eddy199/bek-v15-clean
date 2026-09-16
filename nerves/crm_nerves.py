# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 10 — SUB-CRM ENGINE BRANCHÉ À HERMES (nerves/crm_nerves.py)
# ------------------------------------------------------------------------------
# Ce nerf expose sub_crm_engine.py comme outils Hermes avec traçabilité EventBus.
#
#   NERF 10 : Hermes → SubCRMEngine (spawn/list/get/stats + bridge Tmux)
#
# PROBLÈME RÉSOLU :
#   - Actuellement : sub_crm_engine.py existe et crée des sous-CRM en DB Neon,
#     mais AUCUN outil Hermes ne permet de les piloter.
#   - Résultat : les sous-CRM sont créés manuellement via l'UI, pas via l'IA.
#
# SOLUTION (ce nerf) :
#   - 5 outils Hermes pour piloter les sous-CRM depuis le chat
#   - Bridge Tmux : chaque sous-CRM peut lancer ses propres workers de fond
#   - Traçabilité EventBus complète (correlation_id propagé)
#
# NOUVEAUX OUTILS HERMES (additifs) :
#   - sub_crm_spawn         → crée un nouveau sous-CRM
#   - sub_crm_list          → liste tous les sous-CRM
#   - sub_crm_get           → détail d'un sous-CRM par ID
#   - sub_crm_opportunities → liste les opportunités CRM (Neon)
#   - sub_crm_stats         → statistiques CRM globales
#
# BRIDGES EXPOSÉS :
#   - spawn_sub_crm_with_worker()  → spawn + lancement d'un worker Tmux
#
# RÈGLES D'OR :
#   - Aucune modification de sub_crm_engine.py
#   - Aucune modification de plugin_crm.py
#   - Aucune modification de services/db.py
#   - Aucune modification de hermes_core.py
#   - Feature-flag : BEK_ENABLE_CRM_NERVES (défaut true)
#   - Ne bloque JAMAIS le flux principal
# ==============================================================================

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.nerves.crm")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_CRM_NERVES", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# PUBLICATION EVENTBUS — via le pont unifié du Nerf 3
# ------------------------------------------------------------------------------

def _publish_crm_event(action: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """Publie un événement CRM sur l'EventBus unifié."""
    payload: Dict[str, Any] = {"action": action, "source": "crm_nerves"}
    if extra:
        payload.update(extra)

    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified("skills-index", payload)
        logger.debug("[Nerf 10] Événement publié : skills-index / %s", action)
    except Exception as exc:
        logger.debug("[Nerf 10] Publication EventBus échouée (mode dégradé) : %s", exc)


# ------------------------------------------------------------------------------
# HANDLERS HERMES — pilotage des sous-CRM
# ------------------------------------------------------------------------------

def _handler_sub_crm_spawn(
    niche_name: str = "",
    cahier_des_charges: str = "",
    objectives: Optional[List[str]] = None,
    parent_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Handler Hermes : sub_crm_spawn → SubCRMEngine.spawn_sub_crm().
    Crée un nouveau sous-CRM dans Neon avec ses outils next-gen.
    """
    if not niche_name:
        return {"status": "error", "message": "niche_name obligatoire."}

    try:
        from sub_crm_engine import SubCRMEngine

        objectives = objectives or []
        result = SubCRMEngine.spawn_sub_crm(
            niche_name=niche_name,
            cahier_des_charges=cahier_des_charges or f"Sous-CRM {niche_name}",
            objectives=objectives,
            parent_id=parent_id,
        )

        # Traçabilité A2A
        _publish_crm_event(
            action="sub_crm_spawned",
            extra={
                "niche_name": niche_name[:100],
                "sub_crm_id": result.get("sub_crm_id", "") if isinstance(result, dict) else "",
                "status": result.get("status", "unknown") if isinstance(result, dict) else "unknown",
            },
        )

        return result or {"status": "error", "message": "Résultat vide."}

    except Exception as exc:
        logger.error("[Nerf 10] sub_crm_spawn échoué : %s", exc)
        _publish_crm_event(action="sub_crm_spawn_error", extra={"error": str(exc)[:300]})
        return {"status": "error", "message": f"sub_crm_spawn échoué : {exc}"}


def _handler_sub_crm_list(**kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : sub_crm_list → SubCRMEngine.list_sub_crms()."""
    try:
        from sub_crm_engine import SubCRMEngine
        sub_crms = SubCRMEngine.list_sub_crms()
        return {
            "status": "success",
            "count": len(sub_crms) if isinstance(sub_crms, list) else 0,
            "sub_crms": sub_crms or [],
        }
    except Exception as exc:
        logger.error("[Nerf 10] sub_crm_list échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_sub_crm_get(sub_crm_id: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : sub_crm_get → SubCRMEngine.get_sub_crm()."""
    if not sub_crm_id:
        return {"status": "error", "message": "sub_crm_id obligatoire."}
    try:
        from sub_crm_engine import SubCRMEngine
        sub_crm = SubCRMEngine.get_sub_crm(sub_crm_id)
        if not sub_crm:
            return {"status": "error", "message": f"Sous-CRM '{sub_crm_id}' introuvable."}
        return {"status": "success", "sub_crm": sub_crm}
    except Exception as exc:
        logger.error("[Nerf 10] sub_crm_get échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_sub_crm_opportunities(limit: int = 20, **kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : sub_crm_opportunities → liste des opportunités CRM (Neon)."""
    try:
        limit_int = int(limit) if limit else 20
    except (TypeError, ValueError):
        limit_int = 20
    limit_int = max(1, min(limit_int, 200))

    try:
        from services.db import execute_database_sql
        result = execute_database_sql(
            f'SELECT id, name, amount, currency, stage, created_at '
            f'FROM "opportunities" ORDER BY id DESC LIMIT {limit_int};'
        )

        # Traçabilité A2A
        _publish_crm_event(
            action="opportunities_listed",
            extra={"count": result.get("count", 0), "limit": limit_int},
        )

        return {
            "status": "success",
            "count": result.get("count", 0),
            "opportunities": result.get("data", []),
        }
    except Exception as exc:
        logger.error("[Nerf 10] sub_crm_opportunities échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_sub_crm_stats(**kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : sub_crm_stats → statistiques CRM globales (companies/contacts/opportunities)."""
    try:
        from services.db import execute_database_sql

        companies = execute_database_sql('SELECT count(*)::int as c FROM "companies";')
        contacts = execute_database_sql('SELECT count(*)::int as c FROM "contacts";')
        opportunities = execute_database_sql(
            'SELECT count(*)::int as c, COALESCE(SUM(amount), 0)::float as total FROM "opportunities";'
        )

        stats = {
            "companies": companies.get("data", [{}])[0].get("c", 0) if companies.get("status") == "success" else 0,
            "contacts": contacts.get("data", [{}])[0].get("c", 0) if contacts.get("status") == "success" else 0,
            "deals": opportunities.get("data", [{}])[0].get("c", 0) if opportunities.get("status") == "success" else 0,
            "pipeline_total": opportunities.get("data", [{}])[0].get("total", 0) if opportunities.get("status") == "success" else 0,
        }

        # Traçabilité A2A
        _publish_crm_event(action="crm_stats_fetched", extra={"stats": stats})

        return {"status": "success", **stats}
    except Exception as exc:
        logger.error("[Nerf 10] sub_crm_stats échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


# ------------------------------------------------------------------------------
# BRIDGE — Spawn + Lancement automatique d'un worker Tmux
# ------------------------------------------------------------------------------

def spawn_sub_crm_with_worker(
    niche_name: str,
    cahier_des_charges: str = "",
    objectives: Optional[List[str]] = None,
    worker_command: str = "",
) -> Dict[str, Any]:
    """
    Bridge public : crée un sous-CRM ET lance un worker Tmux pour lui.

    Utilise tmux_nerves.tmux_start_for_sub_crm() (Nerf 17).
    Ne lève JAMAIS d'exception.
    """
    # 1. Spawn du sous-CRM
    spawn_result = _handler_sub_crm_spawn(
        niche_name=niche_name,
        cahier_des_charges=cahier_des_charges,
        objectives=objectives,
    )

    if spawn_result.get("status") != "success":
        return spawn_result

    sub_crm_id = spawn_result.get("sub_crm_id", "")

    # 2. Lancement du worker Tmux (si commande fournie)
    worker_result: Dict[str, Any] = {"status": "not_requested"}
    if worker_command and sub_crm_id:
        try:
            from nerves.tmux_nerves import tmux_start_for_sub_crm
            worker_result = tmux_start_for_sub_crm(
                sub_crm_id=sub_crm_id,
                task_name="init_worker",
                command=worker_command,
            )
        except Exception as exc:
            logger.debug("[Nerf 10] tmux_nerves indisponible : %s", exc)
            worker_result = {"status": "unavailable", "message": str(exc)}

    return {
        "status": "success",
        "sub_crm": spawn_result,
        "worker": worker_result,
    }


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE
# ------------------------------------------------------------------------------

CRM_NERVES_TABLE: Dict[str, tuple] = {
    "sub_crm_spawn":         (_handler_sub_crm_spawn,         "L2"),
    "sub_crm_list":          (_handler_sub_crm_list,          "L1"),
    "sub_crm_get":           (_handler_sub_crm_get,           "L1"),
    "sub_crm_opportunities": (_handler_sub_crm_opportunities, "L1"),
    "sub_crm_stats":         (_handler_sub_crm_stats,         "L1"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_crm_nerves() -> Dict[str, Any]:
    """
    Active les nerfs CRM en enregistrant 5 outils Hermes.

    Idempotent. Feature-flag BEK_ENABLE_CRM_NERVES.
    """
    if not _is_enabled():
        logger.warning("[Nerf 10] Désactivé via BEK_ENABLE_CRM_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_CRM_NERVES=false",
        }

    # Vérification des dépendances
    sub_crm_available = False
    db_available = False
    try:
        from sub_crm_engine import SubCRMEngine  # noqa: F401
        sub_crm_available = True
    except Exception as exc:
        logger.debug("[Nerf 10] sub_crm_engine indisponible : %s", exc)

    try:
        from services.db import execute_database_sql  # noqa: F401
        db_available = True
    except Exception as exc:
        logger.debug("[Nerf 10] services.db indisponible : %s", exc)

    try:
        from hermes_core import hermes
    except ImportError as exc:
        logger.error("[Nerf 10] Impossible d'importer hermes_core : %s", exc)
        return {"status": "error", "message": str(exc)}

    activated: List[str] = []
    failed: List[Dict[str, str]] = []

    for tool_name, (handler, risk_level) in CRM_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("🧠 [Nerf 10] Outil CRM branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 10] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 10] Activation terminée : %d outils CRM branchés, %d échecs. "
        "SubCRMEngine : %s | services.db : %s",
        len(activated), len(failed), sub_crm_available, db_available,
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "sub_crm_engine_available": sub_crm_available,
        "services_db_available": db_available,
        "bridges_exposed": ["spawn_sub_crm_with_worker"],
    }


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_crm_nerves()
    print("Résultat activation Nerf 10 :", result)

    # Test list
    print()
    print("Test sub_crm_list :")
    print(_handler_sub_crm_list())

    # Test stats
    print()
    print("Test sub_crm_stats :")
    print(_handler_sub_crm_stats())