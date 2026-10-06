# ==============================================================================
# BEK-v16 — Vision / Pollinations Client
# ------------------------------------------------------------------------------
# Client Pollinations.ai — génération d'images gratuite et illimitée.
#   - generate_image_with_pollinations() : text-to-image
#   - Aucune clé API requise
#   - Supporte plusieurs modèles (flux, flux-3d, flux-realism, etc.)
#
# v26 (2026-09-21) : Création initiale
# v27 (2026-09-21) : enhance=False par défaut (évite le bruit ajouté)
# ★ v28.1 (2026-10-06) : FIX NORMALISATION PROMPT
#   - Ajout _normalize_prompt_spacing() après optimisation
#   - Corrige "minimalistlogo" → "minimalist logo"
#   - Corrige "suitablefor" → "suitable for"
#   - Corrige "lines,professional" → "lines, professional"
#   - Corrige aussi les majuscules collées : "CleanLines" → "Clean Lines"
#   - ★ AUCUNE fonctionnalité existante supprimée (100% compatible v27)
# ==============================================================================
from __future__ import annotations

import logging
import os
import re
import time
import urllib.parse
import uuid
from typing import Any, Dict, Optional

import requests
from werkzeug.utils import secure_filename

from core.paths import GENERATED_DIR
from services.prompt_optimizer import optimize_prompt_for_media

logger = logging.getLogger("bek.vision.pollinations")


# ==============================================================================
# MODÈLES POLLINATIONS DISPONIBLES
# ==============================================================================
POLLINATIONS_MODELS: Dict[str, str] = {
    # Noms courts UI -> IDs Pollinations
    "flux":           "flux",            # Défaut (généraliste)
    "flux-3d":        "flux-3d",         # 3D render (Pixar-style)
    "flux-realism":   "flux-realism",    # Photoréaliste
    "flux-anime":     "flux-anime",      # Anime / manga
    "any-dark":       "any-dark",        # Cinématique sombre
    "turbo":          "turbo",           # Rapide basse qualité
}

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


# ══════════════════════════════════════════════════════════════════════════════
# ★ v28.1 — NORMALISATION DU PROMPT (fix mots collés)
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_prompt_spacing(prompt: str) -> str:
    """
    Normalise les espaces d'un prompt avant envoi à Pollinations.

    Corrige les collisions classiques issues de la concaténation automatique :
      - "minimalistlogo"        → "minimalist logo"
      - "suitablefor a tech"    → "suitable for a tech"
      - "lines,professional"    → "lines, professional"
      - "CleanLines"            → "Clean Lines"

    ⚠️ On ne touche PAS aux mots composés valides (ex: "flux-3d", "photorealistic").
    """
    if not prompt or not isinstance(prompt, str):
        return prompt

    text = prompt.strip()

    # ─── 1. Minuscule suivie de Majuscule → espace ───
    #    "CleanLines" → "Clean Lines", "BlueColor" → "Blue Color"
    text = re.sub(r'([a-zà-ÿ])([A-ZÀ-Ý])', r'\1 \2', text)

    # ─── 2. Virgule sans espace après → ajouter espace ───
    #    "lines,professional" → "lines, professional"
    text = re.sub(r',([^\s])', r', \1', text)

    # ─── 3. Deux-points sans espace après → ajouter espace ───
    text = re.sub(r':([^\s/])', r': \1', text)

    # ─── 4. Point-virgule sans espace → ajouter espace ───
    text = re.sub(r';([^\s])', r'; \1', text)

    # ─── 5. Mots collés fréquents (français + anglais) ───
    common_collisions = [
        (r'\bsuitablefor\b', 'suitable for'),
        (r'\bminimalistlogo\b', 'minimalist logo'),
        (r'\bmodernlogo\b', 'modern logo'),
        (r'\bcleanlines\b', 'clean lines'),
        (r'\bbluecolor\b', 'blue color'),
        (r'\bprofessional look\b', 'professional look'),
        (r'\btechstartup\b', 'tech startup'),
        (r'\bhighquality\b', 'high quality'),
        (r'\bdetaileddesign\b', 'detailed design'),
        (r'\bsoftlighting\b', 'soft lighting'),
        (r'\bstudiolighting\b', 'studio lighting'),
        (r'\bdigitalart\b', 'digital art'),
        (r'\bconceptart\b', 'concept art'),
    ]
    for pattern, replacement in common_collisions:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # ─── 6. Nettoyage final : espaces multiples → un seul ───
    text = re.sub(r'\s+', ' ', text).strip()

    # ─── 7. Nettoyage des espaces avant ponctuation ───
    text = re.sub(r'\s+([,;:.!?])', r'\1', text)

    return text


