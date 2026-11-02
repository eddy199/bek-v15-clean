# -*- coding: utf-8 -*-
from __future__ import annotations
import logging, os, types, uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("bek.nerves.approval")

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_APPROVAL_NERVES", "true").lower() in ("true", "1", "yes")

def _publish_approval_event(action: str, approval_id: str = "", extra: Optional[Dict[str, Any]] = None) -> None:
    payload: Dict[str, Any] = {"action": action, "approval_id": approval_id, "source": "approval_nerves"}
    if extra: payload.update(extra)
    topic = "error-signals" if action == "rejected" else "skills-index"
    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified(topic, payload)
    except Exception: pass

_original_validate: Optional[Callable[..., Any]] = None
_original_owner: Any = None
_interception_active = False

def _safe_task_value(task: Any, key: str, default: Any = None) -> Any:
    if isinstance(task, dict): return task.get(key, default)
    try: return getattr(task, key, default)
    except Exception: return default

def _extract_task_args(task: Any) -> Dict[str, Any]:
    args = _safe_task_value(task, "args", None) or _safe_task_value(task, "arguments", None)
    return dict(args) if isinstance(args, dict) else {}

def _extract_tool_name(result: Dict[str, Any], task: Any) -> str:
    tool = result.get("tool") or result.get("tool_name") or _safe_task_value(task, "tool", "") or _safe_task_value(task, "tool_name", "")
    return str(tool or "")

def _extract_task_id(result: Dict[str, Any], task: Any) -> str:
    task_id = result.get("task_id") or _safe_task_value(task, "task_id", "") or _safe_task_value(task, "id", "")
    return str(task_id or "")

def _extract_risk_level(result: Dict[str, Any], task: Any) -> str:
    risk = result.get("risk_level") or _safe_task_value(task, "risk_level", "") or "L3"
    return str(risk)

def submit_for_human_approval(tool: str, args: Dict[str, Any], risk_level: str, task_id: str = "", trace_id: str = "", reason: str = "") -> Dict[str, Any]:
    if not tool or not risk_level: return {"status": "error", "message": "Paramètres manquants."}
    try:
        from approval_manager import approval_manager
    except ImportError: return {"status": "error", "message": "approval_manager indisponible."}

    try:
        request = approval_manager.submit_request(task_id=task_id or f"task_{uuid.uuid4().hex[:8]}", trace_id=trace_id or f"trace_{uuid.uuid4().hex[:8]}", tool=tool, args=args or {}, risk_level=risk_level, reason=reason or f"Action {risk_level}.")
        approval_id = str(getattr(request, "approval_id", "") or "")
        _publish_approval_event(action="submitted", approval_id=approval_id, extra={"tool": tool, "risk_level": risk_level})
        return {"status": "submitted", "approval_id": approval_id, "risk_level": risk_level, "tool": tool, "task_id": request.task_id, "trace_id": request.trace_id, "message": f"Demande soumise ({risk_level})."}
    except Exception as exc: return {"status": "error", "message": f"Échec : {exc}"}

def _patched_validate_task(self, task: Any, trace_id: str) -> Optional[Dict[str, Any]]:
    global _original_validate
    if _original_validate is None: return None

    try:
        result = _original_validate(task, trace_id)
    except TypeError:
        try: result = _original_validate(task)
        except Exception: return None
    except Exception: return None

    if not isinstance(result, dict): return result

    risk_level = _extract_risk_level(result, task)
    if risk_level in ("L1", "L2"):
        return result

    if result.get("status") != "SECURITY_APPROVAL_REQUIRED": return result

    tool_name = _extract_tool_name(result, task)
    task_id = _extract_task_id(result, task)
    args = _extract_task_args(task)
    reason = str(result.get("message") or f"Action {risk_level}.")

    submission = submit_for_human_approval(tool=tool_name, args=args, risk_level=risk_level, task_id=task_id, trace_id=trace_id, reason=reason)

    if submission.get("status") == "submitted":
        result["approval_id"] = submission.get("approval_id", "")
        result["approval_status"] = "pending_human_validation"
        result["approval_task_id"] = submission.get("task_id", task_id)
        logger.info("🛡️ [Nerf 5] Approval demandé | tool=%s | risk=%s", tool_name, risk_level)
    else:
        result["approval_status"] = "submission_failed"
        result["approval_error"] = submission.get("message", "")
    return result

