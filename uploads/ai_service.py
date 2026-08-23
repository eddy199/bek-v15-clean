import os
import json
import urllib.request
import urllib.error
from config import MODELS, NVIDIA_MODELS, ENV, logger

PROVIDER_NAMES = {
    "groq": "Groq",
    "nvidia": "NVIDIA"
}

# Modèles confirmés 100% fonctionnels sur Groq
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b"
]

# Modèles confirmés 100% fonctionnels sur NVIDIA
NVIDIA_ACTIVE_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b",
    "meta/llama-3.2-11b-vision-instruct",
    "nvidia/nvidia-nemotron-nano-9b-v2"
]

def configured_providers():
    return [pid for pid, cfg in MODELS.items() if cfg.get("key") or ENV.get(f"{pid.upper()}_API_KEY")]

def list_models(provider):
    if provider == "groq":
        return GROQ_MODELS
    elif provider == "nvidia":
        return NVIDIA_ACTIVE_MODELS
    return []

def fetch_models(provider):
    return list_models(provider)

def _resolve_provider_and_key(provider, model):
    if model in NVIDIA_ACTIVE_MODELS or provider == "nvidia":
        key = None
        if NVIDIA_MODELS:
            for nm in NVIDIA_MODELS:
                if isinstance(nm, dict) and nm.get("model") == model and nm.get("key"):
                    key = nm.get("key").strip()
                    break
        if not key:
            key = ENV.get("NVIDIA_API_KEY") or MODELS.get("nvidia", {}).get("key") or os.getenv("NVIDIA_API_KEY", "")
        return "nvidia", key.strip() if key else "", "https://integrate.api.nvidia.com/v1"

    key = ENV.get("GROQ_API_KEY") or MODELS.get("groq", {}).get("key") or os.getenv("GROQ_API_KEY", "")
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
        "User-Agent": "BEK-Agent/1.0"
    }

    # Nettoyage strict des messages pour éliminer le contenu vide (évite erreur 400)
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
        "temperature": 0.6,
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
        logger.error(f"Inference stream error: {e}")
        yield {"error": f"Erreur de connexion : {str(e)}"}

async def call_ai(messages, provider="groq", model=None):
    text = ""
    async for item in call_ai_stream(messages, provider=provider, model=model):
        if "chunk" in item:
            text += item["chunk"]
        elif "error" in item:
            return f"**Erreur :** {item['error']}"
    return text