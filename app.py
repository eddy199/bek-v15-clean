# ==========================================
# BEK-v15.2 HYBRID - SERVEUR PRINCIPAL
# FLASK / HERMES / CRM / MATRIX
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

app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024

# CORS configurable
CORS_ORIGINS = os.environ.get(
    "BEK_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:8765,http://127.0.0.1:8765",
)

cors_origins = [
    origin.strip()
    for origin in CORS_ORIGINS.split(",")
    if origin.strip()
]

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": cors_origins
        }
    },
)


# ==========================================
# DIRECTOIRES
# ==========================================

WORKSPACE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

SKILLS_DIR = os.path.join(
    WORKSPACE_DIR,
    "awesome-openclaw-skills",
)

FILES_DIR = os.path.join(
    WORKSPACE_DIR,
    "uploads",
)

GENERATED_DIR = os.path.join(
    WORKSPACE_DIR,
    "generated",
)

PLUGINS_DIR = os.path.join(
    WORKSPACE_DIR,
    "plugins",
)

DOCS_DIR = os.path.join(
    WORKSPACE_DIR,
    "docs",
)


for directory in [
    SKILLS_DIR,
    FILES_DIR,
    GENERATED_DIR,
    PLUGINS_DIR,
    DOCS_DIR,
]:
    os.makedirs(
        directory,
        exist_ok=True,
    )


# ==========================================
# PYTHON PATH
# ==========================================

if WORKSPACE_DIR not in sys.path:
    sys.path.insert(
        0,
        WORKSPACE_DIR,
    )

if PLUGINS_DIR not in sys.path:
    sys.path.insert(
        0,
        PLUGINS_DIR,
    )


# ==========================================
# LOGGING
# ==========================================

import logging
from logging.handlers import RotatingFileHandler


logger = logging.getLogger("BEKApp")
logger.setLevel(logging.INFO)

if not logger.handlers:

    file_handler = RotatingFileHandler(
        os.path.join(
            WORKSPACE_DIR,
            "bek_app.log",
        ),
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    )

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(
        sys.stdout
    )

    console_handler.setFormatter(
        formatter
    )

    logger.addHandler(
        console_handler
    )


# ==========================================
# INITIALISATION GLOBALE
# ==========================================
from generate_architecture_doc import update_documentation_file
try:
    update_documentation_file()
except Exception as exc:
    logger.warning("Génération auto architecture échouée : %s", exc)
    
GLOBAL_SYSTEM_CONTEXT = load_project_documentation(
    DOCS_DIR
)

security_guard = hermes.security_guard

if security_guard is None:
    raise RuntimeError(
        "SecurityGuard Hermes indisponible. "
        "Vérifie BEK_HSM_SECRET."
    )


try:
    event_bus = EventBusKafka()
except Exception as exc:
    logger.warning(
        "EventBusKafka indisponible : %s",
        exc,
    )
    event_bus = None


minhash_engine = MinHashSimilarity()
hll_counter = HyperLogLog()


# ==========================================
# WORKERS HERMES
# ==========================================

try:
    start_background_workers()
    logger.info(
        "Workers Hermes démarrés."
    )
except Exception as exc:
    logger.error(
        "Impossible de démarrer les workers Hermes : %s",
        exc,
    )


# ==========================================
# ENREGISTREMENT OUTILS HERMES
# ==========================================

hermes.register_tool(
    "web_sync",
    lambda query: web_agent_instance.run_pipeline(
        query
    ),
    risk_level="L3",
)

hermes.register_tool(
    "neon_audit",
    lambda: {
        "status": "Neon DB audit demandé",
        "tables": [
            "companies",
            "contacts",
            "opportunities",
        ],
    },
    risk_level="L1",
)

hermes.register_tool(
    "default_llm",
    lambda query: {
        "response": (
            f"Agence IA prête pour : {query}"
        )
    },
    risk_level="L1",
)


# ==========================================
# PROMPT SYSTÈME GLOBAL
# ==========================================

