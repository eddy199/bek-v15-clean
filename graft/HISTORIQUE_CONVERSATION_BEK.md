Oui. Étape 2 = memory.py. Ton fichier fonctionne, mais il y a quelques faiblesses importantes : chemin ROOT codé en dur, gestion DB trop permissive, appels réseau sans contrôle suffisant, top_k non borné et gestion des dimensions d'embeddings à renforcer.

Je te donne directement le fichier complet corrigé, comme tu préfères.

"""
BEK-v15.2 HYBRID
Memory Layer
----------------
Couche mémoire locale / Pinecone / Neon PostgreSQL.

Responsabilités :
- chargement sécurisé de la configuration ;
- gestion des embeddings ;
- mémoire vectorielle Pinecone ;
- connexion PostgreSQL / Neon ;
- journalisation ;
- nettoyage et validation des entrées.

IMPORTANT :
Cette couche ne décide pas des permissions d'exécution.
La validation des actions Hermes reste du ressort de SecurityGuard.
"""

from __future__ import annotations

import datetime
import hashlib
import logging
import math
import os
import sys
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


# ============================================================
# ENCODAGE STDOUT / STDERR
# ============================================================

if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer)
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer)


# ============================================================
# PATHS
# ============================================================

# Le fichier memory.py se trouve normalement directement
# dans le workspace du projet.
ROOT = Path(__file__).resolve().parent

WS_DIR = ROOT
SKILLS_DIR = ROOT / "skills"
PLUGINS_DIR = ROOT / "plugins"
UPLOAD_DIR = ROOT / "uploads"
GENERATED_DIR = ROOT / "generated"

for directory in (
    SKILLS_DIR,
    PLUGINS_DIR,
    UPLOAD_DIR,
    GENERATED_DIR,
):
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


# ============================================================
# ENVIRONMENT
# ============================================================

ENV: Dict[str, str] = {}


def _load_env_file(path: Path) -> Dict[str, str]:
    """
    Charge un fichier env.txt simple de type KEY=VALUE.

    Les variables d'environnement système restent prioritaires
    lors de leur récupération via _env().
    """
    values: Dict[str, str] = {}

    if not path.exists() or not path.is_file():
        return values

    try:
        with path.open(
            "r",
            encoding="utf-8-sig",
            errors="replace",
        ) as fh:
            for raw_line in fh:
                line = raw_line.strip()

                if (
                    not line
                    or line.startswith("#")
                    or line.startswith("=")
                ):
                    continue

                if "=" not in line:
                    continue

                key, value = line.split("=", 1)

                key = key.strip()
                value = value.strip()

                if not key:
                    continue

                values[key] = value

    except OSError:
        pass

    return values


# Supporte env.txt à la racine du workspace.
ENV.update(_load_env_file(ROOT / "env.txt"))


def _env(
    key: str,
    default: str = "",
) -> str:
    """
    Récupération de configuration.

    Priorité :
    1. variable d'environnement système ;
    2. env.txt ;
    3. valeur par défaut.
    """
    return os.getenv(
        key,
        ENV.get(key, default),
    )


# ============================================================
# API CONFIGURATION
# ============================================================

GROQ_API_KEY = _env("GROQ_API_KEY", "")
NVIDIA_API_KEY = _env("NVIDIA_API_KEY", "")
PINECONE_API_KEY = _env("PINECONE_API_KEY", "")

PINECONE_INDEX_NAME = _env(
    "PINECONE_INDEX_NAME",
    "bek-memory",
)

NEON_DATABASE_URL = _env(
    "DATABASE_URL",
    _env("NEON_DATABASE_URL", ""),
)


# ============================================================
# LIMITS
# ============================================================

MAX_EMBEDDING_INPUT_LENGTH = 2000
DEFAULT_EMBEDDING_DIM = 1024

DEFAULT_TOP_K = 2
MIN_TOP_K = 1
MAX_TOP_K = 50

PINECONE_TIMEOUT_SECONDS = 10
DATABASE_CONNECT_TIMEOUT_SECONDS = 10


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger("BEKAgent")
logger.setLevel(logging.INFO)

if not logger.handlers:

    try:
        file_handler = RotatingFileHandler(
            ROOT / "bek_agent.log",
            maxBytes=10_000_000,
            backupCount=5,
            encoding="utf-8",
        )

        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - "
                "%(levelname)s - "
                "%(message)s"
            )
        )

        logger.addHandler(file_handler)

    except OSError:
        pass

    stream_handler = logging.StreamHandler(sys.stdout)

    stream_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - "
            "%(levelname)s - "
            "%(message)s"
        )
    )

    logger.addHandler(stream_handler)


# ============================================================
# UTILS
# ============================================================

def clean_string(text: Any) -> str:
    """
    Nettoie les chaînes et supprime les surrogate characters
    pouvant casser JSON / UTF-8.
    """
    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    return "".join(
        character
        for character in text
        if not (
            0xD800
            <= ord(character)
            <= 0xDFFF
        )
    )


def _safe_top_k(top_k: Any) -> int:
    """
    Normalise top_k afin d'éviter des valeurs abusives.
    """
    try:
        value = int(top_k)
    except (TypeError, ValueError):
        value = DEFAULT_TOP_K

    return max(
        MIN_TOP_K,
        min(value, MAX_TOP_K),
    )


# ============================================================
# EMBEDDINGS
# ============================================================

def _fallback_embedding(
    text: str,
    target_dim: int = DEFAULT_EMBEDDING_DIM,
) -> List[float]:
    """
    Embedding local déterministe de secours.

    Ce n'est pas un modèle sémantique équivalent à NVIDIA,
    mais permet au système de continuer à fonctionner sans API.
    """
    if target_dim <= 0:
        return []

    vector = [0.0] * target_dim

    words = text.lower().split()

    if not words:
        words = [text.lower()]

    for index, word in enumerate(words):

        try:
            digest = hashlib.sha256(
                word.encode("utf-8")
            ).hexdigest()

            bucket = int(digest, 16) % target_dim

        except Exception:
            continue

        weight = 1.0 / math.sqrt(index + 1)

        vector[bucket] += weight

    norm = math.sqrt(
        sum(value * value for value in vector)
    )

    if norm <= 0:
        return vector

    return [
        value / norm
        for value in vector
    ]


def get_embedding(
    text: str,
    input_type: str = "query",
    target_dim: int = DEFAULT_EMBEDDING_DIM,
) -> List[float]:
    """
    Génère un embedding NVIDIA si disponible.

    Fallback local déterministe si NVIDIA est indisponible.
    """
    text = clean_string(text)

    if not text:
        return []

    if target_dim <= 0:
        logger.warning(
            "Invalid embedding dimension: %s",
            target_dim,
        )
        return []

    text = text[:MAX_EMBEDDING_INPUT_LENGTH]

    if NVIDIA_API_KEY:

        try:
            url = (
                "https://integrate.api.nvidia.com/"
                "v1/embeddings"
            )

            headers = {
                "Authorization": (
                    f"Bearer {NVIDIA_API_KEY}"
                ),
                "Content-Type": "application/json",
            }

            payload = {
                "input": [text],
                "model": (
                    "nvidia/"
                    "embeddings-nv-embed-qa-4"
                ),
                "input_type": input_type,
            }

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=PINECONE_TIMEOUT_SECONDS,
            )

            response.raise_for_status()

            body = response.json()

            data = body.get("data")

            if (
                isinstance(data, list)
                and data
                and isinstance(data[0], dict)
            ):
                embedding = data[0].get(
                    "embedding"
                )

                if (
                    isinstance(embedding, list)
                    and embedding
                ):
                    try:
                        vector = [
                            float(value)
                            for value in embedding
                        ]
                    except (
                        TypeError,
                        ValueError,
                    ):
                        vector = []

                    if vector:
                        return vector

            logger.warning(
                "NVIDIA returned an invalid embedding."
            )

        except requests.RequestException as exc:
            logger.warning(
                "NVIDIA embedding unavailable: %s",
                exc,
            )

        except Exception as exc:
            logger.warning(
                "NVIDIA embedding processing failed: %s",
                exc,
            )

    return _fallback_embedding(
        text,
        target_dim=target_dim,
    )


# ============================================================
# PINECONE
# ============================================================

def get_pinecone_index() -> Optional[Any]:
    """
    Retourne l'index Pinecone configuré.

    Aucun secret n'est écrit dans les logs.
    """
    if not PINECONE_API_KEY:
        logger.warning(
            "PINECONE_API_KEY non configurée."
        )
        return None

    if not PINECONE_INDEX_NAME:
        logger.warning(
            "PINECONE_INDEX_NAME non configuré."
        )
        return None

    try:
        from pinecone import Pinecone

        client = Pinecone(
            api_key=PINECONE_API_KEY
        )

        return client.Index(
            PINECONE_INDEX_NAME
        )

    except ImportError:
        logger.error(
            "Le package 'pinecone' n'est pas installé."
        )
        return None

    except Exception as exc:
        logger.error(
            "Erreur d'initialisation Pinecone: %s",
            exc,
        )
        return None


# ============================================================
# MEMORY SEARCH
# ============================================================

def search_memory(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> str:
    """
    Recherche dans la mémoire vectorielle.
    """
    query = clean_string(query)

    if not query:
        return ""

    top_k = _safe_top_k(top_k)

    index = get_pinecone_index()

    if index is None:
        return ""

    logger.info(
        "Recherche mémoire Pinecone | query_length=%s | top_k=%s",
        len(query),
        top_k,
    )

    vector = get_embedding(
        query,
        input_type="query",
    )

    if not vector:
        return ""

    try:
        response = index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True,
        )

        matches = []

        if hasattr(response, "get"):
            matches = response.get(
                "matches",
                [],
            )

        elif hasattr(response, "matches"):
            matches = response.matches or []

        if not matches:
            return ""

        context_lines: List[str] = []

        for match in matches:

            if hasattr(match, "get"):
                metadata = match.get(
                    "metadata",
                    {},
                )
            else:
                metadata = getattr(
                    match,
                    "metadata",
                    {},
                )

            if not isinstance(
                metadata,
                dict,
            ):
                metadata = {}

            date_value = clean_string(
                metadata.get(
                    "date",
                    "Inconnue",
                )
            )

            text_value = clean_string(
                metadata.get(
                    "text",
                    "",
                )
            )

            if not text_value:
                continue

            context_lines.append(
                f"- Date: {date_value} | "
                f"Info: {text_value}"
            )

        return "\n".join(context_lines)

    except Exception as exc:
        logger.error(
            "Erreur recherche Pinecone: %s",
            exc,
        )
        return ""


# ============================================================
# MEMORY SAVE
# ============================================================

def save_to_memory(
    user_query: str,
    agent_response: str,
) -> bool:
    """
    Sauvegarde une interaction dans Pinecone.
    """
    user_query = clean_string(user_query)
    agent_response = clean_string(agent_response)

    if not user_query and not agent_response:
        return False

    index = get_pinecone_index()

    if index is None:
        return False

    logger.info(
        "Enregistrement interaction en mémoire Pinecone."
    )

    combined_text = (
        f"Requête: {user_query}\n"
        f"Réponse: {agent_response[:1000]}"
    )

    combined_text = clean_string(
        combined_text
    )

    vector = get_embedding(
        combined_text,
        input_type="passage",
    )

    if not vector:
        return False

    record_id = str(uuid.uuid4())

    metadata = {
        "text": combined_text,
        "date": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "type": "conversation",
    }

    try:
        index.upsert(
            vectors=[
                {
                    "id": record_id,
                    "values": vector,
                    "metadata": metadata,
                }
            ]
        )

        logger.info(
            "Interaction sauvegardée | record=%s",
            record_id,
        )

        return True

    except Exception as exc:
        logger.error(
            "Erreur upsert Pinecone: %s",
            exc,
        )
        return False


# ============================================================
# DATABASE / NEON
# ============================================================

def get_db_connection() -> Optional[Any]:
    """
    Connexion directe à Neon PostgreSQL.

    Retourne None si la configuration ou le driver est
    indisponible.

    Le timeout empêche un blocage prolongé au démarrage.
    """
    if not NEON_DATABASE_URL:
        logger.warning(
            "DATABASE_URL / NEON_DATABASE_URL non configuré."
        )
        return None

    try:
        import psycopg2

    except ImportError:
        logger.error(
            "psycopg2 non installé."
        )
        return None

    try:
        connection = psycopg2.connect(
            NEON_DATABASE_URL,
            connect_timeout=(
                DATABASE_CONNECT_TIMEOUT_SECONDS
            ),
        )

        return connection

    except Exception as exc:
        logger.error(
            "Erreur connexion Neon DB: %s",
            exc,
        )
        return None
Résumé de l'étape 2
État	Résultat
ROOT codé en dur	✅ corrigé
top_k sans limite	✅ corrigé
Embedding fallback	✅ renforcé
NVIDIA timeout/erreurs	✅ mieux gérés
Pinecone erreurs	✅ renforcées
Date mémoire	✅ UTC
PostgreSQL timeout	✅ ajouté
Secrets dans les logs	✅ évités
Compatibilité Hermes get_db_connection()	✅ conservée

Action maintenant : remplace entièrement ton memory.py par celui-ci et lance ton test de démarrage/Hermes.

Une fois que c'est OK, on passe à l'étape 3, sans modifier plusieurs fichiers en même temps.

cest bon code modifier etape suivante go 

Parfait. Étape Memory terminée. ✅

Étape suivante : intégration principale

Envoie-moi maintenant le code complet de app.py.

Je vais vérifier uniquement :

🔴 ce qui est dangereux / bloquant
🟠 ce qui casse l’intégration Hermes ↔ SecurityGuard ↔ Memory
🟢 ce qui est déjà bon
puis je te renverrai le fichier app.py COMPLET corrigé, pas des morceaux.

Après validation de app.py, on passe directement au fichier suivant.

