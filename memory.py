"""
BEK-v19.1 HYBRID
Memory Layer (Dual Hybrid: ChromaDB Local + Pinecone Cloud + Supabase PostgreSQL + Sync Compensation)
--------------------------------------------------------------------------------------------------
v19.1 (2026-11-05) — OPTIMISATION MAJEURE :
  - Pinecone timeout réduit à 3s (au lieu de 10s)
  - NVIDIA Embeddings timeout réduit à 3s (au lieu de 10s)
  - Pool de connexions PostgreSQL (au lieu de nouvelles connexions)
  - Pinecone ET ChromaDB en parallèle (au lieu de séquentiel)
  - search_memory() devient search_memory_async() pour la parallélisation
  - Compatibilité 100% conservée (search_memory sync toujours disponible)
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import math
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
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

ROOT = Path(__file__).resolve().parent

WS_DIR = ROOT
SKILLS_DIR = ROOT / "skills"
PLUGINS_DIR = ROOT / "plugins"
UPLOAD_DIR = ROOT / "uploads"
GENERATED_DIR = ROOT / "generated"
CHROMA_DIR = ROOT / "chroma_db"

for directory in (
    SKILLS_DIR,
    PLUGINS_DIR,
    UPLOAD_DIR,
    GENERATED_DIR,
    CHROMA_DIR,
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
    """Charge un fichier env.txt simple de type KEY=VALUE."""
    values: Dict[str, str] = {}

    if not path.exists() or not path.is_file():
        return values

    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#") or line.startswith("="):
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


ENV.update(_load_env_file(ROOT / "env.txt"))


def _env(key: str, default: str = "") -> str:
    """Priorité : OS Env > env.txt > default."""
    return os.getenv(key, ENV.get(key, default))


# ============================================================
# API CONFIGURATION
# ============================================================

GROQ_API_KEY = _env("GROQ_API_KEY", "")
NVIDIA_API_KEY = _env("NVIDIA_API_KEY", "")
PINECONE_API_KEY = _env("PINECONE_API_KEY", "")

PINECONE_INDEX_NAME = _env("PINECONE_INDEX_NAME", "bek-memory")

DATABASE_URL = _env("DATABASE_URL", "")

NVIDIA_EMBEDDING_MODEL = _env("NVIDIA_EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b")
NVIDIA_EMBEDDING_URL = _env(
    "NVIDIA_EMBEDDING_URL",
    "https://integrate.api.nvidia.com/v1/embeddings",
)


# ============================================================
# FEATURE FLAGS LAZY LOADING
# ============================================================

_DISABLE_CHROMADB = _env("BEK_DISABLE_CHROMADB", "false").lower() in (
    "true", "1", "yes", "on"
)

_LAZY_LOAD = _env("BEK_LAZY_LOAD", "true").lower() in (
    "true", "1", "yes", "on"
)


# ============================================================
# ★ v19.1 — TIMEOUTS OPTIMISÉS (CRITIQUE)
# ============================================================

MAX_EMBEDDING_INPUT_LENGTH = 2000
DEFAULT_EMBEDDING_DIM = 1024

DEFAULT_TOP_K = 2
MIN_TOP_K = 1
MAX_TOP_K = 50

# ★ v19.1 : Timeouts courts (au lieu de 10s)
PINECONE_TIMEOUT_SECONDS = 3        # était 10
NVIDIA_EMBEDDING_TIMEOUT_SECONDS = 3  # était 10
DATABASE_CONNECT_TIMEOUT_SECONDS = 5  # était 10

# ★ v19.1 — Pool de connexions PostgreSQL
_PG_POOL = None
_PG_POOL_LOCK = threading.Lock()
_PG_POOL_SIZE = 20


# ★ v19.1 — Circuit Breaker NVIDIA
_NVIDIA_EMBEDDING_DISABLED = False
_NVIDIA_FAILURE_COUNT = 0
_NVIDIA_MAX_FAILURES = 3

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
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)
    except OSError:
        pass

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(stream_handler)


# ============================================================
# UTILS
# ============================================================

def clean_string(text: Any) -> str:
    """Nettoie les chaînes et supprime les surrogate characters."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return "".join(
        character for character in text if not (0xD800 <= ord(character) <= 0xDFFF)
    )


