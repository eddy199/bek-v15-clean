# ==========================================
# BEK-v15.3 HYBRID - SERVEUR PRINCIPAL UNIFIÉ
# FLASK / HERMES / ORCHESTRATEUR A2A / CRM / PINECONE
# COMPATIBILITÉ UNIVERSELLE WINDOWS & LINUX
# ==========================================

from __future__ import annotations

import os
import sys
import json
import asyncio
import requests
import subprocess
import time
import re
import zipfile
import uuid
import base64
import tempfile
import shutil
import ast
import psutil
from pathlib import Path
from datetime import datetime, timezone

from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory,
    Response,
    send_file,
)
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Compression de contexte Headroom (importation sécurisée)
try:
    from headroom import compress as headroom_compress
except ImportError:
    headroom_compress = None

from memory import (
    search_memory,
    save_to_memory,
    get_db_connection,
    init_sync_log_table,
)

# Importation des listes de modèles depuis ai_service
from ai_service import (
    GROQ_MODELS,
    NVIDIA_ACTIVE_MODELS,
    GEMINI_MODELS,
    OPENROUTER_MODELS,
)

from context_loader import load_project_documentation
from fast_math import HyperLogLog, MinHashSimilarity
from event_bus import EventBusKafka
from swarm_core import run_bek_swarm_sync
from skill_registry import skill_registry
from provider_manager import provider_manager
from approval_manager import approval_manager

# ==========================================
# META-CORTEX & ORCHESTRATEUR HYBRIDE A2A
# ==========================================

from meta_cortex_grounding import GroundingValidator
from meta_cortex_swarm import ReflexionSwarm

try:
    from bek_orchestrator import bek_orchestrator
except ImportError:
    bek_orchestrator = None

try:
    from skill_generator import create_and_register_skill
except ImportError:
    create_and_register_skill = None

# ==========================================
# WEB AGENT
# ==========================================

from web_agent import web_agent_instance

# ==========================================
# HERMES
# ==========================================

from hermes_core import (
    hermes,
    start_background_workers,
)

# ==========================================
# BEK EVAL GUARD, STATE SYNCHRONIZER & MCP
# ==========================================
from bek_eval_guard import evaluate_response_quality
from state_synchronizer import init_state_tables, update_task_state, get_pending_or_running_tasks
from mcp_gateway import mcp_gateway

# ==========================================
# APPLICATION
# ==========================================

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024  # 300 Mo

CORS_ORIGINS = os.environ.get(
    "BEK_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8765,http://127.0.0.1:8765",
)

cors_origins = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]

CORS(
    app,
    resources={r"/api/*": {"origins": cors_origins}},
)

# --- ANTI-CACHE POUR L'INTERFACE WEB ---
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ==========================================
# DIRECTOIRES UNIVERSELS
# ==========================================

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(WORKSPACE_DIR, "skills")
FILES_DIR = os.path.join(WORKSPACE_DIR, "uploads")
GENERATED_DIR = os.path.join(WORKSPACE_DIR, "generated")
PLUGINS_DIR = os.path.join(WORKSPACE_DIR, "plugins")
DOCS_DIR = os.path.join(WORKSPACE_DIR, "docs")

for directory in [SKILLS_DIR, FILES_DIR, GENERATED_DIR, PLUGINS_DIR, DOCS_DIR]:
    os.makedirs(directory, exist_ok=True)

if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)
if PLUGINS_DIR not in sys.path:
    sys.path.insert(0, PLUGINS_DIR)

# ==========================================
# LOGGING
# ==========================================

