# ==============================================================================
# BEK-v16 — Vision / Image Analysis
# ------------------------------------------------------------------------------
# Analyse d'image via Gemini Vision
# v28 (2026-09-20) : Extraction depuis vision_legacy.py
# ==============================================================================
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

import requests

from core.paths import FILES_DIR, GENERATED_DIR, WORKSPACE_DIR
from services.vision.constants import GEMINI_API_BASE

logger = logging.getLogger("bek.vision.image_analysis")


# ==============================================================================
# HELPERS
# ==============================================================================
def _get_api_key(key_name: str) -> str:
    """Récupère une clé API via le provider_manager (import tardif)."""
    from provider_manager import provider_manager
    return provider_manager.get_api_key(key_name)


def _get_latest_media_file(
    directory: str,
    extensions: tuple = (".png", ".jpg", ".jpeg", ".webp", ".mp4"),
) -> Optional[str]:
    """Retourne le fichier média le plus récent d'un dossier."""
    if not os.path.exists(directory):
        return None
    try:
        candidates = [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if f.lower().endswith(extensions) and not f.startswith(".")
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return candidates[0]
    except Exception:
        return None


# ==============================================================================
# ANALYSE IMAGE
# ==============================================================================
def analyze_image_with_vision(
    image_path: str,
    prompt: str = "",
    provider: str = "gemini",
    model: str = "",
) -> str:
    """
    Analyse une image avec Gemini Vision.

    Args:
        image_path: chemin de l'image (relatif à WORKSPACE_DIR, ou nom de fichier)
        prompt: question à poser sur l'image
        provider: "gemini" (seul supporté pour l'instant)
        model: modèle Gemini (optionnel)

    Returns:
        Description textuelle ou message d'erreur
    """
    target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, image_path))
    if not os.path.exists(target_path):
        for d in [GENERATED_DIR, FILES_DIR]:
            alt = os.path.join(d, os.path.basename(image_path))
            if os.path.exists(alt):
                target_path = alt
                break

    if not os.path.exists(target_path):
        latest = _get_latest_media_file(
            GENERATED_DIR, (".png", ".jpg", ".jpeg", ".webp")
        )
        target_path = latest if latest else target_path

    try:
        with open(target_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode("utf-8")

        ext = target_path.split(".")[-1].lower()
        mime_type = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
        }.get(ext, "image/png")

        prompt_text = prompt or (
            "Analyse cette image avec un niveau de détail extrême : identité des "
            "personnages, expressions faciales, barbe poivre et sel, yeux bleus "
            "perçants, vêtements, textures 3D style carton, arrière-plan, texte."
        )

        api_key = _get_api_key("GEMINI_API_KEY")
        if api_key:
            url = (
                f"{GEMINI_API_BASE}/models/gemini-2.5-flash-image:generateContent"
                f"?key={api_key}"
            )
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt_text},
                        {"inline_data": {"mime_type": mime_type, "data": encoded_image}},
                    ]
                }]
            }
            res = requests.post(url, json=payload, timeout=45)
            if res.status_code == 200:
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                logger.warning(
                    "[vision.image_analysis] Gemini HTTP %s: %s",
                    res.status_code, res.text[:300],
                )
    except Exception as e:
        return f"Erreur analyse vision : {str(e)}"
    return "Échec analyse image."