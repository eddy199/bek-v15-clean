import os
import json
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path("/media/moh/84B00E0BB00E0500/workspacekimi")
ENV_FILE = ROOT / "env.txt"
ENV = {}

if ENV_FILE.exists():
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("="):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                ENV[key.strip()] = val.strip()

PROVIDER_NAMES = {
    "groq": "Groq",
    "nvidia": "NVIDIA"
}

# ─── GROQ : modèles actifs et stables (août 2026) ───
# Retirés : llama-3.3-70b-versatile (retiré par Groq le 16/08/2026),
# deepseek-r1-distill-llama-70b (décommissionné),
# compound-beta et compound-beta-mini (erreur 400 rôle message)
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
    "allam-2-7b"
]

# ─── NVIDIA NIM : modèles testés et fonctionnels (août 2026) ───
# Retirés : openai/gpt-oss-* (403 Forbidden), mistralai/* (410 Gone / 400),
# embeddings (404), et tous les modèles spécialisés audio/vision/bio/safety (404)
NVIDIA_ACTIVE_MODELS = [
    # Meta Llama
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3.2-11b-vision-instruct",
    "meta/llama-3.2-90b-vision-instruct",
    # NVIDIA Nemotron
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-nano-12b-v2-vl",
    "nvidia/nvidia-nemotron-nano-9b-v2",
    # Google
    "google/gemma-4-31b-it",
]

def configured_providers():
    providers = []
    if ENV.get("GROQ_API_KEY"): providers.append("groq")
    if ENV.get("NVIDIA_API_KEY"): providers.append("nvidia")
    return providers

def list_models(provider):
    if provider == "groq":
        return GROQ_MODELS
    elif provider == "nvidia":
        return NVIDIA_ACTIVE_MODELS
    return []

def _resolve_provider_and_key(provider, model):
    if model in NVIDIA_ACTIVE_MODELS or provider == "nvidia":
        key = ENV.get("NVIDIA_API_KEY", "")
        return "nvidia", key.strip() if key else "", "https://integrate.api.nvidia.com/v1"

    key = ENV.get("GROQ_API_KEY", "")
    return "groq", key.strip() if key else "", "https://api.groq.com/openai/v1"

async def call_ai_stream(messages, provider="groq", model=None):
    if isinstance(model, dict):
        model = model.get("id") or model.get("name")
        
    resolved_prov, key, base_url = _resolve_provider_and_key(provider, model)
    valid_models = GROQ_MODELS if resolved_prov == "groq" else NVIDIA_ACTIVE_MODELS
    
    if not model or model not in valid_models:
        model = valid_models[0]

    if not key:
        yield {"error": f"Clé API manquante pour {resolved_prov}."}
        return

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "BEK-Agent/15.0"
    }

    formatted = []
    for m in messages:
        if isinstance(m, dict) and "role" in m and "content" in m:
            content = m["content"]
            if isinstance(content, str) and content.strip():
                formatted.append({"role": m["role"], "content": content})
            elif isinstance(content, list) and len(content) > 0:
                formatted.append({"role": m["role"], "content": content})

    if not formatted:
        yield {"error": "Aucun message valide à envoyer."}
        return

    payload = {
        "model": str(model),
        "messages": formatted,
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 4096
    }

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in resp:
                line = line.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                if line == "data: [DONE]":
                    break
                try:
                    raw = line[5:].strip()
                    data = json.loads(raw)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    chunk = delta.get("content", "")
                    if chunk:
                        yield {"chunk": chunk, "model": model}
                except Exception:
                    continue
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        yield {"error": f"Erreur API ({e.code}) sur le modèle {model} : {err_body}"}
    except Exception as e:
        yield {"error": f"Erreur de connexion : {str(e)}"}

async def call_ai(messages, provider="groq", model=None):
    text = ""
    async for item in call_ai_stream(messages, provider=provider, model=model):
        if "chunk" in item:
            text += item["chunk"]
        elif "error" in item:
            return f"**Erreur :** {item['error']}"
    return text