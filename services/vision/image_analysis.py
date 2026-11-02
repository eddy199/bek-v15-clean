# ==============================================================================
# BEK-v19 — Vision / Image Analysis (v35.2)
# ------------------------------------------------------------------------------
# ★ v35.2 (2026-10-21) — 90B RETIRÉ (timeout systématique sur tier gratuit)
#   - 11B seul → analyse en ~4s au lieu de 64s (60s de timeout 90B + 4s 11B)
#   - La qualité du 11B est suffisante (photo plage : description correcte)
# ★ v35.1 (2026-10-21) — TIMEOUT AJUSTÉ (60s, 1 tentative sur 90B)
# ★ v35 (2026-10-21) — MODÈLE 90B EN PRIORITÉ (fallback 11B)
# ★ v34 (2026-10-21) — FIX NVIDIA TIMEOUT + HF RETIRÉ
# ★ v33 (2026-10-20) — FALLBACK TOUJOURS ACTIF
# ★ v32 (2026-10-07) — FORCE LA LANGUE FRANÇAISE
# ==============================================================================
from __future__ import annotations

import base64
import logging
import os
import time
from typing import Optional, Tuple

import requests

from core.paths import FILES_DIR, GENERATED_DIR, WORKSPACE_DIR
from services.vision.constants import GEMINI_API_BASE

logger = logging.getLogger("bek.vision.image_analysis")


# ==============================================================================
# CONFIGURATION PROVIDERS
# ==============================================================================

# ★ v35.2 — 11B seul (90B timeout systématique sur tier gratuit NVIDIA)
# Format : (model_name, timeout_s, max_retries)
NVIDIA_VISION_MODELS = (
    ("meta/llama-3.2-11b-vision-instruct", 60, 1),   # ← seul modèle actif
)
NVIDIA_VISION_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
GEMINI_VISION_MODEL = "gemini-2.5-flash-image"

# ★ v35 — Backoff entre tentatives (appliqué pour chaque modèle)
NVIDIA_RETRY_BACKOFF = 3

# ★ v35 — HF retiré (endpoint DNS mort)
VISION_PROVIDERS = ("nvidia", "gemini")

UPLOADS_DIR = os.path.join(WORKSPACE_DIR, "uploads")


# ==============================================================================
# DÉTECTION DE LANGUE
# ==============================================================================

_LANG_FR_MARKERS = [
    "décris", "decris", "décrit", "décrire",
    "cette", "cet", "ceci", "celle", "celui",
    "image", "photo", "capture", "écran", "ecran",
    "détail", "detail", "détaillé", "detaille",
    "en français", "français", "francais",
    "explique", "analyse", "analyser",
    "que vois", "que vois-tu", "peux-tu", "peux tu",
    "montre", "regarde", "vois", "voir",
    "personnage", "homme", "femme", "visage", "couleur",
    "arrière-plan", "arriere plan", "ambiance",
]

_LANG_EN_MARKERS = [
    "describe", "this", "that", "the", "image", "photo", "picture",
    "detail", "detailed", "explain", "analyze", "what",
    "person", "man", "woman", "face", "color", "background",
    "in english", "english",
]


def _detect_language(text: str) -> str:
    if not text or not isinstance(text, str):
        return "fr"
    text_lower = text.lower()
    fr_score = sum(1 for m in _LANG_FR_MARKERS if m in text_lower)
    en_score = sum(1 for m in _LANG_EN_MARKERS if m in text_lower)
    if fr_score >= en_score and fr_score > 0:
        return "fr"
    if en_score > fr_score:
        return "en"
    return "fr"


def _force_language_suffix(text: str, lang: str) -> str:
    if lang == "fr":
        return (
            text
            + "\n\n⚠️ IMPORTANT : Réponds UNIQUEMENT en français. "
            + "Ne traduis pas en anglais. Toute ta réponse doit être en français."
        )
    return text + "\n\n⚠️ IMPORTANT: Respond ONLY in English."


# ==============================================================================
# HELPERS
# ==============================================================================
def _get_api_key(key_name: str) -> str:
    try:
        from provider_manager import provider_manager
        return provider_manager.get_api_key(key_name)
    except Exception as e:
        logger.debug("[vision] Impossible de lire %s : %s", key_name, e)
        return ""