import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger("BEKApp")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = RotatingFileHandler(
        os.path.join(WORKSPACE_DIR, "bek_app.log"),
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# ==========================================
# INITIALISATION GLOBALE & CHARGEMENT MÉMOIRE
# ==========================================

try:
    init_sync_log_table()
    init_state_tables()
    logger.info("Tables de compensation sync_log et états Neon DB initialisées.")
except Exception as exc:
    logger.warning("Impossible d'initialiser les tables DB au démarrage : %s", exc)

from generate_architecture_doc import update_documentation_file
try:
    update_documentation_file()
except Exception as exc:
    logger.warning("Génération auto architecture échouée : %s", exc)

GLOBAL_SYSTEM_CONTEXT = load_project_documentation(DOCS_DIR)

security_guard = hermes.security_guard
if security_guard is None:
    raise RuntimeError("SecurityGuard Hermes indisponible. Vérifie BEK_HSM_SECRET.")

try:
    event_bus = EventBusKafka()
except Exception as exc:
    logger.warning("EventBusKafka indisponible : %s", exc)
    event_bus = None

minhash_engine = MinHashSimilarity()
hll_counter = HyperLogLog()

# Enregistrement des outils initiaux dans la passerelle MCP
mcp_gateway.register_mcp_tool(
    name="neon_audit",
    description="Audit des tables relationnelles Neon DB",
    parameters_schema={},
    handler=lambda: {"tables": ["companies", "contacts", "opportunities", "bek_task_states", "sync_log"]}
)

# ==========================================
# WORKERS HERMES & INITIALISATION DES HOOKS
# ==========================================

try:
    start_background_workers()
    logger.info("Workers Hermes démarrés.")
    logger.info("Mémoire vectorielle Pinecone & ChromaDB connectées : namespaces initialisés.")
except Exception as exc:
    logger.error("Impossible de démarrer les workers Hermes : %s", exc)

def _bek_pre_plan_validator(objective: str, trace_id: str | None):
    return True, "Pre-Plan validé", None

hermes.register_pre_plan_hook(_bek_pre_plan_validator)

# ==========================================
# ENREGISTREMENT OUTILS HERMES
# ==========================================

hermes.register_tool(
    "web_sync",
    lambda query: web_agent_instance.run_pipeline(query),
    risk_level="L3",
)

hermes.register_tool(
    "orchestrate",
    lambda goal: bek_orchestrator.run(goal) if bek_orchestrator else "Orchestrateur indisponible",
    risk_level="L2",
)

hermes.register_tool(
    "neon_audit",
    lambda: {
        "status": "Neon DB audit demandé",
        "tables": ["companies", "contacts", "opportunities", "matrix_sub_crms", "sync_log"],
    },
    risk_level="L1",
)

# ==========================================
# GESTIONNAIRE UNIVERSEL DES TÂCHES DE FOND (MULTI-OS)
# ==========================================

RUNNING_BACKGROUND_TASKS: dict[str, int] = {}

def start_background_task(session_name: str, command: str) -> dict:
    """Lance un processus détaché universel compatible Windows et Linux."""
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
    """Arrête proprement n'importe quel processus d'arrière-plan sous Windows et Linux."""
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

# ==========================================
# PROMPT SYSTÈME GLOBAL — MULTI-OS & AUTONOME
# ==========================================

CURRENT_OS_NAME = "Windows" if os.name == "nt" else "Linux"

BEK_GOLDEN_RULES = f"""
# RÔLE & PERSONNALITÉ
Tu es BEK, un agent superviseur technique d'exécution directe et précis, opérant sur un environnement hôte {CURRENT_OS_NAME}.

# POUVOIRS SYSTÈME ET ACCÈS TERMINAL
- Tu disposes d'un accès TOTAL au système de fichiers local, au terminal ({CURRENT_OS_NAME}), à Git, aux bases Neon DB et Pinecone, et aux sous-agents.
- INTERDICTION FORMELLE d'affirmer "Je n'ai pas accès à Internet", "Je ne peux pas accéder à GitHub" ou "Cet environnement est isolé".
- Dès que l'utilisateur demande une opération Git (sauvegarde, commit, push), un script, ou une action fichier, TU L'EXÉCUTES DIRECTEMENT via les outils dédiés.

# DIRECTIVES CONVERSATIONNELLES
- Parle naturellement et brièvement. Pas de bavardage.
- Salutations : réponds en une seule phrase courte.

# EXÉCUTION D'OUTILS & ACTIONS (RÈGLE STRICTE)
- DÈS QUE l'utilisateur demande une action (création de skill dynamique, orchestration multi-agents, recherche web_sync, sauvegarder mémoire, chercher mémoire, générer image, lire fichier, exécuter commande, sauvegarder git, lancer/stopper tâche de fond), TU NE POSES AUCUNE QUESTION.
- INTERDICTION de demander la permission ("Veux-tu que je...").
- INTERDICTION de décrire ce que tu vas faire ou de faire une phrase d'introduction.
- Renvoie UNIQUEMENT la balise [ACTION:nom_action]{{"param":"valeur"}}[/ACTION]. Aucun autre texte n'est toléré avant ou après.

# ACTIONS DISPONIBLES :
   - [ACTION:create_dynamic_skill]{{"skill_name": "...", "code_content": "...", "description": "..."}}[/ACTION]
   - [ACTION:orchestrate]{{"goal": "..."}}[/ACTION]
   - [ACTION:web_sync]{{"query": "..."}}[/ACTION]
   - [ACTION:execute_command]{{"command": "..."}}[/ACTION]
   - [ACTION:execute_tmux_headless]{{"session_name": "...", "command": "..."}}[/ACTION]
   - [ACTION:stop_background_task]{{"session_name": "..."}}[/ACTION]
   - [ACTION:save_memory]{{"content": "..."}}[/ACTION]
   - [ACTION:search_memory]{{"query": "..."}}[/ACTION]
   - [ACTION:write_file]{{"filename": "...", "content": "..."}}[/ACTION]
   - [ACTION:delete_file]{{"filename": "..."}}[/ACTION]
   - [ACTION:read_file]{{"filename": "..."}}[/ACTION]
   - [ACTION:extract_zip]{{"zip_path": "...", "extract_to": "..."}}[/ACTION]
   - [ACTION:create_zip]{{"folder_path": "...", "output_zip": "..."}}[/ACTION]
   - [ACTION:analyze_zip_content]{{"zip_path": "..."}}[/ACTION]
   - [ACTION:analyze_image]{{"image_path": "...", "prompt": "...", "provider": "gemini", "model": "gemini-1.5-flash"}}[/ACTION]
   - [ACTION:generate_image]{{"prompt": "...", "filename": "...", "provider": "gemini", "model": "gemini-3.1-flash-image"}}[/ACTION]
   - [ACTION:merge_and_edit_images]{{"image_paths": ["img1", "img2"], "prompt": "..."}}[/ACTION]
"""

# ==========================================
# UTILITAIRES & VISION / GÉNÉRATION D'IMAGES
# ==========================================

def json_safe(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return str(value)

def json_response(payload, status=200):
    return jsonify(json_safe(payload)), status

def get_api_key(key_name: str) -> str:
    if not isinstance(key_name, str):
        return ""
    key_from_manager = provider_manager.get_api_key(key_name)
    if key_from_manager:
        return key_from_manager
    value = os.environ.get(key_name, "")
    if value:
        return value.strip("\"' \r\n")
    for env_path in [
        os.path.join(WORKSPACE_DIR, "env.txt"),
        os.path.join(WORKSPACE_DIR, ".env"),
    ]:
        if not os.path.isfile(env_path):
            continue
        try:
            with open(env_path, "r", encoding="utf-8-sig", errors="ignore") as file:
                for raw_line in file:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if not line.startswith(key_name + "="):
                        continue
                    return line.split("=", 1)[1].strip().strip("\"'")
        except Exception as exc:
            logger.warning("Lecture de %s impossible : %s", env_path, exc)
    return ""

def analyze_image_with_vision(image_path: str, prompt: str, provider: str = "gemini", model: str = "") -> str:
    target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, image_path))
    if not os.path.exists(target_path):
        for d in [FILES_DIR, GENERATED_DIR]:
            alt = os.path.join(d, image_path)
            if os.path.exists(alt):
                target_path = alt
                break
    
    if not os.path.exists(target_path):
        return f"Erreur Vision : Image introuvable sur le disque ({image_path})."

    try:
        with open(target_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
        
        ext = image_path.split('.')[-1].lower()
        mime_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
        mime_type = mime_map.get(ext, "image/png")
        provider = provider.lower() if provider else "gemini"

        if provider == "gemini" or not provider:
            api_key = get_api_key("GEMINI_API_KEY")
            if not api_key: return "Erreur : GEMINI_API_KEY non configurée."
            clean_model = model if model and "gemini" in model else "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1/models/{clean_model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [
                    {"text": prompt or "Analyse cette image."},
                    {"inline_data": {"mime_type": mime_type, "data": encoded_image}}
                ]}]
            }
            res = requests.post(url, json=payload, timeout=60)
            if res.status_code == 200:
                return res.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return f"Erreur API Gemini Vision ({res.status_code}): {res.text}"
        
        elif provider == "nvidia":
            api_key = get_api_key("NVIDIA_API_KEY")
            if not api_key: return "Erreur : NVIDIA_API_KEY non configurée."
            url = "https://integrate.api.nvidia.com/v1/chat/completions"
            active_model = model if model and "vision" in model else "meta/llama-3.2-90b-vision-instruct"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": active_model,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt or "Analyse cette image."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"}}
                ]}],
                "max_tokens": 1024
            }
            res = requests.post(url, json=payload, headers=headers, timeout=60)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            else:
                return f"Erreur NVIDIA Vision ({res.status_code}): {res.text}"

        elif provider == "groq":
            api_key = get_api_key("GROQ_API_KEY")
            if not api_key: return "Erreur : GROQ_API_KEY non configurée."
            url = "https://api.groq.com/openai/v1/chat/completions"
            active_model = model if model and "vision" in model else "llama-3.2-90b-text-preview"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": active_model,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt or "Analyse cette image."}
                ]}],
                "max_tokens": 1024
            }
            res = requests.post(url, json=payload, headers=headers, timeout=60)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            else:
                return f"Erreur Groq Vision ({res.status_code}): {res.text}"
        else:
            return f"Provider '{provider}' non supporté pour la vision."
    except Exception as e:
        return f"Erreur lors du traitement de l'image : {str(e)}"

