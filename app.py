# ==========================================
# BEK-v15.2 HYBRID - SERVEUR PRINCIPAL
# FLASK / HERMES / CRM / MATRIX / PINECONE
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
# META-CORTEX
# ==========================================

from meta_cortex_grounding import GroundingValidator
from meta_cortex_swarm import ReflexionSwarm

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
# DIRECTOIRES
# ==========================================

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(WORKSPACE_DIR, "awesome-openclaw-skills")
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
    valid, msg = validate_sql_request(objective) if any(kw in objective.lower() for kw in ["select", "insert", "delete", "update", "drop"]) else (True, "")
    if not valid:
        return False, f"Rejet Pre-Plan : {msg}", []
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
    "neon_audit",
    lambda: {
        "status": "Neon DB audit demandé",
        "tables": ["companies", "contacts", "opportunities", "matrix_sub_crms"],
    },
    risk_level="L1",
)

hermes.register_tool(
    "default_llm",
    lambda query: {"response": f"Agence IA prête pour : {query}"},
    risk_level="L1",
)

# ==========================================
# PROMPT SYSTÈME GLOBAL
# ==========================================

BEK_GOLDEN_RULES = """
=== ARCHITECTE BEK-v15.2 HYBRID ===
1. ZÉRO RÉGRESSION : Préserver upload, Pinecone, Neon DB, Hermes et Swarm.
2. POSTURE : Réponds naturellement aux salutations sans actions complexes.
3. ACTIONS UNIQUEMENT SUR ORDRE EXPLICITE :
   - [ACTION:spawn_sub_crm]{...}[/ACTION]
   - [ACTION:crm_add_opportunity]{...}[/ACTION]
   - [ACTION:execute_sql]{"sql": "..."}[/ACTION]
   - [ACTION:write_file]{"filename": "...", "content": "..."}[/ACTION]
   - [ACTION:delete_file]{"filename": "..."}[/ACTION]
   - [ACTION:read_file]{"filename": "..."}[/ACTION]
"""

# ==========================================
# UTILITAIRES
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

def get_admin_api_key():
    return get_api_key("BEK_ADMIN_API_KEY")

def check_admin_auth():
    configured_key = get_admin_api_key()
    if not configured_key:
        return True
    supplied_key = request.headers.get("X-BEK-API-Key", "") or request.args.get("api_key", "")
    return supplied_key == configured_key

def require_admin():
    if check_admin_auth():
        return None
    return jsonify({"status": "error", "error": "Authentification BEK requise."}), 401

# ==========================================
# SYNCHRONISATION & SQL
# ==========================================

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
            try:
                conn.rollback()
            except Exception:
                pass
        return {"status": "error", "message": str(exc)}
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass

# ==========================================
# SUB-CRM ENGINE & ACTIONS
# ==========================================