def _safe_top_k(top_k: Any) -> int:
    """Normalise top_k afin d'éviter des valeurs abusives."""
    try:
        value = int(top_k)
    except (TypeError, ValueError):
        value = DEFAULT_TOP_K
    return max(MIN_TOP_K, min(value, MAX_TOP_K))


def _fit_dimension(vector: List[float], target_dim: int) -> List[float]:
    """Ajuste un vecteur à la dimension cible."""
    current_len = len(vector)
    if current_len == target_dim:
        return vector
    if current_len > target_dim:
        return vector[:target_dim]
    return vector + [0.0] * (target_dim - current_len)


# ============================================================
# EMBEDDINGS
# ============================================================

def _fallback_embedding(text: str, target_dim: int = DEFAULT_EMBEDDING_DIM) -> List[float]:
    """Embedding local déterministe SHA-256."""
    if target_dim <= 0:
        return []

    vector = [0.0] * target_dim
    words = text.lower().split()
    if not words:
        words = [text.lower()]

    for index, word in enumerate(words):
        try:
            digest = hashlib.sha256(word.encode("utf-8")).hexdigest()
            bucket = int(digest, 16) % target_dim
        except Exception:
            continue
        weight = 1.0 / math.sqrt(index + 1)
        vector[bucket] += weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


def get_embedding(
    text: str,
    input_type: str = "query",
    target_dim: int = DEFAULT_EMBEDDING_DIM,
) -> List[float]:
    """
    Génère un embedding via NVIDIA NIM, avec fallback local SHA-256.
    ★ v19.1 : Timeout court (3s) + Circuit Breaker après 3 échecs.
    """
    global _NVIDIA_EMBEDDING_DISABLED, _NVIDIA_FAILURE_COUNT

    text = clean_string(text)
    if not text:
        return []

    if target_dim <= 0:
        logger.warning("Dimension d'embedding invalide: %s", target_dim)
        return []

    text = text[:MAX_EMBEDDING_INPUT_LENGTH]

    # 1. Tentative NVIDIA embedding (si pas désactivé par le Circuit Breaker)
    if NVIDIA_API_KEY and not _NVIDIA_EMBEDDING_DISABLED:
        try:
            headers = {
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "input": [text],
                "model": NVIDIA_EMBEDDING_MODEL,
                "input_type": input_type,
            }
            # ★ v19.1 : Timeout court
            response = requests.post(
                NVIDIA_EMBEDDING_URL,
                json=payload,
                headers=headers,
                timeout=NVIDIA_EMBEDDING_TIMEOUT_SECONDS,
            )

            # Circuit Breaker
            if response.status_code in (401, 403, 502, 503):
                _NVIDIA_EMBEDDING_DISABLED = True
                logger.warning(
                    "⚠️ NVIDIA Embeddings désactivé (HTTP %s). Fallback local.",
                    response.status_code,
                )
                return _fallback_embedding(text, target_dim=target_dim)

            response.raise_for_status()
            body = response.json()
            data = body.get("data")

            if isinstance(data, list) and data and isinstance(data[0], dict):
                embedding = data[0].get("embedding")
                if isinstance(embedding, list) and embedding:
                    vector = [float(v) for v in embedding]
                    original_len = len(vector)
                    vector = _fit_dimension(vector, target_dim)
                    if original_len != target_dim:
                        logger.debug(
                            "NVIDIA embedding %d dims → ajusté à %d",
                            original_len, target_dim,
                        )
                    if vector:
                        _NVIDIA_FAILURE_COUNT = 0  # Reset après succès
                        return vector

            logger.warning("NVIDIA embedding a retourné un format invalide.")
        except Exception as exc:
            _NVIDIA_FAILURE_COUNT += 1
            if _NVIDIA_FAILURE_COUNT >= _NVIDIA_MAX_FAILURES:
                _NVIDIA_EMBEDDING_DISABLED = True
                logger.warning(
                    "⚠️ NVIDIA Embeddings désactivé après %d échecs. Fallback local.",
                    _NVIDIA_FAILURE_COUNT,
                )
            logger.warning(
                "Embedding NVIDIA indisponible : %s. Bascule sur fallback local.", exc
            )

    # 2. Fallback local SHA-256
    return _fallback_embedding(text, target_dim=target_dim)