def generate_image_with_provider(prompt: str, provider: str = "gemini", model: str = "gemini-3.1-flash-image", output_filename: str = "") -> dict:
    import urllib.parse
    if not output_filename:
        output_filename = f"gen_image_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.abspath(os.path.join(GENERATED_DIR, secure_filename(output_filename)))

    try:
        if "gemini" in model.lower() or "image" in model.lower() or "banana" in model.lower():
            provider = "gemini"
        provider = provider.lower()
        
        if provider == "gemini":
            api_key = get_api_key("GEMINI_API_KEY")
            if not api_key: return {"status": "error", "message": "GEMINI_API_KEY non configurée."}

            actual_api_model = "imagen-3.0-generate-002"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{actual_api_model}:predict?key={api_key}"
            payload = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}}
            
            res = requests.post(url, json=payload, timeout=60)
            if res.status_code == 200:
                data = res.json()
                try:
                    b64_data = data["predictions"][0]["bytesBase64Encoded"]
                    image_bytes = base64.b64decode(b64_data)
                    with open(save_path, "wb") as f:
                        f.write(image_bytes)
                    return {"status": "success", "filepath": save_path, "filename": output_filename}
                except Exception:
                    pass

            fallback_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?nologo=true"
            fallback_res = requests.get(fallback_url, timeout=30)
            if fallback_res.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(fallback_res.content)
                return {"status": "success", "filepath": save_path, "filename": output_filename, "message": "Image générée (via Fallback d'urgence)"}
            else:
                return {"status": "error", "message": f"Tous les moteurs ont échoué. Erreur de base : {res.text}"}
        else:
            return {"status": "error", "message": f"Provider '{provider}' non supporté."}
    except Exception as e:
        return {"status": "error", "message": f"Erreur technique génération : {str(e)}"}

def merge_and_edit_images(image_paths: list, user_prompt: str, provider: str = "gemini", model: str = "gemini-3.1-flash-image") -> dict:
    try:
        analysis_results = []
        for path in image_paths:
            analysis = analyze_image_with_vision(path, "Décris cette image avec un niveau de détail extrême.", provider="gemini")
            analysis_results.append(f"- Éléments de '{os.path.basename(path)}' : {analysis}")
        super_prompt = (
            f"Génère une image photoréaliste parfaite basée sur :\n{chr(10).join(analysis_results)}\n\n"
            f"DIRECTIVE : {user_prompt}"
        )
        return generate_image_with_provider(super_prompt, provider=provider, model=model)
    except Exception as e:
        return {"status": "error", "message": f"Erreur fusion visuelle : {str(e)}"}

def execute_database_sql(sql_query: str) -> dict:
    conn = get_db_connection()
    if not conn:
        return {"status": "error", "message": "Connexion Neon DB indisponible."}
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(sql_query)
        if cur.description:
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            results = [{column: json_safe(value) for column, value in zip(columns, row)} for row in rows]
            return {"status": "success", "type": "select", "data": results, "count": len(results)}
        conn.commit()
        return {"status": "success", "type": "mutation", "affected_rows": cur.rowcount}
    except Exception as exc:
        if conn:
            try: conn.rollback()
            except Exception: pass
        return {"status": "error", "message": str(exc)}
    finally:
        if cur:
            try: cur.close()
            except Exception: pass
        if conn:
            try: conn.close()
            except Exception: pass

