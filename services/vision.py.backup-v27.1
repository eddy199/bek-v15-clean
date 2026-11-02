# ==============================================================================
# BEK-v16 — Vision & Génération Optimisée (services/vision.py)
# ------------------------------------------------------------------------------
# v27.1 (2026-09-20) :
#   - CORRECTION : mode keyframes = liste de 2 images (pas 1)
#   - CORRECTION : champ "image" (pas "first_frame_image")
#   - Toutes les fonctions v27 conservées
# ==============================================================================
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from werkzeug.utils import secure_filename

from core.paths import FILES_DIR, GENERATED_DIR, WORKSPACE_DIR
from provider_manager import provider_manager
from services.prompt_optimizer import (
    optimize_prompt_for_media,
    optimize_video_prompt_for_clip,
)

logger = logging.getLogger("bek.vision")

# ==============================================================================
# CONSTANTES GÉNÉRALES
# ==============================================================================
VEO_SUPPORTED_DURATIONS = provider_manager.VEO_SUPPORTED_DURATIONS
VEO_MAX_SINGLE_CLIP     = provider_manager.VEO_MAX_SINGLE_CLIP
VEO_MIN_CLIP            = provider_manager.VEO_MIN_CLIP
GEMINI_API_BASE         = provider_manager.GEMINI_API_BASE

VEO_DEFAULT_PERSON_GENERATION = "allow_all"
VEO_FALLBACK_PERSON_GENERATIONS = ["allow_all", "dont_allow"]

# ==============================================================================
# CONSTANTES AGNES
# ==============================================================================
AGNES_V2_MIN_FRAMES: int = 81
AGNES_V2_MAX_FRAMES: int = 441
AGNES_V2_DEFAULT_FPS: int = 24
AGNES_V2_MAX_DURATION: float = AGNES_V2_MAX_FRAMES / AGNES_V2_DEFAULT_FPS
AGNES_V2_MIN_DURATION: float = AGNES_V2_MIN_FRAMES / AGNES_V2_DEFAULT_FPS

AGNES_RPM: int = 1
AGNES_RPM_WAIT_SECONDS: int = 65

AGNES_MAX_RETRIES: int = 3
AGNES_RETRY_BASE_DELAY: int = 5

AGNES_EXTEND_MAX_CLIPS: int = 5

# ==============================================================================
# STYLES AUDIO
# ==============================================================================
AUDIO_STYLE_PROMPTS: Dict[str, str] = {
    "default": (
        "with synchronized audio, ambient sound effects, "
        "natural background sounds matching the scene"
    ),
    "joyful": (
        "with joyful background music, cheerful sound effects, "
        "happy ambient audio synchronized with the action"
    ),
    "children": (
        "with playful children laughter, joyful background music, "
        "cheerful ambient sounds synchronized with the animation"
    ),
    "cinematic": (
        "with cinematic soundtrack, immersive ambient audio, "
        "professional sound design synchronized with the visuals"
    ),
    "nature": (
        "with natural ambient sounds, soft background music, "
        "gentle nature sound effects synchronized with the scene"
    ),
    "music": (
        "with upbeat background music, rhythmic sound effects, "
        "dynamic audio synchronized with the action"
    ),
    "dialog": (
        "with character voices speaking clearly, synchronized lip movements, "
        "natural dialogue audio matching the scene"
    ),
}


# ==============================================================================
# HELPERS PUBLICS
# ==============================================================================
def resolve_model_id(model_name: str, is_video: bool = False) -> str:
    return provider_manager.resolve_model_id(model_name)


def get_api_key(key_name: str) -> str:
    return provider_manager.get_api_key(key_name)


def _get_latest_media_file(
    directory: str,
    extensions: tuple = (".png", ".jpg", ".jpeg", ".webp", ".mp4"),
) -> Optional[str]:
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


def _resolve_existing_media_paths(
    paths_input: Union[str, List[str], None], extensions: tuple
) -> List[str]:
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
        latest = (
            _get_latest_media_file(GENERATED_DIR, extensions)
            or _get_latest_media_file(FILES_DIR, extensions)
        )
        if latest:
            resolved.append(latest)
    return resolved


# ==============================================================================
# FFMPEG HELPERS
# ==============================================================================
def _ffmpeg_run(cmd: List[str], check_output: bool = False) -> Optional[str]:
    logger.info("[vision] FFmpeg: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800 if not check_output else 60,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg introuvable. Installe FFmpeg pour les fonctions vidéo."
        )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg échec: {result.stderr[-800:]}")
    if check_output:
        return result.stdout.strip()
    return None


def _get_video_duration(path: str) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _detect_video_codec(path: str) -> Dict[str, Any]:
    try:
        result_v = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height,r_frame_rate",
                "-of", "json",
                path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        result_a = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name,sample_rate,channels",
                "-of", "json",
                path,
            ],
            capture_output=True, text=True, timeout=30,
        )

        v_data = json.loads(result_v.stdout).get("streams", [{}])[0]
        a_data = json.loads(result_a.stdout).get("streams", [{}])[0] if result_a.stdout.strip() else {}

        return {
            "video_codec":    v_data.get("codec_name"),
            "width":          v_data.get("width"),
            "height":         v_data.get("height"),
            "frame_rate":     v_data.get("r_frame_rate"),
            "audio_codec":    a_data.get("codec_name"),
            "sample_rate":    a_data.get("sample_rate"),
            "channels":       a_data.get("channels"),
            "has_audio":      bool(a_data.get("codec_name")),
        }
    except Exception as e:
        logger.warning("[vision] Erreur détection codec : %s", e)
        return {}


