"""
==============================================================================
BEK-v16 — Paths
------------------------------------------------------------------------------
Source unique des chemins applicatifs.
Ne contient aucune logique métier et ne modifie pas sys.path.
==============================================================================
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

WORKSPACE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Répertoires applicatifs
# ---------------------------------------------------------------------------

SKILLS_DIR = WORKSPACE_DIR / "skills"
FILES_DIR = WORKSPACE_DIR / "uploads"
GENERATED_DIR = WORKSPACE_DIR / "generated"
PLUGINS_DIR = WORKSPACE_DIR / "plugins"
DOCS_DIR = WORKSPACE_DIR / "docs"

# ---------------------------------------------------------------------------
# Initialisation des répertoires
# ---------------------------------------------------------------------------

for _directory in (
    SKILLS_DIR,
    FILES_DIR,
    GENERATED_DIR,
    PLUGINS_DIR,
    DOCS_DIR,
):
    _directory.mkdir(parents=True, exist_ok=True)