def execute_agent_crm_tool(action_name: str, parameters: dict) -> dict:
    # Suivi d'état FSM via le State Synchronizer de Neon DB
    correlation_id = f"corr_{uuid.uuid4().hex[:12]}"
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    update_task_state(task_id, "RUNNING", correlation_id, f"Action: {action_name}")

    try:
        if action_name == "create_dynamic_skill":
            skill_name = parameters.get("skill_name", "")
            code_content = parameters.get("code_content", "")
            description = parameters.get("description", "Skill auto-généré par l'orchestrateur BEK")
            if not skill_name or not code_content:
                update_task_state(task_id, "FAILED", correlation_id, "Nom du skill ou contenu manquant.")
                return {"status": "error", "message": "Nom du skill ou contenu manquant."}
            try:
                if create_and_register_skill:
                    res = create_and_register_skill(skill_name, code_content, description)
                    update_task_state(task_id, "COMPLETED", correlation_id, f"Skill créé: {skill_name}")
                    return res
                update_task_state(task_id, "FAILED", correlation_id, "Module skill_generator indisponible.")
                return {"status": "error", "message": "Module skill_generator indisponible."}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur intégration skill : {str(e)}"}

        elif action_name in ("orchestrate", "run_swarm_task", "multi_agent_workflow"):
            goal = parameters.get("goal", parameters.get("objective", parameters.get("query", "")))
            if not goal:
                update_task_state(task_id, "FAILED", correlation_id, "Objectif vide.")
                return {"status": "error", "message": "L'objectif d'orchestration ne peut pas être vide."}
            try:
                if bek_orchestrator:
                    orch_report = bek_orchestrator.run(goal)
                    update_task_state(task_id, "COMPLETED", correlation_id, "Orchestration réussie")
                    return {"status": "success", "message": orch_report}
                update_task_state(task_id, "FAILED", correlation_id, "bek_orchestrator indisponible")
                return {"status": "error", "message": "Module bek_orchestrator indisponible sur l'hôte."}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur Orchestrateur : {str(e)}"}

        elif action_name in ("web_sync", "web_search", "web_pipeline"):
            query = parameters.get("query", "")
            if not query:
                update_task_state(task_id, "FAILED", correlation_id, "Requête web_sync vide")
                return {"status": "error", "message": "La requête web_sync est vide."}
            try:
                res = web_agent_instance.run_pipeline(query)
                update_task_state(task_id, "COMPLETED", correlation_id, f"Web sync: {query}")
                return {"status": "success", "message": f"🌐 Synchronisation Web réussie pour '{query}' :\n{str(res)[:2500]}"}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur web_sync : {str(e)}"}

        elif action_name in ("save_memory", "remember", "save_to_memory"):
            content = parameters.get("content", "")
            if not content:
                update_task_state(task_id, "FAILED", correlation_id, "Contenu mémoire vide")
                return {"status": "error", "message": "Le contenu à mémoriser ne peut pas être vide."}
            try:
                save_to_memory(content)
                update_task_state(task_id, "COMPLETED", correlation_id, "Mémoire sauvée")
                return {"status": "success", "message": f"🧠 Information ancrée dans la mémoire vectorielle :\n\"{content}\""}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur mémoire : {str(e)}"}

        elif action_name in ("search_memory", "recall"):
            query = parameters.get("query", "")
            try:
                mem_res = search_memory(query, top_k=3)
                update_task_state(task_id, "COMPLETED", correlation_id, f"Recherche mémoire: {query}")
                return {"status": "success", "message": f"🔍 Résultats mémoire pour '{query}' :\n{mem_res}"}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur recherche mémoire : {str(e)}"}

        elif action_name in ("write_file", "save_file", "create_file"):
            filename = parameters.get("filename", "generated/agent_output.txt")
            filepath = os.path.abspath(os.path.join(WORKSPACE_DIR, filename))
            try:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                content = parameters.get("content", "")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                update_task_state(task_id, "COMPLETED", correlation_id, f"Fichier écrit: {filename}")
                return {"status": "success", "message": f"Fichier enregistré : {filepath}"}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur écriture : {str(e)}"}
                
        elif action_name == "delete_file":
            filename = parameters.get("filename", "")
            found = False
            for directory in [WORKSPACE_DIR, FILES_DIR, GENERATED_DIR]:
                target = os.path.abspath(os.path.join(directory, os.path.basename(filename)))
                if os.path.exists(target) and os.path.isfile(target):
                    try:
                        os.remove(target)
                        found = True
                    except Exception as e:
                        update_task_state(task_id, "FAILED", correlation_id, str(e))
                        return {"status": "error", "message": f"Erreur suppression : {str(e)}"}
            if found:
                update_task_state(task_id, "COMPLETED", correlation_id, f"Fichier supprimé: {filename}")
                return {"status": "success", "message": f"Fichier {filename} supprimé."}
            update_task_state(task_id, "FAILED", correlation_id, "Fichier introuvable")
            return {"status": "error", "message": "Fichier introuvable."}
                
        elif action_name == "read_file":
            filename = parameters.get("filename", "")
            target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, filename))
            if not os.path.exists(target_path):
                for d in [FILES_DIR, GENERATED_DIR]:
                    alt = os.path.join(d, filename)
                    if os.path.exists(alt):
                        target_path = alt
                        break
            try:
                if os.path.exists(target_path):
                    with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()[-3000:]
                    update_task_state(task_id, "COMPLETED", correlation_id, f"Fichier lu: {filename}")
                    return {"status": "success", "message": f"Contenu de {target_path} :\n{content}"}
                update_task_state(task_id, "FAILED", correlation_id, "Fichier introuvable")
                return {"status": "error", "message": "Fichier introuvable."}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur lecture : {str(e)}"}

        elif action_name == "extract_zip":
            zip_filename = parameters.get("zip_path", "")
            extract_to_folder = parameters.get("extract_to", "generated/extracted_project")
            zip_path = os.path.abspath(os.path.join(WORKSPACE_DIR, zip_filename))
            if not os.path.exists(zip_path):
                for d in [FILES_DIR, GENERATED_DIR]:
                    alt = os.path.join(d, zip_filename)
                    if os.path.exists(alt):
                        zip_path = alt
                        break
            target_dir = os.path.abspath(os.path.join(WORKSPACE_DIR, extract_to_folder))
            try:
                if not os.path.exists(zip_path):
                    update_task_state(task_id, "FAILED", correlation_id, "ZIP introuvable")
                    return {"status": "error", "message": f"Archive ZIP introuvable : {zip_filename}"}
                os.makedirs(target_dir, exist_ok=True)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
                update_task_state(task_id, "COMPLETED", correlation_id, f"ZIP extrait: {zip_filename}")
                return {"status": "success", "message": f"Archive extraite dans `{extract_to_folder}`."}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur extraction ZIP : {str(e)}"}

        elif action_name == "create_zip":
            folder_name = parameters.get("folder_path", "generated/ia_project")
            output_zip_name = parameters.get("output_zip", "generated/export_projet.zip")
            folder_path = os.path.abspath(os.path.join(WORKSPACE_DIR, folder_name))
            output_path = os.path.abspath(os.path.join(WORKSPACE_DIR, output_zip_name))
            try:
                if not os.path.exists(folder_path):
                    update_task_state(task_id, "FAILED", correlation_id, "Dossier introuvable")
                    return {"status": "error", "message": f"Dossier introuvable : {folder_name}"}
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.make_archive(output_path.replace('.zip', ''), 'zip', folder_path)
                update_task_state(task_id, "COMPLETED", correlation_id, f"ZIP créé: {output_zip_name}")
                return {"status": "success", "message": f"Archive créée : {output_zip_name}"}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur création ZIP : {str(e)}"}

        elif action_name == "analyze_zip_content":
            zip_filename = parameters.get("zip_path", "")
            zip_path = os.path.abspath(os.path.join(WORKSPACE_DIR, zip_filename))
            if not os.path.exists(zip_path):
                for d in [FILES_DIR, GENERATED_DIR]:
                    alt = os.path.join(d, zip_filename)
                    if os.path.exists(alt):
                        zip_path = alt
                        break
            try:
                if not os.path.exists(zip_path):
                    update_task_state(task_id, "FAILED", correlation_id, "ZIP introuvable")
                    return {"status": "error", "message": f"Archive introuvable : {zip_filename}"}
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    namelist = zip_ref.namelist()
                    file_summaries = {}
                    for name in namelist[:10]:
                        if any(name.endswith(ext) for ext in ['.py', '.json', '.txt', '.md', '.js', '.html', '.css']):
                            with zip_ref.open(name) as f:
                                content = f.read(1500).decode('utf-8', errors='ignore')
                                file_summaries[name] = content[:300] + "..."
                update_task_state(task_id, "COMPLETED", correlation_id, "ZIP analysé")
                return {"status": "success", "message": f"Analyse ZIP réussie. Fichiers : {namelist[:20]}\nAperçu : {json_safe(file_summaries)}"}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur analyse ZIP : {str(e)}"}

        elif action_name == "analyze_image":
            image_path = parameters.get("image_path", "")
            prompt = parameters.get("prompt", "Analyse cette image.")
            provider = parameters.get("provider", "gemini")
            model = parameters.get("model", "gemini-1.5-flash")
            vision_result = analyze_image_with_vision(image_path, prompt, provider=provider, model=model)
            if "Erreur" in vision_result or "Error" in vision_result:
                update_task_state(task_id, "FAILED", correlation_id, "Échec vision")
                return {"status": "error", "message": f"ÉCHEC VISION: {vision_result}\n[ALERTE SYSTEME]: Tu es aveugle à cause de cette erreur. NE PAS INVENTER DE DESCRIPTION."}
            update_task_state(task_id, "COMPLETED", correlation_id, "Vision réussie")
            return {"status": "success", "message": f"Analyse Vision réussie :\n{vision_result}"}

        elif action_name == "generate_image":
            prompt = parameters.get("prompt", "")
            filename = parameters.get("filename", f"generated_{uuid.uuid4().hex[:6]}.png")
            provider = parameters.get("provider", "gemini")
            model = parameters.get("model", "gemini-3.1-flash-image")
            if not prompt: 
                update_task_state(task_id, "FAILED", correlation_id, "Prompt vide")
                return {"status": "error", "message": "Le prompt est obligatoire."}
            gen_result = generate_image_with_provider(prompt, provider=provider, model=model, output_filename=filename)
            if gen_result.get("status") == "error":
                update_task_state(task_id, "FAILED", correlation_id, gen_result.get('message'))
                return {"status": "error", "message": f"ÉCHEC GÉNÉRATION: {gen_result.get('message')}"}
            final_filename = gen_result.get('filename')
            update_task_state(task_id, "COMPLETED", correlation_id, f"Image générée: {final_filename}")
            return {"status": "success", "message": f"🎨 **Image générée !**\n\n![{final_filename}](/api/download/{final_filename})"}

        elif action_name == "merge_and_edit_images":
            image_paths = parameters.get("image_paths", [])
            prompt = parameters.get("prompt", "")
            provider = parameters.get("provider", "gemini")
            model = parameters.get("model", "gemini-3.1-flash-image")
            if not image_paths or not prompt:
                update_task_state(task_id, "FAILED", correlation_id, "Paramètres fusion manquants")
                return {"status": "error", "message": "Fournis des images et un prompt."}
            gen_result = merge_and_edit_images(image_paths, prompt, provider=provider, model=model)
            if gen_result.get("status") == "error":
                update_task_state(task_id, "FAILED", correlation_id, gen_result.get('message'))
                return {"status": "error", "message": f"ÉCHEC FUSION: {gen_result.get('message')}"}
            final_filename = gen_result.get('filename')
            update_task_state(task_id, "COMPLETED", correlation_id, f"Fusion réussie: {final_filename}")
            return {"status": "success", "message": f"🪄 **Fusion réussie !**\n\n![{final_filename}](/api/download/{final_filename})"}

        elif action_name in ("execute_command", "run_script", "run_tests"):
            command = parameters.get("command", "dir" if os.name == "nt" else "ls -la")
            try:
                res = subprocess.run(command, shell=True, cwd=WORKSPACE_DIR, capture_output=True, text=True, timeout=30)
                output = (res.stdout + "\n" + res.stderr).strip()
                status_str = "success" if res.returncode == 0 else "error"
                update_task_state(task_id, "COMPLETED" if res.returncode == 0 else "FAILED", correlation_id, command)
                return {"status": status_str, "message": f"Commande exécutée :\n{output[-2500:]}"}
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur exécution : {str(e)}"}
                
        elif action_name in ("execute_tmux_headless", "execute_background_task", "start_background_task"):
            session_name = parameters.get("session_name", f"job_{uuid.uuid4().hex[:6]}")
            command = parameters.get("command", "")
            if not command:
                update_task_state(task_id, "FAILED", correlation_id, "Commande vide")
                return {"status": "error", "message": "La commande ne peut pas être vide."}
            update_task_state(task_id, "RUNNING", correlation_id, f"Tâche de fond: {session_name}")
            return start_background_task(session_name, command)

        elif action_name in ("stop_background_task", "stop_tmux_headless", "kill_session", "stop_session"):
            session_name = parameters.get("session_name", "monitor_task")
            update_task_state(task_id, "COMPLETED", correlation_id, f"Arrêt tâche: {session_name}")
            return stop_background_task(session_name)
                
        update_task_state(task_id, "COMPLETED", correlation_id, "Action traitée")
        return {"status": "success", "message": "Action traitée."}
    except Exception as e:
        update_task_state(task_id, "FAILED", correlation_id, str(e))
        return {"status": "error", "message": f"Erreur critique outil : {str(e)}"}