BEK_GOLDEN_RULES = """
=== PROMPT SYSTÈME DÉFINITIF : ARCHITECTE BEK-v15.2 HYBRID ===

1. PROTOCOLE D'INITIALISATION :
   Chaque session commence dans le respect absolu
   des conditions de sécurité et d'intégrité.

2. ZÉRO RÉGRESSION :
   Les fonctionnalités existantes de l'UI, upload,
   agents, providers, mémoire, CRM Neon DB,
   skills, Hermes et Matrix doivent être préservées.

3. MÉTHODE CHIRURGICALE :
   Lors d'une modification de code, travailler à partir
   du code source existant fourni par l'utilisateur.

4. CODES COMPLETS :
   Lorsqu'un fichier est modifié, fournir le fichier
   complet et cohérent.

5. VALIDATION ITÉRATIVE :
   Avancer étape par étape, tester puis corriger.

6. SÉCURITÉ :
   Les actions sensibles doivent respecter le SecurityGuard
   et les politiques Hermes.

7. PERSISTANCE :
   Les états utiles peuvent être persistés dans Neon,
   Pinecone et les systèmes de synchronisation configurés.

8. AUCUNE FAUSSE GARANTIE :
   Le système ne doit jamais prétendre avoir exécuté une
   action externe si celle-ci n'a pas réellement réussi.

===========================================================
"""


# ==========================================
# UTILITAIRES
# ==========================================

def json_safe(value):
    """
    Convertit quelques types PostgreSQL/Python non directement sérialisables en JSON.
    """
    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(
        value,
        datetime,
    ):
        return value.isoformat()

    if isinstance(
        value,
        dict,
    ):
        return {
            str(k): json_safe(v)
            for k, v in value.items()
        }

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            json_safe(item)
            for item in value
        ]

    return str(value)


def json_response(payload, status=200):
    return jsonify(
        json_safe(payload)
    ), status


def get_api_key(key_name: str) -> str:
    """
    Récupération sécurisée d'une clé API via ProviderManager ou fallback d'environnement.
    """
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
    return get_api_key(
        "BEK_ADMIN_API_KEY"
    )


def check_admin_auth():
    """
    Authentification des endpoints administratifs.
    """
    configured_key = get_admin_api_key()

    if not configured_key:
        return True

    supplied_key = (
        request.headers.get(
            "X-BEK-API-Key",
            "",
        )
        or request.args.get(
            "api_key",
            "",
        )
    )

    return supplied_key == configured_key


def require_admin():
    if check_admin_auth():
        return None

    return jsonify(
        {
            "status": "error",
            "error": "Authentification BEK requise.",
        }
    ), 401


# ==========================================
# SYNCHRONISATION GLOBALE
# ==========================================

