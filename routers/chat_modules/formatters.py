# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Formatters
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Formatage des résultats d'action pour le LLM
# 📄 Doc : docs/BEK_LVC.md
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.4
# Date : 2026-11-08
# ------------------------------------------------------------------------------
# ★ v1.4 — FIX web_sync : nettoyage + formatage Markdown propre des sources
# ★ v1.3 — Log amélioré : affiche TOUTES les clés disponibles si rien trouvé
# ★ v1.2 — Compteur de sources + avertissement si < 3 sources
# ★ v1.1 — FIX web_sync : cherche le contenu dans plusieurs clés possibles
# ==============================================================================

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from . import config as cfg

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION RÉSULTAT PAUVRE
# ══════════════════════════════════════════════════════════════════════════════

def _is_poor_result(exec_res: Optional[dict], act_name: str) -> bool:
    """Détecte si un résultat est "pauvre" (nécessite un fallback)."""
    if not isinstance(exec_res, dict):
        return True
    if exec_res.get("status") != "success":
        return True

    if act_name == "headless_search":
        leads = exec_res.get("leads", []) or []
        return len(leads) == 0

    if act_name == "headless_scrape":
        html = exec_res.get("html", "") or ""
        return len(html) < cfg.POOR_RESULT_THRESHOLD

    if act_name == "web_sync":
        content = _extract_web_sync_content(exec_res)
        return len(content) < cfg.POOR_RESULT_THRESHOLD

    return False


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION TOLÉRANTE DU CONTENU WEB_SYNC
# ══════════════════════════════════════════════════════════════════════════════

_WEB_SYNC_CONTENT_KEYS = (
    "report", "synthesis", "summary", "content",
    "result", "text", "message", "data", "answer", "response", "output",
    "web_report", "final_report", "final_answer", "analysis",
    "synthesized_report", "web_synthesis",
)


def _extract_web_sync_content(exec_res: dict) -> str:
    """Extrait le contenu exploitable d'un résultat web_sync."""
    if not isinstance(exec_res, dict):
        return ""

    best_content = ""
    best_key = ""

    # 1. Chercher dans les clés connues
    for key in _WEB_SYNC_CONTENT_KEYS:
        val = exec_res.get(key)
        if val is None:
            continue
        val_str = str(val).strip()
        if len(val_str) > len(best_content):
            best_content = val_str
            best_key = key

    # 2. Fallback : chercher dans TOUTES les valeurs
    if not best_content or len(best_content) < 100:
        for key, val in exec_res.items():
            if val is None:
                continue
            # Ignorer les clés de métadonnées
            if key in ("status", "error", "error_type", "duration_ms", "elapsed"):
                continue
            val_str = str(val).strip()
            if len(val_str) > len(best_content):
                best_content = val_str
                best_key = key

    if best_content:
        logger.info(
            "[Formatter web_sync] Contenu extrait : clé=%r | %d chars",
            best_key, len(best_content),
        )
    else:
        logger.warning(
            "[Formatter web_sync] Aucun contenu trouvé. "
            "Clés disponibles : %s | Types : %s",
            list(exec_res.keys()),
            {k: type(v).__name__ for k, v in exec_res.items()},
        )

    return best_content


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSE DES SOURCES
# ══════════════════════════════════════════════════════════════════════════════

# Regex pour détecter les URLs dans le rapport web_sync
_URL_REGEX = re.compile(r"<(https?://[^\s>]+)>", re.IGNORECASE)
_URL_RAW_REGEX = re.compile(r"https?://[^\s\)\]\>]+", re.IGNORECASE)

# Mots-clés de fraîcheur
_FRESHNESS_KEYWORDS = (
    "aujourd'hui", "aujourd", "récent", "récente",
    "2026", "2025", "ce matin", "cette semaine",
    "il y a", "dernière", "dernier", "actuel",
)

# Seuil minimum de sources recommandé
_MIN_SOURCES_RECOMMENDED = 3


def _extract_sources_from_report(report_str: str) -> List[Tuple[str, str]]:
    """Extrait les URLs et leurs descriptions depuis le rapport web_sync."""
    if not report_str:
        return []

    sources: List[Tuple[str, str]] = []

    # Chercher les URLs au format <https://...>
    for match in _URL_REGEX.finditer(report_str):
        url = match.group(1).strip()
        start = max(0, match.start() - 100)
        end = min(len(report_str), match.end() + 200)
        context = report_str[start:end].replace("\n", " ").strip()
        sources.append((url, context))

    # Fallback : chercher les URLs brutes
    if not sources:
        for match in _URL_RAW_REGEX.finditer(report_str):
            url = match.group(0).strip()
            start = max(0, match.start() - 100)
            end = min(len(report_str), match.end() + 200)
            context = report_str[start:end].replace("\n", " ").strip()
            sources.append((url, context))

    # Dédupliquer par URL
    seen = set()
    unique_sources = []
    for url, desc in sources:
        if url not in seen:
            seen.add(url)
            unique_sources.append((url, desc))

    return unique_sources


