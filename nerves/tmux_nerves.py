# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 14+15+16+17 — TMUX / WIMUX RELIÉ AU CERVEAU (v3 — Compatibilité Totale)
# ==============================================================================

from __future__ import annotations

import logging
import os
import platform
import subprocess
from typing import Any, Dict, List

logger = logging.getLogger("bek.nerves.tmux")


# ------------------------------------------------------------------------------
# DÉTECTION DE L'ENVIRONNEMENT
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_TMUX_NERVES", "true").lower() in ("true", "1", "yes")


def _get_multiplexer_cmd() -> str:
    """Détecte l'OS et retourne la bonne commande."""
    if platform.system() == "Windows":
        return "wimux"
    return "tmux"


# ------------------------------------------------------------------------------
# PONTS EVENTBUS & STATE
# ------------------------------------------------------------------------------

def _publish_event(topic: str, payload: Dict[str, Any]) -> None:
    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified(topic, payload)
        return
    except Exception:
        pass
    try:
        from event_bus import EventBusKafka
        bus = EventBusKafka()
        bus.publish(topic, payload)
    except Exception:
        pass


def _persist_task_state(session_name: str, state: str, correlation_id: str = "", timeout_sec: float = 2.0) -> None:
    try:
        import concurrent.futures
        from state_synchronizer import update_task_state

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                update_task_state,
                task_id=session_name,
                state=state,
                correlation_id=correlation_id,
                payload=f"tmux_session:{session_name}",
            )
            try:
                future.result(timeout=timeout_sec)
            except concurrent.futures.TimeoutError:
                logger.debug("[Nerf 15] Persistance Neon timeout")
    except Exception:
        pass


# ------------------------------------------------------------------------------
# HANDLERS RÉELS (WIMUX / TMUX NATIF)
# ------------------------------------------------------------------------------

def _handler_tmux_start_task(session_name: str = "", command: str = "", **kwargs: Any) -> Dict[str, Any]:
    if not session_name or not command:
        return {"status": "error", "message": "session_name et command sont obligatoires."}

    mux = _get_multiplexer_cmd()
    
    # 1. Tentative Native
    try:
        # Construction de la commande selon l'outil
        if mux == "wimux":
            # wimux n'a pas besoin de -d, et utilise 'new'
            cmd = [mux, "new", "-s", session_name, command]
        else:
            # tmux classique
            cmd = [mux, "new-session", "-d", "-s", session_name, command]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            _publish_event("skills-index", {"action": "tmux_start_task", "session_name": session_name, "status": "RUNNING", "mux": mux})
            _persist_task_state(session_name, "RUNNING")
            return {"status": "success", "message": f"Tâche lancée via {mux}.", "session": session_name}
        else:
            logger.warning(f"[Nerf 14] Échec natif {mux} : {result.stderr}")
    except FileNotFoundError:
        logger.warning(f"[Nerf 14] {mux} non installé. Fallback sur services.tasks.")
    except Exception as e:
        logger.warning(f"[Nerf 14] Exception {mux} : {e}. Fallback.")

    # 2. Fallback : ancien système services.tasks.py
    try:
        from services.tasks import start_background_task
        result = start_background_task(session_name, command)
        _publish_event("skills-index", {"action": "tmux_start_task", "session_name": session_name, "status": "RUNNING", "mux": "services.tasks"})
        _persist_task_state(session_name, "RUNNING")
        return result or {"status": "success", "message": "Tâche lancée (fallback)."}
    except Exception as exc:
        return {"status": "error", "message": f"Échec total de lancement : {exc}"}


