# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Vision / Face Swap
# v1.2 (2026-10-24) : FIX Replicate API (Upload File au lieu de Base64)
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

REPLICATE_API_BASE = "https://api.replicate.com/v1"
REPLICATE_MODEL = "lucataco/faceswap:9a4298548422074c3f57258c5d544497314ae4112df80d116f0d7616fe8c1a90"
REPLICATE_MODEL_FAST = "jagilley/face-swap:cff87316e31787df12002c9e20a78a017a36cb31f80ea015d4727bd076e4b9a0"
REPLICATE_POLL_INTERVAL = 3
REPLICATE_MAX_WAIT = 600


def _get_replicate_token() -> str:
    from provider_manager import provider_manager
    token = provider_manager.get_api_key("REPLICATE_API_TOKEN")
    if not token:
        token = os.getenv("REPLICATE_API_TOKEN", "")
    return token


def _resolve_image_path(image_path: str) -> str:
    if not image_path: return ""
    if os.path.isabs(image_path) and os.path.exists(image_path): return image_path
    candidates = [
        os.path.join(WORKSPACE_DIR, image_path), os.path.join(WORKSPACE_DIR, "uploads", image_path),
        os.path.join(GENERATED_DIR, image_path), os.path.join(WORKSPACE_DIR, "uploads", os.path.basename(image_path)),
        os.path.join(GENERATED_DIR, os.path.basename(image_path)),
    ]
    for cand in candidates:
        if os.path.exists(cand): return os.path.abspath(cand)
    return ""


def _resolve_video_path(video_path: str) -> str:
    if not video_path: return ""
    if os.path.isabs(video_path) and os.path.exists(video_path): return video_path
    candidates = [
        os.path.join(WORKSPACE_DIR, video_path), os.path.join(WORKSPACE_DIR, "uploads", video_path),
        os.path.join(GENERATED_DIR, video_path), os.path.join(GENERATED_DIR, os.path.basename(video_path)),
    ]
    for cand in candidates:
        if os.path.exists(cand): return os.path.abspath(cand)
    return ""


# ★ FIX v1.2 : Upload vers Replicate au lieu de Base64
def _upload_to_replicate(file_path: str) -> Optional[str]:
    """Upload un fichier vers Replicate et retourne son URL publique."""
    token = _get_replicate_token()
    if not token: return None
    headers = {"Authorization": f"Token {token}"}
    try:
        with open(file_path, "rb") as f:
            res = requests.post("https://api.replicate.com/v1/files", headers=headers, files={"content": f}, timeout=120)
        if res.status_code in (200, 201):
            return res.json().get("urls", {}).get("get")
        logger.error("[face_swap] Upload Replicate HTTP %s : %s", res.status_code, res.text[:300])
        return None
    except Exception as e:
        logger.error("[face_swap] Erreur upload Replicate : %s", e)
        return None


def _replicate_run(model_version: str, inputs: Dict[str, Any], poll_interval: int = REPLICATE_POLL_INTERVAL, max_wait: int = REPLICATE_MAX_WAIT) -> Optional[str]:
    token = _get_replicate_token()
    if not token: return None
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}

    if ":" in model_version:
        _, version = model_version.split(":", 1)
        payload = {"version": version, "input": inputs}
    else:
        payload = {"version": model_version, "input": inputs}

    try:
        res = requests.post(f"{REPLICATE_API_BASE}/predictions", headers=headers, json=payload, timeout=30)
    except requests.RequestException as e:
        logger.error("[face_swap] Erreur réseau Replicate : %s", e); return None

    if res.status_code not in (200, 201):
        logger.error("[face_swap] Replicate HTTP %s : %s", res.status_code, res.text[:300]); return None

    pred_id = res.json().get("id")
    if not pred_id: return None

    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > max_wait: return None
        try:
            res = requests.get(f"{REPLICATE_API_BASE}/predictions/{pred_id}", headers=headers, timeout=30)
        except requests.RequestException:
            time.sleep(poll_interval); continue
        if res.status_code != 200:
            time.sleep(poll_interval); continue

        pred = res.json()
        status = pred.get("status", "")
        if status == "succeeded":
            output = pred.get("output")
            if isinstance(output, list): output = output[0] if output else None
            return output
        if status in ("failed", "canceled"): return None
        time.sleep(poll_interval)


def _download_url(url: str, output_path: str) -> bool:
    try:
        res = requests.get(url, timeout=120, stream=True)
        res.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192): f.write(chunk)
        return True
    except Exception as e:
        logger.error("[face_swap] Erreur téléchargement : %s", e); return False


