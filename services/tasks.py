# ==============================================================================
# BEK-v16 — Tâches de fond multi-OS (extrait de app.py v15.3, DÉPLACÉ à l'identique)
# ==============================================================================
import os
import sys
import subprocess

import psutil

from core.paths import WORKSPACE_DIR, GENERATED_DIR

CURRENT_OS_NAME = "Windows" if os.name == "nt" else "Linux"

RUNNING_BACKGROUND_TASKS: dict[str, int] = {}


def start_background_task(session_name: str, command: str) -> dict:
    os.makedirs(GENERATED_DIR, exist_ok=True)
    log_file_path = os.path.abspath(os.path.join(GENERATED_DIR, f"{session_name}_logs.txt"))

    try:
        log_file = open(log_file_path, "w", encoding="utf-8")
        if sys.platform == "win32":
            win_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=WORKSPACE_DIR,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=win_flags
            )
        else:
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=WORKSPACE_DIR,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setpgrp
            )

        RUNNING_BACKGROUND_TASKS[session_name] = proc.pid
        return {
            "status": "success",
            "message": f"🚀 Tâche lancée en arrière-plan avec succès ({CURRENT_OS_NAME}) !\n- Session : `{session_name}`\n- PID : `{proc.pid}`\n- Logs : `{log_file_path}`"
        }
    except Exception as e:
        return {"status": "error", "message": f"Erreur démarrage tâche de fond : {str(e)}"}


def stop_background_task(session_name: str) -> dict:
    stopped_pids = []
    target_pid = RUNNING_BACKGROUND_TASKS.pop(session_name, None)

    if target_pid and psutil.pid_exists(target_pid):
        try:
            parent = psutil.Process(target_pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
            stopped_pids.append(target_pid)
        except Exception:
            pass

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(proc.info.get('cmdline') or [])
            pid = proc.info.get('pid')
            if pid and pid != os.getpid():
                if session_name in cmdline or (session_name == "monitor_task" and "system_monitor.py" in cmdline):
                    proc.kill()
                    stopped_pids.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if stopped_pids:
        return {
            "status": "success",
            "message": f"🛑 Session `{session_name}` arrêtée avec succès (PIDs purgés: {list(set(stopped_pids))})."
        }
    return {
        "status": "not_found",
        "message": f"ℹ️ Aucun processus actif trouvé pour la session `{session_name}`."
    }
