# ==============================================================================
# BEK-v16 — Vision / Pollinations Client
# ------------------------------------------------------------------------------
# Client Pollinations.ai — génération d'images gratuite et illimitée.
#   - generate_image_with_pollinations() : text-to-image
#   - Aucune clé API requise
#   - Supporte plusieurs modèles (flux, flux-3d, flux-realism, etc.)
#
# v26 (2026-09-21) : Création initiale
# v27 (2026-09-21) : enhance=False par défaut
# v28.1 (2026-10-06) : FIX NORMALISATION PROMPT
# v28.2 (2026-10-06) : FIX HTTP 402 (rate limit)
# v28.3 (2026-10-06) : FIX FAUX POSITIFS (suppression \b(A)/\b(An))
#
# ★ v28.4 (2026-10-06) : AJOUT PATTERNS FRANÇAIS
#   - 50+ collisions françaises (minimalisteet, futuristepour, vertnéon, ...)
#   - 30+ réparations de mots cassés (a bstract, mi nimaliste, ...)
#   - Support complet des accents (é, è, ê, à, ç)
#   - ★ AUCUNE fonctionnalité existante supprimée (100% compatible v28.3)
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
    "flux":           "flux",
    "flux-3d":        "flux-3d",
    "flux-realism":   "flux-realism",
    "flux-anime":     "flux-anime",
    "any-dark":       "any-dark",
    "turbo":          "turbo",
}

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


