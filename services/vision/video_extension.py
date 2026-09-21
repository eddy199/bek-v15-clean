# ==============================================================================
# BEK-v16 — Vision / Video Extension
# ------------------------------------------------------------------------------
# Extension de vidéos existantes avec continuité personnage.
#   - _extract_first_frame() : capture la couleur initiale du personnage
#   - _extract_last_frame()  : état à la fin du clip source
#   - extend_video_with_agnes() : +N secondes avec vraie continuité
#   - extend_video_multiple() : extensions multiples en série
#
# v28 (2026-09-21) :
#   - Passage de mode "keyframes" → "multi_reference"
#   - Ajout _extract_first_frame() comme 2e référence
#
# v29 (2026-09-21) — CORRECTION CRITIQUE :
#   - Passage en mode "keyframes" avec first_frame = DERNIÈRE frame
#   - Le mode "multi_reference" seul ne force PAS la continuité
#   - Concat FFmpeg de la vidéo source + clip étendu
#
# v30 (2026-09-21) — AMÉLIORATION AUDIO :
#   - Prompt audio renforcé : "clear studio audio, no background noise"
#   - Log de vérification ffprobe sur le fichier final
#
# v31 (2026-09-21) — CROSSFADE VISUEL :
#   - Utilisation de _ffmpeg_concat_crossfade() pour transition douce 0.5s
# ==============================================================================
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.paths import GENERATED_DIR, WORKSPACE_DIR
from services.vision.agnes_client import (
    _agnes_generate_single_clip,
    _enrich_prompt_with_audio,
)
from services.vision.constants import (
    AGNES_V2_DEFAULT_FPS,
    AGNES_EXTEND_MAX_CLIPS,
)
from services.vision.ffmpeg_utils import (
    _ffmpeg_concat,
    _ffmpeg_concat_crossfade,
    _ffmpeg_run,
    _detect_video_codec,
)

logger = logging.getLogger("bek.vision.video_extension")


# ==============================================================================
# HELPERS INTERNES
# ==============================================================================
def _resolve_agnes_model_id(model: str) -> str:
    from provider_manager import provider_manager
    return provider_manager.resolve_agnes_model_id(model)


def _resolve_video_path(video_path: str) -> str:
    """
    Résout un chemin de vidéo :
      - Si absolu et existe → retourné tel quel
      - Sinon cherche dans GENERATED_DIR, uploads/, workspace
      - Supporte le mot-clé "LAST" via _find_last_video()
    """
    from core.paths import FILES_DIR

    if not video_path or video_path in ("LAST", "last"):
        return _find_last_video() or ""

    if os.path.isabs(video_path) and os.path.exists(video_path):
        return video_path

    candidates = [
        os.path.join(GENERATED_DIR, video_path),
        os.path.join(WORKSPACE_DIR, "uploads", video_path),
        os.path.join(WORKSPACE_DIR, video_path),
        os.path.join(FILES_DIR, video_path),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return os.path.abspath(cand)

    return ""


def _find_last_video() -> Optional[str]:
    """Retourne la vidéo la plus récente de GENERATED_DIR."""
    import glob

    try:
        mp4_files = glob.glob(os.path.join(GENERATED_DIR, "*.mp4"))
        mp4_files = [
            f for f in mp4_files
            if not os.path.basename(f).startswith("_temp_")
            and not os.path.basename(f).startswith("last_frame_")
            and not os.path.basename(f).startswith("first_frame_")
            and "_extended_" not in os.path.basename(f)
        ]
        if not mp4_files:
            return None
        mp4_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return mp4_files[0]
    except Exception as e:
        logger.warning("[video_extension] _find_last_video erreur : %s", e)
        return None


# ==============================================================================
# EXTRACTION PREMIÈRE FRAME
# ==============================================================================
def _extract_first_frame(video_path: str, output_path: Optional[str] = None) -> str:
    """Extrait la PREMIÈRE frame d'une vidéo en PNG (référence personnage)."""
    if not output_path:
        base = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(
            GENERATED_DIR,
            f"first_frame_{base}_{uuid.uuid4().hex[:6]}.png",
        )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    _ffmpeg_run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path,
    ])

    if not os.path.exists(output_path):
        raise RuntimeError(
            f"[video_extension] Échec extraction première frame de {video_path}"
        )

    logger.info("[video_extension] Première frame extraite : %s", output_path)
    return output_path


