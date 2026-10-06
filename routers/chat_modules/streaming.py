# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Streaming (v1.6.4)
# ------------------------------------------------------------------------------
# ★ v1.6.4 (2026-10-07) : RÉDUCTION TOKENS POUR GROQ FREE
#   - max_tokens : 4096 → 2048 (réduit la taille de la réponse)
#   - Troncature de sécurité des messages > 3000 chars avant envoi LLM
#   - Log de la taille totale de la requête (diagnostic 413)
#   - Fix préventif contre "Request too large for model openai/gpt-oss-120b"
# ★ v1.6.3 : Fix "Décriscette" collé
# ★ v1.6.2 : Fix regex qui cassait les mots
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
# ★ v1.6.4 — TRONCATURE DE SÉCURITÉ (anti-413)
# ==============================================================================

def _truncate_messages_for_groq(
    messages: List[Dict[str, Any]],
    max_chars_per_msg: int = 3000,
    max_total_chars: int = 10000,
) -> List[Dict[str, Any]]:
    """
    ★ v1.6.4 — Tronque les messages avant envoi au LLM.

    Groq Free tier limite à 8000 tokens/minute (~24000 chars).
    On garde une marge de sécurité en limitant à 10000 chars total.

    Stratégie :
      1. Tronque chaque message à `max_chars_per_msg`
      2. Si le total dépasse `max_total_chars`, garde les derniers messages
         (les plus récents) et drop les plus anciens
    """
    if not messages:
        return messages

    # ─── 1. Troncature par message ───
    truncated = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", "")
        if isinstance(content, str) and len(content) > max_chars_per_msg:
            # Coupe le milieu pour préserver début + fin
            half = max_chars_per_msg // 2
            content = (
                content[:half]
                + "\n\n[...tronqué...]\n\n"
                + content[-half:]
            )
            msg = {**msg, "content": content}
        truncated.append(msg)

    # ─── 2. Troncature globale (garde la fin) ───
    total = sum(len(m.get("content", "")) for m in truncated)
    if total <= max_total_chars:
        return truncated

    # Garde le system prompt + les derniers messages
    system_msgs = [m for m in truncated if m.get("role") == "system"]
    other_msgs = [m for m in truncated if m.get("role") != "system"]

    system_chars = sum(len(m.get("content", "")) for m in system_msgs)
    budget = max_total_chars - system_chars

    kept = []
    running = 0
    for msg in reversed(other_msgs):
        msg_len = len(msg.get("content", ""))
        if running + msg_len > budget:
            break
        kept.insert(0, msg)
        running += msg_len

    result = system_msgs + kept

    logger.warning(
        "[Streaming v1.6.4] Troncature : %d → %d messages | %d → %d chars",
        len(messages), len(result), total, sum(len(m.get("content", "")) for m in result),
    )
    return result


# ══════════════════════════════════════════════════════════════════════════════
# ★ v1.6.3 — NORMALISATION DES STRINGS LLM
# ══════════════════════════════════════════════════════════════════════════════