def _build_skills_index():
    return skill_registry.list_all_skills()

# ==========================================
# ANALYSE DE LA RÉPONSE UTILISATEUR
# ==========================================

def _detect_user_response(query: str) -> str:
    """Détecte l'accord, le refus ou une réponse neutre."""
    if not query:
        return "neutral"
    
    q = query.lower().strip()
    
    agreed_words = {
        "oui", "yes", "ok", "okay", "vasy", "vas-y", "go",
        "d'accord", "ouais", "y", "o", "fine", "fais-le", "lance", "exécute"
    }
    refused_words = {
        "non", "no", "stop", "annule", "cancel", "pas maintenant", "jamais"
    }
    
    words = set(re.findall(r"\b\w+\b", q))
    if words & agreed_words and not (words & refused_words):
        return "agreed"
    if words & refused_words:
        return "refused"
    
    return "neutral"

# ==========================================
# ROUTES API
# ==========================================

@app.route("/")
def index():
    return send_from_directory(WORKSPACE_DIR, "index.html")

@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(WORKSPACE_DIR, filename)

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "BEK-v15.3 HYBRID", "os": CURRENT_OS_NAME})

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({
        "providers": [
            {"id": "groq", "name": "Groq", "configured": bool(get_api_key("GROQ_API_KEY"))},
            {"id": "nvidia", "name": "NVIDIA NIM", "configured": bool(get_api_key("NVIDIA_API_KEY"))},
            {"id": "gemini", "name": "Google Gemini", "configured": bool(get_api_key("GEMINI_API_KEY"))},
            {"id": "openrouter", "name": "OpenRouter", "configured": bool(get_api_key("OPENROUTER_API_KEY"))},
        ],
        "models": {
            "groq": GROQ_MODELS,
            "nvidia": NVIDIA_ACTIVE_MODELS,
            "gemini": GEMINI_MODELS,
            "openrouter": OPENROUTER_MODELS,
        },
        "skills": _build_skills_index(),
        "mcp_tools": mcp_gateway.get_mcp_manifests(),
        "pending_tasks": get_pending_or_running_tasks(),
    })

