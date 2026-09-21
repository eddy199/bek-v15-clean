# ==============================================================================
# BEK-v16 — Vision / Hugging Face Client
# ------------------------------------------------------------------------------
# Client Hugging Face Inference API pour la génération d'images.
#   - generate_image_with_huggingface() : text-to-image
#   - edit_image_with_huggingface()     : image-to-image (img2img)
#
# v25 (2026-09-21) : Création initiale
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


# ==============================================================================
# HELPERS INTERNES
# ==============================================================================
def _get_hf_endpoints(model: str) -> Dict[str, Any]:
    """Récupère les endpoints HF via le provider_manager."""
    from provider_manager import provider_manager
    return provider_manager.get_huggingface_image_endpoints(model)


# ==============================================================================
# GÉNÉRATION D'IMAGE (text-to-image)
# ==============================================================================
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
    """
    Génère une image via Hugging Face Inference API.

    Args:
        prompt      : description de l'image (FR ou EN)
        model       : nom court UI ("hf-flux-schnell") ou ID officiel
        output_filename : nom du fichier de sortie
        negative_prompt : ce qu'il ne faut PAS voir
        width, height  : dimensions (défaut 1024x1024)
        num_inference_steps : étapes d'inférence (FLUX.1-schnell: 4)
        guidance_scale : force du prompt (FLUX.1-schnell: 0.0)
        optimize_prompt : optimiser le prompt via prompt_optimizer

    Returns:
        {"status": "success", "filepath": ..., "filename": ..., "model_id": ...}
        ou {"status": "error", "message": ...}
    """
    if not output_filename:
        output_filename = f"hf_image_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.abspath(
        os.path.join(GENERATED_DIR, secure_filename(output_filename))
    )

    # Optimisation du prompt
    final_prompt = prompt
    if optimize_prompt:
        try:
            final_prompt = optimize_prompt_for_media(
                prompt, media_type="image", style_preset="cardboard_3d"
            )
            logger.info(
                "[vision.huggingface] Prompt optimisé : %s", final_prompt[:100]
            )
        except Exception as e:
            logger.warning(
                "[vision.huggingface] Optimisation prompt échouée : %s", e
            )

    ep = _get_hf_endpoints(model)
    predict_url = ep["predict_url"]
    headers = ep["headers"]

    logger.info(
        "[vision.huggingface] generate : model=%s prompt=%r",
        ep["model_id"], final_prompt[:80],
    )

    # Payload HF
    payload: Dict[str, Any] = {
        "inputs": final_prompt,
        "parameters": {
            "width": width,
            "height": height,
            "num_inference_steps": num_inference_steps,
        },
    }

    # FLUX.1-schnell n'utilise PAS guidance_scale (guidance=0)
    if guidance_scale > 0:
        payload["parameters"]["guidance_scale"] = guidance_scale

    if negative_prompt:
        payload["parameters"]["negative_prompt"] = negative_prompt

    # Retry sur 503 (modèle en chargement) — max 3 tentatives
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.post(
                predict_url,
                headers=headers,
                json=payload,
                timeout=120,
            )
        except requests.Timeout:
            return {
                "status": "error",
                "message": "Timeout Hugging Face (modèle trop lent ou surchargé).",
            }
        except requests.RequestException as e:
            return {
                "status": "error",
                "message": f"Erreur réseau Hugging Face : {e}",
            }

        # Succès : HF renvoie les bytes PNG directement
        if res.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(res.content)
            logger.info(
                "[vision.huggingface] OK : %s (%d bytes)",
                output_filename, len(res.content),
            )
            return {
                "status": "success",
                "filepath": save_path,
                "filename": output_filename,
                "model_id": ep["model_id"],
                "provider": "huggingface",
                "size_bytes": len(res.content),
            }

        # Modèle en chargement → attendre et retenter
        if res.status_code == 503:
            try:
                err = res.json()
                estimated = err.get("estimated_time", 10)
            except Exception:
                estimated = 10
            wait_s = min(int(estimated), 30)
            logger.info(
                "[vision.huggingface] Modèle en chargement, attente %ds "
                "(tentative %d/%d)...",
                wait_s, attempt + 1, max_retries,
            )
            time.sleep(wait_s)
            continue

        # Rate limit → message clair
        if res.status_code == 429:
            return {
                "status": "error",
                "message": (
                    "Rate limit Hugging Face atteint (429). "
                    "Attends quelques minutes ou utilise un autre provider."
                ),
            }

        # Autres erreurs
        try:
            err_data = res.json()
            err_txt = str(err_data)[:500]
        except Exception:
            err_txt = res.text[:500]

        logger.error(
            "[vision.huggingface] HTTP %s : %s", res.status_code, err_txt
        )
        return {
            "status": "error",
            "message": f"Hugging Face HTTP {res.status_code} : {err_txt}",
        }

    return {
        "status": "error",
        "message": "Hugging Face : échec après plusieurs tentatives (503 persistant).",
    }


# ==============================================================================
# ÉDITION D'IMAGE (image-to-image)
# ==============================================================================
def edit_image_with_huggingface(
    image_path: str,
    prompt: str,
    model: str = "hf-sd-3.5-large",
    output_filename: str = "",
    strength: float = 0.75,
) -> Dict[str, Any]:
    """
    Édite une image existante via Hugging Face (img2img).

    Args:
        image_path : chemin de l'image source
        prompt     : description de la modification
        model      : modèle HF img2img
        strength   : 0.0 (rien) → 1.0 (tout changer)

    Returns:
        {"status": "success", "filepath": ..., ...}
    """
    if not os.path.exists(image_path):
        return {
            "status": "error",
            "message": f"Image source introuvable : {image_path}",
        }

    if not output_filename:
        output_filename = f"hf_edit_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.abspath(
        os.path.join(GENERATED_DIR, secure_filename(output_filename))
    )

    ep = _get_hf_endpoints(model)
    predict_url = ep["predict_url"]
    headers = ep["headers"]

    # Lire l'image
    with open(image_path, "rb") as f:
        img_bytes = f.read()

    logger.info(
        "[vision.huggingface] edit : model=%s source=%s",
        ep["model_id"], os.path.basename(image_path),
    )

    # HF img2img attend multipart/form-data avec l'image + params
    files = {
        "image": (os.path.basename(image_path), img_bytes, "image/png"),
    }
    data = {
        "prompt": prompt,
        "strength": str(strength),
    }

    try:
        res = requests.post(
            predict_url,
            headers={"Authorization": headers["Authorization"]},
            files=files,
            data=data,
            timeout=180,
        )
    except requests.RequestException as e:
        return {"status": "error", "message": f"Erreur réseau HF : {e}"}

    if res.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(res.content)
        return {
            "status": "success",
            "filepath": save_path,
            "filename": output_filename,
            "model_id": ep["model_id"],
            "provider": "huggingface",
        }

    try:
        err_txt = str(res.json())[:500]
    except Exception:
        err_txt = res.text[:500]

    return {
        "status": "error",
        "message": f"Hugging Face edit HTTP {res.status_code} : {err_txt}",
    }