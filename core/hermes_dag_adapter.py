# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Hermes DAG Adapter (ADR-001 CPU-HIGH-DENSITY)
# ------------------------------------------------------------------------------
# Pont entre un goal_plan (format GOAP / Hermes) et le moteur DAG.
#
# Corrections vs version précédente :
#   1. Détection de cycle AVANT exécution → erreur explicite avec le cycle.
#   2. Propagation d'échec parent → un node dont un parent a échoué est SKIPPED.
#   3. Résolution de placeholders respecte le type (pas de str() aveugle).
#   4. Logging structuré de chaque étape et de chaque skip.
# ==============================================================================
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

import networkx as nx

from core.execution_engine import DAGExecutionEngine

logger = logging.getLogger("bek.hermes.dag_adapter")


# ==============================================================================
# ORCHESTRATEUR DAG
# ==============================================================================
class HermesDAGOrchestrator:
    """
    Convertit un goal_plan GOAP en DAG et exécute les étapes
    en parallèle par vagues topologiques.

    Format attendu du goal_plan :
        {
            "plan_id": "plan_xxx",
            "steps": [
                {
                    "id": "step_1",
                    "action": "tool_name",
                    "params": {...},
                    "depends_on": ["step_0", ...]   # optionnel
                },
                ...
            ]
        }
    """

    def __init__(self, max_workers: Optional[int] = None) -> None:
        self.dag_engine = DAGExecutionEngine(max_workers=max_workers)

    # --------------------------------------------------------------------------
    # RÉSOLUTION DE PARAMÈTRES
    # --------------------------------------------------------------------------
    def _resolve_params(
        self,
        params: Any,
        previous_outputs: Dict[str, Any],
    ) -> Any:
        """
        Remplace récursivement les placeholders `{{step_id.output}}`
        par la valeur réelle produite par l'étape précédente.

        Règles :
          - Si le placeholder est SEUL dans la string → la valeur brute est
            renvoyée (préserve int, dict, list, etc.).
          - Si le placeholder est ENTOURÉ de texte → conversion string.
          - Récursion sur dict / list.
        """
        if isinstance(params, str):
            # Cas 1 : string = uniquement un placeholder → préserver le type
            for step_id, out in previous_outputs.items():
                placeholder = f"{{{{{step_id}.output}}}}"
                if params == placeholder:
                    return out
            # Cas 2 : placeholder(s) imbriqué(s) dans du texte → string
            result = params
            for step_id, out in previous_outputs.items():
                placeholder = f"{{{{{step_id}.output}}}}"
                if placeholder in result:
                    result = result.replace(placeholder, self._safe_str(out))
            return result

        if isinstance(params, dict):
            return {
                k: self._resolve_params(v, previous_outputs)
                for k, v in params.items()
            }

        if isinstance(params, list):
            return [
                self._resolve_params(item, previous_outputs)
                for item in params
            ]

        return params

    @staticmethod
    def _safe_str(value: Any) -> str:
        """Convertit une valeur en string de façon sûre et lisible."""
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                return repr(value)
        return str(value)

    # --------------------------------------------------------------------------
    # CONSTRUCTION DU DAG
    # --------------------------------------------------------------------------
    def _build_dag(
        self,
        goal_plan: Dict[str, Any],
    ) -> nx.DiGraph:
        dag = nx.DiGraph()
        steps = goal_plan.get("steps", [])

        for step in steps:
            node_id = step.get("id")
            if not node_id:
                raise ValueError("Chaque step doit avoir un 'id'.")

            action = step.get("action")
            if not action:
                raise ValueError(f"Step '{node_id}' : 'action' manquante.")

            dag.add_node(
                node_id,
                action=action,
                raw_params=step.get("params", {}),
            )

            for parent_id in step.get("depends_on", []) or []:
                if parent_id not in dag:
                    # Parent déclaré mais pas encore ajouté → on l'ajoute
                    # (cela peut arriver si l'ordre des steps n'est pas topologique)
                    dag.add_node(parent_id, action=None, raw_params={})
                dag.add_edge(parent_id, node_id)

        return dag

    # --------------------------------------------------------------------------
    # EXÉCUTION
    # --------------------------------------------------------------------------
    def execute_goal_plan(
        self,
        goal_plan: Dict[str, Any],
        action_handlers: Dict[str, Callable[..., Any]],
    ) -> Dict[str, Any]:
        """
        Convertit le goal_plan en DAG et exécute les étapes en parallèle.

        Returns:
            {node_id: résultat} — chaque résultat est un dict.
            Les nodes SKIPPED ont la forme :
                {"status": "SKIPPED", "reason": "parents en échec : [...]"}
        """
        plan_id = goal_plan.get("plan_id", "plan_inconnu")

        # ----- 1. Construction -----
        dag = self._build_dag(goal_plan)

        # ----- 2. Détection de cycle -----
        if not nx.is_directed_acyclic_graph(dag):
            cycles = list(nx.simple_cycles(dag))[:3]
            msg = f"Plan '{plan_id}' contient un cycle : {cycles}"
            logger.error(msg)
            raise ValueError(msg)

        logger.info(
            "🚀 [DAG] Exécution plan '%s' (%d étapes, %d arêtes)",
            plan_id,
            dag.number_of_nodes(),
            dag.number_of_edges(),
        )

        # ----- 3. Exécution par générations topologiques -----
        results: Dict[str, Any] = {}
        generation_index = 0

        for generation in nx.topological_generations(dag):
            generation_index += 1
            logger.debug(
                "  → Génération %d : %d nœuds",
                generation_index,
                len(generation),
            )

            task_registry: Dict[str, Callable[[], Any]] = {}

            for node_id in generation:
                node_data = dag.nodes[node_id]
                action_name = node_data.get("action")

                # --- 3a. Propagate parent failures ---
                failed_parents = [
                    p
                    for p in dag.predecessors(node_id)
                    if self._is_failure(results.get(p))
                ]
                if failed_parents:
                    logger.warning(
                        "  ⏭️  Node '%s' SKIPPED (parents en échec : %s)",
                        node_id,
                        failed_parents,
                    )
                    task_registry[node_id] = (
                        lambda fp=list(failed_parents): {
                            "status": "SKIPPED",
                            "reason": f"parents en échec : {fp}",
                        }
                    )
                    continue

                # --- 3b. Handler manquant ---
                handler = action_handlers.get(action_name) if action_name else None
                if not handler:
                    task_registry[node_id] = (
                        lambda a=action_name, n=node_id: {
                            "status": "FAILED",
                            "error": f"Handler introuvable pour '{n}' (action='{a}')",
                            "error_type": "MISSING_HANDLER",
                        }
                    )
                    continue

                # --- 3c. Résolution des params ---
                resolved = self._resolve_params(
                    node_data.get("raw_params", {}),
                    results,
                )

                # --- 3d. Wrapping : handler(resolved_params) ---
                task_registry[node_id] = (
                    lambda p=resolved, h=handler: h(p)
                )

            # --- 3e. Exécution parallèle de la génération ---
            gen_results = self.dag_engine.execute_dag(
                dag.subgraph(generation),
                task_registry,
            )
            results.update(gen_results)

        return results

    # --------------------------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------------------------
    @staticmethod
    def _is_failure(result: Any) -> bool:
        """Détermine si un résultat de node est considéré comme un échec."""
        if result is None:
            return True  # pas encore exécuté → on bloque par prudence
        if not isinstance(result, dict):
            return False  # résultat brut (valeur) → considéré OK
        status = result.get("status")
        if status in ("FAILED", "TIMEOUT", "SKIPPED", "MISSING_HANDLER",
                      "INVALID_HANDLER", "ENGINE_SHUTDOWN"):
            return True
        if result.get("success") is False:
            return True
        return False

    # --------------------------------------------------------------------------
    # CYCLE DE VIE
    # --------------------------------------------------------------------------
    def shutdown(self, wait: bool = True) -> None:
        self.dag_engine.shutdown(wait=wait)

    def __enter__(self) -> "HermesDAGOrchestrator":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown(wait=True)


