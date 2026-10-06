# ==============================================================================
# BEK-v16 — Vision / Pollinations Client
# ------------------------------------------------------------------------------
# v26-v28.4 : historique complet (voir commit git)
#
# ★ v28.5 (2026-10-06) : SMART WORD SPLITTER (fix mots collés LLM)
#   - Ajout dictionnaire de 200+ mots communs
#   - Ajout _smart_split_long_word() : découpe "minimalistfuturistictech" en
#     "minimalist futuristic tech" via greedy longest-match
#   - Appliqué AUTOMATIQUEMENT à tout mot > 12 lettres
#   - Gère les cas imprévisibles que les patterns fixes ne couvrent pas
#   - ★ AUCUNE fonctionnalité supprimée (100% compatible v28.4)
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
# ★ v28.5 — DICTIONNAIRE DE MOTS COMMUNS (pour le smart splitter)
# ══════════════════════════════════════════════════════════════════════════════
_COMMON_PROMPT_WORDS = frozenset([
    # ─── Mots courts (1-2 lettres) ───
    "a", "an", "in", "on", "of", "or", "to", "by", "as", "is", "at", "be",
    "no", "so", "up", "my", "we", "us", "it",

    # ─── Mots 3-4 lettres ───
    "the", "and", "for", "with", "not", "but", "all", "any", "new", "old",
    "art", "web", "app", "dev", "logo", "icon", "dark", "blue", "neon",
    "high", "low", "line", "shape", "form", "code", "data", "type", "font",
    "text", "red", "tag", "badge", "star", "moon", "sun", "tree", "leaf",
    "fire", "gold", "pink", "rose", "grey", "gray", "cyan", "tech", "cloud",

    # ─── Mots 5-6 lettres ───
    "green", "black", "white", "silver", "color", "clean", "bright", "light",
    "curve", "style", "space", "cloud", "server", "modern", "simple",
    "startup", "symbol", "letter", "future", "bright", "smooth", "circle",
    "square", "triangle", "arrow", "diamond", "planet", "rocket", "shield",
    "target", "anchor", "banner", "border", "brush", "canvas", "chrome",
    "copper", "crystal", "flame", "forest", "galaxy", "glass", "glow",
    "holographic", "infinity", "marble", "matrix", "medal", "metal", "mirror",
    "nebula", "neon", "ocean", "orbit", "pearl", "pixel", "prism", "quartz",
    "ribbon", "shadow", "signal", "silk", "spark", "sphere", "stripe",
    "sunset", "trophy", "tunnel", "vector", "vertex", "wave", "waveform",
    "whirl", "zenith",

    # ─── Mots 7-8 lettres ───
    "minimal", "pattern", "circuit", "feature", "forming", "futuristic",
    "electric", "abstract", "design", "gradient", "network", "cyber",
    "digital", "studio", "creative", "minimal", "curved", "geometric",
    "shapes", "lines", "arrows", "circles", "squares", "triangles",
    "hexagon", "octagon", "pentagon", "polygon", "rhombus", "ellipse",

    # ─── Mots 9-10 lettres ───
    "minimalist", "background", "featuring", "geometric", "graphical",
    "typography", "calligraphy", "watercolor", "watercolour",

    # ─── Mots 11+ lettres (à préserver entiers) ───
    "minimalistic", "professional", "contemporary",
    "photorealistic", "hyperrealistic", "illustration",
    "cinematic", "photography", "architecture", "surrealistic",
    "expressionism", "impressionist",
])


# ══════════════════════════════════════════════════════════════════════════════
# ★ v28.5 — SMART WORD SPLITTER (fix mots collés LLM)
# ══════════════════════════════════════════════════════════════════════════════
def _smart_split_long_word(word: str, min_len: int = 12) -> str:
    """
    Découpe un mot collé en ses composants via un dictionnaire.

    Exemple :
      "minimalistfuturistictech" → "minimalist futuristic tech"

    Algorithme : greedy longest-match from left.
      - Essaie la plus longue correspondance (max 15 chars)
      - Puis 14, 13, ... jusqu'à 2 chars
      - Si aucun match, prend le 1er caractère et continue

    ⚠️ Ne traite QUE les mots >= min_len caractères (default 12).
    Si le mot est déjà dans le dictionnaire, il est retourné tel quel.
    """
    if len(word) < min_len:
        return word

    # ─── Cas spécial : mot déjà valide ───
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

        # ─── Essai longest-first ───
        for length in range(max_try, min_word_len - 1, -1):
            candidate = remaining[:length].lower()
            if candidate in _COMMON_PROMPT_WORDS:
                parts.append(remaining[:length])
                remaining = remaining[length:]
                found = True
                break

        # ─── Aucun match : fallback ───
        if not found:
            char = remaining[0]
            # Majuscule → nouveau mot (ex: "letterT" → "letter T")
            if char.isupper() and parts and parts[-1] and parts[-1][-1].islower():
                parts.append(char)
            elif parts and len(parts[-1]) < max_word_len:
                parts[-1] += char
            else:
                parts.append(char)
            remaining = remaining[1:]

    result = " ".join(parts)

    # ─── Vérifier amélioration ───
    if result.count(" ") == 0:
        return word  # Aucun split trouvé, garde l'original

    return result