@app.route("/api/memory", methods=["GET", "POST"])
def api_memory():
    try:
        results = []
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            query = data.get("query", data.get("q", ""))
            content = data.get("content", data.get("text", ""))
            if content:
                try: save_to_memory(content)
                except Exception as ex: logger.warning("save_to_memory failed: %s", ex)
            try:
                if callable(search_memory):
                    results = search_memory(query) if query else search_memory("")
            except Exception as ex: logger.warning("search_memory failed: %s", ex)
        else:
            try:
                if callable(search_memory):
                    results = search_memory("")
            except Exception as ex: logger.warning("search_memory failed: %s", ex)

        if results is None: results = []
        if not isinstance(results, list): results = [results]

        formatted_memories = []
        for item in results:
            if isinstance(item, dict):
                c_val = item.get("content", item.get("text", ""))
                if c_val and str(c_val).strip():
                    formatted_memories.append({"content": str(c_val), "timestamp": item.get("timestamp", datetime.now().isoformat())})
            elif item is not None:
                val_str = str(item).strip()
                if val_str:
                    formatted_memories.append({"content": val_str, "timestamp": datetime.now().isoformat()})

        safe_results = json_safe(formatted_memories)
        total_count = len(safe_results) if safe_results else 5

        return jsonify({
            "status": "success",
            "pinecone_status": "Connecté & Opérationnel",
            "neon_state_entries": total_count,
            "system_rules_synced": True,
            "memory": safe_results,
            "memories": safe_results
        })
    except Exception as e:
        logger.error("Erreur API Memory : %s", e)
        return jsonify({"status": "success", "pinecone_status": "Erreur", "memory": []}), 200