def _has_freshness_indicators(text: str) -> bool:
    """Détecte si le texte contient des indicateurs de fraîcheur."""
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in _FRESHNESS_KEYWORDS)


def _build_sources_warning(nb_sources: int, has_freshness: bool) -> str:
    """Construit un avertissement si le nombre de sources est faible."""
    if nb_sources >= _MIN_SOURCES_RECOMMENDED:
        return ""

    if nb_sources == 0:
        return (
            "\n\n⚠️ **Aucune source détectée dans le rapport.**\n"
            "Les informations peuvent être incomplètes.\n"
        )

    warning = (
        f"\n\n⚠️ **Peu de sources ({nb_sources})** — "
        f"recommandé : {_MIN_SOURCES_RECOMMENDED} minimum.\n"
    )
    if not has_freshness:
        warning += "⚠️ **Aucun indicateur de fraîcheur détecté.**\n"

    return warning


def _build_sources_header(nb_sources: int, has_freshness: bool) -> str:
    """Construit l'en-tête avec le compteur de sources."""
    freshness_icon = "🟢" if has_freshness else "🟡"
    return (
        f"🌐 **Veille web approfondie** "
        f"({nb_sources} source{'s' if nb_sources != 1 else ''} analysée"
        f"{'s' if nb_sources != 1 else ''}) {freshness_icon}\n\n"
    )


# ══════════════════════════════════════════════════════════════════════════════
# ★ v1.4 — NETTOYAGE DU BRUIT HTML
# ══════════════════════════════════════════════════════════════════════════════

def _clean_snippet(text: str) -> str:
    """
    ★ v1.4 — Nettoie le bruit HTML/navigation des snippets web.
    Enlève : [Skip to content], [Reload], liens Markdown, URLs brutes.
    """
    if not text:
        return ""

    # 1. Enlever le bruit de navigation GitHub/Reddit
    noise_patterns = [
        r"\[?Skip to content\]?\([^)]*\)",
        r"You signed in with another tab or window\.?",
        r"\[?Reload\]?\([^)]*\) to refresh your session\.?",
        r"You signed out in another tab or window\.?",
        r"You switched accounts on another tab or window\.?",
        r"Dismiss alert \{\{ message \}\}",
        r"\[?\*\*\d+\*\* (Branches|Tags|Stars|Forks)\]?\([^)]*\)",
        r"\[?Go to (Branches|Tags|file|repository) page\]?\([^)]*\)",
        r"\[?Go to file\]?",
        r"\[?Code\]?",
        r"Open more actions menu",
        r"\[?Search or jump to\.?\.?\.?\]?",
        r"\[?Sign in\]?\([^)]*\)",
        r"\[?Sign up\]?\([^)]*\)",
    ]
    for pat in noise_patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)

    # 2. Nettoyer les liens Markdown [text](url) → garder juste text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # 3. Nettoyer les URLs brutes (sauf si c'est une source explicite)
    text = re.sub(r"https?://\S+", "", text)

    # 4. Enlever les caractères de contrôle
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 5. Normaliser les espaces
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text


# ══════════════════════════════════════════════════════════════════════════════
# FORMATAGE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def _format_execution_result(act_name: str, exec_res: dict) -> str:
    """Formate le résultat d'une action pour injection dans le prompt."""
    if not isinstance(exec_res, dict):
        return str(exec_res)

    fn = exec_res.get("filename", "")
    srt_fn = exec_res.get("srt_filename", "")

    if act_name == "generate_subtitles" and exec_res.get("status") == "success":
        return _format_subtitles(exec_res, srt_fn)

    if act_name == "burn_subtitles" and exec_res.get("status") == "success" and fn:
        return _format_burned_subtitles(exec_res, fn)

    if exec_res.get("status") == "success" and fn:
        if any(fn.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]):
            return f"🎨 **Image générée !**\n\n![{fn}](/api/download/{fn})"

        if any(fn.lower().endswith(ext) for ext in [".mp4", ".webm", ".mov", ".avi"]):
            return _format_video(exec_res, act_name, fn)

    if act_name == "headless_scrape":
        return _format_headless_scrape(exec_res)

    if act_name == "headless_search":
        return _format_headless_search(exec_res)

    if act_name == "web_sync":
        return _format_web_sync(exec_res)

    return exec_res.get("message", "Opération OK")