def _handler_tmux_stop_task(session_name: str = "", **kwargs: Any) -> Dict[str, Any]:
    if not session_name:
        return {"status": "error", "message": "session_name est obligatoire."}

    mux = _get_multiplexer_cmd()
    
    # 1. Tentative Native (kill-session est identique sur les deux)
    try:
        cmd = [mux, "kill-session", "-t", session_name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            _publish_event("skills-index", {"action": "tmux_stop_task", "session_name": session_name, "status": "KILLED", "mux": mux})
            _persist_task_state(session_name, "COMPLETED")
            return {"status": "success", "message": f"Session tuée via {mux}."}
    except Exception:
        pass

    # 2. Fallback
    try:
        from services.tasks import stop_background_task
        result = stop_background_task(session_name)
        _publish_event("skills-index", {"action": "tmux_stop_task", "session_name": session_name, "status": "COMPLETED", "mux": "services.tasks"})
        _persist_task_state(session_name, "COMPLETED")
        return result or {"status": "success", "message": "Tâche arrêtée (fallback)."}
    except Exception as exc:
        return {"status": "error", "message": f"Échec total d'arrêt : {exc}"}


def _handler_tmux_list_tasks(**kwargs: Any) -> Dict[str, Any]:
    mux = _get_multiplexer_cmd()
    
    # 1. Tentative Native
    try:
        # Construction de la commande selon l'outil
        if mux == "wimux":
            cmd = [mux, "ls"]
        else:
            cmd = [mux, "list-sessions"]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0 and result.stdout:
            sessions = []
            for line in result.stdout.strip().split('\n'):
                # Le split(':') fonctionne pour wimux (ex: "test_bek: 1 fenêtre(s)") et tmux
                name = line.split(':')[0].strip()
                if name:
                    sessions.append({"session_name": name, "alive": True, "mux": mux})
            return {"status": "success", "count": len(sessions), "tasks": sessions, "os": os.name}
        elif result.returncode != 0 and ("no server running" in result.stderr.lower() or "aucun serveur" in result.stderr.lower()):
             return {"status": "success", "count": 0, "tasks": [], "os": os.name}
    except Exception:
        pass

    # 2. Fallback
    try:
        from services.tasks import RUNNING_BACKGROUND_TASKS
        tasks_snapshot = dict(RUNNING_BACKGROUND_TASKS or {})
        tasks_report = [{"session_name": k, "pid": v, "alive": True, "mux": "services.tasks"} for k, v in tasks_snapshot.items()]
        return {"status": "success", "count": len(tasks_report), "tasks": tasks_report, "os": os.name}
    except Exception as exc:
        return {"status": "error", "message": f"Échec listage : {exc}"}


def _handler_tmux_task_status(session_name: str = "", **kwargs: Any) -> Dict[str, Any]:
    if not session_name:
        return {"status": "error", "message": "session_name est obligatoire."}

    mux = _get_multiplexer_cmd()
    
    # 1. Tentative Native (capture-pane est identique sur les deux)
    try:
        cmd = [mux, "capture-pane", "-t", session_name, "-p"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            logs = [line for line in result.stdout.split('\n') if line.strip()]
            return {
                "status": "success",
                "session_name": session_name,
                "alive": True,
                "mux": mux,
                "log_tail": logs[-50:]
            }
    except Exception:
        pass

    # 2. Fallback
    try:
        from services.tasks import RUNNING_BACKGROUND_TASKS
        from core.paths import GENERATED_DIR
        pid = (RUNNING_BACKGROUND_TASKS or {}).get(session_name)
        
        log_tail = []
        log_path = os.path.join(GENERATED_DIR, f"{session_name}_logs.txt")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                log_tail = [line.rstrip("\n") for line in f.readlines()[-50:]]

        return {
            "status": "success",
            "session_name": session_name,
            "pid": pid,
            "alive": pid is not None,
            "mux": "services.tasks",
            "log_path": log_path if os.path.exists(log_path) else None,
            "log_tail": log_tail,
        }
    except Exception as exc:
        return {"status": "error", "message": f"Échec statut : {exc}"}


# ------------------------------------------------------------------------------
# BRIDGES & ACTIVATION (Inchangés)
# ------------------------------------------------------------------------------

def tmux_start_for_guardian(task_name: str, command: str) -> Dict[str, Any]:
    return _handler_tmux_start_task(session_name=f"guardian_{task_name}", command=command)

def tmux_start_for_sub_crm(sub_crm_id: str, task_name: str, command: str) -> Dict[str, Any]:
    safe_id = str(sub_crm_id).replace("-", "")[:12]
    return _handler_tmux_start_task(session_name=f"subcrm_{safe_id}_{task_name}", command=command)

TMUX_NERVES_TABLE: Dict[str, tuple] = {
    "tmux_start_task":   (_handler_tmux_start_task,   "L3"),
    "tmux_stop_task":    (_handler_tmux_stop_task,    "L3"),
    "tmux_list_tasks":   (_handler_tmux_list_tasks,   "L1"),
    "tmux_task_status":  (_handler_tmux_task_status,  "L1"),
}

def activate_tmux_nerves() -> Dict[str, Any]:
    if not _is_enabled():
        return {"status": "disabled"}

    try:
        from hermes_core import hermes
    except ImportError as exc:
        return {"status": "error", "message": str(exc)}

    activated = []
    failed = []
    for tool_name, (handler, risk_level) in TMUX_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})

    mux = _get_multiplexer_cmd()
    logger.info(f"✅ [Nerf 14-17] Activation terminée. Moteur détecté : {mux}")

    return {
        "status": "ok",
        "activated_tools": activated,
        "failed": failed,
        "detected_multiplexer": mux
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(activate_tmux_nerves())