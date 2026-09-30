# ==============================================================================
# BEK-v16 — Vision / Face Swap
# ------------------------------------------------------------------------------
# Face swap pour préservation faciale dans les vidéos générées par Agnes.
# Utilise Replicate API (modèles face-swap) pour remplacer les visages
# génériques par les visages des images de référence.
#
# v1.0 (2026-09-29) : Création initiale
#   - apply_face_swap_to_video() : remplace les visages dans une vidéo
#   - apply_face_swap_to_image() : remplace les visages dans une image
#   - Batch processing (frame par frame)
# ==============================================================================
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from core.paths import GENERATED_DIR, WORKSPACE_DIR

logger = logging.getLogger("bek.vision.face_swap")


# ==============================================================================
# CONFIGURATION
# ==============================================================================

REPLICATE_API_BASE = "https://api.replicate.com/v1"

# Modèle Replicate recommandé pour face swap (mis à jour 2026)
# Utilise "face-swap" ou "ghost" (ghost est plus rapide)
REPLICATE_MODEL = "lucataco/faceswap:9a4298548422074c3f57258c5d544497314ae4112df80d116f0d7616fe8c1a90"

# Alternative : Ghost (plus rapide, mais qualité légèrement moindre)
REPLICATE_MODEL_FAST = "jagilley/face-swap:cff87316e31787df12002c9e20a78a017a36cb31f80ea015d4727bd076e4b9a0"

# Polling
REPLICATE_POLL_INTERVAL = 3  # secondes
REPLICATE_MAX_WAIT = 600  # 10 minutes


# ==============================================================================
# HELPERS
# ==============================================================================

def _get_replicate_token() -> str:
    """Récupère le token Replicate via le provider_manager."""
    from provider_manager import provider_manager
    token = provider_manager.get_api_key("REPLICATE_API_TOKEN")
    if not token:
        token = os.getenv("REPLICATE_API_TOKEN", "")
    return token