# ══════════════════════════════════════════════════════════════════════════════
# FORMATTERS SPÉCIALISÉS
# ══════════════════════════════════════════════════════════════════════════════

def _format_subtitles(exec_res: dict, srt_fn: str) -> str:
    language = exec_res.get("language", "?")
    segments = exec_res.get("segments_count", 0)
    text_preview = exec_res.get("text", "")[:300]
    return (
        f"🎤 **Sous-titres générés !**\n"
        f"- Langue détectée : `{language}`\n"
        f"- Segments : **{segments}**\n"
        f"- Fichier : `{srt_fn}`\n\n"
        f"**Aperçu :**\n```\n{text_preview}\n```\n\n"
        f"[📥 Télécharger le .srt](/api/download/{srt_fn})\n"
    )


def _format_burned_subtitles(exec_res: dict, fn: str) -> str:
    size_mb = exec_res.get("size_bytes", 0) / (1024 * 1024)
    return (
        f"🎬 **Vidéo sous-titrée !**\n"
        f"- Fichier : `{fn}`\n"
        f"- Taille : **{size_mb:.1f} Mo**\n\n"
        f"[📥 Télécharger la vidéo sous-titrée](/api/download/{fn})\n\n"
        f'<video controls loop src="/api/download/{fn}" '
        f'style="max-width:100%;border-radius:8px;"></video>'
    )


def _format_video(exec_res: dict, act_name: str, fn: str) -> str:
    duration = exec_res.get("actual_duration") or exec_res.get("duration") or ""
    provider = exec_res.get("provider", "")
    model = exec_res.get("model_id", "")
    with_audio = exec_res.get("with_audio", False)
    stitched = exec_res.get("stitched", False)
    clips = exec_res.get("clips", [])
    mode_used = exec_res.get("mode_used", "")
    extended_by = exec_res.get("extended_by")
    source_video = exec_res.get("source_video", "")

    is_extension = (
        bool(extended_by)
        or act_name in ("extend_video", "extend_video_multiple")
        or bool(mode_used and mode_used in ("keyframes", "multi_reference"))
    )

    if is_extension:
        info_lines = [f"🎬 **Vidéo étendue !**" + (f" (+{extended_by}s)" if extended_by else "")]
        if mode_used:
            info_lines.append(f"- Mode continuité : `{mode_used}`")
        if source_video:
            info_lines.append(f"- Source : `{source_video}`")
        if with_audio:
            info_lines.append(f"- Audio : ✅")
        if duration:
            info_lines.append(f"- Durée totale : **{duration}s**")
        if clips and len(clips) > 1:
            info_lines.append(f"- Multi : `{len(clips)}` clips")
    else:
        info_lines = [f"🎬 **Vidéo générée !**"]
        if duration:
            info_lines.append(f"- Durée : **{duration}s**")
        if provider:
            info_lines.append(f"- Provider : `{provider}`")
        if model:
            info_lines.append(f"- Modèle : `{model}`")
        if with_audio:
            info_lines.append(f"- Audio : ✅")
        if stitched and clips:
            info_lines.append(f"- Multi-clips : `{clips}`")

    info = "\n".join(info_lines)
    video_player = (
        f'\n\n<video controls autoplay loop muted '
        f'style="max-width:100%; border-radius:12px; '
        f'box-shadow:0 4px 20px rgba(0,0,0,0.3); margin:12px 0;">'
        f'<source src="/api/download/{fn}" type="video/mp4">'
        f'Votre navigateur ne supporte pas la vidéo HTML5.'
        f'</video>\n\n'
        f'[📥 Télécharger la vidéo](/api/download/{fn})\n'
    )
    return info + video_player


def _format_headless_scrape(exec_res: dict) -> str:
    if exec_res.get("status") != "success":
        return exec_res.get("message", "❌ headless_scrape a échoué")

    url = exec_res.get("url", "")
    title = exec_res.get("title", "")
    html = exec_res.get("html", "") or ""

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "meta", "link"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
    except ImportError:
        text = html

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    text = "\n".join(lines)
    preview = text[:4000]

    return (
        f"✅ **Scraping réussi** : {url}\n"
        f"- Titre : **{title}**\n"
        f"- Contenu extrait : {len(text)} chars\n\n"
        f"**Contenu textuel** :\n```\n{preview}\n```\n"
        f"→ Analyse ce contenu et donne à l'utilisateur ce qu'il a demandé."
    )


