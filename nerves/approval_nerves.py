# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 5 — APPROVAL (v2.0 — Compatible Hermes v19.28)
# ==============================================================================
from __future__ import annotations
import logging, os, uuid
from typing import Any, Dict, List, Optional

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
    if not _is_enabled(): return {"status": "disabled"}
    try:
        from hermes_core import hermes
    except ImportError as exc:
        return {"status": "error", "message": str(exc)}

    activated, failed = [], []
    for tool_name, (handler, risk_level) in APPROVAL_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            
    logger.info("✅ [Nerf 5] Approval activé : %d outils branchés", len(activated))
    return {"status": "ok", "activated_count": len(activated), "activated_tools": activated, "failed": failed}