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
OPENROUTER_API_KEY = _env("OPENROUTER_API_KEY", "")
PINECONE_API_KEY = _env("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = _env("PINECONE_INDEX_NAME", "bek-memory")
FLASK_SECRET_KEY = _env("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

AGENT_NAME = "BEK-v15-HYBRID"

MODELS = {
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "nvidia/llama-3.3-nemotron-super-49b-v1",
        "key": NVIDIA_API_KEY
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
        "key": GROQ_API_KEY
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openrouter/auto",
        "key": OPENROUTER_API_KEY
    }
}

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