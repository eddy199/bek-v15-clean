# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-FLUX Executor (Optimisation Multi-Core)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-FLUX-v1.0
# 📄 Doc : docs/brevets/BREVET_FLUX.md
# 🎯 Rôle : Parallélisation DAG des tâches (Bypass du GIL Python)
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 2.0 (Refactored)
# Date : 2026-09-28
# ==============================================================================

from __future__ import annotations

import logging
import multiprocessing
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
    TimeoutError as FuturesTimeout
)
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("bek.core.flux")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BEK_FLUX_DEFAULT_WORKERS = min(10, multiprocessing.cpu_count() * 2) # Adaptatif selon la machine
BEK_FLUX_DEFAULT_TIMEOUT = 25.0
BEK_FLUX_DEFAULT_MODE = "thread" # 'thread' (I/O bound) ou 'process' (CPU bound)


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekFluxExecutor:
    """
    Exécuteur DAG BEK-FLUX (Dual Engine).

    Parallélise les tâches en contournant les limitations du GIL Python.
    - mode="thread" : Idéal pour les appels réseau (I/O bound).
    - mode="process" : Idéal pour le parsing lourd et le calcul (CPU bound).

    Usage :
        executor = BekFluxExecutor(mode="process")
        results = executor.run([...])
    """

    def __init__(
        self,
        workers: int = BEK_FLUX_DEFAULT_WORKERS,
        timeout: float = BEK_FLUX_DEFAULT_TIMEOUT,
        mode: str = BEK_FLUX_DEFAULT_MODE,
    ):
        self.workers = max(1, workers)
        self.timeout = max(1.0, timeout)
        self.mode = mode.lower()
        
        if self.mode not in ("thread", "process"):
            logger.warning(f"BekFlux : Mode '{self.mode}' inconnu. Fallback sur 'thread'.")
            self.mode = "thread"

    # ──────────────────────────────────────────────────────────────────────────
    # EXÉCUTION PRINCIPALE
    # ──────────────────────────────────────────────────────────────────────────

    def run(
        self,
        tasks: List[Dict[str, Any]],
        workers: Optional[int] = None,
        timeout: Optional[float] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Exécute une liste de tâches en parallèle.
        """
        import time
        t0 = time.monotonic()

        nb_workers = workers or self.workers
        nb_timeout = timeout or self.timeout
        exec_mode = (mode or self.mode).lower()

        if not tasks:
            return {"_meta": {"total": 0, "success": 0, "failed": 0, "elapsed_ms": 0.0}}

        results: Dict[str, Any] = {}
        success_count = 0
        failed_count = 0

        logger.info(
            "BekFluxExecutor : %d tâches en parallèle (%d workers, timeout=%.1fs, mode=%s)",
            len(tasks), nb_workers, nb_timeout, exec_mode
        )

        # Sélection du moteur d'exécution (Bypass du GIL si "process")
        ExecutorClass = ProcessPoolExecutor if exec_mode == "process" else ThreadPoolExecutor

        try:
            with ExecutorClass(max_workers=nb_workers) as executor:
                future_to_task = {}

                for task in tasks:
                    task_id = task.get("id")
                    fn = task.get("fn")
                    args = task.get("args", [])
                    kwargs = task.get("kwargs", {})

                    if not task_id or not callable(fn):
                        logger.warning("BekFluxExecutor : tâche invalide : %s", task_id)
                        continue

                    future = executor.submit(fn, *args, **kwargs)
                    future_to_task[future] = task_id

                for future in as_completed(future_to_task, timeout=nb_timeout + 5.0):
                    task_id = future_to_task[future]
                    try:
                        result = future.result(timeout=nb_timeout)
                        results[task_id] = result
                        success_count += 1
                        logger.debug("BekFluxExecutor : ✓ %s", task_id)
                    except FuturesTimeout:
                        results[task_id] = {"error": "timeout", "task_id": task_id}
                        failed_count += 1
                        logger.warning("BekFluxExecutor : ✗ %s (timeout)", task_id)
                    except Exception as exc:
                        results[task_id] = {"error": str(exc), "task_id": task_id}
                        failed_count += 1
                        logger.warning("BekFluxExecutor : ✗ %s (%s)", task_id, exc)
                        
        except Exception as exc:
            logger.error("BekFluxExecutor : Erreur critique du pool d'exécution : %s", exc)

        elapsed_ms = (time.monotonic() - t0) * 1000

        results["_meta"] = {
            "total": len(tasks),
            "success": success_count,
            "failed": failed_count,
            "elapsed_ms": round(elapsed_ms, 2),
            "mode": exec_mode
        }

        logger.info(
            "BekFluxExecutor : terminé | %d/%d succès | %.1f ms",
            success_count, len(tasks), elapsed_ms
        )

        return results

    def run_parallel(
        self,
        functions: List[Callable],
        args_list: Optional[List[List[Any]]] = None,
        workers: Optional[int] = None,
        mode: Optional[str] = None,
    ) -> List[Any]:
        if not functions:
            return []

        if args_list is None:
            args_list = [[] for _ in functions]

        tasks = [
            {"id": f"task_{i}", "fn": fn, "args": args}
            for i, (fn, args) in enumerate(zip(functions, args_list))
        ]

        results_dict = self.run(tasks, workers=workers, mode=mode)

        return [
            results_dict.get(f"task_{i}", {"error": "missing"})
            for i in range(len(functions))
        ]


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ══════════════════════════════════════════════════════════════════════════════

def bek_flux_run(
    tasks: List[Dict[str, Any]],
    workers: int = BEK_FLUX_DEFAULT_WORKERS,
    timeout: float = BEK_FLUX_DEFAULT_TIMEOUT,
    mode: str = BEK_FLUX_DEFAULT_MODE,
) -> Dict[str, Any]:
    executor = BekFluxExecutor(workers=workers, timeout=timeout, mode=mode)
    return executor.run(tasks, workers=workers, timeout=timeout, mode=mode)

def bek_flux_run_parallel(
    functions: List[Callable],
    args_list: Optional[List[List[Any]]] = None,
    workers: int = BEK_FLUX_DEFAULT_WORKERS,
    mode: str = BEK_FLUX_DEFAULT_MODE,
) -> List[Any]:
    executor = BekFluxExecutor(workers=workers, mode=mode)
    return executor.run_parallel(functions, args_list, workers=workers, mode=mode)
