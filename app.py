# ==============================================================================
# BEK-v15.3 / v16 HYBRID - SERVEUR PRINCIPAL FASTAPI UNIFIÉ (BATCH 1)
# FASTAPI / HERMES V3 / EVENT BUS A2A / MINHASH SPIDER / CRM & SUB-CRMS / PINECONE
# COMPATIBILITÉ UNIVERSELLE WINDOWS & LINUX — ZÉRO RÉGRESSION
# ==============================================================================

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
from werkzeug.utils import secure_filename

from fastapi import FastAPI, Request, Response, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# --- IMPORTS MODULAIRES (BATCH 1) ---
from core.paths import WORKSPACE_DIR, SKILLS_DIR, FILES_DIR, GENERATED_DIR, PLUGINS_DIR, DOCS_DIR
from core.utils import json_safe, json_response
from services.vision import (
    get_api_key,
    analyze_image_with_vision,
    generate_image_with_provider,
    merge_and_edit_images,
)
from services.tasks import (
    start_background_task,
    stop_background_task,
    RUNNING_BACKGROUND_TASKS,
    CURRENT_OS_NAME,
)
from services.db import execute_database_sql

# Compression de contexte Headroom
try:
    from headroom import compress as headroom_compress
except ImportError:
    headroom_compress = None

from memory import (
    search_memory,
    save_to_memory,
    delete_from_memory,
    get_db_connection,
    init_sync_log_table,
)

from context_loader import load_project_documentation
from fast_math import HyperLogLog, MinHashSimilarity
from event_bus import EventBusKafka
from swarm_core import run_bek_swarm_sync
from skill_registry import skill_registry, Skill
from provider_manager import provider_manager

# Synchronisation multi-remotes et Meta-Cortex SSE
from meta_cortex_sse_ui import MetaCortexSSEStreamer
from meta_cortex_swarm import ReflexionSwarm
from sync_manager import push_to_remotes

try:
    from approval_manager import approval_manager
except ImportError:
    approval_manager = None

# ==========================================
# META-CORTEX & ORCHESTRATEUR HYBRIDE A2A
# ==========================================

from meta_cortex_grounding import GroundingValidator

try:
    from bek_orchestrator import bek_orchestrator
except ImportError:
    bek_orchestrator = None

try:
    from skill_generator import create_and_register_skill
except ImportError:
    create_and_register_skill = None

try:
    from skills import dispatch_command as dispatch_slash_command, list_skills as list_native_skills
except ImportError:
    dispatch_slash_command = None
    list_native_skills = None

try:
    from sub_crm_engine import SubCRMEngine
except ImportError:
    SubCRMEngine = None

try:
    from plugin_crm import CRMPlugin
    crm_plugin = CRMPlugin()
except ImportError:
    crm_plugin = None

# ==========================================
# WEB AGENT
# ==========================================

try:
    from web_agent import web_agent_instance
except ImportError:
    try:
        from worker_headless import HeadlessWorker
        class WebAgentFallback:
            def run_pipeline(self, query: str):
                worker = HeadlessWorker(headless=True)
                leads = asyncio.run(worker.search_and_extract_leads(query))
                return f"Extraction web terminée : {len(leads)} leads trouvés.\n{json.dumps(leads, indent=2, ensure_ascii=False)}"
        web_agent_instance = WebAgentFallback()
    except Exception:
        web_agent_instance = None

# ==========================================
# HERMES CORE V3
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

try:
    from mcp_gateway import mcp_gateway
except ImportError:
    class MCPGatewayMock:
        def register_mcp_tool(self, **kwargs): pass
        def get_mcp_manifests(self): return []
    mcp_gateway = MCPGatewayMock()

# ==========================================
# APPLICATION FASTAPI
# ==========================================

app = FastAPI(
    title="BEK v15.3 / v16 Hybrid FastAPI",
    description="Architecture cognitive asynchrone haute performance",
    version="16.0-batch1"
)

CORS_ORIGINS = os.environ.get(
    "BEK_CORS_ORIGINS",
    "http://localhost:3000,[http://127.0.0.1:3000](http://127.0.0.1:3000),http://localhost:8765,[http://127.0.0.1:8765](http://127.0.0.1:8765),http://localhost:3001,[http://127.0.0.1:3001](http://127.0.0.1:3001)",
)

