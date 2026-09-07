import os
import logging

logger = logging.getLogger("BEK-EvalGuard")

def evaluate_response_quality(user_query: str, agent_response: str) -> dict:
    """
    Vérification légère de la qualité de la réponse et anti-hallucination 
    inspirée des concepts d'évaluation modulaire.
    """
    checks = {
        "is_empty": len(agent_response.strip()) == 0,
        "too_short": len(agent_response.strip()) < 10,
        "has_error_keyword": "error" in agent_response.lower() or "exception" in agent_response.lower()
    }
    
    score = 1.0
    if checks["is_empty"] or checks["has_error_keyword"]:
        score = 0.0
    elif checks["too_short"]:
        score = 0.5

    return {
        "score": score,
        "passed": score >= 0.5,
        "checks": checks
    }