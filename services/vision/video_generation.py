# ==============================================================================
# BEK-v16 — Vision / Video Generation (v32.2)
# ------------------------------------------------------------------------------
# v32.2 (2026-09-30) : Fix _resolve_existing_media_paths
#   - Ajoute UPLOADS_DIR dans les dossiers résolus
#   - Le fallback ne perd plus les images (uploads/...)
# ==============================================================================
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from werkzeug.utils import secure_filename

from core.paths import GENERATED_DIR
from services.prompt_optimizer import (
    optimize_prompt_for_media,
    suggest_agnes_mode_v2,
    build_agnes_reference_prompt,
)
from services.vision.agnes_client import (
    _agnes_generate_single_clip,
    _enrich_prompt_with_audio,
    _is_agnes_v25,
)
from services.vision.constants import (
    AGNES_V2_DEFAULT_FPS,
    AGNES_V2_MAX_DURATION,
    VEO_MAX_SINGLE_CLIP,
    VEO_MIN_CLIP,
    VEO_SUPPORTED_DURATIONS,
)
from services.vision.ffmpeg_utils import (
    _ffmpeg_concat,
    _ffmpeg_trim_exact,
)
from services.vision.veo_client import (
    _veo_generate_single_clip,
    _veo_generate_stitched,
)

logger = logging.getLogger("bek.vision.video_generation")


