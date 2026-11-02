# ==============================================================================
# BEK-v16 — Vision / Video Generation (v32.4 — Cascade Agnes 2.5 → Veo 3.1)
# ------------------------------------------------------------------------------
# ★ v32.4 (2026-10-17) : AGNES 2.0 SUPPRIMÉ (modèle mort chez Agnes)
#   - Retrait total d'Agnes 2.0 de la cascade (HTTP 503 model_not_found)
#   - Cascade : Agnes 2.5 → (attente 30s) → Veo 3.1 → erreur claire
#   - Messages d'erreur enrichis (429 rate limit, 503 quota, etc.)
#   - ★ AUCUNE autre fonctionnalité modifiée (100% compatible v32.3)
# v32.3 (2026-10-16) : FALLBACK INTELLIGENT VIDÉO
# ==============================================================================
from __future__ import annotations

import logging
import os
import tempfile
import time
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
    AgnesError,
    AgnesRateLimitError,
    AgnesServerError,
    AgnesClientError,
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


# ══════════════════════════════════════════════════════════════════════════════
# ★ v32.4 — CONSTANTES (Agnes 2.0 retiré)
# ══════════════════════════════════════════════════════════════════════════════

# Attente avant fallback (politique Agnes : 30-60s entre générations)
_FALLBACK_WAIT_SECONDS = 30

# Modèle Agnes prioritaire (v2.5 Flash) — SEUL modèle Agnes valide
_AGNES_PRIMARY_MODEL = "agnes-video-2.5-flash"

# Modèle Veo par défaut (fallback)
_VEO_DEFAULT_MODEL = "veo-3.1-generate-preview"

# ★ v32.4 — Message d'erreur final enrichi
_FINAL_ERROR_TEMPLATE = (
    "❌ **Tous les providers vidéo sont indisponibles.**\n\n"
    "**Cascade essayée :**\n"
    "1. Agnes 2.5 Flash → {agnes_err}\n"
    "2. Veo 3.1 → {veo_err}\n\n"
    "**Que faire ?**\n"
    "- ⏳ **Attendre 60-120s** (rate limits temporaires)\n"
    "- 💳 **Vérifier ton plan** Agnes (free tier a des limites strictes)\n"
    "- 💳 **Vérifier ton quota** Google Cloud (Veo)\n"
    "- 🖼️ **Essayer avec une image** en attendant (`generate_image`)\n"
)


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


# ══════════════════════════════════════════════════════════════════════════════
# ★ v32.4 — HELPERS DE FALLBACK (Agnes 2.0 RETIRÉ)
# ══════════════════════════════════════════════════════════════════════════════

def _should_wait_before_fallback(exception: Exception) -> bool:
    """
    ★ v32.4 — Détermine si l'erreur justifie une attente de 30s avant fallback.

    Règles :
      - AgnesRateLimitError (429) → attente 30s
      - AgnesServerError (502/503/504/500) → attente 30s
      - TimeoutError → attente 30s
      - AgnesClientError (400/401/403) → PAS d'attente (erreur client)
    """
    if isinstance(exception, (AgnesRateLimitError, AgnesServerError)):
        return True
    if isinstance(exception, TimeoutError):
        return True
    return False


def _format_rate_limit_error(exception: Exception) -> str:
    """
    ★ v32.4 — Formate un message d'erreur lisible selon le type.
    """
    if isinstance(exception, AgnesRateLimitError):
        return "Rate limit free tier atteint (429) — attends 60-120s ou upgrade"
    if isinstance(exception, AgnesServerError):
        status = getattr(exception, "http_status", 500)
        return f"Erreur serveur Agnes ({status}) — modèle peut-être surchargé"
    if isinstance(exception, AgnesClientError):
        status = getattr(exception, "http_status", 400)
        return f"Erreur client Agnes ({status}) — paramètres invalides"
    if isinstance(exception, TimeoutError):
        return "Timeout — génération trop longue"
    return f"Erreur inconnue : {type(exception).__name__}"


def _generate_video_with_veo_fallback(
    enhanced_prompt: str,
    save_path: str,
    safe_name: str,
    aspect_ratio: str,
    duration: int,
    negative_prompt: Optional[str],
    person_generation: str,
) -> Dict[str, Any]:
    """
    ★ v32.4 — Encapsule l'appel Veo pour le fallback.

    Returns:
        Dict avec status="success" ou lève une exception.
    """
    model_id = _resolve_veo_model_id(_VEO_DEFAULT_MODEL)
    api_key = _get_api_key("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY non configurée pour le fallback Veo.")

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
            "fallback_used": True,
            "fallback_from": "agnes-2.5",
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
        "fallback_used": True,
        "fallback_from": "agnes-2.5",
    }


