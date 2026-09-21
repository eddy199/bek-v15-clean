# ==============================================================================
# BEK-v16 — Vision / Image Generation
# ------------------------------------------------------------------------------
# Génération d'image via plusieurs providers :
#   1. Gemini (défaut) — haute qualité, nécessite GEMINI_API_KEY
#   2. Pollinations (fallback) — gratuit, illimité, sans clé API
#   3. Hugging Face (optionnel) — nécessite du crédit HF
#
#   - Fusion d'images (merge_and_edit_images)
#
# v28 (2026-09-20) : Extraction depuis vision_legacy.py
# v25 (2026-09-21) : Routage Hugging Face ajouté
# v26 (2026-09-21) : Routage Pollinations ajouté
# v27 (2026-09-21) : Gemini par défaut + Pollinations fallback
# ==============================================================================
from __future__ import annotations

import base64
import logging
import os
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional, Union

import requests
from werkzeug.utils import secure_filename

from core.paths import FILES_DIR, GENERATED_DIR, WORKSPACE_DIR
from services.prompt_optimizer import optimize_prompt_for_media
from services.vision.constants import GEMINI_API_BASE
from services.vision.image_analysis import analyze_image_with_vision

logger = logging.getLogger("bek.vision.image_generation")


# ==============================================================================
# HELPERS
# ==============================================================================
def _get_api_key(key_name: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.get_api_key(key_name)


def _resolve_model_id(model_name: str) -> str:
    """Convertit un nom court en model ID officiel Gemini."""
    from provider_manager import provider_manager
    return provider_manager.resolve_model_id(model_name)


def _resolve_existing_media_paths(
    paths_input: Union[str, List[str], None],
    extensions: tuple,
) -> List[str]:
    """Résout une liste de chemins d'images existants."""
    resolved: List[str] = []
    raw_list = [paths_input] if isinstance(paths_input, str) else (paths_input or [])

    for raw in raw_list:
        if not raw or not isinstance(raw, str):
            continue
        clean_name = os.path.basename(raw.strip("\"' \r\n"))
        for base_dir in [GENERATED_DIR, FILES_DIR, WORKSPACE_DIR]:
            candidate = os.path.abspath(os.path.join(base_dir, clean_name))
            if os.path.exists(candidate) and os.path.isfile(candidate):
                resolved.append(candidate)
                break

    if not resolved:
        from services.vision.image_analysis import _get_latest_media_file
        latest = (
            _get_latest_media_file(GENERATED_DIR, extensions)
            or _get_latest_media_file(FILES_DIR, extensions)
        )
        if latest:
            resolved.append(latest)
    return resolved


# ==============================================================================
# GÉNÉRATION D'IMAGE
# ==============================================================================
def generate_image_with_provider(
    prompt: str,
    provider: str = "pollinations",
    model: str = "flux-3d",
    output_filename: str = "",
    **kwargs,
) -> Dict[str, Any]:
    """
    Génère une image via le provider spécifié.

    Providers supportés :
      - "gemini"       : Gemini Image (défaut, haute qualité)
      - "pollinations" : Pollinations.ai (gratuit, illimité)
      - "huggingface"  : Hugging Face Inference API (crédit requis)

    Returns:
        {"status": "success", "filepath": ..., "filename": ..., "model_id": ...}
        ou {"status": "error", "message": ...}
    """
    if not output_filename:
        output_filename = f"gen_image_{uuid.uuid4().hex[:8]}.png"

    provider_lower = provider.lower()

    # ══════════════════════════════════════════════════════════════════════
    # ★ v27 — ROUTAGE GEMINI (par défaut, haute qualité)
    # ══════════════════════════════════════════════════════════════════════
    if provider_lower == "gemini":
        logger.info(
            "[vision.image_generation] Routage Gemini : model=%s", model
        )
        save_path = os.path.abspath(
            os.path.join(GENERATED_DIR, secure_filename(output_filename))
        )

        enhanced_prompt = optimize_prompt_for_media(
            prompt, media_type="image", style_preset="cardboard_3d"
        )

        if not model or model in ("flux-3d", "flux"):
            model = "gemini-3.1-flash-image"
        model_id = _resolve_model_id(model)

        try:
            api_key = _get_api_key("GEMINI_API_KEY")
            if api_key:
                url_gen = (
                    f"{GEMINI_API_BASE}/models/{model_id}:generateContent?key={api_key}"
                )
                payload_gen = {
                    "contents": [{"parts": [{"text": enhanced_prompt}]}],
                    "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
                }
                res = requests.post(url_gen, json=payload_gen, timeout=60)
                if res.status_code == 200:
                    data = res.json()
                    parts = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [])
                    )
                    for part in parts:
                        inline = part.get("inline_data") or part.get("inlineData")
                        if inline and inline.get("data"):
                            img_bytes = base64.b64decode(inline["data"])
                            with open(save_path, "wb") as f:
                                f.write(img_bytes)
                            return {
                                "status": "success",
                                "filepath": save_path,
                                "filename": output_filename,
                                "model_id": model_id,
                                "provider": "gemini",
                            }
                else:
                    logger.warning(
                        "[vision.image_generation] Gemini HTTP %s: %s",
                        res.status_code, res.text[:300],
                    )
        except Exception as e:
            logger.warning(
                "[vision.image_generation] Erreur Gemini : %s", e
            )

        # Fallback automatique sur Pollinations
        logger.info(
            "[vision.image_generation] Gemini échoue → fallback Pollinations"
        )
        from services.vision.pollinations_client import generate_image_with_pollinations
        return generate_image_with_pollinations(
            prompt=prompt,
            model="flux-3d",
            output_filename=output_filename,
        )

    # ══════════════════════════════════════════════════════════════════════
    # ROUTAGE POLLINATIONS (fallback gratuit)
    # ══════════════════════════════════════════════════════════════════════
    if provider_lower == "pollinations":
        from services.vision.pollinations_client import generate_image_with_pollinations
        logger.info(
            "[vision.image_generation] Routage Pollinations : model=%s", model
        )
        if not model or model.startswith("gemini-"):
            model = "flux-3d"
        return generate_image_with_pollinations(
            prompt=prompt,
            model=model,
            output_filename=output_filename,
            **kwargs,
        )

    # ══════════════════════════════════════════════════════════════════════
    # ROUTAGE HUGGING FACE (optionnel)
    # ══════════════════════════════════════════════════════════════════════
    if provider_lower == "huggingface":
        from services.vision.huggingface_client import generate_image_with_huggingface
        logger.info(
            "[vision.image_generation] Routage Hugging Face : model=%s", model
        )
        if not model or model in ("gemini-3.1-flash-image", "gemini-2.5-flash-image", "flux-3d"):
            model = "hf-flux-schnell"
        return generate_image_with_huggingface(
            prompt=prompt,
            model=model,
            output_filename=output_filename,
            **kwargs,
        )

    # ══════════════════════════════════════════════════════════════════════
    # FALLBACK FINAL : Pollinations
    # ══════════════════════════════════════════════════════════════════════
    logger.warning(
        "[vision.image_generation] Provider inconnu '%s' → Pollinations", provider
    )
    from services.vision.pollinations_client import generate_image_with_pollinations
    return generate_image_with_pollinations(
        prompt=prompt,
        model="flux-3d",
        output_filename=output_filename,
    )