le code de fichier app.py    # ==========================================
# BEK-v15.2 HYBRID - SERVEUR PRINCIPAL (FLASK)
# ==========================================

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

# Modules Meta-Cortex
from meta_cortex_grounding import GroundingValidator
from meta_cortex_swarm import ReflexionSwarm

# Agent Web
from web_agent import web_agent_instance

# Noyau Hermes
from hermes_core import (
    hermes,
    start_background_workers,
)


# ==========================================
# FLASK
# ==========================================

app = Flask(__name__)

CORS(app)

app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024


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
# INITIALISATION GLOBALE
# ==========================================

GLOBAL_SYSTEM_CONTEXT = load_project_documentation(
    DOCS_DIR
)

security_guard = hermes.security_guard

if security_guard is None:
    raise RuntimeError(
        "SecurityGuard Hermes indisponible : "
        "BEK_HSM_SECRET doit être configuré."
    )


event_bus = EventBusKafka()

minhash_engine = MinHashSimilarity()

hll_counter = HyperLogLog()


# ==========================================
# WORKERS D'ARRIÈRE-PLAN
# ==========================================

start_background_workers()


# ==========================================
# ENREGISTREMENT DES OUTILS HERMES
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
        "status": "Neon DB connectée et stable",
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
        "response": f"Agence IA prête pour : {query}"
    },
    risk_level="L1",
)


# ==========================================
# PROMPT SYSTÈME GLOBAL
# ==========================================

BEK_GOLDEN_RULES = """
=== PROMPT SYSTÈME DÉFINITIF : ARCHITECTE BEK-v15.2 HYBRID ===
1. PROTOCOLE D'INITIALISATION : Chaque session commence par rappeler le respect absolu des conditions.
2. ZÉRO RÉGRESSION : Les fonctionnalités actuelles (UI, upload, agent image, multi-providers, agents web/mémoire, CRM Neon DB, skills) sont sacrées et intouchables.
3. MÉTHODE CHIRURGICALE : Demander l'ancien code source fonctionnel uniquement sur demande explicite de programmation/modification de fichier. Ne jamais réécrire un fichier de zéro.
4. CODES COMPLETS : Fournir les fichiers mis à jour en entier, sans aucun raccourci ni commentaire réducteur.
5. VALIDATION ITÉRATIVE : Avancer étape par étape, tester et corriger immédiatement.
6. SYNCHRONISATION ET AUTOMATISATION GLOBALE : Garantir la persistance et la mise à jour automatique sur GitHub (eddy199/bek-v15-clean), Pinecone, ChromaDB local, Neon DB / CRM API et Vercel.
=============================================================
"""


# ==========================================
# SYNCHRONISATION GLOBALE
# ==========================================

def sync_and_persist_global_state(
    commit_message="BEK-v15.2 Auto-Sync & Persist State"
):
    print(
        "[SyncManager] Démarrage de la "
        "synchronisation globale multi-serveurs..."
    )

    gh_user = os.environ.get(
        "GITHUB_USERNAME",
        "eddy199",
    )

    gh_token = os.environ.get(
        "GITHUB_TOKEN",
        "",
    )

    if gh_token:
        try:
            remote_url = (
                f"https://{gh_user}:{gh_token}"
                f"
@
GitHub
.com/{gh_user}/bek-v15-clean.git"
            )

            subprocess.run(
                [
                    "git",
                    "remote",
                    "set-url",
                    "origin",
                    remote_url,
                ],
                cwd=WORKSPACE_DIR,
                capture_output=True,
            )

            subprocess.run(
                [
                    "git",
                    "add",
                    ".",
                ],
                cwd=WORKSPACE_DIR,
                capture_output=True,
            )

            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    commit_message,
                ],
                cwd=WORKSPACE_DIR,
                capture_output=True,
            )

            push_res = subprocess.run(
                [
                    "git",
                    "push",
                    "origin",
                    "main",
                ],
                cwd=WORKSPACE_DIR,
                capture_output=True,
                text=True,
            )

            if push_res.returncode == 0:
                print(
                    "[SyncManager] "
                    "Synchronisation GitHub réussie."
                )
            else:
                print(
                    "[SyncManager] "
                    f"Git push non effectué : "
                    f"{push_res.stderr.strip()}"
                )

        except Exception as exc:
            print(
                "[SyncManager] "
                f"Erreur GitHub : {exc}"
            )

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
                    created_at TIMESTAMP WITH TIME ZONE
                        DEFAULT CURRENT_TIMESTAMP
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
                INSERT INTO bek_system_state
                    (state_key, state_data)
                VALUES
                    ('global_prompt_v15.2', %s)
                ON CONFLICT (state_key)
                DO UPDATE SET
                    state_data = EXCLUDED.state_data,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    BEK_GOLDEN_RULES,
                ),
            )

            conn.commit()

            cur.close()
            conn.close()

            print(
                "[SyncManager] "
                "État et tables persistés dans Neon PostgreSQL."
            )

    except Exception as db_err:
        print(
            "[SyncManager] "
            f"Erreur persistance Neon DB : {db_err}"
        )

    try:
        save_to_memory(
            "BEK_SYSTEM_SYNC_STATE",
            BEK_GOLDEN_RULES,
        )

        print(
            "[SyncManager] "
            "Mémoire vectorielle synchronisée."
        )

    except Exception as mem_err:
        print(
            "[SyncManager] "
            f"Erreur persistance mémoire : {mem_err}"
        )


# ==========================================
# LOG MISSION HERMES
# ==========================================