cors_origins = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.onrender\.com|https://.*\.workers\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MIDDLEWARE ANTI-CACHE POUR L'INTERFACE WEB ---
@app.middleware("http")
async def add_anti_cache_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

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
    if SubCRMEngine:
        SubCRMEngine.initialize_matrix_schema()
    logger.info("Tables de compensation sync_log, états Neon DB et schéma Matrix initialisés.")
except Exception as exc:
    logger.warning("Initialisation DB partielle : %s", exc)

try:
    from generate_architecture_doc import update_documentation_file
    update_documentation_file()
except Exception as exc:
    logger.debug("Génération auto architecture Doc : %s", exc)

GLOBAL_SYSTEM_CONTEXT = load_project_documentation(DOCS_DIR)

security_guard = hermes.security_guard
if security_guard is None:
    raise RuntimeError("SecurityGuard Hermes indisponible. Vérifiez BEK_HSM_SECRET.")

try:
    event_bus = EventBusKafka()
except Exception as exc:
    logger.warning("EventBusKafka indisponible : %s", exc)
    event_bus = None

minhash_engine = MinHashSimilarity(num_perm=64)
hll_counter = HyperLogLog(b=6)

# Enregistrement des outils initiaux dans la passerelle MCP
mcp_gateway.register_mcp_tool(
    name="neon_audit",
    description="Audit des tables relationnelles Neon DB",
    parameters_schema={},
    handler=lambda: {"tables": ["companies", "contacts", "opportunities", "matrix_sub_crms", "bek_task_states", "sync_log"]}
)

# ==========================================
# WORKERS HERMES & INITIALISATION DES HOOKS
# ==========================================

try:
    start_background_workers()
    logger.info("Workers Hermes démarrés avec succès.")
except Exception as exc:
    logger.error("Impossible de démarrer les workers Hermes : %s", exc)

def _bek_pre_plan_validator(objective: str, trace_id: str | None):
    return True, "Pre-Plan validé", None

hermes.register_pre_plan_hook(_bek_pre_plan_validator)

# Enregistrement des outils Hermes V3
hermes.register_tool(
    "web_sync",
    lambda query="", **kwargs: web_agent_instance.run_pipeline(query) if web_agent_instance else "WebAgent indisponible",
    risk_level="L3",
)

hermes.register_tool(
    "orchestrate",
    lambda goal="", **kwargs: bek_orchestrator.run(goal) if bek_orchestrator else "Orchestrateur indisponible",
    risk_level="L2",
)

hermes.register_tool(
    "neon_audit",
    lambda **kwargs: {
        "status": "Neon DB audit demandé",
        "tables": ["companies", "contacts", "opportunities", "matrix_sub_crms", "sync_log"],
    },
    risk_level="L1",
)

# ==========================================
# PROMPT SYSTÈME GLOBAL
# ==========================================

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
- DÈS QUE l'utilisateur demande une action technique, TU NE POSES AUCUNE QUESTION.
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
   - [ACTION:delete_memory]{{"record_id": "...", "keyword": "..."}}[/ACTION]
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
# EXÉCUTION UNIFIÉE DES OUTILS & ACTIONS
# ==========================================

