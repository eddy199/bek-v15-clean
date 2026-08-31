"""
BEK Hermes Core V2 - HARDENED & DYNAMIC GOAP WITH PLAN ACTION HOOKS
-------------------------------------------------------------------
Noyau d'orchestration Hermes / GOAP / Workers.

Responsabilités :
- registre sécurisé des tools ;
- planification GOAP dynamique via Skill Registry ;
- hooks de cycle de vie de plan (Pre-Plan, Step/Re-Plan, Post-Plan) ;
- validation stricte des tâches ;
- contrôle SecurityGuard avant exécution ;
- gestion des risques L1 -> L5 ;
- demande de validation humaine pour L3/L4/L5 ;
- exécution parallèle ;
- traçabilité task_id / trace_id ;
- timeout applicatif ;
- gestion propre du shutdown ;
- worker Guardian système.

IMPORTANT :
- Hermes n'exécute aucune commande système directement.
- Hermes ne contourne jamais SecurityGuard.
- SecurityGuard reste la couche de certification.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from memory import get_db_connection
from security_guard import SecurityGuard
from skill_registry import skill_registry


logger = logging.getLogger("bek.hermes")


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_MAX_WORKERS = 10
DEFAULT_TASK_TIMEOUT = 15

MIN_WORKERS = 1
MAX_WORKERS = 64

MIN_TASK_TIMEOUT = 1
MAX_TASK_TIMEOUT = 3600

RISK_LEVELS = {"L1", "L2", "L3", "L4", "L5"}

# Ces niveaux ne doivent jamais être exécutés automatiquement.
HUMAN_APPROVAL_LEVELS = {"L3", "L4", "L5"}


# ============================================================
# TOOL MODEL
# ============================================================

@dataclass(frozen=True)
class HermesTool:
    name: str
    func: Callable[..., Any]
    risk_level: str = "L1"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Tool name cannot be empty.")

        if not callable(self.func):
            raise TypeError(
                f"Tool '{self.name}' is not callable."
            )

        if self.risk_level not in RISK_LEVELS:
            raise ValueError(
                f"Invalid risk level '{self.risk_level}' "
                f"for tool '{self.name}'."
            )


# ============================================================
# RESULT MODEL
# ============================================================

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
        }


# ============================================================
# PLAN HOOK TYPES
# ============================================================

PrePlanHook = Callable[[str, Optional[str]], Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]]]
StepHook = Callable[[Dict[str, Any], Dict[str, Any]], Tuple[bool, Optional[Dict[str, Any]]]]
PostPlanHook = Callable[[List[Dict[str, Any]], Dict[str, Any]], Dict[str, Any]]


# ============================================================
# HERMES CORE
# ============================================================

class HermesCore:

    def __init__(
        self,
        max_workers: int = DEFAULT_MAX_WORKERS,
        task_timeout: int = DEFAULT_TASK_TIMEOUT,
        security_guard: Optional[SecurityGuard] = None,
    ) -> None:

        if not isinstance(max_workers, int):
            raise TypeError("max_workers must be an integer.")

        if not MIN_WORKERS <= max_workers <= MAX_WORKERS:
            raise ValueError(
                f"max_workers must be between "
                f"{MIN_WORKERS} and {MAX_WORKERS}."
            )

        if not isinstance(task_timeout, int):
            raise TypeError("task_timeout must be an integer.")

        if not MIN_TASK_TIMEOUT <= task_timeout <= MAX_TASK_TIMEOUT:
            raise ValueError(
                f"task_timeout must be between "
                f"{MIN_TASK_TIMEOUT} and {MAX_TASK_TIMEOUT} seconds."
            )

        self.tools: Dict[str, HermesTool] = {}
        self._tool_lock = threading.RLock()

        self.security_guard = security_guard

        if self.security_guard is None:
            try:
                self.security_guard = SecurityGuard()
            except Exception as exc:
                logger.error(
                    "Hermes SecurityGuard initialization failed: %s",
                    exc,
                )
                self.security_guard = None

        self.max_workers = max_workers
        self.task_timeout = task_timeout

        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="bek-hermes",
        )

        self._worker_lock = threading.Lock()
        self._workers_started = False
        self._shutdown = False

        self.current_provider: Optional[str] = None
        self.current_model: Optional[str] = None

        # Hooks de Plan d'Action
        self._pre_plan_hooks: List[PrePlanHook] = []
        self._step_hooks: List[StepHook] = []
        self._post_plan_hooks: List[PostPlanHook] = []

        logger.info(
            "Hermes initialized | workers=%s | timeout=%ss | "
            "security_guard=%s",
            max_workers,
            task_timeout,
            self.security_guard is not None,
        )

        # Enregistrement natif des outils par défaut
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Enregistre les outils natifs de base dès l'initialisation."""
        self.register_tool(
            "default_llm",
            lambda query="", **kwargs: {"response": f"Exécution terminée pour : {query}"},
            risk_level="L1",
        )
        self.register_tool(
            "neon_audit",
            lambda **kwargs: {"status": "Neon DB audit demandé", "tables": ["companies", "contacts", "opportunities"]},
            risk_level="L1",
        )
        self.register_tool(
            "web_sync",
            lambda query="", **kwargs: {"status": "success", "synced_query": query},
            risk_level="L3",
        )

    # ========================================================
    # HOOK REGISTRATION
    # ========================================================

    def register_pre_plan_hook(self, hook: PrePlanHook) -> None:
        """Enregistre un intercepteur avant planification."""
        self._pre_plan_hooks.append(hook)

    def register_step_hook(self, hook: StepHook) -> None:
        """Enregistre un intercepteur d'étape/re-plan."""
        self._step_hooks.append(hook)

    def register_post_plan_hook(self, hook: PostPlanHook) -> None:
        """Enregistre un intercepteur post-évaluation."""
        self._post_plan_hooks.append(hook)

    # ========================================================
    # IDS
    # ========================================================

    @staticmethod
    def create_trace_id() -> str:
        return f"BEK-TRC-{uuid.uuid4().hex[:12].upper()}"

    @staticmethod
    def create_task_id() -> str:
        return f"BEK-TASK-{uuid.uuid4().hex[:12].upper()}"

    @staticmethod
    def create_job_id() -> str:
        return f"BEK-JOB-{uuid.uuid4().hex[:12].upper()}"

    # ========================================================
    # TOOL REGISTRY
    # ========================================================

    def register_tool(
        self,
        name: str,
        func: Callable[..., Any],
        risk_level: str = "L1",
    ) -> None:

        if self._shutdown:
            raise RuntimeError(
                "Cannot register tools after Hermes shutdown."
            )

        tool = HermesTool(
            name=name,
            func=func,
            risk_level=risk_level,
        )

        with self._tool_lock:
            if name in self.tools:
                logger.warning(
                    "Hermes tool replaced | name=%s | risk=%s",
                    name,
                    risk_level,
                )
            self.tools[name] = tool

        logger.info(
            "Hermes tool registered | name=%s | risk=%s",
            name,
            risk_level,
        )

    def unregister_tool(self, name: str) -> bool:
        if not isinstance(name, str):
            return False

        with self._tool_lock:
            if name in self.tools:
                del self.tools[name]
                logger.info(
                    "Hermes tool unregistered | name=%s",
                    name,
                )
                return True

        return False

    def list_tools(self) -> List[Dict[str, str]]:
        with self._tool_lock:
            return [
                {
                    "name": tool.name,
                    "risk_level": tool.risk_level,
                }
                for tool in self.tools.values()
            ]

    def _get_tool(
        self,
        tool_name: str,
    ) -> Optional[HermesTool]:
        with self._tool_lock:
            return self.tools.get(tool_name)

    # ========================================================
    # GOAP PLANNER DYNAMIQUE AVEC SKILL REGISTRY & HOOK PRE-PLAN
    # ========================================================

    def goap_planner(
        self,
        objective: str,
        trace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        if not isinstance(objective, str) or not objective.strip():
            return []

        trace_id = trace_id or self.create_trace_id()

        # [HOOK POINT A] : Pre-Plan Interceptors
        for hook in self._pre_plan_hooks:
            try:
                allowed, reason, override_tasks = hook(objective, trace_id)
                if not allowed:
                    logger.warning("Pre-Plan Hook a rejeté l'objectif : %s", reason)
                    return []
                if override_tasks is not None:
                    logger.info("Pre-Plan Hook a fourni un plan sur mesure (%d tâches)", len(override_tasks))
                    return override_tasks
            except Exception as hook_err:
                logger.error("Erreur exécution Pre-Plan Hook : %s", hook_err)

        tasks: List[Dict[str, Any]] = []
        obj_lower = objective.lower().strip()

        # 1. Recherche dynamique dans le Skill Registry (P1)
        best_skills = skill_registry.search_skills(objective, limit=2)
        
        if best_skills:
            top_skill = best_skills[0]
            logger.info("GOAP sélection : %s (score=%.2f)", top_skill.name, top_skill.score)

            # Raccordement aux outils requis ou fallback vers default_llm
            if top_skill.required_tools:
                for req_tool in top_skill.required_tools:
                    tasks.append({
                        "task_id": self.create_task_id(),
                        "tool": req_tool,
                        "args": {"query": objective, "skill": top_skill.name, "prompt": top_skill.prompt[:400]},
                    })
            else:
                tasks.append({
                    "task_id": self.create_task_id(),
                    "tool": "default_llm",
                    "args": {"query": objective, "skill": top_skill.name, "prompt": top_skill.prompt[:400]},
                })

        # 2. Règles natives de secours si aucune skill n'a été trouvée
        if not tasks:
            if any(k in obj_lower for k in ("prospect", "web", "cherche", "recherche")):
                tasks.append({
                    "task_id": self.create_task_id(),
                    "tool": "web_sync",
                    "args": {"query": objective},
                })
            elif any(k in obj_lower for k in ("crm", "neon", "base", "database", "sql")):
                tasks.append({
                    "task_id": self.create_task_id(),
                    "tool": "neon_audit",
                    "args": {},
                })
            else:
                tasks.append({
                    "task_id": self.create_task_id(),
                    "tool": "default_llm",
                    "args": {"query": objective},
                })

        if trace_id:
            for task in tasks:
                task["trace_id"] = trace_id

        return tasks

    # ========================================================
    # RISK POLICY
    # ========================================================

    @staticmethod
    def requires_human_approval(
        tool: HermesTool,
    ) -> bool:
        return tool.risk_level in HUMAN_APPROVAL_LEVELS

    # ========================================================
    # SECURITY CHECK
    # ========================================================

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
                "reason": "Niveau de risque exigeant une validation humaine.",
            }

        if self.security_guard is None:
            return {
                "decision": "DENY",
                "risk_level": tool.risk_level,
                "reason": "SecurityGuard indisponible.",
            }

        try:
            ok, message, envelope = self.security_guard.validate_and_certify(
                tool.name,
                args,
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

        return {
            "decision": "ALLOW",
            "risk_level": tool.risk_level,
            "reason": message,
            "envelope": envelope,
        }

    # ========================================================
    # TASK VALIDATION
    # ========================================================

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
        if not tool_name or not isinstance(tool_name, str) or not tool_name.strip():
            return {
                "status": "INVALID_TASK",
                "message": "Invalid or missing tool name.",
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
                "message": f"Invalid args for tool '{tool_name}'.",
                "trace_id": trace_id,
                "task_id": task_id,
                "tool": tool_name,
            }

        tool = self._get_tool(tool_name)
        if tool is None:
            logger.warning(
                "Unknown Hermes tool | trace=%s | task=%s | tool=%s",
                trace_id,
                task_id,
                tool_name,
            )
            return {
                "status": "UNKNOWN_TOOL",
                "message": f"Unknown Hermes tool: {tool_name}",
                "trace_id": trace_id,
                "task_id": task_id,
                "tool": tool_name,
            }

        security = self.security_check(tool, args)
        decision = security["decision"]

        if decision != "ALLOW":
            logger.warning(
                "Hermes security decision | trace=%s | task=%s | tool=%s | risk=%s | decision=%s",
                trace_id,
                task_id,
                tool_name,
                tool.risk_level,
                decision,
            )
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

    # ========================================================
    # PARALLEL DISPATCH AVEC STEP & POST-PLAN HOOKS
    # ========================================================

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

        if not isinstance(task_list, list) or not task_list:
            return {
                "trace_id": trace_id,
                "execution_ms": 0,
                "results": {},
                "status": "NO_TASKS" if isinstance(task_list, list) else "INVALID_TASK_LIST",
            }

        validated_tasks: List[Dict[str, Any]] = []

        for task in task_list:
            validated = self._validate_task(task, trace_id)
            if validated is None:
                continue

            if validated.get("status"):
                return {
                    "trace_id": trace_id,
                    "execution_ms": round((time.monotonic() - start_time) * 1000, 2),
                    "results": {},
                    **validated,
                }
            validated_tasks.append(validated)

        if not validated_tasks:
            return {
                "trace_id": trace_id,
                "execution_ms": round((time.monotonic() - start_time) * 1000, 2),
                "results": {},
                "status": "NO_VALID_TASKS",
            }

        futures = []

        for task in validated_tasks:
            task_id = task["task_id"]
            tool_name = task["tool"]
            args = task["args"]
            tool = self._get_tool(tool_name)

            if tool is None:
                results = {
                    task_id: ToolResult(
                        task_id=task_id,
                        trace_id=trace_id,
                        tool=tool_name,
                        success=False,
                        error="UNKNOWN_TOOL",
                        error_type="ToolNotFound",
                    ).to_dict()
                }
                return {
                    "trace_id": trace_id,
                    "execution_ms": round((time.monotonic() - start_time) * 1000, 2),
                    "results": results,
                    "status": "FAILED",
                    "task_count": 1,
                    "success_count": 0,
                    "failure_count": 1,
                    "timeout_count": 0,
                }

            try:
                future = self.executor.submit(
                    self._execute_tool,
                    tool,
                    args,
                    trace_id,
                    task_id,
                )
            except RuntimeError as exc:
                futures.append((task_id, tool_name, None, exc))
                continue

            futures.append((task_id, tool_name, future, None))

        results: Dict[str, Dict[str, Any]] = {}

        for task_id, tool_name, future, submit_error in futures:
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
                    res_dict = ToolResult(
                        task_id=task_id,
                        trace_id=trace_id,
                        tool=tool_name,
                        success=False,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    ).to_dict()

            # [HOOK POINT B] : Step / Re-Plan Hooks
            current_task_spec = next((t for t in validated_tasks if t["task_id"] == task_id), {})
            for step_hook in self._step_hooks:
                try:
                    ok, replacement_res = step_hook(current_task_spec, res_dict)
                    if replacement_res is not None:
                        res_dict = replacement_res
                except Exception as step_err:
                    logger.error("Erreur Step Hook : %s", step_err)

            results[task_id] = res_dict

        execution_ms = round((time.monotonic() - start_time) * 1000, 2)
        success_count = sum(1 for result in results.values() if result.get("success") is True)
        failure_count = len(results) - success_count
        timed_out_count = sum(1 for result in results.values() if result.get("timed_out") is True)

        if not results:
            status = "FAILED"
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
        }

        # [HOOK POINT C] : Post-Plan Evaluation Hooks
        for post_hook in self._post_plan_hooks:
            try:
                final_payload = post_hook(validated_tasks, final_payload)
            except Exception as post_err:
                logger.error("Erreur Post-Plan Hook : %s", post_err)

        return final_payload

    # ========================================================
    # TOOL EXECUTION
    # ========================================================

    @staticmethod
    def _execute_tool(
        tool: HermesTool,
        args: Dict[str, Any],
        trace_id: str,
        task_id: str,
    ) -> ToolResult:

        start_time = time.monotonic()
        logger.info(
            "Hermes executing tool | trace=%s | task=%s | tool=%s | risk=%s",
            trace_id,
            task_id,
            tool.name,
            tool.risk_level,
        )

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
            logger.exception(
                "Hermes tool exception | trace=%s | task=%s | tool=%s",
                trace_id,
                task_id,
                tool.name,
            )
            return ToolResult(
                task_id=task_id,
                trace_id=trace_id,
                tool=tool.name,
                success=False,
                error=str(exc),
                error_type=type(exc).__name__,
                execution_ms=execution_ms,
            )

    # ========================================================
    # SINGLE DISPATCH
    # ========================================================

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

    # ========================================================
    # RUNTIME STATUS
    # ========================================================

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
            }
        }

    # ========================================================
    # PROVIDER CONTEXT
    # ========================================================

    def set_provider_context(
        self,
        provider: Optional[str],
        model: Optional[str],
    ) -> None:
        self.current_provider = provider.strip() if isinstance(provider, str) and provider.strip() else None
        self.current_model = model.strip() if isinstance(model, str) and model.strip() else None

    # ========================================================
    # SHUTDOWN
    # ========================================================

    def shutdown(self, wait: bool = True) -> None:
        if self._shutdown:
            return
        logger.info("Hermes executor shutting down.")
        self._shutdown = True
        self.executor.shutdown(wait=wait, cancel_futures=True)
        logger.info("Hermes executor stopped.")