def _safe_listdir(directory: str) -> list:
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
    entries = _safe_listdir(directory)
    if not entries:
        return None
    try:
        candidates = [
            os.path.join(directory, f)
            for f in entries
            if f.lower().endswith(extensions)
            and not f.startswith(".")
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
    if not image_path:
        return None
    image_path = str(image_path).strip().strip("\"'")

    if os.path.isabs(image_path) and os.path.exists(image_path):
        logger.info("[vision] Chemin absolu trouvé : %s", image_path)
        return image_path

    try:
        target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, image_path))
        if target_path != WORKSPACE_DIR and os.path.exists(target_path):
            logger.info("[vision] Chemin workspace trouvé : %s", target_path)
            return target_path
    except (PermissionError, OSError) as e:
        logger.warning("[vision] Erreur resolution workspace : %s", e)

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

    latest_uploads = _get_latest_media_file(
        UPLOADS_DIR, (".png", ".jpg", ".jpeg", ".webp")
    )
    if latest_uploads:
        logger.info("[vision] Fallback uploads/ : %s", latest_uploads)
        return latest_uploads

    latest_generated = _get_latest_media_file(
        GENERATED_DIR, (".png", ".jpg", ".jpeg", ".webp")
    )
    if latest_generated:
        logger.info("[vision] Fallback generated/ : %s", latest_generated)
        return latest_generated

    logger.warning("[vision] ❌ Aucun chemin trouvé pour : %r", image_path)
    return None


def _get_mime_type(path: str) -> str:
    ext = path.split(".")[-1].lower()
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(ext, "image/png")


def _read_image_base64(path: str) -> str:
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


# ==============================================================================
# CLASSIFICATION D'ERREUR
# ==============================================================================
def _classify_error(status_code: Optional[int], text: str) -> str:
    if status_code == 429:
        return "quota_429"
    if status_code == 401 or status_code == 403:
        return "auth_401"
    if status_code and 500 <= status_code < 600:
        return "server_5xx"
    txt = (text or "").lower()
    if "quota" in txt or "rate limit" in txt or "exceeded" in txt:
        return "quota_429"
    if "unauthorized" in txt or "invalid api key" in txt or "expired" in txt:
        return "auth_401"
    return "unknown"