# ==============================================================================
# EXTRACTION DERNIÈRE FRAME
# ==============================================================================
def _extract_last_frame(video_path: str, output_path: Optional[str] = None) -> str:
    """
    Extrait la DERNIÈRE frame d'une vidéo en PNG.
    C'est CETTE frame qui sert de point de départ à l'extension
    → continuité visuelle garantie.
    """
    if not output_path:
        base = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(
            GENERATED_DIR,
            f"last_frame_{base}_{uuid.uuid4().hex[:6]}.png",
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
            f"[video_extension] Échec extraction dernière frame de {video_path}"
        )

    logger.info("[video_extension] Dernière frame extraite : %s", output_path)
    return output_path


# ==============================================================================
# EXTENSION AGNES — LOGIQUE PRINCIPALE (v31)
# ==============================================================================
def _agnes_extend_video_with_agnes(
    video_path: str,
    new_prompt: str,
    model_id: str,
    duration: int = 10,
    with_audio: bool = True,
    audio_style: str = "nature",
) -> Dict[str, Any]:
    """
    Étend une vidéo avec Agnes en gardant la cohérence personnage.

    ★ v31 :
      - Mode "keyframes" avec first_frame = DERNIÈRE frame de la source
      - reference_images = première frame → ancre la couleur du personnage
      - Prompt audio renforcé pour un son studio clair
      - ★ Crossfade visuel 0.5s entre clip original et extension

    Args:
        video_path : chemin absolu de la vidéo source
        new_prompt : description de la SUITE (anglais)
        model_id   : "agnes-video-v2.0"
        duration   : secondes à ajouter
        with_audio : True pour générer de l'audio
        audio_style: "nature", "children", "music", "cinematic"
    """
    logger.info(
        "[video_extension] Extension Agnes : video=%s duration=%ss audio=%s style=%s",
        os.path.basename(video_path), duration, with_audio, audio_style,
    )

    # ─── 1. Extraire la DERNIÈRE frame → point de départ de l'extension ───
    try:
        last_frame_path = _extract_last_frame(video_path)
    except Exception as e:
        logger.error(
            "[video_extension] Impossible d'extraire la dernière frame : %s", e
        )
        return {
            "status": "error",
            "message": f"Extraction dernière frame échouée : {e}",
        }

    # ─── 2. Extraire la PREMIÈRE frame → référence couleur personnage ───
    try:
        first_frame_path = _extract_first_frame(video_path)
    except Exception as e:
        logger.warning(
            "[video_extension] Impossible d'extraire la première frame : %s", e
        )
        first_frame_path = None

    # ─── 3. Prompt enrichi avec audio + continuité + clarté audio ───
    enriched_prompt = _enrich_prompt_with_audio(
        new_prompt, with_audio=with_audio, audio_style=audio_style
    )
    enriched_prompt += (
        ". This is a CONTINUATION of the previous clip. The video MUST start "
        "exactly from the provided first frame and continue naturally from "
        "that exact state. Maintain EXACTLY the same character (colors, face, "
        "fur pattern, eyes, size), same environment, same lighting, and same "
        "visual style. Smooth continuous camera movement. Do NOT reset the scene."
    )

    # ★ v30 : insister sur la qualité audio studio
    if with_audio:
        enriched_prompt += (
            " High quality clear studio audio, crisp and clean sound, "
            "no background noise, no distortion."
        )

    # ─── 4. Générer le clip d'extension en mode keyframes ───
    logger.info(
        "[video_extension] Mode continuité : keyframes "
        "(first_frame=%s, duration=%ss)",
        os.path.basename(last_frame_path), duration,
    )

    reference_images: List[str] = []
    if first_frame_path:
        reference_images.append(first_frame_path)
        logger.info(
            "[video_extension] Référence couleur personnage ajoutée : %s",
            os.path.basename(first_frame_path),
        )

    try:
        clip = _agnes_generate_single_clip(
            prompt=enriched_prompt,
            model_id=model_id,
            duration=duration,
            aspect_ratio="16:9",
            fps=AGNES_V2_DEFAULT_FPS,
            mode="keyframes",
            first_frame=last_frame_path,
            reference_images=reference_images,
        )
    except Exception as e:
        logger.exception("[video_extension] Erreur génération clip")
        return {
            "status": "error",
            "message": f"Erreur génération clip Agnes : {e}",
        }

    # ─── 5. Assembler : vidéo originale + clip étendu avec CROSSFADE v31 ───
    tmpdir = tempfile.mkdtemp(prefix="bek_extend_")

    original_copy = os.path.join(tmpdir, "original.mp4")
    shutil.copy(video_path, original_copy)

    ext_path = os.path.join(tmpdir, "extension.mp4")
    with open(ext_path, "wb") as f:
        f.write(clip["bytes"])

    stitched_path = os.path.join(tmpdir, "stitched.mp4")

    logger.info(
        "[video_extension] Concat FFmpeg avec crossfade 0.5s : original + extension"
    )
    try:
        _ffmpeg_concat_crossfade(
            clip1=original_copy,
            clip2=ext_path,
            output=stitched_path,
            fade_duration=0.5,
        )
    except Exception as e:
        logger.warning(
            "[video_extension] Crossfade échoué (%s) → fallback concat simple", e
        )
        _ffmpeg_concat([original_copy, ext_path], stitched_path)

    # ─── 6. Sauvegarder dans GENERATED_DIR ───
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_filename = f"{base_name}_extended_{uuid.uuid4().hex[:6]}.mp4"
    output_path = os.path.join(GENERATED_DIR, output_filename)

    shutil.copy(stitched_path, output_path)

    # ─── 7. Vérification finale (durée + codec) ───
    try:
        final_duration = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                output_path,
            ],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except Exception:
        final_duration = "unknown"

    # ★ v30 : log des paramètres audio finaux pour diagnostic
    try:
        final_info = _detect_video_codec(output_path)
        logger.info(
            "[video_extension] Vidéo finale : %s | durée=%ss | v=%s a=%s sr=%s ch=%s",
            output_filename,
            final_duration,
            final_info.get("video_codec"),
            final_info.get("audio_codec"),
            final_info.get("sample_rate"),
            final_info.get("channels"),
        )
    except Exception as e:
        logger.warning("[video_extension] Détection codec final échouée : %s", e)

    # Nettoyage du dossier temporaire
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass

    return {
        "status": "success",
        "filepath": output_path,
        "filename": output_filename,
        "duration": float(final_duration) if final_duration != "unknown" else duration,
        "provider": "agnes",
        "model_id": model_id,
        "with_audio": with_audio,
        "mode_used": "keyframes",
        "extended_by": duration,
        "source_video": os.path.basename(video_path),
    }