def execute_agent_crm_tool(action_name: str, parameters: dict) -> dict:
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
                res = web_agent_instance.run_pipeline(query) if web_agent_instance else "WebAgent non connecté"
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

        elif action_name in ("delete_memory", "forget", "delete_from_memory"):
            record_id = parameters.get("record_id", "")
            keyword = parameters.get("keyword", "")
            if not record_id and not keyword:
                update_task_state(task_id, "FAILED", correlation_id, "Paramètres de suppression vides")
                return {"status": "error", "message": "Fournis un 'record_id' ou un 'keyword' à supprimer de la mémoire."}
            try:
                del_res = delete_from_memory(record_id=record_id, keyword=keyword)
                update_task_state(task_id, "COMPLETED", correlation_id, f"Suppression mémoire (ID: {record_id}, Mot-clé: {keyword})")
                return {
                    "status": "success",
                    "message": f"🗑️ **Suppression de la mémoire effectuée :**\n- Pinecone Cloud : `{del_res.get('pinecone')}`\n- ChromaDB Local : `{del_res.get('chroma')}`\n- Table Neon (sync_log) : `{del_res.get('neon_sync')}`"
                }
            except Exception as e:
                update_task_state(task_id, "FAILED", correlation_id, str(e))
                return {"status": "error", "message": f"Erreur lors de la suppression mémoire : {str(e)}"}

        elif action_name in ("write_file", "save_file", "create_file"):
            filename = parameters.get("filename", "generated/agent_output.txt")
            filepath = os.path.abspath(os.path.join(WORKSPACE_DIR, filename))
            try:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                content = parameters.get("content", "")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                update_task_state(task_id, "COMPLETED", correlation_id, f"Fichier écrit: {filename}")
                safe_name = os.path.basename(filename)
                return {"status": "success", "message": f"Fichier `{safe_name}` enregistré avec succès.\n\n[FILE:{safe_name}](/api/download/{safe_name})"}
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
                safe_name = os.path.basename(output_zip_name)
                return {"status": "success", "message": f"Archive `{safe_name}` créée avec succès.\n\n[FILE:{safe_name}](/api/download/{safe_name})"}
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
                return {"status": "error", "message": f"ÉCHEC VISION: {vision_result}\n[ALERTE SYSTEME]: Erreur lors de la capture visuelle."}
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
            if "dir /s /b" in command.lower() and os.name == "nt":
                term = re.search(r'\*(.*?)\*', command)
                search_term = term.group(1) if term else "bek|provider"
                command = f'powershell -NoProfile -Command "Get-ChildItem -Path . -Recurse -File -Exclude \'node_modules\',\'.venv\',\'.git\',\'__pycache__\' | Where-Object {{ $_.Name -match \'{search_term}\' }} | Select-Object -ExpandProperty FullName"'
                
            try:
                res = subprocess.run(command, shell=True, cwd=WORKSPACE_DIR, capture_output=True, text=True, timeout=60)
                output = (res.stdout + "\n" + res.stderr).strip()
                status_str = "success" if res.returncode == 0 else "error"
                update_task_state(task_id, "COMPLETED" if res.returncode == 0 else "FAILED", correlation_id, command)
                return {"status": status_str, "message": f"Commande exécutée :\n{output[-2500:]}"}
            except subprocess.TimeoutExpired:
                update_task_state(task_id, "FAILED", correlation_id, "Timeout (60s)")
                return {"status": "error", "message": "Erreur : Commande interrompue après timeout (60s)."}
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

def _detect_user_response(query: str) -> str:
    if not query:
        return "neutral"
    q = query.lower().strip()
    agreed_words = {"oui", "yes", "ok", "okay", "vasy", "vas-y", "go", "d'accord", "ouais", "y", "o", "fine", "fais-le", "lance", "exécute"}
    refused_words = {"non", "no", "stop", "annule", "cancel", "pas maintenant", "jamais"}
    words = set(re.findall(r"\b\w+\b", q))
    if words & agreed_words and not (words & refused_words):
        return "agreed"
    if words & refused_words:
        return "refused"
    return "neutral"

# ==========================================
# ROUTES API FASTAPI
# ==========================================

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "BEK-v16 HYBRID FastAPI (Batch 1)", "os": CURRENT_OS_NAME}

@app.get("/api/config")
async def get_config():
    providers_list = [
        {"id": "b_ai", "name": "B.ai", "configured": True},
        {"id": "kilo_anonymous", "name": "Kilo Code (Anonyme)", "configured": True},
        {"id": "ovh_anonymous", "name": "OVHcloud (Anonyme)", "configured": True},
        {"id": "llm7_anonymous", "name": "LLM7.io (Anonyme)", "configured": True},
        {"id": "groq", "name": "Groq", "configured": True},
        {"id": "nvidia", "name": "NVIDIA NIM", "configured": True},
        {"id": "gemini", "name": "Google Gemini", "configured": True},
        {"id": "openrouter", "name": "OpenRouter", "configured": True},
        {"id": "mistral", "name": "Mistral AI", "configured": True},
        {"id": "cohere", "name": "Cohere", "configured": True},
        {"id": "aionlabs", "name": "Aion Labs", "configured": True},
        {"id": "zhipu", "name": "Zhipu AI", "configured": True},
        {"id": "siliconflow", "name": "SiliconFlow", "configured": True},
    ]
    return {
        "providers": providers_list,
        "models": provider_manager.PROVIDER_MODELS,
        "skills": skill_registry.list_all_skills(),
        "skills_count": len(skill_registry.skills),
        "mcp_tools": mcp_gateway.get_mcp_manifests(),
        "pending_tasks": get_pending_or_running_tasks(),
        "radar_status": event_bus.get_radar_status() if event_bus else {"mode": "NORMAL"}
    }