# ==============================================================================
# TEST AUTONOME
# ==============================================================================
if __name__ == "__main__":
    import logging as _logging
    import time as _time

    _logging.basicConfig(
        level=_logging.DEBUG,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    # ----- Handlers factices -----
    def echo_handler(params):
        _time.sleep(0.2)
        return {"status": "OK", "received": params}

    def failing_handler(params):
        raise RuntimeError("panne simulée")

    def slow_handler(params):
        _time.sleep(1.5)
        return {"status": "OK", "received": params}

    handlers = {
        "echo": echo_handler,
        "fail": failing_handler,
        "slow": slow_handler,
    }

    # ==========================================================================
    print("\n=== TEST 1 : plan linéaire A → B → C ===")
    plan1 = {
        "plan_id": "t1_linear",
        "steps": [
            {"id": "a", "action": "echo", "params": {"query": "start"}},
            {"id": "b", "action": "echo", "params": {"query": "{{a.output}}"},
             "depends_on": ["a"]},
            {"id": "c", "action": "echo", "params": {"query": "{{b.output}}"},
             "depends_on": ["b"]},
        ],
    }
    with HermesDAGOrchestrator(max_workers=4) as orch:
        r = orch.execute_goal_plan(plan1, handlers)
    print(json.dumps(r, indent=2, default=str))
    assert all(v.get("status") == "OK" for v in r.values())
    print("✅ TEST 1 OK")

    # ==========================================================================
    print("\n=== TEST 2 : parallélisme (A → B, A → C) ===")
    plan2 = {
        "plan_id": "t2_parallel",
        "steps": [
            {"id": "a", "action": "echo", "params": {"q": "root"}},
            {"id": "b", "action": "echo", "params": {"q": "{{a.output}}"},
             "depends_on": ["a"]},
            {"id": "c", "action": "echo", "params": {"q": "{{a.output}}"},
             "depends_on": ["a"]},
        ],
    }
    with HermesDAGOrchestrator(max_workers=4) as orch:
        t0 = _time.monotonic()
        r = orch.execute_goal_plan(plan2, handlers)
        elapsed = _time.monotonic() - t0
    print(f"Durée : {elapsed:.2f}s (B et C en parallèle → ~0.4s)")
    assert 0.3 < elapsed < 0.6, f"Parallélisme non détecté : {elapsed}s"
    print("✅ TEST 2 OK")

    # ==========================================================================
    print("\n=== TEST 3 : propagation d'échec (A fail → B skip) ===")
    plan3 = {
        "plan_id": "t3_propagation",
        "steps": [
            {"id": "a", "action": "fail", "params": {}},
            {"id": "b", "action": "echo", "params": {"q": "{{a.output}}"},
             "depends_on": ["a"]},
            {"id": "c", "action": "echo", "params": {"q": "indep"}},
        ],
    }
    with HermesDAGOrchestrator(max_workers=4) as orch:
        r = orch.execute_goal_plan(plan3, handlers)
    print(json.dumps(r, indent=2, default=str))
    assert r["a"]["status"] == "FAILED"
    assert r["b"]["status"] == "SKIPPED"
    assert r["c"]["status"] == "OK"
    print("✅ TEST 3 OK")

    # ==========================================================================
    print("\n=== TEST 4 : cycle détecté ===")
    plan4 = {
        "plan_id": "t4_cycle",
        "steps": [
            {"id": "a", "action": "echo", "params": {}, "depends_on": ["b"]},
            {"id": "b", "action": "echo", "params": {}, "depends_on": ["a"]},
        ],
    }
    with HermesDAGOrchestrator(max_workers=4) as orch:
        try:
            orch.execute_goal_plan(plan4, handlers)
            raise AssertionError("Aurait dû lever ValueError")
        except ValueError as e:
            print(f"Cycle bien détecté : {e}")
    print("✅ TEST 4 OK")

    # ==========================================================================
    print("\n=== TEST 5 : handler manquant ===")
    plan5 = {
        "plan_id": "t5_missing",
        "steps": [
            {"id": "a", "action": "inexistant", "params": {}},
        ],
    }
    with HermesDAGOrchestrator(max_workers=4) as orch:
        r = orch.execute_goal_plan(plan5, handlers)
    print(json.dumps(r, indent=2, default=str))
    assert r["a"]["status"] == "FAILED"
    assert r["a"]["error_type"] == "MISSING_HANDLER"
    print("✅ TEST 5 OK")

    # ==========================================================================
    print("\n=== TEST 6 : résolution de type préservée ===")
    plan6 = {
        "plan_id": "t6_types",
        "steps": [
            {"id": "a", "action": "echo", "params": {"q": "start"}},
            {"id": "b", "action": "echo", "params": "{{a.output}}",
             "depends_on": ["a"]},
        ],
    }
    with HermesDAGOrchestrator(max_workers=4) as orch:
        r = orch.execute_goal_plan(plan6, handlers)
    # Le paramètre "params" de b doit être le dict retourné par a (pas une string)
    assert isinstance(r["b"]["received"], dict), \
        f"Type perdu : {type(r['b']['received'])}"
    print(f"Type préservé : {type(r['b']['received']).__name__}")
    print("✅ TEST 6 OK")

    print("\n🎉 TOUS LES TESTS PASSENT — ÉTAPE 2 VALIDÉE.\n")