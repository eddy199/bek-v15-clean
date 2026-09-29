# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Streaming (v1.3.2 — 4 LEVIERS + Fix espaces NVIDIA)
# ------------------------------------------------------------------------------
# Version : 1.3.2
# Date : 2026-09-29
# ------------------------------------------------------------------------------
# ★ v1.3.2 — FIX espaces NVIDIA nemotron (chunks mot-par-mot)
# ==============================================================================

from __future__ import annotations

import json
import logging
import os
import re as _re
import time
from collections import Counter
from typing import Any, AsyncGenerator, Dict, List, Optional

from . import config as cfg
from . import validation as val
from . import actions as act
from . import formatters as fmt
from . import routing as rt
from . import scrape as scr
from . import stair as st

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGES GARDE-FOUS (hors f-strings pour Python 3.12+)
# ══════════════════════════════════════════════════════════════════════════════

_MSG_TIMEOUT_DUR = "\n\n⏱️ **Délai dépassé** — réponse interrompue."
_MSG_REASONING_OVERFLOW = "\n\n🧠 **Réflexion excessive** — arrêt automatique. Reformulez la demande."
_MSG_LOOP_DETECTED = "\n\n🔁 **Boucle détectée** — arrêt automatique. Reformulez la demande."
_MSG_SYNTH_TIMEOUT = "\n\n⏱️ Synthèse trop longue — interrompue."
_MSG_SYNTH_VERBOSE = "\n\n🧠 Synthèse trop verbeuse — arrêt."


# ══════════════════════════════════════════════════════════════════════════════
# NETTOYAGE LLM
# ══════════════════════════════════════════════════════════════════════════════

_LLM_NATIVE_TOKENS = (
    "<|tool_call_begin|>", "<|tool_call_end|>",
    "<|tool_call_argument_begin|>", "<|tool_call_argument_end|>",
    "<|tool_call|>", "<|tool_sep|>",
    "<|tool_calls_section_begin|>", "<|tool_calls_section_end|>",
)

_LLM_NATIVE_REGEX = _re.compile("|".join(_re.escape(t) for t in _LLM_NATIVE_TOKENS))
_LLM_XML_TOOL_REGEX = _re.compile(r"<tool_call>.*?</tool_call>", _re.DOTALL)


# ══════════════════════════════════════════════════════════════════════════════
# FILTRE REASONING
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# ★ v1.3.2 — CORRECTEUR D'ESPACES (fix NVIDIA nemotron)
# ══════════════════════════════════════════════════════════════════════════════

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
    """Réinsère les espaces manquants. 'Jenotetasatisfaction' -> 'Je note ta satisfaction'."""
    if not text or len(text) < 3:
        return text
    text = _re.sub(r'([a-zà-ÿ])([A-ZÀ-Ý])', r'\1 \2', text)
    text = _re.sub(r'([.!?,;:])([A-ZÀ-Ýa-zà-ÿ])', r'\1 \2', text)
    text = _MOT_PATTERN.sub(lambda m: m.group(1) + ' ', text)
    text = _re.sub(r'  +', ' ', text)
    text = _re.sub(r' ([.!?,;:])', r'\1', text)
    text = _re.sub(r"(\w) '\s*(\w)", r"\1'\2", text)
    return text


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTEUR DE BOUCLE
# ══════════════════════════════════════════════════════════════════════════════

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
# STREAMING PRINCIPAL (v1.3.2)
# ══════════════════════════════════════════════════════════════════════════════

