# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v19 — Image Generation (v6.5 — Fix Modèles + Fallback Placeholder)
# ------------------------------------------------------------------------------
# ★ v6.5 (2026-11-11) — FIX : Modèle HuggingFace déprécié + Gemini stable
#   - HuggingFace : "hf-flux-schnell" → "black-forest-labs/FLUX.1-schnell"
#   - Gemini : vérification du modèle "gemini-2.5-flash-image"
#   - Fallback placeholder : toujours présent si tout échoue
# ==============================================================================
from __future__ import annotations

import base64
import logging
import os
import uuid
from typing import Any, Dict

import requests
from werkzeug.utils import secure_filename

from core.paths import FILES_DIR, GENERATED_DIR, WORKSPACE_DIR

logger = logging.getLogger("bek.vision.image_generation")


def _get_api_key(key_name: str) -> str:
    try:
        from provider_manager import provider_manager
        return provider_manager.get_api_key(key_name)
    except Exception:
        return os.environ.get(key_name, "")


def _resolve_existing_media_paths(paths_input, extensions=(".png", ".jpg", ".jpeg", ".webp")):
    resolved = []
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


def _clean_prompt_for_image(prompt: str) -> str:
    if not prompt or not isinstance(prompt, str):
        return prompt
    import re
    q = re.sub(r'^\s*(User|System|Assistant)\s*:\s*["\']?', '', prompt, flags=re.IGNORECASE)
    q = q.strip(' "\'')
    return q or prompt


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDERS INDIVIDUELS
# ══════════════════════════════════════════════════════════════════════════════

def _try_pollinations(prompt: str, save_path: str, output_filename: str, **kwargs) -> Dict[str, Any]:
    try:
        from services.vision.pollinations_client import generate_image_with_pollinations
        clean_prompt = _clean_prompt_for_image(prompt)
        logger.info("[pollinations] Génération (5 retries robustes)")
        return generate_image_with_pollinations(
            prompt=clean_prompt, model="flux", output_filename=output_filename,
            width=kwargs.get("width", 1024), height=kwargs.get("height", 1024),
            optimize_prompt=False,
        )
    except Exception as e:
        logger.warning("[pollinations] Erreur : %s", e)
        return {"status": "error", "message": f"Pollinations : {e}", "provider": "pollinations"}


def _try_huggingface(prompt: str, save_path: str, output_filename: str, **kwargs) -> Dict[str, Any]:
    api_key = _get_api_key("HUGGINGFACE_API_KEY")
    if not api_key:
        return {"status": "error", "message": "HUGGINGFACE_API_KEY manquante", "provider": "huggingface"}
    try:
        from services.vision.huggingface_client import generate_image_with_huggingface
        clean_prompt = _clean_prompt_for_image(prompt)
        # ★ FIX v6.5 : Remplacement du modèle déprécié par le vrai identifiant
        hf_model = kwargs.get("hf_model", "black-forest-labs/FLUX.1-schnell")
        logger.info("[huggingface] Génération : %d chars | model=%s", len(clean_prompt), hf_model)
        return generate_image_with_huggingface(
            prompt=clean_prompt, model=hf_model, output_filename=output_filename,
            width=kwargs.get("width", 1024), height=kwargs.get("height", 1024),
            optimize_prompt=False,
        )
    except Exception as e:
        logger.warning("[huggingface] Erreur : %s", e)
        return {"status": "error", "message": f"HuggingFace : {e}", "provider": "huggingface"}


def _try_gemini(prompt: str, save_path: str, output_filename: str, **kwargs) -> Dict[str, Any]:
    api_key = _get_api_key("GEMINI_API_KEY")
    if not api_key:
        return {"status": "error", "message": "GEMINI_API_KEY manquante", "provider": "gemini"}
    
    # ★ FIX v6.5 : Utilisation du bon modèle Gemini Image
    model_id = kwargs.get("model", "gemini-2.5-flash-image")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [{"text": _clean_prompt_for_image(prompt)}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }
    try:
        logger.info("[gemini] Génération : %d chars | model=%s", len(prompt), model_id)
        res = requests.post(url, json=payload, timeout=60)
        if res.status_code != 200:
            return {"status": "error", "message": f"Gemini HTTP {res.status_code} - {res.text[:200]}", "provider": "gemini"}
        data = res.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        for part in parts:
            inline = part.get("inline_data") or part.get("inlineData")
            if inline and inline.get("data"):
                with open(save_path, "wb") as f:
                    f.write(base64.b64decode(inline["data"]))
                logger.info("[gemini] ✅ Sauvegardé : %s", output_filename)
                return {"status": "success", "filepath": save_path, "filename": output_filename, "provider": "gemini"}
        return {"status": "error", "message": "Gemini réponse vide", "provider": "gemini"}
    except Exception as e:
        logger.warning("[gemini] Erreur : %s", e)
        return {"status": "error", "message": f"Gemini : {e}", "provider": "gemini"}