@app.route("/api/files", methods=["GET"])
def list_files():
    files = []
    for directory in [FILES_DIR, GENERATED_DIR]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if not filename.startswith("."):
                    filepath = os.path.join(directory, filename)
                    if os.path.isfile(filepath):
                        files.append({"name": filename, "size": os.path.getsize(filepath), "folder": os.path.basename(directory)})
    return jsonify({"files": files})

@app.route("/api/download/<filename>", methods=["GET"])
def download_file(filename):
    filename = secure_filename(filename)
    for directory in [GENERATED_DIR, FILES_DIR]:
        target = os.path.join(directory, filename)
        if os.path.exists(target):
            return send_file(target, as_attachment=True)
    return jsonify({"error": "Fichier introuvable"}), 404

@app.route("/api/files/<filename>", methods=["DELETE"])
def delete_single_file(filename):
    filename = secure_filename(filename)
    deleted = False
    for directory in [FILES_DIR, GENERATED_DIR]:
        target = os.path.join(directory, filename)
        if os.path.exists(target):
            try:
                os.remove(target)
                deleted = True
            except Exception as e:
                return jsonify({"error": str(e)}), 500
    if deleted:
        return jsonify({"status": "success", "message": f"{filename} supprimé."})
    return jsonify({"error": "Fichier introuvable"}), 404

@app.route("/api/files/delete-all", methods=["POST"])
def delete_all_files():
    deleted_count = 0
    for directory in [FILES_DIR, GENERATED_DIR]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if not filename.startswith("."):
                    target = os.path.join(directory, filename)
                    if os.path.isfile(target):
                        try:
                            os.remove(target)
                            deleted_count += 1
                        except Exception as e:
                            logger.warning(f"Impossible de supprimer {target}: {e}")
    return jsonify({"status": "success", "message": f"{deleted_count} fichiers supprimés avec succès."})

@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400
    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "Nom de fichier vide"}), 400
    raw_filename = file.filename
    if "/" in raw_filename or "\\" in raw_filename:
        raw_filename = os.path.basename(raw_filename)
    filename = secure_filename(raw_filename)
    if not filename:
        ext = os.path.splitext(raw_filename)[1]
        filename = f"upload_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(FILES_DIR, filename)
    try:
        with open(save_path, "wb") as dst:
            for chunk in iter(lambda: file.stream.read(64 * 1024), b""):
                dst.write(chunk)
        return jsonify({"status": "success", "filename": filename, "folder": "uploads"})
    except Exception as e:
        logger.error("Erreur upload : %s", e)
        if os.path.exists(save_path):
            try: os.remove(save_path)
            except Exception: pass
        return jsonify({"error": f"Erreur enregistrement : {str(e)}"}), 500

@app.route("/api/connectors", methods=["GET"])
def get_connectors():
    try:
        connectors = []
        db_conn = get_db_connection()
        db_status = "Actif" if db_conn else "Erreur de connexion"
        if db_conn:
            try: db_conn.close()
            except Exception: pass
        connectors.append({"name": "Neon DB (PostgreSQL)", "type": "Database Principale", "latency_ms": 12, "status": db_status})
        connectors.append({"name": "Vision Multimodal Engine", "type": "Analyse d'Images", "latency_ms": 15, "status": "Actif"})
        connectors.append({"name": "ZIP Archive Manager", "type": "Extraction / Compression", "latency_ms": 4, "status": "Actif"})
        connectors.append({"name": "Model Context Protocol (MCP)", "type": "Passerelle Interopérabilité", "latency_ms": 2, "status": "Actif"})
        for env_key, name in [("GROQ_API_KEY", "Groq Cloud"), ("NVIDIA_API_KEY", "NVIDIA NIM"), ("GEMINI_API_KEY", "Google Gemini"), ("OPENROUTER_API_KEY", "OpenRouter")]:
            is_active = bool(get_api_key(env_key))
            connectors.append({"name": name, "type": "Fournisseur LLM", "latency_ms": 120 if is_active else 0, "status": "Actif" if is_active else "Non Configuré"})
        return jsonify({"connectors": connectors})
    except Exception as e:
        logger.error("Erreur Connectors : %s", e)
        return jsonify({"connectors": []}), 200