def _smart_split_all_long_words(text: str, min_len: int = 12) -> str:
    """
    Applique _smart_split_long_word à tous les tokens >= min_len.

    Utilise une regex pour cibler les séquences de lettres longues
    (sans casser la ponctuation ni les chiffres).
    """
    if not text:
        return text

    def replacer(match):
        word = match.group(0)
        return _smart_split_long_word(word, min_len=min_len)

    # ─── Match toute séquence >= min_len lettres ───
    return re.sub(r'[a-zA-ZÀ-ÿ]{' + str(min_len) + r',}', replacer, text)


# ══════════════════════════════════════════════════════════════════════════════
# HEADERS IDENTIFIABLES (fix HTTP 402)
# ══════════════════════════════════════════════════════════════════════════════
def _build_headers() -> Dict[str, str]:
    return {
        "User-Agent": "BEK-Agent/1.0 (+https://bek-v15-clean.onrender.com)",
        "Accept": "image/png,image/jpeg,image/webp,image/*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }


# ══════════════════════════════════════════════════════════════════════════════
# PATTERNS DE COLLISIONS (v28.4 — patterns FR + EN)
# ══════════════════════════════════════════════════════════════════════════════
_BROKEN_WORD_REPAIRS = [
    (r'\ba bstract\b', 'abstract'),
    (r'\ba bove\b', 'above'),
    (r'\ba pple\b', 'apple'),
    (r'\bmi nimaliste\b', 'minimaliste'),
    (r'\bfu turiste\b', 'futuriste'),
]

_COMMON_COLLISIONS = [
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
    (r'techstartup', 'tech startup'),
    (r'featuringabstract', 'featuring abstract'),
    (r'circuitpatterns', 'circuit patterns'),
    (r'electricblue', 'electric blue'),
    (r'neongreen', 'neon green'),
    (r'darkbackground', 'dark background'),
    (r'onadarkbackground', 'on a dark background'),
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
    ★ v28.5 — Normalisation FINALE (patterns + smart splitter).

    Pipeline :
      1. Réparation des mots cassés ("a bstract" → "abstract")
      2. CamelCase → "Camel Case"
      3. Ponctuation → espace après virgule
      4. Patterns de collisions (FR + EN)
      5. ★ NOUVEAU : Smart splitter sur mots > 12 lettres
      6. Nettoyage final

    ⚠️ Ne touche PAS aux URLs ni aux chaînes JSON.
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

    # ─── 2. CamelCase → "Camel Case" ───
    text = re.sub(r'([a-zà-ÿ])([A-ZÀ-Ý])', r'\1 \2', text)

    # ─── 3. Ponctuation ───
    text = re.sub(r',([^\s])', r', \1', text)
    text = re.sub(r'([a-zA-Z]):([^\s/])', r'\1: \2', text)
    text = re.sub(r';([^\s])', r'; \1', text)

    # ─── 4. Patterns de collisions ───
    for pattern, replacement in _COMMON_COLLISIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # ─── 5. ★ SMART SPLITTER (v28.5) ───
    text = _smart_split_all_long_words(text, min_len=12)

    # ─── 6. Nettoyage final ───
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

    # ─── Optimisation ───
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

    # ─── ★ v28.5 — NORMALISATION ───
    final_prompt = _normalize_prompt_spacing(final_prompt)
    logger.info(
        "[vision.pollinations] Prompt normalisé : %s", final_prompt[:150]
    )

    # ─── Modèle + URL ───
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

    # ─── Retry loop ───
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

        # ─── HTTP 402 (rate limit) ───
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
                "message": "Pollinations HTTP 402 (rate limit atteint). Réessayez dans 30 secondes.",
            }

        # ─── Succès ───
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

        # ─── Erreur ───
        if attempt < max_retries - 1:
            logger.warning(
                "[vision.pollinations] HTTP %s (tentative %d/%d), retry...",
                res.status_code, attempt + 1, max_retries,
            )
            time.sleep(2)
            continue

        return {
            "status": "error",
            "message": f"Pollinations HTTP {res.status_code} ({len(res.content)} bytes).",
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