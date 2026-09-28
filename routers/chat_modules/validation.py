# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Validation
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Helpers de validation (URLs, traductions, troncature, mots-clés)
# 📄 Doc : docs/BEK_LVC.md
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-24
# ==============================================================================

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from . import config as cfg

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# FILTRE URLs STÉRILES
# ══════════════════════════════════════════════════════════════════════════════

_STERILE_URL_PATTERNS = (
    # Moteurs de recherche
    r"google\.com/finance\?sa=X",
    r"google\.com/search\?",
    r"bing\.com/search\?",
    r"duckduckgo\.com/\?q=",
    r"duckduckgo\.com/html/\?q=",
    # Login / auth
    r"accounts\.google\.com",
    r"login\.microsoftonline\.com",
    r"signin\.",
    r"/signin",
    r"/login",
    r"/auth/",
    r"auth0\.com",
    r"okta\.com",
    # Homes de portails
    r"^https?://(fr\.)?news\.yahoo\.com/?$",
    r"^https?://(www\.)?yahoo\.com/?$",
    r"^https?://(www\.)?yahoo\.fr/?$",
    r"^https?://news\.google\.com/?",
    r"^https?://(www\.)?msn\.com/?$",
    r"^https?://(www\.)?bing\.com/?$",
    r"^https?://(www\.)?google\.[a-z]{2,3}/?$",
)
_STERILE_URL_REGEX = re.compile("|".join(_STERILE_URL_PATTERNS), re.IGNORECASE)


def _is_sterile_url(url: str) -> bool:
    """
    Vrai si l'URL est une home/login/recherche générique sans contenu éditorial.

    Rejette :
      - https://fr.news.yahoo.com/         (home portail)
      - https://www.google.com/            (home moteur)
      - https://site.com/login             (login)
      - https://site.com/                  (aucun path)
    """
    if not url:
        return False

    try:
        from urllib.parse import urlparse as _up
        p = _up(url)
        path = (p.path or "").strip("/")
        if not path or path in ("index.html", "index.htm", "index.php", "home"):
            return True
    except Exception:
        pass

    return bool(_STERILE_URL_REGEX.search(url))


# ══════════════════════════════════════════════════════════════════════════════
# STOPWORDS POUR EXTRACTION DE MOTS-CLÉS
# ══════════════════════════════════════════════════════════════════════════════

_QUERY_STOPWORDS = {
    "cherche", "chercher", "recherche", "rechercher", "trouve", "trouver",
    "donne", "donner", "montre", "montrer", "résume", "résumer",
    "les", "le", "la", "un", "une", "des", "du", "de", "d",
    "et", "ou", "en", "au", "aux", "ce", "cette", "ces", "cet",
    "sur", "sous", "dans", "par", "pour", "avec", "sans",
    "dernières", "dernière", "dernier", "derniers",
    "chacune", "chacun", "chaque", "phrases", "phrase",
    "actualité", "actualités",
    "à", "a", "y", "ne", "pas", "plus", "que", "qui", "quoi",
    "est", "sont", "été", "être",
    "the", "of", "to", "in", "on", "at", "by", "for",
    "is", "are", "was", "were", "be", "been",
    "it", "its", "as", "or", "and", "but", "if", "so", "no",
    "do", "does", "did", "has", "have", "had", "this", "that",
    "with", "from", "will", "would", "can", "could", "should",
    "search", "find", "get", "give", "show", "summarize",
    "latest", "recent", "top", "best",
    "5", "10", "3", "2", "1",
}


def _extract_keywords(query: str, max_words: int = None) -> str:
    """Extrait les mots-clés d'une requête."""
    if max_words is None:
        max_words = cfg.MAX_QUERY_WORDS

    if not query or not query.strip():
        return query

    words = query.strip().split()
    if len(words) <= max_words:
        return query

    keywords = []
    for w in words:
        w_clean = re.sub(r"[^\w]", "", w.lower())
        if w_clean and w_clean not in _QUERY_STOPWORDS:
            keywords.append(w)

    if not keywords:
        return " ".join(words[:max_words])

    result = " ".join(keywords[:max_words])
    logger.info("[KeywordExtract] '%s' → '%s'", query[:80], result[:80])
    return result


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION TRADUCTION FR → EN
# ══════════════════════════════════════════════════════════════════════════════