# Instance Singleton globale
hermes = HermesCore()


# ============================================================
# DATABASE : SYSTEM JOBS
# ============================================================

def init_system_jobs_table() -> None:
    conn = get_db_connection()
    if not conn:
        logger.warning("Unable to initialize system_jobs: no DB connection.")
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
        logger.exception("System jobs table initialization failed.")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# BACKGROUND GUARDIAN
# ============================================================

def background_guardian_worker() -> None:
    try:
        init_system_jobs_table()
    except Exception:
        logger.exception("Guardian failed during table initialization.")

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
                logger.info("Guardian job started | job=%s", job_id)

                for _ in range(20):
                    if hermes._shutdown:
                        break
                    time.sleep(0.1)

                if hermes._shutdown:
                    break

                cur.execute(
                    """
                    UPDATE system_jobs
                    SET status = %s
                    WHERE job_id = %s;
                    """,
                    ("SUCCESS", job_id),
                )
                conn.commit()
                logger.info("Guardian job completed | job=%s", job_id)

            for _ in range(180):
                if hermes._shutdown:
                    break
                time.sleep(10)

        except Exception:
            logger.exception("Hermes guardian worker failure.")
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
            try:
                if cur:
                    cur.close()
            except Exception:
                pass
            try:
                if conn:
                    conn.close()
            except Exception:
                pass

    logger.info("Hermes guardian worker stopped.")


