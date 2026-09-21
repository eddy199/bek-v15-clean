# ==============================================================================
# BEK-v16 — Vision / Video Concat
# ------------------------------------------------------------------------------
# Assemblage et fusion de vidéos :
#   - concat_videos()          : concatène N vidéos locales (FFmpeg copy)
#   - merge_and_edit_videos()  : fusionne OU génère via Veo si pas de source
# v28 (2026-09-21) : Extraction depuis vision_legacy.py
# ==============================================================================
from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from werkzeug.utils import secure_filename

from core.paths import FILES_DIR, GENERATED_DIR, WORKSPACE_DIR
from services.vision.ffmpeg_utils import (
    _ffmpeg_concat,
    _ffmpeg_run,
    _ffmpeg_trim,
)

logger = logging.getLogger("bek.vision.video_concat")


# ==============================================================================
# HELPERS INTERNES
# ==============================================================================
def _resolve_existing_media_paths(
    paths_input: Union[str, List[str], None],
    extensions: tuple,
) -> List[str]:
    """
    Résout une liste de chemins de fichiers média existants.
    Cherche dans GENERATED_DIR, FILES_DIR, WORKSPACE_DIR.
    """
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


def _get_latest_media_file(
    directory: str,
    extensions: tuple = (".mp4", ".webm", ".mov"),
) -> Optional[str]:
    """Retourne le fichier média le plus récent."""
    if not os.path.exists(directory):
        return None
    try:
        candidates = [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if f.lower().endswith(extensions) and not f.startswith(".")
            and not f.startswith("_temp_")
            and not f.startswith("last_frame_")
            and not f.startswith("first_frame_")
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return candidates[0]
    except Exception:
        return None


# ==============================================================================
# CONCATÉNATION SIMPLE
# ==============================================================================
def concat_videos(
    video_paths: List[str],
    output_path: Optional[str] = None,
    target_duration: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Concatène N vidéos locales avec FFmpeg (mode copy, sans réencodage).

    Args:
        video_paths     : liste de chemins (absolus ou noms de fichiers)
        output_path     : chemin de sortie (auto si None)
        target_duration : si spécifié, coupe le résultat à cette durée

    Returns:
        {"status": "success", "filepath": ..., "videos_merged": N}
    """
    if not video_paths or not isinstance(video_paths, list):
        return {
            "status": "error",
            "message": "Liste 'video_paths' vide ou invalide.",
        }

    valid_paths = _resolve_existing_media_paths(
        video_paths, (".mp4", ".webm", ".mov")
    )

    if len(valid_paths) < 1:
        return {
            "status": "error",
            "message": "Aucune vidéo valide trouvée.",
        }

    # Résoudre le chemin de sortie
    if not output_path:
        output_path = os.path.join(
            GENERATED_DIR, f"merged_video_{uuid.uuid4().hex[:8]}.mp4"
        )
    safe_output = os.path.abspath(
        os.path.join(
            GENERATED_DIR,
            secure_filename(os.path.basename(output_path)),
        )
    )
    Path(safe_output).parent.mkdir(parents=True, exist_ok=True)

    # Cas trivial : une seule vidéo
    if len(valid_paths) == 1:
        logger.info(
            "[video_concat] Une seule vidéo, copie directe vers %s", safe_output
        )
        shutil.copy(valid_paths[0], safe_output)

        if target_duration:
            tmp = safe_output + ".trim.mp4"
            _ffmpeg_trim(safe_output, tmp, target_duration)
            shutil.move(tmp, safe_output)

        return {
            "status": "success",
            "filepath": safe_output,
            "filename": os.path.basename(safe_output),
            "videos_merged": 1,
        }

    # Concat multi-vidéos via FFmpeg
    logger.info(
        "[video_concat] Concaténation de %d vidéos → %s",
        len(valid_paths), safe_output,
    )

    tmpdir = tempfile.mkdtemp(prefix="bek_concat_")
    stitched_tmp = os.path.join(tmpdir, "stitched.mp4")

    try:
        _ffmpeg_concat(valid_paths, stitched_tmp)
    except Exception as e:
        logger.exception("[video_concat] FFmpeg concat échoué")
        return {
            "status": "error",
            "message": f"FFmpeg concat échoué : {e}",
        }

    # Trim optionnel
    if target_duration:
        trimmed = os.path.join(tmpdir, "trimmed.mp4")
        try:
            _ffmpeg_trim(stitched_tmp, trimmed, target_duration)
            shutil.copy(trimmed, safe_output)
        except Exception as e:
            logger.warning(
                "[video_concat] Trim échoué, copie du fichier complet : %s", e
            )
            shutil.copy(stitched_tmp, safe_output)
    else:
        shutil.copy(stitched_tmp, safe_output)

    return {
        "status": "success",
        "filepath": safe_output,
        "filename": os.path.basename(safe_output),
        "videos_merged": len(valid_paths),
        "target_duration": target_duration,
    }


# ==============================================================================
# FUSION / ÉDITION
# ==============================================================================
def merge_and_edit_videos(
    video_paths: Any = None,
    user_prompt: str = "",
    prompt: str = "",
    provider: str = "agnes",
    model: str = "agnes-v2.0",
    output_filename: str = "",
    aspect_ratio: str = "16:9",
    duration: int = 5,
    auto_stitch: bool = True,
) -> Dict[str, Any]:
    """
    Fusionne plusieurs vidéos OU génère une nouvelle vidéo si pas de source.

    Comportement :
      - Si video_paths contient >= 2 vidéos locales → concat FFmpeg + trim
      - Sinon → génère via generate_video_with_provider (Agnes ou Veo)

    Args:
        video_paths    : liste de vidéos à fusionner (optionnel)
        user_prompt    : prompt utilisateur
        prompt         : alias de user_prompt
        provider       : "agnes" (défaut) ou "gemini"
        model          : "agnes-v2.0" ou "veo-3.1-gene-prev"
        output_filename: nom de sortie (auto si vide)
        aspect_ratio   : format
        duration       : durée cible
        auto_stitch    : multi-clips si durée > max

    Returns:
        {"status": "success", "filepath": ..., ...}
    """
    active_prompt = user_prompt or prompt or "Créer une séquence vidéo cohérente."

    # Résoudre les chemins fournis
    valid_paths = _resolve_existing_media_paths(
        video_paths, (".mp4", ".webm", ".mov")
    )

    # ─── Cas A : au moins 2 vidéos locales → concat ───
    if len(valid_paths) >= 2:
        logger.info(
            "[video_concat] Fusion locale de %d vidéos", len(valid_paths)
        )

        if not output_filename:
            output_filename = f"merged_video_{uuid.uuid4().hex[:8]}.mp4"

        result = concat_videos(
            video_paths=valid_paths,
            output_path=output_filename,
            target_duration=duration if duration else None,
        )

        if result.get("status") == "success":
            result["videos_merged"] = len(valid_paths)
            result["mode"] = "concat_local"

        return result

    # ─── Cas B : génération via provider ───
    context = ""
    if valid_paths:
        context = f"Édition basée sur {os.path.basename(valid_paths[0])}. "

    final_prompt = f"{context}Directive: {active_prompt}"

    logger.info(
        "[video_concat] Génération via provider=%s (pas assez de vidéos)",
        provider,
    )

    from services.vision.video_generation import generate_video_with_provider

    return generate_video_with_provider(
        prompt=final_prompt,
        provider=provider,
        model=model,
        output_filename=output_filename,
        aspect_ratio=aspect_ratio,
        duration=duration,
        auto_stitch=auto_stitch,
    )