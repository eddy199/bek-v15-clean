# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — DAG Execution Engine (ADR-001 CPU-HIGH-DENSITY)
# ------------------------------------------------------------------------------
# Moteur d'exécution parallèle pour générations topologiques de tâches.
#
# Une "génération" = ensemble de nœuds sans dépendance entre eux
# (garanti par nx.topological_generations).
#
# Design :
#   - ThreadPoolExecutor (I/O-bound : LLM, DB, HTTP, subprocess)
#   - Timeout par tâche + timeout global de génération
#   - Isolation d'erreur par node (un crash ne tue pas la génération)
#   - Retour : {node_id: dict} — toujours un dict, jamais une exception brute
#
# Dépendances : networkx (déjà présent via hermes_dag_adapter.py)
# ==============================================================================
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeout,
)
from typing import Any, Callable, Dict, Optional

import networkx as nx

logger = logging.getLogger("bek.dag_engine")


# ==============================================================================
# CONFIGURATION
# ==============================================================================
DEFAULT_MAX_WORKERS = 8
DEFAULT_TASK_TIMEOUT_S = 30.0
DEFAULT_GENERATION_TIMEOUT_S = 120.0
MIN_WORKERS = 1
MAX_WORKERS = 128


# ==============================================================================
# MOTEUR DAG
# ==============================================================================
class DAGExecutionEngine:
    """
    Exécute en parallèle toutes les tâches d'une même génération topologique.

    Usage typique (depuis hermes_dag_adapter.py) :

        engine = DAGExecutionEngine(max_workers=8)
        for generation in nx.topological_generations(dag):
            registry = {node_id: callable_0_arg, ...}
            results = engine.execute_dag(dag.subgraph(generation), registry)
        engine.shutdown()
    """

    def __init__(
        self,
        max_workers: Optional[int] = None,
        task_timeout_s: float = DEFAULT_TASK_TIMEOUT_S,
        generation_timeout_s: float = DEFAULT_GENERATION_TIMEOUT_S,
    ) -> None:
        # --- Calibration workers ---
        if max_workers is None:
            cpu = os.cpu_count() or 4
            # 2× CPU : ratio usuel pour tâches I/O-bound
            max_workers = min(DEFAULT_MAX_WORKERS, cpu * 2)

        if not isinstance(max_workers, int) or isinstance(max_workers, bool):
            raise TypeError("max_workers doit être un int.")
        if not MIN_WORKERS <= max_workers <= MAX_WORKERS:
            raise ValueError(
                f"max_workers doit être entre {MIN_WORKERS} et {MAX_WORKERS}."
            )

        self.max_workers = max_workers
        self.task_timeout_s = float(task_timeout_s)
        self.generation_timeout_s = float(generation_timeout_s)

        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="bek-dag",
        )
        self._shutdown = False

        logger.info(
            "DAGExecutionEngine prêt | workers=%d | task_timeout=%.1fs | "
            "gen_timeout=%.1fs",
            self.max_workers,
            self.task_timeout_s,
            self.generation_timeout_s,
        )

    # --------------------------------------------------------------------------
    # API PRINCIPALE
    # --------------------------------------------------------------------------
    def execute_dag(
        self,
        subgraph: nx.DiGraph,
        task_registry: Dict[str, Callable[[], Any]],
    ) -> Dict[str, Any]:
        """
        Exécute toutes les tâches d'une génération en parallèle.

        Args:
            subgraph: sous-graphe networkx (une seule génération, sans arête interne).
            task_registry: {node_id: callable_sans_argument}

        Returns:
            {node_id: résultat} où chaque résultat est :
                - la valeur retournée par la tâche (dict attendu)
                - {"status": "FAILED", "error": ..., "error_type": ...}
                - {"status": "TIMEOUT", "error": ...}
                - {"status": "MISSING_HANDLER", "error": ...}
                - {"status": "ENGINE_SHUTDOWN"}
        """
        if self._shutdown:
            return {
                node_id: {"status": "ENGINE_SHUTDOWN"}
                for node_id in subgraph.nodes
            }

        nodes = list(subgraph.nodes)
        if not nodes:
            return {}

        results: Dict[str, Any] = {}
        futures: Dict[str, Any] = {}

        # --- Soumission ---
        for node_id in nodes:
            handler = task_registry.get(node_id)
            if handler is None:
                results[node_id] = {
                    "status": "MISSING_HANDLER",
                    "error": f"Aucun handler enregistré pour '{node_id}'",
                }
                continue
            if not callable(handler):
                results[node_id] = {
                    "status": "INVALID_HANDLER",
                    "error": f"Handler pour '{node_id}' n'est pas callable.",
                }
                continue
            try:
                futures[node_id] = self._executor.submit(handler)
            except RuntimeError as exc:
                # Cas : executor déjà shutdown
                results[node_id] = {
                    "status": "FAILED",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }

        # --- Collecte avec deadline global de génération ---
        deadline = time.monotonic() + self.generation_timeout_s

        for node_id, future in futures.items():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                future.cancel()
                results[node_id] = {
                    "status": "TIMEOUT",
                    "error": "generation_deadline_exceeded",
                }
                continue

            per_task_budget = min(remaining, self.task_timeout_s)

            try:
                value = future.result(timeout=per_task_budget)
                # Normalise : toujours un dict
                if value is None:
                    results[node_id] = {"status": "OK", "result": None}
                elif isinstance(value, dict):
                    results[node_id] = value
                else:
                    results[node_id] = {"status": "OK", "result": value}

            except FuturesTimeout:
                future.cancel()
                results[node_id] = {
                    "status": "TIMEOUT",
                    "error": f"task_timeout > {per_task_budget:.1f}s",
                }

            except Exception as exc:
                logger.exception("Échec tâche DAG | node=%s", node_id)
                results[node_id] = {
                    "status": "FAILED",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }

        return results

    # --------------------------------------------------------------------------
    # CYCLE DE VIE
    # --------------------------------------------------------------------------
    def shutdown(self, wait: bool = True) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        logger.info("DAGExecutionEngine : arrêt (wait=%s)", wait)
        try:
            self._executor.shutdown(wait=wait, cancel_futures=True)
        except TypeError:
            # Python < 3.9 sans cancel_futures
            self._executor.shutdown(wait=wait)

    def __enter__(self) -> "DAGExecutionEngine":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown(wait=True)