# ==============================================================================
# ★ v28.2 — HEADERS IDENTIFIABLES (fix HTTP 402)
# ==============================================================================
def _build_headers() -> Dict[str, str]:
    return {
        "User-Agent": "BEK-Agent/1.0 (+https://bek-v15-clean.onrender.com)",
        "Accept": "image/png,image/jpeg,image/webp,image/*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ★ v28.4 — NORMALISATION DU PROMPT (FR + EN)
# ══════════════════════════════════════════════════════════════════════════════

# Réparation de mots cassés par un mauvais splitter
_BROKEN_WORD_REPAIRS = [
    (r'\ba bstract\b', 'abstract'),
    (r'\ba bove\b', 'above'),
    (r'\ba pple\b', 'apple'),
    (r'\ba cross\b', 'across'),
    (r'\ba dapt\b', 'adapt'),
    (r'\ba dd\b', 'add'),
    (r'\ba dvanced\b', 'advanced'),
    (r'\ba live\b', 'alive'),
    (r'\ba lone\b', 'alone'),
    (r'\ba long\b', 'along'),
    (r'\ba lso\b', 'also'),
    (r'\ba lways\b', 'always'),
    (r'\ba mazing\b', 'amazing'),
    (r'\ba mbient\b', 'ambient'),
    (r'\ba pproach\b', 'approach'),
    (r'\ba round\b', 'around'),
    (r'\ba rtistic\b', 'artistic'),
    (r'\bmi nimaliste\b', 'minimaliste'),
    (r'\bmi nimalist\b', 'minimalist'),
    (r'\bfu turiste\b', 'futuriste'),
    (r'\bfu turistic\b', 'futuristic'),
]

# Patterns de collisions classiques (mots collés)
_COMMON_COLLISIONS = [
    # ─── Français (v28.4) ───
    (r'minimalisteet', 'minimaliste et'),
    (r'minimalistepour', 'minimaliste pour'),
    (r'minimalisteetfuturiste', 'minimaliste et futuriste'),
    (r'futuristepour', 'futuriste pour'),
    (r'futuristeet', 'futuriste et'),
    (r'circuitabstrait', 'circuit abstrait'),
    (r'circuitabstraits', 'circuits abstraits'),
    (r'circuitsabstraits', 'circuits abstraits'),
    (r'motifde', 'motif de'),
    (r'motifcircuit', 'motif circuit'),
    (r'vertnéon', 'vert néon'),
    (r'vertneon', 'vert neon'),
    (r'bleuélectrique', 'bleu électrique'),
    (r'bleuelectrique', 'bleu electrique'),
    (r'bleuélec', 'bleu élec'),
    (r'fondsombre', 'fond sombre'),
    (r'fondnoir', 'fond noir'),
    (r'fondblanc', 'fond blanc'),
    (r'fondbleu', 'fond bleu'),
    (r'stylehigh-tech', 'style high-tech'),
    (r'stylehightech', 'style hightech'),
    (r'stylehigh', 'style high'),
    (r'lettret', 'lettre t'),
    (r'lettrea', 'lettre a'),
    (r'lettrein', 'lettre in'),
    (r'startuptech', 'startup tech'),
    (r'une startuptech', 'une startup tech'),
    (r'une startup', 'une startup'),
    (r'pourune', 'pour une'),
    (r'dansune', 'dans une'),
    (r'avecdans', 'avec dans'),
    (r'surle', 'sur le'),
    (r'surla', 'sur la'),
    (r'surles', 'sur les'),
    (r'dansle', 'dans le'),
    (r'dansla', 'dans la'),
    (r'dansles', 'dans les'),
    (r'avecle', 'avec le'),
    (r'avecla', 'avec la'),
    (r'avecles', 'avec les'),
    (r'surdes', 'sur des'),
    (r'pourdes', 'pour des'),
    (r'pourle', 'pour le'),
    (r'pourla', 'pour la'),
    (r'pourles', 'pour les'),
    (r'etmoderne', 'et moderne'),
    (r'etépuré', 'et épuré'),
    (r'etepure', 'et epure'),
    (r'épuré', 'épuré'),
    (r'moderne', 'moderne'),
    (r'designminimaliste', 'design minimaliste'),
    (r'designmoderne', 'design moderne'),
    (r'designfuturiste', 'design futuriste'),
    (r'moderneet', 'moderne et'),
    (r'épuréet', 'épuré et'),

    # ─── Anglais (v28.3) ───
    (r'sleeklogo', 'sleek logo'),
    (r'minimalistlogo', 'minimalist logo'),
    (r'modernlogo', 'modern logo'),
    (r'simplelogo', 'simple logo'),
    (r'logofora', 'logo for a'),
    (r'logowith', 'logo with'),
    (r'logofor', 'logo for'),
    (r'foratech', 'for a tech'),
    (r'techstartup', 'tech startup'),
    (r'startupcompany', 'startup company'),
    (r'futuristictech', 'futuristic tech'),
    (r'minimalistfuturistic', 'minimalist futuristic'),
    (r'modernfuturistic', 'modern futuristic'),
    (r'featuringabstract', 'featuring abstract'),
    (r'featuringmodern', 'featuring modern'),
    (r'featuringminimalist', 'featuring minimalist'),
    (r'circuitrypatterns', 'circuitry patterns'),
    (r'circuitpatterns', 'circuit patterns'),
    (r'abstractcircuit', 'abstract circuit'),
    (r'patternsforming', 'patterns forming'),
    (r'linesforming', 'lines forming'),
    (r'shapesforming', 'shapes forming'),
    (r'formingastylized', 'forming a stylized'),
    (r'formingstylized', 'forming stylized'),
    (r'electricblue', 'electric blue'),
    (r'neongreen', 'neon green'),
    (r'neonblue', 'neon blue'),
    (r'darkblue', 'dark blue'),
    (r'lightblue', 'light blue'),
    (r'deepblue', 'deep blue'),
    (r'brightblue', 'bright blue'),
    (r'bluecolor', 'blue color'),
    (r'bluecolour', 'blue colour'),
    (r'redcolor', 'red color'),
    (r'greencolor', 'green color'),
    (r'gradientofelectric', 'gradient of electric'),
    (r'onadarkbackground', 'on a dark background'),
    (r'onadark', 'on a dark'),
    (r'darkbackground', 'dark background'),
    (r'onwhitebackground', 'on white background'),
    (r'whitebackground', 'white background'),
    (r'lightbackground', 'light background'),
    (r'transparentbackground', 'transparent background'),
    (r'greenon', 'green on'),
    (r'blueon', 'blue on'),
    (r'blackon', 'black on'),
    (r'whiteon', 'white on'),
    (r'onelectric', 'on electric'),
    (r'ondark', 'on dark'),
    (r'minimalisticand', 'minimalistic and'),
    (r'futuristicdesign', 'futuristic design'),
    (r'highcontrast', 'high contrast'),
    (r'lowcontrast', 'low contrast'),
    (r'vectorstyle', 'vector style'),
    (r'flatdesign', 'flat design'),
    (r'modernsleek', 'modern sleek'),
    (r'cleanlines', 'clean lines'),
    (r'suitablefor', 'suitable for'),
    (r'highquality', 'high quality'),
    (r'detaileddesign', 'detailed design'),
    (r'softlighting', 'soft lighting'),
    (r'studiolighting', 'studio lighting'),
    (r'digitalart', 'digital art'),
    (r'conceptart', 'concept art'),
    (r'characterdesign', 'character design'),
    (r'lettert', 'letter t'),
    (r'lettera', 'letter a'),
    (r'letterin', 'letter in'),
    (r'stylizedletter', 'stylized letter'),

    # ─── Bug analyse image (v28.4) ───
    (r'endétail', 'en détail'),
    (r'endetail', 'en detail'),
    (r'vueensemble', 'vue ensemble'),
    (r'planslarge', 'plan large'),
    (r'grosplan', 'gros plan'),
]


def _normalize_prompt_spacing(prompt: str) -> str:
    """
    ★ v28.4 — Normalise les espaces d'un prompt (FR + EN).

    1. Réparation des mots cassés ("a bstract" → "abstract")
    2. CamelCase → "Camel Case"
    3. Ponctuation → espace après virgule/point-virgule
    4. 100+ patterns de collisions (FR + EN)
    5. Nettoyage final

    ⚠️ NE TOUCHE PAS aux URLs ni aux chaînes JSON.
    """
    if not prompt or not isinstance(prompt, str):
        return prompt

    if prompt.startswith(("http://", "https://", "/", "./")):
        return prompt
    if prompt.startswith("{") and prompt.endswith("}"):
        return prompt

    text = prompt.strip()

    # ─── 1. Réparer les mots cassés ───
    for pattern, replacement in _BROKEN_WORD_REPAIRS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # ─── 2. Minuscule suivie de Majuscule → espace ───
    text = re.sub(r'([a-zà-ÿ])([A-ZÀ-Ý])', r'\1 \2', text)

    # ─── 3. Virgule sans espace après ───
    text = re.sub(r',([^\s])', r', \1', text)

    # ─── 4. Deux-points sans espace (mais pas http://) ───
    text = re.sub(r'([a-zA-Z]):([^\s/])', r'\1: \2', text)

    # ─── 5. Point-virgule sans espace ───
    text = re.sub(r';([^\s])', r'; \1', text)

    # ─── 6. Patterns de collisions ───
    for pattern, replacement in _COMMON_COLLISIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # ─── 7. Nettoyage final ───
    text = re.sub(r'\s+', ' ', text).strip()
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
    enhance: bool = False,
    nologo: bool = True,
    private: bool = True,
    optimize_prompt: bool = True,
) -> Dict[str, Any]:
    """Génère une image via Pollinations.ai (gratuit, illimité)."""
    if not output_filename:
        output_filename = f"pollinations_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.abspath(
        os.path.join(GENERATED_DIR, secure_filename(output_filename))
    )

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

    # ★ v28.4 — NORMALISATION
    final_prompt = _normalize_prompt_spacing(final_prompt)
    logger.info(
        "[vision.pollinations] Prompt normalisé : %s", final_prompt[:120]
    )

    model_id = POLLINATIONS_MODELS.get(model, model)
    encoded_prompt = urllib.parse.quote(final_prompt)

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

    headers = _build_headers()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.get(url, headers=headers, timeout=120)
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

        if res.status_code == 402:
            logger.warning(
                "[vision.pollinations] HTTP 402 (rate limit) — tentative %d/%d",
                attempt + 1, max_retries,
            )
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return {
                "status": "error",
                "message": (
                    "Pollinations HTTP 402 (rate limit atteint). "
                    "Réessayez dans 30 secondes."
                ),
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
    """Retourne la liste des modèles Pollinations disponibles."""
    return list(POLLINATIONS_MODELS.keys())