def _extract_last_frame(video_path: str, output_path: Optional[str] = None) -> str:
    """Extrait la dernière frame d'une vidéo en PNG."""
    if not output_path:
        base = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(
            GENERATED_DIR, f"last_frame_{base}_{uuid.uuid4().hex[:6]}.png"
        )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    _ffmpeg_run([
        "ffmpeg", "-y",
        "-sseof", "-0.1",
        "-i", video_path,
        "-fps_mode", "passthrough",
        "-q:v", "2",
        "-frames:v", "1",
        output_path,
    ])

    if not os.path.exists(output_path):
        raise RuntimeError(
            f"Échec extraction dernière frame de {video_path}"
        )

    logger.info("[vision] Dernière frame extraite: %s", output_path)
    return output_path


def _ffmpeg_concat(clip_files: List[str], output: str) -> None:
    list_file = output + ".txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for c in clip_files:
            escaped = c.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    _ffmpeg_run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", output,
    ])


def _ffmpeg_trim(input_path: str, output: str, duration: int) -> None:
    _ffmpeg_run([
        "ffmpeg", "-y", "-i", input_path,
        "-t", str(duration), "-c", "copy", output,
    ])


def _ffmpeg_trim_exact(input_path: str, output: str, duration: float) -> None:
    duration_str = f"{duration:.3f}"
    logger.info("[vision] FFmpeg trim exact : %s s", duration_str)
    _ffmpeg_run([
        "ffmpeg", "-y", "-i", input_path,
        "-t", duration_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-avoid_negative_ts", "make_zero",
        output,
    ])


# ==============================================================================
# VISION — ANALYSE IMAGE
# ==============================================================================
def analyze_image_with_vision(
    image_path: str,
    prompt: str = "",
    provider: str = "gemini",
    model: str = "",
) -> str:
    target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, image_path))
    if not os.path.exists(target_path):
        for d in [GENERATED_DIR, FILES_DIR]:
            alt = os.path.join(d, os.path.basename(image_path))
            if os.path.exists(alt):
                target_path = alt
                break

    if not os.path.exists(target_path):
        latest = _get_latest_media_file(GENERATED_DIR, (".png", ".jpg", ".jpeg", ".webp"))
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

        api_key = get_api_key("GEMINI_API_KEY")
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
    except Exception as e:
        return f"Erreur analyse vision : {str(e)}"
    return "Échec analyse image."


# ==============================================================================
# GÉNÉRATION D'IMAGE
# ==============================================================================
def generate_image_with_provider(
    prompt: str,
    provider: str = "gemini",
    model: str = "gemini-3.1-flash-image",
    output_filename: str = "",
) -> Dict[str, Any]:
    if not output_filename:
        output_filename = f"gen_image_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.abspath(
        os.path.join(GENERATED_DIR, secure_filename(output_filename))
    )

    enhanced_prompt = optimize_prompt_for_media(
        prompt, media_type="image", style_preset="cardboard_3d"
    )

    model_id = resolve_model_id(model, is_video=False)

    try:
        api_key = get_api_key("GEMINI_API_KEY")
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
                        }
            else:
                logger.warning(
                    "[vision] generate_image HTTP %s: %s",
                    res.status_code, res.text[:300],
                )

        fallback_url = (
            f"https://image.pollinations.ai/prompt/"
            f"{urllib.parse.quote(enhanced_prompt)}?nologo=true"
        )
        fallback_res = requests.get(fallback_url, timeout=30)
        if fallback_res.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(fallback_res.content)
            return {
                "status": "success",
                "filepath": save_path,
                "filename": output_filename,
                "message": "Généré via Fallback Optimizer",
            }

        return {"status": "error", "message": "Échec de génération d'image."}
    except Exception as e:
        return {"status": "error", "message": f"Erreur technique : {str(e)}"}


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
    try:
        active_prompt = user_prompt or prompt or "Modifier l'image."
        valid_paths = _resolve_existing_media_paths(
            image_paths, (".png", ".jpg", ".jpeg", ".webp")
        )

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
        return generate_image_with_provider(fusion_prompt, provider=provider, model=model)
    except Exception as e:
        return {"status": "error", "message": f"Erreur fusion visuelle : {str(e)}"}


# ==============================================================================
# VEO 3.1 — HELPERS
# ==============================================================================
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
        raise RuntimeError(f"[vision/{context}] HTTP {res.status_code}: {err_txt}")


