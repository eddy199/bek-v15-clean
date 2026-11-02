import logging
from pathlib import Path

logger = logging.getLogger("SyncManager")
WORKSPACE_DIR = Path(__file__).resolve().parent


def push_to_remotes(commit_message: str = "Auto-sync BEK agent state") -> dict:
    """Interface compatible avec l'API ; aucun push distant automatique."""
    logger.warning("[SyncManager] Synchronisation distante désactivée par sécurité.")
    return {
        "status": "disabled",
        "message": "Synchronisation distante désactivée ; aucune modification Git effectuée.",
        "results": {
            "github": "Non exécuté",
            "gitlab": "Non exécuté"
        }
    }
