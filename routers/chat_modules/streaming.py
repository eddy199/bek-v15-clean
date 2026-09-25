# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Streaming
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Streaming SSE du chat (chunks + actions + synthèse)
# 📄 Doc : docs/BEK_LVC.md
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.2
# Date : 2026-09-26
# ------------------------------------------------------------------------------
# ★ v1.1 — Connecteurs branchés :
#   - Connecteur 2 : BEK-STAIR (anti-hallucination)
#   - Filtre reasoning (thinking exposé)
#
# ★ v1.2 — CORRECTIFS ANTI-BOUCLE (2026-09-26) :
#   - Correctif A : Timeout dur sur le stream (env: BEK_STREAM_TIMEOUT_SEC)
#   - Correctif B : Détection de répétition (env: BEK_LOOP_DETECT_ENABLED)
#   - Correctif C : Limite de reasoning sans action (env: BEK_MAX_REASONING_CHARS)
#   - Filtre reasoning renforcé (patterns conversationnels FR/EN)
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
# ★ v1.2 — GARDE-FOUS ANTI-BOUCLE (configurables par env)
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


# Timeout dur du stream complet (secondes). 0 = désactivé.
MAX_STREAM_DURATION_SEC = _env_int("BEK_STREAM_TIMEOUT_SEC", 120, minimum=10)

# Détection de répétition (boucles de chunks identiques).
LOOP_DETECT_ENABLED = _env_bool("BEK_LOOP_DETECT_ENABLED", True)
LOOP_WINDOW = _env_int("BEK_LOOP_WINDOW", 15, minimum=5)
LOOP_THRESHOLD = _env_int("BEK_LOOP_THRESHOLD", 4, minimum=2)

# Limite de reasoning sans action (chars). 0 = désactivé.
MAX_REASONING_CHARS = _env_int("BEK_MAX_REASONING_CHARS", 6000, minimum=500)


# ══════════════════════════════════════════════════════════════════════════════
# NETTOYAGE DES TOKENS LLM
# ══════════════════════════════════════════════════════════════════════════════

_LLM_NATIVE_TOKENS = (
    "<|tool_call_begin|>", "<|tool_call_end|>",
    "<|tool_call_argument_begin|>", "<|tool_call_argument_end|>",
    "<|tool_call|>", "<|tool_sep|>",
    "<|tool_calls_section_begin|>", "<|tool_calls_section_end|>",
)

_LLM_NATIVE_REGEX = _re.compile(
    "|".join(_re.escape(t) for t in _LLM_NATIVE_TOKENS),
)
_LLM_XML_TOOL_REGEX = _re.compile(r"<tool_call>.*?</tool_call>", _re.DOTALL)


# ══════════════════════════════════════════════════════════════════════════════
# ★ FILTRE REASONING (v1.2 — renforcé avec patterns conversationnels)
# ------------------------------------------------------------------------------
# Bloque les patterns de raisonnement interne exposés par le LLM.
# v1.2 : ajoute les patterns "Attendez...", "J'y ai réfléchi...", etc.
# ==============================================================================

