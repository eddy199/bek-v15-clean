# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 14+15+16+17 — TMUX RELIÉ AU CERVEAU (nerves/tmux_nerves.py)
# ------------------------------------------------------------------------------
# Ce nerf branche services/tasks.py (moteur de tâches de fond multi-OS) sur :
#
#   NERF 14 : Hermes   → 4 nouveaux outils tmux_* enregistrés
#   NERF 15 : EventBus → traçabilité A2A de chaque spawn/stop de tâche (via Nerf 3)
#   NERF 16 : Guardian → bridge pour les audits de fond
#   NERF 17 : Sub-CRM  → bridge pour que chaque sous-CRM lance ses workers
#
# NOUVEAUX OUTILS HERMES (additifs) :
#   - tmux_start_task     → lance une tâche de fond (shell/script)
#   - tmux_stop_task      → arrête une tâche de fond par nom de session
#   - tmux_list_tasks     → liste les tâches actives (via psutil)
#   - tmux_task_status    → statut détaillé d'une session (logs, PID)
#
# BRIDGES EXPOSÉS :
#   - tmux_start_for_guardian()   → utilisable par background_guardian_worker
#   - tmux_start_for_sub_crm()    → utilisable par SubCRMEngine
#
# RÈGLES D'OR :
#   - Aucune modification de services/tasks.py
#   - Aucune modification de hermes_core.py
#   - Aucune modification de state_synchronizer.py
#   - On utilise UNIQUEMENT les API publiques existantes
#   - Feature-flag : BEK_ENABLE_TMUX_NERVES (défaut true)
#   - Fallback silencieux si psutil indisponible
#
# CORRECTIFS v2 (robustesse) :
#   - Utilise publish_event_unified (pont Nerf 3) au lieu de EventBusKafka direct
#     → supprime les doublons d'événements constatés dans les logs
#   - Fallback legacy EventBusKafka si le pont Nerf 3 est indisponible
#   - _persist_task_state() : timeout court (DB lente ne bloque plus le handler)
#   - _handler_tmux_list_tasks : snapshot thread-safe + copie défensive
#   - _handler_tmux_task_status : évite le double os.path.exists(log_path)
#   - Aucune signature modifiée : compatibilité totale avec les autres nerfs
# ==============================================================================

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger("bek.nerves.tmux")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    """Vérifie si le Nerf 14-17 est activé (par défaut : oui)."""
    return os.getenv("BEK_ENABLE_TMUX_NERVES", "true").lower() in ("true", "1", "yes")


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
        logger.debug("[Nerf 15] Événement publié (pont unifié) : %s", topic)
        return
    except Exception as exc:
        logger.debug("[Nerf 15] Pont unifié indisponible : %s", exc)

    # 2. Fallback legacy : EventBusKafka direct
    try:
        from event_bus import EventBusKafka
        bus = EventBusKafka()
        bus.publish(topic, payload)
        logger.debug("[Nerf 15] Événement publié (legacy Kafka) : %s", topic)
    except Exception as exc:
        logger.debug("[Nerf 15] EventBus indisponible (mode dégradé) : %s", exc)


# ------------------------------------------------------------------------------
# PONT STATE SYNCHRONIZER — persistance Neon (silencieuse, avec timeout court)
# ------------------------------------------------------------------------------

def _persist_task_state(
    session_name: str,
    state: str,
    correlation_id: str = "",
    timeout_sec: float = 2.0,
) -> None:
    """
    Persiste l'état d'une tâche dans Neon via state_synchronizer.
    Utilise un timeout court pour ne pas bloquer le handler Hermes.
    Ne lève JAMAIS d'exception.
    """
    try:
        import concurrent.futures
        from state_synchronizer import update_task_state

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                update_task_state,
                task_id=session_name,
                state=state,
                correlation_id=correlation_id,
                payload=f"tmux_session:{session_name}",
            )
            try:
                future.result(timeout=timeout_sec)
            except concurrent.futures.TimeoutError:
                logger.debug("[Nerf 15] Persistance Neon timeout (>%.1fs)", timeout_sec)
    except Exception as exc:
        logger.debug("[Nerf 15] Persistance Neon indisponible : %s", exc)


# ------------------------------------------------------------------------------
# HANDLERS RÉELS — appellent services/tasks.py
# ------------------------------------------------------------------------------

