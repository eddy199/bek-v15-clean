# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 5 — APPROVAL MANAGER BRANCHÉ À HERMES (nerves/approval_nerves.py)
# ------------------------------------------------------------------------------
# Ce nerf branche approval_manager.py (validation humaine L3-L5) sur Hermes :
#
#   NERF 5 : Hermes → ApprovalManager (interception automatique des tâches L3+)
#
# PROBLÈME RÉSOLU :
#   - Actuellement : hermes._validate_task() retourne SECURITY_APPROVAL_REQUIRED
#     pour L3-L5, mais RIEN ne soumet la demande à ApprovalManager.
#   - Résultat : les tâches sensibles restent bloquées sans retour utilisateur.
#
# SOLUTION (ce nerf) :
#   - Monkey-patch propre de _validate_task sur l'instance Hermes existante
#   - À chaque tâche L3-L5, soumission automatique à ApprovalManager
#   - Injection de approval_id dans le résultat retourné
#   - Restauration possible via feature-flag
#
# NOUVEAUX OUTILS HERMES (additifs) :
#   - approval_submit   → soumettre manuellement une demande d'approbation
#   - approval_list     → lister les demandes (filtrable par statut)
#   - approval_get      → consulter une demande par ID
#   - approval_approve  → approuver + exécuter une demande
#   - approval_reject   → rejeter une demande
#
# BRIDGES EXPOSÉS :
#   - submit_for_human_approval()  → utilisable par d'autres nerfs
#
# RÈGLES D'OR :
#   - Aucune modification de approval_manager.py
#   - Aucune modification de hermes_core.py
#   - Monkey-patch réversible (restauration possible)
#   - Feature-flag : BEK_ENABLE_APPROVAL_NERVES (défaut true)
#   - Traçabilité EventBus via Nerf 3
# ==============================================================================

from __future__ import annotations

import logging
import os
import types
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("bek.nerves.approval")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_APPROVAL_NERVES", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# PUBLICATION EVENTBUS — via le pont unifié du Nerf 3
# ------------------------------------------------------------------------------

