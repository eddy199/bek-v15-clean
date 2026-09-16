# ==============================================================================
# BEK Hermes Core V4 - HARDENED & DYNAMIC PLANNER (KEYWORD-BASED)
# ==============================================================================
# Responsabilités :
# - Registre sécurisé des tools
# - Planification dynamique via Skill Registry + routage par mots-clés
# - Filtre d'orchestration en deux étapes (Planification -> Exécution)
# - Gestion des risques L1 -> L5 et validation humaine L3+
# - Routage natif multimédia : generate_image, edit_image, generate_video, edit_video
# - Exécution parallèle via ThreadPoolExecutor
# - Worker Guardian système (audit Neon DB + compensation Pinecone)
#
# CORRECTIFS v4 :
#   - Vérification HMAC de l'enveloppe de sécurité AVANT exécution
#     (via SecurityGuard.verify_envelope) — la signature n'est plus cosmétique.
#   - dispatch_parallel ne s'arrête plus à la première tâche invalide :
#     les tâches valides sont exécutées, les tâches invalides sont rapportées.
#   - goap_planner renommé officiellement en plan_from_keywords :
#     la fonction n'implémente PAS un GOAP (pas de préconditions/effets/coût),
#     mais un routeur à mots-clés. Un alias est conservé pour compatibilité.
# ==============================================================================

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from memory import get_db_connection, replay_pending_syncs
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
HUMAN_APPROVAL_LEVELS = {"L3", "L4", "L5"}


# ============================================================
# TOOL & RESULT MODELS
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


# ============================================================
# PLAN HOOK TYPES
# ============================================================

PrePlanHook = Callable[[str, Optional[str]], Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]]]
StepHook = Callable[[Dict[str, Any], Dict[str, Any]], Tuple[bool, Optional[Dict[str, Any]]]]
PostPlanHook = Callable[[List[Dict[str, Any]], Dict[str, Any]], Dict[str, Any]]


# ============================================================
# HERMES CORE ENGINE
# ============================================================