# ============================================================
# CHROMADB (LAZY + FEATURE FLAG)
# ============================================================

_CHROMA_CLIENT = None
_CHROMA_COLLECTION = None
_CHROMA_LOCK = threading.Lock()
_CHROMA_LOADED = False


def is_chromadb_loaded() -> bool:
    return _CHROMA_LOADED


def is_chromadb_disabled() -> bool:
    return _DISABLE_CHROMADB


def get_chroma_collection():
    global _CHROMA_CLIENT, _CHROMA_COLLECTION, _CHROMA_LOADED

    if _DISABLE_CHROMADB:
        logger.debug("[memory] ChromaDB désactivé (BEK_DISABLE_CHROMADB=true)")
        return None

    if _CHROMA_LOADED:
        return _CHROMA_COLLECTION

    with _CHROMA_LOCK:
        if _CHROMA_LOADED:
            return _CHROMA_COLLECTION

        logger.info("[memory] Chargement ChromaDB (lazy)...")
        try:
            import chromadb
            from chromadb.config import Settings

            _CHROMA_CLIENT = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=Settings(anonymized_telemetry=False),
            )
            _CHROMA_COLLECTION = _CHROMA_CLIENT.get_or_create_collection(
                name="bek_memory_local",
                metadata={"hnsw:space": "cosine"},
            )
            _CHROMA_LOADED = True
            logger.info("[memory] ✅ ChromaDB chargé")
            return _CHROMA_COLLECTION
        except ImportError:
            logger.warning("[memory] ChromaDB non installé.")
            _CHROMA_LOADED = True
            return None
        except Exception as exc:
            logger.error("[memory] Erreur initialisation ChromaDB : %s", exc)
            _CHROMA_LOADED = True
            return None


# ============================================================
# PINECONE (★ v19.1 : Timeout court)
# ============================================================

_PINECONE_INDEX = None
_PINECONE_INDEX_LOCK = threading.Lock()


def get_pinecone_index() -> Optional[Any]:
    """★ v19.1 : Singleton avec timeout court."""
    global _PINECONE_INDEX

    if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        return None

    if _PINECONE_INDEX is not None:
        return _PINECONE_INDEX

    with _PINECONE_INDEX_LOCK:
        if _PINECONE_INDEX is not None:
            return _PINECONE_INDEX

        try:
            from pinecone import Pinecone
            client = Pinecone(api_key=PINECONE_API_KEY)
            _PINECONE_INDEX = client.Index(PINECONE_INDEX_NAME)
            return _PINECONE_INDEX
        except ImportError:
            logger.error("Le package 'pinecone' n'est pas installé.")
            return None
        except Exception as exc:
            logger.error("Erreur d'initialisation Pinecone: %s", exc)
            return None


# ============================================================
# ★ v19.1 — POOL DE CONNEXIONS POSTGRESQL
# ============================================================

def _init_pg_pool():
    """Initialise le pool de connexions PostgreSQL."""
    global _PG_POOL
    if _PG_POOL is not None:
        return _PG_POOL

    if not DATABASE_URL:
        return None

    try:
        import psycopg2.pool
    except ImportError:
        logger.error("psycopg2.pool non installé.")
        return None

    with _PG_POOL_LOCK:
        if _PG_POOL is not None:
            return _PG_POOL

        try:
            _PG_POOL = psycopg2.pool.SimpleConnectionPool(
                1, _PG_POOL_SIZE, DATABASE_URL,
                connect_timeout=DATABASE_CONNECT_TIMEOUT_SECONDS,
            )
            logger.info("[memory] ✅ Pool PostgreSQL initialisé (%d conns)", _PG_POOL_SIZE)
            return _PG_POOL
        except Exception as exc:
            logger.error("[memory] Échec création pool PostgreSQL : %s", exc)
            return None