def _handler_approval_submit(tool: str = "", risk_level: str = "L3", reason: str = "", args: Optional[Dict[str, Any]] = None, task_id: str = "", trace_id: str = "", **kwargs: Any) -> Dict[str, Any]:
    return submit_for_human_approval(tool=tool, args=args or {}, risk_level=risk_level, task_id=task_id, trace_id=trace_id, reason=reason) if tool else {"status": "error", "message": "Outil obligatoire."}

def _handler_approval_list(status: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
    try:
        from approval_manager import approval_manager
        return {"status": "success", "count": len(approval_manager.list_requests(status=status)), "requests": approval_manager.list_requests(status=status)}
    except Exception as exc: return {"status": "error", "message": str(exc)}

def _handler_approval_get(approval_id: str = "", **kwargs: Any) -> Dict[str, Any]:
    try:
        from approval_manager import approval_manager
        request = approval_manager.get_request(approval_id)
        return {"status": "success", "request": request.to_dict()} if request else {"status": "error", "message": "Introuvable."}
    except Exception as exc: return {"status": "error", "message": str(exc)}

def _handler_approval_approve(approval_id: str = "", admin_user: str = "admin", **kwargs: Any) -> Dict[str, Any]:
    try:
        from approval_manager import approval_manager
        result = approval_manager.approve_and_execute(approval_id, admin_user=admin_user)
        _publish_approval_event(action="approved", approval_id=approval_id, extra={"admin_user": admin_user})
        return result
    except Exception as exc: return {"status": "error", "message": str(exc)}

def _handler_approval_reject(approval_id: str = "", admin_user: str = "admin", reason: str = "Refusé.", **kwargs: Any) -> Dict[str, Any]:
    try:
        from approval_manager import approval_manager
        result = approval_manager.reject_request(approval_id, admin_user=admin_user, reason=reason)
        _publish_approval_event(action="rejected", approval_id=approval_id, extra={"admin_user": admin_user, "reason": reason})
        return result
    except Exception as exc: return {"status": "error", "message": str(exc)}

APPROVAL_NERVES_TABLE = {
    "approval_submit": (_handler_approval_submit, "L1"), "approval_list": (_handler_approval_list, "L1"),
    "approval_get": (_handler_approval_get, "L1"), "approval_approve": (_handler_approval_approve, "L2"),
    "approval_reject": (_handler_approval_reject, "L2"),
}

def activate_approval_nerves() -> Dict[str, Any]:
    global _original_validate, _original_owner, _interception_active
    if not _is_enabled(): return {"status": "disabled"}
    try: from hermes_core import hermes
    except ImportError as exc: return {"status": "error", "message": str(exc)}

    patch_installed = False
    if not _interception_active:
        try:
            original = getattr(hermes, "_validate_task", None)
            if original is None: return {"status": "error", "message": "_validate_task absent."}
            _original_validate = original; _original_owner = hermes
            hermes._validate_task = types.MethodType(_patched_validate_task, hermes)
            _interception_active = True; patch_installed = True
        except Exception as exc: return {"status": "error", "message": str(exc)}

    activated, failed = [], []
    for tool_name, (handler, risk_level) in APPROVAL_NERVES_TABLE.items():
        try: hermes.register_tool(tool_name, handler, risk_level=risk_level); activated.append(tool_name)
        except Exception as exc: failed.append({"tool": tool_name, "error": str(exc)})
    return {"status": "ok", "activated_count": len(activated), "activated_tools": activated, "failed": failed, "monkey_patch_installed": patch_installed}

def deactivate_approval_nerves() -> Dict[str, Any]:
    global _original_validate, _original_owner, _interception_active
    if not _interception_active: return {"status": "already_inactive"}
    try:
        hermes = _original_owner or __import__("hermes_core").hermes
        if _original_validate is not None: hermes._validate_task = _original_validate
        _original_validate = None; _original_owner = None; _interception_active = False
        return {"status": "ok"}
    except Exception as exc: return {"status": "error", "message": str(exc)}