async def stream_chat(
    exec_messages: List[Dict[str, Any]],
    trimmed_messages: List[Dict[str, Any]],
    last_user_query: str,
    provider: str,
    model: str,
) -> AsyncGenerator[str, None]:
    from provider_manager import provider_manager

    act_name: str = ""
    params: Dict[str, Any] = {}
    res_msg: str = ""
    exec_res: Optional[Dict[str, Any]] = None

    full_text_accumulated: List[str] = []
    action_detected = False
    total_actions_executed = 0
    action_was_executed = False
    last_result_poor = False
    chunks_without_close = 0
    auto_scraped_pages: List[Dict[str, Any]] = []

    _start_time = time.monotonic()
    _reasoning_chars = 0
    _loop_detector = _LoopDetector() if LOOP_DETECT_ENABLED else None

    _routing_result: Dict = {}
    _eco_result: Dict = {}
    _mem_proto_id: str = ""
    _success: bool = True
    _error_type: str = ""
    _cached_response_served: bool = False

    is_freshness_query = rt._bek_rex_is_freshness_query(last_user_query)
    if is_freshness_query:
        logger.info("[Streaming v1.3] Requête de fraîcheur détectée")

    try:
        # LEVIER 3 — BEK-REX
        try:
            _routing_result = rt._bek_rex_route(last_user_query)
            logger.info(
                "[Streaming v1.3] BEK-REX tier=%s conf=%.2f source=%s",
                _routing_result.get("tier"),
                _routing_result.get("confidence", 0.0),
                _routing_result.get("source"),
            )
        except Exception as _rex_err:
            logger.warning("[Streaming v1.3] BEK-REX échec : %s", _rex_err)
            _routing_result = {"tier": "TIER_3", "confidence": 0.5}

        _tier = _routing_result.get("tier", "TIER_3")

        # LEVIER 1 — BEK-ECO (cache)
        if BEK_ECO_CACHE_ENABLED and last_user_query:
            try:
                _eco_result = rt._bek_eco_check_cache(last_user_query, _tier)

                if _eco_result.get("cached") and _eco_result.get("cached_value"):
                    cached_value = _eco_result["cached_value"]
                    cached_response = cached_value.get("response", "")

                    if cached_response:
                        logger.info("[Streaming v1.3] ⚡ BEK-ECO cache HIT — réponse instantanée")
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
                        "[Streaming v1.3] BEK-ECO cache MISS (hash=%s) → appel LLM",
                        _eco_result.get("query_hash", "?"),
                    )
            except Exception as _eco_err:
                logger.warning("[Streaming v1.3] BEK-ECO échec : %s", _eco_err)

        # BOUCLE PRINCIPALE
        for item in provider_manager.execute_chat_stream(
            messages=exec_messages,
            provider=provider,
            model=model,
            temperature=0.7,
            max_tokens=4096,
        ):
            _elapsed = time.monotonic() - _start_time
            if MAX_STREAM_DURATION_SEC and _elapsed > MAX_STREAM_DURATION_SEC:
                logger.warning(
                    "[Streaming v1.3] ⏱️ Timeout dur atteint (%.1fs > %ds) — arrêt.",
                    _elapsed, MAX_STREAM_DURATION_SEC,
                )
                yield f"data: {json.dumps({'chunk': _MSG_TIMEOUT_DUR})}\n\n"
                _success = False
                _error_type = "stream_timeout"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            if "error" in item:
                error_msg = item.get("error", "Erreur inconnue")
                logger.error("[ProviderManager] Erreur : %s", error_msg)
                err_chunk = f"\n\n⚠️ **Erreur provider** : {error_msg}\n\n"
                yield f"data: {json.dumps({'chunk': err_chunk})}\n\n"
                _success = False
                _error_type = "provider_error"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            if "chunk" not in item:
                continue

            chunk = item["chunk"]
            chunk = _sanitize_llm_output(chunk, strip_reasoning=True)
            if BEK_FIX_SPACING_ENABLED:
                chunk = _fix_spacing(chunk)
            if not chunk.strip():
                continue

            full_text_accumulated.append(chunk)
            current_text = "".join(full_text_accumulated)

            if "[ACTION:" in current_text:
                action_detected = True

            if not action_detected and MAX_REASONING_CHARS:
                _reasoning_chars += len(chunk)
                if _reasoning_chars > MAX_REASONING_CHARS:
                    logger.warning(
                        "[Streaming v1.3] 🧠 Réflexion excessive (%d chars > %d) — arrêt.",
                        _reasoning_chars, MAX_REASONING_CHARS,
                    )
                    yield f"data: {json.dumps({'chunk': _MSG_REASONING_OVERFLOW})}\n\n"
                    _success = False
                    _error_type = "reasoning_overflow"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return

            if _loop_detector is not None and not action_detected:
                if _loop_detector.add(chunk):
                    logger.warning(
                        "[Streaming v1.3] 🔁 Boucle détectée (fenêtre=%d, seuil=%d) — arrêt.",
                        LOOP_WINDOW, LOOP_THRESHOLD,
                    )
                    yield f"data: {json.dumps({'chunk': _MSG_LOOP_DETECTED})}\n\n"
                    _success = False
                    _error_type = "loop_detected"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return

            if action_detected and "[/ACTION]" not in current_text:
                chunks_without_close += 1
                if chunks_without_close > cfg.MAX_CHUNKS_WITHOUT_CLOSE:
                    logger.warning(
                        "[Streaming v1.3] Action incomplète après %d chunks — abandon.",
                        chunks_without_close,
                    )
                    warn_incomplete = (
                        "\n\n⚠️ **Action incomplète** détectée. "
                        "Reformulez la demande.\n\n"
                    )
                    yield f"data: {json.dumps({'chunk': warn_incomplete})}\n\n"
                    _success = False
                    _error_type = "incomplete_action"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return

            j_chunk = json.dumps({'chunk': chunk}, ensure_ascii=False)
            yield f"data: {j_chunk}\n\n"

            # EXTRACTION D'ACTION
            if action_detected and not action_was_executed and "[/ACTION]" in current_text:
                action_match = act._extract_first_action(current_text)
                if action_match:
                    act_name = action_match["name"]
                    params = action_match["params"]

                    if act_name == "headless_search":
                        sent_query = params.get("query", "")
                        if val._is_translation(last_user_query, sent_query):
                            logger.warning(
                                "[QueryCorrect] Traduction détectée : '%s' → '%s'",
                                sent_query, last_user_query,
                            )
                            params["query"] = last_user_query

                        try:
                            _should_use_ws = rt._bek_rex_should_use_web_sync(
                                last_user_query, _routing_result,
                            )
                            logger.info(
                                "[PATCH 3.2.b] BEK-REX routing : tier=%s | web_sync=%s",
                                _routing_result.get("tier"),
                                _should_use_ws,
                            )
                            if _should_use_ws:
                                logger.info("[PATCH 3.2.b] Redirection : headless_search → web_sync")
                                act_name = "web_sync"
                                params = {"query": params.get("query", last_user_query)}
                        except Exception as _rex_err:
                            logger.warning("[PATCH 3.2.b] BEK-REX échec : %s", _rex_err)

                    if act_name not in cfg.MULTIMEDIA_ACTIONS:
                        params["provider"] = provider
                        params["model"] = model

                    msg_imm = '\n\n⚙️ *Exécution...*\n'
                    yield f"data: {json.dumps({'chunk': msg_imm})}\n\n"

                    _action_start = time.monotonic()
                    exec_res = act._execute_action_unified(act_name, params)
                    _action_elapsed_ms = (time.monotonic() - _action_start) * 1000
                    res_msg = fmt._format_execution_result(act_name, exec_res)

                    if act_name == "headless_search" and isinstance(exec_res, dict):
                        if exec_res.get("status") == "success":
                            leads = exec_res.get("leads", []) or []
                            if leads:
                                auto_scrape_msg = "\n\n📄 *Extraction du contenu des pages...*\n\n"
                                yield f"data: {json.dumps({'chunk': auto_scrape_msg})}\n\n"
                                try:
                                    auto_scraped_pages = scr._auto_scrape_search_results(
                                        exec_res,
                                        last_user_query or params.get("query", ""),
                                    )
                                except Exception as exc:
                                    logger.warning("[AutoScrape] Échec : %s", exc)
                                    auto_scraped_pages = []

                                if auto_scraped_pages:
                                    pages_msg = f"✅ **{len(auto_scraped_pages)} page(s) extraite(s)**\n\n"
                                    yield f"data: {json.dumps({'chunk': pages_msg})}\n\n"

                    try:
                        from bek_eval_guard import evaluate_response_quality
                        eval_r = evaluate_response_quality(last_user_query, res_msg)
                        if not eval_r["passed"]:
                            res_msg = f"⚠️ [BEK Guard] Filtré : {eval_r['reason']}"
                    except Exception as exc:
                        logger.debug("[EvalGuard] Échec : %s", exc)

                    if st._stair_should_validate(act_name) and st._stair_is_available():
                        try:
                            pages_for_stair = auto_scraped_pages or []
                            if pages_for_stair:
                                toc = st._stair_build_toc(pages_for_stair, last_user_query)
                                if toc:
                                    stair_res = st._stair_validate_response(
                                        res_msg, toc, pages_for_stair,
                                    )
                                    if not stair_res.get("valid", True):
                                        logger.warning(
                                            "[STAIR] Hallucination détectée : %s",
                                            stair_res.get("hallucinations"),
                                        )
                                        res_msg = (
                                            f"⚠️ **Réponse filtrée par BEK-STAIR** : "
                                            f"hallucination détectée "
                                            f"(score {stair_res.get('score', 0):.2f}).\n"
                                            f"→ Reformulez ou demandez une nouvelle recherche."
                                        )
                                    else:
                                        logger.info(
                                            "[STAIR] ✓ Validation OK (score %.2f)",
                                            stair_res.get("score", 1.0),
                                        )
                        except Exception as _stair_err:
                            logger.debug("[STAIR] Échec validation : %s", _stair_err)

                    res_chunk = "\n\n" + str(res_msg) + "\n\n"

                    if auto_scraped_pages:
                        scraped_block = scr._format_auto_scraped_block(auto_scraped_pages)
                        res_chunk += scraped_block

                    yield f"data: {json.dumps({'chunk': res_chunk})}\n\n"

                    total_actions_executed += 1
                    action_was_executed = True
                    last_result_poor = fmt._is_poor_result(exec_res, act_name)

                    # LEVIER 2 — BEK-MEM
                    if BEK_MEM_ENABLED and not last_result_poor:
                        try:
                            _mem_proto_id = rt._bek_mem_store(
                                query=last_user_query,
                                tier=_tier,
                                method=act_name,
                                result_data={
                                    "sources": len(auto_scraped_pages) if auto_scraped_pages else 0,
                                    "action_ms": int(_action_elapsed_ms),
                                },
                            )
                            if _mem_proto_id:
                                logger.info("[Streaming v1.3] BEK-MEM prototype : %s", _mem_proto_id)
                        except Exception as _mem_err:
                            logger.debug("[BEK-MEM] Échec store : %s", _mem_err)

                break

        # SYNTHÈSE
        relance_done = False
        _has_auto_scraped = bool(auto_scraped_pages)
        _needs_synthesis = last_result_poor or _has_auto_scraped

        if _has_auto_scraped:
            logger.info(
                "[PATCH 3D] Synthèse forcée car %d page(s) auto-scrapée(s)",
                len(auto_scraped_pages),
            )

        while (
            _needs_synthesis
            and action_was_executed
            and not relance_done
            and total_actions_executed < cfg.MAX_TOTAL_ACTIONS
        ):
            relance_done = True

            if act_name == "headless_search" and last_result_poor and not _has_auto_scraped:
                fallback_query = last_user_query or params.get("query", "")
                fallback_query = val._extract_keywords(fallback_query)
                logger.info("[Fallback] headless_search pauvre → web_sync('%s')", fallback_query)
                fallback_msg = "\n\n🌐 *Fallback : veille multi-sources...*\n\n"
                yield f"data: {json.dumps({'chunk': fallback_msg})}\n\n"

                exec_res = act._execute_action_unified(
                    "web_sync",
                    {"query": fallback_query, "provider": provider, "model": model},
                )
                res_msg = fmt._format_execution_result("web_sync", exec_res)
                ws_chunk = "\n\n" + str(res_msg) + "\n\n"
                yield f"data: {json.dumps({'chunk': ws_chunk})}\n\n"

                act_name = "web_sync"
                total_actions_executed += 1
                last_result_poor = fmt._is_poor_result(exec_res, act_name)

            synthesis_messages = list(exec_messages) + [
                {
                    "role": "assistant",
                    "content": "".join(full_text_accumulated),
                },
                {
                    "role": "user",
                    "content": (
                        f"[RÉSULTAT DE L'ACTION '{act_name}'] :\n\n"
                        f"{res_msg}\n\n"
                        f"→ Analyse les informations ci-dessus et réponds à ma "
                        f"demande initiale :\n« {last_user_query} »\n\n"
                        f"RÈGLES STRICTES :\n"
                        f"  1. Utilise UNIQUEMENT les informations ci-dessus.\n"
                        f"  2. Si elles sont SUFFISANTES → conclus directement.\n"
                        f"  3. Si elles sont INSUFFISANTES → dis-le honnêtement.\n"
                        f"  4. N'appelle AUCUN outil supplémentaire.\n"
                        f"  5. N'invente RIEN.\n"
                        f"  6. Cite tes sources (URLs) si tu en as.\n"
                        f"  7. Si tu as la réponse, DONNE-LA.\n"
                    ),
                },
            ]

            synth_msg = "\n\n💭 *Synthèse en cours...*\n\n"
            yield f"data: {json.dumps({'chunk': synth_msg})}\n\n"

            _synth_start = time.monotonic()
            _synth_reasoning_chars = 0

            for item2 in provider_manager.execute_chat_stream(
                messages=synthesis_messages,
                provider=provider,
                model=model,
                temperature=0.5,
                max_tokens=2048,
            ):
                if MAX_STREAM_DURATION_SEC and (time.monotonic() - _synth_start) > MAX_STREAM_DURATION_SEC:
                    logger.warning("[Synthèse] ⏱️ Timeout dur atteint — arrêt.")
                    yield f"data: {json.dumps({'chunk': _MSG_SYNTH_TIMEOUT})}\n\n"
                    break

                if "error" in item2:
                    error_msg = item2.get("error", "Erreur inconnue")
                    synth_err = f"\n\n⚠️ Erreur synthèse : {error_msg}\n"
                    yield f"data: {json.dumps({'chunk': synth_err})}\n\n"
                    break

                if "chunk" in item2:
                    chunk2 = _sanitize_llm_output(item2["chunk"], strip_reasoning=True)
                    if BEK_FIX_SPACING_ENABLED:
                        chunk2 = _fix_spacing(chunk2)
                    if chunk2.strip():
                        _synth_reasoning_chars += len(chunk2)
                        if MAX_REASONING_CHARS and _synth_reasoning_chars > MAX_REASONING_CHARS:
                            logger.warning("[Synthèse] 🧠 Réflexion excessive — arrêt.")
                            yield f"data: {json.dumps({'chunk': _MSG_SYNTH_VERBOSE})}\n\n"
                            break

                        if "[ACTION:" in chunk2:
                            logger.warning(
                                "[Synthèse] Action détectée malgré interdiction — ignorée."
                            )
                        else:
                            yield f"data: {json.dumps({'chunk': chunk2}, ensure_ascii=False)}\n\n"

                        full_text_accumulated.append(chunk2)

            break

        # ACTION INCOMPLÈTE
        if action_detected and not action_was_executed:
            logger.warning("[Streaming v1.3] Action détectée mais non exécutée (incomplète).")
            final_incomplete = (
                "\n\n⚠️ **Action incomplète** : le LLM n'a pas fermé sa "
                "balise [/ACTION]. Reformulez la demande.\n\n"
            )
            yield f"data: {json.dumps({'chunk': final_incomplete})}\n\n"

        _total_elapsed = time.monotonic() - _start_time
        logger.info(
            "[Streaming v1.3] ✓ Terminé en %.2fs | actions=%d | chunks=%d",
            _total_elapsed, total_actions_executed, len(full_text_accumulated),
        )

    except Exception as stream_err:
        logger.error("[Streaming v1.3] Erreur : %s", stream_err, exc_info=True)
        err_msg = f"\n\n⚠️ Flux Error : {stream_err}\n"
        yield f"data: {json.dumps({'chunk': err_msg})}\n\n"
        _success = False
        _error_type = type(stream_err).__name__

    finally:
        # LEVIER 4 — BEK-LOOP
        try:
            _total_elapsed_final = time.monotonic() - _start_time

            if BEK_LOOP_ENABLED and not _cached_response_served and last_user_query:
                rt._bek_loop_record(
                    query=last_user_query,
                    tier=_routing_result.get("tier", "TIER_3"),
                    provider=provider,
                    model=model,
                    success=_success,
                    time_ms=_total_elapsed_final * 1000,
                    error_type=_error_type,
                )
                logger.info(
                    "[Streaming v1.3] BEK-LOOP épisode enregistré (%.0fms, success=%s)",
                    _total_elapsed_final * 1000, _success,
                )

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
                        logger.info(
                            "[Streaming v1.3] BEK-ECO réponse mise en cache (%d chars)",
                            len(final_response),
                        )
                except Exception as _cache_store_err:
                    logger.debug("[BEK-ECO] Échec store final : %s", _cache_store_err)

            if BEK_MEM_ENABLED and _mem_proto_id:
                try:
                    rt._bek_mem_update(
                        prototype_id=_mem_proto_id,
                        success=_success,
                        time_ms=_total_elapsed_final * 1000,
                    )
                except Exception as _mem_upd_err:
                    logger.debug("[BEK-MEM] Échec update : %s", _mem_upd_err)

        except Exception as _loop_err:
            logger.debug("[Streaming v1.3] Erreur finally : %s", _loop_err)

        yield f"data: {json.dumps({'done': True})}\n\n"


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ══════════════════════════════════════════════════════════════════════════════

