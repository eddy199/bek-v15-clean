from bek_eval_guard import evaluate_response_quality

def test_valid_response():
    res = evaluate_response_quality("Explique Linux", "Linux est un système d'exploitation open-source basé sur un noyau puissant.")
    assert res["passed"] is True
    assert res["score"] == 1.0

def test_error_response():
    res = evaluate_response_quality("Bug", "Une exception critique est survenue dans le système.")
    assert res["passed"] is False
    assert res["score"] == 0.0

def test_empty_response():
    res = evaluate_response_quality("Test", "   ")
    assert res["passed"] is False
    assert res["checks"]["is_empty"] is True