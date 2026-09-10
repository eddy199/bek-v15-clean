"""
core/security/path_guard.py
Phase 1 - Architecture v16 : Plomberie et Sécurité.
Verrouille tous les accès fichiers au seul répertoire WORKSPACE_DIR.
"""
import os
from pathlib import Path


class PathSecurityError(PermissionError):
    """Levée lorsqu'un chemin tente de s'échapper du WORKSPACE_DIR."""
    pass


def safe_path(path: str, *allowed_dirs: Path) -> Path:
    """
    Valide et résout un chemin relatif au WORKSPACE_DIR.

    - Rejette les chemins vides, absolus, les lecteurs (ex: C:) et les traversées ('..').
    - Retourne un Path absolu, normalisé, garanti contenu dans l'un des allowed_dirs ou WORKSPACE_DIR.
    - Lève PathSecurityError en cas de tentative d'évasion.
    """
    if not path or not str(path).strip():
        raise PathSecurityError("Chemin vide ou nul refusé.")

    workspace = Path(os.environ.get("WORKSPACE_DIR", "F:\\workspacekimi")).resolve()
    candidate = Path(str(path))

    if candidate.is_absolute() or candidate.drive or candidate.root:
        raise PathSecurityError(f"Chemin absolu interdit : {path}")

    resolved = (workspace / candidate).resolve()

    # Si aucun dossier spécifique n'est fourni, on autorise tout le workspace
    allowed = [workspace]
    if allowed_dirs:
        allowed.extend([d.resolve() for d in allowed_dirs])

    if not any(resolved.is_relative_to(a) for a in allowed):
        raise PathSecurityError(f"Évasion de répertoire détectée ou dossier non autorisé : {path}")

    return resolved