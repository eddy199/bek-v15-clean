# -*- coding: utf-8 -*-
"""
==============================================================================
NERF 5 — APPROVAL MANAGER BRANCHÉ À HERMES
nerves/approval_nerves.py
------------------------------------------------------------------------------
Interception automatique des tâches L3-L5 + outils Hermes d'approbation.

Corrections :
  - Monkey-patch réversible et idempotent.
  - Conservation correcte de la méthode originale.
  - Détection robuste de SECURITY_APPROVAL_REQUIRED.
  - Extraction des paramètres depuis plusieurs formats de tâche.
  - Traçabilité EventBus via Nerf 3.
  - Aucun blocage du flux principal.
  - Les erreurs d'ApprovalManager restent isolées.
==============================================================================
"""

from __future__ import annotations

import logging
import os
import types
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("bek.nerves.approval")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_APPROVAL_NERVES", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# EVENTBUS
# ------------------------------------------------------------------------------

def _publish_approval_event(
    action: str,
    approval_id: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    payload: Dict[str, Any] = {
        "action": action,
        "approval_id": approval_id,
        "source": "approval_nerves",
    }
    if extra:
        payload.update(extra)

    topic = "error-signals" if action == "rejected" else "skills-index"

    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified(topic, payload)
        logger.debug("[Nerf 5] EventBus : %s / %s", topic, action)
    except Exception as exc:
        logger.debug("[Nerf 5] EventBus indisponible : %s", exc)


# ------------------------------------------------------------------------------
# ÉTAT DU PATCH
# ------------------------------------------------------------------------------

_original_validate: Optional[Callable[..., Any]] = None
_original_owner: Any = None
_interception_active = False


# ------------------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------------------

def _safe_task_value(task: Any, key: str, default: Any = None) -> Any:
    if isinstance(task, dict):
        return task.get(key, default)
    try:
        return getattr(task, key, default)
    except Exception:
        return default


def _extract_task_args(task: Any) -> Dict[str, Any]:
    """Supporte : task["args"] | task.args | task["arguments"] | task.arguments."""
    args = _safe_task_value(task, "args", None)
    if args is None:
        args = _safe_task_value(task, "arguments", None)
    if isinstance(args, dict):
        return dict(args)
    return {}


def _extract_tool_name(result: Dict[str, Any], task: Any) -> str:
    tool = (
        result.get("tool")
        or result.get("tool_name")
        or _safe_task_value(task, "tool", "")
        or _safe_task_value(task, "tool_name", "")
    )
    return str(tool or "")


def _extract_task_id(result: Dict[str, Any], task: Any) -> str:
    task_id = (
        result.get("task_id")
        or _safe_task_value(task, "task_id", "")
        or _safe_task_value(task, "id", "")
    )
    return str(task_id or "")


def _extract_risk_level(result: Dict[str, Any], task: Any) -> str:
    risk = (
        result.get("risk_level")
        or _safe_task_value(task, "risk_level", "")
        or "L3"
    )
    return str(risk)


# ------------------------------------------------------------------------------
# BRIDGE PUBLIC
# ------------------------------------------------------------------------------

def submit_for_human_approval(
    tool: str,
    args: Dict[str, Any],
    risk_level: str,
    task_id: str = "",
    trace_id: str = "",
    reason: str = "",
) -> Dict[str, Any]:
    """Soumet une tâche à ApprovalManager. Ne lève jamais d'exception."""
    if not tool:
        return {"status": "error", "message": "tool obligatoire."}
    if not risk_level:
        return {"status": "error", "message": "risk_level obligatoire."}

    try:
        from approval_manager import approval_manager
    except ImportError as exc:
        logger.debug("[Nerf 5] approval_manager indisponible : %s", exc)
        return {"status": "error", "message": "approval_manager indisponible."}

    try:
        final_task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        final_trace_id = trace_id or f"trace_{uuid.uuid4().hex[:8]}"
        final_reason = reason or (
            f"Action {risk_level} nécessitant validation humaine."
        )

        request = approval_manager.submit_request(
            task_id=final_task_id,
            trace_id=final_trace_id,
            tool=tool,
            args=args or {},
            risk_level=risk_level,
            reason=final_reason,
        )

        approval_id = str(getattr(request, "approval_id", "") or "")

        _publish_approval_event(
            action="submitted",
            approval_id=approval_id,
            extra={
                "tool": tool,
                "risk_level": risk_level,
                "task_id": final_task_id,
                "trace_id": final_trace_id,
            },
        )

        return {
            "status": "submitted",
            "approval_id": approval_id,
            "risk_level": risk_level,
            "tool": tool,
            "task_id": final_task_id,
            "trace_id": final_trace_id,
            "message": f"Demande soumise pour approbation (niveau {risk_level}).",
        }

    except Exception as exc:
        logger.error("[Nerf 5] submit_for_human_approval échoué : %s", exc)
        return {"status": "error", "message": f"Soumission échouée : {exc}"}


# ------------------------------------------------------------------------------
# PATCH HERMES
# ------------------------------------------------------------------------------

def _patched_validate_task(
    self,
    task: Any,
    trace_id: str,
) -> Optional[Dict[str, Any]]:
    """Wrapper autour de Hermes._validate_task."""
    global _original_validate

    if _original_validate is None:
        logger.error("[Nerf 5] Méthode originale absente.")
        return None

    try:
        result = _original_validate(task, trace_id)
    except TypeError:
        try:
            result = _original_validate(task)
        except Exception as exc:
            logger.error("[Nerf 5] Validation Hermes échouée : %s", exc)
            return None
    except Exception as exc:
        logger.error("[Nerf 5] Validation Hermes échouée : %s", exc)
        return None

    if not isinstance(result, dict):
        return result
    if result.get("status") != "SECURITY_APPROVAL_REQUIRED":
        return result

    tool_name = _extract_tool_name(result, task)
    risk_level = _extract_risk_level(result, task)
    task_id = _extract_task_id(result, task)
    args = _extract_task_args(task)
    reason = str(
        result.get("message")
        or f"Action {risk_level} requérant validation humaine."
    )

    submission = submit_for_human_approval(
        tool=tool_name,
        args=args,
        risk_level=risk_level,
        task_id=task_id,
        trace_id=trace_id,
        reason=reason,
    )

    if submission.get("status") == "submitted":
        result["approval_id"] = submission.get("approval_id", "")
        result["approval_status"] = "pending_human_validation"
        result["approval_task_id"] = submission.get("task_id", task_id)
        logger.info(
            "🛡️ [Nerf 5] Approval demandé | tool=%s | risk=%s | approval_id=%s",
            tool_name, risk_level, submission.get("approval_id"),
        )
    else:
        result["approval_status"] = "submission_failed"
        result["approval_error"] = submission.get(
            "message", "Erreur inconnue."
        )
        logger.error(
            "[Nerf 5] Soumission ApprovalManager échouée pour %s : %s",
            tool_name, result["approval_error"],
        )

    return result


# ------------------------------------------------------------------------------
# HERMES HANDLERS
# ------------------------------------------------------------------------------

def _handler_approval_submit(
    tool: str = "",
    risk_level: str = "L3",
    reason: str = "",
    args: Optional[Dict[str, Any]] = None,
    task_id: str = "",
    trace_id: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    if not tool:
        return {"status": "error", "message": "Le nom de l'outil est obligatoire."}
    return submit_for_human_approval(
        tool=tool,
        args=args or {},
        risk_level=risk_level,
        task_id=task_id,
        trace_id=trace_id,
        reason=reason,
    )


def _handler_approval_list(
    status: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    try:
        from approval_manager import approval_manager
        requests = approval_manager.list_requests(status=status)
        return {
            "status": "success",
            "count": len(requests),
            "requests": requests,
        }
    except Exception as exc:
        logger.error("[Nerf 5] approval_list échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_approval_get(
    approval_id: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    if not approval_id:
        return {"status": "error", "message": "approval_id obligatoire."}
    try:
        from approval_manager import approval_manager
        request = approval_manager.get_request(approval_id)
        if not request:
            return {
                "status": "error",
                "message": f"Demande {approval_id} introuvable.",
            }
        if hasattr(request, "to_dict"):
            data = request.to_dict()
        elif isinstance(request, dict):
            data = request
        else:
            data = {"approval_id": approval_id, "request": str(request)}
        return {"status": "success", "request": data}
    except Exception as exc:
        logger.error("[Nerf 5] approval_get échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_approval_approve(
    approval_id: str = "",
    admin_user: str = "admin",
    **kwargs: Any,
) -> Dict[str, Any]:
    if not approval_id:
        return {"status": "error", "message": "approval_id obligatoire."}
    try:
        from approval_manager import approval_manager
        result = approval_manager.approve_and_execute(
            approval_id, admin_user=admin_user
        )
        result_status = (
            result.get("status", "unknown")
            if isinstance(result, dict)
            else "completed"
        )
        _publish_approval_event(
            action="approved",
            approval_id=approval_id,
            extra={"admin_user": admin_user, "result": result_status},
        )
        return (
            result
            if isinstance(result, dict)
            else {"status": "success", "result": result}
        )
    except Exception as exc:
        logger.error("[Nerf 5] approval_approve échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_approval_reject(
    approval_id: str = "",
    admin_user: str = "admin",
    reason: str = "Refusé par l'administrateur.",
    **kwargs: Any,
) -> Dict[str, Any]:
    if not approval_id:
        return {"status": "error", "message": "approval_id obligatoire."}
    try:
        from approval_manager import approval_manager
        result = approval_manager.reject_request(
            approval_id, admin_user=admin_user, reason=reason
        )
        _publish_approval_event(
            action="rejected",
            approval_id=approval_id,
            extra={"admin_user": admin_user, "reason": reason[:200]},
        )
        return (
            result
            if isinstance(result, dict)
            else {"status": "success", "result": result}
        )
    except Exception as exc:
        logger.error("[Nerf 5] approval_reject échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


# ------------------------------------------------------------------------------
# TABLE HERMES
# ------------------------------------------------------------------------------

APPROVAL_NERVES_TABLE: Dict[str, tuple] = {
    "approval_submit":  (_handler_approval_submit,  "L1"),
    "approval_list":    (_handler_approval_list,    "L1"),
    "approval_get":     (_handler_approval_get,     "L1"),
    "approval_approve": (_handler_approval_approve, "L2"),
    "approval_reject":  (_handler_approval_reject,  "L2"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_approval_nerves() -> Dict[str, Any]:
    """
    Active :
      1. l'interception Hermes._validate_task ;
      2. les cinq outils Hermes.
    """
    global _original_validate
    global _original_owner
    global _interception_active

    if not _is_enabled():
        logger.warning("[Nerf 5] Désactivé via BEK_ENABLE_APPROVAL_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_APPROVAL_NERVES=false",
        }

    # ApprovalManager
    approval_manager_available = False
    try:
        from approval_manager import approval_manager  # noqa: F401
        approval_manager_available = True
    except ImportError as exc:
        logger.warning("[Nerf 5] approval_manager indisponible : %s", exc)

    # Hermes
    try:
        from hermes_core import hermes
    except ImportError as exc:
        logger.error("[Nerf 5] hermes_core indisponible : %s", exc)
        return {"status": "error", "message": str(exc)}

    # PATCH
    patch_installed = False
    if not _interception_active:
        try:
            original = getattr(hermes, "_validate_task", None)
            if original is None:
                return {
                    "status": "error",
                    "message": "hermes._validate_task introuvable.",
                }
            _original_validate = original
            _original_owner = hermes
            hermes._validate_task = types.MethodType(
                _patched_validate_task, hermes
            )
            _interception_active = True
            patch_installed = True
            logger.info("🛡️ [Nerf 5] Interception automatique L3+ installée")
        except Exception as exc:
            logger.error("[Nerf 5] Installation monkey-patch échouée : %s", exc)
            return {
                "status": "error",
                "message": f"Monkey-patch échoué : {exc}",
            }
    else:
        logger.debug("[Nerf 5] Monkey-patch déjà actif")

    # OUTILS HERMES
    activated: List[str] = []
    failed: List[Dict[str, str]] = []

    for tool_name, (handler, risk_level) in APPROVAL_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info(
                "🧠 [Nerf 5] Outil approval branché : %s (risk=%s)",
                tool_name, risk_level,
            )
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 5] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 5] Activation terminée | outils=%d | échecs=%d | "
        "ApprovalManager=%s | patch=%s",
        len(activated), len(failed),
        approval_manager_available, _interception_active,
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "approval_manager_available": approval_manager_available,
        "monkey_patch_installed": patch_installed,
        "interception_active": _interception_active,
        "bridge_exposed": "submit_for_human_approval",
    }


# ------------------------------------------------------------------------------
# DÉSACTIVATION
# ------------------------------------------------------------------------------

def deactivate_approval_nerves() -> Dict[str, Any]:
    """Restaure hermes._validate_task."""
    global _original_validate
    global _original_owner
    global _interception_active

    if not _interception_active:
        return {"status": "already_inactive"}

    try:
        hermes = _original_owner
        if hermes is None:
            from hermes_core import hermes as hermes_instance
            hermes = hermes_instance

        if _original_validate is not None:
            hermes._validate_task = _original_validate

        _original_validate = None
        _original_owner = None
        _interception_active = False
        logger.info("🛡️ [Nerf 5] Interception désinstallée")
        return {"status": "ok", "message": "Interception désactivée."}
    except Exception as exc:
        logger.error("[Nerf 5] Désactivation échouée : %s", exc)
        return {"status": "error", "message": str(exc)}


# ------------------------------------------------------------------------------
# TEST DIRECT
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    result = activate_approval_nerves()
    print("Résultat activation Nerf 5 :", result)

    test = submit_for_human_approval(
        tool="web_sync",
        args={"query": "test sensitive"},
        risk_level="L4",
        reason="Test manuel Nerf 5",
    )
    print("Test submit_for_human_approval :", test)