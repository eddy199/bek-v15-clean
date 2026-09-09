# ==============================================================================
# sync_manager.py — GESTIONNAIRE DE SYNCHRONISATION MULTI-GIT (BEK-v15.3)
# ==============================================================================

import os
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger("SyncManager")
WORKSPACE_DIR = Path(__file__).resolve().parent

def push_to_remotes(commit_message: str = "Auto-sync BEK-v15.3 agent state") -> dict:
    env_path = WORKSPACE_DIR / "env.txt"
    github_user, github_token = "eddy199", ""
    gitlab_user, gitlab_token = "lorianedoird", ""

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GITHUB_USERNAME="):
                    github_user = line.split("=", 1)[1].strip().strip('"\'')
                elif line.startswith("GITHUB_TOKEN="):
                    github_token = line.split("=", 1)[1].strip().strip('"\'')
                elif line.startswith("GITLAB_USERNAME="):
                    gitlab_user = line.split("=", 1)[1].strip().strip('"\'')
                elif line.startswith("GITLAB_TOKEN="):
                    gitlab_token = line.split("=", 1)[1].strip().strip('"\'')

    results = {}

    try:
        subprocess.run(["git", "config", "user.name", "BEK-Agent"], cwd=WORKSPACE_DIR, capture_output=True)
        subprocess.run(["git", "config", "user.email", "agent@bek.local"], cwd=WORKSPACE_DIR, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=WORKSPACE_DIR, capture_output=True)
        subprocess.run(["git", "commit", "-m", commit_message], cwd=WORKSPACE_DIR, capture_output=True)

        # 1. Push GitHub
        if github_token:
            gh_url = f"https://{github_user}:{github_token}@github.com/{github_user}/bek-v15-clean.git"
            gh_res = subprocess.run(["git", "push", gh_url, "main"], cwd=WORKSPACE_DIR, capture_output=True, text=True, timeout=30)
            results["github"] = "Succès" if gh_res.returncode == 0 else gh_res.stderr.strip()
        else:
            results["github"] = "Token GitHub absent"

        # 2. Push GitLab (Gitlit)
        if gitlab_token:
            gl_url = f"https://oauth2:{gitlab_token}@gitlab.com/{gitlab_user}/bek-v15-clean.git"
            gl_res = subprocess.run(["git", "push", gl_url, "main"], cwd=WORKSPACE_DIR, capture_output=True, text=True, timeout=30)
            results["gitlab"] = "Succès" if gl_res.returncode == 0 else gl_res.stderr.strip()
        else:
            # Fallback si pas de token spécifique GitLab, essai de push via le remote configuré
            gl_res = subprocess.run(["git", "push", "origin", "main"], cwd=WORKSPACE_DIR, capture_output=True, text=True, timeout=30)
            results["gitlab"] = "Succès" if gl_res.returncode == 0 else gl_res.stderr.strip()

        logger.info("[SyncManager] Synchronisation multi-dépôts exécutée : %s", results)
        return {"status": "success", "results": results}
    except Exception as e:
        logger.error("[SyncManager] Erreur critique push multi-git : %s", e)
        return {"status": "error", "message": str(e)}