# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Streaming (v1.5.2 — Fix Python 3.14 f-strings)
# ------------------------------------------------------------------------------
# Version : 1.5.2
# Date : 2026-09-30
# ------------------------------------------------------------------------------
# ★ v1.3.3 — HINDSIGHT (memorisation automatique)
# ★ v1.4.0 — FIX : détection tolérante de la balise fermante
# ★ v1.5.0 — MULTI-ACTIONS
# ★ v1.5.1 — Anti-hallucination post-action
# ★ v1.5.2 — FIX Python 3.14 : retire les backslashes dans les f-strings
#             (erreur au build Render : "f-string expression part cannot include a backslash")
# ==============================================================================

from __future__ import annotations

import json
import logging
import os
import re as _re
import time
from collections import Counter
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from . import config as cfg
from . import validation as val
from . import actions as act
from . import formatters as fmt
from . import routing as rt
from . import scrape as scr
from . import stair as st

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# REGEX UNIFIÉE POUR LES ACTIONS
# ==============================================================================

_ACTION_FULL_RE = _re.compile(
    r"\[\s*ACTION\s*:\s*(\w+)\s*\]"
    r"(.*?)"
    r"\[\s*/\s*A\s*CTION\s*\]",
    _re.DOTALL | _re.IGNORECASE,
)

_CLOSING_ACTION_RE = _re.compile(r"\[\s*/\s*A\s*CTION\s*\]", _re.IGNORECASE)

_CLOSING_ACTION_LOOSE_RE = _re.compile(
    r"\[\s*/\s*A\s*C\s*T\s*I\s*O\s*N\s*\]", _re.IGNORECASE
)


def _has_closing_action(text: str) -> bool:
    if not text:
        return False
    if _CLOSING_ACTION_RE.search(text):
        return True
    if _CLOSING_ACTION_LOOSE_RE.search(text):
        return True
    return False


def _has_opening_action(text: str) -> bool:
    if not text:
        return False
    return bool(_re.search(r"\[\s*ACTION\s*:", text, _re.IGNORECASE))


