# ==============================================================================
# BEK-v16 — Vision / Veo Client
# ★ v30 : Fix Thread Freeze (Async Wrapper) + Fix Clip Slicing Logic
# ==============================================================================
from __future__ import annotations

import asyncio
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
    GEMINI_API_BASE, VEO_MAX_SINGLE_CLIP, VEO_MIN_CLIP,
    VEO_DEFAULT_PERSON_GENERATION, VEO_FALLBACK_PERSON_GENERATIONS,
)
from services.vision.ffmpeg_utils import _ffmpeg_concat, _ffmpeg_trim

logger = logging.getLogger("bek.vision.veo")

def _get_api_key(key_name: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.get_api_key(key_name)

def _get_veo_endpoints(model_id: str) -> Dict[str, Any]:
    from provider_manager import provider_manager
    return provider_manager.get_veo_endpoints(model_id)

def _veo_headers(api_key: str) -> Dict[str, str]:
    return {"Content-Type": "application/json", "x-goog-api-key": api_key}

def _veo_raise_for_status(res: requests.Response, context: str) -> None:
    if res.status_code >= 400:
        try: err_txt = json.dumps(res.json())
        except Exception: err_txt = res.text[:800]
        raise RuntimeError(f"[vision/veo/{context}] HTTP {res.status_code}: {err_txt}")

def _veo_extract_video(response: Dict[str, Any]) -> Dict[str, Any]:
    candidates = response.get("generatedVideos") or response.get("generated_samples") or response.get("videos") or response.get("predictions") or []
    if not candidates: return {}
    first = candidates[0]
    if isinstance(first.get("video"), dict) and first["video"].get("uri"): return {"uri": first["video"]["uri"], "mime": first["video"].get("mimeType", "video/mp4")}
    if first.get("uri"): return {"uri": first["uri"], "mime": first.get("mimeType", "video/mp4")}
    if first.get("gcsUri"): return {"uri": first["gcsUri"], "mime": "video/mp4"}
    if first.get("bytesBase64Encoded"): return {"bytes": base64.b64decode(first["bytesBase64Encoded"]), "mime": first.get("mimeType", "video/mp4")}
    return {}

def _veo_download(uri: str, api_key: str) -> bytes:
    res = requests.get(uri, headers=_veo_headers(api_key) if uri.startswith("https://generativelanguage") else {}, timeout=300)
    res.raise_for_status()
    return res.content

def _veo_poll_operation(op_name: str, api_key: str, operations_base: str = GEMINI_API_BASE, poll_interval: int = 10, max_wait: int = 900) -> Tuple[bytes, str]:
    """Attend la fin d'une opération. (Synchrone par nature, à appeler via async_generate_video_with_veo)."""
    url = f"{operations_base}/{op_name}"
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > max_wait: raise TimeoutError(f"Opération Veo non terminée après {max_wait}s")
        res = requests.get(url, headers=_veo_headers(api_key), timeout=60)
        _veo_raise_for_status(res, "poll_operation")
        data = res.json()
        if data.get("done"):
            if "error" in data: raise RuntimeError(f"Veo error: {data['error']}")
            info = _veo_extract_video(data.get("response", {}))
            if info.get("uri"): return _veo_download(info["uri"], api_key), info.get("mime", "video/mp4")
            if info.get("bytes"): return info["bytes"], info.get("mime", "video/mp4")
            raise RuntimeError(f"Aucune vidéo trouvée: {json.dumps(data)[:800]}")
        logger.info("[vision.veo] En cours... (%ds)", int(elapsed))
        time.sleep(poll_interval)

def _veo_generate_single_clip(prompt: str, model_id: str, api_key: str, aspect_ratio: str, duration: int, negative_prompt: Optional[str] = None, person_generation: str = VEO_DEFAULT_PERSON_GENERATION, poll_interval: int = 10, max_wait: int = 900) -> Dict[str, Any]:
    ep = _get_veo_endpoints(model_id)
    url, operations_base = ep["predict_url"], ep["operations_base"]
    attempts = [person_generation] + [p for p in VEO_FALLBACK_PERSON_GENERATIONS if p != person_generation]
    
    for attempt_person in attempts:
        payload = {"instances": [{"prompt": prompt}], "parameters": {"aspectRatio": aspect_ratio, "durationSeconds": duration, "personGeneration": attempt_person}}
        if negative_prompt: payload["parameters"]["negativePrompt"] = negative_prompt
        res = requests.post(url, headers=_veo_headers(api_key), json=payload, timeout=60)
        if res.status_code < 400: break
        err_msg = json.dumps(res.json()) if res.headers.get("content-type") == "application/json" else res.text[:500]
        if "personGeneration" in err_msg: continue
        _veo_raise_for_status(res, "predictLongRunning")
        
    op_name = res.json().get("name")
    if not op_name: raise RuntimeError("Pas d'operation name.")
    video_bytes, mime = _veo_poll_operation(op_name, api_key, operations_base, poll_interval, max_wait)
    return {"bytes": video_bytes, "mime": mime, "duration": duration, "operation": op_name, "model_id": ep["model_id"]}

def _veo_generate_stitched(prompt: str, model_id: str, api_key: str, aspect_ratio: str, total_duration: int, negative_prompt: Optional[str] = None, person_generation: str = VEO_DEFAULT_PERSON_GENERATION, poll_interval: int = 10, max_wait: int = 900) -> Dict[str, Any]:
    # ★ FIX v30 : Logique de découpage parfaite
    clips_plan = []
    remaining = total_duration
    while remaining > 0:
        if remaining <= VEO_MAX_SINGLE_CLIP and remaining >= VEO_MIN_CLIP:
            clips_plan.append(remaining)
            break
        elif remaining > VEO_MAX_SINGLE_CLIP:
            clips_plan.append(VEO_MAX_SINGLE_CLIP)
            remaining -= VEO_MAX_SINGLE_CLIP
        else: # remaining < VEO_MIN_CLIP (ex: il reste 2s)
            if clips_plan:
                # On prend 2s sur le clip précédent pour faire un clip de 4s
                clips_plan[-1] -= (VEO_MIN_CLIP - remaining)
                clips_plan.append(VEO_MIN_CLIP)
            else:
                clips_plan.append(VEO_MIN_CLIP)
            break

    logger.info("[vision.veo] Découpage : %ds -> %s", total_duration, clips_plan)
    tmpdir = tempfile.mkdtemp(prefix="bek_veo_")
    clip_files = []
    for i, clip_duration in enumerate(clips_plan, 1):
        clip_prompt = optimize_video_prompt_for_clip(prompt, i, len(clips_plan), clip_duration, aspect_ratio)
        clip = _veo_generate_single_clip(clip_prompt, model_id, api_key, aspect_ratio, clip_duration, negative_prompt, person_generation, poll_interval, max_wait)
        clip_path = os.path.join(tmpdir, f"clip_{i:02d}.mp4")
        with open(clip_path, "wb") as f: f.write(clip["bytes"])
        clip_files.append(clip_path)
    
    stitched_path, final_path = os.path.join(tmpdir, "stitched.mp4"), os.path.join(tmpdir, "final.mp4")
    _ffmpeg_concat(clip_files, stitched_path)
    _ffmpeg_trim(stitched_path, final_path, total_duration)
    with open(final_path, "rb") as f: final_bytes = f.read()
    return {"bytes": final_bytes, "mime": "video/mp4", "duration": total_duration, "stitched": True, "clips": clips_plan, "model_id": model_id}


# ==============================================================================
# ★ FIX v30 : WRAPPER ASYNC POUR FASTAPI (Anti-Freeze Event Loop)
# ==============================================================================
async def async_generate_video_with_veo(
    prompt: str,
    model_id: str = "veo-3.1-generate-preview",
    aspect_ratio: str = "16:9",
    total_duration: int = 8,
    negative_prompt: Optional[str] = None,
    person_generation: str = VEO_DEFAULT_PERSON_GENERATION,
) -> Dict[str, Any]:
    """
    Point d'entrée ASYNC pour FastAPI.
    Utilise asyncio.to_thread pour ne pas bloquer l'Event Loop Uvicorn.
    """
    api_key = _get_api_key("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY manquante.")

    # On déporte l'exécution synchrone lourde dans un thread isolé
    result = await asyncio.to_thread(
        _veo_generate_stitched,
        prompt=prompt,
        model_id=model_id,
        api_key=api_key,
        aspect_ratio=aspect_ratio,
        total_duration=total_duration,
        negative_prompt=negative_prompt,
        person_generation=person_generation,
    )
    
    # Sauvegarde du fichier final
    import uuid
    from werkzeug.utils import secure_filename
    output_filename = f"veo_{uuid.uuid4().hex[:8]}.mp4"
    save_path = os.path.abspath(os.path.join(GENERATED_DIR, secure_filename(output_filename)))
    
    with open(save_path, "wb") as f:
        f.write(result["bytes"])
        
    return {
        "status": "success",
        "filepath": save_path,
        "filename": output_filename,
        "duration": result["duration"],
        "clips": result["clips"],
        "model_id": result["model_id"]
    }