def _format_headless_search(exec_res: dict) -> str:
    if not isinstance(exec_res, dict):
        return f"Résultat brut : {exec_res}"

    if exec_res.get("status") != "success":
        return f"❌ headless_search a échoué : {exec_res.get('message', 'erreur inconnue')}"

    leads = exec_res.get("leads", []) or []
    query_used = exec_res.get("query", "")

    if not leads:
        return (
            f"ℹ️ Aucun résultat trouvé pour : **{query_used}**\n\n"
            f"→ Dis à l'utilisateur qu'aucun résultat pertinent n'a été "
            f"trouvé et propose de reformuler."
        )

    lines = [f"✅ **{len(leads)} résultats** pour « {query_used} » :\n"]
    for i, lead in enumerate(leads, 1):
        title = (lead.get("title") or "")[:100]
        url = lead.get("source_url") or ""
        snippet = (lead.get("snippet") or "")[:200]
        lines.append(f"**{i}. {title}**")
        lines.append(f"   → {url}")
        if snippet:
            lines.append(f"   {snippet}")
        lines.append("")
    lines.append(
        "→ Utilise ces résultats pour répondre à la demande. "
        "Cite les sources (URLs)."
    )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# ★ v1.4 — FORMAT WEB_SYNC PROPRE
# ══════════════════════════════════════════════════════════════════════════════

def _format_web_sync(exec_res: dict) -> str:
    """
    ★ v1.4 — Formate proprement le résultat de web_sync.
    - Extrait les sources structurées
    - Nettoie le bruit HTML
    - Formate en liste Markdown propre
    """
    if not isinstance(exec_res, dict):
        return f"Résultat brut : {exec_res}"

    if exec_res.get("status") != "success":
        return exec_res.get("message", "❌ web_sync a échoué")

    # 1. Extraire le contenu
    report_str = _extract_web_sync_content(exec_res)

    if not report_str or len(report_str) < 50:
        logger.warning(
            "[Formatter web_sync] Contenu insuffisant (%d chars). Clés : %s",
            len(report_str), list(exec_res.keys()),
        )
        return (
            "⚠️ **Veille web sans résultat exploitable**\n\n"
            "→ Aucune source n'a été trouvée. Reformule ta demande."
        )

    # 2. Nettoyer le contenu brut
    cleaned = _clean_snippet(report_str)

    if not cleaned or len(cleaned) < 50:
        return (
            "⚠️ **Veille web : contenu illisible**\n\n"
            "→ Le pipeline n'a pas pu extraire un contenu exploitable.\n"
            "→ Reformule ta demande."
        )

    # 3. Formater en Markdown propre
    return _format_sources_as_markdown(cleaned)


def _format_sources_as_markdown(text: str) -> str:
    """
    ★ v1.4 — Formate un texte nettoyé en Markdown structuré.
    - Détecte les patterns "Source N" ou "Titre :"
    - Crée des sections propres
    """
    lines = []

    # Chercher les sections "Source N" ou "Titre :"
    source_pattern = re.compile(
        r"(?:\[?Source\s+\d+\]?|Titre\s*:)\s*([^\n]+)",
        re.IGNORECASE,
    )

    sources_found = source_pattern.findall(text)

    if sources_found and len(sources_found) >= 1:
        lines.append("## 🌐 Sources trouvées\n")
        for i, src in enumerate(sources_found[:10], 1):
            src = src.strip()
            # Tronquer si trop long
            if len(src) > 200:
                src = src[:200].rsplit(" ", 1)[0] + "…"
            lines.append(f"### {i}. {src}\n")
    else:
        # Fallback : juste formater le texte en paragraphes
        lines.append("## 🌐 Résultat de la veille web\n")

        # Découper en paragraphes de max 500 chars
        paragraphs = text.split("\n\n")
        for para in paragraphs[:15]:
            para = para.strip()
            if len(para) > 20:
                if len(para) > 500:
                    para = para[:500].rsplit(" ", 1)[0] + "…"
                lines.append(para + "\n")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ══════════════════════════════════════════════════════════════════════════════

def get_formatters_summary() -> dict:
    return {
        "version": "1.4",
        "functions": [
            "_is_poor_result",
            "_extract_web_sync_content",
            "_extract_sources_from_report",
            "_has_freshness_indicators",
            "_build_sources_warning",
            "_build_sources_header",
            "_clean_snippet",
            "_format_sources_as_markdown",
            "_format_execution_result",
            "_format_subtitles",
            "_format_burned_subtitles",
            "_format_video",
            "_format_headless_scrape",
            "_format_headless_search",
            "_format_web_sync",
        ],
        "min_sources_recommended": _MIN_SOURCES_RECOMMENDED,
        "freshness_keywords": list(_FRESHNESS_KEYWORDS),
        "handled_actions": [
            "generate_subtitles", "burn_subtitles",
            "generate_image", "edit_image",
            "generate_video", "edit_video",
            "extend_video", "extend_video_multiple",
            "headless_scrape", "headless_search",
            "web_sync",
        ],
    }