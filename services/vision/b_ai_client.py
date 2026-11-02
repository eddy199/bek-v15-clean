# ==============================================================================
# BEK-v19 — Client B.AI pour la génération d'images (gpt-image-2)
# ==============================================================================
import os
import uuid
import base64
import logging
import requests
from core.paths import GENERATED_DIR

logger = logging.getLogger("bek.vision.b_ai")

def generate_image_with_b_ai(prompt: str, size: str = "1024x1024", quality: str = "high") -> dict:
    """Génère une image via B.ai et la sauvegarde localement."""
    api_key = os.environ.get("B_AI_API_KEY", "").strip()
    if not api_key:
        return {"status": "error", "message": "Clé B_AI_API_KEY manquante dans le .env"}

    url = "https://api.b.ai/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-image-2",  # Le modèle de ta capture
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": quality,
        "output_format": "png"
    }

    try:
        logger.info("[b_ai] Génération d'image : prompt_len=%d | size=%s", len(prompt), size)
        res = requests.post(url, headers=headers, json=payload, timeout=120)

        if res.status_code != 200:
            logger.error("[b_ai] HTTP %s : %s", res.status_code, res.text[:300])
            return {"status": "error", "message": f"Erreur B.ai : {res.text[:200]}"}

        data = res.json()
        
        # B.ai peut renvoyer une URL ou du base64. On gère les deux.
        img_url = data.get("data", [{}])[0].get("url")
        img_b64 = data.get("data", [{}])[0].get("b64_json")

        out_name = f"b_ai_{uuid.uuid4().hex[:8]}.png"
        out_path = os.path.join(GENERATED_DIR, out_name)

        if img_url:
            img_res = requests.get(img_url, timeout=30)
            with open(out_path, "wb") as f:
                f.write(img_res.content)
        elif img_b64:
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(img_b64))
        else:
            return {"status": "error", "message": "Format de réponse B.ai inconnu"}

        logger.info("[b_ai] ✅ Image sauvegardée : %s", out_name)
        return {
            "status": "success",
            "filepath": out_path,
            "filename": out_name,
            "url": img_url or f"/api/download/{out_name}",
            "provider": "b_ai",
            "model": "gpt-image-2"
        }

    except Exception as e:
        logger.exception("[b_ai] Erreur génération")
        return {"status": "error", "message": f"Exception B.ai : {str(e)}"}