# -*- coding: utf-8 -*-
# BEK Hermes Core v19.28 — corrections approbation, erreurs, parallélisme et DAG.
from __future__ import annotations
import concurrent.futures
import copy
import inspect
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
from tools.code_tools import register_code_tools

logger = logging.getLogger("bek.hermes")
DEFAULT_MAX_WORKERS = 10
DEFAULT_TASK_TIMEOUT = 900
MIN_WORKERS, MAX_WORKERS = 1, 64
MIN_TASK_TIMEOUT, MAX_TASK_TIMEOUT = 1, 3600
RISK_LEVELS = {"L1", "L2", "L3", "L4", "L5"}
HUMAN_APPROVAL_LEVELS = {"L3", "L4", "L5"}
SAFETY_SCAN_PREFIX_CHARS = 500
PrePlanHook = Callable[[str, Optional[str]], Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]]]
StepHook = Callable[[Dict[str, Any], Dict[str, Any]], Tuple[bool, Optional[Dict[str, Any]]]]
PostPlanHook = Callable[[List[Dict[str, Any]], Dict[str, Any]], Dict[str, Any]]

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
            raise ValueError(f"Invalid risk level '{self.risk_level}' for tool '{self.name}'.")

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
        return {"task_id": self.task_id, "trace_id": self.trace_id, "tool": self.tool,
                "success": self.success, "data": self.data, "error": self.error,
                "error_type": self.error_type, "execution_ms": self.execution_ms,
                "timed_out": self.timed_out, "validation_failed": self.validation_failed}