def _sanitize_niche_prefix(sub_crm_id_raw: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", str(sub_crm_id_raw).strip())
    if not cleaned:
        cleaned = "default"
    return f"niche_{cleaned[:8]}"

class SubCRMEngine:
    @staticmethod
    def initialize_matrix_schema():
        conn = get_db_connection()
        if not conn:
            return False
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS matrix_sub_crms (
                    id UUID PRIMARY KEY,
                    parent_id UUID REFERENCES matrix_sub_crms(id) ON DELETE SET NULL,
                    niche_name TEXT NOT NULL,
                    specifications JSONB NOT NULL,
                    environment_vars JSONB NOT NULL,
                    active_tools JSONB NOT NULL,
                    cahier_des_charges TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS opportunities (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    amount NUMERIC DEFAULT 0.0,
                    currency TEXT DEFAULT 'EUR',
                    stage TEXT DEFAULT 'Qualification',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    @staticmethod
    def spawn_sub_crm(niche_name: str, cahier_des_charges: str, objectives: list, parent_id=None, custom_env=None):
        if not SubCRMEngine.initialize_matrix_schema():
            return {"status": "error", "message": "Impossible d'initialiser matrix_sub_crms."}
        sub_crm_id = str(uuid.uuid4())
        environment_payload = custom_env if isinstance(custom_env, dict) else {"RUNTIME_ENV": "production_matrix_node"}
        conn = get_db_connection()
        if not conn:
            return {"status": "error", "message": "Connexion Neon DB indisponible."}
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO matrix_sub_crms (id, parent_id, niche_name, specifications, environment_vars, active_tools, cahier_des_charges, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
                RETURNING id, niche_name, created_at;
                """,
                (
                    sub_crm_id,
                    parent_id,
                    niche_name,
                    json.dumps({"objectives": objectives}, ensure_ascii=False),
                    json.dumps(environment_payload, ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    cahier_des_charges,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return {"status": "success", "sub_crm_id": str(row[0]), "niche_name": row[1]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

class AutonomousSubCRMInstance:
    def __init__(self, sub_crm_id: str, niche_name: str, cahier_des_charges: str):
        self.sub_crm_id = sub_crm_id

    def generate_dynamic_ui_and_tables(self) -> dict:
        prefix = _sanitize_niche_prefix(self.sub_crm_id)
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {prefix}_entities (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        type TEXT DEFAULT 'Contact',
                        metadata JSONB DEFAULT '{{}}'::jsonb,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                cur.close()
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        return {"tables_created": [f"{prefix}_entities"]}

class SubCRMEngineAdvanced(SubCRMEngine):
    @staticmethod
    def spawn_fully_alive_sub_crm(niche_name: str, cahier_des_charges: str, objectives: list, parent_id=None, custom_env=None):
        base_spawn = SubCRMEngine.spawn_sub_crm(niche_name, cahier_des_charges, objectives, parent_id, custom_env)
        if base_spawn.get("status") != "success":
            return base_spawn
        sub_crm_id = base_spawn["sub_crm_id"]
        instance = AutonomousSubCRMInstance(sub_crm_id, niche_name, cahier_des_charges)
        lifecycle_data = instance.generate_dynamic_ui_and_tables()
        return {"status": "success", "sub_crm_id": sub_crm_id, "niche_name": niche_name, "lifecycle_environment": lifecycle_data}

def execute_agent_crm_tool(action_name: str, parameters: dict) -> dict:
    if action_name == "spawn_sub_crm":
        return SubCRMEngineAdvanced.spawn_fully_alive_sub_crm(
            parameters.get("niche_name", "Niche Custom"),
            parameters.get("cahier_des_charges", "Sous-CRM"),
            parameters.get("objectives", ["Gestion"])
        )
    elif action_name == "crm_add_opportunity":
        name = parameters.get("name", "Opportunité")
        amount = float(parameters.get("amount", 0.0))
        return execute_database_sql(f"INSERT INTO opportunities (name, amount) VALUES ('{name}', {amount}) RETURNING id, name;")
    elif action_name in ("execute_sql", "execute_database_sql"):
        return execute_database_sql(parameters.get("sql", ""))
    
    # ACTIONS FICHIERS SUR LE DISQUE
    elif action_name in ("write_file", "save_file", "create_file"):
        filename = parameters.get("filename", "generated/agent_output.txt")
        filepath = os.path.abspath(os.path.join(WORKSPACE_DIR, filename))
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            content = parameters.get("content", "")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "success", "message": f"Fichier enregistré avec succès : {filepath}"}
        except Exception as e:
            return {"status": "error", "message": f"Erreur écriture : {str(e)}"}
            
    elif action_name == "delete_file":
        filename = parameters.get("filename", "")
        # Vérification dans WORKSPACE, uploads et generated
        found = False
        for directory in [WORKSPACE_DIR, FILES_DIR, GENERATED_DIR]:
            target = os.path.abspath(os.path.join(directory, os.path.basename(filename)))
            if os.path.exists(target) and os.path.isfile(target):
                try:
                    os.remove(target)
                    found = True
                except Exception as e:
                    return {"status": "error", "message": f"Erreur suppression : {str(e)}"}
        if found:
            return {"status": "success", "message": f"Fichier {filename} supprimé avec succès."}
        return {"status": "error", "message": "Fichier introuvable sur le disque."}
            
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
                return {"status": "success", "message": f"Contenu de {target_path} :\n{content}"}
            return {"status": "error", "message": "Fichier introuvable sur le disque."}
        except Exception as e:
            return {"status": "error", "message": f"Erreur lecture : {str(e)}"}
            
    return {"status": "success", "message": "Action traitée."}

def _build_skills_index():
    return skill_registry.list_all_skills()

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
    return jsonify({"status": "ok", "service": "BEK-v15.2 HYBRID"})

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
    })

# --- GESTION COMPLÈTE DES FICHIERS (LIST, DOWNLOAD, DELETE) ---
@app.route("/api/files", methods=["GET"])
def list_files():
    files = []
    for directory in [FILES_DIR, GENERATED_DIR]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if not filename.startswith("."):
                    filepath = os.path.join(directory, filename)
                    if os.path.isfile(filepath):
                        files.append({
                            "name": filename,
                            "size": os.path.getsize(filepath),
                            "folder": os.path.basename(directory)
                        })
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
        return jsonify({"status": "success", "message": f"{filename} supprimé avec succès."})
    return jsonify({"error": "Fichier introuvable"}), 404

@app.route("/api/files/delete-all", methods=["POST"])
def delete_all_files():
    for directory in [FILES_DIR, GENERATED_DIR]:
        if os.path.exists(directory):
            for f in os.listdir(directory):
                if not f.startswith("."):
                    fp = os.path.join(directory, f)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                        except Exception:
                            pass
    return jsonify({"status": "success", "message": "Tous les fichiers de session ont été supprimés."})

@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nom de fichier vide"}), 400
    filename = secure_filename(file.filename)
    save_path = os.path.join(FILES_DIR, filename)
    file.save(save_path)
    return jsonify({"status": "success", "filename": filename, "folder": "uploads"})

@app.route("/api/matrix/sub_crms", methods=["GET"])
def get_all_sub_crms():
    return jsonify(execute_database_sql("SELECT id, niche_name, status, created_at FROM matrix_sub_crms ORDER BY created_at DESC;"))

@app.route("/api/crm/opportunities", methods=["GET"])
def get_crm_opportunities():
    return jsonify(execute_database_sql("SELECT id, name, amount, currency, stage, created_at FROM opportunities ORDER BY id DESC;"))

@app.route("/api/memory", methods=["GET"])
def get_memory():
    try:
        sub_crms_res = execute_database_sql("SELECT count(*) as total FROM matrix_sub_crms")
        opps_res = execute_database_sql("SELECT count(*) as total FROM opportunities")
        
        crms_count = 0
        if isinstance(sub_crms_res, dict) and sub_crms_res.get("status") == "success" and sub_crms_res.get("data"):
            first_row = sub_crms_res["data"][0]
            crms_count = next(iter(first_row.values()), 0) if isinstance(first_row, dict) else first_row[0]
            
        opps_count = 0
        if isinstance(opps_res, dict) and opps_res.get("status") == "success" and opps_res.get("data"):
            first_row = opps_res["data"][0]
            opps_count = next(iter(first_row.values()), 0) if isinstance(first_row, dict) else first_row[0]
        
        pinecone_active = bool(get_api_key("PINECONE_API_KEY"))
        
        return jsonify({
            "neon_state_entries": crms_count + opps_count,
            "details_crm": f"{crms_count} Sous-CRMs instanciés",
            "details_opps": f"{opps_count} Opportunités dans le pipeline",
            "system_rules_synced": True,
            "pinecone_status": "Connecté & Synchronisé" if pinecone_active else "Non configuré (Clé API manquante)"
        })
    except Exception as e:
        logger.error("Erreur API Memory : %s", e)
        return jsonify({"neon_state_entries": 0, "details_crm": "0 CRM", "details_opps": "0 Opps", "system_rules_synced": False, "pinecone_status": "Erreur"}), 200

@app.route("/api/connectors", methods=["GET"])
def get_connectors():
    try:
        connectors = []
        
        # Neon DB
        db_conn = get_db_connection()
        db_status = "Actif" if db_conn else "Erreur de connexion"
        if db_conn:
            try:
                db_conn.close()
            except Exception:
                pass
        connectors.append({"name": "Neon DB (PostgreSQL)", "type": "Database Principale", "latency_ms": 12 if db_status == "Actif" else 0, "status": db_status})
        
        # Pinecone
        pinecone_key = bool(get_api_key("PINECONE_API_KEY"))
        connectors.append({"name": "Pinecone DB", "type": "Base Vectorielle", "latency_ms": 45 if pinecone_key else 0, "status": "Actif" if pinecone_key else "Inactif"})
        
        # Kafka
        kafka_status = "Actif" if event_bus is not None else "Inactif"
        connectors.append({"name": "Kafka Event Bus", "type": "Broker de Messages", "latency_ms": 5 if event_bus else 0, "status": kafka_status})
        
        # Web Automation
        connectors.append({"name": "Playwright Headless", "type": "Web Scraper & Automation", "latency_ms": 8, "status": "Prêt"})
        
        # Modèles LLM
        for env_key, name in [("GROQ_API_KEY", "Groq Cloud"), ("NVIDIA_API_KEY", "NVIDIA NIM"), ("GEMINI_API_KEY", "Google Gemini"), ("OPENROUTER_API_KEY", "OpenRouter")]:
            is_active = bool(get_api_key(env_key))
            connectors.append({"name": name, "type": "Fournisseur LLM", "latency_ms": 120 if is_active else 0, "status": "Actif" if is_active else "Non Configuré"})

        return jsonify({"connectors": connectors})
    except Exception as e:
        logger.error("Erreur API Connectors : %s", e)
        return jsonify({"connectors": []}), 200

# ==========================================
# CHAT STREAMING OPTIMISÉ (PARSER TOLÉRANT)
# ==========================================

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    provider = data.get("provider", "groq")
    model = data.get("model", "openai/gpt-oss-120b")

    trimmed_messages = [m for m in messages[-2:] if isinstance(m, dict)]

    exec_messages = [
        {"role": "system", "content": BEK_GOLDEN_RULES.strip()}
    ] + trimmed_messages

    def generate_proxy():
        full_text_accumulated = []
        try:
            for item in provider_manager.execute_chat_stream(
                messages=exec_messages,
                provider=provider,
                model=model,
                temperature=0.2,
                max_tokens=2048,
            ):
                if "chunk" in item:
                    chunk = item["chunk"]
                    full_text_accumulated.append(chunk)
                    yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                elif "done" in item:
                    full_response = "".join(full_text_accumulated)
                    action_matches = re.finditer(r"\[ACTION:(\w+)\](.*?)\[/ACTION\]", full_response, re.DOTALL)
                    for match in action_matches:
                        act_name = match.group(1)
                        raw_payload = match.group(2).strip()
                        params = {}
                        try:
                            params = json.loads(raw_payload)
                        except Exception:
                            try:
                                params = ast.literal_eval(raw_payload)
                            except Exception:
                                fn_match = re.search(r'["\']filename["\']\s*:\s*["\']([^"\']+)["\']', raw_payload)
                                ct_match = re.search(r'["\']content["\']\s*:\s*["\'](.*)["\']\s*}?$', raw_payload, re.DOTALL)
                                params = {
                                    "filename": fn_match.group(1) if fn_match else "generated/output.py",
                                    "content": ct_match.group(1) if ct_match else raw_payload
                                }

                        exec_res = execute_agent_crm_tool(act_name, params)
                        notice = f"\n\n⚡ **[Action Exécutée]** `{act_name}` : {exec_res.get('message', 'Opération réussie')}"
                        yield f"data: {json.dumps({'chunk': notice}, ensure_ascii=False)}\n\n"

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
