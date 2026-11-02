# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Core Package
# ==============================================================================

from __future__ import annotations

__version__ = "16.0"
__author__ = "BEK Architecture"

from core.paths import (
    WORKSPACE_DIR,
    SKILLS_DIR,
    FILES_DIR,
    GENERATED_DIR,
    PLUGINS_DIR,
    DOCS_DIR,
)

from core.utils import json_safe, json_response

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
