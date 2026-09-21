# ==============================================================================
# BEK-v16 — Vision / Agnes Client
# ------------------------------------------------------------------------------
# Client complet pour Agnes AI (V2.0 + Flash)
#   - Conversion secondes → frames optimales (formule Agnes 8n+1)
#   - Rate limiting RPM (1 req / 65s)
#   - Retry automatique (502/503/504)
#   - Création de tâche + polling
#   - Multi-mode : ti2vid, keyframes, multi_reference
# v28 (2026-09-21) : Extraction depuis vision_legacy.py
# v28.1 (2026-09-21) : Ajout logs DEBUG temporaires
# v28.2 (2026-09-21) : Fix indentation + extraction video_url élargie
# v29 (2026-09-21) : Support keyframes avec first_frame pour extension
# ==============================================================================
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import time
from typing import Any, Dict, List, Optional

import requests

from services.vision.constants import (
    AGNES_V2_MIN_FRAMES,
    AGNES_V2_MAX_FRAMES,
    AGNES_V2_DEFAULT_FPS,
    AGNES_RPM_WAIT_SECONDS,
    AGNES_MAX_RETRIES,
    AGNES_RETRY_BASE_DELAY,
    AUDIO_STYLE_PROMPTS,
)

logger = logging.getLogger("bek.vision.agnes")


# ==============================================================================
# HELPERS INTERNES
# ==============================================================================
def _get_agnes_endpoints(model_id: str) -> Dict[str, Any]:
    """Récupère les endpoints Agnes via le provider_manager."""
    from provider_manager import provider_manager
    return provider_manager.get_agnes_endpoints(model_id)


# ==============================================================================
# CONVERSION SECONDS → FRAMES
# ==============================================================================
def _agnes_seconds_to_frames_optimal(seconds: float, fps: int = 24) -> int:
    """Convertit une durée en secondes vers le nombre de frames Agnes V2.0."""
    target_frames = seconds * fps

    if target_frames <= AGNES_V2_MIN_FRAMES:
        return AGNES_V2_MIN_FRAMES

    if target_frames >= AGNES_V2_MAX_FRAMES:
        return AGNES_V2_MAX_FRAMES

    n_max = int((target_frames - 1) // 8)
    frames = 8 * n_max + 1
    frames = max(AGNES_V2_MIN_FRAMES, min(AGNES_V2_MAX_FRAMES, frames))
    return frames


# ==============================================================================
# ENRICHISSEMENT PROMPT AVEC AUDIO
# ==============================================================================
def _enrich_prompt_with_audio(
    prompt: str,
    with_audio: bool,
    audio_style: str = "default",
) -> str:
    """Ajoute les instructions audio au prompt si demandé."""
    if not with_audio:
        return prompt

    audio_instructions = AUDIO_STYLE_PROMPTS.get(
        audio_style, AUDIO_STYLE_PROMPTS["default"]
    )
    enriched = f"{prompt}. {audio_instructions}."
    logger.info("[vision.agnes] Prompt enrichi avec audio (style=%s)", audio_style)
    return enriched


# ==============================================================================
# RATE LIMITING (RPM = 1)
# ==============================================================================
_LAST_AGNES_CALL_TIME: float = 0.0


def _agnes_wait_rate_limit() -> None:
    """Respecte la limite RPM d'Agnes (1 req/65s)."""
    global _LAST_AGNES_CALL_TIME
    now = time.time()
    elapsed = now - _LAST_AGNES_CALL_TIME
    wait_needed = AGNES_RPM_WAIT_SECONDS - elapsed

    if wait_needed > 0:
        logger.info(
            "[vision.agnes] Rate limit : attente de %.1fs avant prochain appel...",
            wait_needed,
        )
        time.sleep(wait_needed)

    _LAST_AGNES_CALL_TIME = time.time()


# ==============================================================================
# RETRY SUR ERREURS TRANSIENTES
# ==============================================================================
def _agnes_post_with_retry(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    max_retries: int = AGNES_MAX_RETRIES,
    base_delay: int = AGNES_RETRY_BASE_DELAY,
) -> requests.Response:
    """POST avec retry exponentiel sur 502/503/504."""
    last_res: Optional[requests.Response] = None

    for attempt in range(max_retries):
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        last_res = res

        if res.status_code not in (502, 503, 504):
            return res

        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "[vision.agnes] HTTP %s (tentative %d/%d), retry dans %ds...",
                res.status_code, attempt + 1, max_retries, delay,
            )
            time.sleep(delay)

    return last_res  # type: ignore[return-value]