def _try_b_ai(prompt: str, save_path: str, output_filename: str, **kwargs) -> Dict[str, Any]:
    api_key = _get_api_key("B_AI_API_KEY")
    if not api_key:
        return {"status": "error", "message": "B_AI_API_KEY manquante", "provider": "b_ai"}
    url = "https://api.b.ai/v1/images/generations"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "gpt-image-2", "prompt": _clean_prompt_for_image(prompt), "n": 1, "size": kwargs.get("size", "1024x1024"), "quality": kwargs.get("quality", "high"), "output_format": "png"}
    try:
        logger.info("[b_ai] Génération : %d chars", len(prompt))
        res = requests.post(url, headers=headers, json=payload, timeout=120)
        if res.status_code != 200:
            return {"status": "error", "message": f"B.AI HTTP {res.status_code}", "provider": "b_ai"}
        data = res.json()
        img_url = data.get("data", [{}])[0].get("url")
        img_b64 = data.get("data", [{}])[0].get("b64_json")
        if img_url:
            img_res = requests.get(img_url, timeout=60)
            with open(save_path, "wb") as f: f.write(img_res.content)
        elif img_b64:
            with open(save_path, "wb") as f: f.write(base64.b64decode(img_b64))
        else:
            return {"status": "error", "message": "B.AI réponse vide", "provider": "b_ai"}
        return {"status": "success", "filepath": save_path, "filename": output_filename, "provider": "b_ai", "model_id": "gpt-image-2"}
    except Exception as e:
        return {"status": "error", "message": f"B.AI : {e}", "provider": "b_ai"}


def _try_beatapi(prompt: str, save_path: str, output_filename: str, **kwargs) -> Dict[str, Any]:
    api_key = _get_api_key("BEATAPI_API_KEY")
    if not api_key:
        return {"status": "error", "message": "BEATAPI_API_KEY manquante", "provider": "beatapi"}
    url = "https://api.beatapi.io/v1/images/generations"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "gpt-image-2", "prompt": _clean_prompt_for_image(prompt), "n": 1, "size": kwargs.get("size", "1024x1024"), "quality": kwargs.get("quality", "high"), "output_format": "png"}
    try:
        logger.info("[beatapi] Génération : %d chars", len(prompt))
        res = requests.post(url, headers=headers, json=payload, timeout=120)
        if res.status_code != 200:
            return {"status": "error", "message": f"BeatAPI HTTP {res.status_code}", "provider": "beatapi"}
        data = res.json()
        img_url = data.get("data", [{}])[0].get("url")
        img_b64 = data.get("data", [{}])[0].get("b64_json")
        if img_url:
            img_res = requests.get(img_url, timeout=60)
            with open(save_path, "wb") as f: f.write(img_res.content)
        elif img_b64:
            with open(save_path, "wb") as f: f.write(base64.b64decode(img_b64))
        else:
            return {"status": "error", "message": "BeatAPI réponse vide", "provider": "beatapi"}
        return {"status": "success", "filepath": save_path, "filename": output_filename, "provider": "beatapi", "model_id": "gpt-image-2"}
    except Exception as e:
        return {"status": "error", "message": f"BeatAPI : {e}", "provider": "beatapi"}


# ══════════════════════════════════════════════════════════════════════════════
# ★ v6.4 — FALLBACK PLACEHOLDER (si tous les providers échouent)
# ══════════════════════════════════════════════════════════════════════════════

def _generate_placeholder_image(prompt: str, output_filename: str = "") -> Dict[str, Any]:
    """
    ★ v6.4 — Génère une image placeholder locale si tous les providers sont HS.
    Utilise Pillow pour créer une image 1024x1024 avec le prompt écrit dessus.
    """
    try:
        from PIL import Image, ImageDraw
        
        if not output_filename:
            output_filename = f"placeholder_{uuid.uuid4().hex[:8]}.png"
        
        save_path = os.path.abspath(os.path.join(GENERATED_DIR, secure_filename(output_filename)))
        
        # Créer l'image 1024x1024 avec fond gris foncé
        img = Image.new("RGB", (1024, 1024), color=(30, 30, 40))
        draw = ImageDraw.Draw(img)
        
        # Titre
        draw.text((50, 200), "🖼️ IMAGE PLACEHOLDER", fill=(100, 200, 255))
        
        # Prompt en plusieurs lignes (max 60 chars par ligne)
        prompt_clean = _clean_prompt_for_image(prompt)
        lines = []
        current = ""
        for word in prompt_clean.split():
            if len(current) + len(word) + 1 > 60:
                lines.append(current)
                current = word
            else:
                current = (current + " " + word).strip()
        if current:
            lines.append(current)
        
        # Écrire le prompt
        y = 300
        for line in lines[:15]:
            draw.text((50, y), f"Prompt : {line}" if y == 300 else line, fill=(220, 220, 220))
            y += 30
        
        # Note explicative
        draw.text((50, 900), "⚠️ Tous les providers d'image sont indisponibles.", fill=(255, 180, 100))
        draw.text((50, 930), "Cette image est un placeholder généré localement.", fill=(180, 180, 180))
        
        # Sauvegarder
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        img.save(save_path, "PNG")
        
        logger.info("[Vision/Fallback] ✅ Placeholder généré : %s", output_filename)
        return {
            "status": "success",
            "filename": output_filename,
            "filepath": save_path,
            "provider": "placeholder",
            "model_id": "pillow-fallback",
            "message": "Image placeholder générée (providers indisponibles). Configure un provider pour de vraies images.",
        }
    except Exception as e:
        logger.error("[Vision/Fallback] Échec placeholder : %s", e)
        return {
            "status": "error",
            "message": f"Impossible de générer même un placeholder : {e}",
            "provider": "placeholder",
        }


