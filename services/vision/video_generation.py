# ==============================================================================
# BEK-v16 — Vision / Video Generation
# ------------------------------------------------------------------------------
# Point d'entrée PUBLIC pour la génération de vidéo.
#   - generate_video_with_provider() : dispatch Agnes / Veo 3.1
#   - Multi-clips + auto-stitch pour Agnes
#   - Multi-clips + auto-stitch pour Veo
#   - Enrichissement prompt + audio
# v28 (2026-09-21) : Extraction depuis vision_legacy.py
# ==============================================================================
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from werkzeug.utils import secure_filename

from core.paths import GENERATED_DIR
from services.prompt_optimizer import optimize_prompt_for_media
from services.vision.agnes_client import (
    _agnes_generate_single_clip,
    _enrich_prompt_with_audio,
)
from services.vision.constants import (
    AGNES_V2_DEFAULT_FPS,
    AGNES_V2_MAX_FRAMES,
    AGNES_V2_MAX_DURATION,
    AGNES_EXTEND_MAX_CLIPS,
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


# ==============================================================================
# HELPERS INTERNES
# ==============================================================================
def _get_api_key(key_name: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.get_api_key(key_name)


def _resolve_veo_model_id(model: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.resolve_veo_model_id(model)


def _resolve_agnes_model_id(model: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.resolve_agnes_model_id(model)


def _resolve_existing_media_paths(
    paths_input,
    extensions: tuple,
) -> List[str]:
    """Résout des chemins de fichiers vidéo existants."""
    from core.paths import FILES_DIR, WORKSPACE_DIR

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

    return resolved


# ==============================================================================
# PLAN MULTI-CLIPS AGNES
# ==============================================================================
def _agnes_plan_clips(total_duration: int) -> List[int]:
    """
    Découpe une durée totale en clips Agnes respectant les limites V2.0.
    Agnes V2.0 : max 441 frames / 24 fps = 18.375s par clip.
    """
    max_clip = int(AGNES_V2_MAX_DURATION)  # 18
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

    # Agnes exige durée minimale ~3.4s (81 frames / 24)
    # Si le dernier clip est trop court, on répartit
    min_clip = 4
    if len(clips) > 1 and clips[-1] < min_clip:
        clips[-2] += clips[-1]
        clips = clips[:-1]

    return clips


# ==============================================================================
# GÉNÉRATION AGNES MULTI-CLIPS
# ==============================================================================
def _generate_video_with_agnes(
    prompt: str,
    model_id: str,
    duration: int,
    aspect_ratio: str,
    with_audio: bool,
    audio_style: str,
    negative_prompt: Optional[str],
    output_path: Optional[str],
) -> Dict[str, Any]:
    """Génère une vidéo avec Agnes, multi-clips si nécessaire."""
    clips_plan = _agnes_plan_clips(duration)
    logger.info(
        "[vision.agnes] Plan multi-clips : %s (total %ss)", clips_plan, duration
    )

    # Prompt enrichi avec audio
    enriched_prompt = _enrich_prompt_with_audio(
        prompt, with_audio=with_audio, audio_style=audio_style
    )

    # Cas 1 : un seul clip
    if len(clips_plan) == 1:
        clip = _agnes_generate_single_clip(
            prompt=enriched_prompt,
            model_id=model_id,
            duration=clips_plan[0],
            aspect_ratio=aspect_ratio,
            negative_prompt=negative_prompt,
            fps=AGNES_V2_DEFAULT_FPS,
            mode="ti2vid",
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
            "with_audio": with_audio,
            "stitched": False,
            "clips": clips_plan,
        }

    # Cas 2 : multi-clips + concat
    tmpdir = tempfile.mkdtemp(prefix="bek_agnes_")
    clip_files: List[str] = []

    for i, clip_duration in enumerate(clips_plan, 1):
        # Enrichir le prompt pour cohérence entre clips
        clip_prompt = (
            f"[Clip {i}/{len(clips_plan)}] {enriched_prompt}. "
            f"Maintain EXACTLY the same characters, colors, style, and "
            f"setting as the other clips. Consistent camera movement."
        )

        logger.info(
            "[vision.agnes] Génération clip %d/%d (%ss)",
            i, len(clips_plan), clip_duration,
        )

        clip = _agnes_generate_single_clip(
            prompt=clip_prompt,
            model_id=model_id,
            duration=clip_duration,
            aspect_ratio=aspect_ratio,
            negative_prompt=negative_prompt,
            fps=AGNES_V2_DEFAULT_FPS,
            mode="ti2vid",
        )

        clip_path = os.path.join(tmpdir, f"clip_{i:02d}.mp4")
        with open(clip_path, "wb") as f:
            f.write(clip["bytes"])
        clip_files.append(clip_path)

    # Concat
    stitched_path = os.path.join(tmpdir, "stitched.mp4")
    _ffmpeg_concat(clip_files, stitched_path)

    # Trim exact à la durée totale
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
        "with_audio": with_audio,
        "stitched": True,
        "clips": clips_plan,
    }


# ==============================================================================
# POINT D'ENTRÉE PUBLIC
# ==============================================================================
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
) -> Dict[str, Any]:
    """
    Génère une vidéo avec Agnes ou Veo 3.1.

    Args:
        prompt        : description en anglais
        provider      : "agnes" (recommandé) ou "gemini" (Veo)
        model         : "agnes-v2.0" ou "veo-3.1-gene-prev"
        output_filename : nom du fichier (auto si vide)
        aspect_ratio  : "16:9", "9:16", "1:1"
        duration      : durée en secondes
        auto_stitch   : si durée > max clip, assembler plusieurs clips
        negative_prompt : éléments à éviter
        person_generation : "allow_all" ou "dont_allow"
        with_audio    : ajouter audio (Agnes uniquement)
        audio_style   : "children", "nature", "music", "cinematic", "dialog"

    Returns:
        {"status": "success", "filepath": ..., "filename": ..., ...}
        ou {"status": "error", "message": ...}
    """
    if not prompt:
        return {"status": "error", "message": "Prompt vide."}

    # Enrichir le prompt avec le style
    enhanced_prompt = optimize_prompt_for_media(
        prompt,
        media_type="video",
        style_preset="cinematic_video",
    )

    # Nom du fichier de sortie
    if not output_filename:
        output_filename = f"gen_video_{os.urandom(4).hex()}.mp4"
    safe_name = secure_filename(output_filename)
    save_path = os.path.abspath(os.path.join(GENERATED_DIR, safe_name))

    # ─── ROUTAGE PROVIDER ───
    provider_lower = (provider or "").lower().strip()

    try:
        # ═══════════════════════════════════════════════════════
        # CAS AGNES
        # ═══════════════════════════════════════════════════════
        if provider_lower == "agnes":
            model_id = _resolve_agnes_model_id(model)
            logger.info(
                "[video_generation] AGNES model=%s duration=%ss audio=%s style=%s",
                model_id, duration, with_audio, audio_style,
            )

            if duration > AGNES_V2_MAX_DURATION and not auto_stitch:
                return {
                    "status": "error",
                    "message": (
                        f"Agnes ne génère pas plus de "
                        f"{int(AGNES_V2_MAX_DURATION)}s par clip. "
                        f"Active auto_stitch=True pour assembler plusieurs clips."
                    ),
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
            )

        # ═══════════════════════════════════════════════════════
        # CAS VEO 3.1 (Google)
        # ═══════════════════════════════════════════════════════
        elif provider_lower in ("gemini", "google", "veo"):
            model_id = _resolve_veo_model_id(model)
            api_key = _get_api_key("GEMINI_API_KEY")

            if not api_key:
                return {
                    "status": "error",
                    "message": "GEMINI_API_KEY non configurée.",
                }

            # Arrondir durée non supportée
            if duration not in VEO_SUPPORTED_DURATIONS and duration <= VEO_MAX_SINGLE_CLIP:
                closest = min(VEO_SUPPORTED_DURATIONS, key=lambda d: abs(d - duration))
                logger.warning(
                    "[video_generation] Veo duration=%s non supportée, arrondie à %s",
                    duration, closest,
                )
                duration = closest

            # Cas 1 : clip unique
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

            # Cas 2 : durée > 8s
            if not auto_stitch:
                return {
                    "status": "error",
                    "message": (
                        f"Veo ne génère pas plus de {VEO_MAX_SINGLE_CLIP}s par clip. "
                        f"Active auto_stitch=True."
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
            return {
                "status": "error",
                "message": f"Provider vidéo inconnu : {provider!r}",
            }

    except Exception as e:
        logger.exception("[video_generation] Erreur generate_video_with_provider")
        return {
            "status": "error",
            "message": f"Erreur vidéo ({provider_lower}) : {str(e)}",
        }