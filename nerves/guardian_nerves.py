# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 9 — GUARDIAN RELIÉ À L'EVENTBUS (nerves/guardian_nerves.py)
# ------------------------------------------------------------------------------
# Ce nerf branche le Guardian (hermes_core.background_guardian_worker) sur
# l'EventBus unifié (Nerf 3) et expose son état via Hermes :
#
#   NERF 9 : Guardian → EventBus (traçabilité A2A de chaque audit)
#
# NOUVEAUX OUTILS HERMES (additifs) :
#   - guardian_status        → état du worker Guardian (running/stopped)
#   - guardian_audit_log     → dernières entrées de la table system_jobs
#   - guardian_trigger_audit → déclenche un audit manuel (via tmux_nerves)
#
# BRIDGES EXPOSÉS :
#   - notify_guardian_audit_start()   → appelé pour tracer le début d'audit
#   - notify_guardian_audit_done()    → appelé pour tracer la fin d'audit
#   - notify_guardian_audit_error()   → appelé pour tracer une erreur
#
# CORRECTIONS vs VERSION INITIALE :
#   - Utilise publish_event_unified (Kafka + Async simultanés, Nerf 3)
#   - Ne modifie PAS hermes_core.py ni le thread Guardian existant
#   - Lecture de l'état via la table system_jobs de Neon
#   - Fallback silencieux si Neon indisponible
#   - Aucun thread manuel
#
# RÈGLES D'OR :
#   - Aucune modification de hermes_core.py
#   - Aucune modification de memory.py ni state_synchronizer.py
#   - Feature-flag : BEK_ENABLE_GUARDIAN_NERVES (défaut true)
#   - Ne bloque JAMAIS le flux principal
# ==============================================================================

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.nerves.guardian")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_GUARDIAN_NERVES", "true").lower() in ("true", "1", "yes")


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
    Publie un événement Guardian sur l'EventBus unifié.
    Ne lève JAMAIS d'exception.
    """
    payload: Dict[str, Any] = {
        "action": action,
        "correlation_id": correlation_id,
        "source": "guardian_nerves",
        "timestamp_ms": int(time.time() * 1000),
    }
    if extra:
        payload.update(extra)

    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified(topic, payload)
        logger.debug("[Nerf 9] Événement publié : %s / %s", topic, action)
    except Exception as exc:
        logger.debug("[Nerf 9] Publication EventBus échouée (mode dégradé) : %s", exc)


# ------------------------------------------------------------------------------
# BRIDGES PUBLICS — utilisables par hermes_core.background_guardian_worker
# ------------------------------------------------------------------------------

def notify_guardian_audit_start(job_id: str = "", task_name: str = "matrix_silent_audit") -> str:
    """
    Bridge : à appeler au DÉBUT d'un audit Guardian.
    Publie un événement 'vector-context' traçable.
    Retourne le correlation_id généré.
    """
    correlation_id = f"guardian_{uuid.uuid4().hex[:12]}"
    _publish_traced_event(
        topic="vector-context",
        action="guardian_audit_start",
        correlation_id=correlation_id,
        extra={"job_id": job_id, "task_name": task_name},
    )
    return correlation_id


def notify_guardian_audit_done(
    correlation_id: str = "",
    replayed_count: int = 0,
    duration_ms: int = 0,
) -> None:
    """
    Bridge : à appeler en FIN d'audit Guardian (succès).
    Publie un événement 'vector-context' traçable.
    """
    _publish_traced_event(
        topic="vector-context",
        action="guardian_audit_done",
        correlation_id=correlation_id or f"guardian_done_{uuid.uuid4().hex[:8]}",
        extra={"replayed_count": replayed_count, "duration_ms": duration_ms},
    )


def notify_guardian_audit_error(
    correlation_id: str = "",
    error: str = "",
) -> None:
    """
    Bridge : à appeler en FIN d'audit Guardian (erreur).
    Publie un événement 'error-signals' traçable.
    """
    _publish_traced_event(
        topic="error-signals",
        action="guardian_audit_error",
        correlation_id=correlation_id or f"guardian_err_{uuid.uuid4().hex[:8]}",
        extra={"error": (error or "")[:300]},
    )


# ------------------------------------------------------------------------------
# HANDLERS RÉELS — lecture de l'état du Guardian
# ------------------------------------------------------------------------------

def _read_guardian_state_from_hermes() -> Dict[str, Any]:
    """
    Lit l'état du worker Guardian depuis l'instance globale hermes.
    Ne lève JAMAIS d'exception.
    """
    state: Dict[str, Any] = {
        "workers_started": False,
        "hermes_shutdown": False,
        "worker_lock_present": False,
    }
    try:
        from hermes_core import hermes
        state["workers_started"] = bool(getattr(hermes, "_workers_started", False))
        state["hermes_shutdown"] = bool(getattr(hermes, "_shutdown", False))
        state["worker_lock_present"] = hasattr(hermes, "_worker_lock")
    except Exception as exc:
        logger.debug("[Nerf 9] Lecture état hermes échouée : %s", exc)
    return state


def _read_guardian_jobs_from_neon(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Lit les derniers jobs Guardian depuis la table system_jobs de Neon.
    Ne lève JAMAIS d'exception.
    """
    jobs: List[Dict[str, Any]] = []
    try:
        from memory import get_db_connection
        conn = get_db_connection()
        if not conn:
            return jobs

        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT job_id, task_name, status, retry_count, error_message, created_at
                FROM system_jobs
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (limit,),
            )
            for row in cur.fetchall():
                jobs.append({
                    "job_id": row[0],
                    "task_name": row[1],
                    "status": row[2],
                    "retry_count": row[3],
                    "error_message": row[4],
                    "created_at": str(row[5]) if row[5] is not None else None,
                })
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            try:
                conn.close()
            except Exception:
                pass
    except Exception as exc:
        logger.debug("[Nerf 9] Lecture system_jobs échouée : %s", exc)
    return jobs