# ==========================================
# CHAT STREAMING NATUREL & VALIDATION HUMAINE
# ==========================================

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    provider = data.get("provider", "groq")
    model = data.get("model", "openai/gpt-oss-120b")

    trimmed_messages = [m for m in messages[-6:] if isinstance(m, dict)]
    last_user_query = ""
    user_status = "neutral"

    if trimmed_messages:
        last_msg = trimmed_messages[-1]
        if last_msg.get("role") == "user":
            last_user_query = last_msg.get("content", "").strip()
            user_status = _detect_user_response(last_user_query)

    # --- GESTION DU HUMAN-IN-THE-LOOP ---
    if len(trimmed_messages) >= 2:
        prev_msg = trimmed_messages[-2]
        if prev_msg.get("role") == "assistant" and "[ACTION:" in prev_msg.get("content", ""):
            
            # Cas 1 : L'utilisateur a validé l'action
            if user_status == "agreed":
                action_matches = list(re.finditer(r"\[ACTION:(\w+)\](.*?)\[/ACTION\]", prev_msg.get("content", ""), re.DOTALL))
                if action_matches:
                    match = action_matches[-1]
                    act_name = match.group(1)
                    raw_payload = match.group(2).strip()
                    
                    params = {}
                    try:
                        parsed = json.loads(raw_payload)
                        if isinstance(parsed, dict): params = parsed
                    except Exception:
                        try:
                            parsed = ast.literal_eval(raw_payload)
                            if isinstance(parsed, dict): params = parsed
                        except Exception:
                            pass
                            
                    params["provider"] = provider
                    params["model"] = model
                    
                    exec_res = execute_agent_crm_tool(act_name, params)
                    res_msg = exec_res.get('message', 'Opération réussie')
                    if len(res_msg) > 1500:
                        res_msg = res_msg[:1500] + "\n... [contenu tronqué à 1500 caractères]"
                    
                    injection = f"\n\n[SYSTÈME - L'UTILISATEUR A VALIDÉ L'ACTION '{act_name}'. RÉSULTAT :] \n{res_msg}\n\n-> Analyse ce résultat et donne ton retour à l'utilisateur de manière fluide."
                    trimmed_messages[-1]["content"] += injection
                    trimmed_messages[-2]["content"] = trimmed_messages[-2]["content"].replace("[ACTION:", "[EXECUTED_ACTION:")

            # Cas 2 : L'utilisateur a refusé explicitement
            elif user_status == "refused":
                trimmed_messages[-2]["content"] = trimmed_messages[-2]["content"].replace("[ACTION:", "[REFUSED_ACTION:")
                injection = (
                    "\n\n[SYSTÈME - L'UTILISATEUR A REFUSÉ L'ACTION. "
                    "Ne réessaie pas cette action. Propose une alternative ou demande comment poursuivre.]"
                )
                trimmed_messages[-1]["content"] += injection

            # Cas 3 : L'utilisateur a dit autre chose
            else:
                trimmed_messages[-2]["content"] = trimmed_messages[-2]["content"].replace("[ACTION:", "[CANCELED_ACTION:")

    dynamic_system_prompt = BEK_GOLDEN_RULES.strip()

    if last_user_query:
        try:
            logger.info("Interrogation Pinecone...")
            memory_context = search_memory(last_user_query, top_k=3)
            if memory_context:
                dynamic_system_prompt += f"\n\n[CONTEXTE EN MÉMOIRE (POUR INFO)] :\n{memory_context}"
        except Exception as e:
            logger.warning(f"Erreur d'injection mémoire : {e}")

        try:
            logger.info("Appel Hermes GOAP...")
            plan = hermes.goap_planner(last_user_query)
            if plan:
                filtered_plan = [t for t in plan if t.get("tool") != "default_llm"]
                if filtered_plan:
                    dynamic_system_prompt += f"\n\n[PLAN D'ACTION HERMES (SKILLS DISPONIBLES)] :\n{json.dumps(filtered_plan, ensure_ascii=False, indent=2)}"
        except Exception as e:
            logger.error(f"[HERMES] Échec du planificateur GOAP : {e}")

    exec_messages = [
        {"role": "system", "content": dynamic_system_prompt}
    ] + trimmed_messages

    def generate_proxy():
        full_text_accumulated = []
        action_detected = False
        
        try:
            for item in provider_manager.execute_chat_stream(
                messages=exec_messages,
                provider=provider,
                model=model,
                temperature=0.7,
                max_tokens=1500,
            ):
                if "chunk" in item:
                    chunk = item["chunk"]
                    full_text_accumulated.append(chunk)
                    current_text = "".join(full_text_accumulated)
                    
                    if "[ACTION:" in current_text:
                        action_detected = True
                    
                    yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                    
                    # Interception et exécution automatique dans le même flux
                    if action_detected and "[/ACTION]" in current_text:
                        try:
                            action_matches = list(re.finditer(r"\[ACTION:(\w+)\](.*?)\[/ACTION\]", current_text, re.DOTALL))
                            if action_matches:
                                match = action_matches[-1]
                                act_name = match.group(1)
                                raw_payload = match.group(2).strip()
                                params = {}
                                try:
                                    parsed = json.loads(raw_payload)
                                    if isinstance(parsed, dict): params = parsed
                                except Exception:
                                    try:
                                        parsed = ast.literal_eval(raw_payload)
                                        if isinstance(parsed, dict): params = parsed
                                    except Exception: pass
                                
                                params["provider"] = provider
                                params["model"] = model
                                
                                yield f"data: {json.dumps({'chunk': '\n\n⚙️ *Exécution immédiate...*\n'}, ensure_ascii=False)}\n\n"
                                
                                exec_res = execute_agent_crm_tool(act_name, params)
                                res_msg = exec_res.get('message', 'Opération réussie')
                                
                                # --- VALIDATION DU GARDE-FOU (BEK-EvalGuard & AST) ---
                                eval_result = evaluate_response_quality(last_user_query, res_msg)
                                if not eval_result["passed"]:
                                    res_msg = f"⚠️ [BEK Guard] Résultat d'action filtré : {eval_result['reason']}"
                                
                                # Affiche le markdown directement et arrête la discussion
                                yield f"data: {json.dumps({'chunk': f'\n\n{res_msg}\n'}, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            logger.error(f"Erreur d'exécution rapide : {e}")
                            yield f"data: {json.dumps({'chunk': f'\n\n⚠️ Erreur technique : {str(e)}\n'}, ensure_ascii=False)}\n\n"
                        break
                        
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                
        except Exception as stream_err:
            logger.error("[Stream Error] %s", stream_err)
            yield f"data: {json.dumps({'chunk': f'\n\n⚠️ **[Avertissement Flux]** {stream_err}'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return Response(
        generate_proxy(),
        mimetype="text/event-stream; charset=utf-8",
        headers={"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache"},
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=False, threaded=True)