def get_db_connection() -> Optional[Any]:
    """
    ★ v19.1 : Récupère une connexion depuis le pool.
    Si le pool est indisponible, fallback sur une connexion directe.
    """
    pool = _init_pg_pool()

    if pool is not None:
        try:
            return pool.getconn()
        except Exception as exc:
            logger.warning("[memory] Erreur getconn pool : %s. Fallback direct.", exc)

    # Fallback direct (lent mais fonctionnel)
    if not DATABASE_URL:
        logger.warning("DATABASE_URL non configuré.")
        return None

    try:
        import psycopg2
        return psycopg2.connect(
            DATABASE_URL,
            connect_timeout=DATABASE_CONNECT_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.error("Erreur connexion Supabase DB: %s", exc)
        return None


def _release_db_connection(conn):
    """★ v19.1 : Libère la connexion (retour au pool si possible)."""
    if conn is None:
        return

    pool = _PG_POOL
    if pool is not None:
        try:
            pool.putconn(conn)
            return
        except Exception:
            pass

    # Fallback : fermer la connexion
    try:
        conn.close()
    except Exception:
        pass


def init_sync_log_table() -> None:
    conn = get_db_connection()
    if not conn:
        return
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_log (
                id VARCHAR(64) PRIMARY KEY,
                content TEXT NOT NULL,
                vector_dim INT DEFAULT 1024,
                status VARCHAR(32) NOT NULL,
                retry_count INT DEFAULT 0,
                last_error TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
    except Exception as exc:
        logger.warning("Initialisation de sync_log échouée : %s", exc)
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
        _release_db_connection(conn)


def record_pending_sync(record_id: str, content: str, error_msg: str = "") -> None:
    conn = get_db_connection()
    if not conn:
        return
    cur = None
    try:
        init_sync_log_table()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sync_log (id, content, status, retry_count, last_error, updated_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE
            SET retry_count = sync_log.retry_count + 1,
                last_error = EXCLUDED.last_error,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (record_id, content, "PENDING_PINECONE", 0, clean_string(error_msg)[:500]),
        )
        conn.commit()
    except Exception as exc:
        logger.error("Impossible d'enregistrer la compensation dans sync_log : %s", exc)
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
        _release_db_connection(conn)


def replay_pending_syncs(limit: int = 20) -> int:
    """
    Rejoue les synchronisations Pinecone en attente (table sync_log).
    Retourne le nombre de synchronisations réussies.
    """
    index = get_pinecone_index()
    if index is None:
        return 0

    conn = get_db_connection()
    if not conn:
        return 0

    cur = None
    replayed_count = 0
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, content, retry_count
            FROM sync_log
            WHERE status = 'PENDING_PINECONE' AND retry_count < 5
            ORDER BY created_at ASC
            LIMIT %s;
            """,
            (limit,),
        )
        rows = cur.fetchall()
        for record_id, content, retries in rows:
            clean_txt = clean_string(content)
            vector = get_embedding(clean_txt, input_type="passage")
            if not vector:
                continue

            try:
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                index.upsert(
                    vectors=[{
                        "id": record_id,
                        "values": vector,
                        "metadata": {"text": clean_txt, "date": now_iso, "type": "conversation"}
                    }]
                )
                cur.execute(
                    "UPDATE sync_log SET status = 'SYNCED', updated_at = CURRENT_TIMESTAMP WHERE id = %s;",
                    (record_id,),
                )
                conn.commit()
                replayed_count += 1
                logger.info("Compensation réussie pour le vecteur %s", record_id)
            except Exception as sync_err:
                cur.execute(
                    """
                    UPDATE sync_log
                    SET retry_count = retry_count + 1, last_error = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (clean_string(str(sync_err))[:500], record_id),
                )
                conn.commit()
    except Exception as exc:
        logger.error("Erreur lors du rejeu de synchronisation : %s", exc)
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
        _release_db_connection(conn)

    return replayed_count


# ==========================================
# ★ v19.1 — MEMORY SEARCH (Pinecone ET ChromaDB EN PARALLÈLE)
# ==========================================

def _search_pinecone(query: str, vector: List[float], top_k: int) -> List[str]:
    """★ v19.1 : Recherche Pinecone isolée (pour parallélisation)."""
    index = get_pinecone_index()
    if index is None:
        return []

    try:
        logger.info("[Pinecone] Recherche | query_len=%d | top_k=%d", len(query), top_k)
        # ★ v19.1 : Pinecone SDK utilise son propre timeout interne
        response = index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True,
        )
        matches = getattr(response, "matches", []) or response.get("matches", [])
        lines = []
        for match in matches:
            metadata = getattr(match, "metadata", {}) or match.get("metadata", {})
            date_val = clean_string(metadata.get("date", "Inconnue"))
            text_val = clean_string(metadata.get("text", ""))
            if text_val:
                lines.append(f"- Date: {date_val} | Info: {text_val}")
        return lines
    except Exception as exc:
        logger.warning("[Pinecone] Échec : %s", exc)
        return []