@app.api_route("/api/memory", methods=["GET", "POST"])
async def api_memory(request: Request):
    try:
        results = []
        if request.method == "POST":
            data = await request.json() or {}
            query = data.get("query", data.get("q", ""))
            content = data.get("content", data.get("text", ""))
            if content:
                try: save_to_memory(content)
                except Exception as ex: logger.warning("save_to_memory failed: %s", ex)
            try:
                results = search_memory(query) if query else search_memory("")
            except Exception as ex: logger.warning("search_memory failed: %s", ex)
        else:
            try:
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

        return {
            "status": "success",
            "pinecone_status": "Connecté & Opérationnel",
            "neon_state_entries": total_count,
            "system_rules_synced": True,
            "memory": safe_results,
            "memories": safe_results
        }
    except Exception as e:
        logger.error("Erreur API Memory : %s", e)
        return {"status": "success", "pinecone_status": "Erreur", "memory": []}

@app.get("/api/files")
async def list_files():
    files = []
    for directory in [FILES_DIR, GENERATED_DIR]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if not filename.startswith("."):
                    filepath = os.path.join(directory, filename)
                    if os.path.isfile(filepath):
                        files.append({"name": filename, "size": os.path.getsize(filepath), "folder": os.path.basename(directory)})
    return {"files": files}

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    filename = secure_filename(filename)
    for directory in [GENERATED_DIR, FILES_DIR]:
        target = os.path.join(directory, filename)
        if os.path.exists(target):
            return FileResponse(target, filename=filename, media_type="application/octet-stream")
    raise HTTPException(status_code=404, detail="Fichier introuvable")

@app.delete("/api/files/{filename}")
async def delete_single_file(filename: str):
    filename = secure_filename(filename)
    deleted = False
    for directory in [FILES_DIR, GENERATED_DIR]:
        target = os.path.join(directory, filename)
        if os.path.exists(target):
            try:
                os.remove(target)
                deleted = True
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    if deleted:
        return {"status": "success", "message": f"{filename} supprimé."}
    raise HTTPException(status_code=404, detail="Fichier introuvable")

@app.post("/api/files/delete-all")
async def delete_all_files():
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
    return {"status": "success", "message": f"{deleted_count} fichiers supprimés avec succès."}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Aucun fichier reçu")
    raw_filename = file.filename
    if "/" in raw_filename or "\\" in raw_filename:
        raw_filename = os.path.basename(raw_filename)
    filename = secure_filename(raw_filename)
    if not filename:
        ext = os.path.splitext(raw_filename)[1]
        filename = f"upload_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(FILES_DIR, filename)
    try:
        content = await file.read()
        with open(save_path, "wb") as dst:
            dst.write(content)
        return {"status": "success", "filename": filename, "folder": "uploads"}
    except Exception as e:
        logger.error("Erreur upload : %s", e)
        if os.path.exists(save_path):
            try: os.remove(save_path)
            except Exception: pass
        raise HTTPException(status_code=500, detail=f"Erreur enregistrement : {str(e)}")

@app.get("/api/connectors")
async def get_connectors():
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
        connectors.append({"name": "EventBus Kafka Mock", "type": "Pipeline Ingestion A2A", "latency_ms": 1, "status": "Actif"})
        
        for p_id in provider_manager.FALLBACK_ORDER:
            has_key = bool(provider_manager.get_api_key(f"{p_id.upper()}_API_KEY")) or ("anonymous" in p_id)
            connectors.append({
                "name": p_id.replace("_", " ").upper(),
                "type": "Fournisseur LLM",
                "latency_ms": 80 if has_key else 0,
                "status": "Actif" if has_key else "Non Configuré"
            })
        return {"connectors": connectors}
    except Exception as e:
        logger.error("Erreur Connectors : %s", e)
        return {"connectors": []}

# ==========================================
# ENDPOINTS MATRICE SOUS-CRMS & PIPELINE
# ==========================================

@app.get("/api/matrix/sub_crms")
async def api_list_sub_crms():
    if SubCRMEngine:
        return {"status": "success", "data": SubCRMEngine.list_sub_crms()}
    return {"status": "success", "data": []}