# ══════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE DE GÉNÉRATION AGNES
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# ★ v32.4 — FONCTION PRINCIPALE AVEC CASCADE AGNES 2.5 → VEO 3.1
# ══════════════════════════════════════════════════════════════════════════════

def generate_video_with_provider(
    prompt: str,
    provider: str = "agnes",
    model: str = "agnes-v2.5-flash",
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
    """
    ★ v32.4 — Génération vidéo avec cascade Agnes 2.5 → Veo 3.1.

    Cascade (si provider="agnes") :
      1. Agnes 2.5 Flash (primary)
         ↓ échec (429/503/timeout) → attente 30s
         ↓ échec (400/401/403) → pas d'attente
      2. Veo 3.1 (fallback)
         ↓ échec
      3. Message d'erreur clair (rate limits, quémandage upgrade)

    Agnes 2.0 a été SUPPRIMÉ (modèle mort chez Agnes — HTTP 503 model_not_found).

    Si provider="veo" (explicite) :
      → Comportement inchangé (pas de fallback, respect du choix utilisateur)
    """
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

    # ══════════════════════════════════════════════════════════════════════════
    # ★ v32.4 — CAS 1 : provider="agnes" → cascade Agnes 2.5 → Veo 3.1
    # ══════════════════════════════════════════════════════════════════════════
    if provider_lower == "agnes":
        logger.info(
            "[video_generation] ★ CASCADE v32.4 AGNES 2.5 → VEO 3.1 "
            "(Agnes 2.0 retiré — modèle mort)"
        )

        agnes_error: Optional[Exception] = None
        veo_error: Optional[Exception] = None

        # ─── Tentative 1 : Agnes 2.5 ───
        logger.info("[video_generation] [1/2] Agnes 2.5 en cours...")
        try:
            return _generate_video_with_agnes(
                prompt=enhanced_prompt,
                model_id=_AGNES_PRIMARY_MODEL,
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
        except (AgnesRateLimitError, AgnesServerError, AgnesClientError, TimeoutError, Exception) as e:
            agnes_error = e
            error_type = type(e).__name__
            http_status = getattr(e, "http_status", 0)

            logger.warning(
                "[video_generation] ⚠️ Agnes 2.5 échoué (%s, HTTP %s) : %s",
                error_type, http_status, str(e)[:200],
            )

            # ★ v32.4 — Attente 30s si justifié (429/503/timeout)
            if _should_wait_before_fallback(e):
                logger.info(
                    "[video_generation] ⏳ Attente %ds (politique Agnes : "
                    "30-60s entre générations) avant fallback Veo...",
                    _FALLBACK_WAIT_SECONDS,
                )
                time.sleep(_FALLBACK_WAIT_SECONDS)

        # ─── Tentative 2 : Veo 3.1 ───
        logger.info("[video_generation] [2/2] 🔄 Fallback Veo 3.1...")
        try:
            return _generate_video_with_veo_fallback(
                enhanced_prompt=enhanced_prompt,
                save_path=save_path,
                safe_name=safe_name,
                aspect_ratio=aspect_ratio,
                duration=duration,
                negative_prompt=negative_prompt,
                person_generation=person_generation,
            )
        except Exception as e_veo:
            veo_error = e_veo
            logger.error(
                "[video_generation] ⚠️ Veo 3.1 échoué (%s) : %s",
                type(e_veo).__name__, str(e_veo)[:300],
            )

        # ─── Échec total : message d'erreur enrichi ───
        agnes_err_msg = _format_rate_limit_error(agnes_error) if agnes_error else "inconnue"
        veo_err_msg = (
            f"Quota Google Cloud épuisé (429) — vérifier billing"
            if "429" in str(veo_error) or "quota" in str(veo_error).lower()
            else f"Erreur : {str(veo_error)[:150]}"
        ) if veo_error else "inconnue"

        final_msg = _FINAL_ERROR_TEMPLATE.format(
            agnes_err=agnes_err_msg,
            veo_err=veo_err_msg,
        )

        logger.error(
            "[video_generation] ❌ ÉCHEC TOTAL — Agnes 2.5 (%s) + Veo 3.1 (%s)",
            agnes_err_msg, veo_err_msg,
        )

        return {
            "status": "error",
            "message": final_msg,
            "provider_errors": {
                "agnes_2_5": agnes_err_msg,
                "veo_3_1": veo_err_msg,
            },
            "suggestion": (
                "Attends 60-120s puis réessaie, ou vérifie tes plans "
                "Agnes / Google Cloud. En attendant, tu peux générer "
                "une image avec `generate_image`."
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # ★ v32.4 — CAS 2 : provider="veo" explicite → pas de fallback
    # ══════════════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════════════
    # ★ v32.4 — CAS 3 : provider inconnu
    # ══════════════════════════════════════════════════════════════════════════
    else:
        return {"status": "error", "message": f"Provider inconnu : {provider!r}"}