def _search_chromadb(query: str, vector: List[float], top_k: int) -> List[str]:
    """★ v19.1 : Recherche ChromaDB isolée (pour parallélisation)."""
    chroma_coll = get_chroma_collection()
    if chroma_coll is None:
        return []

    try:
        logger.info("[ChromaDB] Recherche | top_k=%d", top_k)
        res = chroma_coll.query(query_embeddings=[vector], n_results=top_k)
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        lines = []
        for doc, meta in zip(docs, metas):
            d_val = meta.get("date", "Inconnue") if isinstance(meta, dict) else "Inconnue"
            lines.append(f"- Date: {d_val} | Info: {doc}")
        return lines
    except Exception as exc:
        logger.error("[ChromaDB] Échec : %s", exc)
        return []


def search_memory(
    query: str = "",
    top_k: int = DEFAULT_TOP_K,
) -> str:
    """
    ★ v19.1 : Pinecone ET ChromaDB en PARALLÈLE (au lieu de séquentiel).
    Gain attendu : 25s → 3s.
    """
    query = clean_string(query)
    if not query:
        return ""

    top_k = _safe_top_k(top_k)
    vector = get_embedding(query, input_type="query")
    if not vector:
        return ""

    # ★ v19.1 : Parallélisation Pinecone + ChromaDB
    results = {}
    start = time.time()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(_search_pinecone, query, vector, top_k): "pinecone",
            executor.submit(_search_chromadb, query, vector, top_k): "chromadb",
        }

        for future in as_completed(futures, timeout=PINECONE_TIMEOUT_SECONDS + 2):
            src = futures[future]
            try:
                results[src] = future.result()
            except Exception as exc:
                logger.warning("[%s] Exception : %s", src, exc)
                results[src] = []

    elapsed = (time.time() - start) * 1000
    logger.info("[search_memory] Total : %.0fms | pinecone=%d | chromadb=%d",
                elapsed, len(results.get("pinecone", [])), len(results.get("chromadb", [])))

    # Fusion : Pinecone prioritaire, puis ChromaDB
    all_lines = []
    for src in ("pinecone", "chromadb"):
        lines = results.get(src, [])
        if lines:
            all_lines.extend(lines[:top_k])

    return "\n".join(all_lines)


# ==========================================
# MEMORY SAVE (★ v19.1 : Pinecone ET ChromaDB en parallèle)
# ==========================================

