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
NEON_DATABASE_URL = _env("NEON_DATABASE_URL", "") 

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

# --- NOUVEAU FILTRE ANTI-CRASH EMOJI ---
def clean_string(text: str) -> str:
    """Supprime les caractères orphelins (surrogates) qui font crasher Python et NVIDIA."""
    if not text: return ""
    return "".join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))

def get_embedding(text: str) -> list:
    """Génère un vecteur d'embedding via NVIDIA NIM."""
    if not NVIDIA_API_KEY:
        logger.warning("Clé NVIDIA manquante pour l'embedding.")
        return []
        
    text = clean_string(text) # Nettoyage de sécurité
    
    try:
        url = "https://integrate.api.nvidia.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": [text[:2000]], 
            "model": "nvidia/nv-embedqa-e5-v5",
            "input_type": "query"
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()["data"][0]["embedding"]
        else:
            logger.error(f"Erreur API Embedding: {resp.text}")
    except Exception as e:
        logger.error(f"Exception Embedding NVIDIA: {e}")
    return []

def get_pinecone_index():
    """Initialise et retourne l'index Pinecone."""
    if not PINECONE_API_KEY:
        return None
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        return pc.Index(PINECONE_INDEX_NAME)
    except ImportError:
        logger.warning("Package 'pinecone-client' non installé.")
        return None
    except Exception as e:
        logger.error(f"Erreur d'initialisation Pinecone: {e}")
        return None

def search_memory(query: str, top_k: int = 2) -> str:
    """Interroge la base de données vectorielle avec la requête utilisateur."""
    index = get_pinecone_index()
    if not index:
        return ""
        
    query = clean_string(query) # Nettoyage de sécurité
    logger.info(f"Recherche Pinecone pour : {query}")
    
    vector = get_embedding(query)
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
    """Enregistre l'interaction dans Pinecone pour la persistance à long terme."""
    index = get_pinecone_index()
    if not index:
        return False
    
    logger.info("Enregistrement de l'interaction en mémoire Pinecone...")
    combined_text = f"Requête: {user_query}\nRéponse: {agent_response[:1000]}"
    combined_text = clean_string(combined_text) # Nettoyage de sécurité
    
    vector = get_embedding(combined_text)
    
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
    """Prépare la connexion à Neon PostgreSQL pour les manipulations CRM."""
    if not NEON_DATABASE_URL:
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(NEON_DATABASE_URL)
        return conn
    except ImportError:
        logger.warning("psycopg2 non installé. Accès à Neon DB désactivé.")
        return None
    except Exception as e:
        logger.error(f"Erreur de connexion Neon DB: {e}")
        return None