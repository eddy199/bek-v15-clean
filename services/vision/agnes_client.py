# ==============================================================================
# BEK-v16 — Vision / Agnes Client (v32.4 — Limites frames par résolution)
# ------------------------------------------------------------------------------
# v32.4 (2026-10-01) : ★ Fix limite 1080P
#   - 1080P : max 241 frames (10s)  ← AVANT : plantait si > 241
#   - 720P  : max 481 frames (20s)
#   - 480P  : max 961 frames (40s)
#   - Le code ajuste automatiquement à la limite de la résolution choisie
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
    """
    ★ v32.4 — Convertit une durée en frames, en respectant :
      1. La limite de la résolution (1080P=241, 720P=481, 480P=961)
      2. La grille 8n+1 d'Agnes
      3. Les bornes min/max
    """
    max_frames = get_max_frames_for_resolution(resolution)

    target_frames = seconds * fps

    if target_frames <= AGNES_V2_MIN_FRAMES:
        return AGNES_V2_MIN_FRAMES

    if target_frames >= max_frames:
        # ★ Ajuster au max de la grille 8n+1 <= max_frames
        n_max = (max_frames - 1) // 8
        frames = 8 * n_max + 1
        if frames > max_frames:
            n_max -= 1
            frames = 8 * n_max + 1
        logger.info(
            "[vision.agnes] Durée demandée (%ss) dépasse limite %s "
            "(max %d frames) → ajustée à %d frames (%.2fs)",
            seconds, resolution, max_frames, frames, frames / fps,
        )
        return frames

    # Sur la grille 8n+1
    n_max = int((target_frames - 1) // 8)
    frames = 8 * n_max + 1
    frames = max(AGNES_V2_MIN_FRAMES, min(max_frames, frames))
    return frames


def _enrich_prompt_with_audio(prompt, with_audio, audio_style="default"):
    if not with_audio:
        return prompt
    audio_instructions = AUDIO_STYLE_PROMPTS.get(
        audio_style, AUDIO_STYLE_PROMPTS["default"]
    )
    enriched = f"{prompt}. {audio_instructions}."
    logger.info("[vision.agnes] Prompt enrichi avec audio (style=%s)", audio_style)
    return enriched


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


def _agnes_post_with_retry(url, headers, payload, max_retries=AGNES_MAX_RETRIES, base_delay=AGNES_RETRY_BASE_DELAY):
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
    return last_res


# ==============================================================================
# HELPERS IMAGES
# ==============================================================================
def _load_image_as_data_uri(image_path_or_data: str) -> str:
    """Charge une image en data URI (format V2.0)."""
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
    """★ v32.2 — base64 PUR pour Agnes 2.5."""
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


# ==============================================================================
# ★ v32.4 — CRÉATION DE TÂCHE avec limite par résolution
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
    resolution: str = AGNES_V2_DEFAULT_RESOLUTION,
) -> Dict[str, Any]:
    """
    Crée une tâche Agnes.

    ★ v32.4 — La limite de frames est calculée selon la résolution :
      - 1080P : max 241 frames (10s)
      - 720P  : max 481 frames (20s)
      - 480P  : max 961 frames (40s)
    """
    ep = _get_agnes_endpoints(model_id)
    url = ep["create_url"]
    headers = ep["headers"]

    is_v25 = _is_agnes_v25(model_id)

    logger.info(
        "[vision.agnes] v32.4 create_task model=%s is_v25=%s mode=%s resolution=%s",
        model_id, is_v25, mode, resolution,
    )

    final_prompt = prompt
    if is_v25 and reference_images and mode in ("reference", "multi_reference"):
        final_prompt = _inject_picture_refs_in_prompt(prompt, len(reference_images))

    payload: Dict[str, Any] = {
        "model": ep["model_id"],
        "prompt": final_prompt,
    }

    if is_v25 and mode == "multi_reference":
        payload["mode"] = "reference"
    else:
        payload["mode"] = mode

    # ─── Agnes V2.0 : width/height + num_frames ───
    if ep.get("is_v2", False):
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

        # ★ v32.4 — Calcul intelligent selon résolution
        num_frames = _agnes_seconds_to_frames_optimal(
            duration, fps, resolution=resolution
        )
        payload["num_frames"] = num_frames
        payload["frame_rate"] = fps

        actual_duration = num_frames / fps
        logger.info(
            "[vision.agnes] V2.0 : duration=%ss → frames=%s (%.2fs) @ %s",
            duration, num_frames, actual_duration, resolution,
        )
    else:
        # Agnes V2.5 Flash
        payload["size"] = resolution.lower()
        payload["aspect_ratio"] = aspect_ratio
        seconds = max(ep.get("min_seconds", 4), min(ep.get("max_seconds", 12), duration))
        payload["seconds"] = str(seconds)
        logger.info("[vision.agnes] Flash : seconds=%s", seconds)

    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    # ─── keyframes ───
    if mode == "keyframes" and first_frame:
        if is_v25:
            img_data = _load_image_as_base64_pure(first_frame)
        else:
            img_data = _load_image_as_data_uri(first_frame)
        payload["image"] = [img_data, img_data]
        logger.info("[vision.agnes] mode=keyframes : first_frame ajoutée")

    # ─── reference / multi_reference ───
    if reference_images and mode in ("reference", "multi_reference"):
        refs_data: List[str] = []
        for ref_path in reference_images:
            if is_v25:
                refs_data.append(_load_image_as_base64_pure(ref_path))
            else:
                refs_data.append(_load_image_as_data_uri(ref_path))

        if is_v25:
            payload["images"] = refs_data
        else:
            # ★ Agnes 2.0 : image + background_image
            payload["image"] = refs_data
            payload["background_image"] = refs_data[-1]
        logger.info(
            "[vision.agnes] %s mode=%s : %d images ajoutées",
            "V2.5" if is_v25 else "V2.0", mode, len(refs_data),
        )

    if mode == "keyframes" and reference_images and not first_frame:
        refs_data: List[str] = []
        for ref_path in reference_images:
            if is_v25:
                refs_data.append(_load_image_as_base64_pure(ref_path))
            else:
                refs_data.append(_load_image_as_data_uri(ref_path))
        payload["images" if is_v25 else "reference_images"] = refs_data

    logger.info(
        "[vision.agnes] create_task → model=%s mode=%s duration=%ss resolution=%s frames=%s payload_keys=%s",
        ep["model_id"], payload.get("mode"), duration, resolution,
        payload.get("num_frames", "N/A"),
        list(payload.keys()),
    )

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


def _agnes_poll_task(task_id, model_id, poll_interval=10, max_wait=1800):
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
    mode: str = "ti2vid",
    first_frame: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
    poll_interval: int = 10,
    max_wait: int = 1800,
    resolution: str = AGNES_V2_DEFAULT_RESOLUTION,
) -> Dict[str, Any]:
    """Lance UNE génération Agnes complète."""
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
        task_data.get("task_id")
        or task_data.get("id")
        or task_data.get("data", {}).get("task_id")
        or task_data.get("data", {}).get("id")
    )
    if not task_id:
        raise RuntimeError(
            f"[vision.agnes] Pas de task_id : {json.dumps(task_data)[:500]}"
        )

    logger.info("[vision.agnes] Tâche créée : %s", task_id)

    final_data = _agnes_poll_task(
        task_id=task_id,
        model_id=model_id,
        poll_interval=poll_interval,
        max_wait=max_wait,
    )

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
        or final_data.get("metadata", {}).get("url")
        or final_data.get("metadata", {}).get("video_url")
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
        "model_id": model_id,
        "mode": mode,
        "video_url": video_url,
        "resolution": resolution,
    }