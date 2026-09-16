"""
BEK-v15.2 HYBRID - Human Approval Manager
-----------------------------------------
Gestion de la file d'attente et de la validation humaine pour les
actions sensibles Hermes Core V2 (Niveaux de risque L3, L4, L5).
Pont d'observabilité avec EventBusKafka et signatures de dérogation.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.approval_manager")


@dataclass
class ApprovalRequest:
    approval_id: str
    task_id: str
    trace_id: str
    tool: str
    args: Dict[str, Any]
    risk_level: str
    reason: str
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED, EXPIRED, EXECUTED
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)  # 1h expiration
    decision_by: Optional[str] = None
    decision_at: Optional[float] = None
    execution_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "tool": self.tool,
            "args": self.args,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "status": self.status,
            "created_at": datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(self.expires_at, tz=timezone.utc).isoformat(),
            "decision_by": self.decision_by,
            "decision_at": (
                datetime.fromtimestamp(self.decision_at, tz=timezone.utc).isoformat()
                if self.decision_at
                else None
            ),
            "execution_result": self.execution_result,
        }


class ApprovalManager:
    """
    Gestionnaire centralisé et thread-safe des demandes d'approbation humaine.
    """

    def __init__(self) -> None:
        self._requests: Dict[str, ApprovalRequest] = {}
        self._lock = threading.RLock()

    @staticmethod
    def create_approval_id() -> str:
        return f"BEK-APPR-{uuid.uuid4().hex[:10].upper()}"

    def submit_request(
        self,
        task_id: str,
        trace_id: str,
        tool: str,
        args: Dict[str, Any],
        risk_level: str,
        reason: str,
        ttl_seconds: int = 3600,
    ) -> ApprovalRequest:
        """Enregistre une nouvelle demande en attente d'approbation et alerte l'EventBus."""
        approval_id = self.create_approval_id()
        now = time.time()

        req = ApprovalRequest(
            approval_id=approval_id,
            task_id=task_id,
            trace_id=trace_id,
            tool=tool,
            args=args,
            risk_level=risk_level,
            reason=reason,
            created_at=now,
            expires_at=now + ttl_seconds,
        )

        with self._lock:
            self._requests[approval_id] = req

        logger.info(
            "Demande approbation créée | id=%s | tool=%s | risk=%s",
            approval_id,
            tool,
            risk_level,
        )

        # Notification EventBus Kafka sur le topic error-signals si niveau critique L4/L5
        if risk_level in ("L4", "L5"):
            try:
                from event_bus import EventBusKafka
                bus = EventBusKafka()
                bus.publish(
                    "error-signals",
                    {
                        "msg": f"Action sensible retenue pour validation humaine ({risk_level}) : {tool}",
                        "approval_id": approval_id,
                        "trace_id": trace_id,
                    },
                )
            except Exception:
                pass

        return req

    def get_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        with self._lock:
            req = self._requests.get(approval_id)
            if req and req.status == "PENDING" and time.time() > req.expires_at:
                req.status = "EXPIRED"
            return req

    def list_requests(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Liste les demandes avec filtrage optionnel (par défaut tout)."""
        with self._lock:
            now = time.time()
            results = []
            for req in sorted(self._requests.values(), key=lambda r: r.created_at, reverse=True):
                if req.status == "PENDING" and now > req.expires_at:
                    req.status = "EXPIRED"
                if status is None or req.status.upper() == status.upper():
                    results.append(req.to_dict())
            return results

    def approve_and_execute(
        self,
        approval_id: str,
        admin_user: str = "admin",
    ) -> Dict[str, Any]:
        """Approuve la demande et déclenche l'exécution immédiate via Hermes Core."""
        with self._lock:
            req = self.get_request(approval_id)
            if not req:
                return {"status": "error", "message": "Demande d'approbation introuvable."}

            if req.status != "PENDING":
                return {
                    "status": "error",
                    "message": f"Demande déjà traitée ou invalide (statut={req.status}).",
                }

            req.status = "APPROVED"
            req.decision_by = admin_user
            req.decision_at = time.time()

        from hermes_core import hermes

        tool = hermes._get_tool(req.tool)
        if not tool:
            req.status = "FAILED"
            return {"status": "error", "message": f"Outil '{req.tool}' introuvable dans Hermes."}

        # Exécution directe sous dérogation humaine certifiée
        logger.info("Exécution post-approbation humaine | id=%s | tool=%s", approval_id, req.tool)
        tool_result = hermes._execute_tool(tool, req.args, req.trace_id, req.task_id)

        req.execution_result = tool_result.to_dict()
        req.status = "EXECUTED" if tool_result.success else "FAILED"

        return {
            "status": "success" if tool_result.success else "failed",
            "approval_id": approval_id,
            "execution": req.execution_result,
        }

    def reject_request(
        self,
        approval_id: str,
        admin_user: str = "admin",
        reason: str = "Refusé par l'administrateur",
    ) -> Dict[str, Any]:
        """Rejette une demande d'approbation."""
        with self._lock:
            req = self.get_request(approval_id)
            if not req:
                return {"status": "error", "message": "Demande d'approbation introuvable."}

            if req.status != "PENDING":
                return {
                    "status": "error",
                    "message": f"Demande non modifiable (statut={req.status}).",
                }

            req.status = "REJECTED"
            req.decision_by = admin_user
            req.decision_at = time.time()
            req.reason = f"{req.reason} | Rejet: {reason}"

        logger.info("Demande rejetée | id=%s | par=%s", approval_id, admin_user)
        return {"status": "success", "approval_id": approval_id, "decision": "REJECTED"}


# Instance Singleton globale
approval_manager = ApprovalManager()
