# ==============================================================================
# BEK-v16 — Vision / FFmpeg Utils
# ------------------------------------------------------------------------------
# Helpers FFmpeg communs
# v28 (2026-09-20) : Extraction depuis vision.py v27.1
# ==============================================================================
from __future__ import annotations

import json
import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.paths import GENERATED_DIR

logger = logging.getLogger("bek.vision.ffmpeg")


# ==============================================================================
# EXÉCUTION GÉNÉRIQUE
# ==============================================================================
def _ffmpeg_run(cmd: List[str], check_output: bool = False) -> Optional[str]:
    """Exécute une commande FFmpeg."""
    logger.info("[vision.ffmpeg] FFmpeg: %s", " ".join(cmd))
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


# ==============================================================================
# MÉTADONNÉES VIDÉO
# ==============================================================================
def _get_video_duration(path: str) -> float:
    """Retourne la durée d'une vidéo en secondes."""
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
    except Exception as e:
        logger.warning("[vision.ffmpeg] Erreur durée %s : %s", path, e)
        return 0.0


def _detect_video_codec(path: str) -> Dict[str, Any]:
    """Détecte codec, résolution, framerate, audio d'une vidéo."""
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
        a_data = (
            json.loads(result_a.stdout).get("streams", [{}])[0]
            if result_a.stdout.strip()
            else {}
        )

        return {
            "video_codec":  v_data.get("codec_name"),
            "width":        v_data.get("width"),
            "height":       v_data.get("height"),
            "frame_rate":   v_data.get("r_frame_rate"),
            "audio_codec":  a_data.get("codec_name"),
            "sample_rate":  a_data.get("sample_rate"),
            "channels":     a_data.get("channels"),
            "has_audio":    bool(a_data.get("codec_name")),
        }
    except Exception as e:
        logger.warning("[vision.ffmpeg] Erreur détection codec %s : %s", path, e)
        return {}


# ==============================================================================
# EXTRACTION DERNIÈRE FRAME
# ==============================================================================
def _extract_last_frame(video_path: str, output_path: Optional[str] = None) -> str:
    """Extrait la DERNIÈRE frame d'une vidéo en PNG."""
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
            f"Échec extraction dernière frame de {video_path}"
        )

    logger.info("[vision.ffmpeg] Dernière frame extraite: %s", output_path)
    return output_path


# ==============================================================================
# CONCATÉNATION (SANS RÉENCODAGE — rapide)
# ==============================================================================
def _ffmpeg_concat(clip_files: List[str], output: str) -> None:
    """Concat avec FFmpeg concat demuxer (mode -c copy)."""
    list_file = output + ".txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for c in clip_files:
            escaped = c.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    _ffmpeg_run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", output,
    ])


# ==============================================================================
# TRIM
# ==============================================================================
def _ffmpeg_trim(input_path: str, output: str, duration: int) -> None:
    """Coupe une vidéo à une durée entière (rapide)."""
    _ffmpeg_run([
        "ffmpeg", "-y", "-i", input_path,
        "-t", str(duration), "-c", "copy", output,
    ])


def _ffmpeg_trim_exact(input_path: str, output: str, duration: float) -> None:
    """Découpe précise à la durée demandée (supporte décimales)."""
    duration_str = f"{duration:.3f}"
    logger.info("[vision.ffmpeg] Trim exact : %s s", duration_str)

    _ffmpeg_run([
        "ffmpeg", "-y", "-i", input_path,
        "-t", duration_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-avoid_negative_ts", "make_zero",
        output,
    ])