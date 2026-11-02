# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v19 — Source Unique des Chemins Applicatifs (core/paths.py)
# ------------------------------------------------------------------------------
# ★ v19.4 (2026-10-25) — Unification des Workspaces (Audit Sécurité & Robustesse)
#   • Définition explicite de CODE_WORKSPACE = ROOT / "workspace"
#   • Protection de la racine du projet (aucun code généré n'écrit à la racine)
#   • Rétrocompatibilité totale (WORKSPACE_DIR, FILES_DIR, UPLOADS_DIR)
# ==============================================================================
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Racine du projet BEK (où se trouvent app.py, .env, hermes_core.py, etc.)
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent

# Rétrocompatibilité : WORKSPACE_DIR pointe vers la racine du projet
WORKSPACE_DIR = ROOT_DIR

# ---------------------------------------------------------------------------
# ★ WORKSPACE DÉDIÉ AU CODE & AGENTS (Confine toute la production de code)
# ---------------------------------------------------------------------------
_env_workspace = os.environ.get("BEK_CODE_WORKSPACE", "").strip()
if _env_workspace:
    CODE_WORKSPACE = Path(_env_workspace).resolve()
else:
    CODE_WORKSPACE = (ROOT_DIR / "workspace").resolve()

# ---------------------------------------------------------------------------
# Répertoires applicatifs
# ---------------------------------------------------------------------------
SKILLS_DIR = ROOT_DIR / "skills"
UPLOADS_DIR = ROOT_DIR / "uploads"
FILES_DIR = UPLOADS_DIR  # Alias historique pour rétrocompatibilité
GENERATED_DIR = ROOT_DIR / "generated"
PLUGINS_DIR = ROOT_DIR / "plugins"
DOCS_DIR = ROOT_DIR / "docs"

# ---------------------------------------------------------------------------
# Initialisation automatique et sécurisée des répertoires
# ---------------------------------------------------------------------------
for _directory in (
    CODE_WORKSPACE,
    SKILLS_DIR,
    UPLOADS_DIR,
    GENERATED_DIR,
    PLUGINS_DIR,
    DOCS_DIR,
):
    try:
        _directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass