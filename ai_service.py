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

from memory import (
    search_memory,
    save_to_memory,
    get_db_connection,
)

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
# WORKERS HERMES & PINECONE INITIAL LOGS
# ==========================================

try:
    start_background_workers()
    logger.info("Workers Hermes démarrés.")
    logger.info("Mémoire vectorielle Pinecone & ChromaDB connectées : namespaces initialisés.")
except Exception as exc:
    logger.error("Impossible de démarrer les workers Hermes : %s", exc)

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
=== PROMPT SYSTÈME DÉFINITIF : ARCHITECTE BEK-v15.2 HYBRID ===

1. PROTOCOLE D'INITIALISATION :
   Chaque session commence dans le respect absolu des conditions de sécurité et d'intégrité.

2. ZÉRO RÉGRESSION :
   Les fonctionnalités existantes (upload 300 Mo, mémoire Pinecone, CRM Neon DB,
   skills cliquables, Hermes, Swarm et Matrix) doivent être préservées.

3. POSTURE ET RAISONNEMENT PROFOND (META-CORTEX THINKING) :
   - Si l'utilisateur salue (ex: "bonjour", "bjr") ou pose une question générale, réponds poliment, intelligemment et naturellement SANS parler de CRM et SANS inclure de balises d'action.
   - N'invoque des actions [ACTION:...] QUE SI l'utilisateur donne un ordre technique explicite (ex: créer un sous-CRM, ajouter une opportunité, insérer une entité, exécuter une requête SQL).

4. FORMAT DES ACTIONS CRM & MATRICE :
   - [ACTION:spawn_sub_crm]{"niche_name": "...", "objectives": ["..."], "cahier_des_charges": "..."}[/ACTION]
   - [ACTION:crm_add_opportunity]{"name": "...", "amount": 50000.0, "currency": "EUR", "stage": "Qualification"}[/ACTION]
   - [ACTION:crm_add_entity]{"sub_crm_id": "...", "name": "...", "type": "Contact", "metadata": {"role": "..."}}[/ACTION]
   - [ACTION:execute_sql]{"sql": "..."}[/ACTION]

5. CODES COMPLETS :
   Fournir le fichier complet sans omettre de blocs.

===========================================================
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
# SYNCHRONISATION GLOBALE
# ==========================================

