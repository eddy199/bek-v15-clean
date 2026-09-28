# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Core Package
# ------------------------------------------------------------------------------
# Ce package regroupe les briques d'infrastructure :
#   - execution_engine.py    : moteur DAG parallèle (ADR-001)
#   - hermes_dag_adapter.py  : pont GOAP ↔ DAG
#   - logger.py              : logs JSON structurés
#   - paths.py               : chemins centralisés
#   - tracing.py             : OpenTelemetry
#   - utils.py               : helpers (json_safe, json_response)
#   - security/              : PathGuard + SkillSandbox AST
# ==============================================================================
from __future__ import annotations

__version__ = "16.0"
__author__ = "BEK Architecture"

# Expose les chemins les plus utilisés
from core.paths import (  # noqa: F401
    WORKSPACE_DIR,
    SKILLS_DIR,
    FILES_DIR,
    GENERATED_DIR,
    PLUGINS_DIR,
    DOCS_DIR,
)

# Expose le helper JSON-safe
from core.utils import json_safe, json_response  # noqa: F401

__all__ = [
    "__version__",
    "__author__",
    "WORKSPACE_DIR",
    "SKILLS_DIR",
    "FILES_DIR",
    "GENERATED_DIR",
    "PLUGINS_DIR",
    "DOCS_DIR",
    "json_safe",
    "json_response",
]