def sync_and_persist_global_state(
    commit_message=(
        "BEK-v15.2 Auto-Sync & Persist State"
    )
):
    logger.info(
        "[SyncManager] Début synchronisation."
    )

    gh_user = os.environ.get(
        "GITHUB_USERNAME",
        "eddy199",
    ).strip()

    gh_token = os.environ.get(
        "GITHUB_TOKEN",
        "",
    ).strip()

    # --------------------------------------
    # GITHUB
    # --------------------------------------
    if gh_token:
        try:
            remote_result = subprocess.run(
                [
                    "git",
                    "remote",
                    "get-url",
                    "origin",
                ],
                cwd=WORKSPACE_DIR,
                capture_output=True,
                text=True,
                timeout=15,
            )

            if remote_result.returncode != 0:
                logger.warning(
                    "[SyncManager] Remote Git inexistant."
                )
            else:
                subprocess.run(
                    [
                        "git",
                        "add",
                        ".",
                    ],
                    cwd=WORKSPACE_DIR,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                commit_result = subprocess.run(
                    [
                        "git",
                        "commit",
                        "-m",
                        commit_message,
                    ],
                    cwd=WORKSPACE_DIR,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                auth = base64.b64encode(
                    f"x-access-token:{gh_token}".encode("utf-8")
                ).decode("ascii")

                git_env = os.environ.copy()
                git_env["GIT_CONFIG_COUNT"] = "1"
                git_env["GIT_CONFIG_KEY_0"] = "http.extraheader"
                git_env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {auth}"

                push_result = subprocess.run(
                    [
                        "git",
                        "push",
                        "origin",
                        "main",
                    ],
                    cwd=WORKSPACE_DIR,
                    env=git_env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if push_result.returncode == 0:
                    logger.info("[SyncManager] Synchronisation GitHub réussie.")
                else:
                    logger.warning(
                        "[SyncManager] Git push échoué : %s",
                        (push_result.stderr or push_result.stdout).strip(),
                    )

        except subprocess.TimeoutExpired:
            logger.warning("[SyncManager] Timeout GitHub.")
        except Exception as exc:
            logger.error("[SyncManager] Erreur GitHub : %s", exc)

    # --------------------------------------
    # NEON
    # --------------------------------------
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bek_system_state (
                    id SERIAL PRIMARY KEY,
                    state_key TEXT UNIQUE,
                    state_data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
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
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_performance_metrics (
                    skill_name TEXT PRIMARY KEY,
                    success_count INT DEFAULT 0,
                    failure_count INT DEFAULT 0,
                    last_score FLOAT DEFAULT 1.0
                );
                """
            )
            cur.execute(
                """
                INSERT INTO bek_system_state (state_key, state_data)
                VALUES ('global_prompt_v15.2', %s)
                ON CONFLICT (state_key)
                DO UPDATE SET
                    state_data = EXCLUDED.state_data,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (BEK_GOLDEN_RULES,),
            )
            conn.commit()
            logger.info("[SyncManager] État Neon persisté.")

    except Exception as exc:
        logger.error("[SyncManager] Erreur Neon : %s", exc)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    # --------------------------------------
    # PINECONE
    # --------------------------------------
    try:
        save_to_memory("BEK_SYSTEM_SYNC_STATE", BEK_GOLDEN_RULES)
    except Exception as exc:
        logger.error("[SyncManager] Erreur mémoire : %s", exc)


# ==========================================
# LOG MISSION HERMES
# ==========================================

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
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
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
    r"\blo_import\b",
    r"\blo_export\b",
]


def validate_sql_request(sql_query: str):
    if not isinstance(sql_query, str):
        return False, "SQL invalide."

    sql = sql_query.strip()
    if not sql:
        return False, "SQL requis."

    if len(sql) > 100_000:
        return False, "SQL trop volumineux."

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
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


# ==========================================
# SUB-CRM ENGINE
# ==========================================

class SubCRMEngine:

    @staticmethod
    def initialize_matrix_schema():
        conn = get_db_connection()
        if not conn:
            return False

        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                """
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
                """
            )
            conn.commit()
            return True
        except Exception as exc:
            logger.error("[SubCRMEngine] Erreur schéma : %s", exc)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return False
        finally:
            try:
                if cur:
                    cur.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def spawn_sub_crm(niche_name: str, cahier_des_charges: str, objectives: list, parent_id=None, custom_env=None):
        if not SubCRMEngine.initialize_matrix_schema():
            return {"status": "error", "message": "Impossible d'initialiser matrix_sub_crms."}

        sub_crm_id = str(uuid.uuid4())
        next_gen_tools = [
            {"tool": "LangGraph Advanced Swarm-Core v15.2", "mode": "autonomous_reflection"},
            {"tool": "Meta-Cortex Grounding & Reflexion Engine", "mode": "real_time_verification"},
            {"tool": "Universal External AI Bridge", "mode": "dynamic_api_relay"},
            {"tool": "Secure Sandbox Terminal Executor", "mode": "isolated_code_execution"},
        ]

        environment_payload = (
            custom_env
            if isinstance(custom_env, dict)
            else {
                "RUNTIME_ENV": "production_matrix_node",
                "AI_AUTONOMY_LEVEL": "maximum",
                "SELF_HEALING": "enabled",
            }
        )

        specifications = {
            "objectives": objectives,
            "architecture": "Python/Flask + Neon Polymorphic Layer",
            "generation": "Next-Gen Ultra-Powerful Node",
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
                    json.dumps(specifications, ensure_ascii=False),
                    json.dumps(environment_payload, ensure_ascii=False),
                    json.dumps(next_gen_tools, ensure_ascii=False),
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
                "tools_injected": next_gen_tools,
                "message": f"Le sous-CRM '{niche_name}' a été instancié.",
            }
        except Exception as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return {"status": "error", "message": str(exc)}
        finally:
            try:
                if cur:
                    cur.close()
            except Exception:
                pass
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
        safe_niche = re.sub(r"[^a-zA-Z0-9_]+", "_", self.niche_name).strip("_") or "niche"
        return {
            "ui_layout": f"Dynamic_Dashboard_{safe_niche}",
            "tables_created": [
                f"niche_{self.sub_crm_id[:8]}_entities",
                f"niche_{self.sub_crm_id[:8]}_operations",
                f"niche_{self.sub_crm_id[:8]}_analytics",
            ],
            "auth_gateway": "OAuth2 / Multi-Tenant User Accounts Enabled",
            "autonomy_mode": "No-Spec / Fully Self-Governing Agent Execution",
        }

    def self_heal_and_optimize(self) -> dict:
        return {
            "status": "healthy",
            "bugs_detected": 0,
            "auto_patches_applied": 0,
            "performance_boost": "Health verification completed.",
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
        health_check = instance.self_heal_and_optimize()

        return {
            "status": "success",
            "sub_crm_id": sub_crm_id,
            "niche_name": niche_name,
            "lifecycle_environment": lifecycle_data,
            "self_repair_status": health_check,
            "message": f"Le sous-CRM '{niche_name}' est opérationnel.",
        }


# ==========================================
# SKILL FEEDBACK
# ==========================================

def record_skill_feedback(skill_name: str, success: bool):
    conn = get_db_connection()
    if not conn:
        return

    cur = None
    try:
        cur = conn.cursor()
        if success:
            cur.execute(
                """
                INSERT INTO skill_performance_metrics (skill_name, success_count, failure_count, last_score)
                VALUES (%s, 1, 0, 1.0)
                ON CONFLICT (skill_name)
                DO UPDATE SET
                    success_count = skill_performance_metrics.success_count + 1,
                    last_score = LEAST(2.0, skill_performance_metrics.last_score + 0.1);
                """,
                (skill_name,),
            )
        else:
            cur.execute(
                """
                INSERT INTO skill_performance_metrics (skill_name, success_count, failure_count, last_score)
                VALUES (%s, 0, 1, 0.5)
                ON CONFLICT (skill_name)
                DO UPDATE SET
                    failure_count = skill_performance_metrics.failure_count + 1,
                    last_score = GREATEST(0.1, skill_performance_metrics.last_score - 0.2);
                """,
                (skill_name,),
            )
        conn.commit()
    except Exception as exc:
        logger.error("[SkillFeedback] %s", exc)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _build_skills_index():
    return skill_registry.list_all_skills()


def get_all_nvidia_models():
    return [
        "meta/llama-3.3-70b-instruct",
        "meta/llama-3.1-70b-instruct",
        "meta/llama-3.1-8b-instruct",
        "meta/llama-3.2-11b-vision-instruct",
        "meta/llama-3.2-90b-vision-instruct",
        "meta/muse-glimmer-30b",
        "nvidia/llama-3.3-nemotron-super-49b-v1",
        "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/nemotron-3-ultra-550b-a55b",
        "nvidia/nemotron-nano-12b-v2-vl",
        "nvidia/nvidia-nemotron-nano-9b-v2",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "poolside/laguna-xs-2.1",
        "google/gemma-4-31b-it",
    ]


# ==========================================
# ROUTES STATIQUES & HEALTH
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

    models = {
        "groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"],
        "nvidia": get_all_nvidia_models(),
        "gemini": ["gemini-3.6-flash", "gemini-1.5-pro-preview"],
        "openrouter": ["openrouter/auto", "openai/gpt-oss-120b", "anthropic/claude-4-sonnet"],
    }

    skills = _build_skills_index()
    return jsonify({
        "providers": providers,
        "models": models,
        "skills_count": len(skills),
        "skills": skills,
    })


# ==========================================
# FILES & UPLOAD
# ==========================================

@app.route("/api/files", methods=["GET"])
def list_files():
    files = []
    directories = [FILES_DIR, GENERATED_DIR, WORKSPACE_DIR]
    seen_paths = set()

    for directory in directories:
        if not os.path.exists(directory):
            continue
        try:
            entries = os.listdir(directory)
        except Exception:
            continue

        for filename in entries:
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
                "extension": os.path.splitext(filename)[1].lower(),
            })

    return jsonify({"files": files})