# ==============================================================================
# FUSION D'IMAGES
# ==============================================================================
def merge_and_edit_images(
    image_paths: Any = None,
    user_prompt: str = "",
    prompt: str = "",
    provider: str = "gemini",
    model: str = "gemini-3.1-flash-image",
) -> Dict[str, Any]:
    """
    Fusionne/édite des images.

    Providers supportés :
      - "gemini"       : analyse d'image Gemini + regénération (défaut)
      - "pollinations" : utilise le prompt + contexte pour générer
      - "huggingface"  : utilise edit_image_with_huggingface (img2img)
    """
    try:
        active_prompt = user_prompt or prompt or "Modifier l'image."
        valid_paths = _resolve_existing_media_paths(
            image_paths, (".png", ".jpg", ".jpeg", ".webp")
        )

        # ══════════════════════════════════════════════════════════════════════
        # ROUTAGE HUGGING FACE (img2img)
        # ══════════════════════════════════════════════════════════════════════
        if provider.lower() == "huggingface" and valid_paths:
            from services.vision.huggingface_client import edit_image_with_huggingface
            logger.info(
                "[vision.image_generation] Routage HF img2img : %s",
                os.path.basename(valid_paths[0]),
            )
            if not model or model == "gemini-3.1-flash-image":
                model = "hf-sd-3.5-large"
            return edit_image_with_huggingface(
                image_path=valid_paths[0],
                prompt=active_prompt,
                model=model,
            )

        # ══════════════════════════════════════════════════════════════════════
        # ROUTAGE GEMINI (analyse + fusion) — DÉFAUT
        # ══════════════════════════════════════════════════════════════════════
        if provider.lower() == "gemini":
            analysis_context = ""
            if valid_paths:
                analysis_context = analyze_image_with_vision(
                    valid_paths[0],
                    "Décris précisément les traits du visage, la barbe poivre et sel, "
                    "les yeux bleus perçants, le style cartonné 3D et les personnages.",
                )
            fusion_prompt = (
                f"Reference visual analysis: {analysis_context}\n\n"
                f"Required modification: {active_prompt}. "
                f"Maintain strict identity continuity, facial features (barbe poivre "
                f"et sel, yeux bleus perçants), 3D cardboard cutout craft material, "
                f"and vibrant studio lighting."
            )
            return generate_image_with_provider(
                fusion_prompt, provider="gemini", model=model
            )

        # ══════════════════════════════════════════════════════════════════════
        # POLLINATIONS (avec contexte descriptif)
        # ══════════════════════════════════════════════════════════════════════
        fusion_prompt = active_prompt
        if valid_paths:
            fusion_prompt = (
                f"{active_prompt}. "
                f"Maintain continuity with the original image: same character, "
                f"same colors, same style, same environment."
            )
        return generate_image_with_provider(
            fusion_prompt, provider="pollinations", model="flux-3d"
        )
    except Exception as e:
        return {"status": "error", "message": f"Erreur fusion visuelle : {str(e)}"}