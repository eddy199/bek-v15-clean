# ==============================================================================
# BEK-v16 — Vision / Pollinations Client
# ------------------------------------------------------------------------------
# ★ v28.21 (2026-11-17) — FIX ROOT CAUSE : 
#   - Suppression totale de l'appel à optimize_prompt_for_media.
#   - Le prompt est envoyé tel quel (déjà traduit par le LLM choisi par l'utilisateur).
# ==============================================================================
from __future__ import annotations

import logging
import os
import re
import time
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional

import requests
from werkzeug.utils import secure_filename

from core.paths import GENERATED_DIR

logger = logging.getLogger("bek.vision.pollinations")

POLLINATIONS_MODELS: Dict[str, str] = {
    "flux":         "flux",
    "flux-3d":      "flux-3d",
    "flux-realism": "flux-realism",
    "flux-anime":   "flux-anime",
    "any-dark":     "any-dark",
    "turbo":        "turbo",
}

def list_pollinations_models() -> List[str]:
    return list(POLLINATIONS_MODELS.keys())

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
POLLINATIONS_ENDPOINTS: List[str] = [
    "https://image.pollinations.ai/prompt",
    "https://pollinations.ai/p",
]

_USER_AGENTS: List[str] = [
    "BEK-Agent/1.0 (+https://bek-v15-clean.onrender.com)",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def _normalize_prompt_spacing(prompt: str) -> str:
    """Nettoie les espaces et la ponctuation résiduelle (ex: ", .")."""
    if not prompt or not isinstance(prompt, str):
        return prompt

    text = prompt
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r',\s*\.', '.', text)  # Corrige ", ." en "."
    text = re.sub(r',([^\s])', r', \1', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = text.strip()
    if text and not text.endswith('.'):
        text += '.'
    return text

def _build_headers(attempt: int = 0) -> Dict[str, str]:
    return {
        "User-Agent": _USER_AGENTS[attempt % len(_USER_AGENTS)],
        "Accept": "image/png,image/jpeg,image/webp,image/*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }

def _detect_placeholder_response(content_bytes: bytes) -> bool:
    if len(content_bytes) < 100:
        return True
    if b'<html' in content_bytes[:200].lower() or b'<!doctype' in content_bytes[:200].lower():
        return True
    if content_bytes[:4] == b'\x89PNG':
        return False
    if content_bytes[:2] == b'\xff\xd8':
        return False
    if content_bytes[:4] == b'RIFF' and content_bytes[8:12] == b'WEBP':
        return False
    if content_bytes[:6] in (b'GIF87a', b'GIF89a'):
        return False
    return True

def generate_image_with_pollinations(
    prompt: str,
    model: str = "flux",
    output_filename: str = "",
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
    enhance: bool = False,
    nologo: bool = True,
    private: bool = True,
    max_retries: int = 5,
    timeout: int = 120,
) -> Dict[str, Any]:
    
    if not prompt or not prompt.strip():
        return {"status": "error", "message": "Prompt vide."}

    # ★ FIX : On ne fait QUE nettoyer. Pas d'optimisation, pas de traduction.
    final_prompt = _normalize_prompt_spacing(prompt.strip())
    logger.info("[vision.pollinations] Prompt final envoyé : %r", final_prompt)

    if not output_filename:
        output_filename = f"gen_image_{uuid.uuid4().hex[:8]}.png"
    safe_name = secure_filename(output_filename)
    save_path = os.path.join(str(GENERATED_DIR), safe_name)

    encoded_prompt = urllib.parse.quote(final_prompt, safe="")
    last_error = ""
    total_attempts = 0

    for endpoint in POLLINATIONS_ENDPOINTS:
        url = (
            f"{endpoint}/{encoded_prompt}"
            f"?width={width}&height={height}&model={model}"
            f"&nologo={'true' if nologo else 'false'}"
            f"&private={'true' if private else 'false'}"
            f"&enhance={'true' if enhance else 'false'}"
        )
        if seed is not None:
            url += f"&seed={seed}"

        for attempt in range(1, max_retries + 1):
            total_attempts += 1
            try:
                logger.info("[vision.pollinations] Tentative %d/%d (endpoint=%s)...", attempt, max_retries, endpoint.split("//")[-1].split("/")[0])
                response = requests.get(url, timeout=timeout, stream=True, headers=_build_headers(attempt - 1))

                if response.status_code == 200:
                    content = response.content
                    if _detect_placeholder_response(content):
                        last_error = "Placeholder d'erreur reçu"
                        logger.warning("[vision.pollinations] %s — retry %d/%d", last_error, attempt, max_retries)
                    else:
                        with open(save_path, "wb") as f:
                            f.write(content)
                        size_bytes = os.path.getsize(save_path)
                        logger.info("[vision.pollinations] ✅ OK : %s (%d bytes) en %d tentative(s)", safe_name, size_bytes, attempt)
                        return {
                            "status": "success",
                            "filepath": save_path,
                            "filename": safe_name,
                            "model_id": model,
                            "provider": "pollinations",
                            "size_bytes": size_bytes,
                            "attempts": total_attempts,
                            "seed": seed or 0,
                            "fallback_chain": ["pollinations"],
                            "total_attempts": total_attempts,
                            "prompt": final_prompt,
                        }
                elif response.status_code in (402, 429):
                    last_error = f"HTTP {response.status_code} (rate limit/server)"
                    logger.warning("[vision.pollinations] %s — retry %d/%d", last_error, attempt, max_retries)
                else:
                    last_error = f"HTTP {response.status_code}"
                    logger.warning("[vision.pollinations] %s — retry %d/%d", last_error, attempt, max_retries)

            except Exception as exc:
                last_error = str(exc)
                logger.warning("[vision.pollinations] Exception %s — retry %d/%d", last_error, attempt, max_retries)

            if attempt < max_retries:
                time.sleep(5)

    logger.error("[vision.pollinations] ❌ Échec après %d tentatives", total_attempts)
    return {
        "status": "error",
        "message": f"Pollinations surchargé : {last_error}",
        "total_attempts": total_attempts,
        "prompt": final_prompt,
    }

def pollinations_generate_image(*args, **kwargs) -> Dict[str, Any]:
    return generate_image_with_pollinations(*args, **kwargs)

generate_pollinations_image = generate_image_with_pollinations