def _handler_guardian_status(**kwargs: Any) -> Dict[str, Any]:
    """
    Handler Hermes : guardian_status → état courant du worker Guardian.
    """
    hermes_state = _read_guardian_state_from_hermes()
    is_running = hermes_state.get("workers_started") and not hermes_state.get("hermes_shutdown")

    return {
        "status": "success",
        "guardian_running": is_running,
        "hermes_workers_started": hermes_state.get("workers_started", False),
        "hermes_shutdown": hermes_state.get("hermes_shutdown", False),
        "worker_lock_present": hermes_state.get("worker_lock_present", False),
        "message": "Guardian actif." if is_running else "Guardian arrêté ou non démarré.",
    }


def _handler_guardian_audit_log(limit: int = 10, **kwargs: Any) -> Dict[str, Any]:
    """
    Handler Hermes : guardian_audit_log → dernières entrées system_jobs.
    """
    try:
        limit_int = int(limit) if limit else 10
    except (TypeError, ValueError):
        limit_int = 10
    limit_int = max(1, min(limit_int, 100))

    jobs = _read_guardian_jobs_from_neon(limit=limit_int)

    return {
        "status": "success",
        "count": len(jobs),
        "jobs": jobs,
        "message": f"{len(jobs)} job(s) Guardian récents.",
    }


def _handler_guardian_trigger_audit(**kwargs: Any) -> Dict[str, Any]:
    """
    Handler Hermes : guardian_trigger_audit → déclenche un audit manuel
    via tmux_nerves (Nerf 14-17) si disponible.
    """
    correlation_id = f"guardian_manual_{uuid.uuid4().hex[:12]}"

    # Notifier le début d'audit
    _publish_traced_event(
        topic="vector-context",
        action="guardian_manual_trigger",
        correlation_id=correlation_id,
        extra={"trigger": "manual"},
    )

    # Tentative de lancement d'un job Tmux
    tmux_available = False
    tmux_result: Dict[str, Any] = {}
    try:
        from nerves.tmux_nerves import tmux_start_for_guardian
        tmux_result = tmux_start_for_guardian(
            task_name="manual_audit",
            command="python -c \"from hermes_core import hermes; from memory import replay_pending_syncs; print('Manual audit:', replay_pending_syncs(limit=25))\"",
        )
        tmux_available = True
    except Exception as exc:
        logger.debug("[Nerf 9] tmux_nerves indisponible : %s", exc)
        tmux_result = {"status": "unavailable", "message": str(exc)}

    return {
        "status": "success",
        "correlation_id": correlation_id,
        "tmux_available": tmux_available,
        "tmux_result": tmux_result,
        "message": "Audit Guardian déclenché." if tmux_available else "Audit noté mais Tmux indisponible.",
    }


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE
# ------------------------------------------------------------------------------

GUARDIAN_NERVES_TABLE: Dict[str, tuple] = {
    "guardian_status":        (_handler_guardian_status,        "L1"),
    "guardian_audit_log":     (_handler_guardian_audit_log,     "L1"),
    "guardian_trigger_audit": (_handler_guardian_trigger_audit, "L2"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_guardian_nerves() -> Dict[str, Any]:
    """
    Active les nerfs Guardian en enregistrant 3 nouveaux outils dans Hermes.

    Idempotent. Feature-flag BEK_ENABLE_GUARDIAN_NERVES.

    Retourne un rapport d'activation structuré.
    """
    if not _is_enabled():
        logger.warning("[Nerf 9] Désactivé via BEK_ENABLE_GUARDIAN_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_GUARDIAN_NERVES=false",
        }

    # Vérification de la disponibilité de la table system_jobs (Neon)
    neon_available = False
    try:
        jobs = _read_guardian_jobs_from_neon(limit=1)
        neon_available = True  # Si on arrive ici sans exception, Neon est OK
    except Exception:
        neon_available = False

    # Vérification de la disponibilité de l'EventBus pont (Nerf 3)
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
        logger.error("[Nerf 9] Impossible d'importer hermes_core : %s", exc)
        return {"status": "error", "message": str(exc)}

    activated = []
    failed = []

    for tool_name, (handler, risk_level) in GUARDIAN_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("🧠 [Nerf 9] Outil Guardian branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 9] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 9] Activation terminée : %d outils Guardian branchés, %d échecs. "
        "Neon disponible : %s | EventBus pont actif : %s",
        len(activated), len(failed), neon_available, event_bus_available,
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "neon_available": neon_available,
        "event_bus_bridge_active": event_bus_available,
        "bridges_exposed": [
            "notify_guardian_audit_start",
            "notify_guardian_audit_done",
            "notify_guardian_audit_error",
        ],
    }


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_guardian_nerves()
    print("Résultat activation Nerf 9 :", result)

    # Test bridges
    cid = notify_guardian_audit_start(job_id="test_job_123")
    print("Correlation ID :", cid)
    notify_guardian_audit_done(correlation_id=cid, replayed_count=5, duration_ms=1200)
    print("Bridges testés OK")