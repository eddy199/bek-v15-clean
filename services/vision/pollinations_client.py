# ==============================================================================
# BEK-v16 — Vision / Pollinations Client
# ------------------------------------------------------------------------------
# v26-v28.5 : historique complet (voir git log)
#
# ★ v28.6 (2026-10-06) : FIX FINAL NORMALISATION
#   - Support acronymes : "AIstartup" → "AI startup", "3Dmodel" → "3D model"
#   - Ajout dictionnaire "colors", "startups", pluriels, verbes
#   - Ajout patterns : blueand, greenand, redand, blackand, whiteand
#   - Fix "a bstract" : regex maintenant avec lookahead
#   - Fix smart splitter : évite de casser les vrais mots en 2
#   - ★ AUCUNE fonctionnalité supprimée (100% compatible v28.5)
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


# ══════════════════════════════════════════════════════════════════════════════
# ★ v28.6 — DICTIONNAIRE ÉTENDU
# ══════════════════════════════════════════════════════════════════════════════
_COMMON_PROMPT_WORDS = frozenset([
    # ─── Mots courts ───
    "a", "an", "in", "on", "of", "or", "to", "by", "as", "is", "at", "be",
    "no", "so", "up", "my", "we", "us", "it", "as", "if", "do", "go",

    # ─── 3-4 lettres ───
    "the", "and", "for", "with", "not", "but", "all", "any", "new", "old",
    "art", "web", "app", "dev", "logo", "icon", "dark", "blue", "neon",
    "high", "low", "line", "lines", "shape", "shapes", "form", "forms",
    "code", "data", "type", "font", "text", "red", "tag", "badge", "star",
    "moon", "sun", "tree", "leaf", "fire", "gold", "pink", "rose", "grey",
    "gray", "cyan", "tech", "cloud", "wave", "edge", "edges", "tone", "mode",
    "soft", "hard", "flat", "fine", "pure", "true", "bold", "cool", "warm",

    # ─── 5-6 lettres ───
    "green", "black", "white", "silver", "color", "colors", "colour", "colours",
    "clean", "bright", "light", "curve", "curves", "style", "space", "cloud",
    "server", "modern", "simple", "smooth", "circle", "circles", "square",
    "squares", "symbol", "letter", "letters", "future", "sharp", "round",
    "arrow", "arrows", "shape", "shapes", "line", "lines", "glow", "shine",
    "crisp", "focus", "depth", "pixel", "pixels", "spark", "sparks", "shine",
    "startup", "startups", "launch", "brand", "brands", "theme", "themes",
    "waves", "dots", "rings", "cross", "crosses", "pluses", "minus",

    # ─── 7-8 lettres ───
    "minimal", "pattern", "patterns", "circuit", "circuits", "feature",
    "features", "forming", "electric", "abstract", "design", "designs",
    "gradient", "gradients", "network", "networks", "cyber", "digital",
    "studio", "creative", "curved", "geometric", "shapes", "arrows",
    "circles", "squares", "triangles", "hexagon", "octagon", "pentagon",
    "polygon", "rhombus", "ellipse", "vectors", "moderns", "futures",
    "futuristic", "american", "european", "silicon", "quantum", "optical",
    "capital", "segment", "section", "sectors", "hextech", "matrixes",

    # ─── 9-10 lettres ───
    "minimalist", "background", "backgrounds", "featuring", "graphical",
    "typography", "calligraphy", "watercolor", "watercolour", "landscape",
    "character", "characters", "identity", "identities",

    # ─── 11+ lettres (à préserver) ───
    "minimalistic", "professional", "contemporary", "photorealistic",
    "hyperrealistic", "illustration", "illustrations", "cinematic",
    "photography", "architecture", "surrealistic", "expressionism",
    "impressionist", "configurable", "configuration",
])


