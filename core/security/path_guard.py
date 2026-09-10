# ==============================================================================
# BEK-v16 — PathGuard : anti path-traversal [NOUVEAU — Phase 1 plomberie]
# ==============================================================================
from pathlib import Path

from core.paths import WORKSPACE_DIR, FILES_DIR, GENERATED_DIR

WORKSPACE = Path(WORKSPACE_DIR).resolve()
ALLOWED_DIRS = [WORKSPACE, Path(FILES_DIR).resolve(), Path(GENERATED_DIR).resolve()]


def safe_path(filename: str) -> Path:
    """Renvoie un chemin garanti DANS le workspace. Lève ValueError sinon."""
    candidate = (WORKSPACE / Path(filename).name).resolve()
    if not any(candidate.is_relative_to(a) for a in ALLOWED_DIRS):
        raise ValueError(f"Accès refusé hors workspace : {filename}")
    return candidate


def find_existing(filename: str) -> Path | None:
    """Cherche un fichier existant dans WORKSPACE / uploads / generated.
    Ne retourne JAMAIS un chemin hors des dossiers autorisés."""
    base = Path(filename).name
    for d in ALLOWED_DIRS:
        p = (d / base).resolve()
        if any(p.is_relative_to(a) for a in ALLOWED_DIRS) and p.is_file():
            return p
    return None
