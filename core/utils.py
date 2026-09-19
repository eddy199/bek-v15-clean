"""
==============================================================================
BEK-v16 — Utilitaires JSON
------------------------------------------------------------------------------
Utilitaires d'infrastructure partagés.
Aucune logique métier ou dépendance à un domaine particulier.
==============================================================================
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi.responses import JSONResponse


def json_safe(value: Any) -> Any:
    """
    Convertit récursivement une valeur en structure compatible JSON.

    Les types inconnus sont convertis en chaîne afin d'éviter les erreurs
    de sérialisation dans les réponses API.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return str(value)


def json_response(
    payload: Any,
    status: int = 200,
) -> JSONResponse:
    """
    Construit une réponse FastAPI JSON-safe.
    """
    return JSONResponse(
        content=json_safe(payload),
        status_code=status,
    )