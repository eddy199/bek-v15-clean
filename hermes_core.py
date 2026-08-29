"""
BEK Hermes Core V2 - HARDENED
-----------------------------
Noyau d'orchestration Hermes / GOAP / Workers.

Responsabilités :
- registre sécurisé des tools ;
- planification GOAP simple ;
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
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from memory import get_db_connection
from security_guard import SecurityGuard


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
# HERMES CORE
# ============================================================

class HermesCore:

    def __init__(
        self,
        max_workers: int = DEFAULT_MAX_WORKERS,
        task_timeout: int = DEFAULT_TASK_TIMEOUT,
        security_guard: Optional[SecurityGuard] = None,
    ) -> None:

        # ----------------------------------------------------
        # Configuration validation
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Tool registry
        # ----------------------------------------------------

        self.tools: Dict[str, HermesTool] = {}

        # IMPORTANT :
        # le registre peut être consulté/modifié depuis plusieurs
        # threads.
        self._tool_lock = threading.RLock()

        # ----------------------------------------------------
        # Security Guard
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Runtime configuration
        # ----------------------------------------------------

        self.max_workers = max_workers
        self.task_timeout = task_timeout

        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="bek-hermes",
        )

        # ----------------------------------------------------
        # Lifecycle
        # ----------------------------------------------------

        self._worker_lock = threading.Lock()
        self._workers_started = False
        self._shutdown = False

        # ----------------------------------------------------
        # Provider context
        # ----------------------------------------------------

        self.current_provider: Optional[str] = None
        self.current_model: Optional[str] = None

        logger.info(
            "Hermes initialized | workers=%s | timeout=%ss | "
            "security_guard=%s",
            max_workers,
            task_timeout,
            self.security_guard is not None,
        )

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
    # GOAP PLANNER
    # ========================================================

    def goap_planner(
        self,
        objective: str,
        trace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        if not isinstance(objective, str):
            return []

        if not objective.strip():
            return []

        obj = objective.lower().strip()

        tasks: List[Dict[str, Any]] = []

        # ----------------------------------------------------
        # WEB
        # ----------------------------------------------------

        if any(
            keyword in obj
            for keyword in (
                "prospect",
                "web",
                "cherche",
                "recherche",
            )
        ):

            if self._get_tool("web_sync") is not None:

                tasks.append(
                    {
                        "task_id": self.create_task_id(),
                        "tool": "web_sync",
                        "args": {
                            "query": objective,
                        },
                    }
                )

        # ----------------------------------------------------
        # DATABASE
        # ----------------------------------------------------

        if any(
            keyword in obj
            for keyword in (
                "crm",
                "neon",
                "base",
                "database",
                "sql",
            )
        ):

            if self._get_tool("neon_audit") is not None:

                tasks.append(
                    {
                        "task_id": self.create_task_id(),
                        "tool": "neon_audit",
                        "args": {},
                    }
                )

        # ----------------------------------------------------
        # DEFAULT LLM
        # ----------------------------------------------------

        if not tasks:

            if self._get_tool("default_llm") is not None:

                tasks.append(
                    {
                        "task_id": self.create_task_id(),
                        "tool": "default_llm",
                        "args": {
                            "query": objective,
                        },
                    }
                )

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

        # ----------------------------------------------------
        # HUMAN APPROVAL GATE
        # ----------------------------------------------------

        if self.requires_human_approval(tool):

            return {
                "decision": "REQUIRE_HUMAN",
                "risk_level": tool.risk_level,
                "reason": (
                    "Niveau de risque exigeant "
                    "une validation humaine."
                ),
            }

        # ----------------------------------------------------
        # SECURITY GUARD REQUIRED
        # ----------------------------------------------------

        if self.security_guard is None:

            return {
                "decision": "DENY",
                "risk_level": tool.risk_level,
                "reason": "SecurityGuard indisponible.",
            }

        # ----------------------------------------------------
        # SINGLE SECURITY CERTIFICATION
        # ----------------------------------------------------

        try:

            ok, message, envelope = (
                self.security_guard.validate_and_certify(
                    tool.name,
                    args,
                )
            )

        except Exception as exc:

            logger.exception(
                "SecurityGuard exception | tool=%s",
                tool.name,
            )

            return {
                "decision": "DENY",
                "risk_level": tool.risk_level,
                "reason": (
                    "SecurityGuard exception: "
                    f"{type(exc).__name__}"
                ),
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

        # ----------------------------------------------------
        # TASK TYPE
        # ----------------------------------------------------

        if not isinstance(task, dict):

            return {
                "status": "INVALID_TASK",
                "message": "Task must be a dictionary.",
                "trace_id": trace_id,
            }

        # ----------------------------------------------------
        # TASK ID
        # ----------------------------------------------------

        task_id = task.get("task_id")

        if not isinstance(task_id, str) or not task_id.strip():
            task_id = self.create_task_id()

        # ----------------------------------------------------
        # TOOL NAME
        # ----------------------------------------------------

        tool_name = task.get("tool")

        if not tool_name:

            return {
                "status": "INVALID_TASK",
                "message": "Missing tool name.",
                "trace_id": trace_id,
                "task_id": task_id,
            }

        if not isinstance(tool_name, str):

            return {
                "status": "INVALID_TASK",
                "message": "Tool name must be a string.",
                "trace_id": trace_id,
                "task_id": task_id,
            }

        tool_name = tool_name.strip()

        if not tool_name:

            return {
                "status": "INVALID_TASK",
                "message": "Tool name cannot be empty.",
                "trace_id": trace_id,
                "task_id": task_id,
            }

        # ----------------------------------------------------
        # ARGS
        # ----------------------------------------------------

        args = task.get("args", {})

        if args is None:
            args = {}

        if not isinstance(args, dict):

            return {
                "status": "INVALID_TASK",
                "message": (
                    f"Invalid args for tool '{tool_name}'."
                ),
                "trace_id": trace_id,
                "task_id": task_id,
                "tool": tool_name,
            }

        # ----------------------------------------------------
        # IMPORTANT HARDENING
        #
        # On vérifie d'abord que le tool existe.
        #
        # L'ancien ordre envoyait le nom du tool au Guard
        # avant même de savoir si Hermes possédait réellement
        # ce tool.
        # ----------------------------------------------------

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
                "message": (
                    f"Unknown Hermes tool: {tool_name}"
                ),
                "trace_id": trace_id,
                "task_id": task_id,
                "tool": tool_name,
            }

        # ----------------------------------------------------
        # SECURITY GATE
        #
        # C'est maintenant le point unique de certification.
        # On ne certifie pas deux fois la même action.
        # ----------------------------------------------------

        security = self.security_check(
            tool,
            args,
        )

        decision = security["decision"]

        # ----------------------------------------------------
        # DENY / HUMAN APPROVAL
        # ----------------------------------------------------

        if decision != "ALLOW":

            logger.warning(
                "Hermes security decision | "
                "trace=%s | task=%s | tool=%s | "
                "risk=%s | decision=%s",
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

        # ----------------------------------------------------
        # VALIDATED TASK
        # ----------------------------------------------------

        return {
            "task_id": task_id,
            "trace_id": trace_id,
            "tool": tool_name,
            "args": args,
            "risk_level": tool.risk_level,
            "security_decision": "ALLOW",
            "security_envelope": security.get(
                "envelope"
            ),
        }

    # ========================================================
    # PARALLEL DISPATCH
    # ========================================================

    def dispatch_parallel(
        self,
        task_list: List[Dict[str, Any]],
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        trace_id = trace_id or self.create_trace_id()

        start_time = time.monotonic()

        # ----------------------------------------------------
        # SHUTDOWN
        # ----------------------------------------------------

        if self._shutdown:

            return {
                "trace_id": trace_id,
                "execution_ms": 0,
                "results": {},
                "status": "HERMES_SHUTDOWN",
            }

        # ----------------------------------------------------
        # TASK LIST VALIDATION
        # ----------------------------------------------------

        if not isinstance(task_list, list):

            return {
                "trace_id": trace_id,
                "execution_ms": 0,
                "results": {},
                "status": "INVALID_TASK_LIST",
                "message": "task_list must be a list.",
            }

        if not task_list:

            return {
                "trace_id": trace_id,
                "execution_ms": 0,
                "results": {},
                "status": "NO_TASKS",
            }

        # ----------------------------------------------------
        # VALIDATION PHASE
        #
        # Aucune tâche n'est exécutée pendant cette phase.
        # Toute la liste doit passer les contrôles avant
        # lancement des workers.
        # ----------------------------------------------------

        validated_tasks: List[Dict[str, Any]] = []

        for task in task_list:

            validated = self._validate_task(
                task,
                trace_id,
            )

            if validated is None:
                continue

            if validated.get("status"):

                return {
                    "trace_id": trace_id,
                    "execution_ms": round(
                        (
                            time.monotonic()
                            - start_time
                        )
                        * 1000,
                        2,
                    ),
                    "results": {},
                    **validated,
                }

            validated_tasks.append(validated)

        # ----------------------------------------------------
        # EMPTY AFTER VALIDATION
        # ----------------------------------------------------

        if not validated_tasks:

            return {
                "trace_id": trace_id,
                "execution_ms": round(
                    (
                        time.monotonic()
                        - start_time
                    )
                    * 1000,
                    2,
                ),
                "results": {},
                "status": "NO_VALID_TASKS",
            }

        # ----------------------------------------------------
        # SUBMIT PHASE
        # ----------------------------------------------------

        futures = []

        for task in validated_tasks:

            task_id = task["task_id"]
            tool_name = task["tool"]
            args = task["args"]

            tool = self._get_tool(tool_name)

            # Théoriquement impossible car validé juste avant.
            # On garde néanmoins cette défense supplémentaire.
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
                    "execution_ms": round(
                        (
                            time.monotonic()
                            - start_time
                        )
                        * 1000,
                        2,
                    ),
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

                logger.exception(
                    "Hermes executor rejected task | "
                    "trace=%s | task=%s | tool=%s",
                    trace_id,
                    task_id,
                    tool_name,
                )

                futures.append(
                    (
                        task_id,
                        tool_name,
                        None,
                        exc,
                    )
                )

                continue

            futures.append(
                (
                    task_id,
                    tool_name,
                    future,
                    None,
                )
            )

        # ----------------------------------------------------
        # RESULT PHASE
        # ----------------------------------------------------

        results: Dict[str, Dict[str, Any]] = {}

        for (
            task_id,
            tool_name,
            future,
            submit_error,
        ) in futures:

            # -----------------------------------------------
            # SUBMISSION ERROR
            # -----------------------------------------------

            if future is None:

                results[task_id] = ToolResult(
                    task_id=task_id,
                    trace_id=trace_id,
                    tool=tool_name,
                    success=False,
                    error=str(submit_error),
                    error_type=type(
                        submit_error
                    ).__name__,
                ).to_dict()

                continue

            # -----------------------------------------------
            # RESULT
            # -----------------------------------------------

            try:

                result = future.result(
                    timeout=self.task_timeout
                )

                if isinstance(result, ToolResult):

                    results[task_id] = result.to_dict()

                else:

                    results[task_id] = ToolResult(
                        task_id=task_id,
                        trace_id=trace_id,
                        tool=tool_name,
                        success=True,
                        data=result,
                    ).to_dict()

            # -----------------------------------------------
            # TIMEOUT
            # -----------------------------------------------

            except concurrent.futures.TimeoutError:

                logger.error(
                    "Hermes tool timeout | "
                    "trace=%s | task=%s | tool=%s",
                    trace_id,
                    task_id,
                    tool_name,
                )

                # cancel() peut empêcher l'exécution si le future
                # n'a pas encore commencé.
                future.cancel()

                results[task_id] = ToolResult(
                    task_id=task_id,
                    trace_id=trace_id,
                    tool=tool_name,
                    success=False,
                    error="TASK_TIMEOUT",
                    error_type="TimeoutError",
                    timed_out=True,
                ).to_dict()

            # -----------------------------------------------
            # UNEXPECTED FUTURE ERROR
            # -----------------------------------------------

            except Exception as exc:

                logger.exception(
                    "Hermes future failed | "
                    "trace=%s | task=%s | tool=%s",
                    trace_id,
                    task_id,
                    tool_name,
                )

                results[task_id] = ToolResult(
                    task_id=task_id,
                    trace_id=trace_id,
                    tool=tool_name,
                    success=False,
                    error=str(exc),
                    error_type=type(exc).__name__,
                ).to_dict()

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        execution_ms = round(
            (
                time.monotonic()
                - start_time
            )
            * 1000,
            2,
        )

        success_count = sum(
            1
            for result in results.values()
            if result.get("success") is True
        )

        failure_count = (
            len(results)
            - success_count
        )

        timed_out_count = sum(
            1
            for result in results.values()
            if result.get("timed_out") is True
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return {
            "trace_id": trace_id,
            "execution_ms": execution_ms,
            "results": results,
            "status": status,
            "task_count": len(results),
            "success_count": success_count,
            "failure_count": failure_count,
            "timeout_count": timed_out_count,
        }

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
            "Hermes executing tool | "
            "trace=%s | task=%s | tool=%s | risk=%s",
            trace_id,
            task_id,
            tool.name,
            tool.risk_level,
        )

        try:

            data = tool.func(**args)

            execution_ms = round(
                (
                    time.monotonic()
                    - start_time
                )
                * 1000,
                2,
            )

            return ToolResult(
                task_id=task_id,
                trace_id=trace_id,
                tool=tool.name,
                success=True,
                data=data,
                execution_ms=execution_ms,
            )

        except Exception as exc:

            execution_ms = round(
                (
                    time.monotonic()
                    - start_time
                )
                * 1000,
                2,
            )

            logger.exception(
                "Hermes tool exception | "
                "trace=%s | task=%s | tool=%s",
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
            "status": (
                "shutdown"
                if self._shutdown
                else "operational"
            ),
            "security_guard_active": (
                self.security_guard is not None
            ),
            "tools": self.list_tools(),
            "tool_count": len(self.tools),
            "provider": self.current_provider,
            "model": self.current_model,
            "max_workers": self.max_workers,
            "task_timeout": self.task_timeout,
            "workers_started": self._workers_started,
        }

    # ========================================================
    # PROVIDER CONTEXT
    # ========================================================

    def set_provider_context(
        self,
        provider: Optional[str],
        model: Optional[str],
    ) -> None:

        self.current_provider = (
            provider.strip()
            if isinstance(provider, str)
            and provider.strip()
            else None
        )

        self.current_model = (
            model.strip()
            if isinstance(model, str)
            and model.strip()
            else None
        )

    # ========================================================
    # SHUTDOWN
    # ========================================================

    def shutdown(
        self,
        wait: bool = True,
    ) -> None:

        if self._shutdown:
            return

        logger.info(
            "Hermes executor shutting down."
        )

        self._shutdown = True

        self.executor.shutdown(
            wait=wait,
            cancel_futures=True,
        )

        logger.info(
            "Hermes executor stopped."
        )


# ============================================================
# GLOBAL HERMES INSTANCE
# ============================================================

hermes = HermesCore()


# ============================================================
# DATABASE : SYSTEM JOBS
# ============================================================

def init_system_jobs_table() -> None:

    conn = get_db_connection()

    if not conn:

        logger.warning(
            "Unable to initialize system_jobs: "
            "no DB connection."
        )

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
                created_at TIMESTAMP WITH TIME ZONE
                    DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        conn.commit()

    except Exception:

        logger.exception(
            "System jobs table initialization failed."
        )

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

        logger.exception(
            "Guardian failed during table initialization."
        )

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
                    INSERT INTO system_jobs
                        (
                            job_id,
                            task_name,
                            status,
                            retry_count
                        )
                    VALUES
                        (%s, %s, %s, %s);
                    """,
                    (
                        job_id,
                        "matrix_silent_audit",
                        "RUNNING",
                        0,
                    ),
                )

                conn.commit()

                logger.info(
                    "Guardian job started | job=%s",
                    job_id,
                )

                # --------------------------------------------
                # Audit simulation / placeholder
                # --------------------------------------------

                for _ in range(20):

                    if hermes._shutdown:
                        break

                    time.sleep(0.1)

                if hermes._shutdown:
                    break

                # --------------------------------------------
                # SUCCESS
                # --------------------------------------------

                cur.execute(
                    """
                    UPDATE system_jobs
                    SET status = %s
                    WHERE job_id = %s;
                    """,
                    (
                        "SUCCESS",
                        job_id,
                    ),
                )

                conn.commit()

                logger.info(
                    "Guardian job completed | job=%s",
                    job_id,
                )

            # -----------------------------------------------
            # Wait before next audit
            # -----------------------------------------------

            for _ in range(180):

                if hermes._shutdown:
                    break

                time.sleep(10)

        except Exception:

            logger.exception(
                "Hermes guardian worker failure."
            )

            if conn:

                try:
                    conn.rollback()

                except Exception:
                    pass

            # -----------------------------------------------
            # Recovery delay
            # -----------------------------------------------

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

    logger.info(
        "Hermes guardian worker stopped."
    )


