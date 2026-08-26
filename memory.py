import os
import sys
import json
import logging
import requests
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

ROOT = Path("/media/moh/84B00E0BB00E0500/workspacekimi")
ENV = {}

env_file = ROOT / "env.txt"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("="):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                ENV[key.strip()] = val.strip()

def _env(key, default=""):
    return ENV.get(key, os.getenv(key, default))

GROQ_API_KEY = _env("GROQ_API_KEY", "")
NVIDIA_API_KEY = _env("NVIDIA_API_KEY", "")
PINECONE_API_KEY = _env("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = _env("PINECONE_INDEX_NAME", "bek-memory")
# Prise en charge automatique de DATABASE_URL ou NEON_DATABASE_URL
NEON_DATABASE_URL = _env("DATABASE_URL", _env("NEON_DATABASE_URL", ""))

WS_DIR = ROOT
SKILLS_DIR = ROOT / "skills"
PLUGINS_DIR = ROOT / "plugins"
UPLOAD_DIR = WS_DIR / "uploads"
GENERATED_DIR = ROOT / "generated"

for d in [SKILLS_DIR, PLUGINS_DIR, UPLOAD_DIR, GENERATED_DIR]:
    d.mkdir(exist_ok=True)

logger = logging.getLogger('BEKAgent')
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = RotatingFileHandler(ROOT / 'bek_agent.log', maxBytes=10_000_000, backupCount=5, encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

def clean_string(text: str) -> str:
    if not text: return ""
    return "".join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))

def get_embedding(text: str, input_type: str = "query", target_dim: int = 1024) -> list:
    text = clean_string(text)
    if not text:
        return []

    if NVIDIA_API_KEY:
        try:
            url = "https://integrate.api.nvidia.com/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "input": [text[:2000]],
                "model": "nvidia/embeddings-nv-embed-qa-4",
                "input_type": input_type
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=5)
            if resp.status_code == 200:
                return resp.json()["data"][0]["embedding"]
        except Exception:
            pass

    import hashlib
    import math
    vector = [0.0] * target_dim
    words = text.lower().split()
    if not words:
        words = [text.lower()]
        
    for i, word in enumerate(words):
        h = int(hashlib.sha256(word.encode('utf-8')).hexdigest(), 16)
        idx = h % target_dim
        weight = 1.0 / math.sqrt(i + 1)
        vector[idx] += weight

    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0:
        vector = [x / norm for x in vector]
    return vector

def get_pinecone_index():
    if not PINECONE_API_KEY:
        return None
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        return pc.Index(PINECONE_INDEX_NAME)
    except Exception as e:
        logger.error(f"Erreur d'initialisation Pinecone: {e}")
        return None

def search_memory(query: str, top_k: int = 2) -> str:
    index = get_pinecone_index()
    if not index:
        return ""
        
    query = clean_string(query)
    logger.info(f"Recherche Pinecone pour : {query}")
    
    vector = get_embedding(query, input_type="query")
    if not vector:
        return ""
        
    try:
        results = index.query(vector=vector, top_k=top_k, include_metadata=True)
        matches = results.get("matches", [])
        if not matches:
            return ""
        
        context = ""
        for match in matches:
            meta = match.get("metadata", {})
            context += f"- Date: {meta.get('date', 'Inconnue')} | Info: {meta.get('text', '')}\n"
        return context
    except Exception as e:
        logger.error(f"Erreur lors de la recherche Pinecone: {e}")
        return ""

def save_to_memory(user_query: str, agent_response: str):
    index = get_pinecone_index()
    if not index:
        return False
    
    logger.info("Enregistrement de l'interaction en mémoire Pinecone...")
    combined_text = f"Requête: {user_query}\nRéponse: {agent_response[:1000]}"
    combined_text = clean_string(combined_text)
    
    vector = get_embedding(combined_text, input_type="passage")
    if not vector:
        return False
        
    try:
        import datetime
        record_id = str(uuid.uuid4())
        metadata = {
            "text": combined_text,
            "date": datetime.datetime.now().isoformat(),
            "type": "conversation"
        }
        index.upsert(vectors=[{"id": record_id, "values": vector, "metadata": metadata}])
        logger.info("Interaction sauvegardée avec succès.")
        return True
    except Exception as e:
        logger.error(f"Erreur d'upsert Pinecone: {e}")
        return False

def get_db_connection():
    """Connexion directe à Neon PostgreSQL."""
    if not NEON_DATABASE_URL:
        logger.warning("DATABASE_URL non configuré.")
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(NEON_DATABASE_URL)
        return conn
    except ImportError:
        logger.warning("psycopg2 non installé.")
        return None
    except Exception as e:
        logger.error(f"Erreur de connexion Neon DB: {e}")
        return None