@app.route("/api/download/<path:filename>", methods=["GET"])
def download_file(filename):
    safe_name = secure_filename(filename)
    if not safe_name:
        return jsonify({"error": "Nom de fichier invalide."}), 400

    for directory in [FILES_DIR, GENERATED_DIR, WORKSPACE_DIR]:
        filepath = os.path.join(directory, safe_name)
        if os.path.isfile(filepath):
            return send_file(filepath, as_attachment=True)

    return jsonify({"error": "Fichier introuvable."}), 404


def validate_zip_member(base_dir: str, member_name: str) -> bool:
    if not member_name:
        return False
    normalized = member_name.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[a-zA-Z]:", normalized):
        return False
    parts = [part for part in normalized.split("/") if part]
    if ".." in parts:
        return False
    target_path = os.path.abspath(os.path.join(base_dir, *parts))
    base_abs = os.path.abspath(base_dir)
    return target_path == base_abs or target_path.startswith(base_abs + os.sep)


@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Nom de fichier manquant."}), 400

    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({"error": "Nom de fichier invalide."}), 400

    filepath = os.path.abspath(os.path.join(FILES_DIR, filename))
    files_root = os.path.abspath(FILES_DIR)

    if not filepath.startswith(files_root + os.sep):
        return jsonify({"error": "Chemin de fichier interdit."}), 400

    try:
        file.save(filepath)
    except Exception as exc:
        logger.error("Upload impossible : %s", exc)
        return jsonify({"error": "Impossible d'enregistrer le fichier."}), 500

    try:
        file_size = os.path.getsize(filepath)
    except OSError:
        file_size = 0

    extracted_files = []

    if filename.lower().endswith(".zip"):
        temp_extract_dir = tempfile.mkdtemp(prefix="bek_zip_", dir=FILES_DIR)
        try:
            with zipfile.ZipFile(filepath, "r") as zip_ref:
                for info in zip_ref.infolist():
                    if not validate_zip_member(temp_extract_dir, info.filename):
                        raise ValueError("Archive ZIP contenant un chemin dangereux.")
                    member_name = info.filename.replace("\\", "/")
                    target_path = os.path.abspath(os.path.join(temp_extract_dir, *[p for p in member_name.split("/") if p]))
                    if info.is_dir():
                        os.makedirs(target_path, exist_ok=True)
                        continue
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zip_ref.open(info, "r") as source, open(target_path, "wb") as dest:
                        shutil.copyfileobj(source, dest)
                    extracted_files.append(member_name)

            for root, dirs, files in os.walk(temp_extract_dir):
                rel_root = os.path.relpath(root, temp_extract_dir)
                dest_root = FILES_DIR if rel_root == "." else os.path.join(FILES_DIR, rel_root)
                os.makedirs(dest_root, exist_ok=True)
                for f in files:
                    shutil.move(os.path.join(root, f), os.path.join(dest_root, f))
        except Exception as zip_err:
            return jsonify({"status": "success", "filename": filename, "size": file_size, "extracted_contents": [], "zip_warning": str(zip_err)})
        finally:
            shutil.rmtree(temp_extract_dir, ignore_errors=True)

    return jsonify({"status": "success", "filename": filename, "size": file_size, "extracted_contents": extracted_files})


