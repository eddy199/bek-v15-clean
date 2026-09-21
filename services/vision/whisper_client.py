# ==============================================================================
# BEK-v16 — Vision / Whisper Client
# ------------------------------------------------------------------------------
# Génération de sous-titres automatiques via OpenAI Whisper (local, gratuit).
#   - generate_subtitles_from_video() : transcrit une vidéo en .srt
#   - burn_subtitles_into_video()     : incruste les sous-titres dans la vidéo
#
# v32 (2026-09-21) : Création initiale
# ==============================================================================
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import whisper  # pip install openai-whisper

from core.paths import GENERATED_DIR, WORKSPACE_DIR

logger = logging.getLogger("bek.vision.whisper")

# Cache des modèles Whisper (évite de recharger à chaque appel)
_WHISPER_MODELS_CACHE: Dict[str, Any] = {}


# ==============================================================================
# HELPERS INTERNES
# ==============================================================================
def _load_whisper_model(model_name: str = "base"):
    """Charge un modèle Whisper (avec cache)."""
    if model_name in _WHISPER_MODELS_CACHE:
        return _WHISPER_MODELS_CACHE[model_name]

    logger.info("[vision.whisper] Chargement du modèle : %s", model_name)
    model = whisper.load_model(model_name)
    _WHISPER_MODELS_CACHE[model_name] = model
    logger.info("[vision.whisper] Modèle %s chargé", model_name)
    return model


def _extract_audio_from_video(video_path: str) -> str:
    """Extrait la piste audio d'une vidéo en WAV 16kHz mono."""
    audio_path = os.path.join(
        tempfile.gettempdir(),
        f"whisper_audio_{uuid.uuid4().hex[:8]}.wav",
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        audio_path,
    ]

    logger.info("[vision.whisper] Extraction audio : %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr[-500:]}")

    if not os.path.exists(audio_path):
        raise RuntimeError(f"Audio file not created: {audio_path}")

    return audio_path