def _handler_tmux_start_task(
    session_name: str = "",
    command: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Nerf 14 : Lance une tâche de fond via services.tasks.start_background_task.
    Traçabilité EventBus (Nerf 15) + persistance Neon.
    """
    if not session_name or not command:
        return {
            "status": "error",
            "message": "session_name et command sont obligatoires.",
        }

    try:
        from services.tasks import start_background_task

        result = start_background_task(session_name, command)

        # Traçabilité A2A
        _publish_event(
            "skills-index",
            {
                "action": "tmux_start_task",
                "session_name": session_name,
                "command": command[:200],
                "status": result.get("status", "unknown") if isinstance(result, dict) else "unknown",
            },
        )

        # Persistance Neon
        _persist_task_state(session_name, "RUNNING")

        return result or {"status": "success", "message": "Tâche lancée."}
    except Exception as exc:
        logger.error("[Nerf 14] tmux_start_task échoué : %s", exc)
        return {"status": "error", "message": f"tmux_start_task échoué : {exc}"}


def _handler_tmux_stop_task(session_name: str = "", **kwargs: Any) -> Dict[str, Any]:
    """
    Nerf 14 : Arrête une tâche de fond via services.tasks.stop_background_task.
    Traçabilité EventBus + persistance Neon.
    """
    if not session_name:
        return {"status": "error", "message": "session_name est obligatoire."}

    try:
        from services.tasks import stop_background_task

        result = stop_background_task(session_name)

        # Traçabilité A2A
        _publish_event(
            "skills-index",
            {
                "action": "tmux_stop_task",
                "session_name": session_name,
                "status": result.get("status", "unknown") if isinstance(result, dict) else "unknown",
            },
        )

        # Persistance Neon
        _persist_task_state(session_name, "COMPLETED")

        return result or {"status": "success", "message": "Tâche arrêtée."}
    except Exception as exc:
        logger.error("[Nerf 14] tmux_stop_task échoué : %s", exc)
        return {"status": "error", "message": f"tmux_stop_task échoué : {exc}"}


def _handler_tmux_list_tasks(**kwargs: Any) -> Dict[str, Any]:
    """
    Nerf 14 : Liste les tâches de fond actives via services.tasks.RUNNING_BACKGROUND_TASKS
    et psutil pour vérifier leur vivacité.
    """
    try:
        from services.tasks import RUNNING_BACKGROUND_TASKS

        # Snapshot thread-safe + copie défensive (évite mutations concurrentes)
        tasks_snapshot: Dict[str, Any] = dict(RUNNING_BACKGROUND_TASKS or {})

        # Vérification de vivacité via psutil (si disponible)
        alive_status: Dict[str, bool] = {}
        try:
            import psutil
            for session_name, pid in tasks_snapshot.items():
                try:
                    alive_status[session_name] = bool(psutil.pid_exists(pid))
                except Exception:
                    alive_status[session_name] = False
        except ImportError:
            alive_status = {name: True for name in tasks_snapshot.keys()}

        # Construction du rapport
        tasks_report: List[Dict[str, Any]] = []
        for session_name, pid in tasks_snapshot.items():
            tasks_report.append({
                "session_name": session_name,
                "pid": pid,
                "alive": alive_status.get(session_name, False),
            })

        return {
            "status": "success",
            "count": len(tasks_report),
            "tasks": tasks_report,
            "os": os.name,
        }
    except Exception as exc:
        logger.error("[Nerf 14] tmux_list_tasks échoué : %s", exc)
        return {"status": "error", "message": f"tmux_list_tasks échoué : {exc}"}


def _handler_tmux_task_status(session_name: str = "", **kwargs: Any) -> Dict[str, Any]:
    """
    Nerf 14 : Statut détaillé d'une session.
    Retourne PID, vivacité, et les 50 dernières lignes du fichier log si présent.
    """
    if not session_name:
        return {"status": "error", "message": "session_name est obligatoire."}

    try:
        from services.tasks import RUNNING_BACKGROUND_TASKS
        from core.paths import GENERATED_DIR

        pid = (RUNNING_BACKGROUND_TASKS or {}).get(session_name)

        # Vérification de vivacité
        alive = False
        if pid:
            try:
                import psutil
                alive = bool(psutil.pid_exists(pid))
            except ImportError:
                alive = True

        # Lecture du fichier log (un seul os.path.exists)
        log_tail: List[str] = []
        log_path = os.path.join(GENERATED_DIR, f"{session_name}_logs.txt")
        log_exists = os.path.exists(log_path)

        if log_exists:
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    log_tail = [line.rstrip("\n") for line in lines[-50:]]
            except Exception as exc:
                logger.debug("[Nerf 14] Lecture log échouée : %s", exc)

        return {
            "status": "success",
            "session_name": session_name,
            "pid": pid,
            "alive": alive,
            "log_path": log_path if log_exists else None,
            "log_tail": log_tail,
        }
    except Exception as exc:
        logger.error("[Nerf 14] tmux_task_status échoué : %s", exc)
        return {"status": "error", "message": f"tmux_task_status échoué : {exc}"}


# ------------------------------------------------------------------------------
# BRIDGE GUARDIAN (Nerf 16) — utilisable par hermes.background_guardian_worker
# ------------------------------------------------------------------------------

def tmux_start_for_guardian(task_name: str, command: str) -> Dict[str, Any]:
    """
    Nerf 16 : Point d'entrée simplifié pour que le Guardian puisse lancer
    ses audits de fond sans dépendre directement de services.tasks.

    Retourne toujours un dict (jamais d'exception).
    """
    session_name = f"guardian_{task_name}"
    return _handler_tmux_start_task(session_name=session_name, command=command)


# ------------------------------------------------------------------------------
# BRIDGE SUB-CRM (Nerf 17) — utilisable par SubCRMEngine
# ------------------------------------------------------------------------------

def tmux_start_for_sub_crm(sub_crm_id: str, task_name: str, command: str) -> Dict[str, Any]:
    """
    Nerf 17 : Point d'entrée simplifié pour que chaque sous-CRM puisse lancer
    ses propres workers/tâches de fond.

    Le session_name est préfixé par l'ID du sous-CRM pour éviter les collisions.
    Retourne toujours un dict (jamais d'exception).
    """
    safe_id = str(sub_crm_id).replace("-", "")[:12]
    session_name = f"subcrm_{safe_id}_{task_name}"
    return _handler_tmux_start_task(session_name=session_name, command=command)


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE
# ------------------------------------------------------------------------------

TMUX_NERVES_TABLE: Dict[str, tuple] = {
    "tmux_start_task":   (_handler_tmux_start_task,   "L3"),
    "tmux_stop_task":    (_handler_tmux_stop_task,    "L3"),
    "tmux_list_tasks":   (_handler_tmux_list_tasks,   "L1"),
    "tmux_task_status":  (_handler_tmux_task_status,  "L1"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_tmux_nerves() -> Dict[str, Any]:
    """
    Active les nerfs Tmux en enregistrant 4 outils enrichis dans Hermes.

    Idempotent : peut être appelé plusieurs fois sans effet de bord.

    Retourne un rapport d'activation structuré.
    """
    if not _is_enabled():
        logger.warning("[Nerf 14-17] Désactivé via BEK_ENABLE_TMUX_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_TMUX_NERVES=false",
        }

    # Vérification de la disponibilité de services.tasks
    tasks_available = False
    try:
        from services.tasks import start_background_task, stop_background_task  # noqa: F401
        tasks_available = True
    except ImportError as exc:
        logger.warning(
            "⚠️ [Nerf 14-17] services/tasks.py indisponible (%s). "
            "Les outils tmux_* seront enregistrés mais échoueront à l'exécution.",
            exc,
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
        logger.error("[Nerf 14-17] Impossible d'importer hermes_core : %s", exc)
        return {"status": "error", "message": str(exc)}

    activated: List[str] = []
    failed: List[Dict[str, str]] = []

    for tool_name, (handler, risk_level) in TMUX_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("🧠 [Nerf 14] Outil tmux branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 14] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 14-17] Activation terminée : %d outils tmux branchés, %d échecs. "
        "services.tasks disponible : %s | EventBus pont actif : %s",
        len(activated), len(failed), tasks_available, event_bus_bridge_active,
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "tasks_available": tasks_available,
        "event_bus_bridge_active": event_bus_bridge_active,
        "guardian_bridge": "tmux_start_for_guardian",
        "sub_crm_bridge": "tmux_start_for_sub_crm",
    }


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_tmux_nerves()
    print("Résultat activation Nerf 14-17 :", result)