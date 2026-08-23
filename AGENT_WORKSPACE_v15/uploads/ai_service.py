import asyncio
import json
import requests
from config import MODELS, NVIDIA_MODELS, NVIDIA_API_KEY, logger

_ai_clients = {}

PROVIDER_NAMES = {
    "nvidia": "NVIDIA",
    "groq": "Groq",
}


def make_client(base_url, api_key):
    """Crée un client OpenAI-compatible Async."""
    from openai import AsyncOpenAI
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def get_client(provider):
    """Récupère le client configuré."""
    cfg = MODELS.get(provider)
    if not cfg or not cfg.get("key") or not cfg.get("base_url"):
        return None
    if provider not in _ai_clients:
        _ai_clients[provider] = make_client(cfg["base_url"], cfg["key"])
    return _ai_clients.get(provider)


def configured_providers():
    return [p for p, c in MODELS.items() if c.get("key")]


def provider_name(provider):
    return PROVIDER_NAMES.get(provider, provider)


def fetch_models(provider):
    cfg = MODELS.get(provider)
    if not cfg or not cfg.get("key"):
        return []
    url = cfg["base_url"].rstrip("/") + "/models"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {cfg['key']}"}, timeout=20)
        if r.ok:
            data = r.json()
            items = data.get("data", data if isinstance(data, list) else [])
            models = [i.get("id") for i in items if isinstance(i, dict) and i.get("id")]
            return sorted(set(models))
        else:
            logger.warning(f"fetch models {provider}: HTTP {r.status_code}")
    except Exception as e:
        logger.error(f"fetch models {provider}: {e}")
    return []


def list_models(provider):
    if provider == "nvidia":
        base = [m["model"] for m in NVIDIA_MODELS]
    else:
        base = [MODELS[provider]["model"]] if MODELS.get(provider) else []
    fetched = fetch_models(provider)
    seen = set()
    out = []
    for m in base + fetched:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def is_multimodal_model(model_name):
    if not model_name:
        return False
    m = model_name.lower()
    return any(k in m for k in ["vision", "-vl", "4o", "gemini", "paligemma", "claude-3", "fuyu", "kosmos", "deplot"])


def get_nvidia_key_for_model(model_name):
    """Récupère la clé dédiée au modèle ou la clé principale NVIDIA."""
    for item in NVIDIA_MODELS:
        if item.get("model") == model_name and item.get("key"):
            return item["key"]
    return NVIDIA_API_KEY or MODELS.get("nvidia", {}).get("key", "")


async def call_ai_stream(conv, provider="nvidia", model=None, base_url=None, api_key=None,
                         max_tokens=4096, temperature=0.7):
    """Streaming multi-provider strict (NVIDIA et Groq uniquement)."""
    
    # 1. Détection d'images dans les messages
    has_image = any(
        isinstance(m.get("content"), list) and any(isinstance(p, dict) and p.get("type") == "image_url" for p in m["content"])
        for m in conv if isinstance(m, dict)
    )

    # 2. Routage forcé sur NVIDIA Vision si une image est présente
    if has_image:
        provider = "nvidia"
        if not is_multimodal_model(model):
            model = "meta/llama-3.2-11b-vision-instruct"

    # 3. Chaîne de priorité des providers
    providers_to_try = [provider]
    if provider == "nvidia" and MODELS.get("groq", {}).get("key") and not has_image:
        providers_to_try.append("groq")
    elif provider == "groq" and MODELS.get("nvidia", {}).get("key"):
        providers_to_try.append("nvidia")

    last_error = None

    for prov in providers_to_try:
        cfg = MODELS.get(prov)
        if not cfg:
            continue

        if prov == provider and model:
            mdl = model
        else:
            mdl = cfg.get("model")

        is_model_vision = is_multimodal_model(mdl)

        if has_image and not is_model_vision:
            continue

        adapted_conv = []
        for msg in conv:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "user")
            content = msg.get("content")

            if isinstance(content, list):
                if is_model_vision:
                    adapted_conv.append(msg)
                else:
                    txt_parts = []
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                txt_parts.append(part.get("text", ""))
                            elif part.get("type") == "image_url":
                                txt_parts.append("[Capture d'écran / Image]")
                    adapted_conv.append({"role": role, "content": " ".join(txt_parts)})
            else:
                adapted_conv.append({"role": role, "content": content or ""})

        if prov == "nvidia":
            key = get_nvidia_key_for_model(mdl) or api_key
            url = "https://integrate.api.nvidia.com/v1"
        else:
            key = api_key if (prov == provider and api_key) else cfg.get("key")
            url = base_url if (prov == provider and base_url) else cfg.get("base_url")

        if not key or not url:
            continue

        try:
            client = make_client(url, key)
            response = await client.chat.completions.create(
                model=mdl,
                messages=adapted_conv,
                stream=True,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield {"chunk": chunk.choices[0].delta.content}

            yield {"meta": {"provider": prov, "provider_name": provider_name(prov),
                            "model": mdl, "status": "ok"}}
            return

        except Exception as e:
            err_str = str(e)
            logger.warning(f"Erreur provider {prov} avec modèle {mdl}: {err_str}")
            last_error = f"[{prov} - {mdl}] {err_str}"
            
            # Secours immédiat sur la clé générale NVIDIA si échec d'un modèle NVIDIA spécifique
            if prov == "nvidia" and key != NVIDIA_API_KEY and NVIDIA_API_KEY:
                try:
                    client_main = make_client(url, NVIDIA_API_KEY)
                    response = await client_main.chat.completions.create(
                        model=mdl,
                        messages=adapted_conv,
                        stream=True,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    async for chunk in response:
                        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            yield {"chunk": chunk.choices[0].delta.content}
                    yield {"meta": {"provider": prov, "provider_name": provider_name(prov),
                                    "model": mdl, "status": "ok"}}
                    return
                except Exception as e_main:
                    last_error = f"[{prov} - {mdl}] {e_main}"
            continue

    if last_error:
        yield {"error": f"Erreur d'appel API : {last_error}"}
    else:
        yield {"error": "Aucun provider valide configuré."}


async def call_ai(conv, provider="nvidia", model=None, base_url=None, api_key=None,
                  max_tokens=2000, temperature=0.7):
    text = ""
    async for item in call_ai_stream(conv, provider=provider, model=model,
                                     base_url=base_url, api_key=api_key,
                                     max_tokens=max_tokens, temperature=temperature):
        if "chunk" in item:
            text += item["chunk"]
        elif "error" in item:
            return item["error"]
    return text