def log_mission_to_neon(
    trace_id,
    objective,
    plan,
    execution,
):
    conn = None
    cur = None

    try:
        conn = get_db_connection()

        if not conn:
            return

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bek_mission_logs
                (
                    trace_id,
                    objective,
                    goap_plan,
                    execution_results,
                    status,
                    execution_ms
                )
            VALUES
                (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (trace_id)
            DO NOTHING;
            """,
            (
                trace_id,
                objective,
                json.dumps(
                    plan,
                    ensure_ascii=False,
                ),
                json.dumps(
                    execution.get(
                        "results",
                        {},
                    ),
                    ensure_ascii=False,
                ),
                execution.get(
                    "status",
                    "UNKNOWN",
                ),
                execution.get(
                    "execution_ms",
                    0,
                ),
            ),
        )

        conn.commit()

    except Exception as exc:
        print(
            f"[Neon DB Log Error]: {exc}"
        )

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
            if conn:
                conn.close()
        except Exception:
            pass


# ==========================================
# EXÉCUTION SQL
# ==========================================

def execute_database_sql(
    sql_query: str
) -> dict:

    conn = get_db_connection()

    if not conn:
        return {
            "status": "error",
            "message": (
                "Connexion Neon DB indisponible."
            ),
        }

    cur = None

    try:
        cur = conn.cursor()

        cur.execute(sql_query)

        if cur.description:
            columns = [
                desc[0]
                for desc in cur.description
            ]

            rows = cur.fetchall()

            results = [
                dict(
                    zip(
                        columns,
                        row,
                    )
                )
                for row in rows
            ]

            return {
                "status": "success",
                "type": "select",
                "data": results,
                "count": len(results),
            }

        conn.commit()

        affected = cur.rowcount

        return {
            "status": "success",
            "type": "mutation",
            "affected_rows": affected,
        }

    except Exception as exc:

        try:
            conn.rollback()
        except Exception:
            pass

        return {
            "status": "error",
            "message": str(exc),
        }

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
                    parent_id UUID
                        REFERENCES matrix_sub_crms(id)
                        ON DELETE SET NULL,
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

            print(
                "[SubCRMEngine Error] "
                f"Initialisation schéma matrice : {exc}"
            )

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
    def spawn_sub_crm(
        niche_name: str,
        cahier_des_charges: str,
        objectives: list,
        parent_id=None,
        custom_env=None,
    ):

        if not SubCRMEngine.initialize_matrix_schema():
            return {
                "status": "error",
                "message": (
                    "Impossible d'initialiser "
                    "le schéma matrix_sub_crms."
                ),
            }

        sub_crm_id = str(
            uuid.uuid4()
        )

        next_gen_tools = [
            {
                "tool": "LangGraph Advanced Swarm-Core v15.2",
                "mode": "autonomous_reflection",
            },
            {
                "tool": "Meta-Cortex Grounding & Reflexion Engine",
                "mode": "real_time_verification",
            },
            {
                "tool": "Universal External AI Bridge",
                "mode": "dynamic_api_relay",
            },
            {
                "tool": "Secure Sandbox Terminal Executor",
                "mode": "isolated_code_execution",
            },
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
            "architecture": (
                "Python/Flask + Neon Polymorphic Layer"
            ),
            "generation": (
                "Next-Gen Ultra-Powerful Node"
            ),
        }

        conn = get_db_connection()

        if not conn:
            return {
                "status": "error",
                "message": (
                    "Connexion Neon DB indisponible "
                    "pour l'instanciation."
                ),
            }

        cur = None

        try:
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO matrix_sub_crms
                    (
                        id,
                        parent_id,
                        niche_name,
                        specifications,
                        environment_vars,
                        active_tools,
                        cahier_des_charges,
                        status
                    )
                VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'active'
                    )
                RETURNING id, niche_name, created_at;
                """,
                (
                    sub_crm_id,
                    parent_id,
                    niche_name,
                    json.dumps(
                        specifications,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        environment_payload,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        next_gen_tools,
                        ensure_ascii=False,
                    ),
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
                "message": (
                    f"Le sous-CRM '{niche_name}' "
                    "a été instancié."
                ),
            }

        except Exception as exc:

            try:
                conn.rollback()
            except Exception:
                pass

            return {
                "status": "error",
                "message": str(exc),
            }

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
# AUTONOMOUS SUB-CRM
# ==========================================

class AutonomousSubCRMInstance:

    def __init__(
        self,
        sub_crm_id: str,
        niche_name: str,
        cahier_des_charges: str,
    ):
        self.sub_crm_id = sub_crm_id
        self.niche_name = niche_name
        self.cahier_des_charges = cahier_des_charges

    def generate_dynamic_ui_and_tables(self) -> dict:

        safe_niche = re.sub(
            r"[^a-zA-Z0-9_]+",
            "_",
            self.niche_name,
        ).strip("_")

        if not safe_niche:
            safe_niche = "niche"

        return {
            "ui_layout": (
                f"Dynamic_Dashboard_{safe_niche}"
            ),
            "tables_created": [
                f"niche_{self.sub_crm_id[:8]}_entities",
                f"niche_{self.sub_crm_id[:8]}_operations",
                f"niche_{self.sub_crm_id[:8]}_analytics",
            ],
            "auth_gateway": (
                "OAuth2 / Multi-Tenant User Accounts Enabled"
            ),
            "autonomy_mode": (
                "No-Spec / Fully Self-Governing Agent Execution"
            ),
        }

    def self_heal_and_optimize(self) -> dict:
        return {
            "status": "healthy_and_profitable",
            "bugs_detected": 0,
            "auto_patches_applied": 1,
            "performance_boost": (
                "Optimized via Autonomous Swarm "
                "Reflexion & Self-Healing"
            ),
        }


class SubCRMEngineAdvanced(SubCRMEngine):

    @staticmethod
    def spawn_fully_alive_sub_crm(
        niche_name: str,
        cahier_des_charges: str,
        objectives: list,
        parent_id=None,
        custom_env=None,
    ):

        base_spawn = SubCRMEngine.spawn_sub_crm(
            niche_name,
            cahier_des_charges,
            objectives,
            parent_id,
            custom_env,
        )

        if base_spawn.get("status") != "success":
            return base_spawn

        sub_crm_id = base_spawn["sub_crm_id"]

        instance = AutonomousSubCRMInstance(
            sub_crm_id,
            niche_name,
            cahier_des_charges,
        )

        lifecycle_data = (
            instance.generate_dynamic_ui_and_tables()
        )

        health_check = (
            instance.self_heal_and_optimize()
        )

        return {
            "status": "success",
            "sub_crm_id": sub_crm_id,
            "niche_name": niche_name,
            "lifecycle_environment": lifecycle_data,
            "self_repair_status": health_check,
            "message": (
                f"Le sous-CRM '{niche_name}' "
                "est opérationnel."
            ),
        }


# ==========================================
# API KEYS
# ==========================================

def get_api_key(key_name):

    val = os.environ.get(
        key_name,
        "",
    )

    if val:
        return val.strip(
            '"\' \r\n'
        )

    for env_path in [
        os.path.join(
            WORKSPACE_DIR,
            "env.txt",
        ),
        os.path.join(
            WORKSPACE_DIR,
            ".env",
        ),
    ]:

        if not os.path.exists(env_path):
            continue

        try:

            with open(
                env_path,
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as file:

                for line in file:

                    line = line.strip()

                    if line.startswith(
                        key_name + "="
                    ):

                        return (
                            line.split(
                                "=",
                                1,
                            )[1]
                            .strip()
                            .strip('"\'')
                        )

        except Exception:
            pass

    return ""


# ==========================================
# NVIDIA MODELS
# ==========================================

def get_all_nvidia_models():

    return [
        "meta/llama-3.3-70b-instruct",
        "meta/llama-3.1-70b-instruct",
        "meta/llama-3.1-8b-instruct",
        "meta/llama-3.2-11b-vision-instruct",
        "meta/llama-3.2-90b-vision-instruct",
        "nvidia/llama-3.3-nemotron-super-49b-v1",
        "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/nemotron-nano-12b-v2-vl",
        "nvidia/nvidia-nemotron-nano-9b-v2",
        "openai/gpt-oss-120b",
        "google/gemma-4-31b-it",
    ]


# ==========================================
# SKILL FEEDBACK
# ==========================================

def record_skill_feedback(
    skill_name: str,
    success: bool,
):

    conn = get_db_connection()

    if not conn:
        return

    cur = None

    try:

        cur = conn.cursor()

        if success:

            cur.execute(
                """
                INSERT INTO skill_performance_metrics
                    (
                        skill_name,
                        success_count,
                        failure_count,
                        last_score
                    )
                VALUES
                    (%s, 1, 0, 1.0)
                ON CONFLICT (skill_name)
                DO UPDATE SET
                    success_count =
                        skill_performance_metrics.success_count + 1,
                    last_score =
                        LEAST(
                            2.0,
                            skill_performance_metrics.last_score + 0.1
                        );
                """,
                (
                    skill_name,
                ),
            )

        else:

            cur.execute(
                """
                INSERT INTO skill_performance_metrics
                    (
                        skill_name,
                        success_count,
                        failure_count,
                        last_score
                    )
                VALUES
                    (%s, 0, 1, 0.5)
                ON CONFLICT (skill_name)
                DO UPDATE SET
                    failure_count =
                        skill_performance_metrics.failure_count + 1,
                    last_score =
                        GREATEST(
                            0.1,
                            skill_performance_metrics.last_score - 0.2
                        );
                """,
                (
                    skill_name,
                ),
            )

        conn.commit()

    except Exception as exc:

        print(
            f"[SkillFeedback Error]: {exc}"
        )

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
# SKILLS INDEX
# ==========================================

def _build_skills_index():

    index = []

    dirs_to_scan = [
        SKILLS_DIR
    ]

    fallback_dir = os.path.join(
        WORKSPACE_DIR,
        "skills",
    )

    if (
        os.path.exists(fallback_dir)
        and fallback_dir not in dirs_to_scan
    ):
        dirs_to_scan.append(
            fallback_dir
        )

    skill_scores = {}

    try:

        conn = get_db_connection()

        if conn:

            cur = conn.cursor()

            cur.execute(
                """
                SELECT skill_name, last_score
                FROM skill_performance_metrics;
                """
            )

            for row in cur.fetchall():
                skill_scores[row[0]] = float(
                    row[1]
                )

            cur.close()
            conn.close()

    except Exception:
        pass

    for directory in dirs_to_scan:

        if not os.path.exists(directory):
            continue

        try:
            entries = os.listdir(directory)
        except Exception:
            continue

        for filename in entries:

            path = os.path.join(
                directory,
                filename,
            )

            if not os.path.isfile(path):
                continue

            try:

                if filename.endswith(".json"):

                    with open(
                        path,
                        "r",
                        encoding="utf-8",
                    ) as file:

                        data = json.load(file)

                    name = data.get(
                        "name",
                        filename,
                    )

                    score = skill_scores.get(
                        name,
                        1.0,
                    )

                    index.append(
                        {
                            "name": name,
                            "description": data.get(
                                "description",
                                "",
                            ),
                            "prompt": data.get(
                                "prompt",
                                "",
                            ),
                            "command": data.get(
                                "command",
                                filename,
                            ),
                            "score": score,
                        }
                    )

                elif filename.endswith(
                    (
                        ".txt",
                        ".md",
                    )
                ):

                    with open(
                        path,
                        "r",
                        encoding="utf-8",
                    ) as file:

                        content = file.read()

                    lines = content.split(
                        "\n",
                        2,
                    )

                    name = (
                        lines[0].strip()
                        if lines
                        else filename
                    )

                    score = skill_scores.get(
                        name,
                        1.0,
                    )

                    index.append(
                        {
                            "name": name,
                            "description": "Document",
                            "prompt": content,
                            "command": filename,
                            "score": score,
                        }
                    )

            except Exception:
                continue

    index.sort(
        key=lambda item: item.get(
            "score",
            1.0,
        ),
        reverse=True,
    )

    return index


# ==========================================
# ROUTES STATIQUES
# ==========================================

@app.route("/")
def index():
    return send_from_directory(
        WORKSPACE_DIR,
        "index.html",
    )


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(
        WORKSPACE_DIR,
        filename,
    )


# ==========================================
# API CONFIG
# ==========================================

@app.route(
    "/api/config",
    methods=["GET"],
)
def get_config():

    providers = [
        {
            "id": "groq",
            "name": "Groq",
            "configured": bool(
                get_api_key(
                    "GROQ_API_KEY"
                )
            ),
        },
        {
            "id": "nvidia",
            "name": "NVIDIA NIM",
            "configured": bool(
                get_api_key(
                    "NVIDIA_API_KEY"
                )
            ),
        },
        {
            "id": "gemini",
            "name": "Google Gemini",
            "configured": bool(
                get_api_key(
                    "GEMINI_API_KEY"
                )
            ),
        },
        {
            "id": "openrouter",
            "name": "OpenRouter",
            "configured": bool(
                get_api_key(
                    "OPENROUTER_API_KEY"
                )
            ),
        },
    ]

    models = {
        "groq": [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.6-27b",
        ],
        "nvidia": get_all_nvidia_models(),
        "gemini": [
            "gemini-3.6-flash",
            "gemini-1.5-pro-preview",
        ],
        "openrouter": [
            "openrouter/auto",
            "openai/gpt-oss-120b",
            "anthropic/claude-4-sonnet",
        ],
    }

    skills = _build_skills_index()

    return jsonify(
        {
            "providers": providers,
            "models": models,
            "skills_count": len(skills),
            "skills": skills,
        }
    )


# ==========================================
# FILES
# ==========================================

@app.route(
    "/api/files",
    methods=["GET"],
)
def list_files():

    files = []

    for directory in [
        FILES_DIR,
        GENERATED_DIR,
        WORKSPACE_DIR,
    ]:

        if not os.path.exists(directory):
            continue

        try:
            entries = os.listdir(directory)
        except Exception:
            continue

        for filename in entries:

            filepath = os.path.join(
                directory,
                filename,
            )

            if (
                os.path.isfile(filepath)
                and not filename.startswith(".")
            ):

                files.append(
                    {
                        "name": filename,
                        "size": os.path.getsize(
                            filepath
                        ),
                        "extension": os.path.splitext(
                            filename
                        )[1].lower(),
                    }
                )

    return jsonify(
        {
            "files": files
        }
    )


@app.route(
    "/api/download/<path:filename>",
    methods=["GET"],
)
def download_file(filename):

    safe_name = secure_filename(
        filename
    )

    if not safe_name:
        return jsonify(
            {
                "error": "Nom de fichier invalide"
            }
        ), 400

    for directory in [
        FILES_DIR,
        GENERATED_DIR,
        WORKSPACE_DIR,
    ]:

        filepath = os.path.join(
            directory,
            safe_name,
        )

        if os.path.isfile(filepath):

            return send_file(
                filepath,
                as_attachment=True,
            )

    return jsonify(
        {
            "error": "Fichier introuvable"
        }
    ), 404


@app.route(
    "/api/upload",
    methods=["POST"],
)
def upload_file():

    if "file" not in request.files:
        return jsonify(
            {
                "error": "Aucun fichier fourni"
            }
        ), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify(
            {
                "error": "Nom de fichier manquant"
            }
        ), 400

    filename = secure_filename(
        file.filename
    )

    if not filename:
        return jsonify(
            {
                "error": "Nom de fichier invalide"
            }
        ), 400

    filepath = os.path.join(
        FILES_DIR,
        filename,
    )

    file.save(filepath)

    extracted_files = []

    if filename.lower().endswith(".zip"):

        try:

            with zipfile.ZipFile(
                filepath,
                "r",
            ) as zip_ref:

                # Validation anti path traversal avant extraction.
                base_dir = os.path.abspath(
                    FILES_DIR
                )

                for member in zip_ref.infolist():

                    target_path = os.path.abspath(
                        os.path.join(
                            base_dir,
                            member.filename,
                        )
                    )

                    if not (
                        target_path == base_dir
                        or target_path.startswith(
                            base_dir + os.sep
                        )
                    ):
                        raise ValueError(
                            "Archive ZIP contenant "
                            "un chemin dangereux."
                        )

                zip_ref.extractall(
                    FILES_DIR
                )

                extracted_files = (
                    zip_ref.namelist()
                )

        except Exception as zip_err:

            print(
                "[ZipExtractWarning] "
                f"Impossible de décompresser "
                f"{filename}: {zip_err}"
            )

            return jsonify(
                {
                    "status": "success",
                    "filename": filename,
                    "size": os.path.getsize(
                        filepath
                    ),
                    "extracted_contents": [],
                    "zip_warning": str(zip_err),
                }
            )

    return jsonify(
        {
            "status": "success",
            "filename": filename,
            "size": os.path.getsize(
                filepath
            ),
            "extracted_contents": extracted_files,
        }
    )


# ==========================================
# WEB AGENT
# ==========================================

@app.route(
    "/api/agent/web",
    methods=["POST"],
)
def api_web():

    data = request.get_json(
        silent=True
    ) or {}

    query = data.get(
        "query",
        "Tendances SaaS et CRM IA 2026",
    )

    return jsonify(
        web_agent_instance.run_pipeline(
            query
        )
    )


@app.route(
    "/api/agent/web-sync",
    methods=["POST"],
)
def api_trigger_web_sync():

    data = request.get_json(
        silent=True
    ) or {}

    query = data.get(
        "query",
        "CEO SaaS CRM automatisation",
    )

    result = web_agent_instance.run_pipeline(
        query
    )

    return jsonify(result)


# ==========================================
# HERMES RUNTIME
# ==========================================

@app.route(
    "/api/hermes/runtime",
    methods=["GET"],
)
def api_hermes_runtime():

    runtime = hermes.runtime_status()

    trace_id = (
        hermes.create_trace_id()
    )

    return jsonify(
        {
            "hermes_state": runtime["status"],
            "security_guard": runtime[
                "security_guard_active"
            ],
            "tool_count": runtime[
                "tool_count"
            ],
            "tools": [
                {
                    "name": tool["name"],
                    "risk": tool["risk_level"],
                }
                for tool in runtime["tools"]
            ],
            "provider": runtime["provider"],
            "model": runtime["model"],
            "trace_id": trace_id,
        }
    )


# ==========================================
# HERMES GOAP + SECURITY
# ==========================================

@app.route(
    "/api/hermes/goap-execute",
    methods=["POST"],
)
def api_hermes_goap():

    data = request.get_json(
        silent=True
    ) or {}

    user_objective = data.get("objective") or data.get("query") or "Analyse globale de la Matrisse 2026"

    plan = hermes.goap_planner(
        user_objective
    )

    # IMPORTANT :
    # Aucun override client ne peut contourner
    # les règles de risque Hermes.
    execution_result = hermes.dispatch_parallel(
        plan
    )

    log_mission_to_neon(
        trace_id=execution_result.get(
            "trace_id",
            "BEK-TRC-UNKNOWN",
        ),
        objective=user_objective,
        plan=plan,
        execution=execution_result,
    )

    return jsonify(
        {
            "objective": user_objective,
            "goap_plan": plan,
            "execution": execution_result,
        }
    )


# ==========================================
# OBSERVABILITÉ
# ==========================================

@app.route(
    "/api/matrix/observability-logs",
    methods=["GET"],
)
def get_observability_logs():

    conn = get_db_connection()

    if not conn:
        return jsonify(
            {
                "status": "error",
                "message": (
                    "Neon DB non connectée"
                ),
            }
        )

    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                trace_id,
                objective,
                status,
                execution_ms,
                created_at
            FROM bek_mission_logs
            ORDER BY created_at DESC
            LIMIT 10;
            """
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        logs = [
            dict(
                zip(
                    columns,
                    row,
                )
            )
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT
                job_id,
                task_name,
                status,
                created_at
            FROM system_jobs
            ORDER BY created_at DESC
            LIMIT 5;
            """
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        jobs = [
            dict(
                zip(
                    columns,
                    row,
                )
            )
            for row in cur.fetchall()
        ]

        return jsonify(
            {
                "status": "success",
                "mission_logs": logs,
                "system_jobs": jobs,
            }
        )

    except Exception as exc:

        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        )

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
# CRM STATS
# ==========================================

@app.route(
    "/api/crm/stats",
    methods=["GET"],
)
def get_crm_stats():

    conn = get_db_connection()

    if not conn:
        return jsonify(
            {
                "num_contacts": 0,
                "num_companies": 0,
                "num_opportunities": 0,
                "total_amount": 0.0,
                "status": "demo",
            }
        )

    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, name, email, phone
            FROM contacts;
            """
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        contacts = [
            dict(
                zip(
                    columns,
                    row,
                )
            )
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT id, name, created_at
            FROM companies;
            """
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        companies = [
            dict(
                zip(
                    columns,
                    row,
                )
            )
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT
                id,
                name,
                amount,
                currency,
                stage
            FROM opportunities;
            """
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        opportunities = [
            dict(
                zip(
                    columns,
                    row,
                )
            )
            for row in cur.fetchall()
        ]

        total_amount = sum(
            float(
                opportunity.get(
                    "amount",
                    0,
                )
                or 0
            )
            for opportunity in opportunities
        )

        return jsonify(
            {
                "num_contacts": len(
                    contacts
                ),
                "num_companies": len(
                    companies
                ),
                "num_opportunities": len(
                    opportunities
                ),
                "total_amount": total_amount,
                "contacts": contacts,
                "companies": companies,
                "opportunities": opportunities,
                "status": "connected",
            }
        )

    except Exception as exc:

        return jsonify(
            {
                "error": str(exc),
                "status": "error",
            }
        )

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
# CRM SQL
# ==========================================

@app.route(
    "/api/crm/execute",
    methods=["POST"],
)
def execute_crm_direct():

    data = request.get_json(
        silent=True
    ) or {}

    sql = data.get(
        "sql",
        "",
    )

    if not isinstance(sql, str):
        return jsonify(
            {
                "error": "SQL invalide"
            }
        ), 400

    sql = sql.strip()

    if not sql:
        return jsonify(
            {
                "error": "SQL requis"
            }
        ), 400

    return jsonify(
        execute_database_sql(
            sql
        )
    )


# ==========================================
# MATRIX SPAWN
# ==========================================

@app.route(
    "/api/matrix/spawn",
    methods=["POST"],
)
def api_spawn_sub_crm():

    data = request.get_json(
        silent=True
    ) or {}

    niche_name = data.get(
        "niche_name",
        "",
    )

    cahier_des_charges = data.get(
        "cahier_des_charges",
        "Autonomie complète selon les objectifs assignés.",
    )

    objectives = data.get(
        "objectives",
        [
            "Optimisation",
            "Automatisation",
            "Auto-correction",
        ],
    )

    parent_id = data.get(
        "parent_id",
        None,
    )

    custom_env = data.get(
        "custom_env",
        None,
    )

    if not isinstance(
        niche_name,
        str,
    ) or not niche_name.strip():

        return jsonify(
            {
                "error": (
                    "Le nom de la niche "
                    "ou du domaine est requis."
                )
            }
        ), 400

    result = SubCRMEngine.spawn_sub_crm(
        niche_name=niche_name.strip(),
        cahier_des_charges=cahier_des_charges,
        objectives=objectives,
        parent_id=parent_id,
        custom_env=custom_env,
    )

    return jsonify(result)


# ==========================================
# MATRIX SPAWN ALIVE
# ==========================================

@app.route(
    "/api/matrix/spawn-alive",
    methods=["POST"],
)
def api_spawn_alive_sub_crm():

    data = request.get_json(
        silent=True
    ) or {}

    niche_name = data.get(
        "niche_name",
        "",
    )

    cahier_des_charges = data.get(
        "cahier_des_charges",
        (
            "Opérationnel, autonome, "
            "multi-rubriques et auto-réparateur."
        ),
    )

    objectives = data.get(
        "objectives",
        [
            "Création Interface Multi-Vues",
            "Comptes Utilisateurs",
            "Rentabilité & Automatisation sans limites",
        ],
    )

    parent_id = data.get(
        "parent_id",
        None,
    )

    custom_env = data.get(
        "custom_env",
        None,
    )

    if not isinstance(
        niche_name,
        str,
    ) or not niche_name.strip():

        return jsonify(
            {
                "error": (
                    "Le nom de la niche est requis."
                )
            }
        ), 400

    result = (
        SubCRMEngineAdvanced.spawn_fully_alive_sub_crm(
            niche_name=niche_name.strip(),
            cahier_des_charges=cahier_des_charges,
            objectives=objectives,
            parent_id=parent_id,
            custom_env=custom_env,
        )
    )

    return jsonify(result)


# ==========================================
# MATRIX BEK ACTION
# ==========================================

@app.route(
    "/api/matrix/bek-action",
    methods=["POST"],
)
def api_matrix_bek_action():

    data = request.get_json(
        silent=True
    ) or {}

    action = data.get(
        "action",
        "process_data",
    )

    if action == "process_data":

        time.sleep(1.5)

        return jsonify(
            {
                "status": "success",
                "new_sequences": 8492,
                "active_agents": 5,
                "logs": [
                    (
                        ">_ Swarm-Core : "
                        "Lancement de l'analyse "
                        "des flux CRM..."
                    ),
                    (
                        ">_ Agent Web Ultra-Puissant : "
                        "Scan et normalisation "
                        "des flux... OK"
                    ),
                    (
                        ">_ Agent Meta-Cortex : "
                        "Optimisation des pipelines "
                        "de vente..."
                    ),
                    (
                        ">_ Opération terminée. "
                        "Données synchronisées "
                        "avec Neon DB."
                    ),
                ],
            }
        )

    return jsonify(
        {
            "error": "Action inconnue"
        }
    ), 400


# ==========================================
# CHAT PRINCIPAL
# ==========================================

@app.route(
    "/api/chat",
    methods=["POST"],
)
def chat():

    data = request.get_json(
        silent=True
    ) or {}

    messages = data.get(
        "messages",
        [],
    )

    provider = data.get(
        "provider",
        "groq",
    )

    model = data.get(
        "model",
        "openai/gpt-oss-120b",
    )

    use_memory = data.get(
        "use_memory",
        True,
    )

    use_reflection = data.get(
        "use_reflection",
        True,
    )

    hermes.set_provider_context(
        provider,
        model,
    )

    if not isinstance(
        messages,
        list,
    ):
        return jsonify(
            {
                "error": (
                    "messages doit être une liste."
                )
            }
        ), 400

    last_user_msg = ""

    for message in reversed(
        messages
    ):

        if not isinstance(
            message,
            dict,
        ):
            continue

        if message.get(
            "role"
        ) != "user":
            continue

        content = message.get(
            "content"
        )

        if isinstance(
            content,
            str,
        ):

            last_user_msg = content

        elif isinstance(
            content,
            list,
        ):

            parts = []

            for item in content:

                if (
                    isinstance(
                        item,
                        dict,
                    )
                    and isinstance(
                        item.get("text"),
                        str,
                    )
                ):
                    parts.append(
                        item["text"]
                    )

            last_user_msg = " ".join(
                parts
            )

        break

    # ======================================
    # PROVIDERS
    # ======================================

    if provider == "nvidia":

        api_key = (
            get_api_key(model)
            or get_api_key(
                "NVIDIA_API_KEY"
            )
        )

        api_url = (
            "https://integrate.api.nvidia.com/"
            "v1/chat/completions"
        )

    elif provider == "gemini":

        api_key = get_api_key(
            "GEMINI_API_KEY"
        )

        api_url = (
            "https://generativelanguage.googleapis.com/"
            "v1beta/openai/chat/completions"
        )

    elif provider == "openrouter":

        api_key = get_api_key(
            "OPENROUTER_API_KEY"
        )

        api_url = (
            "https://openrouter.ai/"
            "api/v1/chat/completions"
        )

    else:

        api_key = get_api_key(
            "GROQ_API_KEY"
        )

        api_url = (
            "https://api.groq.com/"
            "openai/v1/chat/completions"
        )

    # ======================================
    # INTROSPECTION LOCALE
    # ======================================

    normalized_message = (
        last_user_msg.lower().strip()
        if last_user_msg
        else ""
    )

    introspection_requested = bool(
        normalized_message
        and (
            "introspection runtime"
            in normalized_message
            or "état runtime réel"
            in normalized_message
            or "registre d'outils"
            in normalized_message
        )
    )

    def generate_local_runtime_response():

        runtime = hermes.runtime_status()

        payload = {
            "hermes_state": runtime[
                "status"
            ],
            "security_guard": runtime[
                "security_guard_active"
            ],
            "tools": [
                {
                    "name": tool["name"],
                    "risk": tool["risk_level"],
                }
                for tool in runtime["tools"]
            ],
            "provider": runtime[
                "provider"
            ],
            "model": runtime[
                "model"
            ],
            "trace_id": (
                hermes.create_trace_id()
            ),
        }

        yield (
            "data: "
            + json.dumps(
                {
                    "chunk": json.dumps(
                        payload,
                        ensure_ascii=False,
                    )
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )

        yield (
            "data: "
            + json.dumps(
                {
                    "done": True
                }
            )
            + "\n\n"
        )

    if introspection_requested:

        return Response(
            generate_local_runtime_response(),
            mimetype="text/event-stream",
        )

    # ======================================
    # PROXY LLM
    # ======================================

    def generate_proxy():

        if not api_key:

            yield (
                "data: "
                + json.dumps(
                    {
                        "error": (
                            f"Clé API manquante "
                            f"pour {provider}."
                        )
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

            return

        try:

            sync_and_persist_global_state(
                commit_message=(
                    "BEK-v15.2 Auto-Sync Direct Action"
                )
            )

        except Exception as sync_err:

            print(
                f"[SyncWarning] {sync_err}"
            )

        dynamic_context = (
            f"{BEK_GOLDEN_RULES}\n\n"
        )

        # ==================================
        # FICHIERS
        # ==================================

        try:

            if os.path.exists(
                FILES_DIR
            ):

                for filename in os.listdir(
                    FILES_DIR
                ):

                    filepath = os.path.join(
                        FILES_DIR,
                        filename,
                    )

                    if os.path.isfile(
                        filepath
                    ):

                        dynamic_context += (
                            f"- Fichier : "
                            f"{filename}\n"
                        )

        except Exception:
            pass

        # ==================================
        # CRM CONTEXT
        # ==================================

        real_crm_context = (
            "\n[SCHÉMA CRM STRICT DE NEON DB]\n"
            "Tables autorisées : "
            "'companies', 'contacts', "
            "'opportunities'.\n"
        )

        conn = None
        cur = None

        try:

            conn = get_db_connection()

            if conn:

                cur = conn.cursor()

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM companies;
                    """
                )

                comp_count = (
                    cur.fetchone()[0]
                )

                real_crm_context += (
                    "- Entreprises (companies) : "
                    f"{comp_count}\n"
                )

        except Exception:
            pass

        finally:

            try:
                if cur:
                    cur.close()
            except Exception:
                pass

            try:
                if conn:
                    conn.close()
            except Exception:
                pass

        dynamic_context += (
            real_crm_context
        )

        # ==================================
        # MEMORY
        # ==================================

        if (
            use_memory
            and last_user_msg
        ):

            try:

                memory_results = (
                    search_memory(
                        last_user_msg
                    )
                )

                if memory_results:

                    dynamic_context += (
                        "CTX-MEMOIRE:"
                        f"{memory_results}\n"
                    )

            except Exception:
                pass

        # ==================================
        # SWARM
        # ==================================

        if any(
            keyword in normalized_message
            for keyword in [
                "essaim",
                "swarm",
                "analyse complète",
                "architecture swarm",
            ]
        ):

            try:

                swarm_result = (
                    asyncio.run(
                        run_bek_swarm_sync(
                            last_user_msg,
                            api_key,
                            provider,
                            model,
                        )
                    )
                )

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "chunk": (
                                f"{swarm_result}\n"
                            )
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "done": True
                        }
                    )
                    + "\n\n"
                )

                return

            except Exception as exc:

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "chunk": (
                                "Erreur Swarm-Core : "
                                f"{exc}\n"
                            )
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                return

        # ==================================
        # PROMPT D'ACTION
        # ==================================

        action_prompt = (
            "Tu es BEK-v15.2, une IA hybride avancée "
            "et l'Exécuteur de la Matrisse. "
            "RÈGLE 1 (Social) : Si l'utilisateur te "
            "salue (ex: 'bjr', 'salut', 'cv') ou discute "
            "de façon informelle, réponds naturellement, "
            "brièvement et poliment, SANS JAMAIS "
            "mentionner tes protocoles, le CRM ou Neon DB. "
            "RÈGLE 2 (Technique) : Si l'utilisateur "
            "demande du code, une création ou interroge "
            "les données, active le mode Exécuteur : "
            "sois direct, chirurgical, fournis le code "
            "pur sans blabla d'agent."
        )

        clean_messages = []

        for message in messages[-6:]:

            if not isinstance(
                message,
                dict,
            ):
                continue

            role = message.get(
                "role"
            )

            if role not in [
                "user",
                "assistant",
            ]:
                continue

            clean_messages.append(
                {
                    "role": role,
                    "content": message.get(
                        "content"
                    ),
                }
            )

        exec_messages = [
            {
                "role": "system",
                "content": (
                    f"{action_prompt}\n"
                    f"Contexte:\n"
                    f"{dynamic_context}"
                ).strip(),
            }
        ] + clean_messages

        payload = {
            "model": model,
            "messages": exec_messages,
            "temperature": 0.2,
            "max_tokens": 4096,
            "stream": False,
        }

        headers = {
            "Authorization": (
                f"Bearer {api_key}"
            ),
            "Content-Type": (
                "application/json"
            ),
        }

        # ==================================
        # APPEL PROVIDER
        # ==================================

        try:

            resp = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=90,
            )

            if resp.status_code != 200:

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "error": (
                                f"Erreur API "
                                f"({resp.status_code}) : "
                                f"{resp.text}"
                            )
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                return

            resp_json = resp.json()

            choices = resp_json.get(
                "choices",
                [],
            )

            if not choices:

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "error": (
                                "Réponse provider "
                                "sans choix."
                            )
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                return

            message_data = (
                choices[0].get(
                    "message",
                    {}
                )
            )

            llm_text = (
                message_data.get(
                    "content",
                    ""
                )
                or ""
            ).strip()

            yield (
                "data: "
                + json.dumps(
                    {
                        "chunk": llm_text
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

            yield (
                "data: "
                + json.dumps(
                    {
                        "done": True
                    }
                )
                + "\n\n"
            )

            # ==================================
            # MEMORY SAVE
            # ==================================

            if (
                use_memory
                and last_user_msg
                and llm_text
            ):

                try:

                    save_to_memory(
                        last_user_msg,
                        llm_text,
                    )

                except Exception:
                    pass

        except Exception as exc:

            yield (
                "data: "
                + json.dumps(
                    {
                        "error": str(exc)
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

    return Response(
        generate_proxy(),
        mimetype="text/event-stream",
    )


# ==========================================
# START SERVER
# ==========================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            8765,
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True,
    )


Oui. Étape suivante : on verrouille app.py sans casser les fonctions existantes.

J’ai conservé l’architecture actuelle, mais corrigé les points dangereux/importants : authentification optionnelle de l’endpoint SQL, CORS configurable, debug=False par défaut, suppression du token GitHub dans l’URL remote, validation ZIP renforcée, meilleure gestion des erreurs, correction du choix de clé NVIDIA, initialisation plus propre des tables et prévention de quelques plantages silencieux.

Voici le fichier app.py complet, prêt à remplacer l’ancien :

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

# CORS configurable.
# Par défaut : localhost uniquement.
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
    Convertit quelques types PostgreSQL/Python
    non directement sérialisables en JSON.
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
    Récupération sécurisée d'une clé API.

    Priorité :
    1. variable d'environnement
    2. env.txt
    3. .env
    """

    if not isinstance(
        key_name,
        str,
    ):
        return ""

    value = os.environ.get(
        key_name,
        "",
    )

    if value:
        return value.strip(
            "\"' \r\n"
        )

    for env_path in [
        os.path.join(
            WORKSPACE_DIR,
            "env.txt",
        ),
        os.path.join(
            WORKSPACE_DIR,
            ".env",
        ),
    ]:

        if not os.path.isfile(
            env_path
        ):
            continue

        try:

            with open(
                env_path,
                "r",
                encoding="utf-8-sig",
                errors="ignore",
            ) as file:

                for raw_line in file:

                    line = raw_line.strip()

                    if (
                        not line
                        or line.startswith("#")
                    ):
                        continue

                    if not line.startswith(
                        key_name + "="
                    ):
                        continue

                    return (
                        line.split(
                            "=",
                            1,
                        )[1]
                        .strip()
                        .strip("\"'")
                    )

        except Exception as exc:

            logger.warning(
                "Lecture de %s impossible : %s",
                env_path,
                exc,
            )

    return ""


def get_admin_api_key():
    return get_api_key(
        "BEK_ADMIN_API_KEY"
    )


def check_admin_auth():
    """
    Authentification des endpoints administratifs.

    Si BEK_ADMIN_API_KEY n'est pas configurée,
    les endpoints restent utilisables localement.

    Dès qu'une clé est configurée, elle devient obligatoire.
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

            # Ne jamais écrire le token dans l'URL
            # du remote Git.
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

                if commit_result.returncode != 0:

                    stdout = (
                        commit_result.stdout
                        or ""
                    ).strip()

                    stderr = (
                        commit_result.stderr
                        or ""
                    ).strip()

                    # Rien à commit est normal.
                    if (
                        "nothing to commit"
                        not in stdout.lower()
                        and "nothing to commit"
                        not in stderr.lower()
                    ):
                        logger.warning(
                            "[SyncManager] Commit Git : %s",
                            stderr or stdout,
                        )

                # Authentification temporaire uniquement
                # pendant git push.
                auth = base64.b64encode(
                    f"x-access-token:{gh_token}".encode(
                        "utf-8"
                    )
                ).decode(
                    "ascii"
                )

                git_env = os.environ.copy()

                git_env[
                    "GIT_CONFIG_COUNT"
                ] = "1"

                git_env[
                    "GIT_CONFIG_KEY_0"
                ] = "http.extraheader"

                git_env[
                    "GIT_CONFIG_VALUE_0"
                ] = (
                    f"AUTHORIZATION: basic {auth}"
                )

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

                    logger.info(
                        "[SyncManager] "
                        "Synchronisation GitHub réussie."
                    )

                else:

                    logger.warning(
                        "[SyncManager] "
                        "Git push échoué : %s",
                        (
                            push_result.stderr
                            or push_result.stdout
                        ).strip(),
                    )

        except subprocess.TimeoutExpired:

            logger.warning(
                "[SyncManager] Timeout GitHub."
            )

        except Exception as exc:

            logger.error(
                "[SyncManager] Erreur GitHub : %s",
                exc,
            )

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
                    updated_at TIMESTAMP
                        DEFAULT CURRENT_TIMESTAMP
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
                    created_at TIMESTAMP WITH TIME ZONE
                        DEFAULT CURRENT_TIMESTAMP
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
                INSERT INTO bek_system_state
                    (
                        state_key,
                        state_data
                    )
                VALUES
                    (
                        'global_prompt_v15.2',
                        %s
                    )
                ON CONFLICT (state_key)
                DO UPDATE SET
                    state_data = EXCLUDED.state_data,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    BEK_GOLDEN_RULES,
                ),
            )

            conn.commit()

            logger.info(
                "[SyncManager] État Neon persisté."
            )

    except Exception as exc:

        logger.error(
            "[SyncManager] Erreur Neon : %s",
            exc,
        )

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
            if conn:
                conn.close()
        except Exception:
            pass

    # --------------------------------------
    # PINECONE
    # --------------------------------------

    try:

        saved = save_to_memory(
            "BEK_SYSTEM_SYNC_STATE",
            BEK_GOLDEN_RULES,
        )

        if saved:
            logger.info(
                "[SyncManager] "
                "Mémoire vectorielle synchronisée."
            )
        else:
            logger.warning(
                "[SyncManager] "
                "Mémoire vectorielle non sauvegardée."
            )

    except Exception as exc:

        logger.error(
            "[SyncManager] Erreur mémoire : %s",
            exc,
        )


# ==========================================
# LOG MISSION HERMES
# ==========================================

def log_mission_to_neon(
    trace_id,
    objective,
    plan,
    execution,
):

    conn = None
    cur = None

    try:

        conn = get_db_connection()

        if not conn:
            return

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO bek_mission_logs
                (
                    trace_id,
                    objective,
                    goap_plan,
                    execution_results,
                    status,
                    execution_ms
                )
            VALUES
                (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (trace_id)
            DO NOTHING;
            """,
            (
                trace_id,
                objective,
                json.dumps(
                    plan,
                    ensure_ascii=False,
                    default=str,
                ),
                json.dumps(
                    execution.get(
                        "results",
                        {},
                    ),
                    ensure_ascii=False,
                    default=str,
                ),
                execution.get(
                    "status",
                    "UNKNOWN",
                ),
                execution.get(
                    "execution_ms",
                    0,
                ),
            ),
        )

        conn.commit()

    except Exception as exc:

        logger.error(
            "[Neon DB Log Error] %s",
            exc,
        )

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
            if conn:
                conn.close()
        except Exception:
            pass


# ==========================================
# SQL SECURITY
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


def validate_sql_request(
    sql_query: str
):
    """
    Contrôle complémentaire de l'endpoint CRM SQL.

    Le SecurityGuard Hermes reste la couche de sécurité
    principale pour les actions Hermes.

    Ici on empêche surtout les opérations PostgreSQL
    particulièrement dangereuses pour une API applicative.
    """

    if not isinstance(
        sql_query,
        str,
    ):
        return False, "SQL invalide."

    sql = sql_query.strip()

    if not sql:
        return False, "SQL requis."

    if len(sql) > 100_000:
        return False, "SQL trop volumineux."

    normalized = re.sub(
        r"\s+",
        " ",
        sql.lower(),
    )

    for pattern in SQL_BLOCKED_PATTERNS:

        if re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        ):
            return (
                False,
                "Opération SQL interdite par la politique BEK.",
            )

    return True, ""


# ==========================================
# EXÉCUTION SQL
# ==========================================

def execute_database_sql(
    sql_query: str
) -> dict:

    valid, error_message = (
        validate_sql_request(
            sql_query
        )
    )

    if not valid:

        return {
            "status": "error",
            "message": error_message,
        }

    conn = get_db_connection()

    if not conn:

        return {
            "status": "error",
            "message": (
                "Connexion Neon DB indisponible."
            ),
        }

    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            sql_query
        )

        if cur.description:

            columns = [
                desc[0]
                for desc in cur.description
            ]

            rows = cur.fetchall()

            results = [
                {
                    column: json_safe(value)
                    for column, value in zip(
                        columns,
                        row,
                    )
                }
                for row in rows
            ]

            return {
                "status": "success",
                "type": "select",
                "data": results,
                "count": len(results),
            }

        conn.commit()

        affected = cur.rowcount

        return {
            "status": "success",
            "type": "mutation",
            "affected_rows": affected,
        }

    except Exception as exc:

        try:
            conn.rollback()
        except Exception:
            pass

        return {
            "status": "error",
            "message": str(exc),
        }

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
                    parent_id UUID
                        REFERENCES matrix_sub_crms(id)
                        ON DELETE SET NULL,
                    niche_name TEXT NOT NULL,
                    specifications JSONB NOT NULL,
                    environment_vars JSONB NOT NULL,
                    active_tools JSONB NOT NULL,
                    cahier_des_charges TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP
                        DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            conn.commit()

            return True

        except Exception as exc:

            logger.error(
                "[SubCRMEngine] "
                "Erreur schéma : %s",
                exc,
            )

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
    def spawn_sub_crm(
        niche_name: str,
        cahier_des_charges: str,
        objectives: list,
        parent_id=None,
        custom_env=None,
    ):

        if not SubCRMEngine.initialize_matrix_schema():

            return {
                "status": "error",
                "message": (
                    "Impossible d'initialiser "
                    "matrix_sub_crms."
                ),
            }

        sub_crm_id = str(
            uuid.uuid4()
        )

        next_gen_tools = [
            {
                "tool": "LangGraph Advanced Swarm-Core v15.2",
                "mode": "autonomous_reflection",
            },
            {
                "tool": "Meta-Cortex Grounding & Reflexion Engine",
                "mode": "real_time_verification",
            },
            {
                "tool": "Universal External AI Bridge",
                "mode": "dynamic_api_relay",
            },
            {
                "tool": "Secure Sandbox Terminal Executor",
                "mode": "isolated_code_execution",
            },
        ]

        environment_payload = (
            custom_env
            if isinstance(
                custom_env,
                dict,
            )
            else {
                "RUNTIME_ENV": (
                    "production_matrix_node"
                ),
                "AI_AUTONOMY_LEVEL": (
                    "maximum"
                ),
                "SELF_HEALING": "enabled",
            }
        )

        specifications = {
            "objectives": objectives,
            "architecture": (
                "Python/Flask + Neon Polymorphic Layer"
            ),
            "generation": (
                "Next-Gen Ultra-Powerful Node"
            ),
        }

        conn = get_db_connection()

        if not conn:

            return {
                "status": "error",
                "message": (
                    "Connexion Neon DB indisponible."
                ),
            }

        cur = None

        try:

            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO matrix_sub_crms
                    (
                        id,
                        parent_id,
                        niche_name,
                        specifications,
                        environment_vars,
                        active_tools,
                        cahier_des_charges,
                        status
                    )
                VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'active'
                    )
                RETURNING
                    id,
                    niche_name,
                    created_at;
                """,
                (
                    sub_crm_id,
                    parent_id,
                    niche_name,
                    json.dumps(
                        specifications,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        environment_payload,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        next_gen_tools,
                        ensure_ascii=False,
                    ),
                    cahier_des_charges,
                ),
            )

            row = cur.fetchone()

            conn.commit()

            return {
                "status": "success",
                "sub_crm_id": str(
                    row[0]
                ),
                "niche_name": row[1],
                "created_at": str(
                    row[2]
                ),
                "tools_injected": (
                    next_gen_tools
                ),
                "message": (
                    f"Le sous-CRM '{niche_name}' "
                    "a été instancié."
                ),
            }

        except Exception as exc:

            try:
                conn.rollback()
            except Exception:
                pass

            return {
                "status": "error",
                "message": str(exc),
            }

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
# AUTONOMOUS SUB-CRM
# ==========================================

class AutonomousSubCRMInstance:

    def __init__(
        self,
        sub_crm_id: str,
        niche_name: str,
        cahier_des_charges: str,
    ):

        self.sub_crm_id = sub_crm_id
        self.niche_name = niche_name
        self.cahier_des_charges = (
            cahier_des_charges
        )

    def generate_dynamic_ui_and_tables(
        self
    ) -> dict:

        safe_niche = re.sub(
            r"[^a-zA-Z0-9_]+",
            "_",
            self.niche_name,
        ).strip("_")

        if not safe_niche:
            safe_niche = "niche"

        return {
            "ui_layout": (
                f"Dynamic_Dashboard_{safe_niche}"
            ),
            "tables_created": [
                (
                    f"niche_"
                    f"{self.sub_crm_id[:8]}"
                    "_entities"
                ),
                (
                    f"niche_"
                    f"{self.sub_crm_id[:8]}"
                    "_operations"
                ),
                (
                    f"niche_"
                    f"{self.sub_crm_id[:8]}"
                    "_analytics"
                ),
            ],
            "auth_gateway": (
                "OAuth2 / Multi-Tenant "
                "User Accounts Enabled"
            ),
            "autonomy_mode": (
                "No-Spec / Fully Self-Governing "
                "Agent Execution"
            ),
        }

    def self_heal_and_optimize(
        self
    ) -> dict:

        return {
            "status": "healthy",
            "bugs_detected": 0,
            "auto_patches_applied": 0,
            "performance_boost": (
                "Health verification completed."
            ),
        }


class SubCRMEngineAdvanced(
    SubCRMEngine
):

    @staticmethod
    def spawn_fully_alive_sub_crm(
        niche_name: str,
        cahier_des_charges: str,
        objectives: list,
        parent_id=None,
        custom_env=None,
    ):

        base_spawn = (
            SubCRMEngine.spawn_sub_crm(
                niche_name,
                cahier_des_charges,
                objectives,
                parent_id,
                custom_env,
            )
        )

        if base_spawn.get(
            "status"
        ) != "success":

            return base_spawn

        sub_crm_id = (
            base_spawn["sub_crm_id"]
        )

        instance = (
            AutonomousSubCRMInstance(
                sub_crm_id,
                niche_name,
                cahier_des_charges,
            )
        )

        lifecycle_data = (
            instance.generate_dynamic_ui_and_tables()
        )

        health_check = (
            instance.self_heal_and_optimize()
        )

        return {
            "status": "success",
            "sub_crm_id": sub_crm_id,
            "niche_name": niche_name,
            "lifecycle_environment": (
                lifecycle_data
            ),
            "self_repair_status": (
                health_check
            ),
            "message": (
                f"Le sous-CRM '{niche_name}' "
                "est opérationnel."
            ),
        }


# ==========================================
# NVIDIA MODELS
# ==========================================

def get_all_nvidia_models():

    return [
        "meta/llama-3.3-70b-instruct",
        "meta/llama-3.1-70b-instruct",
        "meta/llama-3.1-8b-instruct",
        "meta/llama-3.2-11b-vision-instruct",
        "meta/llama-3.2-90b-vision-instruct",
        "nvidia/llama-3.3-nemotron-super-49b-v1",
        "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/nemotron-nano-12b-v2-vl",
        "nvidia/nvidia-nemotron-nano-9b-v2",
        "openai/gpt-oss-120b",
        "google/gemma-4-31b-it",
    ]


# ==========================================
# SKILL FEEDBACK
# ==========================================

def record_skill_feedback(
    skill_name: str,
    success: bool,
):

    conn = get_db_connection()

    if not conn:
        return

    cur = None

    try:

        cur = conn.cursor()

        if success:

            cur.execute(
                """
                INSERT INTO skill_performance_metrics
                    (
                        skill_name,
                        success_count,
                        failure_count,
                        last_score
                    )
                VALUES
                    (%s, 1, 0, 1.0)
                ON CONFLICT (skill_name)
                DO UPDATE SET
                    success_count =
                        skill_performance_metrics.success_count + 1,
                    last_score =
                        LEAST(
                            2.0,
                            skill_performance_metrics.last_score + 0.1
                        );
                """,
                (
                    skill_name,
                ),
            )

        else:

            cur.execute(
                """
                INSERT INTO skill_performance_metrics
                    (
                        skill_name,
                        success_count,
                        failure_count,
                        last_score
                    )
                VALUES
                    (%s, 0, 1, 0.5)
                ON CONFLICT (skill_name)
                DO UPDATE SET
                    failure_count =
                        skill_performance_metrics.failure_count + 1,
                    last_score =
                        GREATEST(
                            0.1,
                            skill_performance_metrics.last_score - 0.2
                        );
                """,
                (
                    skill_name,
                ),
            )

        conn.commit()

    except Exception as exc:

        logger.error(
            "[SkillFeedback] %s",
            exc,
        )

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
# SKILLS INDEX
# ==========================================

def _build_skills_index():

    index = []

    dirs_to_scan = [
        SKILLS_DIR
    ]

    fallback_dir = os.path.join(
        WORKSPACE_DIR,
        "skills",
    )

    if (
        os.path.exists(
            fallback_dir
        )
        and fallback_dir not in dirs_to_scan
    ):

        dirs_to_scan.append(
            fallback_dir
        )

    skill_scores = {}

    # --------------------------------------
    # SCORES NEON
    # --------------------------------------

    try:

        conn = get_db_connection()

        if conn:

            cur = conn.cursor()

            cur.execute(
                """
                SELECT
                    skill_name,
                    last_score
                FROM skill_performance_metrics;
                """
            )

            for row in cur.fetchall():

                skill_scores[
                    row[0]
                ] = float(
                    row[1]
                )

            cur.close()
            conn.close()

    except Exception:
        pass

    # --------------------------------------
    # SCAN SKILLS
    # --------------------------------------

    seen_names = set()

    for directory in dirs_to_scan:

        if not os.path.exists(
            directory
        ):
            continue

        try:
            entries = os.listdir(
                directory
            )
        except Exception:
            continue

        for filename in entries:

            path = os.path.join(
                directory,
                filename,
            )

            if not os.path.isfile(
                path
            ):
                continue

            try:

                # JSON
                if filename.endswith(
                    ".json"
                ):

                    with open(
                        path,
                        "r",
                        encoding="utf-8",
                    ) as file:

                        data = json.load(
                            file
                        )

                    if not isinstance(
                        data,
                        dict,
                    ):
                        continue

                    name = data.get(
                        "name",
                        filename,
                    )

                    if name in seen_names:
                        continue

                    seen_names.add(name)

                    score = skill_scores.get(
                        name,
                        1.0,
                    )

                    index.append(
                        {
                            "name": name,
                            "description": data.get(
                                "description",
                                "",
                            ),
                            "prompt": data.get(
                                "prompt",
                                "",
                            ),
                            "command": data.get(
                                "command",
                                filename,
                            ),
                            "score": score,
                        }
                    )

                # TXT / MD
                elif filename.endswith(
                    (
                        ".txt",
                        ".md",
                    )
                ):

                    with open(
                        path,
                        "r",
                        encoding="utf-8",
                        errors="ignore",
                    ) as file:

                        content = file.read()

                    lines = content.split(
                        "\n",
                        2,
                    )

                    name = (
                        lines[0].strip()
                        if lines
                        else filename
                    )

                    if name in seen_names:
                        continue

                    seen_names.add(name)

                    score = skill_scores.get(
                        name,
                        1.0,
                    )

                    index.append(
                        {
                            "name": name,
                            "description": "Document",
                            "prompt": content,
                            "command": filename,
                            "score": score,
                        }
                    )

            except Exception:
                continue

    index.sort(
        key=lambda item: item.get(
            "score",
            1.0,
        ),
        reverse=True,
    )

    return index


# ==========================================
# ROUTES STATIQUES
# ==========================================

@app.route("/")
def index():

    return send_from_directory(
        WORKSPACE_DIR,
        "index.html",
    )


@app.route(
    "/<path:filename>"
)
def serve_static(filename):

    return send_from_directory(
        WORKSPACE_DIR,
        filename,
    )


# ==========================================
# HEALTH
# ==========================================

@app.route(
    "/api/health",
    methods=["GET"],
)
def health():

    runtime = hermes.runtime_status()

    return jsonify(
        {
            "status": "ok",
            "service": "BEK-v15.2 HYBRID",
            "hermes": runtime.get(
                "status",
                "unknown",
            ),
            "security_guard": runtime.get(
                "security_guard_active",
                False,
            ),
        }
    )


# ==========================================
# API CONFIG
# ==========================================

@app.route(
    "/api/config",
    methods=["GET"],
)
def get_config():

    providers = [
        {
            "id": "groq",
            "name": "Groq",
            "configured": bool(
                get_api_key(
                    "GROQ_API_KEY"
                )
            ),
        },
        {
            "id": "nvidia",
            "name": "NVIDIA NIM",
            "configured": bool(
                get_api_key(
                    "NVIDIA_API_KEY"
                )
            ),
        },
        {
            "id": "gemini",
            "name": "Google Gemini",
            "configured": bool(
                get_api_key(
                    "GEMINI_API_KEY"
                )
            ),
        },
        {
            "id": "openrouter",
            "name": "OpenRouter",
            "configured": bool(
                get_api_key(
                    "OPENROUTER_API_KEY"
                )
            ),
        },
    ]

    models = {
        "groq": [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.6-27b",
        ],
        "nvidia": get_all_nvidia_models(),
        "gemini": [
            "gemini-3.6-flash",
            "gemini-1.5-pro-preview",
        ],
        "openrouter": [
            "openrouter/auto",
            "openai/gpt-oss-120b",
            "anthropic/claude-4-sonnet",
        ],
    }

    skills = _build_skills_index()

    return jsonify(
        {
            "providers": providers,
            "models": models,
            "skills_count": len(
                skills
            ),
            "skills": skills,
        }
    )


# ==========================================
# FILES
# ==========================================

@app.route(
    "/api/files",
    methods=["GET"],
)
def list_files():

    files = []

    directories = [
        FILES_DIR,
        GENERATED_DIR,
        WORKSPACE_DIR,
    ]

    seen_paths = set()

    for directory in directories:

        if not os.path.exists(
            directory
        ):
            continue

        try:
            entries = os.listdir(
                directory
            )
        except Exception:
            continue

        for filename in entries:

            if filename.startswith(
                "."
            ):
                continue

            filepath = os.path.abspath(
                os.path.join(
                    directory,
                    filename,
                )
            )

            if filepath in seen_paths:
                continue

            if not os.path.isfile(
                filepath
            ):
                continue

            seen_paths.add(
                filepath
            )

            try:
                size = os.path.getsize(
                    filepath
                )
            except OSError:
                size = 0

            files.append(
                {
                    "name": filename,
                    "size": size,
                    "extension": (
                        os.path.splitext(
                            filename
                        )[1].lower()
                    ),
                }
            )

    return jsonify(
        {
            "files": files
        }
    )


@app.route(
    "/api/download/<path:filename>",
    methods=["GET"],
)
def download_file(filename):

    safe_name = secure_filename(
        filename
    )

    if not safe_name:

        return jsonify(
            {
                "error": (
                    "Nom de fichier invalide."
                )
            }
        ), 400

    for directory in [
        FILES_DIR,
        GENERATED_DIR,
        WORKSPACE_DIR,
    ]:

        filepath = os.path.join(
            directory,
            safe_name,
        )

        if os.path.isfile(
            filepath
        ):

            return send_file(
                filepath,
                as_attachment=True,
            )

    return jsonify(
        {
            "error": (
                "Fichier introuvable."
            )
        }
    ), 404


# ==========================================
# ZIP SECURITY
# ==========================================

def validate_zip_member(
    base_dir: str,
    member_name: str,
) -> bool:

    if not member_name:
        return False

    # Normalisation Windows/Linux.
    normalized = member_name.replace(
        "\\",
        "/",
    )

    # Absolu Unix.
    if normalized.startswith(
        "/"
    ):
        return False

    # Drive Windows.
    if re.match(
        r"^[a-zA-Z]:",
        normalized,
    ):
        return False

    # Path traversal.
    parts = [
        part
        for part in normalized.split("/")
        if part
    ]

    if ".." in parts:
        return False

    target_path = os.path.abspath(
        os.path.join(
            base_dir,
            *parts,
        )
    )

    base_abs = os.path.abspath(
        base_dir
    )

    return (
        target_path == base_abs
        or target_path.startswith(
            base_abs + os.sep
        )
    )


def is_zip_symlink(info):
    """
    Détecte les symlinks Unix présents
    dans une archive ZIP.
    """

    mode = (
        info.external_attr
        >> 16
    )

    return (
        (mode & 0o170000)
        == 0o120000
    )


# ==========================================
# UPLOAD
# ==========================================

@app.route(
    "/api/upload",
    methods=["POST"],
)
def upload_file():

    if "file" not in request.files:

        return jsonify(
            {
                "error": (
                    "Aucun fichier fourni."
                )
            }
        ), 400

    file = request.files["file"]

    if not file.filename:

        return jsonify(
            {
                "error": (
                    "Nom de fichier manquant."
                )
            }
        ), 400

    filename = secure_filename(
        file.filename
    )

    if not filename:

        return jsonify(
            {
                "error": (
                    "Nom de fichier invalide."
                )
            }
        ), 400

    filepath = os.path.abspath(
        os.path.join(
            FILES_DIR,
            filename,
        )
    )

    files_root = os.path.abspath(
        FILES_DIR
    )

    if not filepath.startswith(
        files_root + os.sep
    ):

        return jsonify(
            {
                "error": (
                    "Chemin de fichier interdit."
                )
            }
        ), 400

    try:

        file.save(
            filepath
        )

    except Exception as exc:

        logger.error(
            "Upload impossible : %s",
            exc,
        )

        return jsonify(
            {
                "error": (
                    "Impossible d'enregistrer "
                    "le fichier."
                )
            }
        ), 500

    try:
        file_size = os.path.getsize(
            filepath
        )
    except OSError:
        file_size = 0

    extracted_files = []

    # ======================================
    # ZIP
    # ======================================

    if filename.lower().endswith(
        ".zip"
    ):

        temp_extract_dir = tempfile.mkdtemp(
            prefix="bek_zip_",
            dir=FILES_DIR,
        )

        try:

            with zipfile.ZipFile(
                filepath,
                "r",
            ) as zip_ref:

                infos = zip_ref.infolist()

                # ----------------------------------
                # Validation de tous les membres
                # ----------------------------------

                for info in infos:

                    if not validate_zip_member(
                        temp_extract_dir,
                        info.filename,
                    ):

                        raise ValueError(
                            "Archive ZIP contenant "
                            "un chemin dangereux."
                        )

                    if is_zip_symlink(
                        info
                    ):

                        raise ValueError(
                            "Archive ZIP contenant "
                            "un lien symbolique interdit."
                        )

                # ----------------------------------
                # Extraction contrôlée
                # ----------------------------------

                for info in infos:

                    member_name = (
                        info.filename.replace(
                            "\\",
                            "/",
                        )
                    )

                    target_path = os.path.abspath(
                        os.path.join(
                            temp_extract_dir,
                            *[
                                part
                                for part in member_name.split("/")
                                if part
                            ],
                        )
                    )

                    if info.is_dir():

                        os.makedirs(
                            target_path,
                            exist_ok=True,
                        )

                        continue

                    os.makedirs(
                        os.path.dirname(
                            target_path
                        ),
                        exist_ok=True,
                    )

                    with zip_ref.open(
                        info,
                        "r",
                    ) as source:

                        with open(
                            target_path,
                            "wb",
                        ) as destination:

                            shutil.copyfileobj(
                                source,
                                destination,
                            )

                    extracted_files.append(
                        member_name
                    )

            # ----------------------------------
            # Déplacement final
            # ----------------------------------

            for root, dirs, files in os.walk(
                temp_extract_dir
            ):

                relative_root = os.path.relpath(
                    root,
                    temp_extract_dir,
                )

                destination_root = (
                    FILES_DIR
                    if relative_root == "."
                    else os.path.join(
                        FILES_DIR,
                        relative_root,
                    )
                )

                os.makedirs(
                    destination_root,
                    exist_ok=True,
                )

                for directory in dirs:

                    os.makedirs(
                        os.path.join(
                            destination_root,
                            directory,
                        ),
                        exist_ok=True,
                    )

                for extracted_file in files:

                    source_path = os.path.join(
                        root,
                        extracted_file,
                    )

                    destination_path = os.path.join(
                        destination_root,
                        extracted_file,
                    )

                    os.makedirs(
                        os.path.dirname(
                            destination_path
                        ),
                        exist_ok=True,
                    )

                    shutil.move(
                        source_path,
                        destination_path,
                    )

        except Exception as zip_err:

            logger.warning(
                "[ZipExtractWarning] %s : %s",
                filename,
                zip_err,
            )

            return jsonify(
                {
                    "status": "success",
                    "filename": filename,
                    "size": file_size,
                    "extracted_contents": [],
                    "zip_warning": str(
                        zip_err
                    ),
                }
            )

        finally:

            shutil.rmtree(
                temp_extract_dir,
                ignore_errors=True,
            )

    return jsonify(
        {
            "status": "success",
            "filename": filename,
            "size": file_size,
            "extracted_contents": (
                extracted_files
            ),
        }
    )


# ==========================================
# WEB AGENT
# ==========================================

@app.route(
    "/api/agent/web",
    methods=["POST"],
)
def api_web():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    query = data.get(
        "query",
        "Tendances SaaS et CRM IA 2026",
    )

    if not isinstance(
        query,
        str,
    ):

        return jsonify(
            {
                "error": "query invalide."
            }
        ), 400

    query = query.strip()

    if not query:

        return jsonify(
            {
                "error": "query requis."
            }
        ), 400

    try:

        result = (
            web_agent_instance.run_pipeline(
                query
            )
        )

        return jsonify(
            result
        )

    except Exception as exc:

        logger.error(
            "Web agent error : %s",
            exc,
        )

        return jsonify(
            {
                "status": "error",
                "error": str(exc),
            }
        ), 500


@app.route(
    "/api/agent/web-sync",
    methods=["POST"],
)
def api_trigger_web_sync():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    query = data.get(
        "query",
        "CEO SaaS CRM automatisation",
    )

    if not isinstance(
        query,
        str,
    ):

        return jsonify(
            {
                "error": "query invalide."
            }
        ), 400

    try:

        result = (
            web_agent_instance.run_pipeline(
                query.strip()
            )
        )

        return jsonify(
            result
        )

    except Exception as exc:

        logger.error(
            "Web sync error : %s",
            exc,
        )

        return jsonify(
            {
                "status": "error",
                "error": str(exc),
            }
        ), 500


# ==========================================
# HERMES RUNTIME
# ==========================================

@app.route(
    "/api/hermes/runtime",
    methods=["GET"],
)
def api_hermes_runtime():

    runtime = (
        hermes.runtime_status()
    )

    trace_id = (
        hermes.create_trace_id()
    )

    return jsonify(
        {
            "hermes_state": runtime.get(
                "status",
                "unknown",
            ),
            "security_guard": runtime.get(
                "security_guard_active",
                False,
            ),
            "tool_count": runtime.get(
                "tool_count",
                0,
            ),
            "tools": [
                {
                    "name": tool.get(
                        "name"
                    ),
                    "risk": tool.get(
                        "risk_level"
                    ),
                }
                for tool in runtime.get(
                    "tools",
                    [],
                )
            ],
            "provider": runtime.get(
                "provider"
            ),
            "model": runtime.get(
                "model"
            ),
            "trace_id": trace_id,
        }
    )


# ==========================================
# HERMES GOAP + SECURITY
# ==========================================

@app.route(
    "/api/hermes/goap-execute",
    methods=["POST"],
)
def api_hermes_goap():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    user_objective = (
        data.get("objective")
        or data.get("query")
        or "Analyse globale de la Matrisse 2026"
    )

    if not isinstance(
        user_objective,
        str,
    ):

        return jsonify(
            {
                "error": (
                    "objective invalide."
                )
            }
        ), 400

    user_objective = (
        user_objective.strip()
    )

    if not user_objective:

        return jsonify(
            {
                "error": (
                    "objective requis."
                )
            }
        ), 400

    try:

        plan = (
            hermes.goap_planner(
                user_objective
            )
        )

        execution_result = (
            hermes.dispatch_parallel(
                plan
            )
        )

        log_mission_to_neon(
            trace_id=execution_result.get(
                "trace_id",
                "BEK-TRC-UNKNOWN",
            ),
            objective=user_objective,
            plan=plan,
            execution=execution_result,
        )

        return jsonify(
            {
                "objective": user_objective,
                "goap_plan": plan,
                "execution": execution_result,
            }
        )

    except Exception as exc:

        logger.error(
            "Hermes GOAP error : %s",
            exc,
        )

        return jsonify(
            {
                "status": "error",
                "error": str(exc),
            }
        ), 500


# ==========================================
# OBSERVABILITÉ
# ==========================================

@app.route(
    "/api/matrix/observability-logs",
    methods=["GET"],
)
def get_observability_logs():

    conn = get_db_connection()

    if not conn:

        return jsonify(
            {
                "status": "error",
                "message": (
                    "Neon DB non connectée."
                ),
            }
        )

    cur = None

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                trace_id,
                objective,
                status,
                execution_ms,
                created_at
            FROM bek_mission_logs
            ORDER BY created_at DESC
            LIMIT 10;
            """
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        logs = [
            dict(
                zip(
                    columns,
                    row,
                )
            )
            for row in cur.fetchall()
        ]

        # system_jobs peut ne pas encore exister.
        jobs = []

        try:

            cur.execute(
                """
                SELECT
                    job_id,
                    task_name,
                    status,
                    created_at
                FROM system_jobs
                ORDER BY created_at DESC
                LIMIT 5;
                """
            )

            columns = [
                description[0]
                for description in cur.description
            ]

            jobs = [
                dict(
                    zip(
                        columns,
                        row,
                    )
                )
                for row in cur.fetchall()
            ]

        except Exception as job_exc:

            logger.warning(
                "system_jobs indisponible : %s",
                job_exc,
            )

            try:
                conn.rollback()
            except Exception:
                pass

        return jsonify(
            {
                "status": "success",
                "mission_logs": logs,
                "system_jobs": jobs,
            }
        )

    except Exception as exc:

        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        )

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
# CRM STATS
# ==========================================

@app.route(
    "/api/crm/stats",
    methods=["GET"],
)
def get_crm_stats():

    conn = get_db_connection()

    if not conn:

        return jsonify(
            {
                "num_contacts": 0,
                "num_companies": 0,
                "num_opportunities": 0,
                "total_amount": 0.0,
                "status": "demo",
            }
        )

    cur = None

    try:

        cur = conn.cursor()

        # CONTACTS
        cur.execute(
            """
            SELECT
                id,
                name,
                email,
                phone
            FROM contacts;
            """
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        contacts = [
            dict(
                zip(
                    columns,
                    row,
                )
            )
            for row in cur.fetchall()
        ]

        # COMPANIES
        cur.execute(
            """
            SELECT
                id,
                name,
                created_at
            FROM companies;
            """
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        companies = [
            dict(
                zip(
                    columns,
                    row,
                )
            )
            for row in cur.fetchall()
        ]

        # OPPORTUNITIES
        cur.execute(
            """
            SELECT
                id,
                name,
                amount,
                currency,
                stage
            FROM opportunities;
            """
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        opportunities = [
            dict(
                zip(
                    columns,
                    row,
                )
            )
            for row in cur.fetchall()
        ]

        total_amount = sum(
            float(
                opportunity.get(
                    "amount",
                    0,
                )
                or 0
            )
            for opportunity in opportunities
        )

        return jsonify(
            {
                "num_contacts": len(
                    contacts
                ),
                "num_companies": len(
                    companies
                ),
                "num_opportunities": len(
                    opportunities
                ),
                "total_amount": total_amount,
                "contacts": contacts,
                "companies": companies,
                "opportunities": opportunities,
                "status": "connected",
            }
        )

    except Exception as exc:

        return jsonify(
            {
                "error": str(exc),
                "status": "error",
            }
        )

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
# CRM SQL
# ==========================================

@app.route(
    "/api/crm/execute",
    methods=["POST"],
)
def execute_crm_direct():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    sql = data.get(
        "sql",
        "",
    )

    if not isinstance(
        sql,
        str,
    ):

        return jsonify(
            {
                "error": "SQL invalide."
            }
        ), 400

    sql = sql.strip()

    if not sql:

        return jsonify(
            {
                "error": "SQL requis."
            }
        ), 400

    return jsonify(
        execute_database_sql(
            sql
        )
    )


# ==========================================
# MATRIX SPAWN
# ==========================================

@app.route(
    "/api/matrix/spawn",
    methods=["POST"],
)
def api_spawn_sub_crm():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    niche_name = data.get(
        "niche_name",
        "",
    )

    cahier_des_charges = data.get(
        "cahier_des_charges",
        (
            "Autonomie complète "
            "selon les objectifs assignés."
        ),
    )

    objectives = data.get(
        "objectives",
        [
            "Optimisation",
            "Automatisation",
            "Auto-correction",
        ],
    )

    parent_id = data.get(
        "parent_id",
        None,
    )

    custom_env = data.get(
        "custom_env",
        None,
    )

    if not isinstance(
        niche_name,
        str,
    ) or not niche_name.strip():

        return jsonify(
            {
                "error": (
                    "Le nom de la niche "
                    "ou du domaine est requis."
                )
            }
        ), 400

    if not isinstance(
        objectives,
        list,
    ):

        return jsonify(
            {
                "error": (
                    "objectives doit être une liste."
                )
            }
        ), 400

    result = (
        SubCRMEngine.spawn_sub_crm(
            niche_name=niche_name.strip(),
            cahier_des_charges=(
                str(
                    cahier_des_charges
                )
            ),
            objectives=objectives,
            parent_id=parent_id,
            custom_env=custom_env,
        )
    )

    return jsonify(
        result
    )


# ==========================================
# MATRIX SPAWN ALIVE
# ==========================================

@app.route(
    "/api/matrix/spawn-alive",
    methods=["POST"],
)
def api_spawn_alive_sub_crm():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    niche_name = data.get(
        "niche_name",
        "",
    )

    cahier_des_charges = data.get(
        "cahier_des_charges",
        (
            "Opérationnel, autonome, "
            "multi-rubriques et "
            "auto-réparateur."
        ),
    )

    objectives = data.get(
        "objectives",
        [
            "Création Interface Multi-Vues",
            "Comptes Utilisateurs",
            "Rentabilité & Automatisation",
        ],
    )

    parent_id = data.get(
        "parent_id",
        None,
    )

    custom_env = data.get(
        "custom_env",
        None,
    )

    if not isinstance(
        niche_name,
        str,
    ) or not niche_name.strip():

        return jsonify(
            {
                "error": (
                    "Le nom de la niche est requis."
                )
            }
        ), 400

    if not isinstance(
        objectives,
        list,
    ):

        return jsonify(
            {
                "error": (
                    "objectives doit être une liste."
                )
            }
        ), 400

    result = (
        SubCRMEngineAdvanced.spawn_fully_alive_sub_crm(
            niche_name=niche_name.strip(),
            cahier_des_charges=(
                str(
                    cahier_des_charges
                )
            ),
            objectives=objectives,
            parent_id=parent_id,
            custom_env=custom_env,
        )
    )

    return jsonify(
        result
    )


# ==========================================
# MATRIX BEK ACTION
# ==========================================

@app.route(
    "/api/matrix/bek-action",
    methods=["POST"],
)
def api_matrix_bek_action():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    action = data.get(
        "action",
        "process_data",
    )

    if action == "process_data":

        # Conservation du comportement UI existant.
        time.sleep(1.5)

        return jsonify(
            {
                "status": "success",
                "new_sequences": 8492,
                "active_agents": 5,
                "logs": [
                    (
                        ">_ Swarm-Core : "
                        "Lancement de l'analyse "
                        "des flux CRM..."
                    ),
                    (
                        ">_ Agent Web : "
                        "Scan et normalisation "
                        "des flux... OK"
                    ),
                    (
                        ">_ Agent Meta-Cortex : "
                        "Optimisation des pipelines "
                        "de vente..."
                    ),
                    (
                        ">_ Opération terminée. "
                        "Données synchronisées "
                        "avec Neon DB."
                    ),
                ],
            }
        )

    return jsonify(
        {
            "error": "Action inconnue."
        }
    ), 400


# ==========================================
# CHAT PRINCIPAL
# ==========================================

@app.route(
    "/api/chat",
    methods=["POST"],
)
def chat():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    messages = data.get(
        "messages",
        [],
    )

    provider = data.get(
        "provider",
        "groq",
    )

    model = data.get(
        "model",
        "openai/gpt-oss-120b",
    )

    use_memory = data.get(
        "use_memory",
        True,
    )

    use_reflection = data.get(
        "use_reflection",
        True,
    )

    if not isinstance(
        messages,
        list,
    ):

        return jsonify(
            {
                "error": (
                    "messages doit être une liste."
                )
            }
        ), 400

    if not isinstance(
        provider,
        str,
    ):

        return jsonify(
            {
                "error": "provider invalide."
            }
        ), 400

    if not isinstance(
        model,
        str,
    ):

        return jsonify(
            {
                "error": "model invalide."
            }
        ), 400

    provider = provider.strip().lower()
    model = model.strip()

    allowed_providers = {
        "groq",
        "nvidia",
        "gemini",
        "openrouter",
    }

    if provider not in allowed_providers:

        return jsonify(
            {
                "error": (
                    f"Provider non supporté : "
                    f"{provider}"
                )
            }
        ), 400

    hermes.set_provider_context(
        provider,
        model,
    )

    # ======================================
    # DERNIER MESSAGE UTILISATEUR
    # ======================================

    last_user_msg = ""

    for message in reversed(
        messages
    ):

        if not isinstance(
            message,
            dict,
        ):
            continue

        if message.get(
            "role"
        ) != "user":
            continue

        content = message.get(
            "content"
        )

        if isinstance(
            content,
            str,
        ):

            last_user_msg = content

        elif isinstance(
            content,
            list,
        ):

            parts = []

            for item in content:

                if (
                    isinstance(
                        item,
                        dict,
                    )
                    and isinstance(
                        item.get("text"),
                        str,
                    )
                ):

                    parts.append(
                        item["text"]
                    )

            last_user_msg = " ".join(
                parts
            )

        break

    # ======================================
    # PROVIDERS
    # ======================================

    if provider == "nvidia":

        api_key = get_api_key(
            "NVIDIA_API_KEY"
        )

        api_url = (
            "https://integrate.api.nvidia.com/"
            "v1/chat/completions"
        )

    elif provider == "gemini":

        api_key = get_api_key(
            "GEMINI_API_KEY"
        )

        api_url = (
            "https://generativelanguage.googleapis.com/"
            "v1beta/openai/chat/completions"
        )

    elif provider == "openrouter":

        api_key = get_api_key(
            "OPENROUTER_API_KEY"
        )

        api_url = (
            "https://openrouter.ai/"
            "api/v1/chat/completions"
        )

    else:

        api_key = get_api_key(
            "GROQ_API_KEY"
        )

        api_url = (
            "https://api.groq.com/"
            "openai/v1/chat/completions"
        )

    # ======================================
    # INTROSPECTION LOCALE
    # ======================================

    normalized_message = (
        last_user_msg.lower().strip()
        if last_user_msg
        else ""
    )

    introspection_requested = bool(
        normalized_message
        and (
            "introspection runtime"
            in normalized_message
            or "état runtime réel"
            in normalized_message
            or "registre d'outils"
            in normalized_message
        )
    )

    def generate_local_runtime_response():

        runtime = (
            hermes.runtime_status()
        )

        payload = {
            "hermes_state": runtime.get(
                "status",
                "unknown",
            ),
            "security_guard": runtime.get(
                "security_guard_active",
                False,
            ),
            "tools": [
                {
                    "name": tool.get(
                        "name"
                    ),
                    "risk": tool.get(
                        "risk_level"
                    ),
                }
                for tool in runtime.get(
                    "tools",
                    [],
                )
            ],
            "provider": runtime.get(
                "provider"
            ),
            "model": runtime.get(
                "model"
            ),
            "trace_id": (
                hermes.create_trace_id()
            ),
        }

        yield (
            "data: "
            + json.dumps(
                {
                    "chunk": json.dumps(
                        payload,
                        ensure_ascii=False,
                    )
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )

        yield (
            "data: "
            + json.dumps(
                {
                    "done": True
                }
            )
            + "\n\n"
        )

    if introspection_requested:

        return Response(
            generate_local_runtime_response(),
            mimetype="text/event-stream",
        )

    # ======================================
    # PROXY LLM
    # ======================================

    def generate_proxy():

        if not api_key:

            yield (
                "data: "
                + json.dumps(
                    {
                        "error": (
                            "Clé API manquante "
                            f"pour {provider}."
                        )
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

            return

        # ----------------------------------
        # SYNC
        # ----------------------------------

        try:

            sync_and_persist_global_state(
                commit_message=(
                    "BEK-v15.2 Auto-Sync Direct Action"
                )
            )

        except Exception as sync_err:

            logger.warning(
                "[SyncWarning] %s",
                sync_err,
            )

        # ----------------------------------
        # CONTEXTE
        # ----------------------------------

        dynamic_context = (
            f"{BEK_GOLDEN_RULES}\n\n"
        )

        if GLOBAL_SYSTEM_CONTEXT:

            dynamic_context += (
                "[DOCUMENTATION PROJET]\n"
                f"{GLOBAL_SYSTEM_CONTEXT}\n"
            )

        # ----------------------------------
        # FICHIERS
        # ----------------------------------

        try:

            if os.path.exists(
                FILES_DIR
            ):

                for filename in os.listdir(
                    FILES_DIR
                ):

                    filepath = os.path.join(
                        FILES_DIR,
                        filename,
                    )

                    if os.path.isfile(
                        filepath
                    ):

                        dynamic_context += (
                            "- Fichier : "
                            f"{filename}\n"
                        )

        except Exception as exc:

            logger.warning(
                "Lecture fichiers contexte : %s",
                exc,
            )

        # ----------------------------------
        # CRM CONTEXT
        # ----------------------------------

        real_crm_context = (
            "\n[SCHÉMA CRM STRICT DE NEON DB]\n"
            "Tables autorisées : "
            "'companies', 'contacts', "
            "'opportunities'.\n"
        )

        conn = None
        cur = None

        try:

            conn = get_db_connection()

            if conn:

                cur = conn.cursor()

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM companies;
                    """
                )

                result = cur.fetchone()

                comp_count = (
                    result[0]
                    if result
                    else 0
                )

                real_crm_context += (
                    "- Entreprises "
                    "(companies) : "
                    f"{comp_count}\n"
                )

        except Exception as exc:

            logger.warning(
                "CRM context indisponible : %s",
                exc,
            )

        finally:

            try:
                if cur:
                    cur.close()
            except Exception:
                pass

            try:
                if conn:
                    conn.close()
            except Exception:
                pass

        dynamic_context += (
            real_crm_context
        )

        # ----------------------------------
        # MEMORY
        # ----------------------------------

        if (
            use_memory
            and last_user_msg
        ):

            try:

                memory_results = (
                    search_memory(
                        last_user_msg
                    )
                )

                if memory_results:

                    dynamic_context += (
                        "\n[CTX-MEMOIRE]\n"
                        f"{memory_results}\n"
                    )

            except Exception as exc:

                logger.warning(
                    "Mémoire indisponible : %s",
                    exc,
                )

        # ----------------------------------
        # REFLECTION
        # ----------------------------------

        if use_reflection:

            dynamic_context += (
                "\n[REFLEXION]\n"
                "Utilise une vérification interne "
                "de cohérence avant de répondre lorsque "
                "la tâche est technique ou critique.\n"
            )

        # ----------------------------------
        # SWARM
        # ----------------------------------

        if any(
            keyword in normalized_message
            for keyword in [
                "essaim",
                "swarm",
                "analyse complète",
                "architecture swarm",
            ]
        ):

            try:

                swarm_result = asyncio.run(
                    run_bek_swarm_sync(
                        last_user_msg,
                        api_key,
                        provider,
                        model,
                    )
                )

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "chunk": (
                                f"{swarm_result}\n"
                            )
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "done": True
                        }
                    )
                    + "\n\n"
                )

                return

            except Exception as exc:

                logger.error(
                    "Erreur Swarm-Core : %s",
                    exc,
                )

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "error": (
                                "Erreur Swarm-Core : "
                                f"{exc}"
                            )
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                return

        # ----------------------------------
        # PROMPT D'ACTION
        # ----------------------------------

        action_prompt = (
            "Tu es BEK-v15.2, une IA hybride avancée "
            "et l'Exécuteur de la Matrisse.\n\n"
            "RÈGLE 1 — SOCIAL : "
            "Si l'utilisateur te salue ou discute "
            "de façon informelle, réponds naturellement, "
            "brièvement et poliment. "
            "Ne mentionne pas inutilement les protocoles, "
            "le CRM ou Neon DB.\n\n"
            "RÈGLE 2 — TECHNIQUE : "
            "Si l'utilisateur demande du code, une création "
            "ou une modification technique, sois direct "
            "et précis.\n\n"
            "RÈGLE 3 — VÉRACITÉ : "
            "Ne prétends jamais avoir effectué une action "
            "externe si elle n'a pas réellement été exécutée.\n\n"
            "RÈGLE 4 — CODE : "
            "Lorsque l'utilisateur demande la correction "
            "d'un fichier complet, fournis le fichier complet "
            "et cohérent sans remplacer des sections par "
            "des raccourcis du type '...'."
        )

        # ----------------------------------
        # MESSAGES
        # ----------------------------------

        clean_messages = []

        for message in messages[-6:]:

            if not isinstance(
                message,
                dict,
            ):
                continue

            role = message.get(
                "role"
            )

            if role not in [
                "user",
                "assistant",
            ]:
                continue

            content = message.get(
                "content",
                "",
            )

            if not isinstance(
                content,
                (
                    str,
                    list,
                ),
            ):
                continue

            clean_messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        exec_messages = [
            {
                "role": "system",
                "content": (
                    f"{action_prompt}\n\n"
                    f"Contexte :\n"
                    f"{dynamic_context}"
                ).strip(),
            }
        ] + clean_messages

        payload = {
            "model": model,
            "messages": exec_messages,
            "temperature": 0.2,
            "max_tokens": 4096,
            "stream": False,
        }

        headers = {
            "Authorization": (
                f"Bearer {api_key}"
            ),
            "Content-Type": (
                "application/json"
            ),
        }

        # ----------------------------------
        # PROVIDER
        # ----------------------------------

        try:

            resp = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=90,
            )

            if resp.status_code != 200:

                # Ne pas exposer inutilement
                # des headers sensibles.
                error_body = resp.text

                if len(
                    error_body
                ) > 4000:

                    error_body = (
                        error_body[:4000]
                        + "..."
                    )

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "error": (
                                f"Erreur API "
                                f"({resp.status_code}) : "
                                f"{error_body}"
                            )
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                return

            try:

                resp_json = (
                    resp.json()
                )

            except ValueError:

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "error": (
                                "Réponse provider "
                                "non JSON."
                            )
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                return

            choices = resp_json.get(
                "choices",
                [],
            )

            if not choices:

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "error": (
                                "Réponse provider "
                                "sans choix."
                            )
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                return

            message_data = (
                choices[0].get(
                    "message",
                    {}
                )
            )

            llm_text = (
                message_data.get(
                    "content",
                    "",
                )
                or ""
            ).strip()

            if not llm_text:

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "error": (
                                "Réponse LLM vide."
                            )
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )

                return

            yield (
                "data: "
                + json.dumps(
                    {
                        "chunk": llm_text
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

            yield (
                "data: "
                + json.dumps(
                    {
                        "done": True
                    }
                )
                + "\n\n"
            )

            # ----------------------------------
            # MEMORY SAVE
            # ----------------------------------

            if (
                use_memory
                and last_user_msg
                and llm_text
            ):

                try:

                    save_to_memory(
                        last_user_msg,
                        llm_text,
                    )

                except Exception as memory_exc:

                    logger.warning(
                        "Memory save failed : %s",
                        memory_exc,
                    )

        except requests.Timeout:

            yield (
                "data: "
                + json.dumps(
                    {
                        "error": (
                            "Timeout du provider."
                        )
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

        except requests.RequestException as exc:

            yield (
                "data: "
                + json.dumps(
                    {
                        "error": (
                            "Erreur réseau provider : "
                            f"{exc}"
                        )
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

        except Exception as exc:

            logger.exception(
                "Erreur chat proxy."
            )

            yield (
                "data: "
                + json.dumps(
                    {
                        "error": str(exc)
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

    return Response(
        generate_proxy(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ==========================================
# ERROR HANDLERS
# ==========================================

@app.errorhandler(
    413
)
def request_entity_too_large(error):

    return jsonify(
        {
            "status": "error",
            "error": (
                "Fichier ou requête trop volumineux."
            ),
        }
    ), 413


@app.errorhandler(
    404
)
def not_found(error):

    return jsonify(
        {
            "status": "error",
            "error": "Route introuvable.",
        }
    ), 404


@app.errorhandler(
    500
)
def internal_server_error(error):

    logger.exception(
        "Erreur interne Flask."
    )

    return jsonify(
        {
            "status": "error",
            "error": (
                "Erreur interne du serveur."
            ),
        }
    ), 500


# ==========================================
# START SERVER
# ==========================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "8765",
        )
    )

    host = os.environ.get(
        "HOST",
        "0.0.0.0",
    )

    debug_mode = (
        os.environ.get(
            "BEK_DEBUG",
            "false",
        ).lower()
        in (
            "1",
            "true",
            "yes",
            "on",
        )
    )

    logger.info(
        "=========================================="
    )

    logger.info(
        "BEK-v15.2 HYBRID démarrage"
    )

    logger.info(
        "Host: %s",
        host,
    )

    logger.info(
        "Port: %s",
        port,
    )

    logger.info(
        "Debug: %s",
        debug_mode,
    )

    logger.info(
        "Hermes SecurityGuard: actif"
    )

    logger.info(
        "=========================================="
    )

    app.run(
        host=host,
        port=port,
        debug=debug_mode,
        threaded=True,
    )
Ce qu'on vient de sécuriser dans app.py
Zone	Correction
Hermes	Vérification que le SecurityGuard est réellement disponible
CRM SQL	Endpoint administratif protégé si BEK_ADMIN_API_KEY est configurée
SQL	Blocage de plusieurs opérations PostgreSQL particulièrement dangereuses
GitHub	Le GITHUB_TOKEN n'est plus placé dans l'URL du remote
ZIP	Protection traversal + chemins absolus + symlinks
CORS	Plus de CORS(app) ouvert à tout Internet par défaut
Debug	debug=False par défaut
NVIDIA	Correction du bug get_api_key(model) → NVIDIA_API_KEY
Provider	Validation des providers acceptés
API	Gestion plus propre des erreurs/JSON
SSE	Headers adaptés au streaming
Flask	Handlers 404/413/500
Memory	Les erreurs mémoire ne cassent pas le chat
Neon	Nettoyage systématique des connexions/cursors
Skills	Évite les doublons dans l'index
Runtime	Endpoint /api/health ajouté

Important : je n'ai volontairement pas inventé d'appel à une méthode inconnue de ton SecurityGuard dans app.py. Comme ton hermes_core.py et ton security_guard.py ont leur propre API, on doit maintenant vérifier leur contrat réel plutôt que de fabriquer une intégration qui pourrait casser Hermes.

Étape suivante

Maintenant que memory.py + app.py sont corrigés, on passe au fichier suivant : hermes_core.py.

C'est là qu'on doit vérifier le point central : GOAP → SecurityGuard → validation → dispatch → outils → résultats → trace, pour être sûr qu'aucune route ou aucun outil ne puisse contourner le noyau de sécurité.

Chat en pause jusqu’à la réinitialisation du quota à 19:43
Vous avez épuisé le quota de chats avec analyse de données. Démarrez un nouveau chat (texte uniquement), ou changez de forfait pour continuer.
Nouveau chat
Mettre à niveau
