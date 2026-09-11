# ==============================================================================
# BEK-v16 — Vision & Génération d'images (Ultra-Résilient & Multi-Modèles)
# ==============================================================================
import os
import base64
import uuid
import urllib.parse

import requests
from werkzeug.utils import secure_filename

from core.paths import WORKSPACE_DIR, FILES_DIR, GENERATED_DIR
from provider_manager import provider_manager


def get_api_key(key_name: str) -> str:
    return provider_manager.get_api_key(key_name)


def analyze_image_with_vision(image_path: str, prompt: str, provider: str = "gemini", model: str = "") -> str:
    target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, image_path))
    if not os.path.exists(target_path):
        for d in [FILES_DIR, GENERATED_DIR]:
            alt = os.path.join(d, image_path)
            if os.path.exists(alt):
                target_path = alt
                break

    if not os.path.exists(target_path):
        return f"Erreur Vision : Image introuvable sur le disque ({image_path})."

    try:
        with open(target_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode('utf-8')

        ext = image_path.split('.')[-1].lower()
        mime_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
        mime_type = mime_map.get(ext, "image/png")
        provider = (provider or "gemini").lower()
        prompt_text = prompt or "Analyse cette image en détail."

        # 1. Tentative NVIDIA NIM
        if provider == "nvidia":
            api_key = get_api_key("NVIDIA_API_KEY")
            if api_key:
                url = "https://integrate.api.nvidia.com/v1/chat/completions"
                active_model = model if model else "meta/llama-3.2-90b-vision-instruct"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": active_model,
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"}}
                    ]}],
                    "max_tokens": 1024
                }
                try:
                    res = requests.post(url, json=payload, headers=headers, timeout=45)
                    if res.status_code == 200:
                        return res.json()["choices"][0]["message"]["content"]
                except Exception:
                    pass

        # 2. Tentative B.ai ou autres OpenAI-compatibles
        if provider in ["b_ai", "groq", "mistral"]:
            key_name = f"{provider.upper()}_API_KEY" if provider != "b_ai" else "B_AI_API_KEY"
            api_key = get_api_key(key_name) or get_api_key("GROQ_API_KEY")
            if api_key:
                # Si le fournisseur supporte le multimodal OpenAI-compatible
                pass

        # 3. Tentative GEMINI (avec liste de modèles de secours automatiques)
        gemini_candidates = [model, "gemini-3.6-flash", "gemini-2.5-flash", "gemini-1.5-flash"]
        # Filtrer les valeurs vides ou invalides et supprimer les doublons
        gemini_candidates = [m for i, m in enumerate(gemini_candidates) if m and m not in gemini_candidates[:i]]
        
        api_key = get_api_key("GEMINI_API_KEY")
        if api_key:
            for candidate_model in gemini_candidates:
                # Nettoyer le nom du modèle pour l'API Google v1beta
                clean_model = candidate_model.replace("models/", "")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [
                        {"text": prompt_text},
                        {"inline_data": {"mime_type": mime_type, "data": encoded_image}}
                    ]}]
                }
                try:
                    res = requests.post(url, json=payload, timeout=45)
                    if res.status_code == 200:
                        data = res.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                except Exception:
                    continue

        return "Erreur Vision : Tous les fournisseurs et modèles testés ont échoué à analyser l'image."
    except Exception as e:
        return f"Erreur critique lors du traitement de l'image : {str(e)}"


def generate_image_with_provider(prompt: str, provider: str = "gemini", model: str = "gemini-3.1-flash-image", output_filename: str = "") -> dict:
    if not output_filename:
        output_filename = f"gen_image_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.abspath(os.path.join(GENERATED_DIR, secure_filename(output_filename)))

    try:
        if "gemini" in model.lower() or "image" in model.lower() or "banana" in model.lower():
            provider = "gemini"
        provider = provider.lower()

        if provider == "gemini":
            api_key = get_api_key("GEMINI_API_KEY")
            if not api_key: return {"status": "error", "message": "GEMINI_API_KEY non configurée."}

            actual_api_model = "imagen-3.0-generate-002"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{actual_api_model}:predict?key={api_key}"
            payload = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}}

            res = requests.post(url, json=payload, timeout=60)
            if res.status_code == 200:
                data = res.json()
                try:
                    b64_data = data["predictions"][0]["bytesBase64Encoded"]
                    image_bytes = base64.b64decode(b64_data)
                    with open(save_path, "wb") as f:
                        f.write(image_bytes)
                    return {"status": "success", "filepath": save_path, "filename": output_filename}
                except Exception:
                    pass

            fallback_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?nologo=true"
            fallback_res = requests.get(fallback_url, timeout=30)
            if fallback_res.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(fallback_res.content)
                return {"status": "success", "filepath": save_path, "filename": output_filename, "message": "Image générée (via Fallback d'urgence)"}
            return {"status": "error", "message": f"Tous les moteurs ont échoué. Erreur de base : {res.text}"}
        return {"status": "error", "message": f"Provider '{provider}' non supporté."}
    except Exception as e:
        return {"status": "error", "message": f"Erreur technique génération : {str(e)}"}


def merge_and_edit_images(image_paths: list, user_prompt: str, provider: str = "gemini", model: str = "gemini-3.1-flash-image") -> dict:
    try:
        analysis_results = []
        for path in image_paths:
            analysis = analyze_image_with_vision(path, "Décris cette image avec un niveau de détail extrême.", provider="gemini", model=model)
            analysis_results.append(f"- Éléments de '{os.path.basename(path)}' : {analysis}")
        super_prompt = (
            f"Génère une image photoréaliste parfaite basée sur :\n{chr(10).join(analysis_results)}\n\n"
            f"DIRECTIVE : {user_prompt}"
        )
        return generate_image_with_provider(super_prompt, provider=provider, model=model)
    except Exception as e:
        return {"status": "error", "message": f"Erreur fusion visuelle : {str(e)}"}