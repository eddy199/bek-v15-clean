import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

ROOT = Path(__file__).parent.resolve()
ENV = {}

env_file = ROOT / ".env.txt"
if not env_file.exists():
    env_file = ROOT / "env.txt"
if not env_file.exists():
    env_file = ROOT / ".env"
ENV_FILE = env_file

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
FLASK_SECRET_KEY = _env("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

AGENT_NAME = "BEK-v15-HYBRID"
AGENT_AUTHOR = "Bek Mohammed"

# Fournisseurs actifs
MODELS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
        "key": GROQ_API_KEY
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "nvidia/nemotron-3-super-120b-a12b",
        "key": NVIDIA_API_KEY
    }
}

# Chargement dynamique des modèles NVIDIA déclarés dans env.txt
NVIDIA_MODELS = []

for key, val in ENV.items():
    if (
        key.startswith("meta/")
        or key.startswith("nvidia/")
        or key.startswith("openai/")
        or key.startswith("mistralai/")
        or key.startswith("google/")
        or key.startswith("nv-")
        or key in [
            "paligemma",
            "esm2-650m",
            "esmfold",
            "riva-translate-4b-instruct-v1",
            "Background-Noise-Removal",
            "Studio-Voice",
            "llama-3.1-nemotron-safety-guard-8b-v3",
            "solar-10.7b-instruct",
            "Bevformer",
            "Sparsedrive"
        ]
    ):
        NVIDIA_MODELS.append({
            "id": key,
            "model": key,
            "key": val or NVIDIA_API_KEY,
            "base_url": "https://integrate.api.nvidia.com/v1"
        })

WS_DIR = ROOT / "AGENT_WORKSPACE_v15"
SKILLS_DIR = ROOT / "skills"
PLUGINS_DIR = ROOT / "plugins"
UPLOAD_DIR = WS_DIR / "uploads"
GENERATED_DIR = ROOT / "generated"

for d in [WS_DIR, SKILLS_DIR, PLUGINS_DIR, UPLOAD_DIR, GENERATED_DIR]:
    d.mkdir(exist_ok=True)

logger = logging.getLogger('BEKAgent')
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = RotatingFileHandler('bek_agent.log', maxBytes=10_000_000, backupCount=5, encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)