_NORMALIZE_PATTERNS = [
    # ─── Collisions AI ───
    (r'\baistartup\b', 'AI startup'),
    (r'\baimodel\b', 'AI model'),
    (r'\baicompany\b', 'AI company'),
    (r'\baibusiness\b', 'AI business'),
    (r'\baiassistant\b', 'AI assistant'),
    (r'\baichat\b', 'AI chat'),
    (r'\baitool\b', 'AI tool'),

    # ─── Fix vision ───
    (r'\bdécriscette\b', 'décris cette'),
    (r'\bdecriscette\b', 'decris cette'),
    (r'\bdécriscetimage\b', 'décris cette image'),
    (r'\bdecriscetimage\b', 'decris cette image'),
    (r'\bdécriscetteimage\b', 'décris cette image'),
    (r'\bdecriscetteimage\b', 'decris cette image'),
    (r'\bexpliquecette\b', 'explique cette'),
    (r'\banalysecette\b', 'analyse cette'),
    (r'\banalysecet\b', 'analyse cet'),
    (r'\bregardecette\b', 'regarde cette'),
    (r'\bmontrecette\b', 'montre cette'),
    (r'\bdécrisce\b', 'décris ce'),
    (r'\bdecrisce\b', 'decris ce'),

    # ─── Autres mots collés ───
    (r'\bsleeklogo\b', 'sleek logo'),
    (r'\bmodernlogo\b', 'modern logo'),
    (r'\bminimalistlogo\b', 'minimalist logo'),
    (r'\bsimplelogo\b', 'simple logo'),
    (r'\blogofora\b', 'logo for a'),
    (r'\blogofor\b', 'logo for'),
    (r'\blogowith\b', 'logo with'),
    (r'\bforatech\b', 'for a tech'),
    (r'\btechstartup\b', 'tech startup'),
    (r'\bstartupcompany\b', 'startup company'),
    (r'\bmodernsleek\b', 'modern sleek'),
    (r'\bfeaturingabstract\b', 'featuring abstract'),
    (r'\bcircuitrypatterns\b', 'circuitry patterns'),
    (r'\bcircuitpatterns\b', 'circuit patterns'),
    (r'\bcircuitpattern\b', 'circuit pattern'),
    (r'\bformingastylized\b', 'forming a stylized'),
    (r'\bwithagradient\b', 'with a gradient'),
    (r'\bofelectricblue\b', 'of electric blue'),
    (r'\bandneongreen\b', 'and neon green'),
    (r'\bneongreen\b', 'neon green'),
    (r'\belectricblue\b', 'electric blue'),
    (r'\bonelectricblue\b', 'on electric blue'),
    (r'\bonadarkbackground\b', 'on a dark background'),
    (r'\bdarkbackground\b', 'dark background'),
    (r'\bonwhitebackground\b', 'on white background'),
    (r'\bminimalisticand\b', 'minimalistic and'),
    (r'\bfuturisticdesign\b', 'futuristic design'),
    (r'\bhighcontrast\b', 'high contrast'),
    (r'\bvectorstyle\b', 'vector style'),
    (r'\bcleanlines\b', 'clean lines'),
    (r'\bbluecolor\b', 'blue color'),
    (r'\bbluecolour\b', 'blue colour'),
    (r'\bsuitablefor\b', 'suitable for'),
    (r'\bhighquality\b', 'high quality'),
    (r'\bdetaileddesign\b', 'detailed design'),
    (r'\bsoftlighting\b', 'soft lighting'),
    (r'\bstudiolighting\b', 'studio lighting'),
    (r'\bdigitalart\b', 'digital art'),
    (r'\bconceptart\b', 'concept art'),
    (r'\bcharacterdesign\b', 'character design'),
    (r'\bcolorson\b', 'colors on'),
    (r'\bcolorsona\b', 'colors on a'),
    (r'\bfora\b', 'for a'),
    (r'\bforan\b', 'for an'),
]


def _normalize_llm_string(text: str) -> str:
    """Normalise une string générée par le LLM."""
    if not text or not isinstance(text, str):
        return text

    if text.startswith(("http://", "https://", "/", "./", "data:")):
        return text
    if text.startswith("{") and text.endswith("}"):
        return text

    result = text

    for pattern, replacement in _NORMALIZE_PATTERNS:
        result = _re.sub(pattern, replacement, result, flags=_re.IGNORECASE)

    result = _re.sub(r',([^\s])', r', \1', result)
    result = _re.sub(r'([a-zà-ÿ])([A-ZÀ-Ý])', r'\1 \2', result)
    result = _re.sub(r'([a-zA-Z]):([^\s/])', r'\1: \2', result)
    result = _re.sub(r'\s+', ' ', result).strip()
    result = _re.sub(r'\s+([,;:.!?])', r'\1', result)

    return result


def _normalize_action_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise récursivement les params d'une action."""
    if not isinstance(params, dict):
        return params

    skip_keys = {
        "provider", "model", "url", "endpoint",
        "image_path", "video_path", "file_path", "path",
        "zip_path", "output_filename", "output_path",
        "id", "record_id", "seed",
    }

    normalized: Dict[str, Any] = {}
    for k, v in params.items():
        if k in skip_keys:
            normalized[k] = v
        elif isinstance(v, str):
            normalized[k] = _normalize_llm_string(v)
        elif isinstance(v, dict):
            normalized[k] = _normalize_action_params(v)
        elif isinstance(v, list):
            normalized[k] = [
                _normalize_llm_string(item) if isinstance(item, str) else item
                for item in v
            ]
        else:
            normalized[k] = v

    return normalized


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
BEK_FIX_SPACING_ENABLED = _env_bool("BEK_FIX_SPACING_ENABLED", False)