# ==============================================================================
# PROVIDER 1 — NVIDIA NIM VISION (11B seul)
# ==============================================================================
def _analyze_with_nvidia(
    image_path: str,
    prompt_text: str,
    mime_type: str,
    encoded_image: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    ★ v35.2 — 11B seul (timeout 60s, retry 1×).
    Le 90B timeout systématiquement sur tier gratuit NVIDIA → retiré.
    """
    api_key = _get_api_key("NVIDIA_API_KEY")
    if not api_key:
        return None, "no_api_key"

    payload_base = {
        "messages": [{
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
        }],
        "max_tokens": 1024,
        "temperature": 0.3,
        "stream": False,
    }

    last_reason = "nvidia_unknown"

    for model_name, timeout_s, max_retries in NVIDIA_VISION_MODELS:
        payload = {**payload_base, "model": model_name}

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "[vision.nvidia] Tentative %d/%d model=%s (timeout=%ds)",
                    attempt, max_retries, model_name.split("/")[-1], timeout_s,
                )
                res = requests.post(
                    NVIDIA_VISION_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                    timeout=timeout_s,
                )

                if res.status_code == 200:
                    choices = res.json().get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if content:
                            logger.info(
                                "[vision.nvidia] ✅ Analyse OK (%d chars) model=%s",
                                len(content), model_name.split("/")[-1],
                            )
                            return content.strip(), None

                reason = _classify_error(res.status_code, res.text)
                logger.warning(
                    "[vision.nvidia] HTTP %s [%s] model=%s : %s",
                    res.status_code, reason, model_name.split("/")[-1],
                    res.text[:200],
                )
                last_reason = f"nvidia_{reason}"

                # Erreur auth → inutile de retry
                if reason == "auth_401":
                    logger.error(
                        "[vision.nvidia] ❌ Clé NVIDIA_API_KEY expirée. "
                        "Régénère-la sur https://build.nvidia.com"
                    )
                    return None, last_reason

            except requests.Timeout:
                logger.warning(
                    "[vision.nvidia] Timeout %ds model=%s",
                    timeout_s, model_name.split("/")[-1],
                )
                last_reason = "nvidia_timeout"
            except Exception as e:
                logger.warning(
                    "[vision.nvidia] Erreur model=%s : %s",
                    model_name.split("/")[-1], e,
                )
                last_reason = f"nvidia_error:{e}"

            if attempt < max_retries:
                logger.info(
                    "[vision.nvidia] Backoff %ds avant retry (model=%s)...",
                    NVIDIA_RETRY_BACKOFF, model_name.split("/")[-1],
                )
                time.sleep(NVIDIA_RETRY_BACKOFF)

        # Passage au modèle suivant (si plusieurs)
        if len(NVIDIA_VISION_MODELS) > 1:
            logger.info(
                "[vision.nvidia] Model %s échoué (%s) → modèle suivant",
                model_name.split("/")[-1], last_reason,
            )

    return None, last_reason


# ==============================================================================
# PROVIDER 2 — GEMINI VISION
# ==============================================================================
def _analyze_with_gemini(
    image_path: str,
    prompt_text: str,
    mime_type: str,
    encoded_image: str,
) -> Tuple[Optional[str], Optional[str]]:
    api_key = _get_api_key("GEMINI_API_KEY")
    if not api_key:
        return None, "no_api_key"

    try:
        url = (
            f"{GEMINI_API_BASE}/models/{GEMINI_VISION_MODEL}:generateContent"
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
            try:
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                if content:
                    logger.info(
                        "[vision.gemini] ✅ Analyse OK (%d chars)",
                        len(content),
                    )
                    return content.strip(), None
            except (KeyError, IndexError) as e:
                logger.warning("[vision.gemini] Structure inattendue : %s", e)
                return None, "gemini_bad_response"

        reason = _classify_error(res.status_code, res.text)
        logger.warning(
            "[vision.gemini] HTTP %s [%s] : %s",
            res.status_code, reason, res.text[:300],
        )
        return None, f"gemini_{reason}"

    except requests.Timeout:
        logger.warning("[vision.gemini] Timeout")
        return None, "gemini_timeout"
    except Exception as e:
        logger.warning("[vision.gemini] Erreur : %s", e)
        return None, f"gemini_error:{e}"


# ==============================================================================
# DISPATCHER PRINCIPAL
# ==============================================================================
def analyze_image_with_vision(
    image_path: str,
    prompt: str = "",
    provider: str = "auto",
    model: str = "",
) -> str:
    """
    ★ v35.2 — Chaîne : provider explicite → NVIDIA (11B) → Gemini.
    HF retiré (endpoint mort).
    """
    target_path = _resolve_image_path(image_path)
    if not target_path or not os.path.exists(target_path):
        logger.warning("[vision] Image introuvable : %s", image_path)
        return (
            f"Erreur analyse vision : image introuvable.\n"
            f"Chemin tenté : {image_path}\n"
            f"Vérifiez que le fichier existe dans uploads/ ou generated/."
        )

    raw_prompt = prompt or (
        "Décris cette image en détail : identité des personnages, "
        "expressions faciales, couleurs de cheveux, yeux, barbe, vêtements, "
        "arrière-plan, ambiance générale."
    )
    detected_lang = _detect_language(raw_prompt)
    prompt_text = _force_language_suffix(raw_prompt, detected_lang)

    logger.info(
        "[vision] Langue détectée : %s | prompt final (80 chars) : %r",
        detected_lang, prompt_text[:80],
    )

    try:
        encoded_image = _read_image_base64(target_path)
        mime_type = _get_mime_type(target_path)
    except Exception as e:
        logger.exception("[vision] Lecture image échouée")
        return f"Erreur analyse vision : impossible de lire {target_path} ({e})"

    logger.info(
        "[vision] Analyse : %s (provider demandé=%s)",
        os.path.basename(target_path), provider,
    )

    # ★ v35.2 — chaîne : provider explicite → NVIDIA (11B) → Gemini
    chain = []
    if provider and provider != "auto":
        chain.append(provider)
    for p in VISION_PROVIDERS:
        if p not in chain:
            chain.append(p)

    errors: dict = {}

    for prov in chain:
        if prov == "nvidia":
            result, err = _analyze_with_nvidia(
                target_path, prompt_text, mime_type, encoded_image,
            )
        elif prov == "gemini":
            result, err = _analyze_with_gemini(
                target_path, prompt_text, mime_type, encoded_image,
            )
        else:
            logger.warning("[vision] Provider inconnu : %s", prov)
            continue

        if result:
            return result

        errors[prov] = err or "unknown"
        logger.info(
            "[vision] %s échoué (%s) → provider suivant",
            prov, err,
        )

    # Tout a échoué
    logger.warning("[vision] ❌ Tous les providers ont échoué : %s", errors)

    hints = []
    if errors.get("gemini") == "gemini_quota_429":
        hints.append(
            "• **Gemini** : quota 429 dépassé — attends 1 min ou change de clé "
            "(https://ai.dev/rate-limit)"
        )
    if errors.get("nvidia") == "nvidia_auth_401":
        hints.append(
            "• **NVIDIA** : clé expirée — régénère-la sur https://build.nvidia.com"
        )
    if errors.get("nvidia") == "nvidia_no_api_key":
        hints.append("• **NVIDIA** : NVIDIA_API_KEY absente du .env")
    if errors.get("gemini") == "nvidia_no_api_key":
        hints.append("• **Gemini** : GEMINI_API_KEY absente du .env")

    detail_lines = "\n".join(f"  - {p} : {err}" for p, err in errors.items())
    hints_block = ("\n\n**Causes probables :**\n" + "\n".join(hints)) if hints else ""

    return (
        "❌ Aucun provider vision n'a pu analyser cette image.\n\n"
        f"**Détail des échecs :**\n{detail_lines}"
        f"{hints_block}\n\n"
        "**Solution rapide :** vérifie tes clés dans `.env` "
        "(NVIDIA_API_KEY, GEMINI_API_KEY) puis redémarre le serveur."
    )