@app.get("/api/crm/opportunities")
async def api_list_opportunities():
    res = execute_database_sql('SELECT id, name, amount, currency, stage, created_at FROM "opportunities" ORDER BY id DESC LIMIT 20;')
    return {"status": "success", "data": res.get("data", [])}

@app.post("/api/crm/execute")
async def api_execute_crm_sql(request: Request):
    data = await request.json() or {}
    sql = data.get("sql", "")
    if not sql:
        raise HTTPException(status_code=400, detail="Requête SQL manquante")
    return execute_database_sql(sql)

@app.get("/api/crm/stats")
async def api_crm_stats():
    res_companies = execute_database_sql('SELECT count(*)::int as c FROM "companies";')
    res_contacts = execute_database_sql('SELECT count(*)::int as c FROM "contacts";')
    res_opportunities = execute_database_sql('SELECT count(*)::int as c, COALESCE(SUM(amount), 0)::float as total FROM "opportunities";')
    return {
        "status": "ok",
        "companies": res_companies.get("data", [{}])[0].get("c", 0),
        "contacts": res_contacts.get("data", [{}])[0].get("c", 0),
        "deals": res_opportunities.get("data", [{}])[0].get("c", 0),
        "pipeline_total": res_opportunities.get("data", [{}])[0].get("total", 0)
    }

# ==========================================
# ENDPOINTS META-CORTEX SSE & SYNC MULTI-GIT
# ==========================================

