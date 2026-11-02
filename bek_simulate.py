import logging
from bek_eval_guard import evaluate_response_quality

logger = logging.getLogger("BEK-Simulator")

def run_simulation_scenario(scenario_name: str, test_turns: list) -> dict:
    """
    Simule une suite de conversations multi-tours pour tester l'agent 
    avant déploiement, en s'appuyant sur le garde-fou d'évaluation.
    """
    results = []
    passed_all = True

    for turn_idx, turn in enumerate(test_turns, 1):
        user_query = turn.get("query", "")
        mock_agent_response = turn.get("response", "")

        # Applique l'évaluation de qualité (Brique 1) sur chaque tour
        eval_res = evaluate_response_quality(user_query, mock_agent_response)
        
        turn_result = {
            "turn": turn_idx,
        "query": user_query,
            "response": mock_agent_response,
            "evaluation": eval_res
        }
        results.append(turn_result)

        if not eval_res["passed"]:
            passed_all = False

    return {
        "scenario": scenario_name,
        "passed_all": passed_all,
        "turns_evaluated": len(results),
        "details": results
    }