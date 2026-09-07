def evaluate_response_quality(query: str, response: str) -> dict:
    is_empty = not response or not str(response).strip()
    if is_empty:
        return {'passed': False, 'score': 0.0, 'reason': 'Réponse vide', 'checks': {'is_empty': True, 'has_critical_error': False, 'valid_length': False}}
    response_lower = str(response).lower()
    critical_markers = ['exception critique', 'erreur critique', 'traceback (most recent call last)', 'unhandled exception:']
    has_critical_error = any(marker in response_lower for marker in critical_markers)
    valid_length = len(str(response).strip()) >= 5
    passed = (not is_empty) and (not has_critical_error) and valid_length
    score = 1.0 if passed else 0.0
    reason = 'Conforme' if passed else ('Erreur critique détectée' if has_critical_error else 'Longueur insuffisante')
    return {'passed': passed, 'score': score, 'reason': reason, 'checks': {'is_empty': is_empty, 'has_critical_error': has_critical_error, 'valid_length': valid_length}}