def _publish_approval_event(
    action: str,
    approval_id: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Publie un événement d'approbation sur l'EventBus unifié.
    Ne lève JAMAIS d'exception.
    """
    payload: Dict[str, Any] = {
        "action": action,
        "approval_id": approval_id,
        "source": "approval_nerves",
    }
    if extra:
        payload.update(extra)

    # Les événements d'approbation sont critiques → topic error-signals si rejet, sinon skills-index
    topic = "error-signals" if action == "rejected" else "skills-index"

    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified(topic, payload)
        logger.debug("[Nerf 5] Événement publié : %s / %s", topic, action)
    except Exception as exc:
        logger.debug("[Nerf 5] Publication EventBus échouée (mode dégradé) : %s", exc)


# ------------------------------------------------------------------------------
# ÉTAT DE L'INTERCEPTION (pour restauration)
# ------------------------------------------------------------------------------

_original_validate: Optional[Callable] = None
_interception_active: bool = False


# ------------------------------------------------------------------------------
# BRIDGE PUBLIC — soumission automatique à l'ApprovalManager
# ------------------------------------------------------------------------------

def submit_for_human_approval(
    tool: str,
    args: Dict[str, Any],
    risk_level: str,
    task_id: str = "",
    trace_id: str = "",
    reason: str = "",
) -> Dict[str, Any]:
    """
    Bridge public : soumet une demande à l'ApprovalManager.
    Utilisable directement par d'autres nerfs (Sub-CRM, orchestrateurs, etc.)
    Ne lève JAMAIS d'exception. Retourne un dict avec approval_id.
    """
    if not tool or not risk_level:
        return {"status": "error", "message": "tool et risk_level obligatoires."}

    try:
        from approval_manager import approval_manager
    except ImportError as exc:
        logger.debug("[Nerf 5] approval_manager indisponible : %s", exc)
        return {"status": "error", "message": "approval_manager indisponible."}

    try:
        request = approval_manager.submit_request(
            task_id=task_id or f"task_{uuid.uuid4().hex[:8]}",
            trace_id=trace_id or f"trace_{uuid.uuid4().hex[:8]}",
            tool=tool,
            args=args or {},
            risk_level=risk_level,
            reason=reason or f"Action {risk_level} nécessitant validation humaine.",
        )

        approval_id = getattr(request, "approval_id", "")

        # Traçabilité A2A
        _publish_approval_event(
            action="submitted",
            approval_id=approval_id,
            extra={
                "tool": tool,
                "risk_level": risk_level,
                "task_id": task_id,
                "trace_id": trace_id,
            },
        )

        return {
            "status": "submitted",
            "approval_id": approval_id,
            "risk_level": risk_level,
            "tool": tool,
            "message": f"Demande soumise pour approbation (niveau {risk_level}).",
        }
    except Exception as exc:
        logger.error("[Nerf 5] submit_for_human_approval échoué : %s", exc)
        return {"status": "error", "message": f"Soumission échouée : {exc}"}


# ------------------------------------------------------------------------------
# INTERCEPTION AUTOMATIQUE — monkey-patch réversible de _validate_task
# ------------------------------------------------------------------------------

def _patched_validate_task(self, task: Any, trace_id: str) -> Optional[Dict[str, Any]]:
    """
    Version patchée de HermesCore._validate_task.
    Appelle la version originale puis, si le résultat indique
    SECURITY_APPROVAL_REQUIRED, soumet automatiquement la demande.
    """
    # Appel de la méthode originale (stockée dans _original_validate)
    try:
        if _original_validate is None:
            return None
        result = _original_validate(self, task, trace_id)
    except Exception as exc:
        logger.error("[Nerf 5] Erreur dans la méthode originale : %s", exc)
        return None

    # Interception uniquement si le résultat est une demande d'approbation
    if not result or not isinstance(result, dict):
        return result

    if result.get("status") != "SECURITY_APPROVAL_REQUIRED":
        return result

    # Extraction des données de la tâche
    tool_name = result.get("tool", "")
    risk_level = result.get("risk_level", "L3")
    task_id = result.get("task_id", "")
    args = task.get("args", {}) if isinstance(task, dict) else {}

    # Soumission automatique à ApprovalManager
    submission = submit_for_human_approval(
        tool=tool_name,
        args=args,
        risk_level=risk_level,
        task_id=task_id,
        trace_id=trace_id,
        reason=result.get("message", f"Action {risk_level} requérant validation."),
    )

    # Enrichir le résultat avec l'approval_id
    if submission.get("status") == "submitted":
        result["approval_id"] = submission.get("approval_id", "")
        result["approval_status"] = "pending_human_validation"
        logger.info(
            "🛡️ [Nerf 5] Tâche %s (L3+) interceptée → approval_id=%s",
            tool_name, submission.get("approval_id"),
        )
    else:
        result["approval_status"] = "submission_failed"
        result["approval_error"] = submission.get("message", "Erreur inconnue")

    return result


# ------------------------------------------------------------------------------
# HANDLERS HERMES — pilotage des approbations
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
    """Handler Hermes : soumettre manuellement une demande d'approbation."""
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


def _handler_approval_list(status: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : lister les demandes d'approbation."""
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


def _handler_approval_get(approval_id: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : consulter une demande par ID."""
    if not approval_id:
        return {"status": "error", "message": "approval_id obligatoire."}
    try:
        from approval_manager import approval_manager
        req = approval_manager.get_request(approval_id)
        if not req:
            return {"status": "error", "message": f"Demande {approval_id} introuvable."}
        return {
            "status": "success",
            "request": req.to_dict(),
        }
    except Exception as exc:
        logger.error("[Nerf 5] approval_get échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_approval_approve(
    approval_id: str = "",
    admin_user: str = "admin",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Handler Hermes : approuver + exécuter une demande."""
    if not approval_id:
        return {"status": "error", "message": "approval_id obligatoire."}
    try:
        from approval_manager import approval_manager
        result = approval_manager.approve_and_execute(approval_id, admin_user=admin_user)

        # Traçabilité A2A
        _publish_approval_event(
            action="approved",
            approval_id=approval_id,
            extra={"admin_user": admin_user, "result": result.get("status")},
        )

        return result
    except Exception as exc:
        logger.error("[Nerf 5] approval_approve échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_approval_reject(
    approval_id: str = "",
    admin_user: str = "admin",
    reason: str = "Refusé par l'administrateur.",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Handler Hermes : rejeter une demande."""
    if not approval_id:
        return {"status": "error", "message": "approval_id obligatoire."}
    try:
        from approval_manager import approval_manager
        result = approval_manager.reject_request(
            approval_id,
            admin_user=admin_user,
            reason=reason,
        )

        # Traçabilité A2A
        _publish_approval_event(
            action="rejected",
            approval_id=approval_id,
            extra={"admin_user": admin_user, "reason": reason[:200]},
        )

        return result
    except Exception as exc:
        logger.error("[Nerf 5] approval_reject échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE
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
    Active les nerfs Approval en :
      1. Installant le monkey-patch d'interception sur HermesCore._validate_task
      2. Enregistrant 5 nouveaux outils Hermes pour piloter les approbations

    Idempotent. Feature-flag BEK_ENABLE_APPROVAL_NERVES.

    Retourne un rapport d'activation structuré.
    """
    global _original_validate, _interception_active

    if not _is_enabled():
        logger.warning("[Nerf 5] Désactivé via BEK_ENABLE_APPROVAL_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_APPROVAL_NERVES=false",
        }

    # Vérification de la disponibilité d'ApprovalManager
    approval_manager_available = False
    try:
        from approval_manager import approval_manager  # noqa: F401
        approval_manager_available = True
    except ImportError as exc:
        logger.warning(
            "⚠️ [Nerf 5] approval_manager.py indisponible (%s). "
            "Les outils seront enregistrés mais échoueront à l'exécution.",
            exc,
        )

    try:
        from hermes_core import hermes
    except ImportError as exc:
        logger.error("[Nerf 5] Impossible d'importer hermes_core : %s", exc)
        return {"status": "error", "message": str(exc)}

    # Étape 1 : Installation du monkey-patch (une seule fois)
    patch_installed = False
    if not _interception_active:
        try:
            # Sauvegarder la méthode originale (bound method sur l'instance)
            _original_validate = hermes._validate_task

            # Installer la version patchée (bound method sur l'instance)
            hermes._validate_task = types.MethodType(_patched_validate_task, hermes)

            _interception_active = True
            patch_installed = True
            logger.info("🛡️ [Nerf 5] Interception automatique L3+ installée sur Hermes")
        except Exception as exc:
            logger.error("[Nerf 5] Échec installation monkey-patch : %s", exc)
            return {
                "status": "error",
                "message": f"Monkey-patch échoué : {exc}",
            }
    else:
        logger.debug("[Nerf 5] Monkey-patch déjà installé (idempotent)")

    # Étape 2 : Enregistrement des 5 outils Hermes
    activated: List[str] = []
    failed: List[Dict[str, str]] = []

    for tool_name, (handler, risk_level) in APPROVAL_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("🧠 [Nerf 5] Outil approval branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 5] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 5] Activation terminée : %d outils approval branchés, %d échecs. "
        "ApprovalManager disponible : %s | Monkey-patch : %s",
        len(activated), len(failed), approval_manager_available, patch_installed,
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
# DÉSACTIVATION (restauration propre)
# ------------------------------------------------------------------------------

def deactivate_approval_nerves() -> Dict[str, Any]:
    """
    Désactive le monkey-patch et restaure la méthode originale.
    Utile pour tests ou rollback.
    """
    global _original_validate, _interception_active

    if not _interception_active:
        return {"status": "already_inactive"}

    try:
        from hermes_core import hermes
        if _original_validate is not None:
            hermes._validate_task = _original_validate
        _interception_active = False
        _original_validate = None
        logger.info("🛡️ [Nerf 5] Interception désinstallée, comportement legacy restauré")
        return {"status": "ok", "message": "Interception désactivée."}
    except Exception as exc:
        logger.error("[Nerf 5] Échec désactivation : %s", exc)
        return {"status": "error", "message": str(exc)}


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_approval_nerves()
    print("Résultat activation Nerf 5 :", result)

    # Test soumission manuelle
    sub = submit_for_human_approval(
        tool="web_sync",
        args={"query": "test sensitive"},
        risk_level="L4",
        reason="Test manuel Nerf 5",
    )
    print("Test submit_for_human_approval :", sub)