# ==============================================================================
# BEK-v16 — Vision / Image Analysis
# ------------------------------------------------------------------------------
# Analyse d'image via plusieurs providers vision :
#   1. NVIDIA NIM (prioritaire — llama-3.2-11b-vision)
#   2. Gemini (fallback — gemini-2.5-flash-image)
#   3. Hugging Face (fallback final)
#
# v28 (2026-09-20) : Extraction depuis vision_legacy.py
# v30 (2026-09-29) : Ajout NVIDIA Vision prioritaire + multi-fallback
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
# CONFIGURATION PROVIDERS
# ==============================================================================

NVIDIA_VISION_MODEL = "meta/llama-3.2-11b-vision-instruct"
NVIDIA_VISION_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

GEMINI_VISION_MODEL = "gemini-2.5-flash-image"


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


def _resolve_image_path(image_path: str) -> Optional[str]:
    """Résout le chemin absolu d'une image."""
    # 1. Chemin absolu direct
    target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, image_path))
    if os.path.exists(target_path):
        return target_path

    # 2. Chercher dans GENERATED_DIR et FILES_DIR
    for d in [GENERATED_DIR, FILES_DIR]:
        alt = os.path.join(d, os.path.basename(image_path))
        if os.path.exists(alt):
            return alt

    # 3. Fallback : dernière image générée
    latest = _get_latest_media_file(
        GENERATED_DIR, (".png", ".jpg", ".jpeg", ".webp")
    )
    if latest:
        return latest

    return None


def _get_mime_type(path: str) -> str:
    """Retourne le mime type d'une image."""
    ext = path.split(".")[-1].lower()
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(ext, "image/png")


def _read_image_base64(path: str) -> str:
    """Lit une image et la retourne en base64."""
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


# ==============================================================================
# PROVIDER 1 — NVIDIA NIM VISION (prioritaire)
# ==============================================================================
def _analyze_with_nvidia(
    image_path: str,
    prompt_text: str,
    mime_type: str,
    encoded_image: str,
) -> Optional[str]:
    """
    Analyse une image avec NVIDIA NIM vision.

    Returns:
        str: description, ou None si échec
    """
    api_key = _get_api_key("NVIDIA_API_KEY")
    if not api_key:
        logger.debug("[vision.nvidia] Pas de NVIDIA_API_KEY — skip")
        return None

    try:
        payload = {
            "model": NVIDIA_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{encoded_image}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.3,
            "stream": False,
        }

        res = requests.post(
            NVIDIA_VISION_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=60,
        )

        if res.status_code == 200:
            data = res.json()
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    logger.info(
                        "[vision.nvidia] ✅ Analyse OK (%d chars)",
                        len(content),
                    )
                    return content.strip()

        logger.warning(
            "[vision.nvidia] HTTP %s : %s",
            res.status_code, res.text[:300],
        )
        return None

    except requests.Timeout:
        logger.warning("[vision.nvidia] Timeout")
        return None
    except Exception as e:
        logger.warning("[vision.nvidia] Erreur : %s", e)
        return None


# ==============================================================================
# PROVIDER 2 — GEMINI VISION (fallback)
# ==============================================================================
def _analyze_with_gemini(
    image_path: str,
    prompt_text: str,
    mime_type: str,
    encoded_image: str,
) -> Optional[str]:
    """
    Analyse une image avec Gemini Vision.

    Returns:
        str: description, ou None si échec
    """
    api_key = _get_api_key("GEMINI_API_KEY")
    if not api_key:
        logger.debug("[vision.gemini] Pas de GEMINI_API_KEY — skip")
        return None

    try:
        url = (
            f"{GEMINI_API_BASE}/models/{GEMINI_VISION_MODEL}:generateContent"
            f"?key={api_key}"
        )
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt_text},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": encoded_image,
                        }
                    },
                ]
            }]
        }
        res = requests.post(url, json=payload, timeout=45)

        if res.status_code == 200:
            data = res.json()
            try:
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                if content:
                    logger.info(
                        "[vision.gemini] ✅ Analyse OK (%d chars)",
                        len(content),
                    )
                    return content.strip()
            except (KeyError, IndexError) as e:
                logger.warning(
                    "[vision.gemini] Structure inattendue : %s", e,
                )

        logger.warning(
            "[vision.gemini] HTTP %s : %s",
            res.status_code, res.text[:300],
        )
        return None

    except requests.Timeout:
        logger.warning("[vision.gemini] Timeout")
        return None
    except Exception as e:
        logger.warning("[vision.gemini] Erreur : %s", e)
        return None