def _get_api_key(key_name: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.get_api_key(key_name)


def _resolve_veo_model_id(model: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.resolve_veo_model_id(model)


def _resolve_agnes_model_id(model: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.resolve_agnes_model_id(model)


def _resolve_existing_media_paths(paths_input, extensions: tuple) -> List[str]:
    """Résout des chemins de fichiers (inclut uploads/)."""
    from core.paths import FILES_DIR, WORKSPACE_DIR

    # ★ v32.2 — Ajouter UPLOADS_DIR dans les dossiers résolus
    try:
        from core.paths import UPLOADS_DIR
    except ImportError:
        UPLOADS_DIR = os.path.join(WORKSPACE_DIR, "uploads")

    resolved: List[str] = []
    raw_list = [paths_input] if isinstance(paths_input, str) else (paths_input or [])

    for raw in raw_list:
        if not raw or not isinstance(raw, str):
            continue
        clean_name = os.path.basename(raw.strip("\"' \r\n"))
        for base_dir in [GENERATED_DIR, FILES_DIR, WORKSPACE_DIR, UPLOADS_DIR]:
            candidate = os.path.abspath(os.path.join(base_dir, clean_name))
            if os.path.exists(candidate) and os.path.isfile(candidate):
                resolved.append(candidate)
                break

    return resolved


def _agnes_plan_clips(total_duration: int) -> List[int]:
    max_clip = int(AGNES_V2_MAX_DURATION)
    if total_duration <= max_clip:
        return [total_duration]

    clips: List[int] = []
    remaining = total_duration
    while remaining > 0:
        if remaining <= max_clip:
            clips.append(remaining)
            break
        clips.append(max_clip)
        remaining -= max_clip

    min_clip = 4
    if len(clips) > 1 and clips[-1] < min_clip:
        clips[-2] += clips[-1]
        clips = clips[:-1]

    return clips


def _generate_video_with_agnes(
    prompt, model_id, duration, aspect_ratio,
    with_audio, audio_style, negative_prompt, output_path,
    image_paths=None, style_preset="cardboard_3d",
    resolution: str = "1080P",
) -> Dict[str, Any]:
    reference_images: List[str] = []
    if image_paths:
        reference_images = _resolve_existing_media_paths(
            image_paths, (".png", ".jpg", ".jpeg", ".webp")
        )
        logger.info(
            "[video_generation] %d image(s) : %s",
            len(reference_images),
            [os.path.basename(p) for p in reference_images],
        )

    auto_mode = suggest_agnes_mode_v2(model_id, len(reference_images))
    is_v25 = _is_agnes_v25(model_id)

    logger.info(
        "[video_generation] Mode Agnes : %s (modèle=%s, V2.5=%s, images=%d)",
        auto_mode, model_id, is_v25, len(reference_images),
    )

    enriched_prompt = _enrich_prompt_with_audio(
        prompt, with_audio=with_audio, audio_style=audio_style
    )

    if reference_images and is_v25 and auto_mode == "reference":
        enriched_prompt = build_agnes_reference_prompt(
            base_prompt=enriched_prompt,
            num_images=len(reference_images),
        )
        logger.info("[video_generation] Prompt V2.5 <Picture N> construit")

    if reference_images and not is_v25:
        face_lock = (
            " CRITICAL: Reference images show EXACT people. "
            "Preserve their EXACT facial features: same face, eyes, nose, "
            "mouth, hair, skin tone. This is a STYLIZED CARICATURE."
        )
        enriched_prompt += face_lock
        logger.info("[video_generation] FACE LOCK ajouté (V2.0)")

    clips_plan = _agnes_plan_clips(duration)
    logger.info("[vision.agnes] Plan clips : %s (total %ss)", clips_plan, duration)

    # ─── UN SEUL CLIP ───
    if len(clips_plan) == 1:
        first_frame = None
        if auto_mode == "keyframes" and reference_images:
            first_frame = reference_images[0]
            logger.info(
                "[video_generation] keyframes : first_frame=%s",
                os.path.basename(first_frame),
            )

        clip = _agnes_generate_single_clip(
            prompt=enriched_prompt,
            model_id=model_id,
            duration=clips_plan[0],
            aspect_ratio=aspect_ratio,
            negative_prompt=negative_prompt,
            fps=AGNES_V2_DEFAULT_FPS,
            mode=auto_mode,
            first_frame=first_frame,
            reference_images=reference_images if reference_images else None,
            resolution=resolution,
        )

        if not output_path:
            output_path = os.path.join(
                GENERATED_DIR, f"agnes_video_{os.urandom(4).hex()}.mp4"
            )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(clip["bytes"])

        return {
            "status": "success",
            "filepath": output_path,
            "filename": os.path.basename(output_path),
            "duration": clips_plan[0],
            "provider": "agnes",
            "model_id": model_id,
            "model_version": "2.5" if is_v25 else "2.0",
            "with_audio": with_audio,
            "stitched": False,
            "clips": clips_plan,
            "mode_used": auto_mode,
            "reference_images_count": len(reference_images),
        }

    # ─── MULTI-CLIPS ───
    tmpdir = tempfile.mkdtemp(prefix="bek_agnes_")
    clip_files: List[str] = []

    for i, clip_duration in enumerate(clips_plan, 1):
        if i == 1 and auto_mode == "keyframes" and reference_images:
            clip_mode = "keyframes"
            clip_first_frame = reference_images[0]
            clip_refs = None
        elif reference_images:
            clip_mode = auto_mode
            clip_first_frame = None
            clip_refs = reference_images
        else:
            clip_mode = "ti2vid"
            clip_first_frame = None
            clip_refs = None

        clip_prompt = (
            f"[Clip {i}/{len(clips_plan)}] {enriched_prompt}. "
            f"Maintain EXACTLY the same characters, colors, style."
        )

        logger.info(
            "[vision.agnes] Clip %d/%d (%ss) mode=%s",
            i, len(clips_plan), clip_duration, clip_mode,
        )

        clip = _agnes_generate_single_clip(
            prompt=clip_prompt,
            model_id=model_id,
            duration=clip_duration,
            aspect_ratio=aspect_ratio,
            negative_prompt=negative_prompt,
            fps=AGNES_V2_DEFAULT_FPS,
            mode=clip_mode,
            first_frame=clip_first_frame,
            reference_images=clip_refs,
        )

        clip_path = os.path.join(tmpdir, f"clip_{i:02d}.mp4")
        with open(clip_path, "wb") as f:
            f.write(clip["bytes"])
        clip_files.append(clip_path)

    stitched_path = os.path.join(tmpdir, "stitched.mp4")
    _ffmpeg_concat(clip_files, stitched_path)

    if not output_path:
        output_path = os.path.join(
            GENERATED_DIR, f"agnes_video_{os.urandom(4).hex()}.mp4"
        )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg_trim_exact(stitched_path, output_path, duration)

    return {
        "status": "success",
        "filepath": output_path,
        "filename": os.path.basename(output_path),
        "duration": duration,
        "provider": "agnes",
        "model_id": model_id,
        "model_version": "2.5" if is_v25 else "2.0",
        "with_audio": with_audio,
        "stitched": True,
        "clips": clips_plan,
        "mode_used": auto_mode,
        "reference_images_count": len(reference_images),
    }


def generate_video_with_provider(
    prompt: str,
    provider: str = "agnes",
    model: str = "agnes-v2.0",
    output_filename: str = "",
    aspect_ratio: str = "16:9",
    duration: int = 5,
    auto_stitch: bool = True,
    negative_prompt: Optional[str] = None,
    person_generation: str = "allow_all",
    with_audio: bool = True,
    audio_style: str = "children",
    image_paths: Optional[List[str]] = None,
    reference_images: Optional[List[str]] = None,
    style_preset: str = "auto",
    resolution: str = "1080P",
) -> Dict[str, Any]:
    if not prompt:
        return {"status": "error", "message": "Prompt vide."}

    refs = reference_images or image_paths
    if isinstance(refs, str):
        refs = [refs]

    effective_style = style_preset
    if not style_preset or style_preset == "auto":
        from services.prompt_optimizer import detect_style_from_prompt
        detected = detect_style_from_prompt(prompt)
        effective_style = detected or "cardboard_3d"
        logger.info("[video_generation] Style auto : %s", effective_style)

    enhanced_prompt = optimize_prompt_for_media(
        prompt,
        media_type="video",
        style_preset=effective_style,
        preserve_faces=bool(refs),
        image_count=len(refs) if refs else 0,
    )

    if not output_filename:
        output_filename = f"gen_video_{os.urandom(4).hex()}.mp4"
    safe_name = secure_filename(output_filename)
    save_path = os.path.abspath(os.path.join(GENERATED_DIR, safe_name))

    provider_lower = (provider or "").lower().strip()

    try:
        if provider_lower == "agnes":
            model_id = _resolve_agnes_model_id(model)
            logger.info(
                "[video_generation] AGNES model=%s duration=%ss refs=%d",
                model_id, duration, len(refs) if refs else 0,
            )

            if duration > AGNES_V2_MAX_DURATION and not auto_stitch:
                return {
                    "status": "error",
                    "message": f"Active auto_stitch=True pour durée > {int(AGNES_V2_MAX_DURATION)}s",
                }

            return _generate_video_with_agnes(
                prompt=enhanced_prompt,
                model_id=model_id,
                duration=duration,
                aspect_ratio=aspect_ratio,
                with_audio=with_audio,
                audio_style=audio_style,
                negative_prompt=negative_prompt,
                output_path=save_path,
                image_paths=refs,
                style_preset=effective_style,
                resolution=resolution,
            )

        elif provider_lower in ("gemini", "google", "veo"):
            model_id = _resolve_veo_model_id(model)
            api_key = _get_api_key("GEMINI_API_KEY")

            if not api_key:
                return {"status": "error", "message": "GEMINI_API_KEY non configurée."}

            if duration not in VEO_SUPPORTED_DURATIONS and duration <= VEO_MAX_SINGLE_CLIP:
                closest = min(VEO_SUPPORTED_DURATIONS, key=lambda d: abs(d - duration))
                duration = closest

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
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(clip["bytes"])

                return {
                    "status": "success",
                    "filepath": save_path,
                    "filename": safe_name,
                    "duration": duration,
                    "provider": "veo",
                    "model_id": clip.get("model_id", model_id),
                    "with_audio": False,
                    "stitched": False,
                }

            if not auto_stitch:
                return {"status": "error", "message": "Active auto_stitch=True"}

            stitched = _veo_generate_stitched(
                prompt=enhanced_prompt,
                model_id=model_id,
                api_key=api_key,
                aspect_ratio=aspect_ratio,
                total_duration=duration,
                negative_prompt=negative_prompt,
                person_generation=person_generation,
            )
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(stitched["bytes"])

            return {
                "status": "success",
                "filepath": save_path,
                "filename": safe_name,
                "duration": duration,
                "provider": "veo",
                "model_id": model_id,
                "with_audio": False,
                "stitched": True,
                "clips": stitched.get("clips", []),
            }

        else:
            return {"status": "error", "message": f"Provider inconnu : {provider!r}"}

    except Exception as e:
        logger.exception("[video_generation] Erreur")
        return {"status": "error", "message": f"Erreur vidéo : {str(e)}"}