def _find_all_complete_actions(text: str) -> List[Dict[str, Any]]:
    """Extrait TOUTES les actions complètes d'un texte."""
    if not text:
        return []

    results = []
    for match in _ACTION_FULL_RE.finditer(text):
        act_name = match.group(1)
        raw_payload = match.group(2).strip()
        end_pos = match.end()

        params: Dict[str, Any] = {}
        try:
            import json as _json
            p_json = _json.loads(raw_payload)
            if isinstance(p_json, dict):
                params = p_json
        except Exception:
            try:
                import ast as _ast
                p_ast = _ast.literal_eval(raw_payload)
                if isinstance(p_ast, dict):
                    params = p_ast
            except Exception:
                pass

        params = act._clean_action_params(params)

        results.append({
            "name": act_name,
            "params": params,
            "end_pos": end_pos,
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# HINDSIGHT
# ==============================================================================

try:
    from hindsight_memory import hindsight_retain_conversation
    _HINDSIGHT_AVAILABLE = True
except ImportError:
    _HINDSIGHT_AVAILABLE = False
    def hindsight_retain_conversation(user_message, agent_response, context=None):
        return False


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ==============================================================================

def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = True) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


MAX_STREAM_DURATION_SEC = _env_int("BEK_STREAM_TIMEOUT_SEC", 300, minimum=60)
LOOP_DETECT_ENABLED = _env_bool("BEK_LOOP_DETECT_ENABLED", True)
LOOP_WINDOW = _env_int("BEK_LOOP_WINDOW", 15, minimum=5)
LOOP_THRESHOLD = _env_int("BEK_LOOP_THRESHOLD", 4, minimum=2)
MAX_REASONING_CHARS = _env_int("BEK_MAX_REASONING_CHARS", 6000, minimum=500)

BEK_ECO_CACHE_ENABLED = _env_bool("BEK_ECO_CACHE_ENABLED", True)
BEK_MEM_ENABLED = _env_bool("BEK_MEM_ENABLED", True)
BEK_LOOP_ENABLED = _env_bool("BEK_LOOP_ENABLED", True)
BEK_FIX_SPACING_ENABLED = _env_bool("BEK_FIX_SPACING_ENABLED", True)

BEK_MULTI_ACTIONS_ENABLED = _env_bool("BEK_MULTI_ACTIONS_ENABLED", True)
BEK_MAX_ACTIONS_PER_RESPONSE = _env_int("BEK_MAX_ACTIONS_PER_RESPONSE", 5)

BEK_ANTIHALLU_ENABLED = _env_bool("BEK_ANTIHALLU_ENABLED", True)
BEK_POST_ACTION_GRACE_MAX = _env_int("BEK_POST_ACTION_GRACE_MAX", 50, minimum=10)


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGES GARDE-FOUS
# ==============================================================================

_MSG_TIMEOUT_DUR = "\n\n⏱️ **Délai dépassé** — réponse interrompue."
_MSG_REASONING_OVERFLOW = "\n\n🧠 **Réflexion excessive** — arrêt automatique."
_MSG_LOOP_DETECTED = "\n\n🔁 **Boucle détectée** — arrêt automatique."


# ══════════════════════════════════════════════════════════════════════════════
# NETTOYAGE LLM
# ==============================================================================

_LLM_NATIVE_TOKENS = (
    "<|tool_call_begin|>", "<|tool_call_end|>",
    "<|tool_call_argument_begin|>", "<|tool_call_argument_end|>",
    "<|tool_call|>", "<|tool_sep|>",
    "<|tool_calls_section_begin|>", "<|tool_calls_section_end|>",
)

_LLM_NATIVE_REGEX = _re.compile("|".join(_re.escape(t) for t in _LLM_NATIVE_TOKENS))
_LLM_XML_TOOL_REGEX = _re.compile(r"<tool_call>.*?</tool_call>", _re.DOTALL)


_THINKING_PATTERNS = (
    _re.compile(r"<think>.*?</think>", _re.DOTALL | _re.IGNORECASE),
    _re.compile(r"<thinking>.*?</thinking>", _re.DOTALL | _re.IGNORECASE),
    _re.compile(r"<reasoning>.*?</reasoning>", _re.DOTALL | _re.IGNORECASE),
)

_THINKING_LINE_PATTERNS = (
    _re.compile(
        r"^\s*(?:Okay|OK|Alright|Let me|Let's|I need to|I should|"
        r"I will|I'm going to|First,|Second,|Third,|Wait,|Hmm,)"
        r"\s*,?\s*(?:the user|I|we).*$",
        _re.IGNORECASE | _re.MULTILINE,
    ),
    _re.compile(
        r"^\s*(?:Attends?|Attendez|Vérifions|Analysons|Réfléchissons)"
        r"\s*,?\s+(?:je|on|nous|il|elle)\s+.*$",
        _re.IGNORECASE | _re.MULTILINE,
    ),
)


def _strip_reasoning(text: str) -> str:
    if not text:
        return text
    for pattern in _THINKING_PATTERNS:
        text = pattern.sub("", text)
    for pattern in _THINKING_LINE_PATTERNS:
        text = pattern.sub("", text)
    text = _re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _sanitize_llm_output(text: str, strip_reasoning: bool = True) -> str:
    if not text:
        return text
    text = _LLM_NATIVE_REGEX.sub("", text)
    text = _LLM_XML_TOOL_REGEX.sub("", text)
    if strip_reasoning:
        text = _strip_reasoning(text)
    return text


_MOT_PATTERN = _re.compile(
    r'\b('
    r'je|tu|il|elle|on|nous|vous|ils|elles|'
    r'le|la|les|un|une|des|du|de|d|l|'
    r'et|ou|mais|car|donc|or|ni|'
    r'ne|pas|plus|moins|tres|bien|mal|'
    r'est|sont|etait|etaient|sera|seront|'
    r'ai|as|a|avons|avez|ont|avait|avaient|'
    r'pour|par|avec|sans|sur|sous|dans|'
    r'que|qui|quoi|dont|ou|'
    r'ce|cet|cette|ces|mon|ma|mes|ton|ta|tes|son|sa|ses|'
    r'notre|nos|votre|vos|leur|leurs'
    r')\b',
    _re.IGNORECASE,
)


def _fix_spacing(text: str) -> str:
    if not text or len(text) < 3:
        return text
    if ('":' in text) or ('{' in text and '}' in text):
        return text
    text = _re.sub(r'([a-zà-ÿ])([A-ZÀ-Ý])', r'\1 \2', text)
    text = _re.sub(r'([.!?,;:])([A-ZÀ-Ýa-zà-ÿ])', r'\1 \2', text)
    text = _MOT_PATTERN.sub(lambda m: m.group(1) + ' ', text)
    text = _re.sub(r'  +', ' ', text)
    text = _re.sub(r' ([.!?,;:])', r'\1', text)
    text = _re.sub(r"(\w) '\s*(\w)", r"\1'\2", text)
    return text


class _LoopDetector:
    def __init__(self, window: int = LOOP_WINDOW, threshold: int = LOOP_THRESHOLD):
        self.window = window
        self.threshold = threshold
        self._buffer: List[str] = []

    def add(self, chunk: str) -> bool:
        if not chunk:
            return False
        normalized = chunk.strip().lower()[:80]
        if not normalized or len(normalized) < 5:
            return False
        self._buffer.append(normalized)
        if len(self._buffer) > self.window:
            self._buffer.pop(0)
        if len(self._buffer) < self.window:
            return False
        counts = Counter(self._buffer)
        _, most_common_count = counts.most_common(1)[0]
        return most_common_count >= self.threshold

    def reset(self):
        self._buffer.clear()


# ══════════════════════════════════════════════════════════════════════════════
# STREAMING PRINCIPAL
# ==============================================================================

async def stream_chat(
    exec_messages: List[Dict[str, Any]],
    trimmed_messages: List[Dict[str, Any]],
    last_user_query: str,
    provider: str,
    model: str,
) -> AsyncGenerator[str, None]:
    from provider_manager import provider_manager

    full_text_accumulated: List[str] = []

    # ══════════════════════════════════════════════════════════════════
    # ★ v1.5.2 — PRÉ-PARSING : action utilisateur → exécution directe
    # ==========================================================================
    _user_part = last_user_query or ""
    _instr_pos = _user_part.find("(INSTRUCTION SYSTEME")
    if _instr_pos > 0:
        _user_part = _user_part[:_instr_pos]

    _user_actions = _find_all_complete_actions(_user_part)

    if _user_actions:
        logger.info(
            "[Streaming v1.5.2] %d action(s) utilisateur — exécution DIRECTE (bypass LLM)",
            len(_user_actions),
        )
        # ★ v1.5.2 — Variables intermédiaires (f-string compatible Python 3.14)
        _direct_msg = "\n\n⚙️ *Exécution directe...*\n\n"
        yield f"data: {json.dumps({'chunk': _direct_msg})}\n\n"

        for _idx, _ua in enumerate(_user_actions, 1):
            _ua_name = _ua["name"]
            _ua_params = _ua["params"]

            if _ua_name not in cfg.MULTIMEDIA_ACTIONS:
                _ua_params["provider"] = provider
                _ua_params["model"] = model

            logger.info(
                "[Streaming v1.5.2] 🎯 Action directe %d : %s | params=%s",
                _idx, _ua_name, list(_ua_params.keys()),
            )
            _exec_msg = f"\n\n⚙️ *Exécution {_idx}...*\n"
            yield f"data: {json.dumps({'chunk': _exec_msg})}\n\n"

            _t0 = time.monotonic()
            try:
                _exec_res = act._execute_action_unified(_ua_name, _ua_params)
                _elapsed = (time.monotonic() - _t0) * 1000
                _res_msg = fmt._format_execution_result(_ua_name, _exec_res)
                logger.info(
                    "[Streaming v1.5.2] ✅ Action %s terminée (%.0fms)",
                    _ua_name, _elapsed,
                )
                _res_chunk = "\n\n" + str(_res_msg) + "\n\n"
                yield f"data: {json.dumps({'chunk': _res_chunk})}\n\n"
            except Exception as _err:
                logger.exception("[Streaming v1.5.2] Action %s échouée", _ua_name)
                _err_chunk = f"\n\n⚠️ Erreur action {_ua_name} : {_err}\n\n"
                yield f"data: {json.dumps({'chunk': _err_chunk})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"
        return
    # ══════════════════════════════════════════════════════════════════
    # Fin du pré-parsing — suite normale ci-dessous
    # ==========================================================================
    action_detected = False
    total_actions_executed = 0
    chunks_without_close = 0

    processed_actions: Set[int] = set()

    _post_action_mode: bool = False
    _post_action_grace_chunks: int = 0
    _last_action_end_pos: int = 0

    _start_time = time.monotonic()
    _reasoning_chars = 0
    _loop_detector = _LoopDetector() if LOOP_DETECT_ENABLED else None

    _routing_result: Dict = {}
    _eco_result: Dict = {}
    _success: bool = True
    _error_type: str = ""
    _cached_response_served: bool = False

    is_freshness_query = rt._bek_rex_is_freshness_query(last_user_query)
    if is_freshness_query:
        logger.info("[Streaming v1.5.2] Requête de fraîcheur détectée")
    # ══════════════════════════════════════════════════════════════════
    # ★ v1.6.0 — DÉTECTION ALTER EGO
    # ══════════════════════════════════════════════════════════════════
    _detected_ego = rt._bek_rex_detect_alter_ego(last_user_query)
    _alter_ego_prompt = ""

    if _detected_ego and _detected_ego != "bek":
        logger.info(
            "[Streaming v1.6.0] 🎭 Alter ego activé : %s",
            _detected_ego
        )
        _alter_ego_prompt = rt._bek_rex_get_alter_ego_prompt(_detected_ego)

        if _alter_ego_prompt:
            logger.info(
                "[Streaming v1.6.0] Alter ego injecté (%d chars)",
                len(_alter_ego_prompt)
            )
            # Injecter l'alter ego dans le dernier message système
            for _msg in exec_messages:
                if _msg.get("role") == "system":
                    _msg["content"] = (
                        _alter_ego_prompt
                        + "\n\n"
                        + _msg.get("content", "")
                    )
                    break

    try:
        # BEK-REX
        try:
            _routing_result = rt._bek_rex_route(last_user_query)
            logger.info(
                "[Streaming v1.5.2] BEK-REX tier=%s conf=%.2f source=%s",
                _routing_result.get("tier"),
                _routing_result.get("confidence", 0.0),
                _routing_result.get("source"),
            )
        except Exception as _rex_err:
            logger.warning("[Streaming v1.5.2] BEK-REX échec : %s", _rex_err)
            _routing_result = {"tier": "TIER_3", "confidence": 0.5}

        _tier = _routing_result.get("tier", "TIER_3")

        # BEK-ECO
        if BEK_ECO_CACHE_ENABLED and last_user_query:
            try:
                _eco_result = rt._bek_eco_check_cache(last_user_query, _tier)
                if _eco_result.get("cached") and _eco_result.get("cached_value"):
                    cached_response = _eco_result["cached_value"].get("response", "")
                    if cached_response:
                        logger.info("[Streaming v1.5.2] ⚡ BEK-ECO cache HIT")
                        _cached_response_served = True
                        cache_badge = "⚡ *[réponse en cache]*\n\n"
                        yield f"data: {json.dumps({'chunk': cache_badge}, ensure_ascii=False)}\n\n"
                        CHUNK_SIZE = 80
                        for i in range(0, len(cached_response), CHUNK_SIZE):
                            piece = cached_response[i:i + CHUNK_SIZE]
                            yield f"data: {json.dumps({'chunk': piece}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        return
                else:
                    logger.info(
                        "[Streaming v1.5.2] BEK-ECO cache MISS (hash=%s)",
                        _eco_result.get("query_hash", "?"),
                    )
            except Exception as _eco_err:
                logger.warning("[Streaming v1.5.2] BEK-ECO échec : %s", _eco_err)

        # ══════════════════════════════════════════════════════════════════
        # BOUCLE PRINCIPALE
        # ══════════════════════════════════════════════════════════════════
        for item in provider_manager.execute_chat_stream(
            messages=exec_messages,
            provider=provider,
            model=model,
            temperature=0.7,
            max_tokens=4096,
        ):
            _elapsed = time.monotonic() - _start_time
            if MAX_STREAM_DURATION_SEC and _elapsed > MAX_STREAM_DURATION_SEC:
                logger.warning("[Streaming v1.5.2] ⏱️ Timeout dur atteint")
                yield f"data: {json.dumps({'chunk': _MSG_TIMEOUT_DUR})}\n\n"
                _success = False
                _error_type = "stream_timeout"
                break

            if "error" in item:
                error_msg = item.get("error", "Erreur inconnue")
                logger.error("[ProviderManager] Erreur : %s", error_msg)
                err_chunk = f"\n\n⚠️ **Erreur provider** : {error_msg}\n\n"
                yield f"data: {json.dumps({'chunk': err_chunk})}\n\n"
                _success = False
                _error_type = "provider_error"
                break

            if "chunk" not in item:
                continue

            chunk = item["chunk"]
            chunk = _sanitize_llm_output(chunk, strip_reasoning=True)
            if BEK_FIX_SPACING_ENABLED:
                chunk = _fix_spacing(chunk)
            if not chunk.strip():
                continue

            # ══════════════════════════════════════════════════════════════
            # ANTI-HALLUCINATION POST-ACTION
            # ==========================================================================
            if BEK_ANTIHALLU_ENABLED and _post_action_mode:
                _post_action_grace_chunks += 1

                if _post_action_grace_chunks > BEK_POST_ACTION_GRACE_MAX:
                    logger.info(
                        "[Streaming v1.5.2] ✂️ STOP post-action après %d chunks",
                        _post_action_grace_chunks,
                    )
                    _success = True
                    _error_type = "post_action_stop"
                    break

                full_text_accumulated.append(chunk)
                current_text = "".join(full_text_accumulated)

                text_since_action = current_text[_last_action_end_pos:]
                if not _has_opening_action(text_since_action):
                    logger.debug(
                        "[Streaming v1.5.2] Chunk ignoré (post-action) : %r",
                        chunk[:60],
                    )
                    continue
                else:
                    logger.info(
                        "[Streaming v1.5.2] Nouvelle action détectée → sortie post-action",
                    )
                    _post_action_mode = False
                    _post_action_grace_chunks = 0

            # ══════════════════════════════════════════════════════════════
            # TRAITEMENT NORMAL
            # ==========================================================================
            full_text_accumulated.append(chunk)
            current_text = "".join(full_text_accumulated)

            if _has_opening_action(current_text):
                action_detected = True

            if not action_detected and MAX_REASONING_CHARS:
                _reasoning_chars += len(chunk)
                if _reasoning_chars > MAX_REASONING_CHARS:
                    logger.warning("[Streaming v1.5.2] 🧠 Réflexion excessive")
                    yield f"data: {json.dumps({'chunk': _MSG_REASONING_OVERFLOW})}\n\n"
                    _success = False
                    _error_type = "reasoning_overflow"
                    break

            if _loop_detector is not None and not action_detected:
                if _loop_detector.add(chunk):
                    logger.warning("[Streaming v1.5.2] 🔁 Boucle détectée")
                    yield f"data: {json.dumps({'chunk': _MSG_LOOP_DETECTED})}\n\n"
                    _success = False
                    _error_type = "loop_detected"
                    break

            if action_detected and not _has_closing_action(current_text):
                chunks_without_close += 1
                if chunks_without_close > cfg.MAX_CHUNKS_WITHOUT_CLOSE:
                    logger.warning(
                        "[Streaming v1.5.2] Action incomplète après %d chunks — abandon.",
                        chunks_without_close,
                    )
                    warn_incomplete = (
                        "\n\n⚠️ **Action incomplète** détectée. "
                        "Reformulez la demande.\n\n"
                    )
                    yield f"data: {json.dumps({'chunk': warn_incomplete})}\n\n"
                    _success = False
                    _error_type = "incomplete_action"
                    break

            yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

            # ══════════════════════════════════════════════════════════════
            # EXTRACTION MULTI-ACTIONS
            # ==========================================================================
            if BEK_MULTI_ACTIONS_ENABLED and action_detected:
                all_actions = _find_all_complete_actions(current_text)
                for action in all_actions:
                    end_pos = action["end_pos"]

                    if end_pos in processed_actions:
                        continue

                    if total_actions_executed >= BEK_MAX_ACTIONS_PER_RESPONSE:
                        logger.warning(
                            "[Streaming v1.5.2] Limite %d actions atteinte",
                            BEK_MAX_ACTIONS_PER_RESPONSE,
                        )
                        break

                    act_name = action["name"]
                    params = action["params"]

                    logger.info(
                        "[Streaming v1.5.2] 🎯 Action %d : %s (end_pos=%d)",
                        total_actions_executed + 1, act_name, end_pos,
                    )

                    if act_name == "headless_search":
                        try:
                            _should_use_ws = rt._bek_rex_should_use_web_sync(
                                last_user_query, _routing_result,
                            )
                            if _should_use_ws:
                                logger.info("[Streaming v1.5.2] headless_search → web_sync")
                                act_name = "web_sync"
                                params = {"query": params.get("query", last_user_query)}
                        except Exception as _rex_err:
                            logger.warning("[Streaming v1.5.2] BEK-REX échec : %s", _rex_err)

                    if act_name not in cfg.MULTIMEDIA_ACTIONS:
                        params["provider"] = provider
                        params["model"] = model

                    msg_imm = f'\n\n⚙️ *Exécution {total_actions_executed + 1}...*\n'
                    yield f"data: {json.dumps({'chunk': msg_imm})}\n\n"

                    _action_start = time.monotonic()
                    try:
                        exec_res = act._execute_action_unified(act_name, params)
                        _action_elapsed_ms = (time.monotonic() - _action_start) * 1000
                        res_msg = fmt._format_execution_result(act_name, exec_res)

                        try:
                            from bek_eval_guard import evaluate_response_quality
                            eval_r = evaluate_response_quality(last_user_query, res_msg)
                            if not eval_r["passed"]:
                                res_msg = f"⚠️ [BEK Guard] Filtré : {eval_r['reason']}"
                        except Exception:
                            pass

                        res_chunk = "\n\n" + str(res_msg) + "\n\n"
                        yield f"data: {json.dumps({'chunk': res_chunk})}\n\n"

                        total_actions_executed += 1
                        processed_actions.add(end_pos)
                        _last_action_end_pos = end_pos

                        logger.info(
                            "[Streaming v1.5.2] ✅ Action %s terminée (%.0fms)",
                            act_name, _action_elapsed_ms,
                        )

                    except Exception as _act_err:
                        logger.exception("[Streaming v1.5.2] Action %s échouée", act_name)
                        err_chunk = f"\n\n⚠️ Erreur action {act_name} : {_act_err}\n\n"
                        yield f"data: {json.dumps({'chunk': err_chunk})}\n\n"
                        processed_actions.add(end_pos)
                        _last_action_end_pos = end_pos
                        _success = False
                        _error_type = f"action_{act_name}_error"

                if BEK_ANTIHALLU_ENABLED and total_actions_executed > 0:
                    _post_action_mode = True
                    _post_action_grace_chunks = 0

        _total_elapsed = time.monotonic() - _start_time
        logger.info(
            "[Streaming v1.5.2] ✓ Terminé en %.2fs | actions=%d | chunks=%d",
            _total_elapsed, total_actions_executed, len(full_text_accumulated),
        )

    except Exception as stream_err:
        logger.error("[Streaming v1.5.2] Erreur : %s", stream_err, exc_info=True)
        err_msg = f"\n\n⚠️ Flux Error : {stream_err}\n"
        yield f"data: {json.dumps({'chunk': err_msg})}\n\n"
        _success = False
        _error_type = type(stream_err).__name__

    finally:
        try:
            _total_elapsed_final = time.monotonic() - _start_time

            if BEK_LOOP_ENABLED and not _cached_response_served and last_user_query:
                try:
                    rt._bek_loop_record(
                        query=last_user_query,
                        tier=_routing_result.get("tier", "TIER_3"),
                        provider=provider,
                        model=model,
                        success=_success,
                        time_ms=_total_elapsed_final * 1000,
                        error_type=_error_type,
                    )
                except Exception:
                    pass

            if (
                BEK_ECO_CACHE_ENABLED
                and _success
                and not _cached_response_served
                and last_user_query
                and full_text_accumulated
                and not action_detected
            ):
                try:
                    final_response = "".join(full_text_accumulated)
                    if final_response and len(final_response) > 50:
                        rt._bek_eco_store_cache(
                            query=last_user_query,
                            tier=_routing_result.get("tier", "TIER_3"),
                            response=final_response,
                        )
                except Exception:
                    pass

            if (
                _HINDSIGHT_AVAILABLE
                and _success
                and not _cached_response_served
                and last_user_query
                and full_text_accumulated
            ):
                try:
                    final_agent_response = "".join(full_text_accumulated)
                    if final_agent_response and len(final_agent_response) > 20:
                        hindsight_retain_conversation(
                            user_message=last_user_query,
                            agent_response=final_agent_response[:1000],
                            context="chat_conversation",
                        )
                except Exception:
                    pass

        except Exception as _loop_err:
            logger.debug("[Streaming v1.5.2] Erreur finally : %s", _loop_err)

        yield f"data: {json.dumps({'done': True})}\n\n"


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ==============================================================================

def get_streaming_summary() -> dict:
    return {
        "version": "1.5.2",
        "functions": [
            "_sanitize_llm_output", "_strip_reasoning", "_fix_spacing",
            "_has_closing_action", "_has_opening_action",
            "_find_all_complete_actions",
            "stream_chat",
        ],
        "features": {
            "multi_actions": BEK_MULTI_ACTIONS_ENABLED,
            "max_actions_per_response": BEK_MAX_ACTIONS_PER_RESPONSE,
            "closing_tag_tolerant": True,
            "nvidia_space_fix": True,
            "★ anti_hallucination_post_action": BEK_ANTIHALLU_ENABLED,
            "★ post_action_grace_max": BEK_POST_ACTION_GRACE_MAX,
            "★ python_3_14_fstring_safe": True,
        },
        "env_flags": {
            "BEK_MULTI_ACTIONS_ENABLED": BEK_MULTI_ACTIONS_ENABLED,
            "BEK_MAX_ACTIONS_PER_RESPONSE": BEK_MAX_ACTIONS_PER_RESPONSE,
            "BEK_ECO_CACHE_ENABLED": BEK_ECO_CACHE_ENABLED,
            "BEK_ANTIHALLU_ENABLED": BEK_ANTIHALLU_ENABLED,
            "BEK_POST_ACTION_GRACE_MAX": BEK_POST_ACTION_GRACE_MAX,
        },
    }