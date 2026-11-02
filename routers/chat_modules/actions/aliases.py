# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Actions : Aliases (anti-hallucination LLM)
# ------------------------------------------------------------------------------
# ★ v1.4.5 (2026-10-10) — ALIAS D'ACTIONS (anti-hallucination)
# ★ v1.4.6 (2026-10-10) — AJOUT ALIAS MANQUANTS
# ★ v1.4.8 (2026-10-16) — Migration : extraction dans actions/aliases.py
#   - AUCUNE fonctionnalité modifiée
# ==============================================================================
from __future__ import annotations

import logging
from typing import Dict

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# ★ v1.4.5 — ALIAS D'ACTIONS (anti-hallucination LLM)
# ══════════════════════════════════════════════════════════════════════════════

_ACTION_ALIASES: Dict[str, str] = {
    # ─── Image ───
    "generate_logo":        "generate_image",
    "create_logo":          "generate_image",
    "make_logo":            "generate_image",
    "gen_logo":             "generate_image",
    "logo":                 "generate_image",
    "create_image":         "generate_image",
    "make_image":           "generate_image",
    "gen_image":            "generate_image",
    "create_picture":       "generate_image",
    "make_picture":         "generate_image",
    "draw":                 "generate_image",
    "drawing":              "generate_image",
    "illustration":         "generate_image",
    "text_to_image":        "generate_image",
    "txt2img":              "generate_image",
    "txt2image":            "generate_image",
    "image_generation":     "generate_image",
    "image_gen":            "generate_image",
    "image_creator":        "generate_image",
    "image_maker":          "generate_image",
    "generate_picture":     "generate_image",

    # ─── Édition image ───
    "edit_picture":             "edit_image",
    "modify_image":             "edit_image",
    "img2img":                  "edit_image",
    "image_to_image":           "edit_image",
    "merge_images":             "edit_image",
    "merge_image":              "edit_image",
    "merge_and_edit_images":    "edit_image",

    # ─── Vidéo ───
    "create_video":         "generate_video",
    "make_video":           "generate_video",
    "gen_video":            "generate_video",
    "video":                "generate_video",
    "text_to_video":        "generate_video",
    "txt2vid":              "generate_video",
    "txt2video":            "generate_video",
    "animate":              "generate_video",
    "animation":            "generate_video",
    "video_generation":     "generate_video",

    # ─── Édition vidéo ───
    "modify_video":             "edit_video",
    "video_edit":               "edit_video",
    "merge_videos":             "edit_video",
    "merge_and_edit_videos":    "edit_video",
    "extend":                   "extend_video",
    "continue_video":           "extend_video",
    "prolong_video":            "extend_video",

    # ─── Sous-titres ───
    "subtitle":                 "generate_subtitles",
    "subtitles":                "generate_subtitles",
    "subtitle_video":           "generate_subtitles",
    "whisper_transcribe":       "generate_subtitles",
    "transcribe":               "generate_subtitles",
    "transcription":            "generate_subtitles",
    "captions":                 "generate_subtitles",
    "add_subtitles_to_video":   "burn_subtitles",

    # ─── Web ───
    "search_web":           "web_sync",
    "google_search":        "web_sync",
    "web_search":           "web_sync",
    "web_pipeline":         "web_sync",
    "search":               "web_sync",
    "recherche_web":        "web_sync",
    "scrape":               "headless_scrape",
    "scrape_url":           "headless_scrape",
    "fetch_url":            "headless_scrape",
    "get_page":             "headless_scrape",
    "web_agent_scrape":     "headless_scrape",

    # ─── Mémoire ───
    "remember":             "save_memory",
    "save":                 "save_memory",
    "store_memory":         "save_memory",
    "save_to_memory":       "save_memory",
    "mémoriser":            "save_memory",
    "memorize":             "save_memory",
    "recall_memory":        "search_memory",
    "recall":               "search_memory",
    "search_memories":      "search_memory",
    "retrieve_memory":      "search_memory",
    "forget":               "delete_memory",
    "forget_memory":        "delete_memory",
    "delete_from_memory":   "delete_memory",

    # ─── Fichiers ───
    "create_file":          "write_file",
    "save_file":            "write_file",
    "write":                "write_file",
    "read":                 "read_file",
    "load_file":            "read_file",
    "cat_file":             "read_file",
    "remove_file":          "delete_file",
    "zip":                  "create_zip",
    "unzip":                "extract_zip",
    "compress":             "create_zip",
    "decompress":           "extract_zip",

    # ─── Système ───
    "shell":                "execute_command",
    "bash":                 "execute_command",
    "run_command":          "execute_command",
    "cmd":                  "execute_command",
    "terminal":             "execute_command",
    "run":                  "run_script",
    "execute":              "execute_command",

    # ─── Vision (analyse) ───
    "vision":               "analyze_image",
    "see_image":            "analyze_image",
    "describe_image":       "analyze_image",
    "ocr":                  "analyze_image",
    "image_description":    "analyze_image",
    "analyser_image":       "analyze_image",
    "décrire_image":        "analyze_image",
}


def _resolve_action_alias(act_name: str) -> str:
    """
    ★ v1.4.5 — Résout les alias d'actions hallucinées par le LLM.
    Ex: "generate_logo" → "generate_image"
    """
    if not act_name:
        return act_name

    normalized = act_name.strip().lower()

    if normalized in _ACTION_ALIASES:
        aliased = _ACTION_ALIASES[normalized]
        logger.warning(
            "[ActionAlias] ✅ '%s' → '%s' (hallucination LLM corrigée)",
            act_name, aliased,
        )
        return aliased

    return normalized