# ══════════════════════════════════════════════════════════════════════════════
# ★ v28.6 — SMART WORD SPLITTER
# ══════════════════════════════════════════════════════════════════════════════
def _smart_split_long_word(word: str, min_len: int = 12) -> str:
    """Découpe un mot collé en composants via dictionnaire."""
    if len(word) < min_len:
        return word
    if word.lower() in _COMMON_PROMPT_WORDS:
        return word

    remaining = word
    parts: list[str] = []
    max_word_len = 15
    min_word_len = 2
    safety = 0

    while remaining and safety < 50:
        safety += 1
        found = False
        max_try = min(max_word_len, len(remaining))

        for length in range(max_try, min_word_len - 1, -1):
            candidate = remaining[:length].lower()
            if candidate in _COMMON_PROMPT_WORDS:
                parts.append(remaining[:length])
                remaining = remaining[length:]
                found = True
                break

        if not found:
            char = remaining[0]
            if char.isupper() and parts and parts[-1] and parts[-1][-1].islower():
                parts.append(char)
            elif parts and len(parts[-1]) < max_word_len:
                parts[-1] += char
            else:
                parts.append(char)
            remaining = remaining[1:]

    result = " ".join(parts)
    if result.count(" ") == 0:
        return word
    return result


def _smart_split_all_long_words(text: str, min_len: int = 12) -> str:
    """Applique _smart_split_long_word à tous les tokens >= min_len."""
    if not text:
        return text

    def replacer(match):
        return _smart_split_long_word(match.group(0), min_len=min_len)

    return re.sub(r'[a-zA-ZÀ-ÿ]{' + str(min_len) + r',}', replacer, text)