def _resolve_image_path(image_path: str) -> str:
    """Résout le chemin d'une image."""
    if not image_path:
        return ""

    # Absolu
    if os.path.isabs(image_path) and os.path.exists(image_path):
        return image_path

    # Chercher dans plusieurs dossiers
    candidates = [
        os.path.join(WORKSPACE_DIR, image_path),
        os.path.join(WORKSPACE_DIR, "uploads", image_path),
        os.path.join(GENERATED_DIR, image_path),
        os.path.join(WORKSPACE_DIR, "uploads", os.path.basename(image_path)),
        os.path.join(GENERATED_DIR, os.path.basename(image_path)),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return os.path.abspath(cand)

    return ""


def _resolve_video_path(video_path: str) -> str:
    """Résout le chemin d'une vidéo."""
    if not video_path:
        return ""

    if os.path.isabs(video_path) and os.path.exists(video_path):
        return video_path

    candidates = [
        os.path.join(WORKSPACE_DIR, video_path),
        os.path.join(WORKSPACE_DIR, "uploads", video_path),
        os.path.join(GENERATED_DIR, video_path),
        os.path.join(GENERATED_DIR, os.path.basename(video_path)),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return os.path.abspath(cand)

    return ""


def _file_to_data_uri(file_path: str) -> str:
    """Convertit un fichier en data URI base64."""
    import base64
    import mimetypes

    with open(file_path, "rb") as f:
        content = f.read()

    mime = mimetypes.guess_type(file_path)[0] or "image/jpeg"
    b64 = base64.b64encode(content).decode("utf-8")
    return f"data:{mime};base64,{b64}"


# ==============================================================================
# REPLICATE API
# ==============================================================================

def _replicate_run(
    model_version: str,
    inputs: Dict[str, Any],
    poll_interval: int = REPLICATE_POLL_INTERVAL,
    max_wait: int = REPLICATE_MAX_WAIT,
) -> Optional[str]:
    """
    Lance une prédiction Replicate et attend le résultat.

    Returns:
        URL du fichier de sortie (str) ou None en cas d'échec.
    """
    token = _get_replicate_token()
    if not token:
        logger.warning("[face_swap] REPLICATE_API_TOKEN non configuré")
        return None

    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    }

    # 1. Créer la prédiction
    payload = {
        "version": model_version.split(":")[-1] if ":" in model_version else model_version,
        "input": inputs,
    }
    # Si le modèle est au format "owner/name:version"
    if ":" in model_version:
        owner_name, version = model_version.split(":")
        payload = {
            "version": version,
            "input": inputs,
        }

    logger.info("[face_swap] Création prédiction Replicate...")

    try:
        res = requests.post(
            f"{REPLICATE_API_BASE}/predictions",
            headers=headers,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as e:
        logger.error("[face_swap] Erreur réseau Replicate : %s", e)
        return None

    if res.status_code not in (200, 201):
        logger.error(
            "[face_swap] Replicate HTTP %s : %s",
            res.status_code, res.text[:300],
        )
        return None

    pred = res.json()
    pred_id = pred.get("id")
    if not pred_id:
        logger.error("[face_swap] Pas de pred_id : %s", pred)
        return None

    logger.info("[face_swap] Prédiction créée : %s", pred_id)

    # 2. Poller jusqu'à completion
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            logger.error("[face_swap] Timeout après %ds", max_wait)
            return None

        try:
            res = requests.get(
                f"{REPLICATE_API_BASE}/predictions/{pred_id}",
                headers=headers,
                timeout=30,
            )
        except requests.RequestException as e:
            logger.warning("[face_swap] Erreur poll : %s", e)
            time.sleep(poll_interval)
            continue

        if res.status_code != 200:
            logger.warning("[face_swap] Poll HTTP %s", res.status_code)
            time.sleep(poll_interval)
            continue

        pred = res.json()
        status = pred.get("status", "")

        if status == "succeeded":
            output = pred.get("output")
            if isinstance(output, list):
                output = output[0] if output else None
            if output:
                logger.info("[face_swap] ✅ Prédiction réussie : %s", output[:100])
                return output
            logger.error("[face_swap] Output vide")
            return None

        if status in ("failed", "canceled"):
            error = pred.get("error", "unknown")
            logger.error("[face_swap] Prédiction échouée : %s", error)
            return None

        logger.debug("[face_swap] En cours (%ds, status=%s)", int(elapsed), status)
        time.sleep(poll_interval)


def _download_url(url: str, output_path: str) -> bool:
    """Télécharge un fichier depuis une URL."""
    try:
        res = requests.get(url, timeout=120, stream=True)
        res.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        logger.error("[face_swap] Erreur téléchargement : %s", e)
        return False


# ==============================================================================
# FACE SWAP — IMAGE
# ==============================================================================

def apply_face_swap_to_image(
    source_image: str,
    target_image: str,
    output_filename: str = "",
    fast_mode: bool = False,
) -> Dict[str, Any]:
    """
    Applique un face swap : remplace le visage de `target_image` par celui de
    `source_image`.

    Args:
        source_image : image contenant le visage à COPIER (ex: Mohamed original)
        target_image : image où appliquer le visage (ex: génération Agnes)
        output_filename : nom du fichier de sortie
        fast_mode : utiliser le modèle rapide (moins de qualité)

    Returns:
        {"status": "success", "filepath": ..., "filename": ...}
        ou {"status": "error", "message": ...}
    """
    src = _resolve_image_path(source_image)
    tgt = _resolve_image_path(target_image)

    if not src:
        return {"status": "error", "message": f"Image source introuvable : {source_image}"}
    if not tgt:
        return {"status": "error", "message": f"Image cible introuvable : {target_image}"}

    if not output_filename:
        output_filename = f"face_swap_{uuid.uuid4().hex[:8]}.png"
    out_path = os.path.abspath(os.path.join(GENERATED_DIR, output_filename))

    logger.info(
        "[face_swap] Image : source=%s → target=%s",
        os.path.basename(src), os.path.basename(tgt),
    )

    # Préparer les data URIs
    try:
        src_uri = _file_to_data_uri(src)
        tgt_uri = _file_to_data_uri(tgt)
    except Exception as e:
        return {"status": "error", "message": f"Erreur encodage : {e}"}

    # Replicate input : selon le modèle, les noms changent
    # Pour lucataco/faceswap : "swap_image" (source) et "target_image" (target)
    inputs = {
        "swap_image": src_uri,   # Visage à copier
        "target_image": tgt_uri, # Où appliquer
    }

    model = REPLICATE_MODEL_FAST if fast_mode else REPLICATE_MODEL
    output_url = _replicate_run(model, inputs)

    if not output_url:
        return {"status": "error", "message": "Échec Replicate face swap"}

    # Télécharger
    if not _download_url(output_url, out_path):
        return {"status": "error", "message": "Échec téléchargement résultat"}

    logger.info("[face_swap] ✅ Image swappée : %s", out_path)

    return {
        "status": "success",
        "filepath": out_path,
        "filename": os.path.basename(out_path),
        "source_face": os.path.basename(src),
        "target_image": os.path.basename(tgt),
    }


# ==============================================================================
# FACE SWAP — VIDÉO
# ==============================================================================

def _extract_video_frames(
    video_path: str,
    output_dir: str,
    fps: int = 12,
    max_frames: int = 200,
) -> List[str]:
    """
    Extrait les frames d'une vidéo en PNG.

    Args:
        video_path : chemin de la vidéo
        output_dir : dossier de sortie
        fps : images par seconde (12 = suffisant pour vidéo courte)
        max_frames : nombre maximum de frames à extraire

    Returns:
        Liste des chemins de frames extraites.
    """
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-frames:v", str(max_frames),
        os.path.join(frames_dir, "frame_%05d.png"),
    ]

    logger.info("[face_swap] Extraction frames : fps=%d, max=%d", fps, max_frames)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg extraction échouée : {result.stderr[-500:]}")

    frames = sorted([
        os.path.join(frames_dir, f)
        for f in os.listdir(frames_dir)
        if f.startswith("frame_") and f.endswith(".png")
    ])

    logger.info("[face_swap] %d frames extraites", len(frames))
    return frames


def _reassemble_video(
    frames_dir: str,
    original_video: str,
    output_path: str,
    fps: int = 24,
) -> bool:
    """
    Réassemble une vidéo à partir de frames, en récupérant l'audio original.
    """
    frames_pattern = os.path.join(frames_dir, "frames", "frame_%05d.png")

    # Encoder la vidéo sans audio
    tmp_video = output_path + ".noaudio.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", frames_pattern,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        tmp_video,
    ]

    logger.info("[face_swap] Réassemblage vidéo (sans audio)...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)

    if result.returncode != 0:
        logger.error("[face_swap] Échec réassemblage : %s", result.stderr[-500:])
        return False

    # Ajouter l'audio original
    cmd_audio = [
        "ffmpeg", "-y",
        "-i", tmp_video,
        "-i", original_video,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-shortest",
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info("[face_swap] Ajout audio original...")
    result = subprocess.run(cmd_audio, capture_output=True, text=True, timeout=600)

    # Nettoyer le temporaire
    try:
        os.remove(tmp_video)
    except Exception:
        pass

    if result.returncode != 0:
        logger.warning(
            "[face_swap] Ajout audio échoué, copie vidéo sans audio : %s",
            result.stderr[-300:],
        )
        # Fallback : copier la vidéo sans audio
        shutil.copy(tmp_video, output_path)

    return os.path.exists(output_path)


def apply_face_swap_to_video(
    source_image: str,
    target_video: str,
    output_filename: str = "",
    fps: int = 12,
    max_frames: int = 200,
    fast_mode: bool = False,
) -> Dict[str, Any]:
    """
    Applique un face swap sur une vidéo : remplace le visage principal
    de la vidéo par celui de `source_image`.

    Args:
        source_image : image contenant le visage à COPIER (ex: Mohamed original)
        target_video : vidéo où appliquer (ex: génération Agnes)
        output_filename : nom du fichier de sortie
        fps : images par seconde à extraire (12 = bon compromis)
        max_frames : nombre max de frames (limite le coût Replicate)
        fast_mode : utiliser le modèle rapide

    Returns:
        {"status": "success", "filepath": ..., "filename": ..., "frames_processed": N}
    """
    src = _resolve_image_path(source_image)
    tgt = _resolve_video_path(target_video)

    if not src:
        return {"status": "error", "message": f"Image source introuvable : {source_image}"}
    if not tgt:
        return {"status": "error", "message": f"Vidéo cible introuvable : {target_video}"}

    if not _get_replicate_token():
        return {
            "status": "error",
            "message": (
                "REPLICATE_API_TOKEN non configuré. "
                "Ajoute-le dans env.txt : REPLICATE_API_TOKEN=r8_..."
            ),
        }

    if not output_filename:
        base = os.path.splitext(os.path.basename(tgt))[0]
        output_filename = f"{base}_faceswap_{uuid.uuid4().hex[:6]}.mp4"
    out_path = os.path.abspath(os.path.join(GENERATED_DIR, output_filename))

    logger.info(
        "[face_swap] Vidéo : source=%s → target=%s (fps=%d, max=%d)",
        os.path.basename(src), os.path.basename(tgt), fps, max_frames,
    )

    tmpdir = tempfile.mkdtemp(prefix="bek_faceswap_")

    try:
        # 1. Extraire les frames
        frames = _extract_video_frames(tgt, tmpdir, fps=fps, max_frames=max_frames)
        if not frames:
            return {"status": "error", "message": "Aucune frame extraite"}

        # 2. Préparer le data URI de la source
        try:
            src_uri = _file_to_data_uri(src)
        except Exception as e:
            return {"status": "error", "message": f"Erreur encodage source : {e}"}

        # 3. Face swap sur chaque frame
        swaped_count = 0
        failed_count = 0

        model = REPLICATE_MODEL_FAST if fast_mode else REPLICATE_MODEL

        for i, frame_path in enumerate(frames):
            logger.info(
                "[face_swap] Frame %d/%d : %s",
                i + 1, len(frames), os.path.basename(frame_path),
            )

            try:
                tgt_uri = _file_to_data_uri(frame_path)
            except Exception as e:
                logger.warning("[face_swap] Frame %d encodage échoué : %s", i + 1, e)
                failed_count += 1
                continue

            inputs = {
                "swap_image": src_uri,
                "target_image": tgt_uri,
            }

            output_url = _replicate_run(model, inputs)
            if not output_url:
                logger.warning("[face_swap] Frame %d face swap échoué", i + 1)
                failed_count += 1
                continue

            # Remplacer la frame par la version swappée
            if _download_url(output_url, frame_path):
                swaped_count += 1
            else:
                failed_count += 1

        logger.info(
            "[face_swap] Face swap terminé : %d réussies, %d échouées",
            swaped_count, failed_count,
        )

        if swaped_count == 0:
            return {
                "status": "error",
                "message": "Aucune frame n'a pu être swappée",
            }

        # 4. Réassembler la vidéo
        if not _reassemble_video(tmpdir, tgt, out_path, fps=fps):
            return {"status": "error", "message": "Échec réassemblage vidéo"}

        logger.info("[face_swap] ✅ Vidéo swappée : %s", out_path)

        return {
            "status": "success",
            "filepath": out_path,
            "filename": os.path.basename(out_path),
            "frames_processed": swaped_count,
            "frames_failed": failed_count,
            "total_frames": len(frames),
            "source_face": os.path.basename(src),
            "target_video": os.path.basename(tgt),
        }

    except Exception as e:
        logger.exception("[face_swap] Erreur vidéo")
        return {"status": "error", "message": str(e)}

    finally:
        # Nettoyer le dossier temporaire
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


# ==============================================================================
# HELPER PUBLIC
# ==============================================================================

def is_replicate_available() -> bool:
    """Vérifie si Replicate est configuré."""
    return bool(_get_replicate_token())


# ==============================================================================
# EXEMPLE D'USAGE
# ==============================================================================
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if not is_replicate_available():
        print("REPLICATE_API_TOKEN non configuré. Ajoute-le dans env.txt")
        sys.exit(1)

    if len(sys.argv) < 3:
        print("Usage:")
        print("  python face_swap.py image <source> <target> [output]")
        print("  python face_swap.py video <source> <target> [output] [fps]")
        sys.exit(0)

    mode = sys.argv[1]

    if mode == "image" and len(sys.argv) >= 4:
        src = sys.argv[2]
        tgt = sys.argv[3]
        out = sys.argv[4] if len(sys.argv) > 4 else ""
        result = apply_face_swap_to_image(src, tgt, out)
        print(result)

    elif mode == "video" and len(sys.argv) >= 4:
        src = sys.argv[2]
        tgt = sys.argv[3]
        out = sys.argv[4] if len(sys.argv) > 4 else ""
        fps = int(sys.argv[5]) if len(sys.argv) > 5 else 12
        result = apply_face_swap_to_video(src, tgt, out, fps=fps)
        print(result)

    else:
        print("Arguments invalides")