_EN_MARKERS = {
    "latest", "news", "price", "current", "how", "what", "the",
    "today", "info", "update", "trending", "recent",
}
_FR_MARKERS = {
    "actualité", "actualités", "prix", "actuel", "actuelle", "aujourd",
    "comment", "quoi", "quel", "quelle", "dernières", "dernière",
    "nouvelles", "nouveaux", "récent", "récente",
}


def _is_translation(original_query: str, sent_query: str) -> bool:
    """Vrai si la requête envoyée est une traduction de l'originale."""
    if not original_query or not sent_query:
        return False

    o_lower = original_query.lower()
    s_lower = sent_query.lower()

    o_fr = sum(1 for m in _FR_MARKERS if m in o_lower)
    s_en = sum(1 for m in _EN_MARKERS if m in s_lower)
    s_fr = sum(1 for m in _FR_MARKERS if m in s_lower)

    return o_fr >= 1 and s_en >= 2 and s_fr == 0


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS STRING
# ══════════════════════════════════════════════════════════════════════════════

def _safe_str(value: Any) -> str:
    """Convertit une valeur en string de manière safe."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    try:
        return str(value)
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# TRONCATURE DE MESSAGES
# ══════════════════════════════════════════════════════════════════════════════

def _truncate_messages(
    messages: List[Dict[str, Any]],
    window: int = None,
    max_per_msg: int = None,
    max_total: int = None,
) -> List[Dict[str, Any]]:
    """Tronque l'historique des messages."""
    if window is None:
        window = cfg.HISTORY_WINDOW
    if max_per_msg is None:
        max_per_msg = cfg.MAX_CHARS_PER_MESSAGE
    if max_total is None:
        max_total = cfg.MAX_TOTAL_CHARS

    if not messages or not isinstance(messages, list):
        return []

    recent = [m for m in messages[-window:] if isinstance(m, dict)]

    normalized: List[Dict[str, Any]] = []
    for m in recent:
        role = _safe_str(m.get("role", "user"))[:32] or "user"
        content = _safe_str(m.get("content", ""))
        if len(content) > max_per_msg:
            content = content[:max_per_msg] + "\n…[tronqué]"
        normalized.append({"role": role, "content": content})

    total = sum(len(m["content"]) for m in normalized)
    if total > max_total:
        overflow = total - max_total
        for m in normalized:
            if overflow <= 0:
                break
            content_len = len(m["content"])
            if content_len <= overflow:
                overflow -= content_len
                m["content"] = "[…contenu ancien tronqué…]"
            else:
                m["content"] = "[…tronqué…] " + m["content"][overflow:]
                overflow = 0

    return normalized


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION RÉPONSE UTILISATEUR (OUI/NON)
# ══════════════════════════════════════════════════════════════════════════════

def _detect_user_response(query: str) -> str:
    """Détecte si l'utilisateur a dit oui, non, ou autre chose."""
    if not query:
        return "neutral"

    q = query.lower().strip()
    agreed = {
        "oui", "yes", "ok", "okay", "vasy", "vas-y",
        "go", "d'accord", "ouais", "y", "o", "fine",
    }
    refused = {"non", "no", "stop", "annule", "cancel", "jamais"}

    words = set(re.findall(r"\b\w+\b", q))

    if words & agreed and not (words & refused):
        return "agreed"
    if words & refused:
        return "refused"
    return "neutral"


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ══════════════════════════════════════════════════════════════════════════════

def get_validation_summary() -> dict:
    """Résumé des validateurs disponibles."""
    return {
        "sterile_patterns_count": len(_STERILE_URL_PATTERNS),
        "stopwords_count": len(_QUERY_STOPWORDS),
        "en_markers": len(_EN_MARKERS),
        "fr_markers": len(_FR_MARKERS),
        "functions": [
            "_is_sterile_url",
            "_extract_keywords",
            "_is_translation",
            "_safe_str",
            "_truncate_messages",
            "_detect_user_response",
        ],
    }