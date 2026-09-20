# ==============================================================================
# BEK-v16 — Vision / Veo Client
# ------------------------------------------------------------------------------
# Client complet pour Veo 3.1 (Google)
#   - predictLongRunning + polling
#   - Extraction vidéo multi-format
#   - Téléchargement MP4
#   - Multi-clips + stitching
# v28 (2026-09-20) : Extraction depuis vision_legacy.py
# ==============================================================================
from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from core.paths import GENERATED_DIR
from services.prompt_optimizer import optimize_video_prompt_for_clip
from services.vision.constants import (
    GEMINI_API_BASE,
    VEO_MAX_SINGLE_CLIP,
    VEO_MIN_CLIP,
    VEO_DEFAULT_PERSON_GENERATION,
    VEO_FALLBACK_PERSON_GENERATIONS,
)
from services.vision.ffmpeg_utils import (
    _ffmpeg_concat,
    _ffmpeg_trim,
)

logger = logging.getLogger("bek.vision.veo")


# ==============================================================================
# HELPERS INTERNES
# ==============================================================================
def _get_api_key(key_name: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.get_api_key(key_name)


def _get_veo_endpoints(model_id: str) -> Dict[str, Any]:
    from provider_manager import provider_manager
    return provider_manager.get_veo_endpoints(model_id)


def _resolve_veo_model_id(model: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.resolve_veo_model_id(model)


def _veo_headers(api_key: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }


def _veo_raise_for_status(res: requests.Response, context: str) -> None:
    if res.status_code >= 400:
        try:
            err = res.json()
            err_txt = json.dumps(err)
        except Exception:
            err_txt = res.text[:800]
        raise RuntimeError(f"[vision/veo/{context}] HTTP {res.status_code}: {err_txt}")


def _veo_extract_video(response: Dict[str, Any]) -> Dict[str, Any]:
    """Cherche les vidéos dans la réponse Veo (multi-format)."""
    candidates: List[Any] = []
    for key in ("generatedVideos", "generated_samples", "videos", "predictions"):
        if key in response and response[key]:
            candidates = response[key]
            break

    if not candidates:
        return {}

    first = candidates[0]
    if not isinstance(first, dict):
        return {}

    if isinstance(first.get("video"), dict):
        v = first["video"]
        if v.get("uri"):
            return {"uri": v["uri"], "mime": v.get("mimeType", "video/mp4")}

    if first.get("uri"):
        return {"uri": first["uri"], "mime": first.get("mimeType", "video/mp4")}

    if first.get("gcsUri"):
        return {"uri": first["gcsUri"], "mime": "video/mp4"}

    if first.get("bytesBase64Encoded"):
        return {
            "bytes": base64.b64decode(first["bytesBase64Encoded"]),
            "mime": first.get("mimeType", "video/mp4"),
        }

    return {}


def _veo_download(uri: str, api_key: str) -> bytes:
    if uri.startswith("https://generativelanguage.googleapis.com"):
        res = requests.get(uri, headers=_veo_headers(api_key), timeout=300)
    else:
        res = requests.get(uri, timeout=300)
    res.raise_for_status()
    return res.content


def _veo_poll_operation(
    op_name: str,
    api_key: str,
    operations_base: str = GEMINI_API_BASE,
    poll_interval: int = 10,
    max_wait: int = 900,
) -> Tuple[bytes, str]:
    """Attend la fin d'une opération long-running Veo."""
    url = f"{operations_base}/{op_name}"
    start = time.time()

    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            raise TimeoutError(
                f"Opération Veo non terminée après {max_wait}s ({op_name})"
            )

        res = requests.get(url, headers=_veo_headers(api_key), timeout=60)
        _veo_raise_for_status(res, "poll_operation")
        data = res.json()

        if data.get("done"):
            if "error" in data:
                raise RuntimeError(f"Veo operation error: {data['error']}")

            response = data.get("response", {})
            info = _veo_extract_video(response)

            if info.get("uri"):
                return _veo_download(info["uri"], api_key), info.get("mime", "video/mp4")
            if info.get("bytes"):
                return info["bytes"], info.get("mime", "video/mp4")

            raise RuntimeError(
                f"Aucune vidéo trouvée. Réponse: {json.dumps(data)[:800]}"
            )

        logger.info("[vision.veo] En cours... (%ds) %s", int(elapsed), op_name)
        time.sleep(poll_interval)


def _veo_generate_single_clip(
    prompt: str,
    model_id: str,
    api_key: str,
    aspect_ratio: str,
    duration: int,
    negative_prompt: Optional[str] = None,
    person_generation: str = VEO_DEFAULT_PERSON_GENERATION,
    poll_interval: int = 10,
    max_wait: int = 900,
) -> Dict[str, Any]:
    """Lance UNE génération Veo avec predictLongRunning + polling."""
    ep = _get_veo_endpoints(model_id)
    url = ep["predict_url"]
    headers = ep["headers"]
    operations_base = ep["operations_base"]

    if person_generation not in VEO_FALLBACK_PERSON_GENERATIONS:
        attempts = [person_generation] + VEO_FALLBACK_PERSON_GENERATIONS
    else:
        attempts = [person_generation] + [
            p for p in VEO_FALLBACK_PERSON_GENERATIONS if p != person_generation
        ]

    last_error: Optional[str] = None
    res = None

    for attempt_person in attempts:
        instance: Dict[str, Any] = {"prompt": prompt}
        parameters: Dict[str, Any] = {
            "aspectRatio": aspect_ratio,
            "durationSeconds": duration,
            "personGeneration": attempt_person,
        }
        if negative_prompt:
            parameters["negativePrompt"] = negative_prompt

        payload = {"instances": [instance], "parameters": parameters}

        logger.info(
            "[vision.veo] predictLongRunning model=%s ratio=%s duration=%ss personGeneration=%s",
            ep["model_id"], aspect_ratio, duration, attempt_person,
        )

        res = requests.post(url, headers=headers, json=payload, timeout=60)

        if res.status_code < 400:
            break

        try:
            err_data = res.json()
            err_msg = json.dumps(err_data)
        except Exception:
            err_msg = res.text[:500]

        last_error = err_msg

        if "personGeneration" in err_msg or "person_generation" in err_msg:
            logger.warning(
                "[vision.veo] personGeneration='%s' rejeté, essai suivant...",
                attempt_person,
            )
            continue

        _veo_raise_for_status(res, "predictLongRunning")

    if res is None or res.status_code >= 400:
        raise RuntimeError(
            f"[vision.veo] Toutes les tentatives personGeneration ont échoué. "
            f"Dernière erreur : {last_error}"
        )

    op = res.json()
    op_name = op.get("name")
    if not op_name:
        raise RuntimeError(f"Pas d'operation name. Réponse: {json.dumps(op)[:500]}")

    logger.info("[vision.veo] Opération lancée: %s", op_name)

    video_bytes, mime = _veo_poll_operation(
        op_name=op_name,
        api_key=api_key,
        operations_base=operations_base,
        poll_interval=poll_interval,
        max_wait=max_wait,
    )

    return {
        "bytes": video_bytes,
        "mime": mime,
        "duration": duration,
        "operation": op_name,
        "model_id": ep["model_id"],
    }


def _veo_generate_stitched(
    prompt: str,
    model_id: str,
    api_key: str,
    aspect_ratio: str,
    total_duration: int,
    negative_prompt: Optional[str] = None,
    person_generation: str = VEO_DEFAULT_PERSON_GENERATION,
    poll_interval: int = 10,
    max_wait: int = 900,
) -> Dict[str, Any]:
    """Génère plusieurs clips Veo et les concatène avec FFmpeg."""
    n_full = total_duration // VEO_MAX_SINGLE_CLIP
    remainder = total_duration % VEO_MAX_SINGLE_CLIP

    clips_plan: List[int] = [VEO_MAX_SINGLE_CLIP] * n_full
    if remainder > 0:
        if remainder < VEO_MIN_CLIP and clips_plan:
            clips_plan[-1] += remainder
        else:
            clips_plan.append(remainder)

    logger.info(
        "[vision.veo] Plan multi-clips: %s (total %ss)", clips_plan, total_duration
    )

    tmpdir = tempfile.mkdtemp(prefix="bek_veo_")
    clip_files: List[str] = []

    for i, clip_duration in enumerate(clips_plan, 1):
        clip_prompt = optimize_video_prompt_for_clip(
            base_prompt=prompt,
            clip_index=i,
            total_clips=len(clips_plan),
            clip_duration=clip_duration,
            aspect_ratio=aspect_ratio,
        )

        logger.info(
            "[vision.veo] Génération clip %d/%d (%ss)",
            i, len(clips_plan), clip_duration,
        )
        clip = _veo_generate_single_clip(
            prompt=clip_prompt,
            model_id=model_id,
            api_key=api_key,
            aspect_ratio=aspect_ratio,
            duration=clip_duration,
            negative_prompt=negative_prompt,
            person_generation=person_generation,
            poll_interval=poll_interval,
            max_wait=max_wait,
        )

        clip_path = os.path.join(tmpdir, f"clip_{i:02d}.mp4")
        with open(clip_path, "wb") as f:
            f.write(clip["bytes"])
        clip_files.append(clip_path)

    stitched_path = os.path.join(tmpdir, "stitched.mp4")
    _ffmpeg_concat(clip_files, stitched_path)

    final_path = os.path.join(tmpdir, "final.mp4")
    _ffmpeg_trim(stitched_path, final_path, total_duration)

    with open(final_path, "rb") as f:
        final_bytes = f.read()

    return {
        "bytes": final_bytes,
        "mime": "video/mp4",
        "duration": total_duration,
        "stitched": True,
        "clips": clips_plan,
        "model_id": model_id,
    }