BEK_MULTI_ACTIONS_ENABLED = _env_bool("BEK_MULTI_ACTIONS_ENABLED", True)
BEK_MAX_ACTIONS_PER_RESPONSE = _env_int("BEK_MAX_ACTIONS_PER_RESPONSE", 5)

BEK_ANTIHALLU_ENABLED = _env_bool("BEK_ANTIHALLU_ENABLED", True)
BEK_POST_ACTION_GRACE_MAX = _env_int("BEK_POST_ACTION_GRACE_MAX", 50, minimum=10)

# ★ v1.6.4 — max_tokens réduit pour Groq Free
BEK_MAX_TOKENS = _env_int("BEK_MAX_TOKENS", 2048, minimum=256)


_MSG_TIMEOUT_DUR = "\n\n⏱️ **Délai dépassé** — réponse interrompue."
_MSG_REASONING_OVERFLOW = "\n\n🧠 **Réflexion excessive** — arrêt automatique."
_MSG_LOOP_DETECTED = "\n\n🔁 **Boucle détectée** — arrêt automatique."


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
    # ★ v1.6.4 — TRONCATURE DE SÉCURITÉ AVANT ENVOI
    # ==========================================================================
    _total_before = sum(len(m.get("content", "")) for m in exec_messages if isinstance(m, dict))
    exec_messages = _truncate_messages_for_groq(
        exec_messages,
        max_chars_per_msg=cfg.MAX_CHARS_PER_MESSAGE,
        max_total_chars=cfg.MAX_TOTAL_CHARS,
    )
    _total_after = sum(len(m.get("content", "")) for m in exec_messages if isinstance(m, dict))
    logger.info(
        "[Streaming v1.6.4] Requête : %d messages | %d → %d chars (limite %d)",
        len(exec_messages), _total_before, _total_after, cfg.MAX_TOTAL_CHARS,
    )

    # ══════════════════════════════════════════════════════════════════
    # PRÉ-PARSING
    # ==========================================================================
    _user_part = last_user_query or ""
    _instr_pos = _user_part.find("(INSTRUCTION SYSTEME")
    if _instr_pos > 0:
        _user_part = _user_part[:_instr_pos]

    _user_actions = _find_all_complete_actions(_user_part)

    if _user_actions:
        logger.info(
            "[Streaming v1.6.4] %d action(s) utilisateur — exécution DIRECTE",
            len(_user_actions),
        )
        _direct_msg = "\n\n⚙️ *Exécution directe...*\n\n"
        yield f"data: {json.dumps({'chunk': _direct_msg})}\n\n"

        for _idx, _ua in enumerate(_user_actions, 1):
            _ua_name = _ua["name"]
            _ua_params = _normalize_action_params(_ua["params"])

            if _ua_name not in cfg.MULTIMEDIA_ACTIONS:
                _ua_params["provider"] = provider
                _ua_params["model"] = model

            logger.info(
                "[Streaming v1.6.4] 🎯 Action directe %d : %s",
                _idx, _ua_name,
            )
            _exec_msg = f"\n\n⚙️ *Exécution {_idx}...*\n"
            yield f"data: {json.dumps({'chunk': _exec_msg})}\n\n"

            _t0 = time.monotonic()
            try:
                _exec_res = act._execute_action_unified(_ua_name, _ua_params)
                _elapsed = (time.monotonic() - _t0) * 1000
                _res_msg = fmt._format_execution_result(_ua_name, _exec_res)
                logger.info(
                    "[Streaming v1.6.4] ✅ Action %s terminée (%.0fms)",
                    _ua_name, _elapsed,
                )
                _res_chunk = "\n\n" + str(_res_msg) + "\n\n"
                yield f"data: {json.dumps({'chunk': _res_chunk})}\n\n"
            except Exception as _err:
                logger.exception("[Streaming v1.6.4] Action %s échouée", _ua_name)
                _err_chunk = f"\n\n⚠️ Erreur action {_ua_name} : {_err}\n\n"
                yield f"data: {json.dumps({'chunk': _err_chunk})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"
        return

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
        logger.info("[Streaming v1.6.4] Requête de fraîcheur détectée")

    _detected_ego = rt._bek_rex_detect_alter_ego(last_user_query)
    if _detected_ego and _detected_ego != "bek":
        logger.info("[Streaming v1.6.4] 🎭 Alter ego activé : %s", _detected_ego)
        _alter_ego_prompt = rt._bek_rex_get_alter_ego_prompt(_detected_ego)
        if _alter_ego_prompt:
            for _msg in exec_messages:
                if _msg.get("role") == "system":
                    _msg["content"] = _alter_ego_prompt + "\n\n" + _msg.get("content", "")
                    break

    try:
        try:
            _routing_result = rt._bek_rex_route(last_user_query)
            logger.info(
                "[Streaming v1.6.4] BEK-REX tier=%s conf=%.2f",
                _routing_result.get("tier"),
                _routing_result.get("confidence", 0.0),
            )
        except Exception as _rex_err:
            logger.warning("[Streaming v1.6.4] BEK-REX échec : %s", _rex_err)
            _routing_result = {"tier": "TIER_3", "confidence": 0.5}

        _tier = _routing_result.get("tier", "TIER_3")

        if BEK_ECO_CACHE_ENABLED and last_user_query:
            try:
                _eco_result = rt._bek_eco_check_cache(last_user_query, _tier)
                if _eco_result.get("cached") and _eco_result.get("cached_value"):
                    cached_response = _eco_result["cached_value"].get("response", "")
                    if cached_response:
                        _cached_response_served = True
                        cache_badge = "⚡ *[réponse en cache]*\n\n"
                        yield f"data: {json.dumps({'chunk': cache_badge}, ensure_ascii=False)}\n\n"
                        CHUNK_SIZE = 80
                        for i in range(0, len(cached_response), CHUNK_SIZE):
                            piece = cached_response[i:i + CHUNK_SIZE]
                            yield f"data: {json.dumps({'chunk': piece}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        return
            except Exception as _eco_err:
                logger.warning("[Streaming v1.6.4] BEK-ECO échec : %s", _eco_err)

        # ★ v1.6.4 — max_tokens réduit
        for item in provider_manager.execute_chat_stream(
            messages=exec_messages,
            provider=provider,
            model=model,
            temperature=0.7,
            max_tokens=BEK_MAX_TOKENS,  # 2048 au lieu de 4096
        ):
            _elapsed = time.monotonic() - _start_time
            if MAX_STREAM_DURATION_SEC and _elapsed > MAX_STREAM_DURATION_SEC:
                yield f"data: {json.dumps({'chunk': _MSG_TIMEOUT_DUR})}\n\n"
                _success = False
                _error_type = "stream_timeout"
                break

            if "error" in item:
                error_msg = item.get("error", "Erreur inconnue")
                err_chunk = f"\n\n⚠️ **Erreur provider** : {error_msg}\n\n"
                yield f"data: {json.dumps({'chunk': err_chunk})}\n\n"
                _success = False
                _error_type = "provider_error"
                break

            if "chunk" not in item:
                continue

            chunk = item["chunk"]
            chunk = _sanitize_llm_output(chunk, strip_reasoning=True)
            if not chunk.strip():
                continue

            if BEK_ANTIHALLU_ENABLED and _post_action_mode:
                _post_action_grace_chunks += 1
                if _post_action_grace_chunks > BEK_POST_ACTION_GRACE_MAX:
                    _success = True
                    _error_type = "post_action_stop"
                    break

                full_text_accumulated.append(chunk)
                current_text = "".join(full_text_accumulated)
                text_since_action = current_text[_last_action_end_pos:]
                if not _has_opening_action(text_since_action):
                    continue
                else:
                    _post_action_mode = False
                    _post_action_grace_chunks = 0

            full_text_accumulated.append(chunk)
            current_text = "".join(full_text_accumulated)

            if _has_opening_action(current_text):
                action_detected = True

            if not action_detected and MAX_REASONING_CHARS:
                _reasoning_chars += len(chunk)
                if _reasoning_chars > MAX_REASONING_CHARS:
                    yield f"data: {json.dumps({'chunk': _MSG_REASONING_OVERFLOW})}\n\n"
                    _success = False
                    _error_type = "reasoning_overflow"
                    break

            if _loop_detector is not None and not action_detected:
                if _loop_detector.add(chunk):
                    yield f"data: {json.dumps({'chunk': _MSG_LOOP_DETECTED})}\n\n"
                    _success = False
                    _error_type = "loop_detected"
                    break

            if action_detected and not _has_closing_action(current_text):
                chunks_without_close += 1
                if chunks_without_close > cfg.MAX_CHUNKS_WITHOUT_CLOSE:
                    warn_incomplete = (
                        "\n\n⚠️ **Action incomplète** détectée. "
                        "Reformulez la demande.\n\n"
                    )
                    yield f"data: {json.dumps({'chunk': warn_incomplete})}\n\n"
                    _success = False
                    _error_type = "incomplete_action"
                    break

            yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

            if BEK_MULTI_ACTIONS_ENABLED and action_detected:
                all_actions = _find_all_complete_actions(current_text)
                for action in all_actions:
                    end_pos = action["end_pos"]
                    if end_pos in processed_actions:
                        continue
                    if total_actions_executed >= BEK_MAX_ACTIONS_PER_RESPONSE:
                        break

                    act_name = action["name"]
                    params = _normalize_action_params(action["params"])

                    logger.info(
                        "[Streaming v1.6.4] 🎯 Action %d : %s",
                        total_actions_executed + 1, act_name,
                    )

                    if act_name == "headless_search":
                        try:
                            _should_use_ws = rt._bek_rex_should_use_web_sync(
                                last_user_query, _routing_result,
                            )
                            if _should_use_ws:
                                act_name = "web_sync"
                                params = {"query": params.get("query", last_user_query)}
                        except Exception:
                            pass

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
                        res_chunk = "\n\n" + str(res_msg) + "\n\n"
                        yield f"data: {json.dumps({'chunk': res_chunk})}\n\n"

                        total_actions_executed += 1
                        processed_actions.add(end_pos)
                        _last_action_end_pos = end_pos

                        logger.info(
                            "[Streaming v1.6.4] ✅ Action %s terminée (%.0fms)",
                            act_name, _action_elapsed_ms,
                        )
                    except Exception as _act_err:
                        logger.exception("[Streaming v1.6.4] Action %s échouée", act_name)
                        err_chunk = f"\n\n⚠️ Erreur action {act_name} : {_act_err}\n\n"
                        yield f"data: {json.dumps({'chunk': err_chunk})}\n\n"
                        processed_actions.add(end_pos)
                        _last_action_end_pos = end_pos
                        _success = False
                        _error_type = f"action_{act_name}_error"

                if BEK_ANTIHALLU_ENABLED and total_actions_executed > 0:
                    _post_action_mode = True
                    _post_action_grace_chunks = 0

    except Exception as stream_err:
        logger.error("[Streaming v1.6.4] Erreur : %s", stream_err, exc_info=True)
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
                        # ★ v1.6.4 — NE PAS cacher les réponses d'erreur
                        _lower = final_response.lower()
                        _error_markers = [
                            "erreur", "error", "échec", "failed",
                            "permission denied", "errno",
                            "tous les providers", "quota", "rate limit",
                        ]
                        _is_error = any(m in _lower for m in _error_markers)
                        if not _is_error:
                            rt._bek_eco_store_cache(
                                query=last_user_query,
                                tier=_routing_result.get("tier", "TIER_3"),
                                response=final_response,
                            )
                        else:
                            logger.info(
                                "[Streaming v1.6.4] Cache SKIP : réponse d'erreur détectée",
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
            logger.debug("[Streaming v1.6.4] Erreur finally : %s", _loop_err)

        yield f"data: {json.dumps({'done': True})}\n\n"


def get_streaming_summary() -> dict:
    return {
        "version": "1.6.4",
        "features": {
            "multi_actions": BEK_MULTI_ACTIONS_ENABLED,
            "closing_tag_tolerant": True,
            "★ llm_string_normalization": True,
            "★ regex_fix_v162": True,
            "★ vision_typo_fix_v163": True,
            "★ groq_free_optimized_v164": True,
            "★ max_tokens": BEK_MAX_TOKENS,
            "★ truncate_security": True,
        },
    }