class HermesCore:

    def __init__(
        self,
        max_workers: int = DEFAULT_MAX_WORKERS,
        task_timeout: int = DEFAULT_TASK_TIMEOUT,
        security_guard: Optional[SecurityGuard] = None,
    ) -> None:

        if not isinstance(max_workers, int) or not MIN_WORKERS <= max_workers <= MAX_WORKERS:
            raise ValueError(f"max_workers must be between {MIN_WORKERS} and {MAX_WORKERS}.")

        if not isinstance(task_timeout, int) or not MIN_TASK_TIMEOUT <= task_timeout <= MAX_TASK_TIMEOUT:
            raise ValueError(f"task_timeout must be between {MIN_TASK_TIMEOUT} and {MAX_TASK_TIMEOUT} seconds.")

        self.tools: Dict[str, HermesTool] = {}
        self._tool_lock = threading.RLock()

        self.security_guard = security_guard
        if self.security_guard is None:
            try:
                self.security_guard = SecurityGuard()
            except Exception as exc:
                logger.error("Hermes SecurityGuard initialization failed: %s", exc)
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

        self._pre_plan_hooks: List[PrePlanHook] = []
        self._step_hooks: List[StepHook] = []
        self._post_plan_hooks: List[PostPlanHook] = []

        logger.info(
            "Hermes initialized | workers=%s | timeout=%ss | security_guard=%s",
            max_workers,
            task_timeout,
            self.security_guard is not None,
        )

        self._register_default_tools()
        self.register_pre_plan_hook(self._two_stage_orchestration_filter)
        self.register_pre_plan_hook(self._fable_policy_guard)

    def _register_default_tools(self) -> None:
        """Enregistre les outils natifs de base."""
        self.register_tool(
            "default_llm",
            lambda query="", **kwargs: {"response": f"Exécution terminée pour : {query}"},
            risk_level="L1",
        )
        self.register_tool(
            "neon_audit",
            lambda **kwargs: {
                "status": "Neon DB audit demandé",
                "tables": ["companies", "contacts", "opportunities", "matrix_sub_crms", "sync_log"]
            },
            risk_level="L1",
        )
        self.register_tool(
            "web_sync",
            lambda query="", **kwargs: {"status": "success", "synced_query": query},
            risk_level="L3",
        )
        self.register_tool(
            "generate_image",
            lambda prompt="", **kwargs: {"status": "error", "message": "En attente de montage via app.py"},
            risk_level="L1",
        )
        self.register_tool(
            "edit_image",
            lambda image_paths=[], prompt="", **kwargs: {"status": "error", "message": "En attente de montage via app.py"},
            risk_level="L1",
        )
        self.register_tool(
            "generate_video",
            lambda prompt="", **kwargs: {"status": "error", "message": "En attente de montage via app.py"},
            risk_level="L1",
        )
        self.register_tool(
            "edit_video",
            lambda video_paths=[], prompt="", **kwargs: {"status": "error", "message": "En attente de montage via app.py"},
            risk_level="L1",
        )

    # ========================================================
    # FILTRES DE SÉCURITÉ
    # ========================================================

    @staticmethod
    def _two_stage_orchestration_filter(objective: str, trace_id: Optional[str]) -> Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]]:
        if not objective or not objective.strip():
            return False, "Objectif vide rejeté par l'orchestrateur.", []

        obj_lower = objective.lower()
        dangerous_keywords = ["rm -rf", "drop database", "format c:", "del /s /q"]
        if any(kw in obj_lower for kw in dangerous_keywords):
            logger.warning("Filtre d'orchestration : Action destructive bloquée | trace=%s", trace_id)
            return False, "Action destructive bloquée par le filtre de sécurité.", []

        return True, "Planification validée", None

    @staticmethod
    def _fable_policy_guard(objective: str, trace_id: Optional[str]) -> Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]]:
        if not objective:
            return True, "OK", None

        obj_lower = objective.lower()
        forbidden_terms = ["api_key=", "password=", "secret=", "bearer ", "sk-"]
        if any(term in obj_lower for term in forbidden_terms):
            logger.warning("Violation de sécurité : Injection de secrets détectée | trace=%s", trace_id)
            return False, "Les secrets et clés d'API ne doivent jamais être inclus dans les objectifs.", []

        return True, "Politique respectée", None

    # ========================================================
    # HOOKS & IDENTIFIANTS
    # ========================================================

    def register_pre_plan_hook(self, hook: PrePlanHook) -> None:
        self._pre_plan_hooks.append(hook)

    def register_step_hook(self, hook: StepHook) -> None:
        self._step_hooks.append(hook)

    def register_post_plan_hook(self, hook: PostPlanHook) -> None:
        self._post_plan_hooks.append(hook)

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
    # GESTION DES OUTILS
    # ========================================================

    def register_tool(self, name: str, func: Callable[..., Any], risk_level: str = "L1") -> None:
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
            return [{"name": tool.name, "risk_level": tool.risk_level} for tool in self.tools.values()]

    def _get_tool(self, tool_name: str) -> Optional[HermesTool]:
        with self._tool_lock:
            return self.tools.get(tool_name)

    # ========================================================
    # PLANIFICATEUR PAR MOTS-CLÉS
    # ========================================================
    # NOTE HONNÊTETÉ ARCHITECTURALE :
    #   Cette fonction s'appelait historiquement "goap_planner".
    #   Elle n'implémente PAS un GOAP au sens strict (pas de préconditions,
    #   pas d'effets, pas de coût, pas de recherche A*). Il s'agit d'un
    #   routeur par mots-clés couplé à une recherche Skill Registry.
    #   - Le nom public `plan_from_keywords` est désormais la référence.
    #   - L'alias `goap_planner` est conservé pour compatibilité ascendante.

    def plan_from_keywords(self, objective: str, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Planifie une liste de tâches à partir d'un objectif en langage naturel.

        Étapes :
          1. Applique les Pre-Plan Hooks (filtres de sécurité).
          2. Interroge le Skill Registry.
          3. Si un skill correspond, génère une tâche à partir de ses required_tools.
          4. Sinon, applique un routage par mots-clés (multimédia, web, CRM, fallback LLM).
        """
        if not isinstance(objective, str) or not objective.strip():
            return []

        trace_id = trace_id or self.create_trace_id()

        for hook in self._pre_plan_hooks:
            try:
                allowed, reason, override_tasks = hook(objective, trace_id)
                if not allowed:
                    logger.warning("Pre-Plan Hook a rejeté l'objectif : %s", reason)
                    return []
                if override_tasks is not None:
                    return override_tasks
            except Exception as hook_err:
                logger.error("Erreur Pre-Plan Hook : %s\n%s", hook_err, traceback.format_exc())

        tasks: List[Dict[str, Any]] = []
        obj_lower = objective.lower().strip()

        best_skills = skill_registry.search_skills(objective, limit=2)

        if best_skills:
            top_skill = best_skills[0]
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

        # Routage natif multimédia & système
        if not tasks:
            if "modifier" in obj_lower and any(k in obj_lower for k in ("vidéo", "video", "film")):
                tasks.append({"task_id": self.create_task_id(), "tool": "edit_video", "args": {"prompt": objective}})
            elif "modifier" in obj_lower and any(k in obj_lower for k in ("image", "photo", "dessin")):
                tasks.append({"task_id": self.create_task_id(), "tool": "edit_image", "args": {"prompt": objective}})
            elif any(k in obj_lower for k in ("vidéo", "video", "film", "génère une vidéo")):
                tasks.append({"task_id": self.create_task_id(), "tool": "generate_video", "args": {"prompt": objective}})
            elif any(k in obj_lower for k in ("image", "photo", "dessin", "génère une image")):
                tasks.append({"task_id": self.create_task_id(), "tool": "generate_image", "args": {"prompt": objective}})
            elif any(k in obj_lower for k in ("prospect", "web", "cherche", "recherche")):
                tasks.append({"task_id": self.create_task_id(), "tool": "web_sync", "args": {"query": objective}})
            elif any(k in obj_lower for k in ("crm", "neon", "base", "database", "sql")):
                tasks.append({"task_id": self.create_task_id(), "tool": "neon_audit", "args": {}})
            else:
                tasks.append({"task_id": self.create_task_id(), "tool": "default_llm", "args": {"query": objective}})

        if trace_id:
            for task in tasks:
                task["trace_id"] = trace_id

        return tasks

    # Alias de compatibilité ascendante — NE PAS SUPPRIMER.
    def goap_planner(self, objective: str, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Alias historique de `plan_from_keywords`. Conservé pour compatibilité.
        Voir la docstring de `plan_from_keywords` pour les détails.
        """
        return self.plan_from_keywords(objective, trace_id=trace_id)

    # ========================================================
    # SÉCURITÉ & VALIDATION
    # ========================================================

    @staticmethod
    def requires_human_approval(tool: HermesTool) -> bool:
        return tool.risk_level in HUMAN_APPROVAL_LEVELS

    def security_check(self, tool: HermesTool, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        args = args or {}
        if self.requires_human_approval(tool):
            return {"decision": "REQUIRE_HUMAN", "risk_level": tool.risk_level, "reason": "Validation humaine requise."}
        if self.security_guard is None:
            return {"decision": "DENY", "risk_level": tool.risk_level, "reason": "SecurityGuard indisponible."}

        try:
            ok, message, envelope = self.security_guard.validate_and_certify(tool.name, args)
        except Exception as exc:
            logger.exception("SecurityGuard exception | tool=%s", tool.name)
            return {"decision": "DENY", "risk_level": tool.risk_level, "reason": f"SecurityGuard exception: {type(exc).__name__}"}

        if not ok:
            return {"decision": "DENY", "risk_level": tool.risk_level, "reason": message}

        # ---------------------------------------------------------------
        # CORRECTIF v4 : vérification immédiate de l'enveloppe produite.
        # Si la signature HMAC est invalide (par exemple clé régénérée,
        # enveloppe altérée), on refuse AVANT que la tâche ne soit exécutée.
        # ---------------------------------------------------------------
        if envelope and hasattr(self.security_guard, "verify_envelope"):
            try:
                sig_ok, sig_msg = self.security_guard.verify_envelope(envelope)
                if not sig_ok:
                    logger.error(
                        "Enveloppe HMAC invalide pour tool=%s : %s", tool.name, sig_msg
                    )
                    return {
                        "decision": "DENY",
                        "risk_level": tool.risk_level,
                        "reason": f"Signature HMAC invalide : {sig_msg}",
                    }
            except Exception as exc:
                logger.exception("verify_envelope exception | tool=%s", tool.name)
                return {
                    "decision": "DENY",
                    "risk_level": tool.risk_level,
                    "reason": f"verify_envelope exception: {type(exc).__name__}",
                }

        return {"decision": "ALLOW", "risk_level": tool.risk_level, "reason": message, "envelope": envelope}

    def _validate_task(self, task: Any, trace_id: str) -> Optional[Dict[str, Any]]:
        if not isinstance(task, dict):
            return {"status": "INVALID_TASK", "message": "Task must be a dictionary.", "trace_id": trace_id}

        task_id = task.get("task_id") or self.create_task_id()
        tool_name = task.get("tool")
        if not tool_name or not isinstance(tool_name, str) or not tool_name.strip():
            return {"status": "INVALID_TASK", "message": "Missing tool name.", "trace_id": trace_id, "task_id": task_id}

        tool_name = tool_name.strip()
        args = task.get("args") or {}

        tool = self._get_tool(tool_name)
        if tool is None:
            return {"status": "UNKNOWN_TOOL", "message": f"Unknown tool: {tool_name}", "trace_id": trace_id, "task_id": task_id, "tool": tool_name}

        security = self.security_check(tool, args)
        decision = security["decision"]

        if decision != "ALLOW":
            status = "SECURITY_APPROVAL_REQUIRED" if decision == "REQUIRE_HUMAN" else "SECURITY_DENIED"
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
    # DISPATCH & EXÉCUTION PARALLÈLE
    # ========================================================

    def dispatch_parallel(self, task_list: List[Dict[str, Any]], trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Exécute une liste de tâches en parallèle.

        CORRECTIF v4 :
          - Une tâche invalide n'annule plus l'ensemble du batch.
          - Les tâches valides sont exécutées.
          - Les tâches invalides sont rapportées avec validation_failed=True.
        """
        trace_id = trace_id or self.create_trace_id()
        start_time = time.monotonic()

        if self._shutdown:
            return {"trace_id": trace_id, "execution_ms": 0, "results": {}, "status": "HERMES_SHUTDOWN"}

        if not isinstance(task_list, list) or not task_list:
            return {"trace_id": trace_id, "execution_ms": 0, "results": {}, "status": "NO_TASKS"}

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

        # Si AUCUNE tâche n'est valide, on renvoie un résultat global
        # qui contient le détail des tâches invalides.
        if not validated_tasks:
            results_invalid: Dict[str, Dict[str, Any]] = {}
            for inv in invalid_tasks:
                inv_task_id = inv.get("task_id") or self.create_task_id()
                results_invalid[inv_task_id] = ToolResult(
                    task_id=inv_task_id,
                    trace_id=trace_id,
                    tool=inv.get("tool", "unknown"),
                    success=False,
                    error=inv.get("message"),
                    error_type=inv.get("status"),
                    validation_failed=True,
                ).to_dict()

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

        # Soumission des tâches valides au pool
        futures = []
        for task in validated_tasks:
            task_id = task["task_id"]
            tool_name = task["tool"]
            args = task["args"]
            tool = self._get_tool(tool_name)

            if tool is None:
                continue

            try:
                future = self.executor.submit(self._execute_tool, tool, args, trace_id, task_id)
                futures.append((task_id, tool_name, future, None))
            except RuntimeError as exc:
                futures.append((task_id, tool_name, None, exc))

        results: Dict[str, Dict[str, Any]] = {}

        # On ajoute d'abord les tâches invalides dans le rapport final
        for inv in invalid_tasks:
            inv_task_id = inv.get("task_id") or self.create_task_id()
            results[inv_task_id] = ToolResult(
                task_id=inv_task_id,
                trace_id=trace_id,
                tool=inv.get("tool", "unknown"),
                success=False,
                error=inv.get("message"),
                error_type=inv.get("status"),
                validation_failed=True,
            ).to_dict()

        # Puis on collecte les résultats des tâches valides
        for task_id, tool_name, future, submit_error in futures:
            if future is None:
                res_dict = ToolResult(
                    task_id=task_id, trace_id=trace_id, tool=tool_name, success=False,
                    error=str(submit_error), error_type=type(submit_error).__name__
                ).to_dict()
            else:
                try:
                    result = future.result(timeout=self.task_timeout)
                    if isinstance(result, ToolResult):
                        res_dict = result.to_dict()
                    else:
                        res_dict = ToolResult(task_id=task_id, trace_id=trace_id, tool=tool_name, success=True, data=result).to_dict()
                except concurrent.futures.TimeoutError:
                    future.cancel()
                    res_dict = ToolResult(task_id=task_id, trace_id=trace_id, tool=tool_name, success=False, error="TASK_TIMEOUT", error_type="TimeoutError", timed_out=True).to_dict()
                except Exception as exc:
                    res_dict = ToolResult(task_id=task_id, trace_id=trace_id, tool=tool_name, success=False, error=str(exc), error_type=type(exc).__name__).to_dict()

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
        success_count = sum(1 for res in results.values() if res.get("success") is True)
        failure_count = len(results) - success_count
        timed_out_count = sum(1 for res in results.values() if res.get("timed_out") is True)
        invalid_count = sum(1 for res in results.values() if res.get("validation_failed") is True)

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
                final_payload = post_hook(validated_tasks, final_payload)
            except Exception as post_err:
                logger.error("Erreur Post-Plan Hook : %s", post_err)

        return final_payload

    @staticmethod
    def _execute_tool(tool: HermesTool, args: Dict[str, Any], trace_id: str, task_id: str) -> ToolResult:
        start_time = time.monotonic()
        try:
            data = tool.func(**args)
            execution_ms = round((time.monotonic() - start_time) * 1000, 2)
            return ToolResult(task_id=task_id, trace_id=trace_id, tool=tool.name, success=True, data=data, execution_ms=execution_ms)
        except Exception as exc:
            execution_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.exception("Erreur d'exécution de l'outil %s", tool.name)
            return ToolResult(task_id=task_id, trace_id=trace_id, tool=tool.name, success=False, error=str(exc), error_type=type(exc).__name__, execution_ms=execution_ms)

    def dispatch(self, tool_name: str, args: Optional[Dict[str, Any]] = None, trace_id: Optional[str] = None) -> Dict[str, Any]:
        return self.dispatch_parallel([{"task_id": self.create_task_id(), "tool": tool_name, "args": args or {}}], trace_id=trace_id)

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

    def set_provider_context(self, provider: Optional[str], model: Optional[str]) -> None:
        self.current_provider = provider.strip() if isinstance(provider, str) and provider.strip() else None
        self.current_model = model.strip() if isinstance(model, str) and model.strip() else None

    def shutdown(self, wait: bool = True) -> None:
        if self._shutdown:
            return
        logger.info("Hermes executor shutting down.")
        self._shutdown = True
        self.executor.shutdown(wait=wait, cancel_futures=True)


# Instance Singleton globale
hermes = HermesCore()


# ============================================================
# JOBS SYSTÈME & BACKGROUND GUARDIAN
# ============================================================

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


def background_guardian_worker() -> None:
    try:
        init_system_jobs_table()
    except Exception:
        pass

    while not hermes._shutdown:
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            if conn:
                job_id = hermes.create_job_id()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO system_jobs (job_id, task_name, status, retry_count) VALUES (%s, %s, %s, %s);",
                    (job_id, "matrix_silent_audit", "RUNNING", 0)
                )
                conn.commit()

                try:
                    replayed = replay_pending_syncs(limit=25)
                    if replayed > 0:
                        logger.info("Guardian a synchronisé %d vecteurs orphelins vers Pinecone.", replayed)
                except Exception:
                    pass

                for _ in range(20):
                    if hermes._shutdown:
                        break
                    time.sleep(0.1)

                if hermes._shutdown:
                    break

                cur.execute("UPDATE system_jobs SET status = %s WHERE job_id = %s;", ("SUCCESS", job_id))
                conn.commit()

            for _ in range(180):
                if hermes._shutdown:
                    break
                time.sleep(10)

        except Exception:
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
        if hermes._shutdown or hermes._workers_started:
            return
        thread = threading.Thread(
            target=background_guardian_worker,
            name="bek-hermes-guardian",
            daemon=True,
        )
        thread.start()
        hermes._workers_started = True


# ============================================================
# EXPOSITION DE L'API PUBLIQUE
# ============================================================

def register_tool(name: str, func: Callable[..., Any], risk_level: str = "L1") -> None:
    hermes.register_tool(name=name, func=func, risk_level=risk_level)

def unregister_tool(name: str) -> bool:
    return hermes.unregister_tool(name)

def list_tools() -> List[Dict[str, str]]:
    return hermes.list_tools()

def plan_from_keywords(objective: str) -> List[Dict[str, Any]]:
    """Planification par mots-clés (nom officiel v4)."""
    return hermes.plan_from_keywords(objective)

def goap_planner(objective: str) -> List[Dict[str, Any]]:
    """Alias historique de plan_from_keywords, conservé pour compatibilité."""
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