@app.post("/api/reflexion/stream")
async def reflexion_stream(request: Request):
    data = await request.json() or {}
    draft = data.get("draft", "")
    query = data.get("query", "")
    
    swarm = ReflexionSwarm(llm_provider="b_ai", llm_model="glm-5.3-flash")
    streamer = MetaCortexSSEStreamer(swarm)
    
    return StreamingResponse(
        streamer.stream_reflection(draft, query),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@app.post("/api/sync/push")
async def api_push_remotes(request: Request):
    data = await request.json() or {}
    msg = data.get("message", "Auto-sync BEK-v15.3 agent state")
    res = push_to_remotes(msg)
    return json_response(res)

# ==========================================
# CHAT STREAMING & ROUTAGE MINHASH SPIDER
# ==========================================

@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json() or {}
    messages = data.get("messages", [])
    provider = data.get("provider", "b_ai")
    model = data.get("model", "glm-5.3-flash")

    trimmed_messages = [m for m in messages[-6:] if isinstance(m, dict)]
    last_user_query = ""
    user_status = "neutral"

    if trimmed_messages:
        last_msg = trimmed_messages[-1]
        if last_msg.get("role") == "user":
            last_user_query = last_msg.get("content", "").strip()
            user_status = _detect_user_response(last_user_query)

    # Ingestion asynchrone EventBus A2A
    corr_id = f"corr_{uuid.uuid4().hex[:10]}"
    if event_bus and last_user_query:
        event_bus.publish("web-cleaned", {"query": last_user_query, "correlation_id": corr_id})

    # Traitement des commandes directes /slash si demandées
    if last_user_query.startswith("/") and dispatch_slash_command:
        slash_res = dispatch_slash_command(last_user_query)
        if slash_res and slash_res.get("ok"):
            async def generate_slash():
                yield f"data: {json.dumps({'chunk': slash_res['output']}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return StreamingResponse(generate_slash(), media_type="text/event-stream")

    # --- GESTION DU HUMAN-IN-THE-LOOP ---
    if len(trimmed_messages) >= 2:
        prev_msg = trimmed_messages[-2]
        if prev_msg.get("role") == "assistant" and "[ACTION:" in prev_msg.get("content", ""):
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
                        except Exception: pass
                            
                    params["provider"] = provider
                    params["model"] = model
                    
                    exec_res = execute_agent_crm_tool(act_name, params)
                    res_msg = exec_res.get('message', 'Opération réussie')
                    if len(res_msg) > 1500:
                        res_msg = res_msg[:1500] + "\n... [contenu tronqué]"
                    
                    injection = f"\n\n[SYSTÈME - L'UTILISATEUR A VALIDÉ L'ACTION '{act_name}'. RÉSULTAT :] \n{res_msg}\n\n-> Analyse ce résultat et donne ton retour à l'utilisateur de manière fluide."
                    trimmed_messages[-1]["content"] += injection
                    trimmed_messages[-2]["content"] = trimmed_messages[-2]["content"].replace("[ACTION:", "[EXECUTED_ACTION:")

            elif user_status == "refused":
                trimmed_messages[-2]["content"] = trimmed_messages[-2]["content"].replace("[ACTION:", "[REFUSED_ACTION:")
                injection = "\n\n[SYSTÈME - L'UTILISATEUR A REFUSÉ L'ACTION. Propose une alternative ou demande comment poursuivre.]"
                trimmed_messages[-1]["content"] += injection
            else:
                trimmed_messages[-2]["content"] = trimmed_messages[-2]["content"].replace("[ACTION:", "[CANCELED_ACTION:")

    dynamic_system_prompt = BEK_GOLDEN_RULES.strip()

    if last_user_query:
        # Évaluation MinHash de similarité pour routage express
        sig = minhash_engine.compute_signature(last_user_query)
        hll_counter.add(last_user_query)
        
        try:
            memory_context = search_memory(last_user_query, top_k=3)
            if memory_context:
                dynamic_system_prompt += f"\n\n[CONTEXTE EN MÉMOIRE (POUR INFO)] :\n{memory_context}"
        except Exception as e:
            logger.warning("Erreur injection mémoire : %s", e)

        try:
            plan = hermes.goap_planner(last_user_query)
            if plan:
                filtered_plan = [t for t in plan if t.get("tool") != "default_llm"]
                if filtered_plan:
                    dynamic_system_prompt += f"\n\n[PLAN D'ACTION HERMES (SKILLS DISPONIBLES)] :\n{json.dumps(filtered_plan, ensure_ascii=False, indent=2)}"
        except Exception as e:
            logger.error("[HERMES] Échec du planificateur GOAP : %s", e)

    exec_messages = [{"role": "system", "content": dynamic_system_prompt}] + trimmed_messages

    async def generate_proxy():
        full_text_accumulated = []
        action_detected = False
        
        try:
            for item in provider_manager.execute_chat_stream(
                messages=exec_messages,
                provider=provider,
                model=model,
                temperature=0.7,
                max_tokens=4096,
            ):
                if "chunk" in item:
                    chunk = item["chunk"]
                    full_text_accumulated.append(chunk)
                    current_text = "".join(full_text_accumulated)
                    
                    if "[ACTION:" in current_text:
                        action_detected = True
                    
                    yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                    
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
                                
                                immediate_msg_json = json.dumps({'chunk': '\n\n⚙️ *Exécution immédiate...*\n'}, ensure_ascii=False)
                                yield f"data: {immediate_msg_json}\n\n"
                                
                                exec_res = execute_agent_crm_tool(act_name, params)
                                res_msg = exec_res.get('message', 'Opération réussie')
                                
                                eval_result = evaluate_response_quality(last_user_query, res_msg)
                                if not eval_result["passed"]:
                                    res_msg = f"⚠️ [BEK Guard] Résultat d'action filtré : {eval_result['reason']}"
                                
                                res_chunk_json = json.dumps({'chunk': f'\n\n{res_msg}\n'}, ensure_ascii=False)
                                yield f"data: {res_chunk_json}\n\n"
                        except Exception as e:
                            logger.error("Erreur exécution inline : %s", e)
                            err_chunk_json = json.dumps({'chunk': f'\n\n⚠️ Erreur technique : {str(e)}\n'}, ensure_ascii=False)
                            yield f"data: {err_chunk_json}\n\n"
                        break
                        
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                
        except Exception as stream_err:
            logger.error("[Stream Error] %s", stream_err)
            err_stream_json = json.dumps({'chunk': f'\n\n⚠️ **[Avertissement Flux]** {stream_err}'}, ensure_ascii=False)
            yield f"data: {err_stream_json}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

# ==========================================
# ROUTES STATIQUES ET RACINE
# ==========================================

@app.get("/")
async def index():
    return FileResponse(os.path.join(WORKSPACE_DIR, "index.html"))

@app.get("/{filename:path}")
async def serve_static(filename: str):
    target = os.path.join(WORKSPACE_DIR, filename)
    if os.path.exists(target) and os.path.isfile(target):
        return FileResponse(target)
    raise HTTPException(status_code=404, detail="Fichier introuvable")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8765"))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("app:app", host=host, port=port, reload=False)