# ============================================================
# START BACKGROUND WORKERS
# ============================================================

def start_background_workers() -> None:
    with hermes._worker_lock:
        if hermes._shutdown or hermes._workers_started:
            return

        thread = threading.Thread(
            target=background_guardian_worker,
            name="bek-hermes-guardian",
            daemon=True,
        )
        thread.start()
        hermes._workers_started = True
        logger.info("Hermes background guardian started.")


# ============================================================
# PUBLIC API
# ============================================================

def register_tool(name: str, func: Callable[..., Any], risk_level: str = "L1") -> None:
    hermes.register_tool(name=name, func=func, risk_level=risk_level)


def unregister_tool(name: str) -> bool:
    return hermes.unregister_tool(name)


def list_tools() -> List[Dict[str, str]]:
    return hermes.list_tools()


def goap_planner(objective: str) -> List[Dict[str, Any]]:
    return hermes.goap_planner(objective)


def dispatch_parallel(task_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    return hermes.dispatch_parallel(task_list)


def dispatch(tool_name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return hermes.dispatch(tool_name=tool_name, args=args)


def runtime_status() -> Dict[str, Any]:
    return hermes.runtime_status()


def set_provider_context(provider: Optional[str], model: Optional[str]) -> None:
    hermes.set_provider_context(provider=provider, model=model)


def shutdown(wait: bool = True) -> None:
    hermes.shutdown(wait=wait)