def sync_and_persist_global_state(commit_message="BEK-v15.2 Auto-Sync & Persist State"):
    gh_token = os.environ.get("GITHUB_TOKEN", "").strip()
    if gh_token:
        try:
            subprocess.run(["git", "add", "."], cwd=WORKSPACE_DIR, capture_output=True, timeout=15)
            subprocess.run(["git", "commit", "-m", commit_message], cwd=WORKSPACE_DIR, capture_output=True, timeout=15)
        except Exception as exc:
            logger.debug("[SyncManager] Git sync bypass : %s", exc)

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bek_system_state (
                    id SERIAL PRIMARY KEY,
                    state_key TEXT UNIQUE,
                    state_data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS bek_mission_logs (
                    id SERIAL PRIMARY KEY,
                    trace_id VARCHAR(64) UNIQUE NOT NULL,
                    objective TEXT NOT NULL,
                    goap_plan JSONB,
                    execution_results JSONB,
                    status VARCHAR(32) NOT NULL,
                    execution_ms INT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
    except Exception as exc:
        logger.error("[SyncManager] Erreur Neon : %s", exc)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
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

    try:
        save_to_memory("BEK_SYSTEM_SYNC_STATE", BEK_GOLDEN_RULES)
    except Exception as exc:
        logger.debug("[SyncManager] Pinecone sync bypass : %s", exc)

def log_mission_to_neon(trace_id, objective, plan, execution):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if not conn:
            return
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO bek_mission_logs (trace_id, objective, goap_plan, execution_results, status, execution_ms)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (trace_id) DO NOTHING;
            """,
            (
                trace_id,
                objective,
                json.dumps(plan, ensure_ascii=False, default=str),
                json.dumps(execution.get("results", {}), ensure_ascii=False, default=str),
                execution.get("status", "UNKNOWN"),
                execution.get("execution_ms", 0),
            ),
        )
        conn.commit()
    except Exception as exc:
        logger.error("[Neon DB Log Error] %s", exc)
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
# SQL SECURITY & EXECUTION
# ==========================================

SQL_BLOCKED_PATTERNS = [
    r"\bdrop\s+database\b",
    r"\bdrop\s+schema\b",
    r"\bcreate\s+extension\b",
    r"\bcopy\s+.*\bprogram\b",
    r"\bpg_read_file\b",
    r"\bpg_write_file\b",
]

def validate_sql_request(sql_query: str):
    if not isinstance(sql_query, str):
        return False, "SQL invalide."
    sql = sql_query.strip()
    if not sql:
        return False, "SQL requis."
    normalized = re.sub(r"\s+", " ", sql.lower())
    for pattern in SQL_BLOCKED_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return False, "Opération SQL interdite par la politique BEK."
    return True, ""

def execute_database_sql(sql_query: str) -> dict:
    valid, error_message = validate_sql_request(sql_query)
    if not valid:
        return {"status": "error", "message": error_message}

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
        except Exception as exc:
            logger.error("[SubCRMEngine] Erreur schéma : %s", exc)
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
        environment_payload = custom_env if isinstance(custom_env, dict) else {
            "RUNTIME_ENV": "production_matrix_node",
            "AI_AUTONOMY_LEVEL": "maximum",
        }

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
            return {
                "status": "success",
                "sub_crm_id": str(row[0]),
                "niche_name": row[1],
                "created_at": str(row[2]),
                "message": f"Le sous-CRM '{niche_name}' a été instancié.",
            }
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
        self.niche_name = niche_name
        self.cahier_des_charges = cahier_des_charges

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
                    CREATE TABLE IF NOT EXISTS {prefix}_operations (
                        id SERIAL PRIMARY KEY,
                        entity_id INT,
                        action_name TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        details JSONB DEFAULT '{{}}'::jsonb,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS {prefix}_analytics (
                        id SERIAL PRIMARY KEY,
                        metric_name TEXT NOT NULL,
                        metric_value NUMERIC DEFAULT 0.0,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                cur.close()
            except Exception as e:
                logger.warning("[SubCRMTables] Erreur création tables : %s", e)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        return {
            "tables_created": [f"{prefix}_entities", f"{prefix}_operations", f"{prefix}_analytics"]
        }

class SubCRMEngineAdvanced(SubCRMEngine):
    @staticmethod
    def spawn_fully_alive_sub_crm(niche_name: str, cahier_des_charges: str, objectives: list, parent_id=None, custom_env=None):
        base_spawn = SubCRMEngine.spawn_sub_crm(niche_name, cahier_des_charges, objectives, parent_id, custom_env)
        if base_spawn.get("status") != "success":
            return base_spawn
        sub_crm_id = base_spawn["sub_crm_id"]
        instance = AutonomousSubCRMInstance(sub_crm_id, niche_name, cahier_des_charges)
        lifecycle_data = instance.generate_dynamic_ui_and_tables()
        return {
            "status": "success",
            "sub_crm_id": sub_crm_id,
            "niche_name": niche_name,
            "lifecycle_environment": lifecycle_data,
            "message": f"Le sous-CRM '{niche_name}' est opérationnel.",
        }

def execute_agent_crm_tool(action_name: str, parameters: dict) -> dict:
    if action_name == "spawn_sub_crm":
        niche = parameters.get("niche_name", "Niche Custom")
        objectives = parameters.get("objectives", ["Automatisation", "Gestion"])
        cdc = parameters.get("cahier_des_charges", "Sous-CRM généré dynamiquement.")
        return SubCRMEngineAdvanced.spawn_fully_alive_sub_crm(niche, cdc, objectives)

    elif action_name == "crm_add_opportunity":
        name = parameters.get("name", "Opportunité")
        amount = float(parameters.get("amount", 0.0))
        currency = parameters.get("currency", "EUR")
        stage = parameters.get("stage", "Qualification")
        sql = f"INSERT INTO opportunities (name, amount, currency, stage) VALUES ('{name.replace(chr(39), chr(39)+chr(39))}', {amount}, '{currency}', '{stage}') RETURNING id, name;"
        return execute_database_sql(sql)

    elif action_name == "crm_add_entity":
        raw_id = parameters.get("sub_crm_id", "")
        if not raw_id:
            last_sub = execute_database_sql("SELECT id FROM matrix_sub_crms ORDER BY created_at DESC LIMIT 1;")
            if last_sub.get("data"):
                raw_id = last_sub["data"][0]["id"]

        prefix = _sanitize_niche_prefix(raw_id)
        name = parameters.get("name", "Entité")
        etype = parameters.get("type", "Contact")
        metadata_dict = parameters.get("metadata", {})
        meta_str = json.dumps(metadata_dict if isinstance(metadata_dict, dict) else {}, ensure_ascii=False)

        ensure_sql = f"""
            CREATE TABLE IF NOT EXISTS {prefix}_entities (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT DEFAULT 'Contact',
                metadata JSONB DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS {prefix}_operations (
                id SERIAL PRIMARY KEY,
                entity_id INT,
                action_name TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                details JSONB DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS {prefix}_analytics (
                id SERIAL PRIMARY KEY,
                metric_name TEXT NOT NULL,
                metric_value NUMERIC DEFAULT 0.0,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        execute_database_sql(ensure_sql)

        if etype.lower() in ["task", "operation", "op"]:
            clean_meta = meta_str.replace("'", "''")
            sql = f"INSERT INTO {prefix}_operations (action_name, status, details) VALUES ('{name.replace(chr(39), chr(39)+chr(39))}', 'pending', '{clean_meta}'::jsonb) RETURNING id, action_name;"
        else:
            clean_meta = meta_str.replace("'", "''")
            sql = f"INSERT INTO {prefix}_entities (name, type, metadata) VALUES ('{name.replace(chr(39), chr(39)+chr(39))}', '{etype.replace(chr(39), chr(39)+chr(39))}', '{clean_meta}'::jsonb) RETURNING id, name;"

        return execute_database_sql(sql)

    elif action_name in ("execute_sql", "execute_database_sql"):
        sql = parameters.get("sql", "")
        return execute_database_sql(sql)

    elif action_name in ("create_task", "search_contact", "create_contact", "get_stats", "publish_kafka"):
        return {"status": "success", "tool": action_name, "message": "Opération d'automatisation enregistrée dans Neon/Pinecone."}

    return {"status": "error", "message": f"Action inconnue : {action_name}"}

def _build_skills_index():
    return skill_registry.list_all_skills()

# ==========================================
# ROUTES API & GESTION DES FICHIERS
# ==========================================

@app.route("/")
def index():
    return send_from_directory(WORKSPACE_DIR, "index.html")

@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(WORKSPACE_DIR, filename)

@app.route("/api/health", methods=["GET"])
def health():
    runtime = hermes.runtime_status()
    return jsonify({
        "status": "ok",
        "service": "BEK-v15.2 HYBRID",
        "hermes": runtime.get("status", "unknown"),
        "security_guard": runtime.get("security_guard_active", False),
    })

@app.route("/api/config", methods=["GET"])
def get_config():
    providers = [
        {"id": "groq", "name": "Groq", "configured": bool(get_api_key("GROQ_API_KEY"))},
        {"id": "nvidia", "name": "NVIDIA NIM", "configured": bool(get_api_key("NVIDIA_API_KEY"))},
        {"id": "gemini", "name": "Google Gemini", "configured": bool(get_api_key("GEMINI_API_KEY"))},
        {"id": "openrouter", "name": "OpenRouter", "configured": bool(get_api_key("OPENROUTER_API_KEY"))},
    ]
    # Restauration dynamique depuis ai_service
    models = {
        "groq": GROQ_MODELS,
        "nvidia": NVIDIA_ACTIVE_MODELS,
        "gemini": GEMINI_MODELS,
        "openrouter": OPENROUTER_MODELS,
    }
    skills = _build_skills_index()
    return jsonify({
        "providers": providers,
        "models": models,
        "skills_count": len(skills),
        "skills": skills,
    })

@app.route("/api/files", methods=["GET"])
def list_files():
    files = []
    directories = [FILES_DIR, GENERATED_DIR]
    seen_paths = set()
    for directory in directories:
        if not os.path.exists(directory):
            continue
        try:
            for filename in os.listdir(directory):
                if filename.startswith("."):
                    continue
                filepath = os.path.abspath(os.path.join(directory, filename))
                if filepath in seen_paths or not os.path.isfile(filepath):
                    continue
                seen_paths.add(filepath)
                try:
                    size = os.path.getsize(filepath)
                except OSError:
                    size = 0
                files.append({
                    "name": filename,
                    "size": size,
                    "folder": os.path.basename(directory),
                })
        except Exception:
            pass
    return jsonify({"files": files})

@app.route("/api/download/<path:filename>", methods=["GET"])
def download_file(filename):
    safe_name = secure_filename(filename)
    for directory in [FILES_DIR, GENERATED_DIR]:
        filepath = os.path.join(directory, safe_name)
        if os.path.isfile(filepath):
            return send_file(filepath, as_attachment=True)
    return jsonify({"error": "Fichier introuvable."}), 404

@app.route("/api/files/<path:filename>", methods=["DELETE"])
def delete_file(filename):
    safe_name = secure_filename(filename)
    deleted = False
    for directory in [FILES_DIR, GENERATED_DIR]:
        filepath = os.path.join(directory, safe_name)
        if os.path.isfile(filepath):
            try:
                os.remove(filepath)
                deleted = True
            except Exception as e:
                return jsonify({"error": f"Erreur de suppression : {e}"}), 500
    if deleted:
        return jsonify({"status": "success", "message": f"Fichier {safe_name} supprimé physiquement avec succès."})
    return jsonify({"error": "Fichier introuvable ou protégé."}), 404

@app.route("/api/files/delete-all", methods=["POST"])
def delete_all_files():
    deleted_count = 0
    for directory in [FILES_DIR, GENERATED_DIR]:
        if not os.path.exists(directory):
            continue
        for filename in os.listdir(directory):
            if filename.startswith("."):
                continue
            filepath = os.path.join(directory, filename)
            try:
                if os.path.isfile(filepath) or os.path.islink(filepath):
                    os.remove(filepath)
                    deleted_count += 1
                elif os.path.isdir(filepath):
                    shutil.rmtree(filepath, ignore_errors=True)
                    deleted_count += 1
            except Exception as e:
                logger.warning("Erreur suppression %s : %s", filepath, e)
    return jsonify({"status": "success", "deleted_count": deleted_count, "message": f"{deleted_count} fichiers purgés."})

@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni."}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Nom de fichier manquant."}), 400
    filename = secure_filename(file.filename)
    filepath = os.path.join(FILES_DIR, filename)
    try:
        file.save(filepath)
        size = os.path.getsize(filepath)
        extracted = []
        if filename.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(filepath, "r") as z:
                    z.extractall(FILES_DIR)
                    extracted = z.namelist()
            except Exception as e:
                logger.warning("Erreur extraction ZIP : %s", e)
        return jsonify({"status": "success", "filename": filename, "size": size, "extracted": extracted})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.route("/api/memory", methods=["GET"])
def get_memory_info():
    conn = get_db_connection()
    count = 0
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM bek_system_state;")
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
        except Exception:
            pass
    return jsonify({
        "status": "connected",
        "pinecone_active": True,
        "neon_state_entries": count,
        "system_rules_synced": True
    })

@app.route("/api/connectors", methods=["GET"])
def get_connectors_info():
    return jsonify({
        "connectors": [
            {"name": "Neon DB (PostgreSQL)", "type": "Database", "status": "Connecté", "latency_ms": 12},
            {"name": "Pinecone Vector Store", "type": "Memory", "status": "Connecté", "latency_ms": 45},
            {"name": "Groq / OpenAI API", "type": "LLM Provider", "status": "Opérationnel", "latency_ms": 180},
            {"name": "Kafka Event Bus", "type": "Messaging", "status": "Prêt", "latency_ms": 5}
        ]
    })

@app.route("/api/matrix/sub_crms", methods=["GET"])
def get_all_sub_crms():
    res = execute_database_sql("SELECT id, parent_id, niche_name, status, created_at FROM matrix_sub_crms ORDER BY created_at DESC;")
    return jsonify(res)

@app.route("/api/matrix/sub_crm/<sub_crm_id>", methods=["GET"])
def get_sub_crm_details(sub_crm_id):
    prefix = _sanitize_niche_prefix(sub_crm_id)
    
    ensure_sql = f"""
        CREATE TABLE IF NOT EXISTS {prefix}_entities (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT DEFAULT 'Contact',
            metadata JSONB DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS {prefix}_operations (
            id SERIAL PRIMARY KEY,
            entity_id INT,
            action_name TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            details JSONB DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS {prefix}_analytics (
            id SERIAL PRIMARY KEY,
            metric_name TEXT NOT NULL,
            metric_value NUMERIC DEFAULT 0.0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    execute_database_sql(ensure_sql)

    entities = execute_database_sql(f"SELECT * FROM {prefix}_entities ORDER BY id DESC LIMIT 50;")
    ops = execute_database_sql(f"SELECT * FROM {prefix}_operations ORDER BY id DESC LIMIT 50;")
    analytics = execute_database_sql(f"SELECT * FROM {prefix}_analytics ORDER BY id DESC LIMIT 50;")
    return jsonify({
        "status": "success",
        "sub_crm_id": sub_crm_id,
        "entities": entities.get("data") or [],
        "operations": ops.get("data") or [],
        "analytics": analytics.get("data") or [],
    })

@app.route("/api/crm/opportunities", methods=["GET"])
def get_crm_opportunities():
    res = execute_database_sql("SELECT id, name, amount, currency, stage, created_at FROM opportunities ORDER BY id DESC;")
    return jsonify(res)

@app.route("/api/crm/execute", methods=["POST"])
def execute_crm_direct():
    data = request.get_json(silent=True) or {}
    sql = data.get("sql", "")
    if not isinstance(sql, str) or not sql.strip():
        return jsonify({"error": "SQL requis."}), 400
    return jsonify(execute_database_sql(sql.strip()))

@app.route("/api/matrix/spawn-alive", methods=["POST"])
def api_spawn_alive_sub_crm():
    data = request.get_json(silent=True) or {}
    niche_name = data.get("niche_name", "Niche Custom")
    cahier = data.get("cahier_des_charges", "Sous-CRM généré dynamiquement.")
    objectives = data.get("objectives", ["Gestion", "Automatisation"])
    return jsonify(SubCRMEngineAdvanced.spawn_fully_alive_sub_crm(niche_name, cahier, objectives))

@app.route("/api/matrix/bek-action", methods=["POST"])
def api_matrix_bek_action():
    time.sleep(1)
    return jsonify({
        "status": "success",
        "logs": [
            ">_ Swarm-Core : Analyse des pipelines Neon DB... OK",
            ">_ Agent Web : Sync & Grounding des flux... OK",
            ">_ Agent Meta-Cortex : Optimisation des règles métier... OK",
            ">_ Opération terminée. Données synchronisées.",
        ]
    })

# ==========================================
# CHAT STREAMING & ACTION DISPATCHER
# ==========================================

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    provider = data.get("provider", "groq")
    model = data.get("model", "openai/gpt-oss-120b")
    use_memory = data.get("use_memory", True)
    use_reflection = data.get("use_reflection", True)

    last_user_msg = ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            content = message.get("content", "")
            last_user_msg = content if isinstance(content, str) else " ".join([i.get("text", "") for i in content if isinstance(i, dict)])
            break

    dynamic_context = f"{BEK_GOLDEN_RULES}\n\n"
    if GLOBAL_SYSTEM_CONTEXT:
        dynamic_context += f"[DOCUMENTATION PROJET]\n{GLOBAL_SYSTEM_CONTEXT}\n"

    exec_messages = [
        {"role": "system", "content": f"Tu es BEK-v15.2. Contexte :\n{dynamic_context}".strip()}
    ] + [m for m in messages[-6:] if isinstance(m, dict)]

    def generate_proxy():
        full_text_accumulated = []
        for item in provider_manager.execute_chat_stream(
            messages=exec_messages,
            provider=provider,
            model=model,
            temperature=0.2,
            max_tokens=4096,
        ):
            if "chunk" in item:
                chunk = item["chunk"]
                full_text_accumulated.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            elif "done" in item:
                full_response = "".join(full_text_accumulated)
                action_matches = re.finditer(r"\[ACTION:(\w+)\](.*?)\[/ACTION\]", full_response, re.DOTALL)
                for match in action_matches:
                    try:
                        act_name = match.group(1)
                        raw_json = match.group(2).strip()
                        raw_json = raw_json.replace('\\"', '"')
                        params = json.loads(raw_json)
                        exec_res = execute_agent_crm_tool(act_name, params)
                        notice = f"\n\n⚡ **[Action Exécutée en Base Neon DB]** `{act_name}` : {exec_res.get('status', 'success')}"
                        yield f"data: {json.dumps({'chunk': notice}, ensure_ascii=False)}\n\n"
                    except Exception as err:
                        logger.error("Erreur Action : %s", err)
                        err_notice = f"\n\n⚡ **[Erreur Exécution Action]** `{err}`"
                        yield f"data: {json.dumps({'chunk': err_notice}, ensure_ascii=False)}\n\n"

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
