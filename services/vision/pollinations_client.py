# ==============================================================================
# BEK-v16 — Vision / Pollinations Client (v28.9)
# ------------------------------------------------------------------------------
# ★ v28.9 (2026-10-06) : FIX HTTP 402/500 (rate limit Pollinations)
#   - 5 retries (au lieu de 3) avec backoff exponentiel (2→32s)
#   - Rotation User-Agent
#   - Rotation endpoints (image.pollinations.ai + pollinations.ai/p)
#   - Timeout 180s (au lieu de 120s)
#   - Logs détaillés pour diagnostic
# ==============================================================================
from __future__ import annotations

import logging
import os
import random
import re
import time
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional

import requests
from werkzeug.utils import secure_filename

from core.paths import GENERATED_DIR
from services.prompt_optimizer import optimize_prompt_for_media

logger = logging.getLogger("bek.vision.pollinations")


POLLINATIONS_MODELS: Dict[str, str] = {
    "flux":         "flux",
    "flux-3d":      "flux-3d",
    "flux-realism": "flux-realism",
    "flux-anime":   "flux-anime",
    "any-dark":     "any-dark",
    "turbo":        "turbo",
}

# ★ v28.9 — Endpoints alternatifs (rotation si l'un échoue)
POLLINATIONS_ENDPOINTS: List[str] = [
    "https://image.pollinations.ai/prompt",
    "https://pollinations.ai/p",              # Endpoint alternatif
]