# ==============================================================================
# HELPER — Charger une image locale en base64 data URI
# ==============================================================================
def _load_image_as_data_uri(image_path_or_data: str) -> str:
    """
    Si c'est un chemin local → convertit en data URI base64.
    Si c'est déjà un data URI → retourne tel quel.
    """
    if not image_path_or_data:
        return ""

    if image_path_or_data.startswith("data:"):
        return image_path_or_data

    if os.path.exists(image_path_or_data):
        with open(image_path_or_data, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        mime = mimetypes.guess_type(image_path_or_data)[0] or "image/png"
        return f"data:{mime};base64,{img_b64}"

    return image_path_or_data


# ==============================================================================
# CRÉATION DE TÂCHE
# ==============================================================================
def _agnes_create_task(
    prompt: str,
    model_id: str,
    duration: int,
    aspect_ratio: str,
    negative_prompt: Optional[str] = None,
    fps: int = AGNES_V2_DEFAULT_FPS,
    mode: str = "ti2vid",
    first_frame: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Crée une tâche Agnes et retourne la réponse JSON.

    Modes supportés :
      - "ti2vid"          : text-to-video
      - "keyframes"       : first_frame comme point de départ
      - "multi_reference" : N images de référence (personnages)
    """
    ep = _get_agnes_endpoints(model_id)
    url = ep["create_url"]
    headers = ep["headers"]

    payload: Dict[str, Any] = {
        "model": ep["model_id"],
        "prompt": prompt,
        "mode": mode,
    }

    # ─── Agnes V2.0 : width/height + num_frames ───
    if ep["is_v2"]:
        if aspect_ratio == "16:9":
            payload["width"] = 1920
            payload["height"] = 1080
        elif aspect_ratio == "9:16":
            payload["width"] = 1080
            payload["height"] = 1920
        elif aspect_ratio == "1:1":
            payload["width"] = 1080
            payload["height"] = 1080
        else:
            payload["width"] = 1920
            payload["height"] = 1080

        num_frames = _agnes_seconds_to_frames_optimal(duration, fps)
        payload["num_frames"] = num_frames
        payload["frame_rate"] = fps

        actual_duration = num_frames / fps
        logger.info(
            "[vision.agnes] V2.0 mode=%s : duration=%ss -> num_frames=%s (%.2fs)",
            mode, duration, num_frames, actual_duration,
        )
    else:
        payload["size"] = "720P"
        payload["aspect_ratio"] = aspect_ratio
        seconds = max(ep["min_seconds"], min(ep["max_seconds"], duration))
        payload["seconds"] = str(seconds)
        logger.info("[vision.agnes] Flash mode=%s : seconds=%s", mode, seconds)

    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    # ─── Mode keyframes : first_frame comme point de départ ───
    if mode == "keyframes" and first_frame:
        img_data = _load_image_as_data_uri(first_frame)

        # Agnes attend une LISTE de 2 images (start + end)
        # Si une seule fournie → on duplique (start = end)
        payload["image"] = [img_data, img_data]

        logger.info(
            "[vision.agnes] mode=keyframes : first_frame ajoutée "
            "(taille_data_uri=%d)", len(img_data),
        )

    # ─── Mode multi_reference : N images en référence ───
    if mode == "multi_reference" and reference_images:
        refs_data: List[str] = []
        for ref_path in reference_images:
            refs_data.append(_load_image_as_data_uri(ref_path))

        payload["reference_images"] = refs_data
        logger.info(
            "[vision.agnes] mode=multi_reference : %d images ajoutées",
            len(refs_data),
        )

    # ─── Si les DEUX modes sont fournis (keyframes + refs) ───
    if mode == "keyframes" and reference_images and not first_frame:
        refs_data: List[str] = []
        for ref_path in reference_images:
            refs_data.append(_load_image_as_data_uri(ref_path))
        payload["reference_images"] = refs_data
        logger.info(
            "[vision.agnes] mode=keyframes (fallback refs) : %d refs",
            len(refs_data),
        )

    logger.info(
        "[vision.agnes] create_task model=%s mode=%s duration=%ss "
        "first_frame=%s refs=%d",
        ep["model_id"], mode, duration,
        "oui" if first_frame else "non",
        len(reference_images) if reference_images else 0,
    )

    # Rate limiting + POST avec retry
    _agnes_wait_rate_limit()
    res = _agnes_post_with_retry(url, headers, payload)

    if res.status_code >= 400:
        try:
            err = res.json()
            err_txt = json.dumps(err)
        except Exception:
            err_txt = res.text[:800]
        raise RuntimeError(
            f"[vision.agnes] create_task HTTP {res.status_code}: {err_txt}"
        )

    data = res.json()
    logger.info("[vision.agnes] create_task OK : %s", json.dumps(data)[:500])
    return data


# ==============================================================================
# POLLING DE TÂCHE
# ==============================================================================
def _agnes_poll_task(
    task_id: str,
    model_id: str,
    poll_interval: int = 10,
    max_wait: int = 1800,
) -> Dict[str, Any]:
    """
    Attend la fin d'une tâche Agnes (status=completed ou failed).
    """
    ep = _get_agnes_endpoints(model_id)
    base_status_url = ep["status_url"]
    headers = ep["headers"]

    url = f"{base_status_url.rstrip('/')}/{task_id}"
    start = time.time()

    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            raise TimeoutError(
                f"[vision.agnes] Tâche {task_id} non terminée après {max_wait}s"
            )

        res = requests.get(url, headers=headers, timeout=60)
        if res.status_code >= 400:
            try:
                err = res.json()
                err_txt = json.dumps(err)
            except Exception:
                err_txt = res.text[:800]
            raise RuntimeError(
                f"[vision.agnes] poll_task HTTP {res.status_code}: {err_txt}"
            )

        data = res.json()
        # Agnes retourne "internal_status" au lieu de "status"
        status = (
            data.get("status")
            or data.get("internal_status")
            or ""
        ).lower()

        if status in ("completed", "success", "succeeded"):
            logger.info(
                "[vision.agnes] Tâche %s terminée (%ds)", task_id, int(elapsed)
            )
            return data

        if status in ("failed", "error"):
            err = data.get("error") or data.get("message") or "unknown"
            raise RuntimeError(f"[vision.agnes] Tâche {task_id} échouée: {err}")

        logger.info(
            "[vision.agnes] Tâche %s en cours... (%ds, status=%s)",
            task_id, int(elapsed), status or "pending",
        )
        time.sleep(poll_interval)


# ==============================================================================
# TÉLÉCHARGEMENT DU MP4
# ==============================================================================
def _agnes_download_video(video_url: str) -> bytes:
    """Télécharge le MP4 depuis l'URL retournée par Agnes."""
    logger.info("[vision.agnes] Téléchargement MP4 : %s", video_url[:120])
    res = requests.get(video_url, timeout=300)
    res.raise_for_status()
    return res.content


# ==============================================================================
# GÉNÉRATION D'UN CLIP UNIQUE
# ==============================================================================
def _agnes_generate_single_clip(
    prompt: str,
    model_id: str,
    duration: int,
    aspect_ratio: str = "16:9",
    negative_prompt: Optional[str] = None,
    fps: int = AGNES_V2_DEFAULT_FPS,
    mode: str = "ti2vid",
    first_frame: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
    poll_interval: int = 10,
    max_wait: int = 1800,
) -> Dict[str, Any]:
    """
    Lance UNE génération Agnes complète :
    create_task → poll → download → retourne {bytes, mime, task_id, duration}
    """
    # 1. Créer la tâche
    task_data = _agnes_create_task(
        prompt=prompt,
        model_id=model_id,
        duration=duration,
        aspect_ratio=aspect_ratio,
        negative_prompt=negative_prompt,
        fps=fps,
        mode=mode,
        first_frame=first_frame,
        reference_images=reference_images,
    )

    # Extraction task_id (couvre toutes les structures Agnes connues)
    task_id = (
        task_data.get("task_id")
        or task_data.get("id")
        or task_data.get("data", {}).get("task_id")
        or task_data.get("data", {}).get("id")
        or task_data.get("data", {}).get("task", {}).get("id")
        or task_data.get("result", {}).get("task_id")
        or task_data.get("result", {}).get("id")
    )
    if not task_id:
        raise RuntimeError(
            f"[vision.agnes] Pas de task_id dans la réponse : "
            f"{json.dumps(task_data)[:500]}"
        )

    logger.info("[vision.agnes] Tâche créée : %s", task_id)

    # 2. Polling
    final_data = _agnes_poll_task(
        task_id=task_id,
        model_id=model_id,
        poll_interval=poll_interval,
        max_wait=max_wait,
    )

    # 3. Récupérer l'URL de la vidéo
    video_url = (
        final_data.get("video_url")
        or final_data.get("output")
        or final_data.get("url")
        or final_data.get("video")
        or final_data.get("result", {}).get("video_url")
        or final_data.get("data", {}).get("video_url")
        or final_data.get("data", {}).get("output")
        or final_data.get("data", {}).get("url")
        or final_data.get("assets", {}).get("video")
        or final_data.get("assets", {}).get("video_url")
    )

    if not video_url:
        logger.error(
            "[vision.agnes] final_data keys = %s", list(final_data.keys())
        )
        logger.error(
            "[vision.agnes] final_data FULL = %s", json.dumps(final_data)
        )
        raise RuntimeError(
            f"[vision.agnes] Aucune video_url dans la réponse finale : "
            f"{json.dumps(final_data)[:3000]}"
        )

    # 4. Télécharger le MP4
    video_bytes = _agnes_download_video(video_url)

    return {
        "bytes": video_bytes,
        "mime": "video/mp4",
        "duration": duration,
        "task_id": task_id,
        "model_id": model_id,
        "mode": mode,
        "video_url": video_url,
    }