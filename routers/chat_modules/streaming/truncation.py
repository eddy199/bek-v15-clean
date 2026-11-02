# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Streaming : Troncature intelligente (v1.7.0)
# ------------------------------------------------------------------------------
# ★ v1.7.0 (2026-10-25) — FORCE LES LIMITES HAUTES
#   - max_chars_per_msg : 120_000
#   - max_total_chars   : 200_000
# ==============================================================================
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("BEKApp")

_FILE_MARKER_START = "--- CONTENU DES FICHIERS JOINTS ---"
_FILE_MARKER_END = "--- FIN DU CONTENU DES FICHIERS JOINTS ---"
_FILE_BLOCK_MARKER = "=== CONTENU DU FICHIER :"

_MAX_USER_INSTRUCTION_CHARS = 4_000
_MAX_FILE_HEAD_CHARS = 50_000

def _has_attached_file_marker(content: str) -> bool:
    if not isinstance(content, str):
        return False
    return (
        _FILE_MARKER_START in content
        or _FILE_MARKER_END in content
        or _FILE_BLOCK_MARKER in content
    )

def _truncate_preserving_file(
    content: str,
    max_chars: int,
    msg_role: str = "user",
) -> str:
    original_len = len(content)
    marker_pos = content.find(_FILE_MARKER_START)

    if marker_pos < 0:
        logger.debug(
            "[Truncation v1.7.0] Marqueur fichier absent du msg '%s' "
            "(longueur %d chars)", msg_role, original_len,
        )
        half = max_chars // 2
        return (
            content[:half]
            + f"\n\n[...{original_len - max_chars} chars omis (troncature classique)...]\n\n"
            + content[-half:]
        )

    user_part = content[:marker_pos]
    file_part = content[marker_pos:]

    logger.info(
        "[Truncation v1.7.0] Fichier joint détecté dans msg '%s' : "
        "instruction=%d chars, contenu fichiers=%d chars, limite=%d",
        msg_role, len(user_part), len(file_part), max_chars,
    )

    user_budget = min(_MAX_USER_INSTRUCTION_CHARS, len(user_part))
    file_budget = max_chars - user_budget

    if file_budget < 500:
        logger.warning(
            "[Truncation v1.7.0] Budget fichier trop faible (%d chars) → "
            "priorité à l'instruction utilisateur", file_budget,
        )
        file_budget = max(500, max_chars - user_budget)

    user_truncated = user_part[:user_budget]
    file_truncated = file_part[:file_budget]

    omitted_chars = original_len - len(user_truncated) - len(file_truncated)

    result = (
        user_truncated
        + file_truncated
        + (
            f"\n\n[...{omitted_chars} chars omis du fichier joint "
            f"(fichier trop long : {len(file_part)} chars, "
            f"limite totale {max_chars})...]"
        )
    )

    logger.info(
        "[Truncation v1.7.0] ✅ Troncature préservante appliquée : "
        "%d → %d chars (user=%d, file=%d, omis=%d)",
        original_len, len(result),
        len(user_truncated), len(file_truncated), omitted_chars,
    )
    return result

def _truncate_messages_for_groq(
    messages: List[Dict[str, Any]],
    max_chars_per_msg: int = 120_000,
    max_total_chars: int = 200_000,
) -> List[Dict[str, Any]]:
    if not messages:
        return messages

    system_msgs: List[Dict[str, Any]] = []
    other_msgs: List[Dict[str, Any]] = []

    for msg in messages:
        if not isinstance(msg, dict): continue
        if msg.get("role") == "system":
            system_msgs.append(msg)
        else:
            other_msgs.append(msg)

    truncated_others: List[Dict[str, Any]] = []
    for idx, msg in enumerate(other_msgs):
        content = msg.get("content", "")
        is_last_user = (idx == len(other_msgs) - 1 and msg.get("role") == "user")
        effective_msg_limit = max_chars_per_msg * 2 if is_last_user else max_chars_per_msg

        if isinstance(content, str) and len(content) > effective_msg_limit:
            if _has_attached_file_marker(content):
                logger.info(
                    "[Truncation v1.7.0] Message '%s' contient un fichier joint "
                    "(%d chars > limite %d) → troncature préservante",
                    msg.get("role", "?"), len(content), effective_msg_limit,
                )
                content = _truncate_preserving_file(
                    content, max_chars=effective_msg_limit, msg_role=msg.get("role", "?"),
                )
            else:
                half = effective_msg_limit // 2
                content = (
                    content[:half]
                    + f"\n\n[...{len(content) - effective_msg_limit} chars omis...]\n\n"
                    + content[-half:]
                )
            msg = {**msg, "content": content}
        truncated_others.append(msg)

    system_chars = sum(len(m.get("content", "")) for m in system_msgs)
    other_chars = sum(len(m.get("content", "")) for m in truncated_others)

    if system_chars + other_chars <= max_total_chars:
        return system_msgs + truncated_others

    budget = max(6000, max_total_chars - system_chars)
    kept: List[Dict[str, Any]] = []
    running = 0

    logger.info(
        "[Truncation v1.7.0] Budget global dépassé : system=%d + others=%d > %d "
        "→ conservation des messages récents (budget %d)",
        system_chars, other_chars, max_total_chars, budget,
    )

    for msg in reversed(truncated_others):
        msg_len = len(msg.get("content", ""))
        if running + msg_len > budget:
            if not kept:
                msg_content = msg.get("content", "")
                if _has_attached_file_marker(msg_content):
                    trimmed_c = _truncate_preserving_file(
                        msg_content, max_chars=budget, msg_role=msg.get("role", "?"),
                    )
                else:
                    trimmed_c = msg_content[:budget]
                kept.insert(0, {**msg, "content": trimmed_c})
            break
        kept.insert(0, msg)
        running += msg_len

    return system_msgs + kept