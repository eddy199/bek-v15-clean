# ==============================================================================
# BEK-v16 — Vision / Image Analysis (v31)
# ------------------------------------------------------------------------------
# ★ v31 (2026-10-07) : FIX PERMISSION DENIED + RÉSOLUTION ROBUSTE
#   - _resolve_image_path() gère maintenant [Errno 13] Permission denied
#   - Fallback ultime sur uploads/ (là où sont les fichiers attachés)
#   - Logs détaillés pour diagnostiquer les chemins
#   - Fix hallucinations agent (voir prompts.py v2.5)
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

# ★ v31 — Dossier uploads (là où les fichiers attachés sont stockés)
UPLOADS_DIR = os.path.join(WORKSPACE_DIR, "uploads")


# ==============================================================================
# HELPERS
# ==============================================================================
def _get_api_key(key_name: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.get_api_key(key_name)


def _safe_listdir(directory: str) -> list:
    """
    ★ v31 — listdir SÉCURISÉ qui ne crash pas sur permission denied.
    Retourne [] au lieu de lever [Errno 13].
    """
    if not directory or not os.path.exists(directory):
        return []
    try:
        return os.listdir(directory)
    except PermissionError:
        logger.warning("[vision] Permission denied sur %s — skip", directory)
        return []
    except Exception as e:
        logger.warning("[vision] Erreur listdir %s : %s", directory, e)
        return []


def _get_latest_media_file(
    directory: str,
    extensions: tuple = (".png", ".jpg", ".jpeg", ".webp", ".mp4"),
) -> Optional[str]:
    """Retourne le fichier média le plus récent d'un dossier (version safe)."""
    entries = _safe_listdir(directory)
    if not entries:
        return None

    try:
        candidates = [
            os.path.join(directory, f)
            for f in entries
            if f.lower().endswith(extensions) and not f.startswith(".")
            and not f.startswith("_temp_")
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return candidates[0]
    except Exception as e:
        logger.warning("[vision] Erreur latest_media_file : %s", e)
        return None


def _resolve_image_path(image_path: str) -> Optional[str]:
    """
    ★ v31 — Résout le chemin absolu d'une image avec fallbacks robustes.

    Ordre de recherche :
      1. Chemin absolu direct (si commence par / ou C:\\ ou F:\\)
      2. WORKSPACE_DIR / image_path
      3. UPLOADS_DIR / basename(image_path)     ← ★ v31 NOUVEAU
      4. GENERATED_DIR / basename(image_path)
      5. FILES_DIR / basename(image_path)
      6. Fallback : dernière image de UPLOADS_DIR ← ★ v31
      7. Fallback : dernière image de GENERATED_DIR
    """
    if not image_path:
        return None

    # Nettoie le chemin (supprime espaces parasites)
    image_path = str(image_path).strip().strip("\"'")

    # ─── 1. Chemin absolu direct ───
    if os.path.isabs(image_path) and os.path.exists(image_path):
        logger.info("[vision] Chemin absolu trouvé : %s", image_path)
        return image_path

    # ─── 2. WORKSPACE_DIR / image_path ───
    try:
        target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, image_path))
        # ⚠️ Ne PAS tester os.path.exists sur le dossier racine seul
        if target_path != WORKSPACE_DIR and os.path.exists(target_path):
            logger.info("[vision] Chemin workspace trouvé : %s", target_path)
            return target_path
    except (PermissionError, OSError) as e:
        logger.warning("[vision] Erreur resolution workspace : %s", e)

    # ─── 3-5. Chercher dans uploads/, generated/, files/ ───
    basename = os.path.basename(image_path)
    if basename:
        for base_dir in (UPLOADS_DIR, GENERATED_DIR, FILES_DIR):
            try:
                candidate = os.path.join(base_dir, basename)
                if os.path.exists(candidate):
                    logger.info("[vision] Chemin trouvé dans %s : %s", base_dir, candidate)
                    return candidate
            except (PermissionError, OSError) as e:
                logger.warning("[vision] Erreur accès %s : %s", base_dir, e)
                continue

    # ─── 6. Fallback : dernière image d'uploads/ ───
    latest_uploads = _get_latest_media_file(
        UPLOADS_DIR, (".png", ".jpg", ".jpeg", ".webp")
    )
    if latest_uploads:
        logger.info("[vision] Fallback uploads/ : %s", latest_uploads)
        return latest_uploads

    # ─── 7. Fallback : dernière image de generated/ ───
    latest_generated = _get_latest_media_file(
        GENERATED_DIR, (".png", ".jpg", ".jpeg", ".webp")
    )
    if latest_generated:
        logger.info("[vision] Fallback generated/ : %s", latest_generated)
        return latest_generated

    logger.warning("[vision] ❌ Aucun chemin trouvé pour : %r", image_path)
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
# PROVIDER 1 — NVIDIA NIM VISION
# ==============================================================================
def _analyze_with_nvidia(
    image_path: str,
    prompt_text: str,
    mime_type: str,
    encoded_image: str,
) -> Optional[str]:
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

        # ★ v31 — Log détaillé si erreur
        if res.status_code == 401:
            logger.error(
                "[vision.nvidia] ❌ 401 Unauthorized — la clé NVIDIA_API_KEY est "
                "EXPIRÉE. Régénère-la sur https://build.nvidia.com"
            )
        else:
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
# PROVIDER 2 — GEMINI VISION
# ==============================================================================
def _analyze_with_gemini(
    image_path: str,
    prompt_text: str,
    mime_type: str,
    encoded_image: str,
) -> Optional[str]:
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
                logger.warning("[vision.gemini] Structure inattendue : %s", e)

        logger.warning(
            "[vision.gemini] HTTP %s : %s",
            res.status_code, res.text[:300],
        )
        return None

    except Exception as e:
        logger.warning("[vision.gemini] Erreur : %s", e)
        return None


# ==============================================================================
# PROVIDER 3 — HUGGING FACE
# ==============================================================================
def _analyze_with_huggingface(
    image_path: str,
    prompt_text: str,
) -> Optional[str]:
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
    """
    # 1. Résoudre le chemin (v31 robuste)
    target_path = _resolve_image_path(image_path)
    if not target_path or not os.path.exists(target_path):
        logger.warning("[vision] Image introuvable : %s", image_path)
        return (
            f"Erreur analyse vision : image introuvable.\n"
            f"Chemin tenté : {image_path}\n"
            f"Vérifiez que le fichier existe dans uploads/ ou generated/."
        )

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
        return (
            "❌ Aucun provider vision n'a pu analyser cette image.\n\n"
            "**Causes possibles :**\n"
            "- Clé `NVIDIA_API_KEY` expirée (voir https://build.nvidia.com)\n"
            "- Clé `GEMINI_API_KEY` révoquée\n"
            "- Rate limit atteint\n\n"
            "**Solution :** régénérer la clé NVIDIA puis redémarrer le serveur."
        )

    except Exception as e:
        logger.exception("[vision] Erreur analyse")
        return f"Erreur analyse vision : {str(e)}"