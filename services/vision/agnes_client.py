# ==============================================================================
# BEK-v16 — Vision / Agnes Client (v34.1 — Anti Rate-Limit 429)
# ------------------------------------------------------------------------------
# ★ v34.1 (2026-10-19) : FIX RETRY
#   - Suppression des tentatives multiples (retry) sur les erreurs 503
#   - Abandon immédiat si 503 pour ne PAS déclencher le Rate Limit (429)
# ★ v34.0 (2026-10-18) : CORRECTION DU CONTRAT API
#   - Mode UNIQUE "text" pour le text-to-video
#   - seconds envoyé en chaîne ("4"–"12")
#   - size forcé à "720P" pour Flash
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
    AGNES_V2_DEFAULT_RESOLUTION,
    AGNES_RPM_WAIT_SECONDS,
    AGNES_MAX_RETRIES,
    AGNES_RETRY_BASE_DELAY,
    AUDIO_STYLE_PROMPTS,
    get_max_frames_for_resolution,
)

logger = logging.getLogger("bek.vision.agnes")


class AgnesError(Exception):
    def __init__(self, message: str, http_status: int = 0):
        super().__init__(message)
        self.http_status = http_status


class AgnesRateLimitError(AgnesError):
    pass


class AgnesServerError(AgnesError):
    pass


class AgnesClientError(AgnesError):
    pass


_V25_FLASH_MODEL_ID = "agnes-video-2.5-flash"
_V25_MODEL_ID = "agnes-video-2.5"


def _is_agnes_flash(model_id: str) -> bool:
    if not model_id:
        return False
    m = model_id.lower()
    return "2.5" in m and "flash" in m


def _get_agnes_endpoints(model_id: str) -> Dict[str, Any]:
    from provider_manager import provider_manager
    return provider_manager.get_agnes_endpoints(model_id)


def _is_agnes_v25(model_id: str) -> bool:
    return "2.5" in model_id or "3.0" in model_id or "3.5" in model_id


def _inject_picture_refs_in_prompt(prompt: str, num_images: int) -> str:
    if num_images <= 0:
        return prompt
    if "<Picture" in prompt:
        return prompt
    picture_refs = ", ".join(f"<Picture {i+1}>" for i in range(num_images))
    prefix = (
        f"Refer to the provided images as {picture_refs}. "
        f"Use their EXACT facial features, hair, and appearance. "
    )
    return prefix + prompt


