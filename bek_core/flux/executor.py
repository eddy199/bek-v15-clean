# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-FLUX Executor
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-FLUX-v1.0
# 📄 Doc : docs/brevets/BREVET_FLUX.md
# 🎯 Rôle : Parallélisation DAG des tâches
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("bek.core.flux")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BEK_FLUX_DEFAULT_WORKERS = 10
BEK_FLUX_DEFAULT_TIMEOUT = 25.0


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekFluxExecutor:
    """
    Exécuteur DAG BEK-FLUX.

    Parallélise les tâches en utilisant un DAG Engine.
    Chaque tâche a un timeout individuel.
    Une erreur sur une tâche n'affecte pas les autres.

    Usage :
        executor = BekFluxExecutor()
        results = executor.run([
            {"id": "t1", "fn": scrape, "args": ["url1"]},
            {"id": "t2", "fn": scrape, "args": ["url2"]},
        ], workers=10)
    """

    def __init__(
        self,
        workers: int = BEK_FLUX_DEFAULT_WORKERS,
        timeout: float = BEK_FLUX_DEFAULT_TIMEOUT,
    ):
        self.workers = max(1, workers)
        self.timeout = max(1.0, timeout)

    # ──────────────────────────────────────────────────────────────────────────
    # EXÉCUTION PRINCIPALE
    # ──────────────────────────────────────────────────────────────────────────

    def run(
        self,
        tasks: List[Dict[str, Any]],
        workers: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Exécute une liste de tâches en parallèle.

        Args:
            tasks: Liste de tâches
                Chaque tâche : {
                    "id": str (requis),
                    "fn": callable (requis),
                    "args": list (optionnel),
                    "kwargs": dict (optionnel),
                }
            workers: Nombre de workers (défaut 10)
            timeout: Timeout par tâche en secondes (défaut 25.0)

        Returns:
            dict: {
                "task_id": result,
                "_meta": {
                    "total": int,
                    "success": int,
                    "failed": int,
                    "elapsed_ms": float,
                }
            }
        """
        import time
        t0 = time.monotonic()

        nb_workers = workers or self.workers
        nb_timeout = timeout or self.timeout

        if not tasks:
            return {"_meta": {"total": 0, "success": 0, "failed": 0, "elapsed_ms": 0.0}}

        results: Dict[str, Any] = {}
        success_count = 0
        failed_count = 0

        logger.info(
            "BekFluxExecutor : %d tâches en parallèle (%d workers, timeout=%.1fs)",
            len(tasks),
            nb_workers,
            nb_timeout,
        )

        with ThreadPoolExecutor(max_workers=nb_workers) as executor:
            future_to_task = {}

            for task in tasks:
                task_id = task.get("id")
                fn = task.get("fn")
                args = task.get("args", [])
                kwargs = task.get("kwargs", {})

                if not task_id or not callable(fn):
                    logger.warning("BekFluxExecutor : tâche invalide : %s", task)
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

        elapsed_ms = (time.monotonic() - t0) * 1000

        results["_meta"] = {
            "total": len(tasks),
            "success": success_count,
            "failed": failed_count,
            "elapsed_ms": round(elapsed_ms, 2),
        }

        logger.info(
            "BekFluxExecutor : terminé | %d/%d succès | %.1f ms",
            success_count,
            len(tasks),
            elapsed_ms,
        )

        return results

    def run_parallel(
        self,
        functions: List[Callable],
        args_list: Optional[List[List[Any]]] = None,
        workers: Optional[int] = None,
    ) -> List[Any]:
        """
        Version simplifiée : exécute N fonctions en parallèle.

        Args:
            functions: Liste de fonctions
            args_list: Liste d'arguments (même longueur que functions)
            workers: Nombre de workers

        Returns:
            Liste des résultats dans l'ordre
        """
        if not functions:
            return []

        if args_list is None:
            args_list = [[] for _ in functions]

        tasks = [
            {"id": f"task_{i}", "fn": fn, "args": args}
            for i, (fn, args) in enumerate(zip(functions, args_list))
        ]

        results_dict = self.run(tasks, workers=workers)

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
) -> Dict[str, Any]:
    """
    Fonction principale BEK-FLUX.

    API publique du brevet BEK-FLUX-v1.0.
    """
    executor = BekFluxExecutor(workers=workers, timeout=timeout)
    return executor.run(tasks, workers=workers, timeout=timeout)


def bek_flux_run_parallel(
    functions: List[Callable],
    args_list: Optional[List[List[Any]]] = None,
    workers: int = BEK_FLUX_DEFAULT_WORKERS,
) -> List[Any]:
    """Version simplifiée : N fonctions en parallèle."""
    executor = BekFluxExecutor(workers=workers)
    return executor.run_parallel(functions, args_list, workers=workers)