# ==============================================================================
# GÉNÉRATION D'IMAGE
# ==============================================================================
def generate_image_with_pollinations(
    prompt: str,
    model: str = "flux-3d",
    output_filename: str = "",
    width: int = 1024,
    height: int = 1024,
    seed: Optional[int] = None,
    enhance: bool = False,        # ★ v27 : False par défaut (pas de bruit)
    nologo: bool = True,
    private: bool = True,
    optimize_prompt: bool = True,
) -> Dict[str, Any]:
    """
    Génère une image via Pollinations.ai (gratuit, illimité, sans clé API).

    Args:
        prompt      : description de l'image (FR ou EN)
        model       : "flux-3d" (défaut) | "flux" | "flux-realism" |
                      "flux-anime" | "any-dark" | "turbo"
        output_filename : nom du fichier de sortie
        width, height  : dimensions (défaut 1024x1024)
        seed        : graine pour reproductibilité (None = aléatoire)
        enhance     : Pollinations améliore automatiquement le prompt
                      (★ False par défaut — évite le bruit)
        nologo      : retire le watermark "pollinations.ai"
        private     : n'expose pas l'image dans la galerie publique
        optimize_prompt : optimiser le prompt via prompt_optimizer

    Returns:
        {"status": "success", "filepath": ..., "filename": ..., "model_id": ...}
        ou {"status": "error", "message": ...}
    """
    if not output_filename:
        output_filename = f"pollinations_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.abspath(
        os.path.join(GENERATED_DIR, secure_filename(output_filename))
    )

    # Optimisation du prompt
    final_prompt = prompt
    if optimize_prompt:
        try:
            final_prompt = optimize_prompt_for_media(
                prompt, media_type="image", style_preset="cardboard_3d"
            )
            logger.info(
                "[vision.pollinations] Prompt optimisé : %s", final_prompt[:100]
            )
        except Exception as e:
            logger.warning(
                "[vision.pollinations] Optimisation prompt échouée : %s", e
            )

    # ══════════════════════════════════════════════════════════════════════
    # ★ v28.1 — NORMALISATION OBLIGATOIRE APRÈS OPTIMISATION
    # ══════════════════════════════════════════════════════════════════════
    final_prompt = _normalize_prompt_spacing(final_prompt)
    logger.info(
        "[vision.pollinations] Prompt normalisé : %s", final_prompt[:120]
    )

    # Résolution du modèle
    model_id = POLLINATIONS_MODELS.get(model, model)

    # Construction de l'URL
    encoded_prompt = urllib.parse.quote(final_prompt)

    # ★ v28 : seed aléatoire par défaut pour éviter le cache Pollinations
    if seed is None:
        seed = int(time.time() * 1000) % (2 ** 31)

    params = {
        "width": width,
        "height": height,
        "model": model_id,
        "nologo": str(nologo).lower(),
        "private": str(private).lower(),
        "enhance": str(enhance).lower(),
        "seed": seed,
    }

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{POLLINATIONS_BASE}/{encoded_prompt}?{query_string}"

    logger.info(
        "[vision.pollinations] generate : model=%s size=%dx%d enhance=%s prompt=%r",
        model_id, width, height, enhance, final_prompt[:80],
    )

    # Retry (Pollinations peut timeout sur grosses images)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.get(url, timeout=120)
        except requests.Timeout:
            logger.warning(
                "[vision.pollinations] Timeout (tentative %d/%d)",
                attempt + 1, max_retries,
            )
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return {
                "status": "error",
                "message": "Timeout Pollinations (3 tentatives échouées).",
            }
        except requests.RequestException as e:
            return {
                "status": "error",
                "message": f"Erreur réseau Pollinations : {e}",
            }

        if res.status_code == 200 and len(res.content) > 1000:
            with open(save_path, "wb") as f:
                f.write(res.content)
            logger.info(
                "[vision.pollinations] OK : %s (%d bytes)",
                output_filename, len(res.content),
            )
            return {
                "status": "success",
                "filepath": save_path,
                "filename": output_filename,
                "model_id": model_id,
                "provider": "pollinations",
                "size_bytes": len(res.content),
                "url": url,
            }

        # Erreur HTTP ou contenu trop petit (probablement vide)
        if attempt < max_retries - 1:
            logger.warning(
                "[vision.pollinations] HTTP %s (tentative %d/%d), retry...",
                res.status_code, attempt + 1, max_retries,
            )
            time.sleep(2)
            continue

        return {
            "status": "error",
            "message": (
                f"Pollinations HTTP {res.status_code} "
                f"({len(res.content)} bytes reçus)."
            ),
        }

    return {
        "status": "error",
        "message": "Pollinations : échec après plusieurs tentatives.",
    }


# ==============================================================================
# LISTE DES MODÈLES
# ==============================================================================
def list_pollinations_models() -> list:
    """Retourne la liste des modèles Pollinations disponibles (noms courts UI)."""
    return list(POLLINATIONS_MODELS.keys())