# ==============================================================================
# TEST AUTONOME — à lancer après création
# ==============================================================================
if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    print("\n=== TEST 1 : génération simple, 3 tâches en parallèle ===")
    g = nx.DiGraph()
    g.add_nodes_from(["a", "b", "c"])

    def make_task(name, sleep_s):
        def _task():
            time.sleep(sleep_s)
            return {"status": "OK", "node": name, "slept": sleep_s}
        return _task

    with DAGExecutionEngine(max_workers=4) as engine:
        t0 = time.monotonic()
        res = engine.execute_dag(
            g,
            {
                "a": make_task("a", 0.5),
                "b": make_task("b", 0.5),
                "c": make_task("c", 0.5),
            },
        )
        elapsed = time.monotonic() - t0
        print(f"Résultats : {res}")
        print(f"Durée totale : {elapsed:.2f}s (attendu ~0.5s si parallèle)")
        assert elapsed < 1.0, "❌ Pas de parallélisme !"
        assert all(r["status"] == "OK" for r in res.values())
        print("✅ TEST 1 OK")

    print("\n=== TEST 2 : une tâche plante, les autres survivent ===")
    g2 = nx.DiGraph()
    g2.add_nodes_from(["ok1", "boom", "ok2"])

    def boom():
        raise ValueError("crash intentionnel")

    with DAGExecutionEngine(max_workers=4) as engine:
        res = engine.execute_dag(
            g2,
            {
                "ok1": make_task("ok1", 0.1),
                "boom": boom,
                "ok2": make_task("ok2", 0.1),
            },
        )
        print(f"Résultats : {res}")
        assert res["ok1"]["status"] == "OK"
        assert res["ok2"]["status"] == "OK"
        assert res["boom"]["status"] == "FAILED"
        assert res["boom"]["error_type"] == "ValueError"
        print("✅ TEST 2 OK")

    print("\n=== TEST 3 : timeout par tâche ===")
    g3 = nx.DiGraph()
    g3.add_node("slow")

    with DAGExecutionEngine(max_workers=2, task_timeout_s=0.3) as engine:
        res = engine.execute_dag(g3, {"slow": make_task("slow", 2.0)})
        print(f"Résultats : {res}")
        assert res["slow"]["status"] == "TIMEOUT"
        print("✅ TEST 3 OK")

    print("\n=== TEST 4 : handler manquant ===")
    g4 = nx.DiGraph()
    g4.add_node("orphan")

    with DAGExecutionEngine(max_workers=2) as engine:
        res = engine.execute_dag(g4, {})
        print(f"Résultats : {res}")
        assert res["orphan"]["status"] == "MISSING_HANDLER"
        print("✅ TEST 4 OK")

    print("\n🎉 TOUS LES TESTS PASSENT — ÉTAPE 1 VALIDÉE.\n")