def get_streaming_summary() -> dict:
    return {
        "version": "1.3.2",
        "functions": [
            "_sanitize_llm_output",
            "_strip_reasoning",
            "_fix_spacing",
            "stream_chat",
        ],
        "uses_modules": [
            "config", "validation", "actions", "formatters",
            "routing", "scrape", "stair",
        ],
        "leviers_v1_3": {
            "bek_eco_cache": "✅ branché (avant appel LLM)",
            "bek_mem_prototypes": "✅ branché (après web_sync)",
            "bek_rex_routing": "✅ branché",
            "bek_loop_feedback": "✅ branché (dans finally)",
        },
        "flags_activation": {
            "BEK_ECO_CACHE_ENABLED": BEK_ECO_CACHE_ENABLED,
            "BEK_MEM_ENABLED": BEK_MEM_ENABLED,
            "BEK_LOOP_ENABLED": BEK_LOOP_ENABLED,
            "BEK_FIX_SPACING_ENABLED": BEK_FIX_SPACING_ENABLED,
        },
        "garde_fous_v1_2": {
            "timeout_dur": f"{MAX_STREAM_DURATION_SEC}s (env: BEK_STREAM_TIMEOUT_SEC)",
            "loop_detection": f"window={LOOP_WINDOW}, threshold={LOOP_THRESHOLD}",
            "reasoning_limit": f"{MAX_REASONING_CHARS} chars",
        },
    }