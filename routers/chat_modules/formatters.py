# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Formatters
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Formatage des résultats d'action pour le LLM
# 📄 Doc : docs/BEK_LVC.md
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-24
# ==============================================================================

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from . import config as cfg

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION RÉSULTAT PAUVRE
# ══════════════════════════════════════════════════════════════════════════════

def _is_poor_result(exec_res: Optional[dict], act_name: str) -> bool:
    """
    Détecte si un résultat est "pauvre" (nécessite un fallback).

    Règles :
        - headless_search : pauvre si 0 leads
        - headless_scrape : pauvre si HTML < 200 chars
        - web_sync : pauvre si rapport < 200 chars
    """
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
        report = exec_res.get("report", "") or ""
        return len(str(report)) < cfg.POOR_RESULT_THRESHOLD

    return False


# ══════════════════════════════════════════════════════════════════════════════
# FORMATAGE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def _format_execution_result(act_name: str, exec_res: dict) -> str:
    """
    Formate le résultat d'une action pour injection dans le prompt.
    """
    if not isinstance(exec_res, dict):
        return str(exec_res)

    fn = exec_res.get("filename", "")
    srt_fn = exec_res.get("srt_filename", "")

    # ─── SOUS-TITRES ───
    if act_name == "generate_subtitles" and exec_res.get("status") == "success":
        return _format_subtitles(exec_res, srt_fn)

    if act_name == "burn_subtitles" and exec_res.get("status") == "success" and fn:
        return _format_burned_subtitles(exec_res, fn)

    # ─── IMAGE / VIDÉO ───
    if exec_res.get("status") == "success" and fn:
        if any(fn.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]):
            return f"🎨 **Image générée !**\n\n![{fn}](/api/download/{fn})"

        if any(fn.lower().endswith(ext) for ext in [".mp4", ".webm", ".mov", ".avi"]):
            return _format_video(exec_res, act_name, fn)

    # ─── HEADLESS_SCRAPE ───
    if act_name == "headless_scrape":
        return _format_headless_scrape(exec_res)

    # ─── HEADLESS_SEARCH (conservé pour compatibilité) ───
    if act_name == "headless_search":
        return _format_headless_search(exec_res)

    # ─── WEB_SYNC ───
    if act_name == "web_sync":
        return _format_web_sync(exec_res)

    # ─── FALLBACK ───
    return exec_res.get("message", "Opération OK")


# ══════════════════════════════════════════════════════════════════════════════
# FORMATTERS SPÉCIALISÉS
# ══════════════════════════════════════════════════════════════════════════════

def _format_subtitles(exec_res: dict, srt_fn: str) -> str:
    """Formate le résultat de generate_subtitles."""
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
    """Formate le résultat de burn_subtitles."""
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
    """Formate le résultat de génération/édition/extension vidéo."""
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
    """Formate le résultat de headless_scrape."""
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
    """Formate le résultat de headless_search (compatibilité)."""
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


def _format_web_sync(exec_res: dict) -> str:
    """Formate le résultat de web_sync (WebAgent profond)."""
    if exec_res.get("status") != "success":
        return exec_res.get("message", "❌ web_sync a échoué")

    report = exec_res.get("report", "") or ""
    report_str = str(report).strip()

    if not report_str or len(report_str) < 100:
        return (
            "⚠️ **Veille web sans résultat exploitable**\n\n"
            "→ Le pipeline WebAgent n'a pas pu extraire de contenu.\n"
            "→ Dis HONNÊTEMENT à l'utilisateur qu'aucune source n'a été "
            "trouvée et propose de reformuler.\n"
            "→ N'INVENTE AUCUNE actualité."
        )

    return f"🌐 **Veille web approfondie** :\n\n{report_str[:5000]}"


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ══════════════════════════════════════════════════════════════════════════════

def get_formatters_summary() -> dict:
    """Résumé des formateurs disponibles."""
    return {
        "functions": [
            "_is_poor_result",
            "_format_execution_result",
            "_format_subtitles",
            "_format_burned_subtitles",
            "_format_video",
            "_format_headless_scrape",
            "_format_headless_search",
            "_format_web_sync",
        ],
        "handled_actions": [
            "generate_subtitles",
            "burn_subtitles",
            "generate_image",
            "edit_image",
            "generate_video",
            "edit_video",
            "extend_video",
            "extend_video_multiple",
            "headless_scrape",
            "headless_search",
            "web_sync",
        ],
    }