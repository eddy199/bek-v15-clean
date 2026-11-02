# ==============================================================================
# BEK-v16 — Vision / Hugging Face Client
# ★ v26.1 : Fix style_preset auto confirmé (plus de cardboard_3d écrasé)
# ==============================================================================
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import requests
from werkzeug.utils import secure_filename

from core.paths import GENERATED_DIR
from services.prompt_optimizer import optimize_prompt_for_media

logger = logging.getLogger("bek.vision.huggingface")

def _get_hf_endpoints(model: str) -> Dict[str, Any]:
    from provider_manager import provider_manager
    return provider_manager.get_huggingface_image_endpoints(model)

def generate_image_with_huggingface(
    prompt: str,
    model: str = "hf-flux-schnell",
    output_filename: str = "",
    negative_prompt: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
    num_inference_steps: int = 4,
    guidance_scale: float = 0.0,
    optimize_prompt: bool = True,
) -> Dict[str, Any]:
    if not output_filename:
        output_filename = f"hf_image_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.abspath(os.path.join(GENERATED_DIR, secure_filename(output_filename)))

    final_prompt = prompt
    if optimize_prompt:
        try:
            # ★ FIX : "auto" au lieu de "cardboard_3d"
            final_prompt = optimize_prompt_for_media(prompt, media_type="image", style_preset="auto")
            logger.info("[vision.huggingface] Prompt optimisé : %s", final_prompt[:100])
        except Exception as e:
            logger.warning("[vision.huggingface] Optimisation prompt échouée : %s", e)

    ep = _get_hf_endpoints(model)
    predict_url = ep["predict_url"]
    headers = ep["headers"]

    payload: Dict[str, Any] = {"inputs": final_prompt, "parameters": {"width": width, "height": height, "num_inference_steps": num_inference_steps}}
    if guidance_scale > 0: payload["parameters"]["guidance_scale"] = guidance_scale
    if negative_prompt: payload["parameters"]["negative_prompt"] = negative_prompt

    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.post(predict_url, headers=headers, json=payload, timeout=120)
        except requests.Timeout:
            return {"status": "error", "message": "Timeout Hugging Face."}
        except requests.RequestException as e:
            return {"status": "error", "message": f"Erreur réseau Hugging Face : {e}"}

        if res.status_code == 200:
            with open(save_path, "wb") as f: f.write(res.content)
            return {"status": "success", "filepath": save_path, "filename": output_filename, "model_id": ep["model_id"], "provider": "huggingface", "size_bytes": len(res.content)}

        if res.status_code == 503:
            try: estimated = res.json().get("estimated_time", 10)
            except Exception: estimated = 10
            time.sleep(min(int(estimated), 30))
            continue

        if res.status_code == 429:
            return {"status": "error", "message": "Rate limit HF (429)."}

        try: err_txt = str(res.json())[:500]
        except Exception: err_txt = res.text[:500]
        return {"status": "error", "message": f"Hugging Face HTTP {res.status_code} : {err_txt}"}

    return {"status": "error", "message": "Hugging Face : échec après plusieurs tentatives."}

def edit_image_with_huggingface(
    image_path: str, prompt: str, model: str = "hf-sd-3.5-large",
    output_filename: str = "", strength: float = 0.75,
) -> Dict[str, Any]:
    if not os.path.exists(image_path): return {"status": "error", "message": f"Image source introuvable : {image_path}"}
    if not output_filename: output_filename = f"hf_edit_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.abspath(os.path.join(GENERATED_DIR, secure_filename(output_filename)))

    ep = _get_hf_endpoints(model)
    predict_url, headers = ep["predict_url"], ep["headers"]

    with open(image_path, "rb") as f: img_bytes = f.read()

    files = {"image": (os.path.basename(image_path), img_bytes, "image/png")}
    data = {"prompt": prompt, "strength": str(strength)}

    try:
        res = requests.post(predict_url, headers={"Authorization": headers["Authorization"]}, files=files, data=data, timeout=180)
    except requests.RequestException as e: return {"status": "error", "message": f"Erreur réseau HF : {e}"}

    if res.status_code == 200:
        with open(save_path, "wb") as f: f.write(res.content)
        return {"status": "success", "filepath": save_path, "filename": output_filename, "model_id": ep["model_id"], "provider": "huggingface"}

    try: err_txt = str(res.json())[:500]
    except Exception: err_txt = res.text[:500]
    return {"status": "error", "message": f"Hugging Face edit HTTP {res.status_code} : {err_txt}"}