_THINKING_PATTERNS = (
    # ─── Balises explicites ───
    _re.compile(r"<think>.*?</think>", _re.DOTALL | _re.IGNORECASE),
    _re.compile(r"<thinking>.*?</thinking>", _re.DOTALL | _re.IGNORECASE),
    _re.compile(r"<reasoning>.*?</reasoning>", _re.DOTALL | _re.IGNORECASE),

    # ─── Débuts de reasoning classiques (EN) ───
    _re.compile(
        r"^(?:Okay|OK|Alright|Let me|Let's|I need to|I should|I will|"
        r"I'm going to|First,|Hmm,|Wait,|Actually,|So,)\s+"
        r"(?:the user|I|we|check|see|look|think|consider|analyze).*?"
        r"(?=\n\n|\[ACTION:|\Z)",
        _re.DOTALL | _re.IGNORECASE | _re.MULTILINE,
    ),

    # ─── ★ v1.2 : Patterns conversationnels FR ───
    _re.compile(
        r"^(?:Attends?|Attendez|Hmm+|Bizarre|Bon|Alors|Voyons|Vérifions)\s*,?\s*"
        r"(?:je|il|elle|on|nous|tu|vous|ça|cela|ceci)\s+.*?$",
        _re.MULTILINE | _re.IGNORECASE,
    ),
    _re.compile(
        r"^J'y ai réfléchi.*?(?=\n\n|\Z)",
        _re.DOTALL | _re.IGNORECASE,
    ),
    _re.compile(
        r"^(?:En fait|Cependant|Toutefois)\s*,\s+"
        r"(?:je|il|elle|on|nous)\s+.*?$",
        _re.MULTILINE | _re.IGNORECASE,
    ),
    _re.compile(
        r"^(?:Il y a|Il est|C'est)\s+(?:un conflit|un problème|délicat|ambigu|"
        r"possible que|probable que).*?$",
        _re.MULTILINE | _re.IGNORECASE,
    ),

    # ─── Bloc entièrement en italique markdown entourant du reasoning ───
    _re.compile(
        r"^\*(?:Attends?|Vérifions|Analysons|Réfléchissons|Hmm)\b.*?\*$",
        _re.MULTILINE | _re.IGNORECASE,
    ),
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
    """
    Retire le raisonnement interne exposé par le LLM.

    v1.2 : patterns conversationnels renforcés (FR + EN).
    """
    if not text:
        return text

    # Balises explicites
    for pattern in _THINKING_PATTERNS:
        text = pattern.sub("", text)

    # Lignes de reasoning isolées
    for pattern in _THINKING_LINE_PATTERNS:
        text = pattern.sub("", text)

    # Nettoyage des lignes vides multiples
    text = _re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _sanitize_llm_output(text: str, strip_reasoning: bool = True) -> str:
    """
    Nettoie les tokens natifs du LLM + reasoning.
    """
    if not text:
        return text

    text = _LLM_NATIVE_REGEX.sub("", text)
    text = _LLM_XML_TOOL_REGEX.sub("", text)

    if strip_reasoning:
        text = _strip_reasoning(text)

    return text


# ══════════════════════════════════════════════════════════════════════════════
# ★ v1.2 — DÉTECTEUR DE BOUCLE (répétitions de chunks)
# ══════════════════════════════════════════════════════════════════════════════

class _LoopDetector:
    """
    Détecte les boucles de raisonnement via répétition de chunks normalisés.

    Mécanisme : conserve les N derniers chunks normalisés, et déclenche
    si un même chunk apparaît >= LOOP_THRESHOLD fois dans la fenêtre.
    """

    def __init__(self, window: int = LOOP_WINDOW, threshold: int = LOOP_THRESHOLD):
        self.window = window
        self.threshold = threshold
        self._buffer: List[str] = []

    def add(self, chunk: str) -> bool:
        """
        Ajoute un chunk et retourne True si une boucle est détectée.
        """
        if not chunk:
            return False

        # Normalisation légère : strip + lowercase + troncature
        normalized = chunk.strip().lower()[:80]
        if not normalized or len(normalized) < 5:
            # Trop court pour être significatif
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
# ══════════════════════════════════════════════════════════════════════════════

async def stream_chat(
    exec_messages: List[Dict[str, Any]],
    trimmed_messages: List[Dict[str, Any]],
    last_user_query: str,
    provider: str,
    model: str,
) -> AsyncGenerator[str, None]:
    """
    Génère le flux SSE complet pour une requête de chat.

    v1.2 : intègre timeout dur + détection de boucle + limite reasoning.
    """
    from provider_manager import provider_manager

    # ─── ÉTAT ───
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

    # ★ v1.2 — Garde-fous
    _start_time = time.monotonic()
    _reasoning_chars = 0
    _loop_detector = _LoopDetector() if LOOP_DETECT_ENABLED else None

    # Détection fraîcheur
    is_freshness_query = rt._bek_rex_is_freshness_query(last_user_query)
    if is_freshness_query:
        logger.info("[Streaming] Requête de fraîcheur détectée")

    try:
        # ══════════════════════════════════════════════════════════════════════
        # BOUCLE PRINCIPALE — Stream du LLM
        # ══════════════════════════════════════════════════════════════════════
        for item in provider_manager.execute_chat_stream(
            messages=exec_messages,
            provider=provider,
            model=model,
            temperature=0.7,
            max_tokens=4096,
        ):
            # ─── CORRECTIF A : Timeout dur ───
            _elapsed = time.monotonic() - _start_time
            if MAX_STREAM_DURATION_SEC and _elapsed > MAX_STREAM_DURATION_SEC:
                logger.warning(
                    "[Streaming] ⏱️ Timeout dur atteint (%.1fs > %ds) — arrêt.",
                    _elapsed, MAX_STREAM_DURATION_SEC,
                )
                yield f"data: {json.dumps({'chunk': '\n\n⏱️ **Délai dépassé** — réponse interrompue.'})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            if "error" in item:
                error_msg = item.get("error", "Erreur inconnue")
                logger.error("[ProviderManager] Erreur : %s", error_msg)
                err_chunk = f"\n\n⚠️ **Erreur provider** : {error_msg}\n\n"
                yield f"data: {json.dumps({'chunk': err_chunk})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            if "chunk" not in item:
                continue

            chunk = item["chunk"]
            chunk = _sanitize_llm_output(chunk, strip_reasoning=True)
            if not chunk.strip():
                continue

            full_text_accumulated.append(chunk)
            current_text = "".join(full_text_accumulated)

            if "[ACTION:" in current_text:
                action_detected = True

            # ─── CORRECTIF C : Limite de reasoning sans action ───
            if not action_detected and MAX_REASONING_CHARS:
                _reasoning_chars += len(chunk)
                if _reasoning_chars > MAX_REASONING_CHARS:
                    logger.warning(
                        "[Streaming] 🧠 Réflexion excessive (%d chars > %d) — arrêt.",
                        _reasoning_chars, MAX_REASONING_CHARS,
                    )
                    yield f"data: {json.dumps({'chunk': '\n\n🧠 **Réflexion excessive** — arrêt automatique. Reformulez la demande.'})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return

            # ─── CORRECTIF B : Détection de boucle ───
            if _loop_detector is not None and not action_detected:
                if _loop_detector.add(chunk):
                    logger.warning(
                        "[Streaming] 🔁 Boucle détectée (fenêtre=%d, seuil=%d) — arrêt.",
                        LOOP_WINDOW, LOOP_THRESHOLD,
                    )
                    yield f"data: {json.dumps({'chunk': '\n\n🔁 **Boucle détectée** — arrêt automatique. Reformulez la demande.'})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return

            # Détection action incomplète
            if action_detected and "[/ACTION]" not in current_text:
                chunks_without_close += 1
                if chunks_without_close > cfg.MAX_CHUNKS_WITHOUT_CLOSE:
                    logger.warning(
                        "[Streaming] Action incomplète après %d chunks — abandon.",
                        chunks_without_close,
                    )
                    warn_incomplete = (
                        "\n\n⚠️ **Action incomplète** détectée. "
                        "Reformulez la demande.\n\n"
                    )
                    yield f"data: {json.dumps({'chunk': warn_incomplete})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return

            # Envoi du chunk brut
            j_chunk = json.dumps({'chunk': chunk}, ensure_ascii=False)
            yield f"data: {j_chunk}\n\n"

            # ─── EXTRACTION ET EXÉCUTION D'ACTION ───
            if action_detected and not action_was_executed and "[/ACTION]" in current_text:
                action_match = act._extract_first_action(current_text)
                if action_match:
                    act_name = action_match["name"]
                    params = action_match["params"]

                    # Correction traduction
                    if act_name == "headless_search":
                        sent_query = params.get("query", "")
                        if val._is_translation(last_user_query, sent_query):
                            logger.warning(
                                "[QueryCorrect] Traduction détectée : '%s' → '%s'",
                                sent_query, last_user_query,
                            )
                            params["query"] = last_user_query

                        try:
                            _routing = rt._bek_rex_route(last_user_query)
                            _should_use_ws = rt._bek_rex_should_use_web_sync(
                                last_user_query, _routing,
                            )
                            logger.info(
                                "[PATCH 3.2.b] BEK-REX routing : tier=%s | web_sync=%s | source=%s",
                                _routing.get("tier"),
                                _should_use_ws,
                                _routing.get("source"),
                            )
                            if _should_use_ws:
                                logger.info(
                                    "[PATCH 3.2.b] Redirection : headless_search → web_sync"
                                )
                                act_name = "web_sync"
                                params = {
                                    "query": params.get("query", last_user_query),
                                }
                        except Exception as _rex_err:
                            logger.warning(
                                "[PATCH 3.2.b] BEK-REX échec : %s",
                                _rex_err,
                            )

                    if act_name not in cfg.MULTIMEDIA_ACTIONS:
                        params["provider"] = provider
                        params["model"] = model

                    msg_imm = '\n\n⚙️ *Exécution...*\n'
                    yield f"data: {json.dumps({'chunk': msg_imm})}\n\n"

                    # ─── EXÉCUTION ───
                    exec_res = act._execute_action_unified(act_name, params)
                    res_msg = fmt._format_execution_result(act_name, exec_res)

                    # ─── AUTO-SCRAPE ───
                    if act_name == "headless_search" and isinstance(exec_res, dict):
                        if exec_res.get("status") == "success":
                            leads = exec_res.get("leads", []) or []
                            if leads:
                                auto_scrape_msg = (
                                    "\n\n📄 *Extraction du contenu des pages...*\n\n"
                                )
                                yield f"data: {json.dumps({'chunk': auto_scrape_msg})}\n\n"
                                try:
                                    auto_scraped_pages = scr._auto_scrape_search_results(
                                        exec_res,
                                        last_user_query or params.get("query", ""),
                                    )
                                except Exception as exc:
                                    logger.warning(
                                        "[AutoScrape] Échec : %s", exc,
                                    )
                                    auto_scraped_pages = []

                                if auto_scraped_pages:
                                    pages_msg = (
                                        f"✅ **{len(auto_scraped_pages)} page(s) "
                                        f"extraite(s)**\n\n"
                                    )
                                    yield f"data: {json.dumps({'chunk': pages_msg})}\n\n"

                    # ─── ÉVALUATION QUALITÉ ───
                    try:
                        from bek_eval_guard import evaluate_response_quality
                        eval_r = evaluate_response_quality(last_user_query, res_msg)
                        if not eval_r["passed"]:
                            res_msg = f"⚠️ [BEK Guard] Filtré : {eval_r['reason']}"
                    except Exception as exc:
                        logger.debug("[EvalGuard] Échec : %s", exc)

                    # ─── BEK-STAIR ───
                    if st._stair_should_validate(act_name) and st._stair_is_available():
                        try:
                            pages_for_stair = auto_scraped_pages or []
                            if pages_for_stair:
                                toc = st._stair_build_toc(
                                    pages_for_stair, last_user_query,
                                )
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
                        scraped_block = scr._format_auto_scraped_block(
                            auto_scraped_pages,
                        )
                        res_chunk += scraped_block

                    yield f"data: {json.dumps({'chunk': res_chunk})}\n\n"

                    total_actions_executed += 1
                    action_was_executed = True
                    last_result_poor = fmt._is_poor_result(exec_res, act_name)

                break

        # ══════════════════════════════════════════════════════════════════════
        # SYNTHÈSE (PATCH 3D)
        # ══════════════════════════════════════════════════════════════════════
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

            # Fallback web_sync si pauvre ET pas de scrape
            if act_name == "headless_search" and last_result_poor and not _has_auto_scraped:
                fallback_query = last_user_query or params.get("query", "")
                fallback_query = val._extract_keywords(fallback_query)
                logger.info(
                    "[Fallback] headless_search pauvre → web_sync('%s')",
                    fallback_query,
                )
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

            # ─── MESSAGE DE SYNTHÈSE ───
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
                # ★ v1.2 : Timeout dur sur la synthèse aussi
                if MAX_STREAM_DURATION_SEC and (time.monotonic() - _synth_start) > MAX_STREAM_DURATION_SEC:
                    logger.warning("[Synthèse] ⏱️ Timeout dur atteint — arrêt.")
                    yield f"data: {json.dumps({'chunk': '\n\n⏱️ Synthèse trop longue — interrompue.'})}\n\n"
                    break

                if "error" in item2:
                    error_msg = item2.get("error", "Erreur inconnue")
                    synth_err = f"\n\n⚠️ Erreur synthèse : {error_msg}\n"
                    yield f"data: {json.dumps({'chunk': synth_err})}\n\n"
                    break

                if "chunk" in item2:
                    chunk2 = _sanitize_llm_output(
                        item2["chunk"], strip_reasoning=True,
                    )
                    if chunk2.strip():
                        # ★ v1.2 : limite reasoning dans la synthèse aussi
                        _synth_reasoning_chars += len(chunk2)
                        if MAX_REASONING_CHARS and _synth_reasoning_chars > MAX_REASONING_CHARS:
                            logger.warning("[Synthèse] 🧠 Réflexion excessive — arrêt.")
                            yield f"data: {json.dumps({'chunk': '\n\n🧠 Synthèse trop verbeuse — arrêt.'})}\n\n"
                            break

                        if "[ACTION:" in chunk2:
                            logger.warning(
                                "[Synthèse] Action détectée malgré interdiction — ignorée."
                            )
                        else:
                            yield f"data: {json.dumps({'chunk': chunk2}, ensure_ascii=False)}\n\n"

            break

        # ══════════════════════════════════════════════════════════════════════
        # ACTION INCOMPLÈTE
        # ══════════════════════════════════════════════════════════════════════
        if action_detected and not action_was_executed:
            logger.warning(
                "[Streaming] Action détectée mais non exécutée (incomplète)."
            )
            final_incomplete = (
                "\n\n⚠️ **Action incomplète** : le LLM n'a pas fermé sa "
                "balise [/ACTION]. Reformulez la demande.\n\n"
            )
            yield f"data: {json.dumps({'chunk': final_incomplete})}\n\n"

        # ══════════════════════════════════════════════════════════════════════
        # FIN
        # ══════════════════════════════════════════════════════════════════════
        _total_elapsed = time.monotonic() - _start_time
        logger.info(
            "[Streaming] ✓ Terminé en %.2fs | actions=%d | chunks=%d",
            _total_elapsed, total_actions_executed, len(full_text_accumulated),
        )
        yield f"data: {json.dumps({'done': True})}\n\n"

    except Exception as stream_err:
        logger.error("[Streaming] Erreur : %s", stream_err, exc_info=True)
        err_msg = f"\n\n⚠️ Flux Error : {stream_err}\n"
        yield f"data: {json.dumps({'chunk': err_msg})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ══════════════════════════════════════════════════════════════════════════════

def get_streaming_summary() -> dict:
    """Résumé du module streaming."""
    return {
        "version": "1.2",
        "functions": [
            "_sanitize_llm_output",
            "_strip_reasoning",
            "stream_chat",
        ],
        "uses_modules": [
            "config", "validation", "actions", "formatters",
            "routing", "scrape", "stair",
        ],
        "connecteurs": {
            "bek_stair": "✅ branché (anti-hallucination)",
            "filtre_reasoning": "✅ renforcé (FR + EN)",
            "loop_detector": "✅ actif",
            "episode_logger": "✅ via actions.py",
            "dag_engine": "✅ via actions.py",
        },
        "garde_fous_v1_2": {
            "timeout_dur": f"{MAX_STREAM_DURATION_SEC}s (env: BEK_STREAM_TIMEOUT_SEC)",
            "loop_detection": f"window={LOOP_WINDOW}, threshold={LOOP_THRESHOLD} (env: BEK_LOOP_*)",
            "reasoning_limit": f"{MAX_REASONING_CHARS} chars (env: BEK_MAX_REASONING_CHARS)",
        },
        "headless_search": "redirigé vers web_sync",
        "freshness_detection": True,
    }