def _seconds_to_srt_time(seconds: float) -> str:
    """Convertit un nombre de secondes en format SRT (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# ==============================================================================
# GÉNÉRATION DE SOUS-TITRES (.srt)
# ==============================================================================
def _resolve_video_path(video_path: str) -> str:
    """
    Résout un chemin de vidéo :
      - Si absolu et existe → retourné tel quel
      - Sinon cherche dans GENERATED_DIR, uploads/, workspace
      - Supporte le mot-clé "LAST"
    """
    if not video_path:
        return ""

    # Mot-clé LAST → chercher la vidéo la plus récente
    if video_path in ("LAST", "last"):
        import glob
        try:
            mp4_files = glob.glob(os.path.join(GENERATED_DIR, "*.mp4"))
            mp4_files = [
                f for f in mp4_files
                if not os.path.basename(f).startswith("_temp_")
                and not os.path.basename(f).startswith("last_frame_")
                and not os.path.basename(f).startswith("first_frame_")
            ]
            if mp4_files:
                mp4_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                return mp4_files[0]
        except Exception:
            pass
        return ""

    # Absolu + existe
    if os.path.isabs(video_path) and os.path.exists(video_path):
        return video_path

    # Chercher dans plusieurs dossiers
    from core.paths import FILES_DIR
    candidates = [
        os.path.join(GENERATED_DIR, video_path),
        os.path.join(GENERATED_DIR, os.path.basename(video_path)),
        os.path.join(WORKSPACE_DIR, "uploads", video_path),
        os.path.join(WORKSPACE_DIR, "uploads", os.path.basename(video_path)),
        os.path.join(WORKSPACE_DIR, video_path),
        os.path.join(WORKSPACE_DIR, os.path.basename(video_path)),
        os.path.join(FILES_DIR, video_path),
        os.path.join(FILES_DIR, os.path.basename(video_path)),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return os.path.abspath(cand)

    return ""


def generate_subtitles_from_video(
    video_path: str,
    language: Optional[str] = None,
    model_name: str = "base",
    output_srt_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Transcrit une vidéo en sous-titres .srt via Whisper.
    """
    # ★ v32.1 : résolution automatique du chemin
    resolved_path = _resolve_video_path(video_path)
    if not resolved_path:
        return {
            "status": "error",
            "message": f"Vidéo introuvable : {video_path} (cherché dans generated/, uploads/, workspace/)"
        }

    video_path = resolved_path
    logger.info("[vision.whisper] Chemin résolu : %s", video_path)

    if not output_srt_path:
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        srt_filename = f"{base_name}_subtitles_{uuid.uuid4().hex[:6]}.srt"
        output_srt_path = os.path.join(GENERATED_DIR, srt_filename)
    else:
        srt_filename = os.path.basename(output_srt_path)

    audio_path = None
    try:
        logger.info("[vision.whisper] Étape 1 : extraction audio")
        audio_path = _extract_audio_from_video(video_path)

        logger.info("[vision.whisper] Étape 2 : chargement Whisper (%s)", model_name)
        model = _load_whisper_model(model_name)

        logger.info("[vision.whisper] Étape 3 : transcription...")
        transcribe_options = {"task": "transcribe", "fp16": False}
        if language:
            transcribe_options["language"] = language

        result = model.transcribe(audio_path, **transcribe_options)

        detected_lang = result.get("language", "unknown")
        segments = result.get("segments", [])
        full_text = result.get("text", "").strip()

        logger.info(
            "[vision.whisper] Transcription OK : %d segments, langue=%s",
            len(segments), detected_lang,
        )

        with open(output_srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                start = _seconds_to_srt_time(seg["start"])
                end = _seconds_to_srt_time(seg["end"])
                text = seg["text"].strip()
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

        logger.info("[vision.whisper] Fichier .srt écrit : %s", output_srt_path)

        return {
            "status": "success",
            "srt_path": output_srt_path,
            "srt_filename": srt_filename,
            "language": detected_lang,
            "segments_count": len(segments),
            "text": full_text[:500] + ("..." if len(full_text) > 500 else ""),
            "video_source": os.path.basename(video_path),
        }

    except Exception as e:
        logger.exception("[vision.whisper] Erreur transcription")
        return {"status": "error", "message": f"Erreur Whisper : {str(e)}"}

    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass


# ==============================================================================
# INCRUSTATION DES SOUS-TITRES DANS LA VIDÉO
# ==============================================================================
def burn_subtitles_into_video(
    video_path: str,
    srt_path: str,
    output_path: Optional[str] = None,
    font_size: int = 22,
) -> Dict[str, Any]:
    """
    Incruste les sous-titres .srt dans la vidéo (hard subs).
    """
    # ★ v32.1 : résolution automatique du chemin vidéo
    resolved_path = _resolve_video_path(video_path)
    if not resolved_path:
        return {
            "status": "error",
            "message": f"Vidéo introuvable : {video_path}"
        }
    video_path = resolved_path

    # ★ v32.1 : résolution du chemin .srt
    if not os.path.isabs(srt_path):
        srt_candidates = [
            os.path.join(GENERATED_DIR, srt_path),
            os.path.join(GENERATED_DIR, os.path.basename(srt_path)),
            os.path.join(WORKSPACE_DIR, srt_path),
            os.path.join(WORKSPACE_DIR, os.path.basename(srt_path)),
        ]
        for cand in srt_candidates:
            if os.path.exists(cand):
                srt_path = os.path.abspath(cand)
                break

        if not os.path.exists(srt_path):
            return {"status": "error", "message": f"Sous-titres introuvables : {srt_path}"}

    if not output_path:
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_filename = f"{base_name}_subtitled_{uuid.uuid4().hex[:6]}.mp4"
        output_path = os.path.join(GENERATED_DIR, output_filename)
    else:
        output_filename = os.path.basename(output_path)

    srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")

    style = (
        f"FontSize={font_size},"
        f"PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,"
        f"BorderStyle=1,Outline=2,Shadow=1"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles='{srt_escaped}':force_style='{style}'",
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info("[vision.whisper] Incrustation sous-titres : %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            return {
                "status": "error",
                "message": f"FFmpeg subtitle burn failed: {result.stderr[-500:]}",
            }
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Timeout FFmpeg (30 min)"}

    if not os.path.exists(output_path):
        return {"status": "error", "message": "Fichier de sortie non créé"}

    return {
        "status": "success",
        "filepath": output_path,
        "filename": output_filename,
        "size_bytes": os.path.getsize(output_path),
    }