# ==============================================================================
# PROVIDER 3 — HUGGING FACE (fallback final)
# ==============================================================================
def _analyze_with_huggingface(
    image_path: str,
    prompt_text: str,
) -> Optional[str]:
    """
    Analyse une image avec Hugging Face (BLIP-2).
    Mode fallback uniquement.

    Returns:
        str: description, ou None si échec
    """
    hf_key = _get_api_key("HUGGINGFACE_API_KEY")
    if not hf_key:
        return None

    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        url = (
            "https://api-inference.huggingface.co/models/"
            "Salesforce/blip-image-captioning-large"
        )
        res = requests.post(
            url,
            headers={"Authorization": f"Bearer {hf_key}"},
            data=img_bytes,
            timeout=45,
        )

        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and data:
                caption = data[0].get("generated_text", "")
                if caption:
                    logger.info("[vision.hf] ✅ Analyse OK")
                    return caption.strip()

        return None

    except Exception as e:
        logger.debug("[vision.hf] Erreur : %s", e)
        return None


# ==============================================================================
# ANALYSE IMAGE — DISPATCHER PRINCIPAL
# ==============================================================================
def analyze_image_with_vision(
    image_path: str,
    prompt: str = "",
    provider: str = "auto",
    model: str = "",
) -> str:
    """
    Analyse une image avec un provider vision (NVIDIA → Gemini → HF).

    Args:
        image_path: chemin de l'image (relatif à WORKSPACE_DIR, ou nom de fichier)
        prompt: question à poser sur l'image
        provider: "auto" (défaut), "nvidia", "gemini", "huggingface"
        model: modèle spécifique (ignoré si auto)

    Returns:
        Description textuelle ou message d'erreur
    """
    # 1. Résoudre le chemin
    target_path = _resolve_image_path(image_path)
    if not target_path or not os.path.exists(target_path):
        logger.warning("[vision] Image introuvable : %s", image_path)
        return f"Erreur analyse vision : image introuvable ({image_path})"

    # 2. Préparer le prompt
    prompt_text = prompt or (
        "Décris cette image en détail : identité des personnages, "
        "expressions faciales, couleurs de cheveux, yeux, barbe, vêtements, "
        "arrière-plan, ambiance générale."
    )

    try:
        encoded_image = _read_image_base64(target_path)
        mime_type = _get_mime_type(target_path)

        logger.info(
            "[vision] Analyse : %s (provider=%s)",
            os.path.basename(target_path), provider,
        )

        # 3. Router selon le provider
        if provider in ("auto", "nvidia"):
            result = _analyze_with_nvidia(
                target_path, prompt_text, mime_type, encoded_image,
            )
            if result:
                return result
            if provider == "nvidia":
                return "Échec analyse image (NVIDIA vision)"

        if provider in ("auto", "gemini"):
            result = _analyze_with_gemini(
                target_path, prompt_text, mime_type, encoded_image,
            )
            if result:
                return result
            if provider == "gemini":
                return "Échec analyse image (Gemini vision)"

        if provider in ("auto", "huggingface"):
            result = _analyze_with_huggingface(target_path, prompt_text)
            if result:
                return result

        # 4. Aucun provider n'a fonctionné
        logger.warning("[vision] Tous les providers vision ont échoué")
        return "Échec analyse image (tous les providers vision ont échoué)"

    except Exception as e:
        logger.exception("[vision] Erreur analyse")
        return f"Erreur analyse vision : {str(e)}"