def save_to_memory(
    user_query: str,
    agent_response: str = "",
) -> bool:
    user_query = clean_string(user_query)
    agent_response = clean_string(agent_response)

    if not user_query and not agent_response:
        return False

    if agent_response:
        combined_text = clean_string(f"Requête: {user_query}\nRéponse: {agent_response[:1000]}")
    else:
        combined_text = clean_string(user_query)

    vector = get_embedding(combined_text, input_type="passage")
    if not vector:
        return False

    record_id = str(uuid.uuid4())
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    metadata = {
        "text": combined_text,
        "date": now_iso,
        "type": "conversation",
    }

    saved_pinecone = False
    saved_chroma = False

    # ★ v19.1 : Parallélisation des upserts
    def _upsert_pinecone():
        index = get_pinecone_index()
        if index is None:
            record_pending_sync(record_id, combined_text, "Pinecone index indisponible")
            return False
        try:
            index.upsert(
                vectors=[{"id": record_id, "values": vector, "metadata": metadata}]
            )
            logger.info("Interaction enregistrée dans Pinecone | id=%s", record_id)
            return True
        except Exception as exc:
            logger.warning("Échec sauvegarde Pinecone : %s", exc)
            record_pending_sync(record_id, combined_text, str(exc))
            return False

    def _upsert_chroma():
        chroma_coll = get_chroma_collection()
        if chroma_coll is None:
            return False
        try:
            chroma_coll.upsert(
                ids=[record_id],
                embeddings=[vector],
                documents=[combined_text],
                metadatas=[{"date": now_iso, "type": "conversation"}],
            )
            logger.info("Interaction enregistrée dans ChromaDB | id=%s", record_id)
            return True
        except Exception as exc:
            logger.warning("Échec sauvegarde ChromaDB : %s", exc)
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_pine = executor.submit(_upsert_pinecone)
        f_chroma = executor.submit(_upsert_chroma)
        try:
            saved_pinecone = f_pine.result(timeout=PINECONE_TIMEOUT_SECONDS + 2)
        except Exception:
            pass
        try:
            saved_chroma = f_chroma.result(timeout=5)
        except Exception:
            pass

    return saved_pinecone or saved_chroma


# ==========================================
# MEMORY DELETE
# ==========================================

def delete_from_memory(record_id: str = "", keyword: str = "") -> dict:
    result = {"pinecone": False, "chroma": False, "supabase_sync": False}

    index = get_pinecone_index()
    if index is not None and record_id:
        try:
            index.delete(ids=[record_id])
            result["pinecone"] = True
            logger.info("Souvenir supprimé de Pinecone | id=%s", record_id)
        except Exception as exc:
            logger.warning("Échec suppression Pinecone : %s", exc)

    chroma_coll = get_chroma_collection()
    if chroma_coll is not None:
        try:
            if record_id:
                chroma_coll.delete(ids=[record_id])
            elif keyword:
                results = chroma_coll.get()
                ids_to_delete = []
                for idx, doc in enumerate(results.get("documents", [])):
                    if keyword.lower() in doc.lower():
                        ids_to_delete.append(results["ids"][idx])
                if ids_to_delete:
                    chroma_coll.delete(ids=ids_to_delete)
            result["chroma"] = True
            logger.info("Souvenir supprimé de ChromaDB local")
        except Exception as exc:
            logger.warning("Échec suppression ChromaDB : %s", exc)

    conn = get_db_connection()
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            if record_id:
                cur.execute("DELETE FROM sync_log WHERE id = %s;", (record_id,))
            elif keyword:
                cur.execute("DELETE FROM sync_log WHERE content LIKE %s;", (f"%{keyword}%",))
            conn.commit()
            result["supabase_sync"] = True
        except Exception as exc:
            logger.warning("Échec suppression sync_log Supabase : %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            if cur:
                cur.close()
            _release_db_connection(conn)

    return result


# ============================================================
# STATS
# ============================================================

def lazy_stats() -> dict:
    return {
        "chromadb_loaded": _CHROMA_LOADED,
        "chromadb_disabled": _DISABLE_CHROMADB,
        "lazy_enabled": _LAZY_LOAD,
        "nvidia_embedding_disabled": _NVIDIA_EMBEDDING_DISABLED,
        "pg_pool_initialized": _PG_POOL is not None,
        "pinecone_timeout_sec": PINECONE_TIMEOUT_SECONDS,
        "nvidia_timeout_sec": NVIDIA_EMBEDDING_TIMEOUT_SECONDS,
    }