def _veo_extract_video(response: Dict[str, Any]) -> Dict[str, Any]:
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

        logger.info("[vision] Veo en cours... (%ds) %s", int(elapsed), op_name)
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
    ep = provider_manager.get_veo_endpoints(model_id)
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
            "[vision] Veo predictLongRunning model=%s ratio=%s duration=%ss personGeneration=%s",
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
                "[vision] personGeneration='%s' rejeté par l'API, essai suivant...",
                attempt_person,
            )
            continue

        _veo_raise_for_status(res, "predictLongRunning")

    if res is None or res.status_code >= 400:
        raise RuntimeError(
            f"[vision/predictLongRunning] Toutes les tentatives personGeneration "
            f"ont échoué. Dernière erreur : {last_error}"
        )

    op = res.json()
    op_name = op.get("name")
    if not op_name:
        raise RuntimeError(f"Pas d'operation name. Réponse: {json.dumps(op)[:500]}")

    logger.info("[vision] Opération Veo lancée: %s", op_name)

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
    n_full = total_duration // VEO_MAX_SINGLE_CLIP
    remainder = total_duration % VEO_MAX_SINGLE_CLIP

    clips_plan: List[int] = [VEO_MAX_SINGLE_CLIP] * n_full
    if remainder > 0:
        if remainder < VEO_MIN_CLIP and clips_plan:
            clips_plan[-1] += remainder
        else:
            clips_plan.append(remainder)

    logger.info(
        "[vision] Plan multi-clips Veo: %s (total %ss)", clips_plan, total_duration
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
            "[vision] Génération clip %d/%d (%ss)", i, len(clips_plan), clip_duration
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


# ==============================================================================
# ★ AGNES AI — HELPERS ★
# ==============================================================================
def _agnes_seconds_to_frames_optimal(seconds: float, fps: int = 24) -> int:
    target_frames = seconds * fps

    if target_frames <= AGNES_V2_MIN_FRAMES:
        return AGNES_V2_MIN_FRAMES

    if target_frames >= AGNES_V2_MAX_FRAMES:
        return AGNES_V2_MAX_FRAMES

    n_max = int((target_frames - 1) // 8)
    frames = 8 * n_max + 1
    frames = max(AGNES_V2_MIN_FRAMES, min(AGNES_V2_MAX_FRAMES, frames))
    return frames


def _enrich_prompt_with_audio(prompt: str, with_audio: bool, audio_style: str = "default") -> str:
    if not with_audio:
        return prompt

    audio_instructions = AUDIO_STYLE_PROMPTS.get(audio_style, AUDIO_STYLE_PROMPTS["default"])
    enriched = f"{prompt}. {audio_instructions}."
    logger.info("[vision] Prompt enrichi avec audio (style=%s)", audio_style)
    return enriched


# ==============================================================================
# ★ RATE LIMITING ★
# ==============================================================================
_LAST_AGNES_CALL_TIME: float = 0.0


def _agnes_wait_rate_limit():
    global _LAST_AGNES_CALL_TIME
    now = time.time()
    elapsed = now - _LAST_AGNES_CALL_TIME
    wait_needed = AGNES_RPM_WAIT_SECONDS - elapsed

    if wait_needed > 0:
        logger.info(
            "[vision] Agnes RPM respect : attente de %.1fs avant prochain appel...",
            wait_needed,
        )
        time.sleep(wait_needed)

    _LAST_AGNES_CALL_TIME = time.time()


# ==============================================================================
# ★ AGNES — RETRY ★
# ==============================================================================
def _agnes_post_with_retry(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    max_retries: int = AGNES_MAX_RETRIES,
    base_delay: int = AGNES_RETRY_BASE_DELAY,
) -> requests.Response:
    last_res = None
    for attempt in range(max_retries):
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        last_res = res

        if res.status_code not in (503, 502, 504):
            return res

        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "[vision] Agnes HTTP %s (tentative %d/%d), retry dans %ds...",
                res.status_code, attempt + 1, max_retries, delay,
            )
            time.sleep(delay)

    return last_res


# ==============================================================================
# ★ AGNES — CREATE TASK (avec keyframes corrigés v27.1) ★
# ==============================================================================
def _agnes_create_task(
    prompt: str,
    model_id: str,
    duration: int,
    aspect_ratio: str,
    negative_prompt: Optional[str] = None,
    fps: int = 24,
    mode: str = "ti2vid",
    first_frame: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
) -> Dict[str, Any]:
    ep = provider_manager.get_agnes_endpoints(model_id)
    url = ep["create_url"]
    headers = ep["headers"]

    payload: Dict[str, Any] = {
        "model": ep["model_id"],
        "prompt": prompt,
        "mode": mode,
    }

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
            "[vision] Agnes v2.0 mode=%s : duration=%ss -> num_frames=%s (%.2fs)",
            mode, duration, num_frames, actual_duration,
        )
    else:
        payload["size"] = "720P"
        payload["aspect_ratio"] = aspect_ratio
        seconds = max(ep["min_seconds"], min(ep["max_seconds"], duration))
        payload["seconds"] = str(seconds)
        logger.info("[vision] Agnes flash mode=%s : seconds=%s", mode, seconds)

    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    if mode == "keyframes" and first_frame:
        # Agnes exige une LISTE de 2 images minimum
        if os.path.exists(first_frame):
            with open(first_frame, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            mime = mimetypes.guess_type(first_frame)[0] or "image/png"
            img_data = f"data:{mime};base64,{img_b64}"
        else:
            img_data = first_frame

        payload["image"] = [img_data, img_data]
        logger.info(
            "[vision] Agnes mode keyframes : image ajoutée en liste [debut, fin] (taille: %d)",
            len(img_data),
        )

    elif mode == "multi_reference" and reference_images:
        refs_data: List[str] = []
        for ref_path in reference_images:
            if os.path.exists(ref_path):
                with open(ref_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")
                mime = mimetypes.guess_type(ref_path)[0] or "image/png"
                refs_data.append(f"data:{mime};base64,{img_b64}")
            else:
                refs_data.append(ref_path)

        payload["reference_images"] = refs_data
        logger.info(
            "[vision] Agnes mode multi_reference : %d images ajoutées",
            len(refs_data),
        )

    logger.info(
        "[vision] Agnes create_task model=%s mode=%s url=%s payload_keys=%s",
        ep["model_id"], mode, url, list(payload.keys()),
    )

    res = _agnes_post_with_retry(url, headers, payload)

    if res.status_code >= 400:
        try:
            err = res.json()
            err_txt = json.dumps(err)
        except Exception:
            err_txt = res.text[:800]
        raise RuntimeError(
            f"[vision/agnes_create] HTTP {res.status_code}: {err_txt}"
        )

    data = res.json()

    task_id = (
        data.get("id")
        or data.get("task_id")
        or data.get("video_id")
        or (data.get("data", {}) or {}).get("id")
        or (data.get("data", {}) or {}).get("task_id")
        or (data.get("data", {}) or {}).get("video_id")
    )

    if not task_id:
        raise RuntimeError(
            f"[vision/agnes_create] Pas de task_id dans la réponse: "
            f"{json.dumps(data)[:500]}"
        )

    logger.info("[vision] Agnes tâche créée (mode=%s): id=%s", mode, task_id)

    return {
        "task_id": task_id,
        "raw": data,
        "model_id": ep["model_id"],
        "duration": duration,
        "mode": mode,
    }


# ==============================================================================
# AGNES — POLL RESULT
# ==============================================================================
def _agnes_poll_result(
    task_id: str,
    poll_interval: int = 8,
    max_wait: int = 900,
) -> Tuple[bytes, str]:
    ep = provider_manager.get_agnes_endpoints("agnes-v2.0")
    api_key = ep["api_key"]
    base_url = ep["base_url"]
    headers = {"Authorization": f"Bearer {api_key}"}

    start = time.time()
    last_status = ""

    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            raise TimeoutError(
                f"Agnes vidéo non prête après {max_wait}s (task_id={task_id})"
            )

        url = f"{base_url}/videos/{task_id}"
        res = requests.get(url, headers=headers, timeout=60)

        if res.status_code >= 400:
            try:
                err = res.json()
                err_txt = json.dumps(err)
            except Exception:
                err_txt = res.text[:500]
            raise RuntimeError(
                f"[vision/agnes_poll] HTTP {res.status_code}: {err_txt}"
            )

        data = res.json()

        status = (
            data.get("status")
            or (data.get("data", {}) or {}).get("status")
            or "unknown"
        )
        status = str(status).lower()

        if status != last_status:
            logger.info(
                "[vision] Agnes status=%s (task_id=%s, %ds)",
                status, task_id, int(elapsed),
            )
            last_status = status

        if status in ("completed", "success", "succeeded", "done", "finished"):
            video_url = (
                (data.get("metadata", {}) or {}).get("url")
                or data.get("video_url")
                or data.get("url")
                or data.get("output")
                or (data.get("data", {}) or {}).get("metadata", {}).get("url")
                or (data.get("data", {}) or {}).get("video_url")
                or (data.get("data", {}) or {}).get("url")
                or (data.get("data", {}) or {}).get("output")
            )

            if not video_url:
                raise RuntimeError(
                    f"[vision/agnes_poll] Vidéo prête mais pas d'URL: "
                    f"{json.dumps(data)[:800]}"
                )

            logger.info("[vision] Agnes vidéo prête, téléchargement: %s", video_url)

            if video_url.startswith("http"):
                dl = requests.get(video_url, timeout=300)
                dl.raise_for_status()
                return dl.content, "video/mp4"

            if video_url.startswith("data:video"):
                _, b64 = video_url.split(",", 1)
                return base64.b64decode(b64), "video/mp4"

            raise RuntimeError(f"[vision/agnes_poll] URL vidéo inconnue: {video_url}")

        if status in ("failed", "error", "cancelled"):
            err_msg = (
                data.get("error")
                or data.get("message")
                or (data.get("data", {}) or {}).get("error")
                or "Erreur inconnue"
            )
            raise RuntimeError(f"[vision/agnes_poll] Tâche échouée: {err_msg}")

        logger.info(
            "[vision] Agnes en cours... (%ds) status=%s",
            int(elapsed), status,
        )
        time.sleep(poll_interval)


# ==============================================================================
# AGNES — GENERATE SINGLE CLIP
# ==============================================================================
def _agnes_generate_single_clip(
    prompt: str,
    model_id: str,
    duration: int,
    aspect_ratio: str,
    negative_prompt: Optional[str] = None,
    fps: int = 24,
    poll_interval: int = 8,
    max_wait: int = 900,
    mode: str = "ti2vid",
    first_frame: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
    respect_rate_limit: bool = True,
) -> Dict[str, Any]:
    if respect_rate_limit:
        _agnes_wait_rate_limit()

    task = _agnes_create_task(
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

    video_bytes, mime = _agnes_poll_result(
        task_id=task["task_id"],
        poll_interval=poll_interval,
        max_wait=max_wait,
    )

    return {
        "bytes": video_bytes,
        "mime": mime,
        "duration": duration,
        "task_id": task["task_id"],
        "model_id": task["model_id"],
        "mode": mode,
    }


# ==============================================================================
# AGNES — MULTI-CLIPS
# ==============================================================================
def _agnes_generate_multi_clips(
    prompt: str,
    model_id: str,
    total_duration: int,
    aspect_ratio: str,
    negative_prompt: Optional[str] = None,
    fps: int = 24,
    poll_interval: int = 8,
    max_wait: int = 900,
) -> Dict[str, Any]:
    max_dur = AGNES_V2_MAX_DURATION

    n_full = int(total_duration // max_dur)
    remainder = total_duration - (n_full * max_dur)

    clips_plan: List[float] = [max_dur] * n_full
    if remainder > 0:
        if remainder < AGNES_V2_MIN_DURATION and clips_plan:
            clips_plan[-1] += remainder
        else:
            clips_plan.append(remainder)

    logger.info(
        "[vision] Plan multi-clips Agnes : %s (total %ss)",
        [f"{d:.2f}s" for d in clips_plan], total_duration,
    )

    tmpdir = tempfile.mkdtemp(prefix="bek_agnes_")
    clip_files: List[str] = []

    for i, clip_duration in enumerate(clips_plan, 1):
        clip_prompt = optimize_video_prompt_for_clip(
            base_prompt=prompt,
            clip_index=i,
            total_clips=len(clips_plan),
            clip_duration=int(clip_duration),
            aspect_ratio=aspect_ratio,
        )

        logger.info(
            "[vision] Génération clip Agnes %d/%d (%.2fs)",
            i, len(clips_plan), clip_duration,
        )

        clip = _agnes_generate_single_clip(
            prompt=clip_prompt,
            model_id=model_id,
            duration=int(clip_duration),
            aspect_ratio=aspect_ratio,
            negative_prompt=negative_prompt,
            fps=fps,
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
    _ffmpeg_trim_exact(stitched_path, final_path, float(total_duration))

    with open(final_path, "rb") as f:
        final_bytes = f.read()

    return {
        "bytes": final_bytes,
        "mime": "video/mp4",
        "duration": total_duration,
        "stitched": True,
        "clips": [round(d, 2) for d in clips_plan],
        "model_id": model_id,
    }


# ==============================================================================
# EXTEND VIDEO WITH AGNES
# ==============================================================================
def extend_video_with_agnes(
    video_path: str,
    new_prompt: str,
    model: str = "agnes-v2.0",
    duration: int = 8,
    aspect_ratio: str = "16:9",
    with_audio: bool = True,
    audio_style: str = "default",
    reference_images: Optional[List[str]] = None,
    output_filename: str = "",
    negative_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    if not os.path.exists(video_path):
        return {
            "status": "error",
            "message": f"Vidéo source introuvable : {video_path}",
        }

    if not output_filename:
        base = os.path.splitext(os.path.basename(video_path))[0]
        output_filename = f"{base}_extended_{uuid.uuid4().hex[:6]}.mp4"
    save_path = os.path.abspath(
        os.path.join(GENERATED_DIR, secure_filename(output_filename))
    )

    agnes_model_id = provider_manager.resolve_agnes_model_id(model)
    ep = provider_manager.get_agnes_endpoints(agnes_model_id)

    if not ep["api_key"]:
        return {"status": "error", "message": "AGNES_API_KEY non configurée."}

    try:
        logger.info("[vision] Extension vidéo : extraction dernière frame...")
        last_frame_path = _extract_last_frame(video_path)

        enhanced_prompt = optimize_prompt_for_media(
            new_prompt, media_type="video", style_preset="cinematic_video"
        )
        enhanced_prompt = _enrich_prompt_with_audio(
            enhanced_prompt, with_audio=with_audio, audio_style=audio_style
        )

        if reference_images and len(reference_images) > 0:
            mode = "multi_reference"
            logger.info(
                "[vision] Mode continuité : multi_reference (%d images)",
                len(reference_images),
            )
            clip = _agnes_generate_single_clip(
                prompt=enhanced_prompt,
                model_id=agnes_model_id,
                duration=duration,
                aspect_ratio=aspect_ratio,
                negative_prompt=negative_prompt,
                fps=ep["default_fps"],
                mode=mode,
                reference_images=reference_images,
            )
        else:
            mode = "keyframes"
            logger.info("[vision] Mode continuité : keyframes (last_frame)")
            clip = _agnes_generate_single_clip(
                prompt=enhanced_prompt,
                model_id=agnes_model_id,
                duration=duration,
                aspect_ratio=aspect_ratio,
                negative_prompt=negative_prompt,
                fps=ep["default_fps"],
                mode=mode,
                first_frame=last_frame_path,
            )

        logger.info("[vision] Concaténation avec réencodage...")

        tmpdir = tempfile.mkdtemp(prefix="bek_extend_")
        new_clip_path = os.path.join(tmpdir, "new_clip.mp4")
        with open(new_clip_path, "wb") as f:
            f.write(clip["bytes"])

        concat_result = concat_videos(
            video_paths=[video_path, new_clip_path],
            output_filename=output_filename,
            force_reencode=True,
        )

        if concat_result.get("status") != "success":
            return concat_result

        try:
            if os.path.exists(last_frame_path):
                os.remove(last_frame_path)
        except Exception:
            pass

        final_duration = _get_video_duration(save_path)

        return {
            "status": "success",
            "filepath": save_path,
            "filename": output_filename,
            "original_duration": _get_video_duration(video_path),
            "added_duration": duration,
            "final_duration": final_duration,
            "mode_used": mode,
            "model_id": agnes_model_id,
            "provider": "agnes",
            "with_audio": with_audio,
            "audio_style": audio_style if with_audio else None,
        }

    except Exception as e:
        logger.exception("[vision] Erreur extend_video_with_agnes")
        return {"status": "error", "message": f"Erreur extension : {str(e)}"}


# ==============================================================================
# EXTEND VIDEO MULTIPLE
# ==============================================================================
def extend_video_multiple(
    video_path: str,
    prompts: List[str],
    model: str = "agnes-v2.0",
    duration_per_clip: int = 8,
    aspect_ratio: str = "16:9",
    with_audio: bool = True,
    audio_style: str = "default",
    reference_images: Optional[List[str]] = None,
    output_filename: str = "",
    max_clips: int = AGNES_EXTEND_MAX_CLIPS,
) -> Dict[str, Any]:
    if not os.path.exists(video_path):
        return {
            "status": "error",
            "message": f"Vidéo source introuvable : {video_path}",
        }

    if len(prompts) == 0:
        return {"status": "error", "message": "Aucun prompt fourni."}

    if len(prompts) > max_clips:
        logger.warning(
            "[vision] %d prompts fournis, plafonné à %d (max_clips)",
            len(prompts), max_clips,
        )
        prompts = prompts[:max_clips]

    if not output_filename:
        base = os.path.splitext(os.path.basename(video_path))[0]
        output_filename = f"{base}_extended_x{len(prompts)}_{uuid.uuid4().hex[:6]}.mp4"

    current_video = video_path
    generated_clips: List[str] = []
    total_added = 0

    for i, prompt in enumerate(prompts, 1):
        logger.info(
            "[vision] Extension %d/%d : '%s'",
            i, len(prompts), prompt[:80],
        )

        temp_filename = f"_temp_extend_{i}_{uuid.uuid4().hex[:6]}.mp4"

        result = extend_video_with_agnes(
            video_path=current_video,
            new_prompt=prompt,
            model=model,
            duration=duration_per_clip,
            aspect_ratio=aspect_ratio,
            with_audio=with_audio,
            audio_style=audio_style,
            reference_images=reference_images,
            output_filename=temp_filename,
        )

        if result.get("status") != "success":
            logger.error(
                "[vision] Extension %d échouée : %s",
                i, result.get("message"),
            )
            return {
                "status": "error",
                "message": f"Échec à l'extension {i}/{len(prompts)} : {result.get('message')}",
                "generated_clips": generated_clips,
                "stopped_at": i,
            }

        intermediate_path = result["filepath"]
        generated_clips.append(intermediate_path)
        current_video = intermediate_path
        total_added += result.get("added_duration", duration_per_clip)

    final_path = os.path.abspath(
        os.path.join(GENERATED_DIR, secure_filename(output_filename))
    )
    shutil.copy(current_video, final_path)

    final_duration = _get_video_duration(final_path)
    original_duration = _get_video_duration(video_path)

    return {
        "status": "success",
        "filepath": final_path,
        "filename": output_filename,
        "original_duration": original_duration,
        "total_added": total_added,
        "final_duration": final_duration,
        "clips_count": len(prompts),
        "prompts_used": prompts,
        "model_id": model,
        "provider": "agnes",
        "with_audio": with_audio,
    }


# ==============================================================================
# CONCAT_VIDEOS
# ==============================================================================
def concat_videos(
    video_paths: List[str],
    output_filename: str = "",
    force_reencode: bool = True,
) -> Dict[str, Any]:
    if not video_paths or len(video_paths) < 2:
        return {
            "status": "error",
            "message": "Il faut au moins 2 vidéos pour concaténer.",
        }

    for vp in video_paths:
        if not os.path.exists(vp):
            return {
                "status": "error",
                "message": f"Fichier introuvable : {vp}",
            }

    if not output_filename:
        output_filename = f"concat_{uuid.uuid4().hex[:6]}.mp4"
    final_path = os.path.abspath(
        os.path.join(GENERATED_DIR, secure_filename(output_filename))
    )

    tmpdir = tempfile.mkdtemp(prefix="bek_concat_")

    if not force_reencode:
        codecs = [_detect_video_codec(vp) for vp in video_paths]
        first_codec = codecs[0]
        all_same = all(
            c.get("video_codec") == first_codec.get("video_codec")
            and c.get("width") == first_codec.get("width")
            and c.get("height") == first_codec.get("height")
            for c in codecs[1:]
        )
        if not all_same:
            logger.warning(
                "[vision] Codecs différents détectés → bascule en réencodage forcé"
            )
            force_reencode = True

    try:
        if force_reencode:
            logger.info("[vision] Concat méthode 2 (réencodage) — %d vidéos", len(video_paths))

            inputs = []
            for vp in video_paths:
                inputs.extend(["-i", vp])

            filter_parts = []
            for i in range(len(video_paths)):
                filter_parts.append(f"[{i}:v][{i}:a]")
            filter_complex = (
                "".join(filter_parts)
                + f"concat=n={len(video_paths)}:v=1:a=1[v][a]"
            )

            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "[a]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                final_path,
            ]
            _ffmpeg_run(cmd)
        else:
            logger.info("[vision] Concat méthode 1 (rapide) — %d vidéos", len(video_paths))

            list_file = os.path.join(tmpdir, "list.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                for vp in video_paths:
                    escaped = vp.replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                final_path,
            ]
            _ffmpeg_run(cmd)

        final_duration = _get_video_duration(final_path)

        return {
            "status": "success",
            "filepath": final_path,
            "filename": output_filename,
            "videos_merged": len(video_paths),
            "final_duration": final_duration,
            "method": "reencode" if force_reencode else "fast",
        }

    except Exception as e:
        logger.exception("[vision] Erreur concat_videos")
        return {"status": "error", "message": f"Erreur concaténation : {str(e)}"}


# ==============================================================================
# POINT D'ENTRÉE PUBLIC — VIDÉO
# ==============================================================================
def generate_video_with_provider(
    prompt: str,
    provider: str = "gemini",
    model: str = "veo-3.1-gene-prev",
    output_filename: str = "",
    aspect_ratio: str = "16:9",
    duration: int = 8,
    auto_stitch: bool = True,
    negative_prompt: Optional[str] = None,
    person_generation: str = VEO_DEFAULT_PERSON_GENERATION,
    with_audio: bool = False,
    audio_style: str = "default",
) -> Dict[str, Any]:
    if not output_filename:
        output_filename = f"gen_video_{uuid.uuid4().hex[:8]}.mp4"
    save_path = os.path.abspath(
        os.path.join(GENERATED_DIR, secure_filename(output_filename))
    )

    if provider.lower() == "agnes":
        agnes_model_id = provider_manager.resolve_agnes_model_id(model)
        ep = provider_manager.get_agnes_endpoints(agnes_model_id)

        if not ep["api_key"]:
            return {
                "status": "error",
                "message": "AGNES_API_KEY non configurée dans env.txt.",
            }

        if not ep["is_v2"]:
            duration = max(ep["min_seconds"], min(ep["max_seconds"], duration))
            logger.info("[vision] Agnes flash : duration clampée à %ss", duration)

        enhanced_prompt = optimize_prompt_for_media(
            prompt, media_type="video", style_preset="cinematic_video"
        )
        enhanced_prompt = _enrich_prompt_with_audio(
            enhanced_prompt, with_audio=with_audio, audio_style=audio_style
        )

        try:
            if duration <= AGNES_V2_MAX_DURATION:
                clip = _agnes_generate_single_clip(
                    prompt=enhanced_prompt,
                    model_id=agnes_model_id,
                    duration=duration,
                    aspect_ratio=aspect_ratio,
                    negative_prompt=negative_prompt,
                    fps=ep["default_fps"],
                )

                tmpdir = tempfile.mkdtemp(prefix="bek_agnes_trim_")
                raw_path = os.path.join(tmpdir, "raw.mp4")
                with open(raw_path, "wb") as f:
                    f.write(clip["bytes"])

                _ffmpeg_trim_exact(raw_path, save_path, float(duration))

                final_duration = _get_video_duration(save_path)

                return {
                    "status": "success",
                    "filepath": save_path,
                    "filename": output_filename,
                    "duration": duration,
                    "actual_duration": final_duration,
                    "model_id": clip["model_id"],
                    "provider": "agnes",
                    "task_id": clip["task_id"],
                    "stitched": False,
                    "with_audio": with_audio,
                    "audio_style": audio_style if with_audio else None,
                }
            else:
                result = _agnes_generate_multi_clips(
                    prompt=enhanced_prompt,
                    model_id=agnes_model_id,
                    total_duration=duration,
                    aspect_ratio=aspect_ratio,
                    negative_prompt=negative_prompt,
                    fps=ep["default_fps"],
                )

                with open(save_path, "wb") as f:
                    f.write(result["bytes"])

                final_duration = _get_video_duration(save_path)

                return {
                    "status": "success",
                    "filepath": save_path,
                    "filename": output_filename,
                    "duration": duration,
                    "actual_duration": final_duration,
                    "model_id": result["model_id"],
                    "provider": "agnes",
                    "stitched": True,
                    "clips": result["clips"],
                    "with_audio": with_audio,
                    "audio_style": audio_style if with_audio else None,
                }

        except Exception as e:
            logger.exception("[vision] Erreur generate_video Agnes")
            return {"status": "error", "message": f"Erreur vidéo Agnes : {str(e)}"}

    model_id = provider_manager.resolve_veo_model_id(model)

    if duration not in VEO_SUPPORTED_DURATIONS and duration <= VEO_MAX_SINGLE_CLIP:
        closest = min(VEO_SUPPORTED_DURATIONS, key=lambda d: abs(d - duration))
        logger.warning(
            "[vision] duration=%s non supportée, arrondie à %s", duration, closest
        )
        duration = closest

    enhanced_prompt = optimize_prompt_for_media(
        prompt, media_type="video", style_preset="cinematic_video"
    )

    if with_audio:
        logger.info(
            "[vision] with_audio=True pour Veo (non supporté nativement)."
        )
        enhanced_prompt = _enrich_prompt_with_audio(
            enhanced_prompt, with_audio=True, audio_style=audio_style
        )

    try:
        api_key = get_api_key("GEMINI_API_KEY")
        if not api_key:
            return {
                "status": "error",
                "message": "GEMINI_API_KEY non configurée pour la vidéo.",
            }

        if duration <= VEO_MAX_SINGLE_CLIP:
            clip = _veo_generate_single_clip(
                prompt=enhanced_prompt,
                model_id=model_id,
                api_key=api_key,
                aspect_ratio=aspect_ratio,
                duration=duration,
                negative_prompt=negative_prompt,
                person_generation=person_generation,
            )
            with open(save_path, "wb") as f:
                f.write(clip["bytes"])

            return {
                "status": "success",
                "filepath": save_path,
                "filename": output_filename,
                "duration": duration,
                "model_id": clip.get("model_id", model_id),
                "provider": "gemini",
                "stitched": False,
                "with_audio": with_audio,
                "audio_style": audio_style if with_audio else None,
            }

        if not auto_stitch:
            return {
                "status": "error",
                "message": (
                    f"Veo 3.1 ne génère pas de clip unique de {duration}s. "
                    f"Durées supportées : {VEO_SUPPORTED_DURATIONS}. "
                    f"Active auto_stitch=True pour assembler plusieurs clips."
                ),
            }

        stitched = _veo_generate_stitched(
            prompt=enhanced_prompt,
            model_id=model_id,
            api_key=api_key,
            aspect_ratio=aspect_ratio,
            total_duration=duration,
            negative_prompt=negative_prompt,
            person_generation=person_generation,
        )

        with open(save_path, "wb") as f:
            f.write(stitched["bytes"])

        return {
            "status": "success",
            "filepath": save_path,
            "filename": output_filename,
            "duration": duration,
            "model_id": model_id,
            "provider": "gemini",
            "stitched": True,
            "clips": stitched["clips"],
            "with_audio": with_audio,
            "audio_style": audio_style if with_audio else None,
        }

    except Exception as e:
        logger.exception("[vision] Erreur generate_video Veo")
        return {"status": "error", "message": f"Erreur vidéo Veo : {str(e)}"}


# ==============================================================================
# ÉDITION / FUSION VIDÉO
# ==============================================================================
def merge_and_edit_videos(
    video_paths: Any = None,
    user_prompt: str = "",
    prompt: str = "",
    provider: str = "gemini",
    model: str = "veo-3.1-gene-prev",
    output_filename: str = "",
    aspect_ratio: str = "16:9",
    duration: int = 8,
    auto_stitch: bool = True,
) -> Dict[str, Any]:
    try:
        active_prompt = user_prompt or prompt or "Créer une séquence vidéo cohérente."
        valid_paths = _resolve_existing_media_paths(
            video_paths, (".mp4", ".webm", ".mov")
        )

        if len(valid_paths) >= 2:
            if not output_filename:
                output_filename = f"merged_video_{uuid.uuid4().hex[:8]}.mp4"

            concat_result = concat_videos(
                video_paths=valid_paths,
                output_filename=output_filename,
                force_reencode=True,
            )

            if concat_result.get("status") == "success" and duration:
                final_path = concat_result["filepath"]
                tmpdir = tempfile.mkdtemp(prefix="bek_trim_")
                trimmed = os.path.join(tmpdir, "trimmed.mp4")
                _ffmpeg_trim_exact(final_path, trimmed, float(duration))
                shutil.copy(trimmed, final_path)

            return concat_result

        context = (
            f"Édition basée sur {os.path.basename(valid_paths[0])}. "
            if valid_paths else ""
        )
        return generate_video_with_provider(
            f"{context}Directive: {active_prompt}",
            provider=provider,
            model=model,
            output_filename=output_filename,
            aspect_ratio=aspect_ratio,
            duration=duration,
            auto_stitch=auto_stitch,
        )
    except Exception as e:
        logger.exception("[vision] Erreur merge_and_edit_videos")
        return {"status": "error", "message": f"Erreur édition vidéo : {str(e)}"}