# -*- coding: utf-8 -*-
"""Test d'intégration HermesCore + DAG (Étape 3)."""
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

from hermes_core import HermesCore


def main():
    hermes = HermesCore(max_workers=4)

    # ----- TEST 1 : plan DAG 3 étapes, succès attendu -----
    print("\n=== TEST 1 : plan DAG simple ===")
    plan = {
        "plan_id": "integration_01",
        "steps": [
            {"id": "s1", "action": "default_llm", "params": {"query": "step1"}},
            {"id": "s2", "action": "default_llm", "params": {"query": "step2"},
             "depends_on": ["s1"]},
            {"id": "s3", "action": "default_llm", "params": {"query": "step3"},
             "depends_on": ["s1"]},
        ],
    }
    res = hermes.dispatch_dag_plan(plan)
    print(f"Status global : {res['status']}")
    print(f"Success : {res['success_count']} / {res['task_count']}")
    assert res["status"] == "SUCCESS", f"Attendu SUCCESS, reçu {res['status']}"
    assert res["success_count"] == 3
    assert res["failure_count"] == 0
    print("✅ TEST 1 OK")

    # ----- TEST 2 : action inconnue → FAILED global -----
    print("\n=== TEST 2 : action inconnue ===")
    plan2 = {
        "plan_id": "integration_02",
        "steps": [
            {"id": "s1", "action": "tool_qui_nexiste_pas", "params": {}},
        ],
    }
    res = hermes.dispatch_dag_plan(plan2)
    print(f"Status global : {res['status']}")
    print(f"Failure : {res['failure_count']}")
    assert res["status"] == "FAILED"
    assert res["failure_count"] == 1
    print("✅ TEST 2 OK")

    # ----- TEST 3 : cycle → INVALID_DAG -----
    print("\n=== TEST 3 : cycle ===")
    plan3 = {
        "plan_id": "integration_03",
        "steps": [
            {"id": "a", "action": "default_llm", "params": {}, "depends_on": ["b"]},
            {"id": "b", "action": "default_llm", "params": {}, "depends_on": ["a"]},
        ],
    }
    res = hermes.dispatch_dag_plan(plan3)
    print(f"Status global : {res['status']}")
    assert res["status"] == "INVALID_DAG"
    print("✅ TEST 3 OK")

    # ----- TEST 4 : plan vide → NO_STEPS -----
    print("\n=== TEST 4 : plan vide ===")
    res = hermes.dispatch_dag_plan({"plan_id": "empty", "steps": []})
    assert res["status"] == "NO_STEPS"
    print("✅ TEST 4 OK")

    hermes.shutdown()
    print("\n🎉 TOUS LES TESTS PASSENT — ÉTAPE 3 VALIDÉE.\n")


if __name__ == "__main__":
    main()