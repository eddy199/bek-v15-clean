# -*- coding: utf-8 -*-
# ==============================================================================
# BEK Hermes Core V4 - HARDENED & DYNAMIC PLANNER + DAG ADAPTER (ADR-001)
# ==============================================================================
# Fichier : hermes_core.py
#
# Responsabilités :
# - Registre sécurisé des tools
# - Planification dynamique via Skill Registry + routage par mots-clés
# - Filtre d'orchestration en deux étapes
# - Gestion des risques L1 -> L5
# - Validation humaine pour L3+
# - Vérification HMAC avant exécution
# - Exécution parallèle via ThreadPoolExecutor et Moteur DAG Haute Densité
# - Worker Guardian système
# ==============================================================================
from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from memory import get_db_connection, replay_pending_syncs
from security_guard import SecurityGuard
from skill_registry import skill_registry
from core.hermes_dag_adapter import HermesDAGOrchestrator

logger = logging.getLogger("bek.hermes")


# ==============================================================================
# CONFIGURATION
# ==============================================================================
DEFAULT_MAX_WORKERS = 10
DEFAULT_TASK_TIMEOUT = 300   # ★ v4.1 — 5 min (Agnes vidéo = 2-3 min)
MIN_WORKERS = 1
MAX_WORKERS = 64
MIN_TASK_TIMEOUT = 1
MAX_TASK_TIMEOUT = 3600
RISK_LEVELS = {"L1", "L2", "L3", "L4", "L5"}
HUMAN_APPROVAL_LEVELS = {"L3", "L4", "L5"}


# ==============================================================================
# TYPES
# ==============================================================================
PrePlanHook = Callable[
    [str, Optional[str]],
    Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]],
]
StepHook = Callable[
    [Dict[str, Any], Dict[str, Any]],
    Tuple[bool, Optional[Dict[str, Any]]],
]
PostPlanHook = Callable[
    [List[Dict[str, Any]], Dict[str, Any]],
    Dict[str, Any],
]


# ==============================================================================
# TOOL MODEL
# ==============================================================================
@dataclass(frozen=True)
class HermesTool:
    name: str
    func: Callable[..., Any]
    risk_level: str = "L1"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Tool name cannot be empty.")
        if not callable(self.func):
            raise TypeError(f"Tool '{self.name}' is not callable.")
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(
                f"Invalid risk level '{self.risk_level}' "
                f"for tool '{self.name}'."
            )


# ==============================================================================
# RESULT MODEL
# ==============================================================================
@dataclass
class ToolResult:
    task_id: str
    trace_id: str
    tool: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    execution_ms: float = 0.0
    timed_out: bool = False
    validation_failed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "tool": self.tool,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "error_type": self.error_type,
            "execution_ms": self.execution_ms,
            "timed_out": self.timed_out,
            "validation_failed": self.validation_failed,
        }