# ==============================================================================
# POINT D'ENTRÉE PUBLIC — EXTENSION SIMPLE
# ==============================================================================
def extend_video_with_agnes(
    video_path: str,
    new_prompt: str,
    model: str = "agnes-v2.0",
    duration: int = 10,
    with_audio: bool = True,
    audio_style: str = "nature",
) -> Dict[str, Any]:
    """
    Étend une vidéo existante de +N secondes avec Agnes.

    Args:
        video_path : chemin (absolu, relatif, ou "LAST")
        new_prompt : description de la SUITE (en anglais)
        model      : "agnes-v2.0" (défaut)
        duration   : secondes à ajouter (défaut 10)
        with_audio : ajouter audio synchronisé
        audio_style: "nature", "children", "music", "cinematic"

    Returns:
        {"status": "success", "filepath": ..., "extended_by": 10, ...}
    """
    if not new_prompt:
        return {"status": "error", "message": "Prompt d'extension obligatoire."}

    resolved = _resolve_video_path(video_path)
    if not resolved:
        return {
            "status": "error",
            "message": f"Vidéo introuvable : {video_path}",
        }

    try:
        model_id = _resolve_agnes_model_id(model)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Modèle Agnes invalide : {model} ({e})",
        }

    try:
        return _agnes_extend_video_with_agnes(
            video_path=resolved,
            new_prompt=new_prompt,
            model_id=model_id,
            duration=duration,
            with_audio=with_audio,
            audio_style=audio_style,
        )
    except Exception as e:
        logger.exception("[video_extension] Erreur extend_video_with_agnes")
        return {
            "status": "error",
            "message": f"Erreur extension Agnes : {str(e)}",
        }