def _agnes_seconds_to_frames_optimal(
    seconds: float,
    fps: int = 24,
    resolution: str = AGNES_V2_DEFAULT_RESOLUTION,
) -> int:
    max_frames = get_max_frames_for_resolution(resolution)
    target_frames = seconds * fps

    if target_frames <= AGNES_V2_MIN_FRAMES:
        return AGNES_V2_MIN_FRAMES

    if target_frames >= max_frames:
        n_max = (max_frames - 1) // 8
        frames = 8 * n_max + 1
        if frames > max_frames:
            n_max -= 1
            frames = 8 * n_max + 1
        return frames

    n_max = int((target_frames - 1) // 8)
    frames = 8 * n_max + 1
    return max(AGNES_V2_MIN_FRAMES, min(max_frames, frames))


def _get_dimensions_for_resolution(resolution: str, aspect_ratio: str) -> tuple:
    res_upper = resolution.upper()
    if res_upper == "720P":
        base_w, base_h = 1280, 720
    elif res_upper == "480P":
        base_w, base_h = 854, 480
    else:
        base_w, base_h = 1920, 1080

    if aspect_ratio == "16:9":
        return base_w, base_h
    elif aspect_ratio == "9:16":
        return base_h, base_w
    elif aspect_ratio == "1:1":
        return base_h, base_h
    return base_w, base_h


def _enrich_prompt_with_audio(prompt, with_audio, audio_style="default"):
    if not with_audio:
        return prompt
    audio_instructions = AUDIO_STYLE_PROMPTS.get(
        audio_style, AUDIO_STYLE_PROMPTS["default"]
    )
    return f"{prompt}. {audio_instructions}."


_LAST_AGNES_CALL_TIME: float = 0.0


def _agnes_wait_rate_limit() -> None:
    global _LAST_AGNES_CALL_TIME
    now = time.time()
    elapsed = now - _LAST_AGNES_CALL_TIME
    wait_needed = AGNES_RPM_WAIT_SECONDS - elapsed
    if wait_needed > 0:
        logger.info("[vision.agnes] Rate limit : attente de %.1fs...", wait_needed)
        time.sleep(wait_needed)
    _LAST_AGNES_CALL_TIME = time.time()


# ══════════════════════════════════════════════════════════════════════════════
# ★ v34.1 — NO RETRY SUR 503 (pour éviter le 429)
# ══════════════════════════════════════════════════════════════════════════════

def _agnes_post_with_retry(url, headers, payload, max_retries=AGNES_MAX_RETRIES, base_delay=AGNES_RETRY_BASE_DELAY):
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.RequestException as e:
        logger.warning("[vision.agnes] Erreur réseau : %s", e)
        raise AgnesServerError(f"Erreur réseau : {e}", http_status=0)
        
    if res.status_code == 503:
        logger.warning(
            "[vision.agnes] HTTP 503 (Serveur surchargé). "
            "Abandon immédiat pour ne pas déclencher le Rate Limit (429)."
        )
    return res


def _load_image_as_data_uri(image_path_or_data: str) -> str:
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


def _load_image_as_base64_pure(image_path_or_data: str) -> str:
    if not image_path_or_data:
        return ""
    if image_path_or_data.startswith("data:"):
        if "," in image_path_or_data:
            return image_path_or_data.split(",", 1)[1]
        return image_path_or_data
    if os.path.exists(image_path_or_data):
        with open(image_path_or_data, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return image_path_or_data


# ══════════════════════════════════════════════════════════════════════════════
# CREATE TASK (Contrat v34.0)
# ══════════════════════════════════════════════════════════════════════════════

def _agnes_create_task(
    prompt: str,
    model_id: str,
    duration: int,
    aspect_ratio: str,
    negative_prompt: Optional[str] = None,
    fps: int = AGNES_V2_DEFAULT_FPS,
    mode: str = "text",
    first_frame: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
    resolution: str = AGNES_V2_DEFAULT_RESOLUTION,
) -> Dict[str, Any]:
    ep = _get_agnes_endpoints(model_id)
    url = ep["create_url"]
    headers = ep["headers"]

    is_v25 = _is_agnes_v25(model_id)
    is_flash = _is_agnes_flash(model_id)

    logger.info(
        "[vision.agnes] v34.1 create_task model=%s is_v25=%s is_flash=%s mode=%s resolution=%s",
        model_id, is_v25, is_flash, mode, resolution,
    )

    final_prompt = prompt
    if is_v25 and reference_images and mode in ("reference", "multi_reference"):
        final_prompt = _inject_picture_refs_in_prompt(prompt, len(reference_images))

    base_payload: Dict[str, Any] = {
        "model": ep["model_id"],
        "prompt": final_prompt,
    }

    if is_v25:
        seconds = max(ep.get("min_seconds", 4), min(ep.get("max_seconds", 12), duration))
        base_payload["seconds"] = str(seconds)

        if is_flash:
            base_payload["size"] = "720P"
        else:
            base_payload["size"] = resolution.lower()

        base_payload["aspect_ratio"] = aspect_ratio
        base_payload["mode"] = mode if mode in ("text", "keyframe", "reference") else "text"

        logger.info(
            "[vision.agnes] ★ v34.1 : payload mode=%s, seconds=%s, size=%s, aspect=%s",
            base_payload["mode"], base_payload["seconds"],
            base_payload["size"], base_payload["aspect_ratio"],
        )
    else:
        width, height = _get_dimensions_for_resolution(resolution, aspect_ratio)
        base_payload["width"] = width
        base_payload["height"] = height
        num_frames = _agnes_seconds_to_frames_optimal(duration, fps, resolution=resolution)
        base_payload["num_frames"] = num_frames
        base_payload["frame_rate"] = fps
        base_payload["mode"] = mode

    if reference_images and mode in ("reference", "multi_reference"):
        refs_data: List[str] = []
        for ref_path in reference_images:
            if is_v25:
                refs_data.append(_load_image_as_base64_pure(ref_path))
            else:
                refs_data.append(_load_image_as_data_uri(ref_path))

        if is_v25:
            base_payload["images"] = refs_data
        else:
            base_payload["image"] = refs_data
            base_payload["background_image"] = refs_data[-1]

    if negative_prompt:
        base_payload["negative_prompt"] = negative_prompt

    _agnes_wait_rate_limit()

    res = _agnes_post_with_retry(url, headers, base_payload)

    if res.status_code >= 400:
        try:
            err = res.json()
            err_txt = json.dumps(err)
        except Exception:
            err_txt = res.text[:800]

        err_msg = f"[vision.agnes] create_task HTTP {res.status_code}: {err_txt}"

        logger.error(
            "[vision.agnes] ★ ERREUR CREATE_TASK HTTP %d\n"
            "  → URL: %s\n"
            "  → Payload envoyé: %s\n"
            "  → Réponse Agnes: %s",
            res.status_code,
            url,
            json.dumps({k: v for k, v in base_payload.items() if k != "images"})[:500],
            err_txt[:500],
        )

        if res.status_code == 429:
            raise AgnesRateLimitError(err_msg, http_status=429)
        elif res.status_code in (502, 503, 504):
            raise AgnesServerError(err_msg, http_status=res.status_code)
        elif res.status_code in (400, 401, 403):
            raise AgnesClientError(err_msg, http_status=res.status_code)
        else:
            raise AgnesServerError(err_msg, http_status=res.status_code)

    data = res.json()
    logger.info("[vision.agnes] create_task OK : %s", json.dumps(data)[:800])
    return data


# ══════════════════════════════════════════════════════════════════════════════
# POLLING & DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

def _agnes_poll_task(task_id, model_id, poll_interval=10, max_wait=1800):
    ep = _get_agnes_endpoints(model_id)
    base_status_url = ep["status_url"]
    headers = ep["headers"]

    url = f"{base_status_url.rstrip('/')}?video_id={task_id}&model_name={model_id}"

    start = time.time()

    logger.info("[vision.agnes] v34.1 poll_task : %s", url)

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
        status = (data.get("status") or data.get("internal_status") or "").lower()

        if status in ("completed", "success", "succeeded"):
            logger.info("[vision.agnes] Tâche %s terminée (%ds)", task_id, int(elapsed))
            return data

        if status in ("failed", "error"):
            err = data.get("error") or data.get("message") or "unknown"
            raise RuntimeError(f"[vision.agnes] Tâche {task_id} échouée: {err}")

        logger.info(
            "[vision.agnes] Tâche %s en cours... (%ds, status=%s)",
            task_id, int(elapsed), status or "pending",
        )
        time.sleep(poll_interval)


def _agnes_download_video(video_url: str) -> bytes:
    logger.info("[vision.agnes] Téléchargement MP4 : %s", video_url[:120])
    res = requests.get(video_url, timeout=300)
    res.raise_for_status()
    return res.content


def _agnes_generate_single_clip(
    prompt: str,
    model_id: str,
    duration: int,
    aspect_ratio: str = "16:9",
    negative_prompt: Optional[str] = None,
    fps: int = AGNES_V2_DEFAULT_FPS,
    mode: str = "text",
    first_frame: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
    poll_interval: int = 10,
    max_wait: int = 1800,
    resolution: str = AGNES_V2_DEFAULT_RESOLUTION,
) -> Dict[str, Any]:
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
        resolution=resolution,
    )

    task_id = (
        task_data.get("video_id")
        or task_data.get("task_id")
        or task_data.get("id")
        or task_data.get("data", {}).get("video_id")
        or task_data.get("data", {}).get("task_id")
        or task_data.get("data", {}).get("id")
    )
    if not task_id:
        raise RuntimeError(
            f"[vision.agnes] Pas de video_id/task_id : {json.dumps(task_data)[:800]}"
        )

    logger.info(
        "[vision.agnes] ★ v34.1 Tâche créée : %s (keys: %s)",
        task_id, list(task_data.keys()),
    )

    final_data = _agnes_poll_task(
        task_id=task_id,
        model_id=model_id,
        poll_interval=poll_interval,
        max_wait=max_wait,
    )

    video_url = (
        final_data.get("url")
        or final_data.get("video_url")
        or final_data.get("output")
        or final_data.get("data", {}).get("url")
    )

    if not video_url:
        logger.error("[vision.agnes] final_data keys = %s", list(final_data.keys()))
        logger.error("[vision.agnes] final_data FULL = %s", json.dumps(final_data))
        raise RuntimeError(
            f"[vision.agnes] Aucune video_url : {json.dumps(final_data)[:3000]}"
        )

    video_bytes = _agnes_download_video(video_url)

    return {
        "bytes": video_bytes,
        "mime": "video/mp4",
        "duration": duration,
        "task_id": task_id,
        "video_id": task_data.get("video_id") or task_id,
        "model_id": model_id,
        "mode": mode,
        "video_url": video_url,
        "resolution": resolution,
    }