# ==============================================================================
# HERMES CORE
# ==============================================================================
class HermesCore:
    def __init__(
        self,
        max_workers: int = DEFAULT_MAX_WORKERS,
        task_timeout: int = DEFAULT_TASK_TIMEOUT,
        security_guard: Optional[SecurityGuard] = None,
    ) -> None:
        # ----- Configuration validation -----
        if (
            not isinstance(max_workers, int)
            or isinstance(max_workers, bool)
            or not MIN_WORKERS <= max_workers <= MAX_WORKERS
        ):
            raise ValueError(
                f"max_workers must be between "
                f"{MIN_WORKERS} and {MAX_WORKERS}."
            )

        if (
            not isinstance(task_timeout, int)
            or isinstance(task_timeout, bool)
            or not MIN_TASK_TIMEOUT <= task_timeout <= MAX_TASK_TIMEOUT
        ):
            raise ValueError(
                f"task_timeout must be between "
                f"{MIN_TASK_TIMEOUT} and {MAX_TASK_TIMEOUT} seconds."
            )

        # ----- Tool registry -----
        self.tools: Dict[str, HermesTool] = {}
        self._tool_lock = threading.RLock()

        # ----- Security Guard -----
        self.security_guard = security_guard
        if self.security_guard is None:
            try:
                self.security_guard = SecurityGuard()
            except Exception as exc:
                logger.exception(
                    "Hermes SecurityGuard initialization failed: %s", exc
                )
                self.security_guard = None

        # ----- Executor -----
        self.max_workers = max_workers
        self.task_timeout = task_timeout
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="bek-hermes",
        )

        # ----- [ADR-001] Moteur d'exécution DAG Haute Densité CPU -----
        self.dag_orchestrator = HermesDAGOrchestrator(max_workers=max_workers)

        # ----- Runtime state -----
        self._worker_lock = threading.Lock()
        self._workers_started = False
        self._shutdown = False
        self.current_provider: Optional[str] = None
        self.current_model: Optional[str] = None

        # ----- Hooks -----
        self._pre_plan_hooks: List[PrePlanHook] = []
        self._step_hooks: List[StepHook] = []
        self._post_plan_hooks: List[PostPlanHook] = []

        logger.info(
            "Hermes initialized | workers=%s | timeout=%ss | security_guard=%s",
            max_workers,
            task_timeout,
            self.security_guard is not None,
        )

        # ----- Native tools -----
        self._register_default_tools()

        # ----- Security hooks -----
        self.register_pre_plan_hook(self._two_stage_orchestration_filter)
        self.register_pre_plan_hook(self._fable_policy_guard)

    # ==========================================================================
    # DEFAULT TOOLS
    # ==========================================================================
    def _register_default_tools(self) -> None:
        """Enregistre les outils natifs de base."""
        self.register_tool(
            "default_llm",
            lambda query="", **kwargs: {
                "response": f"Exécution terminée pour : {query}"
            },
            risk_level="L1",
        )
        self.register_tool(
            "neon_audit",
            lambda **kwargs: {
                "status": "Neon DB audit demandé",
                "tables": [
                    "companies",
                    "contacts",
                    "opportunities",
                    "matrix_sub_crms",
                    "sync_log",
                ],
            },
            risk_level="L1",
        )
        self.register_tool(
            "web_sync",
            lambda query="", **kwargs: {
                "status": "success",
                "synced_query": query,
            },
            risk_level="L3",
        )
        self.register_tool(
            "generate_image",
            lambda prompt="", **kwargs: {
                "status": "error",
                "message": "En attente de montage via app.py",
            },
            risk_level="L1",
        )
        self.register_tool(
            "edit_image",
            lambda image_paths=None, prompt="", **kwargs: {
                "status": "error",
                "message": "En attente de montage via app.py",
            },
            risk_level="L1",
        )
        self.register_tool(
            "generate_video",
            lambda prompt="", **kwargs: {
                "status": "error",
                "message": "En attente de montage via app.py",
            },
            risk_level="L1",
        )
        self.register_tool(
            "edit_video",
            lambda video_paths=None, prompt="", **kwargs: {
                "status": "error",
                "message": "En attente de montage via app.py",
            },
            risk_level="L1",
        )

    # ==========================================================================
    # SECURITY FILTERS
    # ==========================================================================
    @staticmethod
    def _two_stage_orchestration_filter(
        objective: str,
        trace_id: Optional[str],
    ) -> Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]]:
        if not objective or not objective.strip():
            return (False, "Objectif vide rejeté par l'orchestrateur.", [])

        obj_lower = objective.lower()
        dangerous_keywords = ("rm -rf", "drop database", "format c:", "del /s /q")
        if any(keyword in obj_lower for keyword in dangerous_keywords):
            logger.warning(
                "Filtre orchestration : action destructive bloquée | trace=%s",
                trace_id,
            )
            return (
                False,
                "Action destructive bloquée par le filtre de sécurité.",
                [],
            )
        return True, "Planification validée", None

    @staticmethod
    def _fable_policy_guard(
        objective: str,
        trace_id: Optional[str],
    ) -> Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]]:
        if not objective:
            return True, "OK", None
        obj_lower = objective.lower()
        forbidden_terms = ("api_key=", "password=", "secret=", "bearer ", "sk-")
        if any(term in obj_lower for term in forbidden_terms):
            logger.warning(
                "Violation sécurité : injection de secrets détectée | trace=%s",
                trace_id,
            )
            return (
                False,
                "Les secrets et clés d'API ne doivent jamais "
                "être inclus dans les objectifs.",
                [],
            )
        return True, "Politique respectée", None

    # ==========================================================================
    # HOOKS
    # ==========================================================================
    def register_pre_plan_hook(self, hook: PrePlanHook) -> None:
        if not callable(hook):
            raise TypeError("Pre-plan hook must be callable.")
        self._pre_plan_hooks.append(hook)

    def register_step_hook(self, hook: StepHook) -> None:
        if not callable(hook):
            raise TypeError("Step hook must be callable.")
        self._step_hooks.append(hook)

    def register_post_plan_hook(self, hook: PostPlanHook) -> None:
        if not callable(hook):
            raise TypeError("Post-plan hook must be callable.")
        self._post_plan_hooks.append(hook)

    # ==========================================================================
    # IDENTIFIERS
    # ==========================================================================
    @staticmethod
    def create_trace_id() -> str:
        return f"BEK-TRC-{uuid.uuid4().hex[:12].upper()}"

    @staticmethod
    def create_task_id() -> str:
        return f"BEK-TASK-{uuid.uuid4().hex[:12].upper()}"

    @staticmethod
    def create_job_id() -> str:
        return f"BEK-JOB-{uuid.uuid4().hex[:12].upper()}"

    # ==========================================================================
    # TOOL MANAGEMENT
    # ==========================================================================
    def register_tool(
        self,
        name: str,
        func: Callable[..., Any],
        risk_level: str = "L1",
    ) -> None:
        if self._shutdown:
            raise RuntimeError("Cannot register tools after Hermes shutdown.")
        tool = HermesTool(name=name, func=func, risk_level=risk_level)
        with self._tool_lock:
            self.tools[name] = tool
        logger.info("Hermes tool registered | name=%s | risk=%s", name, risk_level)

    def unregister_tool(self, name: str) -> bool:
        if not isinstance(name, str):
            return False
        with self._tool_lock:
            if name in self.tools:
                del self.tools[name]
                return True
            return False

    def list_tools(self) -> List[Dict[str, str]]:
        with self._tool_lock:
            return [
                {"name": tool.name, "risk_level": tool.risk_level}
                for tool in self.tools.values()
            ]

    def _get_tool(self, tool_name: str) -> Optional[HermesTool]:
        with self._tool_lock:
            return self.tools.get(tool_name)

    # ==========================================================================
    # KEYWORD PLANNER
    # ==========================================================================
    def plan_from_keywords(
        self,
        objective: str,
        trace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not isinstance(objective, str) or not objective.strip():
            return []

        trace_id = trace_id or self.create_trace_id()

        # ----- Pre-plan security hooks -----
        for hook in self._pre_plan_hooks:
            try:
                allowed, reason, override_tasks = hook(objective, trace_id)
                if not allowed:
                    logger.warning("Pre-Plan Hook a rejeté l'objectif : %s", reason)
                    return []
                if override_tasks is not None:
                    return override_tasks
            except Exception as hook_err:
                logger.error(
                    "Erreur Pre-Plan Hook : %s\n%s",
                    hook_err,
                    traceback.format_exc(),
                )

        tasks: List[Dict[str, Any]] = []
        obj_lower = objective.lower().strip()

        # ----- Skill Registry -----
        try:
            best_skills = skill_registry.search_skills(objective, limit=2)
        except Exception as exc:
            logger.error("Skill Registry search failed: %s", exc)
            best_skills = []

        if best_skills:
            top_skill = best_skills[0]
            if top_skill.required_tools:
                for req_tool in top_skill.required_tools:
                    tasks.append(
                        {
                            "task_id": self.create_task_id(),
                            "tool": req_tool,
                            "args": {
                                "query": objective,
                                "skill": top_skill.name,
                                "prompt": top_skill.prompt[:400],
                            },
                            "trace_id": trace_id,
                        }
                    )
            else:
                tasks.append(
                    {
                        "task_id": self.create_task_id(),
                        "tool": "default_llm",
                        "args": {
                            "query": objective,
                            "skill": top_skill.name,
                            "prompt": top_skill.prompt[:400],
                        },
                        "trace_id": trace_id,
                    }
                )

        # ----- Native keyword routing -----
        if not tasks:
            if "modifier" in obj_lower and any(
                k in obj_lower for k in ("image", "photo", "dessin")
            ):
                tasks.append(
                    {
                        "task_id": self.create_task_id(),
                        "tool": "edit_image",
                        "args": {"prompt": objective},
                        "trace_id": trace_id,
                    }
                )
            elif "modifier" in obj_lower and any(
                k in obj_lower for k in ("vidéo", "video", "film")
            ):
                tasks.append(
                    {
                        "task_id": self.create_task_id(),
                        "tool": "edit_video",
                        "args": {"prompt": objective},
                        "trace_id": trace_id,
                    }
                )
            elif any(
                k in obj_lower
                for k in ("vidéo", "video", "film", "génère une vidéo")
            ):
                tasks.append(
                    {
                        "task_id": self.create_task_id(),
                        "tool": "generate_video",
                        "args": {"prompt": objective},
                        "trace_id": trace_id,
                    }
                )
            elif any(
                k in obj_lower
                for k in ("image", "photo", "dessin", "génère une image")
            ):
                tasks.append(
                    {
                        "task_id": self.create_task_id(),
                        "tool": "generate_image",
                        "args": {"prompt": objective},
                        "trace_id": trace_id,
                    }
                )
            elif any(
                k in obj_lower
                for k in ("prospect", "web", "cherche", "recherche")
            ):
                tasks.append(
                    {
                        "task_id": self.create_task_id(),
                        "tool": "web_sync",
                        "args": {"query": objective},
                        "trace_id": trace_id,
                    }
                )
            elif any(
                k in obj_lower
                for k in ("crm", "neon", "base", "database", "sql")
            ):
                tasks.append(
                    {
                        "task_id": self.create_task_id(),
                        "tool": "neon_audit",
                        "args": {},
                        "trace_id": trace_id,
                    }
                )
            else:
                tasks.append(
                    {
                        "task_id": self.create_task_id(),
                        "tool": "default_llm",
                        "args": {"query": objective},
                        "trace_id": trace_id,
                    }
                )

        return tasks

    # Compatibilité historique
    def goap_planner(
        self,
        objective: str,
        trace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self.plan_from_keywords(objective, trace_id=trace_id)

    # ==========================================================================
    # SECURITY
    # ==========================================================================
    @staticmethod
    def requires_human_approval(tool: HermesTool) -> bool:
        return tool.risk_level in HUMAN_APPROVAL_LEVELS

    def security_check(
        self,
        tool: HermesTool,
        args: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = args or {}

        if self.requires_human_approval(tool):
            return {
                "decision": "REQUIRE_HUMAN",
                "risk_level": tool.risk_level,
                "reason": "Validation humaine requise.",
            }

        if self.security_guard is None:
            return {
                "decision": "DENY",
                "risk_level": tool.risk_level,
                "reason": "SecurityGuard indisponible.",
            }

        try:
            ok, message, envelope = self.security_guard.validate_and_certify(
                tool.name, args
            )
        except Exception as exc:
            logger.exception("SecurityGuard exception | tool=%s", tool.name)
            return {
                "decision": "DENY",
                "risk_level": tool.risk_level,
                "reason": f"SecurityGuard exception: {type(exc).__name__}",
            }

        if not ok:
            return {
                "decision": "DENY",
                "risk_level": tool.risk_level,
                "reason": message,
            }

        if not envelope:
            return {
                "decision": "DENY",
                "risk_level": tool.risk_level,
                "reason": "Enveloppe de sécurité absente.",
            }

        verify_envelope = getattr(self.security_guard, "verify_envelope", None)
        if not callable(verify_envelope):
            return {
                "decision": "DENY",
                "risk_level": tool.risk_level,
                "reason": "SecurityGuard incompatible : verify_envelope() manquant.",
            }

        try:
            sig_ok, sig_msg = verify_envelope(envelope)
        except Exception as exc:
            logger.exception("verify_envelope exception | tool=%s", tool.name)
            return {
                "decision": "DENY",
                "risk_level": tool.risk_level,
                "reason": f"verify_envelope exception: {type(exc).__name__}",
            }

        if not sig_ok:
            logger.error(
                "Enveloppe HMAC invalide | tool=%s | reason=%s",
                tool.name,
                sig_msg,
            )
            return {
                "decision": "DENY",
                "risk_level": tool.risk_level,
                "reason": f"Signature HMAC invalide : {sig_msg}",
            }

        return {
            "decision": "ALLOW",
            "risk_level": tool.risk_level,
            "reason": message,
            "envelope": envelope,
        }

    # ==========================================================================
    # TASK VALIDATION
    # ==========================================================================
    def _validate_task(
        self,
        task: Any,
        trace_id: str,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(task, dict):
            return {
                "status": "INVALID_TASK",
                "message": "Task must be a dictionary.",
                "trace_id": trace_id,
            }

        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            task_id = self.create_task_id()

        tool_name = task.get("tool")
        if not isinstance(tool_name, str) or not tool_name.strip():
            return {
                "status": "INVALID_TASK",
                "message": "Missing tool name.",
                "trace_id": trace_id,
                "task_id": task_id,
            }
        tool_name = tool_name.strip()

        args = task.get("args", {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return {
                "status": "INVALID_TASK",
                "message": "Task args must be a dictionary.",
                "trace_id": trace_id,
                "task_id": task_id,
                "tool": tool_name,
            }

        tool = self._get_tool(tool_name)
        if tool is None:
            return {
                "status": "UNKNOWN_TOOL",
                "message": f"Unknown tool: {tool_name}",
                "trace_id": trace_id,
                "task_id": task_id,
                "tool": tool_name,
            }

        security = self.security_check(tool, args)
        decision = security["decision"]
        if decision != "ALLOW":
            status = (
                "SECURITY_APPROVAL_REQUIRED"
                if decision == "REQUIRE_HUMAN"
                else "SECURITY_DENIED"
            )
            return {
                "status": status,
                "message": security["reason"],
                "trace_id": trace_id,
                "task_id": task_id,
                "tool": tool_name,
                "risk_level": tool.risk_level,
                "security_decision": decision,
            }

        return {
            "task_id": task_id,
            "trace_id": trace_id,
            "tool": tool_name,
            "args": args,
            "risk_level": tool.risk_level,
            "security_decision": "ALLOW",
            "security_envelope": security.get("envelope"),
        }

    # ==========================================================================
    # PARALLEL DISPATCH
    # ==========================================================================
    def dispatch_parallel(
        self,
        task_list: List[Dict[str, Any]],
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        trace_id = trace_id or self.create_trace_id()
        start_time = time.monotonic()

        if self._shutdown:
            return {
                "trace_id": trace_id,
                "execution_ms": 0,
                "results": {},
                "status": "HERMES_SHUTDOWN",
            }

        if not isinstance(task_list, list):
            return {
                "trace_id": trace_id,
                "execution_ms": 0,
                "results": {},
                "status": "INVALID_TASK_LIST",
            }

        if not task_list:
            return {
                "trace_id": trace_id,
                "execution_ms": 0,
                "results": {},
                "status": "NO_TASKS",
            }

        validated_tasks: List[Dict[str, Any]] = []
        invalid_tasks: List[Dict[str, Any]] = []

        for task in task_list:
            validated = self._validate_task(task, trace_id)
            if validated is None:
                continue
            if validated.get("status"):
                invalid_tasks.append(validated)
            else:
                validated_tasks.append(validated)

        def invalid_result(inv: Dict[str, Any]) -> Dict[str, Any]:
            inv_task_id = inv.get("task_id") or self.create_task_id()
            return ToolResult(
                task_id=inv_task_id,
                trace_id=trace_id,
                tool=inv.get("tool", "unknown"),
                success=False,
                error=inv.get("message"),
                error_type=inv.get("status"),
                validation_failed=True,
            ).to_dict()

        if not validated_tasks:
            results_invalid = {}
            for inv in invalid_tasks:
                inv_task_id = inv.get("task_id") or self.create_task_id()
                results_invalid[inv_task_id] = invalid_result(inv)
            return {
                "trace_id": trace_id,
                "execution_ms": round((time.monotonic() - start_time) * 1000, 2),
                "results": results_invalid,
                "status": "ALL_TASKS_INVALID",
                "task_count": len(results_invalid),
                "success_count": 0,
                "failure_count": len(results_invalid),
                "timeout_count": 0,
                "invalid_count": len(results_invalid),
            }

        futures = []
        for task in validated_tasks:
            task_id = task["task_id"]
            tool_name = task["tool"]
            args = task["args"]
            tool = self._get_tool(tool_name)
            if tool is None:
                invalid_tasks.append(
                    {
                        "status": "UNKNOWN_TOOL",
                        "message": f"Unknown tool: {tool_name}",
                        "task_id": task_id,
                        "tool": tool_name,
                    }
                )
                continue
            try:
                future = self.executor.submit(
                    self._execute_tool, tool, args, trace_id, task_id
                )
                futures.append((task_id, tool_name, future, None))
            except RuntimeError as exc:
                futures.append((task_id, tool_name, None, exc))

        results: Dict[str, Dict[str, Any]] = {}

        for inv in invalid_tasks:
            inv_task_id = inv.get("task_id") or self.create_task_id()
            results[inv_task_id] = invalid_result(inv)

        for (task_id, tool_name, future, submit_error) in futures:
            if future is None:
                res_dict = ToolResult(
                    task_id=task_id,
                    trace_id=trace_id,
                    tool=tool_name,
                    success=False,
                    error=str(submit_error),
                    error_type=type(submit_error).__name__,
                ).to_dict()
            else:
                try:
                    result = future.result(timeout=self.task_timeout)
                    if isinstance(result, ToolResult):
                        res_dict = result.to_dict()
                    else:
                        res_dict = ToolResult(
                            task_id=task_id,
                            trace_id=trace_id,
                            tool=tool_name,
                            success=True,
                            data=result,
                        ).to_dict()
                except concurrent.futures.TimeoutError:
                    future.cancel()
                    res_dict = ToolResult(
                        task_id=task_id,
                        trace_id=trace_id,
                        tool=tool_name,
                        success=False,
                        error="TASK_TIMEOUT",
                        error_type="TimeoutError",
                        timed_out=True,
                    ).to_dict()
                except Exception as exc:
                    logger.exception(
                        "Task execution failed | tool=%s | task=%s",
                        tool_name,
                        task_id,
                    )
                    res_dict = ToolResult(
                        task_id=task_id,
                        trace_id=trace_id,
                        tool=tool_name,
                        success=False,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    ).to_dict()

            current_task_spec = next(
                (t for t in validated_tasks if t["task_id"] == task_id), {}
            )
            for step_hook in self._step_hooks:
                try:
                    ok, replacement_res = step_hook(current_task_spec, res_dict)
                    if replacement_res is not None:
                        res_dict = replacement_res
                except Exception as step_err:
                    logger.error("Erreur Step Hook : %s", step_err)

            results[task_id] = res_dict

        execution_ms = round((time.monotonic() - start_time) * 1000, 2)
        success_count = sum(1 for r in results.values() if r.get("success") is True)
        failure_count = len(results) - success_count
        timed_out_count = sum(
            1 for r in results.values() if r.get("timed_out") is True
        )
        invalid_count = sum(
            1 for r in results.values() if r.get("validation_failed") is True
        )

        if not results:
            status = "FAILED"
        elif invalid_count == len(results):
            status = "ALL_TASKS_INVALID"
        elif success_count == len(results):
            status = "SUCCESS"
        elif timed_out_count == len(results):
            status = "TIMEOUT"
        elif success_count > 0:
            status = "PARTIAL_SUCCESS"
        else:
            status = "FAILED"

        final_payload = {
            "trace_id": trace_id,
            "execution_ms": execution_ms,
            "results": results,
            "status": status,
            "task_count": len(results),
            "success_count": success_count,
            "failure_count": failure_count,
            "timeout_count": timed_out_count,
            "invalid_count": invalid_count,
        }

        for post_hook in self._post_plan_hooks:
            try:
                updated_payload = post_hook(validated_tasks, final_payload)
                if isinstance(updated_payload, dict):
                    final_payload = updated_payload
            except Exception as post_err:
                logger.error("Erreur Post-Plan Hook : %s", post_err)

        return final_payload

    # ==========================================================================
    # DAG PARALLEL DISPATCH (ADR-001) — v2 corrigée
    # ==========================================================================
    def dispatch_dag_plan(
        self,
        goal_plan: Dict[str, Any],
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Exécute un plan GOAP structuré en DAG avec parallélisme par vagues.

        Correction vs v1 :
          - Agrégation de status réelle (SUCCESS / PARTIAL_SUCCESS / FAILED).
          - Cycle détecté → INVALID_DAG au lieu de crash générique.
          - Handler DAG factorisé via _make_dag_handler.
          - Payload final cohérent avec dispatch_parallel.
        """
        trace_id = trace_id or self.create_trace_id()
        start_time = time.monotonic()

        if self._shutdown:
            return {
                "trace_id": trace_id,
                "status": "HERMES_SHUTDOWN",
                "execution_ms": 0,
                "results": {},
            }

        if not isinstance(goal_plan, dict) or "steps" not in goal_plan:
            return {
                "trace_id": trace_id,
                "status": "INVALID_GOAL_PLAN",
                "execution_ms": 0,
                "results": {},
                "error": "goal_plan doit être un dict avec une clé 'steps'.",
            }

        if not goal_plan.get("steps"):
            return {
                "trace_id": trace_id,
                "status": "NO_STEPS",
                "execution_ms": 0,
                "results": {},
            }

        # ----- 1. Construction des handlers à partir des tools enregistrés -----
        action_handlers: Dict[str, Callable[..., Any]] = {}

        with self._tool_lock:
            for name, tool in self.tools.items():
                action_handlers[name] = self._make_dag_handler(tool, trace_id)

        # ----- 2. Exécution DAG -----
        try:
            dag_results = self.dag_orchestrator.execute_goal_plan(
                goal_plan, action_handlers
            )
        except ValueError as exc:
            # Cas : cycle détecté par l'orchestrateur
            logger.error("Plan DAG invalide : %s", exc)
            return {
                "trace_id": trace_id,
                "status": "INVALID_DAG",
                "execution_ms": round((time.monotonic() - start_time) * 1000, 2),
                "results": {},
                "error": str(exc),
            }
        except Exception as exc:
            logger.exception("Erreur inattendue lors de l'exécution DAG")
            return {
                "trace_id": trace_id,
                "status": "FAILED",
                "execution_ms": round((time.monotonic() - start_time) * 1000, 2),
                "results": {},
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

        # ----- 3. Agrégation de status -----
        execution_ms = round((time.monotonic() - start_time) * 1000, 2)
        payload = self._aggregate_dag_results(
            dag_results, trace_id, execution_ms, goal_plan
        )

        # ----- 4. Post-plan hooks (persistance Reflex-Loop) -----
        for post_hook in self._post_plan_hooks:
            try:
                updated = post_hook(
                    [
                        {"action": s.get("action"), "id": s.get("id")}
                        for s in goal_plan.get("steps", [])
                    ],
                    payload,
                )
                if isinstance(updated, dict):
                    payload = updated
            except Exception as post_err:
                logger.error("Erreur Post-Plan Hook (DAG) : %s", post_err)

        return payload

    # --------------------------------------------------------------------------
    def _make_dag_handler(
        self,
        tool: HermesTool,
        trace_id: str,
    ) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        """
        Fabrique un handler DAG pour un outil Hermes.
        Combine security_check + exécution en une seule passe.
        """

        def handler(params: Dict[str, Any]) -> Dict[str, Any]:
            # --- Security check ---
            try:
                sec = self.security_check(tool, params or {})
            except Exception as exc:
                logger.exception(
                    "Security check exceptionnel | tool=%s", tool.name
                )
                return {
                    "status": "FAILED",
                    "tool": tool.name,
                    "success": False,
                    "error": f"security_check exception: {type(exc).__name__}",
                    "error_type": "SECURITY_EXCEPTION",
                }

            if sec.get("decision") != "ALLOW":
                return {
                    "status": "FAILED",
                    "tool": tool.name,
                    "success": False,
                    "error": sec.get("reason", "Security denied"),
                    "error_type": "SECURITY_DENIED",
                    "risk_level": tool.risk_level,
                    "security_decision": sec.get("decision"),
                }

            # --- Exécution ---
            task_id = self.create_task_id()
            result = self._execute_tool(tool, params or {}, trace_id, task_id)
            res_dict = result.to_dict()
            # Normalise pour cohérence DAG
            res_dict.setdefault(
                "status", "OK" if res_dict.get("success") else "FAILED"
            )
            return res_dict

        return handler

    # --------------------------------------------------------------------------
    @staticmethod
    def _aggregate_dag_results(
        dag_results: Dict[str, Any],
        trace_id: str,
        execution_ms: float,
        goal_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Agrège les résultats DAG en un payload cohérent avec dispatch_parallel.
        """
        if not dag_results:
            return {
                "trace_id": trace_id,
                "status": "EMPTY",
                "execution_ms": execution_ms,
                "results": {},
                "task_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "skipped_count": 0,
                "timeout_count": 0,
                "plan_id": goal_plan.get("plan_id"),
            }

        success = 0
        failed = 0
        skipped = 0
        timeout = 0

        for node_id, res in dag_results.items():
            if not isinstance(res, dict):
                success += 1
                continue
            status = res.get("status", "")
            if status in ("OK", "SUCCESS") or res.get("success") is True:
                success += 1
            elif status == "SKIPPED":
                skipped += 1
            elif status == "TIMEOUT":
                timeout += 1
            else:
                failed += 1

        total = len(dag_results)
        if success == total:
            overall = "SUCCESS"
        elif success == 0 and (failed + timeout) == total:
            overall = "FAILED"
        elif success == 0 and skipped == total:
            overall = "ALL_SKIPPED"
        else:
            overall = "PARTIAL_SUCCESS"

        return {
            "trace_id": trace_id,
            "status": overall,
            "execution_ms": execution_ms,
            "results": dag_results,
            "plan_id": goal_plan.get("plan_id"),
            "task_count": total,
            "success_count": success,
            "failure_count": failed,
            "skipped_count": skipped,
            "timeout_count": timeout,
        }

    # ==========================================================================
    # TOOL EXECUTION
    # ==========================================================================
    @staticmethod
    def _execute_tool(
        tool: HermesTool,
        args: Dict[str, Any],
        trace_id: str,
        task_id: str,
    ) -> ToolResult:
        start_time = time.monotonic()
        try:
            data = tool.func(**args)
            execution_ms = round((time.monotonic() - start_time) * 1000, 2)
            return ToolResult(
                task_id=task_id,
                trace_id=trace_id,
                tool=tool.name,
                success=True,
                data=data,
                execution_ms=execution_ms,
            )
        except Exception as exc:
            execution_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.exception("Erreur d'exécution de l'outil %s", tool.name)
            return ToolResult(
                task_id=task_id,
                trace_id=trace_id,
                tool=tool.name,
                success=False,
                error=str(exc),
                error_type=type(exc).__name__,
                execution_ms=execution_ms,
            )

    # ==========================================================================
    # SIMPLE DISPATCH
    # ==========================================================================
    def dispatch(
        self,
        tool_name: str,
        args: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.dispatch_parallel(
            [
                {
                    "task_id": self.create_task_id(),
                    "tool": tool_name,
                    "args": args or {},
                }
            ],
            trace_id=trace_id,
        )

    # ==========================================================================
    # RUNTIME STATUS
    # ==========================================================================
    def runtime_status(self) -> Dict[str, Any]:
        return {
            "status": "shutdown" if self._shutdown else "operational",
            "security_guard_active": self.security_guard is not None,
            "tools": self.list_tools(),
            "tool_count": len(self.tools),
            "provider": self.current_provider,
            "model": self.current_model,
            "max_workers": self.max_workers,
            "task_timeout": self.task_timeout,
            "workers_started": self._workers_started,
            "active_hooks": {
                "pre_plan": len(self._pre_plan_hooks),
                "step_replan": len(self._step_hooks),
                "post_plan": len(self._post_plan_hooks),
            },
        }

    # ==========================================================================
    # PROVIDER CONTEXT
    # ==========================================================================
    def set_provider_context(
        self,
        provider: Optional[str],
        model: Optional[str],
    ) -> None:
        self.current_provider = (
            provider.strip()
            if isinstance(provider, str) and provider.strip()
            else None
        )
        self.current_model = (
            model.strip()
            if isinstance(model, str) and model.strip()
            else None
        )

    # ==========================================================================
    # SHUTDOWN
    # ==========================================================================
    def shutdown(self, wait: bool = True) -> None:
        if self._shutdown:
            return
        logger.info("Hermes executor shutting down.")
        self._shutdown = True
        self.executor.shutdown(wait=wait, cancel_futures=True)

        # Fermeture propre du orchestrateur DAG
        try:
            self.dag_orchestrator.shutdown()
        except Exception:
            pass


# ==============================================================================
# GLOBAL SINGLETON
# ==============================================================================
hermes = HermesCore()


# ==============================================================================
# SYSTEM JOBS
# ==============================================================================
def init_system_jobs_table() -> None:
    conn = get_db_connection()
    if not conn:
        return
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS system_jobs (
                job_id VARCHAR(64) PRIMARY KEY,
                task_name TEXT NOT NULL,
                status VARCHAR(32) NOT NULL,
                retry_count INT DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ==============================================================================
# BACKGROUND GUARDIAN
# ==============================================================================
def background_guardian_worker() -> None:
    try:
        init_system_jobs_table()
    except Exception:
        logger.exception("Unable to initialize system_jobs table.")

    while not hermes._shutdown:
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            if conn:
                job_id = hermes.create_job_id()
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO system_jobs (job_id, task_name, status, retry_count)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (job_id, "matrix_silent_audit", "RUNNING", 0),
                )
                conn.commit()

                try:
                    replayed = replay_pending_syncs(limit=25)
                    if replayed > 0:
                        logger.info(
                            "Guardian a synchronisé %d vecteurs orphelins "
                            "vers Pinecone.",
                            replayed,
                        )
                except Exception:
                    logger.exception("Guardian replay_pending_syncs failed.")

                for _ in range(20):
                    if hermes._shutdown:
                        break
                    time.sleep(0.1)

                if hermes._shutdown:
                    break

                cur.execute(
                    "UPDATE system_jobs SET status = %s WHERE job_id = %s;",
                    ("SUCCESS", job_id),
                )
                conn.commit()

            for _ in range(180):
                if hermes._shutdown:
                    break
                time.sleep(10)

        except Exception:
            logger.exception("Hermes background guardian error.")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            for _ in range(60):
                if hermes._shutdown:
                    break
                time.sleep(1)
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


def start_background_workers() -> None:
    with hermes._worker_lock:
        if hermes._shutdown:
            return
        if hermes._workers_started:
            return
        thread = threading.Thread(
            target=background_guardian_worker,
            name="bek-hermes-guardian",
            daemon=True,
        )
        thread.start()
        hermes._workers_started = True


# ==============================================================================
# PUBLIC API
# ==============================================================================
def register_tool(
    name: str,
    func: Callable[..., Any],
    risk_level: str = "L1",
) -> None:
    hermes.register_tool(name=name, func=func, risk_level=risk_level)


def unregister_tool(name: str) -> bool:
    return hermes.unregister_tool(name)


def list_tools() -> List[Dict[str, str]]:
    return hermes.list_tools()


def plan_from_keywords(objective: str) -> List[Dict[str, Any]]:
    return hermes.plan_from_keywords(objective)


def goap_planner(objective: str) -> List[Dict[str, Any]]:
    return hermes.goap_planner(objective)


def dispatch_parallel(task_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    return hermes.dispatch_parallel(task_list)


def dispatch_dag_plan(goal_plan: Dict[str, Any]) -> Dict[str, Any]:
    return hermes.dispatch_dag_plan(goal_plan)


def dispatch(
    tool_name: str,
    args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return hermes.dispatch(tool_name=tool_name, args=args)


def runtime_status() -> Dict[str, Any]:
    return hermes.runtime_status()


def set_provider_context(
    provider: Optional[str],
    model: Optional[str],
) -> None:
    hermes.set_provider_context(provider=provider, model=model)


def shutdown(wait: bool = True) -> None:
    hermes.shutdown(wait=wait)