# ==============================================================================
# POINT D'ENTRÉE PUBLIC — EXTENSIONS MULTIPLES
# ==============================================================================
def extend_video_multiple(
    video_path: str,
    prompts: List[str],
    model: str = "agnes-v2.0",
    duration_per_clip: int = 10,
    with_audio: bool = True,
    audio_style: str = "nature",
    max_clips: int = AGNES_EXTEND_MAX_CLIPS,
) -> Dict[str, Any]:
    """
    Étend une vidéo en série avec plusieurs prompts successifs.

    Args:
        video_path       : chemin de la vidéo initiale
        prompts          : liste de descriptions de suites
        duration_per_clip: secondes par extension (défaut 10)
        max_clips        : nombre max d'extensions (défaut 5)

    Returns:
        {"status": "success", "filepath": ..., "clips": [...]}
    """
    if not prompts or not isinstance(prompts, list):
        return {"status": "error", "message": "Fournis une liste 'prompts'."}

    prompts = prompts[:max_clips]
    logger.info(
        "[video_extension] Extensions multiples : %d clips x %ss",
        len(prompts), duration_per_clip,
    )

    current_video = _resolve_video_path(video_path)
    if not current_video:
        return {
            "status": "error",
            "message": f"Vidéo de départ introuvable : {video_path}",
        }

    clips_done: List[Dict[str, Any]] = []
    original_path = current_video

    try:
        for i, prompt in enumerate(prompts, 1):
            logger.info(
                "[video_extension] Extension %d/%d : %s",
                i, len(prompts), prompt[:80],
            )

            result = extend_video_with_agnes(
                video_path=current_video,
                new_prompt=prompt,
                model=model,
                duration=duration_per_clip,
                with_audio=with_audio,
                audio_style=audio_style,
            )

            if result.get("status") != "success":
                return {
                    "status": "error",
                    "message": (
                        f"Extension {i}/{len(prompts)} échouée : "
                        f"{result.get('message', 'inconnu')}"
                    ),
                    "clips_done": len(clips_done),
                }

            current_video = result["filepath"]
            clips_done.append({
                "index": i,
                "prompt": prompt,
                "filepath": result["filepath"],
                "duration": result.get("duration"),
                "mode_used": result.get("mode_used"),
            })

        return {
            "status": "success",
            "filepath": current_video,
            "filename": os.path.basename(current_video),
            "source_video": os.path.basename(original_path),
            "total_extensions": len(clips_done),
            "duration_per_clip": duration_per_clip,
            "clips": clips_done,
            "provider": "agnes",
            "model_id": _resolve_agnes_model_id(model),
            "with_audio": with_audio,
        }

    except Exception as e:
        logger.exception("[video_extension] Erreur extend_video_multiple")
        return {
            "status": "error",
            "message": f"Erreur extensions multiples : {str(e)}",
            "clips_done": len(clips_done),
        }