# ============================================================
# START BACKGROUND WORKERS
# ============================================================

def start_background_workers() -> None:

    with hermes._worker_lock:

        if hermes._shutdown:

            logger.warning(
                "Cannot start background workers: "
                "Hermes is shutdown."
            )

            return

        if hermes._workers_started:

            logger.info(
                "Hermes background workers already started."
            )

            return

        thread = threading.Thread(
            target=background_guardian_worker,
            name="bek-hermes-guardian",
            daemon=True,
        )

        thread.start()

        hermes._workers_started = True

        logger.info(
            "Hermes background guardian started."
        )


# ============================================================
# PUBLIC API
# ============================================================

def register_tool(
    name: str,
    func: Callable[..., Any],
    risk_level: str = "L1",
) -> None:

    hermes.register_tool(
        name=name,
        func=func,
        risk_level=risk_level,
    )


def unregister_tool(
    name: str,
) -> bool:

    return hermes.unregister_tool(name)


def list_tools() -> List[Dict[str, str]]:

    return hermes.list_tools()


def goap_planner(
    objective: str,
) -> List[Dict[str, Any]]:

    return hermes.goap_planner(objective)


def dispatch_parallel(
    task_list: List[Dict[str, Any]],
) -> Dict[str, Any]:

    return hermes.dispatch_parallel(
        task_list
    )


def dispatch(
    tool_name: str,
    args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    return hermes.dispatch(
        tool_name=tool_name,
        args=args,
    )


def runtime_status() -> Dict[str, Any]:

    return hermes.runtime_status()


def set_provider_context(
    provider: Optional[str],
    model: Optional[str],
) -> None:

    hermes.set_provider_context(
        provider=provider,
        model=model,
    )


def shutdown(
    wait: bool = True,
) -> None:

    hermes.shutdown(
        wait=wait
    )
