# ==============================================================================
# BEK-v16 — Utilitaires JSON (extrait de app.py v15.3, DÉPLACÉ à l'identique)
# ==============================================================================
import json
from datetime import datetime

from fastapi.responses import JSONResponse


def json_safe(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return str(value)


def json_response(payload, status=200):
    return JSONResponse(content=json_safe(payload), status_code=status)
