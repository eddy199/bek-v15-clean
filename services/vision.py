# ==============================================================================
# BEK-v16 — Vision & Génération Optimisée (services/vision.py)
# ==============================================================================
from __future__ import annotations

import base64
import os
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional, Union

import requests
from werkzeug.utils import secure_filename

from core.paths import FILES_DIR, GENERATED_DIR, WORKSPACE_DIR
from provider_manager import provider_manager
from services.prompt_optimizer import optimize_prompt_for_media


def get_api_key(key_name: str) -> str:
    return provider_manager.get_api_key(key_name)


def _get_latest_media_file(directory: str, extensions: tuple = (".png", ".jpg", ".jpeg", ".webp", ".mp4")) -> Optional[str]:
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


def _resolve_existing_media_paths(paths_input: Union[str, List[str], None], extensions: tuple) -> List[str]:
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
        latest = _get_latest_media_file(GENERATED_DIR, extensions) or _get_latest_media_file(FILES_DIR, extensions)
        if latest:
            resolved.append(latest)
    return resolved


def analyze_image_with_vision(image_path: str, prompt: str = "", provider: str = "gemini", model: str = "") -> str:
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
        mime_type = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")
        
        prompt_text = prompt or "Analyze this image with extreme detail: characters identity, facial expressions, salt-and-pepper beard, striking blue eyes, clothing, 3D cardboard craft textures, background, and text."

        api_key = get_api_key("GEMINI_API_KEY")
        if api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt_text},
                        {"inline_data": {"mime_type": mime_type, "data": encoded_image}}
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


def generate_image_with_provider(
    prompt: str,
    provider: str = "gemini",
    model: str = "gemini-2.5-flash-image",
    output_filename: str = ""
) -> Dict[str, Any]:
    if not output_filename:
        output_filename = f"gen_image_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.abspath(os.path.join(GENERATED_DIR, secure_filename(output_filename)))

    enhanced_prompt = optimize_prompt_for_media(prompt, media_type="image", style_preset="cardboard_3d")

    try:
        api_key = get_api_key("GEMINI_API_KEY")
        if api_key:
            url_gen = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={api_key}"
            payload_gen = {
                "contents": [{"parts": [{"text": enhanced_prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
            }
            res = requests.post(url_gen, json=payload_gen, timeout=60)
            if res.status_code == 200:
                data = res.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inline_data" in part and "data" in part["inline_data"]:
                        img_bytes = base64.b64decode(part["inline_data"]["data"])
                        with open(save_path, "wb") as f:
                            f.write(img_bytes)
                        return {"status": "success", "filepath": save_path, "filename": output_filename}

        fallback_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(enhanced_prompt)}?nologo=true"
        fallback_res = requests.get(fallback_url, timeout=30)
        if fallback_res.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(fallback_res.content)
            return {"status": "success", "filepath": save_path, "filename": output_filename, "message": "Généré via Fallback Optimizer"}

        return {"status": "error", "message": "Échec de génération d'image."}
    except Exception as e:
        return {"status": "error", "message": f"Erreur technique : {str(e)}"}


def merge_and_edit_images(
    image_paths: Any = None,
    user_prompt: str = "",
    prompt: str = "",
    provider: str = "gemini",
    model: str = "gemini-2.5-flash-image"
) -> Dict[str, Any]:
    try:
        active_prompt = user_prompt or prompt or "Modifier l'image."
        valid_paths = _resolve_existing_media_paths(image_paths, (".png", ".jpg", ".jpeg", ".webp"))

        analysis_context = ""
        if valid_paths:
            analysis_context = analyze_image_with_vision(
                valid_paths[0],
                "Décris précisément les traits du visage, la barbe poivre et sel, les yeux bleus perçants, le style cartonné 3D et les personnages présents."
            )

        fusion_prompt = (
            f"Reference visual analysis: {analysis_context}\n\n"
            f"Required modification: {active_prompt}. "
            f"Maintain strict identity continuity, facial features (salt-and-pepper beard, striking blue eyes for Mohamed), 3D cardboard cutout craft material, and vibrant studio lighting."
        )
        return generate_image_with_provider(fusion_prompt, provider=provider, model=model)
    except Exception as e:
        return {"status": "error", "message": f"Erreur fusion visuelle : {str(e)}"}


def generate_video_with_provider(
    prompt: str,
    provider: str = "gemini",
    model: str = "veo-3.1-lite-gene-prev",
    output_filename: str = ""
) -> Dict[str, Any]:
    if not output_filename:
        output_filename = f"gen_video_{uuid.uuid4().hex[:8]}.mp4"
    save_path = os.path.abspath(os.path.join(GENERATED_DIR, secure_filename(output_filename)))

    enhanced_video_prompt = optimize_prompt_for_media(prompt, media_type="video", style_preset="cinematic_video")

    try:
        api_key = get_api_key("GEMINI_API_KEY")
        if not api_key:
            return {"status": "error", "message": "GEMINI_API_KEY non configurée pour la vidéo."}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={api_key}"
        payload = {
            "instances": [{"prompt": enhanced_video_prompt}],
            "parameters": {"aspectRatio": "16:9", "durationSeconds": 5}
        }

        res = requests.post(url, json=payload, timeout=120)
        if res.status_code == 200:
            data = res.json()
            b64_data = data["predictions"][0]["bytesBase64Encoded"]
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(b64_data))
            return {"status": "success", "filepath": save_path, "filename": output_filename}

        return {"status": "error", "message": f"Échec API Veo : {res.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Erreur vidéo : {str(e)}"}


def merge_and_edit_videos(
    video_paths: Any = None,
    user_prompt: str = "",
    prompt: str = "",
    provider: str = "gemini",
    model: str = "veo-3.1-lite-gene-prev"
) -> Dict[str, Any]:
    try:
        active_prompt = user_prompt or prompt or "Améliorer la séquence vidéo."
        valid_paths = _resolve_existing_media_paths(video_paths, (".mp4", ".webm", ".mov"))
        context = f"Based on video file {os.path.basename(valid_paths[0])}" if valid_paths else ""
        
        return generate_video_with_provider(f"{context}. Modification directive: {active_prompt}", provider=provider, model=model)
    except Exception as e:
        return {"status": "error", "message": f"Erreur édition vidéo : {str(e)}"}