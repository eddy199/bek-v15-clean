"""
BEK-v15.2 HYBRID
Memory Layer (Dual Hybrid: ChromaDB Local + Pinecone Cloud + Neon PostgreSQL)
-----------------------------------------------------------------------------
Couche mémoire locale / Pinecone / Neon PostgreSQL / ChromaDB.

Responsabilités :
- Chargement sécurisé de la configuration via provider_manager et env.txt ;
- Gestion des embeddings (NVIDIA API avec fallback déterministe) ;
- Mémoire vectorielle hybride : Pinecone (distant) + ChromaDB (local) ;
- Connexion PostgreSQL / Neon DB ;
- Journalisation et normalisation des entrées.

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

NEON_DATABASE_URL = _env("DATABASE_URL", _env("NEON_DATABASE_URL", ""))


# ============================================================
# LIMITS & TIMEOUTS
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


# ============================================================
# EMBEDDINGS
# ============================================================

def _fallback_embedding(text: str, target_dim: int = DEFAULT_EMBEDDING_DIM) -> List[float]:
    """Embedding local déterministe de secours SHA-256."""
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
    """Génère un embedding NVIDIA si disponible avec fallback déterministe."""
    text = clean_string(text)
    if not text:
        return []

    if target_dim <= 0:
        logger.warning("Dimension d'embedding invalide: %s", target_dim)
        return []

    text = text[:MAX_EMBEDDING_INPUT_LENGTH]

    if NVIDIA_API_KEY:
        try:
            url = "https://integrate.api.nvidia.com/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "input": [text],
                "model": "nvidia/embeddings-nv-embed-qa-4",
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

            if isinstance(data, list) and data and isinstance(data[0], dict):
                embedding = data[0].get("embedding")
                if isinstance(embedding, list) and embedding:
                    vector = [float(value) for value in embedding]
                    if vector:
                        return vector

            logger.warning("NVIDIA a retourné un embedding invalide.")
        except Exception as exc:
            logger.warning("Embedding NVIDIA indisponible : %s. Bascule sur fallback local.", exc)

    return _fallback_embedding(text, target_dim=target_dim)


# ============================================================
# CHROMADB (LOCAL HYBRID FALLBACK & PERSISTENCE)
# ============================================================

_CHROMA_CLIENT = None


def get_chroma_collection():
    """Initialise et retourne la collection locale persistante ChromaDB."""
    global _CHROMA_CLIENT
    try:
        import chromadb
        from chromadb.config import Settings

        if _CHROMA_CLIENT is None:
            _CHROMA_CLIENT = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=Settings(anonymized_telemetry=False),
            )
        return _CHROMA_CLIENT.get_or_create_collection(
            name="bek_memory_local",
            metadata={"hnsw:space": "cosine"},
        )
    except ImportError:
        logger.debug("ChromaDB non installé localement.")
        return None
    except Exception as exc:
        logger.error("Erreur initialisation ChromaDB local : %s", exc)
        return None


# ============================================================
# PINECONE
# ============================================================

def get_pinecone_index() -> Optional[Any]:
    """Retourne l'index Pinecone configuré."""
    if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        return None

    try:
        from pinecone import Pinecone

        client = Pinecone(api_key=PINECONE_API_KEY)
        return client.Index(PINECONE_INDEX_NAME)
    except ImportError:
        logger.error("Le package 'pinecone' n'est pas installé.")
        return None
    except Exception as exc:
        logger.error("Erreur d'initialisation Pinecone: %s", exc)
        return None


# ============================================================
# MEMORY SEARCH (HYBRIDE DUAL)
# ============================================================

def search_memory(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> str:
    """Recherche duale : Pinecone (Cloud) avec fallback automatique ChromaDB (Local)."""
    query = clean_string(query)
    if not query:
        return ""

    top_k = _safe_top_k(top_k)
    vector = get_embedding(query, input_type="query")
    if not vector:
        return ""

    # 1. Tentative Pinecone Cloud
    index = get_pinecone_index()
    if index is not None:
        try:
            logger.info("Recherche mémoire Pinecone | query_len=%d | top_k=%d", len(query), top_k)
            response = index.query(vector=vector, top_k=top_k, include_metadata=True)
            matches = getattr(response, "matches", []) or response.get("matches", [])
            if matches:
                context_lines = []
                for match in matches:
                    metadata = getattr(match, "metadata", {}) or match.get("metadata", {})
                    date_val = clean_string(metadata.get("date", "Inconnue"))
                    text_val = clean_string(metadata.get("text", ""))
                    if text_val:
                        context_lines.append(f"- Date: {date_val} | Info: {text_val}")
                if context_lines:
                    return "\n".join(context_lines)
        except Exception as exc:
            logger.warning("Erreur recherche Pinecone : %s. Bascule sur ChromaDB local.", exc)

    # 2. Fallback ChromaDB Local
    chroma_coll = get_chroma_collection()
    if chroma_coll is not None:
        try:
            logger.info("Recherche mémoire ChromaDB local | top_k=%d", top_k)
            res = chroma_coll.query(query_embeddings=[vector], n_results=top_k)
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            lines = []
            for doc, meta in zip(docs, metas):
                d_val = meta.get("date", "Inconnue") if isinstance(meta, dict) else "Inconnue"
                lines.append(f"- Date: {d_val} | Info: {doc}")
            if lines:
                return "\n".join(lines)
        except Exception as exc:
            logger.error("Erreur recherche ChromaDB local: %s", exc)

    return ""


# ============================================================
# MEMORY SAVE (HYBRIDE DUAL)
# ============================================================

def save_to_memory(
    user_query: str,
    agent_response: str,
) -> bool:
    """Sauvegarde simultanée dans Pinecone (Cloud) et ChromaDB (Local)."""
    user_query = clean_string(user_query)
    agent_response = clean_string(agent_response)

    if not user_query and not agent_response:
        return False

    combined_text = clean_string(f"Requête: {user_query}\nRéponse: {agent_response[:1000]}")
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

    saved = False

    # 1. Upsert Pinecone Cloud
    index = get_pinecone_index()
    if index is not None:
        try:
            index.upsert(
                vectors=[{"id": record_id, "values": vector, "metadata": metadata}]
            )
            saved = True
            logger.info("Interaction enregistrée dans Pinecone | id=%s", record_id)
        except Exception as exc:
            logger.warning("Échec sauvegarde Pinecone: %s", exc)

    # 2. Upsert ChromaDB Local
    chroma_coll = get_chroma_collection()
    if chroma_coll is not None:
        try:
            chroma_coll.upsert(
                ids=[record_id],
                embeddings=[vector],
                documents=[combined_text],
                metadatas=[{"date": now_iso, "type": "conversation"}],
            )
            saved = True
            logger.info("Interaction enregistrée dans ChromaDB local | id=%s", record_id)
        except Exception as exc:
            logger.warning("Échec sauvegarde ChromaDB: %s", exc)

    return saved


# ============================================================
# DATABASE / NEON
# ============================================================

def get_db_connection() -> Optional[Any]:
    """Connexion directe à Neon PostgreSQL."""
    if not NEON_DATABASE_URL:
        logger.warning("DATABASE_URL / NEON_DATABASE_URL non configuré.")
        return None

    try:
        import psycopg2
    except ImportError:
        logger.error("psycopg2 non installé.")
        return None

    try:
        connection = psycopg2.connect(
            NEON_DATABASE_URL,
            connect_timeout=DATABASE_CONNECT_TIMEOUT_SECONDS,
        )
        return connection
    except Exception as exc:
        logger.error("Erreur connexion Neon DB: %s", exc)
        return None