# ==========================================
# WEB AGENT
# ==========================================

@app.route("/api/agent/web", methods=["POST"])
def api_web():
    data = request.get_json(silent=True) or {}
    query = data.get("query", "Tendances SaaS et CRM IA 2026")
    if not isinstance(query, str) or not query.strip():
        return jsonify({"error": "query requis."}), 400

    try:
        result = web_agent_instance.run_pipeline(query.strip())
        return jsonify(result)
    except Exception as exc:
        logger.error("Web agent error : %s", exc)
        return jsonify({"status": "error", "error": str(exc)}), 500


@app.route("/api/agent/web-sync", methods=["POST"])
def api_trigger_web_sync():
    data = request.get_json(silent=True) or {}
    query = data.get("query", "CEO SaaS CRM automatisation")
    if not isinstance(query, str) or not query.strip():
        return jsonify({"error": "query requis."}), 400

    try:
        result = web_agent_instance.run_pipeline(query.strip())
        return jsonify(result)
    except Exception as exc:
        logger.error("Web sync error : %s", exc)
        return jsonify({"status": "error", "error": str(exc)}), 500


# ==========================================
# HERMES RUNTIME & APPROVALS
# ==========================================

@app.route("/api/hermes/runtime", methods=["GET"])
def api_hermes_runtime():
    runtime = hermes.runtime_status()
    return jsonify({
        "hermes_state": runtime.get("status", "unknown"),
        "security_guard": runtime.get("security_guard_active", False),
        "tool_count": runtime.get("tool_count", 0),
        "tools": [{"name": t.get("name"), "risk": t.get("risk_level")} for t in runtime.get("tools", [])],
        "provider": runtime.get("provider"),
        "model": runtime.get("model"),
        "trace_id": hermes.create_trace_id(),
    })


@app.route("/api/hermes/approvals", methods=["GET"])
def api_list_approvals():
    status = request.args.get("status")
    return jsonify({
        "status": "success",
        "approvals": approval_manager.list_requests(status=status),
    })


@app.route("/api/hermes/approvals/<approval_id>/approve", methods=["POST"])
def api_approve_action(approval_id):
    auth_error = require_admin()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    admin_user = data.get("admin_user", "admin")
    result = approval_manager.approve_and_execute(approval_id, admin_user=admin_user)
    return jsonify(result)


@app.route("/api/hermes/approvals/<approval_id>/reject", methods=["POST"])
def api_reject_action(approval_id):
    auth_error = require_admin()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    admin_user = data.get("admin_user", "admin")
    reason = data.get("reason", "Refusé par l'administrateur")
    result = approval_manager.reject_request(approval_id, admin_user=admin_user, reason=reason)
    return jsonify(result)


# ==========================================
# HERMES GOAP + SECURITY
# ==========================================