class HermesCore:
    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS, task_timeout: int = DEFAULT_TASK_TIMEOUT,
                 security_guard: Optional[SecurityGuard] = None) -> None:
        if isinstance(max_workers, bool) or not isinstance(max_workers, int) or not MIN_WORKERS <= max_workers <= MAX_WORKERS:
            raise ValueError(f"max_workers doit être un entier entre {MIN_WORKERS} et {MAX_WORKERS}.")
        if isinstance(task_timeout, bool) or not isinstance(task_timeout, int) or not MIN_TASK_TIMEOUT <= task_timeout <= MAX_TASK_TIMEOUT:
            raise ValueError(f"task_timeout doit être un entier entre {MIN_TASK_TIMEOUT} et {MAX_TASK_TIMEOUT}.")
        self.tools: Dict[str, HermesTool] = {}
        self._tool_lock = threading.RLock()
        self.security_guard = security_guard or SecurityGuard()
        self.max_workers, self.task_timeout = max_workers, task_timeout
        # Pools séparés: les tâches d'orchestration ne bloquent pas les workers d'outils.
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bek-hermes-tool")
        self._dispatch_executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bek-hermes-dispatch")
        self.dag_orchestrator = HermesDAGOrchestrator(max_workers=max_workers)
        self._worker_lock = threading.Lock()
        self._workers_started = False
        self._shutdown = False
        self._shutdown_lock = threading.Lock()
        self.current_provider: Optional[str] = None
        self.current_model: Optional[str] = None
        self._pre_plan_hooks: List[PrePlanHook] = []
        self._step_hooks: List[StepHook] = []
        self._post_plan_hooks: List[PostPlanHook] = []
        # Les clés consommées sont conservées pour empêcher le rejeu d'une approbation.
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}
        self._approval_lock = threading.RLock()
        logger.info("Hermes initialized | workers=%s | timeout=%ss | security_guard=%s", max_workers, task_timeout, self.security_guard is not None)
        self._register_default_tools()
        try:
            registration = register_code_tools(self)
            logger.info('Code Tools registration: %s', registration)
        except Exception:
            logger.exception('Code Tools registration failed')
        self.register_pre_plan_hook(self._two_stage_orchestration_filter)
        self.register_pre_plan_hook(self._fable_policy_guard)

    def _register_default_tools(self) -> None:
        self.register_tool("default_llm", lambda query="", **kwargs: {"response": f"Exécution terminée pour : {query}"})
        self.register_tool("neon_audit", lambda **kwargs: {"status": "Neon DB audit demandé", "tables": ["companies", "contacts", "opportunities", "sync_log"]})
        self.register_tool("web_sync", lambda query="", **kwargs: {"status": "success", "synced_query": query}, "L3")
        self.register_tool("generate_image", lambda prompt="", **kwargs: {"status": "error", "message": "En attente de montage"})
        self.register_tool("edit_image", lambda image_paths=None, prompt="", **kwargs: {"status": "error", "message": "En attente de montage"})
        self.register_tool("generate_video", lambda prompt="", **kwargs: {"status": "error", "message": "En attente de montage"})
        self.register_tool("edit_video", lambda video_paths=None, prompt="", **kwargs: {"status": "error", "message": "En attente de montage"})

    @staticmethod
    def _two_stage_orchestration_filter(objective: str, trace_id: Optional[str]) -> Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]]:
        if not objective or not objective.strip(): return False, "Objectif vide.", []
        prefix = objective[:SAFETY_SCAN_PREFIX_CHARS].lower()
        if any(k in prefix for k in ("rm -rf", "drop database", "format c:", "del /s /q")):
            return False, "Action destructive bloquée.", []
        return True, "Planification validée", None

    @staticmethod
    def _fable_policy_guard(objective: str, trace_id: Optional[str]) -> Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]]:
        if not objective: return True, "OK", None
        prefix = objective[:SAFETY_SCAN_PREFIX_CHARS].lower()
        if any(term in prefix for term in ("api_key=", "password=", "secret=", "bearer ", "sk-")):
            return False, "Injection de secrets détectée.", []
        return True, "Politique respectée", None

    def register_pre_plan_hook(self, hook: PrePlanHook) -> None:
        if not callable(hook): raise TypeError("Le hook doit être appelable.")
        self._pre_plan_hooks.append(hook)
    def register_step_hook(self, hook: StepHook) -> None:
        if not callable(hook): raise TypeError("Le hook doit être appelable.")
        self._step_hooks.append(hook)
    def register_post_plan_hook(self, hook: PostPlanHook) -> None:
        if not callable(hook): raise TypeError("Le hook doit être appelable.")
        self._post_plan_hooks.append(hook)

    @staticmethod
    def create_trace_id() -> str: return f"BEK-TRC-{uuid.uuid4().hex[:12].upper()}"
    @staticmethod
    def create_task_id() -> str: return f"BEK-TASK-{uuid.uuid4().hex[:12].upper()}"
    @staticmethod
    def create_job_id() -> str: return f"BEK-JOB-{uuid.uuid4().hex[:12].upper()}"

    def register_tool(self, name: str, func: Callable[..., Any], risk_level: str = "L1") -> None:
        if self._shutdown: raise RuntimeError("Hermes is shutdown.")
        tool = HermesTool(name=name, func=func, risk_level=risk_level)
        with self._tool_lock: self.tools[name] = tool
        logger.info("Hermes tool registered | name=%s | risk=%s", name, risk_level)
    def unregister_tool(self, name: str) -> bool:
        with self._tool_lock:
            if name in self.tools: del self.tools[name]; return True
            return False
    def list_tools(self) -> List[Dict[str, str]]:
        with self._tool_lock: return [{"name": t.name, "risk_level": t.risk_level} for t in self.tools.values()]
    def _get_tool(self, tool_name: str) -> Optional[HermesTool]:
        with self._tool_lock: return self.tools.get(tool_name)

    @staticmethod
    def _normalize_required_tools(raw: Any) -> List[str]:
        if raw is None: return ["default_llm"]
        if isinstance(raw, str): return [raw.strip()] if raw.strip() else ["default_llm"]
        if isinstance(raw, (list, tuple, set)):
            vals = [str(t).strip() for t in raw if t is not None and str(t).strip()]
            return vals or ["default_llm"]
        return ["default_llm"]
    @staticmethod
    def _extract_skill_info(skill: Any) -> Tuple[List[str], str]:
        if isinstance(skill, dict):
            raw = skill.get("required_tools") or skill.get("tools") or skill.get("tool")
            name = skill.get("name") or skill.get("id") or skill.get("skill_name") or "unknown"
        else:
            raw = getattr(skill, "required_tools", None) or getattr(skill, "tools", None) or getattr(skill, "tool", None)
            name = getattr(skill, "name", None) or getattr(skill, "id", None) or getattr(skill, "skill_name", None) or str(skill)
        return HermesCore._normalize_required_tools(raw), str(name)

    def plan_from_keywords(self, objective: str, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not isinstance(objective, str) or not objective.strip(): return []
        trace_id = trace_id or self.create_trace_id()
        for hook in tuple(self._pre_plan_hooks):
            try: allowed, reason, override = hook(objective, trace_id)
            except Exception: logger.exception("Échec du hook pré-plan"); return []
            if not allowed: logger.warning("Hook rejeté: %s", reason); return []
            if override is not None: return override
        tasks: List[Dict[str, Any]] = []
        lower = objective.lower().strip()
        try: skills = skill_registry.search_skills(objective, limit=2)
        except Exception: logger.exception("Recherche de compétences impossible"); skills = []
        if skills:
            req_tools, skill_name = self._extract_skill_info(skills[0])
            for req_tool in req_tools:
                tasks.append({"task_id": self.create_task_id(), "tool": req_tool, "args": {"query": objective, "skill": skill_name}, "trace_id": trace_id})
        else:
            if any(k in lower for k in ("audit", "base de données", "database", "neon", "sql")):
                tasks.append({"task_id": self.create_task_id(), "tool": "neon_audit", "args": {"query": objective}, "trace_id": trace_id})
            if any(k in lower for k in ("scrape", "sync", "web", "site")):
                tasks.append({"task_id": self.create_task_id(), "tool": "web_sync", "args": {"query": objective}, "trace_id": trace_id})
            if any(k in lower for k in ("image", "photo", "dessin")):
                tasks.append({"task_id": self.create_task_id(), "tool": "generate_image", "args": {"prompt": objective}, "trace_id": trace_id})
            if not tasks: tasks.append({"task_id": self.create_task_id(), "tool": "default_llm", "args": {"query": objective}, "trace_id": trace_id})
        for hook in tuple(self._post_plan_hooks):
            try: hook(tasks, {"objective": objective, "trace_id": trace_id})
            except Exception as exc: logger.warning("Post-plan hook error: %s", exc)
        return tasks
    def goap_planner(self, objective: str, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.plan_from_keywords(objective, trace_id)

    @staticmethod
    def _validate_tool_args(tool: HermesTool, args: Dict[str, Any]) -> Optional[str]:
        try: sig = inspect.signature(tool.func)
        except (TypeError, ValueError): return f"Signature non inspectable pour l'outil '{tool.name}'."
        params = sig.parameters
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
        allowed = {n for n, p in params.items() if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)}
        if not has_kwargs:
            unknown = sorted(set(args) - allowed)
            if unknown: return "Arguments non reconnus : " + ", ".join(unknown)
        required = [n for n, p in params.items() if p.default is inspect.Parameter.empty and p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)]
        missing = [n for n in required if n not in args]
        if missing: return "Arguments obligatoires manquants : " + ", ".join(missing)
        return None

    def _execute_tool(self, tool: HermesTool, args: Dict[str, Any], task_id: str, trace_id: str) -> ToolResult:
        start = time.monotonic()
        try:
            data = tool.func(**args)
            elapsed = (time.monotonic() - start) * 1000
            if isinstance(data, dict):
                status = data.get("status")
                status = status.strip().lower() if isinstance(status, str) else ""
                if status in {"error", "failed", "failure", "rejected", "cancelled"} or data.get("success") is False:
                    msg = data.get("message") or data.get("error") or str(data)
                    return ToolResult(task_id, trace_id, tool.name, False, data, str(msg), "ToolReportedError", elapsed)
            return ToolResult(task_id, trace_id, tool.name, True, data=data, execution_ms=elapsed)
        except concurrent.futures.TimeoutError:
            return ToolResult(task_id, trace_id, tool.name, False, error=f"Timeout après {self.task_timeout}s", error_type="TimeoutError", execution_ms=(time.monotonic()-start)*1000, timed_out=True)
        except Exception as exc:
            logger.debug("Erreur outil %s:\n%s", tool.name, traceback.format_exc())
            return ToolResult(task_id, trace_id, tool.name, False, error=str(exc), error_type=type(exc).__name__, execution_ms=(time.monotonic()-start)*1000)

    def dispatch(self, task: Dict[str, Any]) -> ToolResult:
        result = self._dispatch_impl(task)
        if not self._step_hooks:
            return result
        try:
            observed_task = copy.deepcopy(task) if isinstance(task, dict) else {"invalid_task": repr(task)}
        except Exception:
            observed_task = dict(task) if isinstance(task, dict) else {"invalid_task": repr(task)}
        for hook in tuple(self._step_hooks):
            try:
                observed_result = copy.deepcopy(result.to_dict())
            except Exception:
                observed_result = result.to_dict()
            try:
                hook(copy.deepcopy(observed_task), observed_result)
            except Exception as exc:
                logger.warning("Task Observer hook error: %s", exc)
        return result

    def _dispatch_impl(self, task: Dict[str, Any]) -> ToolResult:
        if not isinstance(task, dict):
            return ToolResult(self.create_task_id(), self.create_trace_id(), "?", False, error="La tâche doit être un dictionnaire.", error_type="InvalidTask", validation_failed=True)
        task_id, trace_id = task.get("task_id") or self.create_task_id(), task.get("trace_id") or self.create_trace_id()
        name, args = task.get("tool"), task.get("args", {})
        if not isinstance(task_id, str) or not task_id.strip(): task_id = self.create_task_id()
        if not isinstance(trace_id, str) or not trace_id.strip(): trace_id = self.create_trace_id()
        if not isinstance(name, str) or not name.strip():
            return ToolResult(task_id, trace_id, "?", False, error="Nom d'outil absent ou invalide.", error_type="InvalidTask", validation_failed=True)
        if not isinstance(args, dict):
            return ToolResult(task_id, trace_id, name, False, error="Les arguments doivent être un dictionnaire.", error_type="InvalidArguments", validation_failed=True)
        if self._shutdown:
            return ToolResult(task_id, trace_id, name, False, error="Hermes est arrêté.", error_type="ShuttingDown")
        tool = self._get_tool(name)
        if tool is None: return ToolResult(task_id, trace_id, name, False, error=f"Tool inconnu : {name}", error_type="UnknownTool")
        arg_error = self._validate_tool_args(tool, args)
        if arg_error: return ToolResult(task_id, trace_id, name, False, error=arg_error, error_type="InvalidArguments", validation_failed=True)

        if tool.risk_level in HUMAN_APPROVAL_LEVELS:
            key = f"{task_id}:{name}"
            try: snapshot = copy.deepcopy(args)
            except Exception as exc:
                return ToolResult(task_id, trace_id, name, False, error=f"Impossible de figer les arguments: {exc}", error_type="ApprovalSnapshotError", validation_failed=True)
            with self._approval_lock:
                record = self._pending_approvals.get(key)
                if record is None:
                    self._pending_approvals[key] = {"task_id": task_id, "trace_id": trace_id, "tool": name, "args": snapshot, "risk_level": tool.risk_level, "requested_at": time.time(), "status": "pending"}
                    return ToolResult(task_id, trace_id, name, False, error=f"Approbation requise pour '{name}'. Après vérification, appelle hermes.approve('{key}').", error_type="ApprovalRequired", validation_failed=True)
                if record["status"] == "pending":
                    return ToolResult(task_id, trace_id, name, False, error=f"Approbation toujours en attente : {key}", error_type="ApprovalRequired", validation_failed=True)
                if record["status"] == "consumed":
                    return ToolResult(task_id, trace_id, name, False, error=f"Approbation déjà consommée : {key}", error_type="ApprovalAlreadyConsumed", validation_failed=True)
                if record["status"] != "approved":
                    return ToolResult(task_id, trace_id, name, False, error=f"État d'approbation invalide : {key}", error_type="InvalidApprovalState", validation_failed=True)
                if record["args"] != snapshot:
                    return ToolResult(task_id, trace_id, name, False, error="Les arguments diffèrent de ceux approuvés.", error_type="ApprovalArgumentsMismatch", validation_failed=True)
                record["status"] = "consumed"
                args = copy.deepcopy(record["args"])
        try: future = self.executor.submit(self._execute_tool, tool, args, task_id, trace_id)
        except RuntimeError as exc: return ToolResult(task_id, trace_id, name, False, error=str(exc), error_type="ExecutorError")
        try: return future.result(timeout=self.task_timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            return ToolResult(task_id, trace_id, name, False, error=f"Timeout global après {self.task_timeout}s; l'annulation ne garantit pas l'arrêt du code déjà démarré.", error_type="TimeoutError", timed_out=True)

    def approve(self, approval_key: str) -> bool:
        """Marque une demande pending comme approved; n'exécute jamais l'outil."""
        if not isinstance(approval_key, str) or not approval_key.strip(): return False
        with self._approval_lock:
            record = self._pending_approvals.get(approval_key)
            if not record or record.get("status") != "pending": return False
            record["status"] = "approved"
            record["approved_at"] = time.time()
            return True

    def dispatch_parallel(self, tasks: List[Dict[str, Any]]) -> List[ToolResult]:
        if not isinstance(tasks, list): return [ToolResult(self.create_task_id(), self.create_trace_id(), "dispatch_parallel", False, error="tasks doit être une liste.", error_type="InvalidTaskList", validation_failed=True)]
        if not tasks: return []
        futures = []
        for task in tasks:
            try: futures.append(self._dispatch_executor.submit(self.dispatch, task))
            except RuntimeError: futures.append(None)
        results: List[ToolResult] = []
        for i, future in enumerate(futures):
            task = tasks[i] if isinstance(tasks[i], dict) else {}
            if future is None:
                results.append(ToolResult(str(task.get("task_id") or self.create_task_id()), str(task.get("trace_id") or self.create_trace_id()), str(task.get("tool") or "?"), False, error="Pool d'orchestration arrêté.", error_type="ExecutorError")); continue
            try: results.append(future.result(timeout=self.task_timeout + 1))
            except concurrent.futures.TimeoutError:
                future.cancel()
                results.append(ToolResult(str(task.get("task_id") or self.create_task_id()), str(task.get("trace_id") or self.create_trace_id()), str(task.get("tool") or "?"), False, error="Délai d'attente de l'orchestration parallèle dépassé.", error_type="TimeoutError", timed_out=True))
            except Exception as exc:
                results.append(ToolResult(str(task.get("task_id") or self.create_task_id()), str(task.get("trace_id") or self.create_trace_id()), str(task.get("tool") or "?"), False, error=str(exc), error_type=type(exc).__name__))
        return results

    def dispatch_dag_plan(self, plan: Any, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """Exécute un plan DAG et renvoie un résumé stable des résultats."""
        trace_id = trace_id or self.create_trace_id()
        if isinstance(plan, list):
            plan_id = f"hermes_{trace_id}"
            raw_steps = plan
        elif isinstance(plan, dict):
            plan_id = str(plan.get("plan_id") or f"hermes_{trace_id}")
            raw_steps = plan.get("steps", [])
        else:
            return {"plan_id": f"hermes_{trace_id}", "status": "INVALID_DAG", "task_count": 0, "success_count": 0, "failure_count": 1, "results": {}, "error": "Le plan DAG doit être une liste de tâches ou un dictionnaire contenant 'steps'."}

        if not isinstance(raw_steps, list):
            return {"plan_id": plan_id, "status": "INVALID_DAG", "task_count": 0, "success_count": 0, "failure_count": 1, "results": {}, "error": "Le champ 'steps' doit être une liste."}
        if not raw_steps:
            return {"plan_id": plan_id, "status": "NO_STEPS", "task_count": 0, "success_count": 0, "failure_count": 0, "results": {}}

        steps = []
        original = {}
        for index, item in enumerate(raw_steps):
            if not isinstance(item, dict):
                return {"plan_id": plan_id, "status": "INVALID_DAG", "task_count": len(raw_steps), "success_count": 0, "failure_count": len(raw_steps), "results": {}, "error": f"L'étape {index} doit être un dictionnaire."}
            step_id = item.get("id") or item.get("task_id") or f"step_{index}"
            action = item.get("action") or item.get("tool")
            params = item.get("params", item.get("args", {}))
            if not isinstance(step_id, str) or not step_id.strip() or not isinstance(action, str) or not action.strip() or not isinstance(params, dict):
                return {"plan_id": plan_id, "status": "INVALID_DAG", "task_count": len(raw_steps), "success_count": 0, "failure_count": len(raw_steps), "results": {}, "error": f"Étape invalide à l'index {index} : id, action/tool et params/args sont requis."}
            if step_id in original:
                return {"plan_id": plan_id, "status": "INVALID_DAG", "task_count": len(raw_steps), "success_count": 0, "failure_count": len(raw_steps), "results": {}, "error": f"Identifiant d'étape dupliqué : {step_id}"}
            deps = item.get("depends_on", item.get("dependencies", [])) or []
            if not isinstance(deps, list):
                return {"plan_id": plan_id, "status": "INVALID_DAG", "task_count": len(raw_steps), "success_count": 0, "failure_count": len(raw_steps), "results": {}, "error": f"Les dépendances de l'étape {step_id} doivent être une liste."}
            original[step_id] = {"task_id": str(item.get("task_id") or step_id), "trace_id": str(item.get("trace_id") or trace_id), "tool": action}
            steps.append({"id": step_id, "action": action, "params": {"args": params, "_hermes_task_id": original[step_id]["task_id"], "_hermes_trace_id": original[step_id]["trace_id"]}, "depends_on": deps})

        known_ids = set(original)
        for step in steps:
            missing = [dep for dep in step["depends_on"] if dep not in known_ids]
            if missing:
                return {"plan_id": plan_id, "status": "INVALID_DAG", "task_count": len(steps), "success_count": 0, "failure_count": len(steps), "results": {}, "error": f"Dépendance(s) inconnue(s) pour {step['id']} : {missing}"}

        actions = {step["action"] for step in steps}
        def make_handler(action_name):
            def handler(params):
                task = {"task_id": params.get("_hermes_task_id"), "trace_id": params.get("_hermes_trace_id"), "tool": action_name, "args": params.get("args", {})}
                result = self.dispatch(task)
                return {"status": "OK" if result.success else "FAILED", "success": result.success, "output": result.data, "error": result.error, "error_type": result.error_type, "tool_result": result.to_dict()}
            return handler

        try:
            dag_results = self.dag_orchestrator.execute_goal_plan({"plan_id": plan_id, "steps": steps}, {action: make_handler(action) for action in actions})
        except Exception as exc:
            logger.exception("Échec DAG; aucune relance automatique.")
            message = str(exc)
            is_cycle = "cycle" in message.lower()
            return {"plan_id": plan_id, "status": "INVALID_DAG" if is_cycle else "FAILED", "task_count": len(steps), "success_count": 0, "failure_count": len(steps), "results": {}, "error": message}

        results = {}
        success_count = 0
        for step in steps:
            step_id = step["id"]
            value = dag_results.get(step_id)
            if isinstance(value, dict) and isinstance(value.get("tool_result"), dict):
                result = dict(value["tool_result"])
                result["dag_status"] = value.get("status", "OK")
            else:
                status = value.get("status", "FAILED") if isinstance(value, dict) else "FAILED"
                result = {"task_id": original[step_id]["task_id"], "trace_id": original[step_id]["trace_id"], "tool": original[step_id]["tool"], "success": False, "data": value, "error": (value.get("error") or value.get("reason") or status) if isinstance(value, dict) else "Résultat DAG invalide", "error_type": (value.get("error_type") or status) if isinstance(value, dict) else "InvalidDAGResult", "timed_out": status == "TIMEOUT", "validation_failed": status in {"MISSING_HANDLER", "INVALID_HANDLER"}, "dag_status": status}
            results[step_id] = result
            if result.get("success") is True:
                success_count += 1

        failure_count = len(steps) - success_count
        return {"plan_id": plan_id, "status": "SUCCESS" if failure_count == 0 else "FAILED", "task_count": len(steps), "success_count": success_count, "failure_count": failure_count, "results": results}

    def start_workers(self) -> None:
        with self._worker_lock:
            if self._workers_started or self._shutdown: return
            self._workers_started = True
            threading.Thread(target=self._background_guardian_worker, daemon=True, name="bek-hermes-worker").start()
    def start_background_workers(self) -> None: self.start_workers()
    def _background_guardian_worker(self) -> None:
        while not self._shutdown: time.sleep(30)
    def shutdown(self) -> None:
        with self._shutdown_lock:
            if self._shutdown: return
            self._shutdown = True
        try: self.dag_orchestrator.shutdown()
        except Exception: logger.exception("Erreur pendant l'arrêt du DAG")
        self._dispatch_executor.shutdown(wait=False, cancel_futures=True)
        self.executor.shutdown(wait=False, cancel_futures=True)

# Compatibilité historique avec app.py et brain.py.
hermes = HermesCore()
def start_background_workers() -> None:
    """Point d'entrée fonction pour app.py (compatibilité)."""
    hermes.start_background_workers()