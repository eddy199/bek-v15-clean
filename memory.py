
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