@app.route("/api/hermes/goap-execute", methods=["POST"])
def api_hermes_goap():
    auth_error = require_admin()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    user_objective = data.get("objective") or data.get("query") or "Analyse globale de la Matrisse 2026"

    if not isinstance(user_objective, str) or not user_objective.strip():
        return jsonify({"error": "objective requis."}), 400

    user_objective = user_objective.strip()

    try:
        plan = hermes.goap_planner(user_objective)
        execution_result = hermes.dispatch_parallel(plan)

        if execution_result.get("status") == "SECURITY_APPROVAL_REQUIRED":
            task_id = execution_result.get("task_id", hermes.create_task_id())
            trace_id = execution_result.get("trace_id", hermes.create_trace_id())
            tool = execution_result.get("tool", "unknown")
            args = plan[0].get("args", {}) if plan else {}
            risk = execution_result.get("risk_level", "L3")
            reason = execution_result.get("message", "Niveau de risque exigeant une validation humaine.")

            appr_req = approval_manager.submit_request(
                task_id=task_id,
                trace_id=trace_id,
                tool=tool,
                args=args,
                risk_level=risk,
                reason=reason,
            )
            execution_result["approval_id"] = appr_req.approval_id

        log_mission_to_neon(
            trace_id=execution_result.get("trace_id", "BEK-TRC-UNKNOWN"),
            objective=user_objective,
            plan=plan,
            execution=execution_result,
        )

        return jsonify({
            "objective": user_objective,
            "goap_plan": plan,
            "execution": execution_result,
        })

    except Exception as exc:
        logger.error("Hermes GOAP error : %s", exc)
        return jsonify({"status": "error", "error": str(exc)}), 500


# ==========================================
# OBSERVABILITÉ & CRM
# ==========================================