# ══════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE AVEC CASCADE
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULT_CHAIN = ["pollinations", "huggingface", "gemini"]
_CHAIN_BY_PROVIDER = {
    "auto": _DEFAULT_CHAIN, "pollinations": _DEFAULT_CHAIN,
    "huggingface": ["huggingface", "pollinations", "gemini"],
    "gemini": ["gemini", "pollinations", "huggingface"],
    "b_ai": ["b_ai", "pollinations", "huggingface", "gemini"],
    "biai": ["b_ai", "pollinations", "huggingface", "gemini"],
    "b.ai": ["b_ai", "pollinations", "huggingface", "gemini"],
    "beatapi": ["beatapi", "pollinations", "huggingface", "gemini"],
}
_PROVIDER_FUNCS = {"pollinations": _try_pollinations, "huggingface": _try_huggingface, "gemini": _try_gemini, "b_ai": _try_b_ai, "beatapi": _try_beatapi}


def generate_image_with_provider(prompt: str, provider: str = "pollinations", model: str = "flux", output_filename: str = "", **kwargs) -> Dict[str, Any]:
    if not output_filename:
        output_filename = f"gen_image_{uuid.uuid4().hex[:8]}.png"

    # ★ FIX v6.3 : Lazy import pour casser l'import circulaire
    try:
        from services.prompt_optimizer import optimize_prompt_for_media
        prompt = optimize_prompt_for_media(prompt, media_type="image")
    except Exception as e:
        logger.warning("[image_generation] Impossible d'optimiser le prompt : %s", e)

    save_path = os.path.abspath(os.path.join(GENERATED_DIR, secure_filename(output_filename)))
    provider_lower = (provider or "pollinations").lower().strip()
    chain = _CHAIN_BY_PROVIDER.get(provider_lower, _DEFAULT_CHAIN)

    logger.info("[image_generation] Cascade : %s (provider demandé=%s)", chain, provider_lower)
    errors: Dict[str, str] = {}

    for idx, prov in enumerate(chain, 1):
        func = _PROVIDER_FUNCS.get(prov)
        if not func: continue
        logger.info("[image_generation] [%d/%d] Tentative %s...", idx, len(chain), prov)
        result = func(prompt, save_path, output_filename, **kwargs)
        if result.get("status") == "success":
            result["fallback_chain"] = chain[:idx]
            result["total_attempts"] = idx
            return result
        errors[prov] = result.get("message", "inconnu")
        logger.warning("[image_generation] ❌ %s échoué : %s", prov, errors[prov])

    # ★ v6.4 : Fallback placeholder si TOUS les providers échouent
    logger.warning("[image_generation] ⚠️ Tous les providers ont échoué → fallback placeholder")
    placeholder_result = _generate_placeholder_image(prompt, output_filename)
    
    if placeholder_result.get("status") == "success":
        placeholder_result["provider_errors"] = errors
        placeholder_result["message"] = (
            "⚠️ Tous les providers d'image ont échoué. "
            "Un placeholder local a été généré à la place.\n\n"
            "**Providers testés :**\n" 
            + "\n".join(f"  • {p}: {e}" for p, e in errors.items())
        )
        return placeholder_result
    
    # Si même le placeholder échoue, on retourne l'erreur finale
    return {
        "status": "error",
        "message": "Tous les providers d'image ont échoué ET le placeholder n'a pas pu être généré.\n" 
                   + "\n".join(f"  • {p}: {e}" for p, e in errors.items()),
        "provider_errors": errors,
    }


def merge_and_edit_images(image_paths: Any = None, user_prompt: str = "", prompt: str = "", provider: str = "pollinations", model: str = "flux") -> Dict[str, Any]:
    active_prompt = user_prompt or prompt or "Modify this image"
    valid_paths = _resolve_existing_media_paths(image_paths)
    analysis = ""
    if valid_paths:
        try:
            from services.vision.image_analysis import analyze_image_with_vision
            analysis = analyze_image_with_vision(valid_paths[0], "Describe this image in detail")
        except Exception as e:
            logger.warning("[merge_and_edit] analyse échouée : %s", e)
    full_prompt = f"Reference: {analysis}\n\nModification: {active_prompt}" if analysis else active_prompt
    return generate_image_with_provider(full_prompt, provider=provider, model=model)