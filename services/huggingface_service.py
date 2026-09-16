# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — PLUGIN HUGGING FACE PUISSANT v2.0
# Texte (streaming + fallback multi-modèles gratuits) • Image (FLUX/SDXL)
# ==============================================================================
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, Generator, List

import requests
from werkzeug.utils import secure_filename

try:
    from core.paths import FILES_DIR, GENERATED_DIR
except Exception:
    _WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    FILES_DIR = os.path.join(_WORKSPACE, "uploads")
    GENERATED_DIR = os.path.join(_WORKSPACE, "generated")

from provider_manager import provider_manager

HF_CHAT_ROUTER = "https://router.huggingface.co/v1/chat/completions"
HF_SERVERLESS = "https://api-inference.huggingface.co/models"

# Modèles texte serverless gratuits — essayés dans l'ordre en cas d'echec
HF_TEXT_MODELS: List[str] = [
    "microsoft/Phi-3.5-mini-instruct",
    "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "meta-llama/Llama-3.2-3B-Instruct",
]

# Modèles image serverless — fallback automatique
HF_IMAGE_MODELS: List[str] = [
    "black-forest-labs/FLUX.1-schnell",
    "stabilityai/stable-diffusion-xl-base-1.0",
]


def get_huggingface_api_key() -> str:
    """Recupère la clé Hugging Face via provider_manager ou l'environnement."""
    try:
        key = provider_manager.get_api_key("HUGGINGFACE_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("HUGGINGFACE_API_KEY", "")


def _hf_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {get_huggingface_api_key()}"}


# ---------------------------------------------------------------------------
# TEXTE — chat multi-modèles avec fallback automatique
# ---------------------------------------------------------------------------
def query_huggingface_text(
    prompt: str,
    model_id: str = "",
    max_new_tokens: int = 1024,
    temperature: float = 0.7,
    system_prompt: str = "",
) -> Dict[str, Any]:
    """Interroge Hugging Face (router OpenAI-compatible) avec fallback sur les modèles gratuits."""
    api_key = get_huggingface_api_key()
    if not api_key:
        return {"status": "error", "message": "HUGGINGFACE_API_KEY introuvable (env.txt ou .env)"}

    candidates: List[str] = ([model_id] if model_id else []) + [m for m in HF_TEXT_MODELS if m != model_id]
    attempts: List[str] = []

    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for model in candidates:
        try:
            resp = requests.post(
                HF_CHAT_ROUTER,
                headers={**_hf_headers(), "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_new_tokens,
                    "temperature": temperature,
                    "stream": False,
                },
                timeout=90,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                return {
                    "status": "success",
                    "model": model,
                    "response": text.strip(),
                    "attempts": attempts,
                }
            detail = resp.text[:180].replace("\n", " ")
            attempts.append(f"{model} -> HTTP {resp.status_code} : {detail}")
            if resp.status_code in (402, 403):
                attempts[-1] += " (modèle payant/licence — fallback vers un modèle gratuit)"
        except Exception as exc:
            attempts.append(f"{model} -> {exc}")
        time.sleep(0.4)

    return {
        "status": "error",
        "message": "Tous les modèles Hugging Face ont échoué. Derniers essais :\n" + "\n".join(attempts[-3:]),
        "attempts": attempts,
    }


def stream_huggingface_text(
    prompt: str,
    model_id: str = "",
    max_new_tokens: int = 1024,
    temperature: float = 0.7,
    system_prompt: str = "",
) -> Generator[Dict[str, Any], None, None]:
    """Version streaming du chat Hugging Face (yield {'chunk': ...} / {'done': True} / {'error': ...})."""
    api_key = get_huggingface_api_key()
    if not api_key:
        yield {"error": "HUGGINGFACE_API_KEY introuvable (env.txt ou .env)"}
        return

    candidates: List[str] = ([model_id] if model_id else []) + [m for m in HF_TEXT_MODELS if m != model_id]

    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for model in candidates:
        try:
            with requests.post(
                HF_CHAT_ROUTER,
                headers={**_hf_headers(), "Content-Type": "application/json", "Accept": "text/event-stream"},
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_new_tokens,
                    "temperature": temperature,
                    "stream": True,
                },
                stream=True,
                timeout=(10, 120),
            ) as resp:
                if resp.status_code != 200:
                    continue
                got_chunk = False
                for raw_line in resp.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    if not line.startswith("data:"):
                        continue
                    if line in ("data: [DONE]", "data:[DONE]"):
                        break
                    try:
                        payload = __import__("json").loads(line[5:].strip())
                        choices = payload.get("choices", [{}])
                        chunk = choices[0].get("delta", {}).get("content", "")
                        if chunk:
                            got_chunk = True
                            yield {"chunk": chunk, "model": model}
                    except Exception:
                        continue
                if got_chunk:
                    yield {"done": True, "model": model}
                    return
        except Exception:
            continue
        time.sleep(0.4)

    yield {"error": "Tous les modèles Hugging Face ont échoué (streaming)."}


# ---------------------------------------------------------------------------
# IMAGE — génération serverless avec fallback (FLUX.1-schnell -> SDXL)
# ---------------------------------------------------------------------------
def generate_image_hf(prompt: str, output_filename: str = "") -> Dict[str, Any]:
    """Génère une image via Hugging Face Inference (serverless), avec fallback multi-modèles."""
    api_key = get_huggingface_api_key()
    if not api_key:
        return {"status": "error", "message": "HUGGINGFACE_API_KEY introuvable (env.txt ou .env)"}

    if not output_filename:
        output_filename = f"hf_image_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.join(GENERATED_DIR, secure_filename(output_filename))

    attempts: List[str] = []
    for model in HF_IMAGE_MODELS:
        try:
            resp = requests.post(
                f"{HF_SERVERLESS}/{model}",
                headers=_hf_headers(),
                json={"inputs": prompt},
                timeout=180,
            )
            if resp.status_code == 200 and resp.content:
                ctype = resp.headers.get("Content-Type", "")
                if "image" in ctype:
                    with open(save_path, "wb") as fh:
                        fh.write(resp.content)
                    return {
                        "status": "success",
                        "filepath": save_path,
                        "filename": output_filename,
                        "model": model,
                        "message": f"Image générée via Hugging Face ({model})",
                    }
                attempts.append(f"{model} -> réponse non-image ({ctype})")
            elif resp.status_code == 503:
                attempts.append(f"{model} -> modèle en cours de chargement, réessayez dans ~30s")
            else:
                attempts.append(f"{model} -> HTTP {resp.status_code} : {resp.text[:140]}")
        except Exception as exc:
            attempts.append(f"{model} -> {exc}")
        time.sleep(0.5)

    return {
        "status": "error",
        "message": "Génération image Hugging Face échouée :\n" + "\n".join(attempts),
    }


# ---------------------------------------------------------------------------
# DIAGNOSTIC — ping chaque modèle pour savoir lesquels marchent avec VOTRE clé
# ---------------------------------------------------------------------------
def diagnose_hf_plugin() -> Dict[str, Any]:
    """Teste rapidement chaque modèle et retourne un rapport 'OK' / 'HTTP xxx'."""
    api_key = get_huggingface_api_key()
    if not api_key:
        return {"status": "error", "message": "HUGGINGFACE_API_KEY introuvable (env.txt ou .env)"}

    import json as _json
    report: Dict[str, str] = {}
    for m in HF_TEXT_MODELS:
        try:
            r = requests.post(
                HF_CHAT_ROUTER,
                headers={**_hf_headers(), "Content-Type": "application/json"},
                json={"model": m, "messages": [{"role": "user", "content": "Say OK"}], "max_tokens": 5},
                timeout=45,
            )
            report[m] = "OK" if r.status_code == 200 else f"HTTP {r.status_code} : {r.text[:120]}"
        except Exception as e:
            report[m] = f"ERR : {e}"
        time.sleep(0.3)

    return {"status": "success", "api_key": "présente" if api_key else "absente", "report": report}


# ---------------------------------------------------------------------------
# RETRO-COMPATIBILITÉ — app.py importe ce nom au démarrage
# ---------------------------------------------------------------------------
def query_huggingface_model(
    prompt: str,
    model_id: str = "",
    max_new_tokens: int = 512,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """Ancien nom conservé pour ne pas casser app.py — délègue au plugin v2."""
    return query_huggingface_text(
        prompt=prompt,
        model_id=model_id,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
    )