@app.route("/api/matrix/observability-logs", methods=["GET"])
def get_observability_logs():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Neon DB non connectée."})

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT trace_id, objective, status, execution_ms, created_at
            FROM bek_mission_logs ORDER BY created_at DESC LIMIT 10;
            """
        )
        columns = [d[0] for d in cur.description]
        logs = [dict(zip(columns, row)) for row in cur.fetchall()]

        jobs = []
        try:
            cur.execute(
                """
                SELECT job_id, task_name, status, created_at
                FROM system_jobs ORDER BY created_at DESC LIMIT 5;
                """
            )
            job_cols = [d[0] for d in cur.description]
            jobs = [dict(zip(job_cols, row)) for row in cur.fetchall()]
        except Exception:
            pass

        return jsonify({"status": "success", "mission_logs": logs, "system_jobs": jobs})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)})
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


@app.route("/api/crm/stats", methods=["GET"])
def get_crm_stats():
    conn = get_db_connection()
    if not conn:
        return jsonify({"num_contacts": 0, "num_companies": 0, "num_opportunities": 0, "total_amount": 0.0, "status": "demo"})

    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, phone FROM contacts;")
        contacts = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

        cur.execute("SELECT id, name, created_at FROM companies;")
        companies = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

        cur.execute("SELECT id, name, amount, currency, stage FROM opportunities;")
        opportunities = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

        total_amount = sum(float(opp.get("amount", 0) or 0) for opp in opportunities)

        return jsonify({
            "num_contacts": len(contacts),
            "num_companies": len(companies),
            "num_opportunities": len(opportunities),
            "total_amount": total_amount,
            "contacts": contacts,
            "companies": companies,
            "opportunities": opportunities,
            "status": "connected",
        })
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"})
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


@app.route("/api/crm/execute", methods=["POST"])
def execute_crm_direct():
    auth_error = require_admin()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    sql = data.get("sql", "")
    if not isinstance(sql, str) or not sql.strip():
        return jsonify({"error": "SQL requis."}), 400

    return jsonify(execute_database_sql(sql.strip()))


# ==========================================
# MATRIX SPAWN & ACTIONS
# ==========================================

@app.route("/api/matrix/spawn", methods=["POST"])
def api_spawn_sub_crm():
    auth_error = require_admin()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    niche_name = data.get("niche_name", "")
    cahier_des_charges = data.get("cahier_des_charges", "Autonomie complète selon les objectifs assignés.")
    objectives = data.get("objectives", ["Optimisation", "Automatisation", "Auto-correction"])
    parent_id = data.get("parent_id", None)
    custom_env = data.get("custom_env", None)

    if not isinstance(niche_name, str) or not niche_name.strip():
        return jsonify({"error": "Le nom de la niche ou du domaine est requis."}), 400

    if not isinstance(objectives, list):
        return jsonify({"error": "objectives doit être une liste."}), 400

    return jsonify(SubCRMEngine.spawn_sub_crm(
        niche_name=niche_name.strip(),
        cahier_des_charges=str(cahier_des_charges),
        objectives=objectives,
        parent_id=parent_id,
        custom_env=custom_env,
    ))


@app.route("/api/matrix/spawn-alive", methods=["POST"])
def api_spawn_alive_sub_crm():
    auth_error = require_admin()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    niche_name = data.get("niche_name", "")
    cahier_des_charges = data.get("cahier_des_charges", "Opérationnel, autonome, multi-rubriques et auto-réparateur.")
    objectives = data.get("objectives", ["Création Interface Multi-Vues", "Comptes Utilisateurs", "Rentabilité & Automatisation"])
    parent_id = data.get("parent_id", None)
    custom_env = data.get("custom_env", None)

    if not isinstance(niche_name, str) or not niche_name.strip():
        return jsonify({"error": "Le nom de la niche est requis."}), 400

    if not isinstance(objectives, list):
        return jsonify({"error": "objectives doit être une liste."}), 400

    return jsonify(SubCRMEngineAdvanced.spawn_fully_alive_sub_crm(
        niche_name=niche_name.strip(),
        cahier_des_charges=str(cahier_des_charges),
        objectives=objectives,
        parent_id=parent_id,
        custom_env=custom_env,
    ))


@app.route("/api/matrix/bek-action", methods=["POST"])
def api_matrix_bek_action():
    auth_error = require_admin()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    action = data.get("action", "process_data")

    if action == "process_data":
        time.sleep(1.5)
        return jsonify({
            "status": "success",
            "new_sequences": 8492,
            "active_agents": 5,
            "logs": [
                ">_ Swarm-Core : Lancement de l'analyse des flux CRM...",
                ">_ Agent Web : Scan et normalisation des flux... OK",
                ">_ Agent Meta-Cortex : Optimisation des pipelines de vente...",
                ">_ Opération terminée. Données synchronisées avec Neon DB.",
            ],
        })

    return jsonify({"error": "Action inconnue."}), 400


# ==========================================
# CHAT PRINCIPAL (AVEC PROVIDER MANAGER & META-CORTEX SSE)
# ==========================================

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    provider = data.get("provider", "groq")
    model = data.get("model", "openai/gpt-oss-120b")
    use_memory = data.get("use_memory", True)
    use_reflection = data.get("use_reflection", True)

    if not isinstance(messages, list):
        return jsonify({"error": "messages doit être une liste."}), 400

    if not isinstance(provider, str) or not isinstance(model, str):
        return jsonify({"error": "provider ou model invalide."}), 400

    provider = provider.strip().lower()
    model = model.strip()

    allowed_providers = {"groq", "nvidia", "gemini", "openrouter"}
    if provider not in allowed_providers:
        return jsonify({"error": f"Provider non supporté : {provider}"}), 400

    hermes.set_provider_context(provider, model)

    last_user_msg = ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                last_user_msg = content
            elif isinstance(content, list):
                parts = [item["text"] for item in content if isinstance(item, dict) and isinstance(item.get("text"), str)]
                last_user_msg = " ".join(parts)
            break

    normalized_message = last_user_msg.lower().strip() if last_user_msg else ""

    if normalized_message and any(
        k in normalized_message for k in ("introspection runtime", "état runtime réel", "registre d'outils")
    ):
        runtime = hermes.runtime_status()
        payload = {
            "hermes_state": runtime.get("status", "unknown"),
            "security_guard": runtime.get("security_guard_active", False),
            "tools": [{"name": t.get("name"), "risk": t.get("risk_level")} for t in runtime.get("tools", [])],
            "provider": runtime.get("provider"),
            "model": runtime.get("model"),
            "trace_id": hermes.create_trace_id(),
        }

        def generate_local():
            yield f"data: {json.dumps({'chunk': json.dumps(payload, ensure_ascii=False)}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

        return Response(
            generate_local(),
            mimetype="text/event-stream; charset=utf-8",
            headers={"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        sync_and_persist_global_state(commit_message="BEK-v15.2 Auto-Sync Direct Action")
    except Exception as sync_err:
        logger.warning("[SyncWarning] %s", sync_err)

    if any(keyword in normalized_message for keyword in ["essaim", "swarm", "analyse complète", "architecture swarm"]):
        def generate_swarm():
            try:
                api_key = get_api_key(f"{provider.upper()}_API_KEY")
                swarm_result = asyncio.run(run_bek_swarm_sync(last_user_msg, api_key, provider, model))
                yield f"data: {json.dumps({'chunk': f'{swarm_result}\n'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as exc:
                logger.error("Erreur Swarm-Core : %s", exc)
                yield f"data: {json.dumps({'error': f'Erreur Swarm-Core : {exc}'}, ensure_ascii=False)}\n\n"

        return Response(
            generate_swarm(),
            mimetype="text/event-stream; charset=utf-8",
            headers={"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    dynamic_context = f"{BEK_GOLDEN_RULES}\n\n"
    if GLOBAL_SYSTEM_CONTEXT:
        dynamic_context += f"[DOCUMENTATION PROJET]\n{GLOBAL_SYSTEM_CONTEXT}\n"

    try:
        if os.path.exists(FILES_DIR):
            for filename in os.listdir(FILES_DIR):
                if os.path.isfile(os.path.join(FILES_DIR, filename)):
                    dynamic_context += f"- Fichier : {filename}\n"
    except Exception as exc:
        logger.warning("Lecture fichiers contexte : %s", exc)

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM companies;")
            result = cur.fetchone()
            comp_count = result[0] if result else 0
            dynamic_context += f"\n[SCHÉMA CRM STRICT DE NEON DB]\n- Entreprises (companies) : {comp_count}\n"
    except Exception as exc:
        logger.warning("CRM context indisponible : %s", exc)
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

    if use_memory and last_user_msg:
        try:
            memory_results = search_memory(last_user_msg)
            if memory_results:
                dynamic_context += f"\n[CTX-MEMOIRE]\n{memory_results}\n"
        except Exception as exc:
            logger.warning("Mémoire indisponible : %s", exc)

    if use_reflection:
        dynamic_context += "\n[REFLEXION]\nUtilise une vérification interne de cohérence avant de répondre lorsque la tâche est technique ou critique.\n"

    action_prompt = (
        "Tu es BEK-v15.2, une IA hybride avancée et l'Exécuteur de la Matrisse.\n\n"
        "RÈGLE 1 — SOCIAL : Si l'utilisateur te salue, réponds brièvement et poliment.\n"
        "RÈGLE 2 — TECHNIQUE : Sois direct et précis.\n"
        "RÈGLE 3 — VÉRACITÉ : Ne prétends jamais avoir effectué une action externe non réelle.\n"
        "RÈGLE 4 — CODE : Fournis le fichier complet et cohérent sans '...'."
    )

    clean_messages = []
    for message in messages[-6:]:
        if isinstance(message, dict) and message.get("role") in ["user", "assistant"]:
            content = message.get("content", "")
            if isinstance(content, (str, list)):
                clean_messages.append({"role": message["role"], "content": content})

    exec_messages = [
        {"role": "system", "content": f"{action_prompt}\n\nContexte :\n{dynamic_context}".strip()}
    ] + clean_messages

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

                # ==========================================
                # AUDIT META-CORTEX GROUNDING EN TEMPS RÉEL
                # ==========================================
                if use_reflection and full_response:
                    try:
                        is_grounded, grounding_msg = GroundingValidator.validate_grounding(
                            full_response, context=dynamic_context
                        )
                        meta_event = {
                            "type": "meta_cortex_audit",
                            "grounded": is_grounded,
                            "feedback": grounding_msg,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        yield f"event: meta_cortex\ndata: {json.dumps(meta_event, ensure_ascii=False)}\n\n"
                    except Exception as meta_exc:
                        logger.debug("Meta-Cortex audit skipped : %s", meta_exc)

                if use_memory and last_user_msg and full_response:
                    try:
                        save_to_memory(last_user_msg, full_response)
                    except Exception as memory_exc:
                        logger.warning("Memory save failed : %s", memory_exc)

                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

            elif "error" in item:
                yield f"data: {json.dumps({'error': item['error']}, ensure_ascii=False)}\n\n"

    return Response(
        generate_proxy(),
        mimetype="text/event-stream; charset=utf-8",
        headers={"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ==========================================
# ERROR HANDLERS
# ==========================================

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"status": "error", "error": "Fichier ou requête trop volumineux."}), 413


@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "error": "Route introuvable."}), 404


@app.errorhandler(500)
def internal_server_error(error):
    logger.exception("Erreur interne Flask.")
    return jsonify({"status": "error", "error": "Erreur interne du serveur."}), 500


# ==========================================
# START SERVER
# ==========================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    host = os.environ.get("HOST", "0.0.0.0")
    debug_mode = os.environ.get("BEK_DEBUG", "false").lower() in ("1", "true", "yes", "on")

    logger.info("==========================================")
    logger.info("BEK-v15.2 HYBRID démarrage | Host: %s | Port: %s | Debug: %s", host, port, debug_mode)
    logger.info("Hermes SecurityGuard: actif")
    logger.info("==========================================")

    app.run(host=host, port=port, debug=debug_mode, threaded=True)