# ★ v28.9 — User-Agents variés (rotation)
_USER_AGENTS: List[str] = [
    "BEK-Agent/1.0 (+https://bek-v15-clean.onrender.com)",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


# ══════════════════════════════════════════════════════════════════════════════
# DICTIONNAIRE POUR LE SMART SPLITTER
# ══════════════════════════════════════════════════════════════════════════════
_COMMON_PROMPT_WORDS = frozenset([
    "a", "an", "in", "on", "of", "or", "to", "by", "as", "is", "at", "be",
    "no", "so", "up", "my", "we", "us", "it", "if", "do", "go", "ai", "ia",
    "the", "and", "for", "with", "not", "but", "all", "any", "new", "old",
    "art", "web", "app", "dev", "logo", "icon", "dark", "blue", "neon",
    "high", "low", "line", "lines", "shape", "shapes", "form", "forms",
    "code", "data", "type", "font", "text", "red", "tag", "badge", "star",
    "moon", "sun", "tree", "leaf", "fire", "gold", "pink", "rose", "grey",
    "gray", "cyan", "tech", "cloud", "wave", "edge", "edges", "tone", "mode",
    "soft", "hard", "flat", "fine", "pure", "true", "bold", "cool", "warm",
    "green", "black", "white", "silver", "color", "colors", "colour", "colours",
    "clean", "bright", "light", "curve", "curves", "style", "space",
    "server", "modern", "simple", "smooth", "circle", "circles", "square",
    "squares", "symbol", "letter", "letters", "future", "sharp", "round",
    "arrow", "arrows", "glow", "shine", "crisp", "focus", "depth", "pixel",
    "pixels", "spark", "sparks", "startup", "startups", "launch", "brand",
    "brands", "theme", "themes", "waves", "dots", "rings", "cross", "crosses",
    "pluses", "minus", "minimal", "pattern", "patterns", "circuit", "circuits",
    "feature", "features", "forming", "electric", "abstract", "design",
    "designs", "gradient", "gradients", "network", "networks", "cyber",
    "digital", "studio", "creative", "curved", "geometric", "triangles",
    "hexagon", "octagon", "pentagon", "polygon", "rhombus", "ellipse",
    "vectors", "futuristic", "american", "european", "silicon", "quantum",
    "optical", "capital", "segment", "section", "sectors", "minimalist",
    "background", "backgrounds", "featuring", "graphical", "typography",
    "calligraphy", "watercolor", "watercolour", "landscape", "character",
    "characters", "identity", "identities", "minimalistic", "professional",
    "contemporary", "photorealistic", "hyperrealistic", "illustration",
    "illustrations", "cinematic", "photography", "architecture",
    "surrealistic", "expressionism", "impressionist", "configurable",
    "configuration",
])


# ══════════════════════════════════════════════════════════════════════════════
# SMART WORD SPLITTER
# ══════════════════════════════════════════════════════════════════════════════
def _smart_split_long_word(word: str, min_len: int = 12) -> str:
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
    if not text:
        return text

    def replacer(match):
        return _smart_split_long_word(match.group(0), min_len=min_len)

    return re.sub(r'[a-zA-ZÀ-ÿ]{' + str(min_len) + r',}', replacer, text)


# ══════════════════════════════════════════════════════════════════════════════
# HEADERS avec rotation User-Agent (v28.9)
# ══════════════════════════════════════════════════════════════════════════════
def _build_headers(attempt: int = 0) -> Dict[str, str]:
    """Construit les headers avec rotation User-Agent."""
    return {
        "User-Agent": _USER_AGENTS[attempt % len(_USER_AGENTS)],
        "Accept": "image/png,image/jpeg,image/webp,image/*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }


# ══════════════════════════════════════════════════════════════════════════════
# PATTERNS DE RÉPARATION
# ══════════════════════════════════════════════════════════════════════════════
_BROKEN_WORD_REPAIRS = [
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
    (r'andgreen', 'and green'),
    (r'andblue', 'and blue'),
    (r'andred', 'and red'),
    (r'andblack', 'and black'),
    (r'andwhite', 'and white'),
    (r'anddark', 'and dark'),
    (r'andlight', 'and light'),
    (r'andneon', 'and neon'),
    (r'andbright', 'and bright'),
    (r'andclean', 'and clean'),
    (r'\bfora\b', 'for a'),
    (r'\bforan\b', 'for an'),
    (r'forai', 'for AI'),
    (r'foria', 'for IA'),
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
    (r'minimalistlogo', 'minimalist logo'),
    (r'logofora', 'logo for a'),
    (r'logowith', 'logo with'),
    (r'logofor', 'logo for'),
    (r'techstartup', 'tech startup'),
    (r'aistartup', 'AI startup'),
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
    (r'endétail', 'en détail'),
    (r'endetail', 'en detail'),
    (r'vueensemble', 'vue ensemble'),
]


def _normalize_prompt_spacing(prompt: str) -> str:
    if not prompt or not isinstance(prompt, str):
        return prompt
    if prompt.startswith(("http://", "https://", "/", "./")):
        return prompt
    if prompt.startswith("{") and prompt.endswith("}"):
        return prompt

    text = prompt.strip()

    for pattern, replacement in _BROKEN_WORD_REPAIRS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r'([A-ZÀ-Ý]{2,})([a-zà-ÿ])', r'\1 \2', text)
    text = re.sub(r'([a-zà-ÿ])([A-ZÀ-Ý])', r'\1 \2', text)
    text = re.sub(r',([^\s])', r', \1', text)
    text = re.sub(r'([a-zA-Z]):([^\s/])', r'\1: \2', text)
    text = re.sub(r';([^\s])', r'; \1', text)

    for pattern, replacement in _COMMON_COLLISIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = _smart_split_all_long_words(text, min_len=12)

    # Post-traitements v28.8
    text = re.sub(r'\b([A-Z]) ([A-Z])\b', r'\1\2', text)
    text = re.sub(r'\ba nd(\w+)', r'and \1', text)
    text = re.sub(r'\ba nd\b', 'and', text)
    text = re.sub(r'\bo r\b', 'or', text)
    text = re.sub(r'\bi n\b', 'in', text)
    text = re.sub(r'\ba s\b', 'as', text)
    text = re.sub(r'\ba t\b', 'at', text)
    text = re.sub(r'\bt o\b', 'to', text)
    text = re.sub(r'\bb y\b', 'by', text)
    text = re.sub(r'\bw ith\b', 'with', text)
    text = re.sub(r'\bf or\b', 'for', text)
    text = re.sub(r'\bf rom\b', 'from', text)
    text = re.sub(r'\bmi nimalist\b', 'minimalist', text)
    text = re.sub(r'\bmi nimal\b', 'minimal', text)
    text = re.sub(r'\bfu turistic\b', 'futuristic', text)
    text = re.sub(r'\bmi nimalistic\b', 'minimalistic', text)

    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s+([,;:.!?])', r'\1', text)

    return text


# ==============================================================================
# GÉNÉRATION D'IMAGE (v28.9 — 5 retries + rotation endpoints)
# ==============================================================================
def generate_image_with_pollinations(
    prompt: str,
    model: str = "flux",
    output_filename: str = "",
    width: int = 1024,
    height: int = 1024,
    seed: Optional[int] = None,
    enhance: bool = False,
    nologo: bool = True,
    private: bool = True,
    optimize_prompt: bool = True,
) -> Dict[str, Any]:
    """
    Génère une image via Pollinations.ai.

    ★ v28.9 — 5 retries avec backoff exponentiel + rotation endpoints/UA.
    """
    if not output_filename:
        output_filename = f"pollinations_{uuid.uuid4().hex[:8]}.png"
    save_path = os.path.abspath(
        os.path.join(GENERATED_DIR, secure_filename(output_filename))
    )

    # ─── Optimisation + normalisation ───
    final_prompt = prompt
    if optimize_prompt:
        try:
            final_prompt = optimize_prompt_for_media(
                prompt, media_type="image", style_preset="auto",
            )
            logger.info(
                "[vision.pollinations] Prompt optimisé : %s", final_prompt[:120]
            )
        except Exception as e:
            logger.warning(
                "[vision.pollinations] Optimisation prompt échouée : %s", e
            )

    final_prompt = _normalize_prompt_spacing(final_prompt)
    logger.info(
        "[vision.pollinations] Prompt normalisé : %s", final_prompt[:180]
    )

    # ─── Préparer les params ───
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

    # ══════════════════════════════════════════════════════════════════════
    # ★ v28.9 — 5 retries avec backoff exponentiel + rotation endpoints
    # ══════════════════════════════════════════════════════════════════════
    max_retries = 5
    last_error = "unknown"

    for attempt in range(max_retries):
        # Rotation endpoint
        base_url = POLLINATIONS_ENDPOINTS[attempt % len(POLLINATIONS_ENDPOINTS)]
        url = f"{base_url}/{encoded_prompt}?{query_string}"

        # Rotation User-Agent
        headers = _build_headers(attempt)

        # Backoff exponentiel : 0s, 2s, 4s, 8s, 16s (avant tentative)
        if attempt > 0:
            backoff = min(2 ** attempt, 32)
            logger.info(
                "[vision.pollinations] Attente backoff %ds avant retry %d/%d",
                backoff, attempt + 1, max_retries,
            )
            time.sleep(backoff)

        logger.info(
            "[vision.pollinations] generate : model=%s size=%dx%d "
            "enhance=%s endpoint=%s attempt=%d/%d prompt=%r",
            model_id, width, height, enhance,
            base_url.split("//")[1].split("/")[0],
            attempt + 1, max_retries,
            final_prompt[:80],
        )

        try:
            res = requests.get(url, headers=headers, timeout=180)
        except requests.Timeout:
            last_error = "Timeout"
            logger.warning(
                "[vision.pollinations] Timeout (tentative %d/%d)",
                attempt + 1, max_retries,
            )
            continue
        except requests.RequestException as e:
            last_error = f"Réseau : {e}"
            logger.warning(
                "[vision.pollinations] Erreur réseau (tentative %d/%d) : %s",
                attempt + 1, max_retries, e,
            )
            continue

        # ─── HTTP 200 + contenu valide ───
        if res.status_code == 200 and len(res.content) > 1000:
            with open(save_path, "wb") as f:
                f.write(res.content)
            logger.info(
                "[vision.pollinations] OK : %s (%d bytes) en %d tentative(s)",
                output_filename, len(res.content), attempt + 1,
            )
            return {
                "status": "success",
                "filepath": save_path,
                "filename": output_filename,
                "model_id": model_id,
                "provider": "pollinations",
                "size_bytes": len(res.content),
                "attempts": attempt + 1,
                "url": url,
            }

        # ─── HTTP 402 (rate limit) ───
        if res.status_code == 402:
            last_error = "HTTP 402 (rate limit)"
            logger.warning(
                "[vision.pollinations] HTTP 402 rate limit (tentative %d/%d)",
                attempt + 1, max_retries,
            )
            continue

        # ─── HTTP 500 (server error) ───
        if res.status_code >= 500:
            last_error = f"HTTP {res.status_code} (server error)"
            logger.warning(
                "[vision.pollinations] HTTP %s server error (tentative %d/%d)",
                res.status_code, attempt + 1, max_retries,
            )
            continue

        # ─── Autres erreurs ───
        last_error = f"HTTP {res.status_code}"
        logger.warning(
            "[vision.pollinations] HTTP %s (tentative %d/%d) : %s",
            res.status_code, attempt + 1, max_retries, res.text[:200],
        )

    # ─── Échec final ───
    logger.error(
        "[vision.pollinations] Échec après %d tentatives. Dernière erreur : %s",
        max_retries, last_error,
    )
    return {
        "status": "error",
        "message": (
            f"Pollinations indisponible après {max_retries} tentatives "
            f"({last_error}). Réessayez dans 1 minute."
        ),
    }


# ==============================================================================
# LISTE DES MODÈLES
# ==============================================================================
def list_pollinations_models() -> list:
    return list(POLLINATIONS_MODELS.keys())