def apply_face_swap_to_image(source_image: str, target_image: str, output_filename: str = "", fast_mode: bool = False) -> Dict[str, Any]:
    src = _resolve_image_path(source_image)
    tgt = _resolve_image_path(target_image)
    if not src: return {"status": "error", "message": f"Image source introuvable : {source_image}"}
    if not tgt: return {"status": "error", "message": f"Image cible introuvable : {target_image}"}

    if not output_filename: output_filename = f"face_swap_{uuid.uuid4().hex[:8]}.png"
    out_path = os.path.abspath(os.path.join(GENERATED_DIR, output_filename))

    # ★ FIX v1.2 : Upload des fichiers
    src_url = _upload_to_replicate(src)
    tgt_url = _upload_to_replicate(tgt)
    if not src_url or not tgt_url: return {"status": "error", "message": "Erreur upload des images vers Replicate."}

    inputs = {"swap_image": src_url, "target_image": tgt_url}
    model = REPLICATE_MODEL_FAST if fast_mode else REPLICATE_MODEL
    output_url = _replicate_run(model, inputs)

    if not output_url: return {"status": "error", "message": "Échec Replicate face swap"}
    if not _download_url(output_url, out_path): return {"status": "error", "message": "Échec téléchargement"}

    return {"status": "success", "filepath": out_path, "filename": os.path.basename(out_path), "source_face": os.path.basename(src), "target_image": os.path.basename(tgt)}


def _extract_video_frames(video_path: str, output_dir: str, fps: int = 12, max_frames: int = 200) -> List[str]:
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", f"fps={fps}", "-frames:v", str(max_frames), os.path.join(frames_dir, "frame_%05d.png")]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0: raise RuntimeError(f"FFmpeg extraction échouée : {result.stderr[-500:]}")
    return sorted([os.path.join(frames_dir, f) for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".png")])


def _reassemble_video(frames_dir: str, original_video: str, output_path: str, fps: int = 24) -> bool:
    frames_pattern = os.path.join(frames_dir, "frames", "frame_%05d.png")
    tmp_video = output_path + ".noaudio.mp4"
    cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", frames_pattern, "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", tmp_video]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if result.returncode != 0: return False

    cmd_audio = ["ffmpeg", "-y", "-i", tmp_video, "-i", original_video, "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0?", "-shortest", "-movflags", "+faststart", output_path]
    result = subprocess.run(cmd_audio, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        if os.path.exists(tmp_video):
            try: shutil.copy(tmp_video, output_path)
            except: return False
        else: return False
    try:
        if os.path.exists(tmp_video): os.remove(tmp_video)
    except: pass
    return os.path.exists(output_path)


def apply_face_swap_to_video(source_image: str, target_video: str, output_filename: str = "", fps: int = 12, max_frames: int = 200, fast_mode: bool = False) -> Dict[str, Any]:
    src = _resolve_image_path(source_image)
    tgt = _resolve_video_path(target_video)
    if not src: return {"status": "error", "message": f"Image source introuvable : {source_image}"}
    if not tgt: return {"status": "error", "message": f"Vidéo cible introuvable : {target_video}"}
    if not _get_replicate_token(): return {"status": "error", "message": "REPLICATE_API_TOKEN non configuré."}

    if not output_filename:
        base = os.path.splitext(os.path.basename(tgt))[0]
        output_filename = f"{base}_faceswap_{uuid.uuid4().hex[:6]}.mp4"
    out_path = os.path.abspath(os.path.join(GENERATED_DIR, output_filename))
    tmpdir = tempfile.mkdtemp(prefix="bek_faceswap_")

    try:
        frames = _extract_video_frames(tgt, tmpdir, fps=fps, max_frames=max_frames)
        if not frames: return {"status": "error", "message": "Aucune frame extraite"}

        src_url = _upload_to_replicate(src)
        if not src_url: return {"status": "error", "message": "Erreur upload image source."}

        swaped_count, failed_count = 0, 0
        model = REPLICATE_MODEL_FAST if fast_mode else REPLICATE_MODEL

        for i, frame_path in enumerate(frames):
            # ★ FIX v1.2 : Upload frame par frame
            tgt_url = _upload_to_replicate(frame_path)
            if not tgt_url:
                failed_count += 1; continue

            inputs = {"swap_image": src_url, "target_image": tgt_url}
            output_url = _replicate_run(model, inputs)
            if not output_url or not _download_url(output_url, frame_path):
                failed_count += 1; continue
            swaped_count += 1

        if swaped_count == 0: return {"status": "error", "message": "Aucune frame n'a pu être swappée"}

        if not _reassemble_video(tmpdir, tgt, out_path, fps=fps): return {"status": "error", "message": "Échec réassemblage"}

        return {"status": "success", "filepath": out_path, "filename": os.path.basename(out_path), "frames_processed": swaped_count, "frames_failed": failed_count, "total_frames": len(frames)}

    except Exception as e:
        logger.exception("[face_swap] Erreur vidéo"); return {"status": "error", "message": str(e)}
    finally:
        try: shutil.rmtree(tmpdir, ignore_errors=True)
        except: pass


def is_replicate_available() -> bool: return bool(_get_replicate_token())