# ══════════════════════════════════════════════════════════════════════════════
# HEADERS
# ══════════════════════════════════════════════════════════════════════════════
def _build_headers() -> Dict[str, str]:
    return {
        "User-Agent": "BEK-Agent/1.0 (+https://bek-v15-clean.onrender.com)",
        "Accept": "image/png,image/jpeg,image/webp,image/*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ★ v28.6 — PATTERNS DE RÉPARATION
# ══════════════════════════════════════════════════════════════════════════════
_BROKEN_WORD_REPAIRS = [
    # ★ v28.6 — regex avec lookahead pour éviter les faux positifs
    (r'\ba bstract(?=\s|,|$)', 'abstract'),
    (r'\ba bstract(\w)', 'abstract\1'),
    (r'\ba bove(?=\s|,|$)', 'above'),
    (r'\ba pple(?=\s|,|$)', 'apple'),
    (r'\bmi nimalist\b', 'minimalist'),
    (r'\bmi nimaliste\b', 'minimaliste'),
    (r'\bfu turiste\b', 'futuriste'),
    (r'\bfu turistic\b', 'futuristic'),
    (r'\bmi nimal\b', 'minimal'),
]

_COMMON_COLLISIONS = [
    # ─── Conjonctions collées (★ v28.6) ───
    (r'blueand', 'blue and'),
    (r'greenand', 'green and'),
    (r'redand', 'red and'),
    (r'blackand', 'black and'),
    (r'whiteand', 'white and'),
    (r'darkand', 'dark and'),
    (r'lightand', 'light and'),
    (r'grayand', 'gray and'),
    (r'greyand', 'grey and'),
    (r'silverand', 'silver and'),

    # ─── Français ───
    (r'minimalisteet', 'minimaliste et'),
    (r'futuristepour', 'futuriste pour'),
    (r'circuitabstrait', 'circuit abstrait'),
    (r'motifde', 'motif de'),
    (r'vertnéon', 'vert néon'),
    (r'vertneon', 'vert neon'),
    (r'bleuélectrique', 'bleu électrique'),
    (r'fondsombre', 'fond sombre'),
    (r'fondnoir', 'fond noir'),
    (r'lettret', 'lettre t'),
    (r'pourune', 'pour une'),
    (r'dansune', 'dans une'),
    (r'surle', 'sur le'),
    (r'surla', 'sur la'),
    (r'dansle', 'dans le'),
    (r'dansla', 'dans la'),
    (r'avecle', 'avec le'),
    (r'avecla', 'avec la'),
    (r'pourle', 'pour le'),
    (r'pourla', 'pour la'),

    # ─── Anglais ───
    (r'minimalistlogo', 'minimalist logo'),
    (r'logofora', 'logo for a'),
    (r'logowith', 'logo with'),
    (r'logofor', 'logo for'),
    (r'techstartup', 'tech startup'),
    (r'aistartup', 'ai startup'),
    (r'featuringabstract', 'featuring abstract'),
    (r'circuitpatterns', 'circuit patterns'),
    (r'circuitpattern', 'circuit pattern'),
    (r'electricblue', 'electric blue'),
    (r'neongreen', 'neon green'),
    (r'darkbackground', 'dark background'),
    (r'onadarkbackground', 'on a dark background'),
    (r'colorsona', 'colors on a'),
    (r'colorson', 'colors on'),
    (r'color son', 'colors on'),
    (r'suitablefor', 'suitable for'),
    (r'highquality', 'high quality'),
    (r'cleanlines', 'clean lines'),

    # ─── Bug analyse image ───
    (r'endétail', 'en détail'),
    (r'endetail', 'en detail'),
    (r'vueensemble', 'vue ensemble'),
]


def _normalize_prompt_spacing(prompt: str) -> str:
    """
    ★ v28.6 — Normalisation complète.

    Pipeline :
      1. Réparation des mots cassés ("a bstract" → "abstract")
      2. Acronymes collés ("AIstartup" → "AI startup")
      3. CamelCase → "Camel Case"
      4. Ponctuation
      5. Patterns de collisions (FR + EN)
      6. Smart splitter sur mots > 12 lettres
      7. Nettoyage final
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

    # ─── 2. ★ v28.6 — Acronymes collés (AIstartup → AI startup) ───
    # Match : 2+ majuscules suivies d'une minuscule
    text = re.sub(r'([A-ZÀ-Ý]{2,})([a-zà-ÿ])', r'\1 \2', text)

    # ─── 3. CamelCase ───
    text = re.sub(r'([a-zà-ÿ])([A-ZÀ-Ý])', r'\1 \2', text)

    # ─── 4. Ponctuation ───
    text = re.sub(r',([^\s])', r', \1', text)
    text = re.sub(r'([a-zA-Z]):([^\s/])', r'\1: \2', text)
    text = re.sub(r';([^\s])', r'; \1', text)

    # ─── 5. Patterns de collisions ───
    for pattern, replacement in _COMMON_COLLISIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # ─── 6. Smart splitter ───
    text = _smart_split_all_long_words(text, min_len=12)

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
                "[vision.pollinations] Prompt optimisé : %s", final_prompt[:120]
            )
        except Exception as e:
            logger.warning(
                "[vision.pollinations] Optimisation prompt échouée : %s", e
            )

    # ─── Normalisation ───
    final_prompt = _normalize_prompt_spacing(final_prompt)
    logger.info(
        "[vision.pollinations] Prompt normalisé : %s", final_prompt[:180]
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
            return {"status": "error", "message": "Timeout Pollinations."}
        except requests.RequestException as e:
            return {"status": "error", "message": f"Erreur réseau : {e}"}

        if res.status_code == 402:
            logger.warning("[vision.pollinations] HTTP 402 — retry")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return {"status": "error", "message": "HTTP 402 rate limit."}

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
                "[vision.pollinations] HTTP %s — retry", res.status_code
            )
            time.sleep(2)
            continue

        return {
            "status": "error",
            "message": f"Pollinations HTTP {res.status_code}.",
        }

    return {"status": "error", "message": "Échec après plusieurs tentatives."}


# ==============================================================================
# LISTE DES MODÈLES
# ==============================================================================
def list_pollinations_models() -> list:
    return list(POLLINATIONS_MODELS.keys())