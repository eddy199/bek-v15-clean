# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Streaming : Core (v1.6.27)
# ------------------------------------------------------------------------------
# ★ v1.6.27 (2026-11-08) — FIX affichage JSON brut des outils
#   - Correction de l'ordre : format AVANT _apply_post_tool_bricks
#   - Suppression du doublon res_msg = fmt._format_execution_result(...)
#   - Ajout de _clean_action_result() pour nettoyer les dicts Python bruts
# ★ v1.6.26 (2026-11-06) — FIX Rebond analytique post-outil
# ==============================================================================
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Set

from .. import config as cfg
from .. import actions as act
from .. import formatters as fmt
from .. import routing as rt

from .constants import (
    MAX_STREAM_DURATION_SEC,
    LOOP_DETECT_ENABLED,
    MAX_REASONING_CHARS,
    BEK_ECO_CACHE_ENABLED,
    BEK_LOOP_ENABLED,
    BEK_MULTI_ACTIONS_ENABLED,
    BEK_MAX_ACTIONS_PER_RESPONSE,
    BEK_ANTIHALLU_ENABLED,
    BEK_POST_ACTION_GRACE_MAX,
    BEK_MAX_TOKENS,
    BEK_FORCE_IMAGE_ON_INTENT,
    BEK_SKIP_BYPASS_ON_MULTI_INTENT,
    BEK_FOLLOWUP_AFTER_TOOL,
    _MSG_TIMEOUT_DUR,
    _MSG_REASONING_OVERFLOW,
    _MSG_LOOP_DETECTED,
)

from .parsing import (
    _find_all_complete_actions,
    _has_closing_action,
    _has_opening_action,
    _sanitize_llm_output,
    _normalize_action_params,
)

from .guards import (
    _has_multi_intent,
    _user_wants_image,
    _has_attached_file,
    _query_requires_verification,
    _add_verification_guard,
    _add_file_context_guard,
    _llm_refused_to_generate,
    _extract_image_subject,
)

from .truncation import _truncate_messages_for_groq
from .loop_detect import _LoopDetector

logger = logging.getLogger("BEKApp")

_ANALYZE_KEYWORDS_STREAM = (
    "analyse", "analyser", "analyses",
    "décris", "decris", "décrire", "decrire",
    "décrit", "decrit", "description",
    "regarde", "regarde cette", "regarde l'image",
    "que vois-tu", "que vois tu", "qu'est-ce que c'est",
    "qu'est ce que c'est", "qu'est-ce qu'il y a",
    "identifie", "reconnais", "reconnaître", "reconnait",
    "détaille", "détaille", "détailler",
    "explique cette image", "explique l'image",
    "lis l'image", "lis cette image",
    "extrait le texte", "ocr",
    "describe", "describe this", "what do you see",
    "what is this", "identify", "recognize",
)

_ORCH_MIN_GOAL_LENGTH = 10
_ORCH_META_KEYWORDS = (
    "réponds", "reponds", "répond", "repond",
    "répondre", "repondre",
    "aide l'utilisateur", "aide l’utilisateur",
    "answer the user", "respond to the user",
    "réponds directement", "reponds directement",
    "réponds en texte", "reponds en texte",
    "réponds à l'utilisateur", "reponds a l'utilisateur",
)

_ACTION_MARKER = "[ACTION:"
_FOLLOWUP_BUFFER_MARGIN = 64


def _clean_action_result(result: Any) -> str:
    """
    ★ v1.6.27 : Nettoie le résultat d'une action.
    - Si c'est un dict avec 'content', extrait le contenu.
    - Si c'est un dict avec 'message', extrait le message.
    - Sinon, convertit en string propre.
    """
    if isinstance(result, str):
        # Si c'est déjà une string contenant un dict Python brut, essaye de l'extraire
        if result.startswith("{") and ("'status':" in result or "\"status\":" in result):
            try:
                import ast
                parsed = ast.literal_eval(result)
                if isinstance(parsed, dict):
                    content = parsed.get("content") or parsed.get("message") or ""
                    if content:
                        return str(content).strip()
            except Exception:
                pass
        return result

    if isinstance(result, dict):
        # Chercher le contenu exploitable
        for key in ("content", "message", "response", "text", "data", "result"):
            val = result.get(key)
            if val and isinstance(val, str) and len(val.strip()) > 10:
                return val.strip()
        
        # Si status=error
        if result.get("status") == "error":
            return f"❌ {result.get('message', result.get('error', 'Erreur'))}"
        
        # Sinon, pas de contenu exploitable
        return "✅ Action exécutée."

    return str(result)


def _is_orchestrate_goal_empty_or_meta(goal: Any) -> tuple:
    if not isinstance(goal, str):
        return True, "goal_non_string"
    clean = goal.strip()
    if not clean:
        return True, "goal_vide"
    if len(clean) < _ORCH_MIN_GOAL_LENGTH:
        return True, f"goal_trop_court({len(clean)}<{_ORCH_MIN_GOAL_LENGTH})"
    lower = clean.lower()
    for kw in _ORCH_META_KEYWORDS:
        if lower.startswith(kw):
            return True, f"goal_meta_starts_with({kw!r})"
    return False, ""


try:
    from hindsight_memory import hindsight_retain_conversation_async
    _HINDSIGHT_AVAILABLE = True
except ImportError:
    _HINDSIGHT_AVAILABLE = False
    async def hindsight_retain_conversation_async(user_message, agent_response, context=None):
        return False


def _apply_post_tool_bricks(tool_name: str, result: Any) -> str:
    """Applique LVC, Anti-Hallucination et Mémoire sur le résultat (retourne une string)."""
    result_str = str(result) if not isinstance(result, str) else result

    # 1. LVC
    if len(result_str) > 3000:
        try:
            compressed = result_str[:3000] + "\n...[tronqué par LVC]"
            logger.info("[LVC] 🗜️ Résultat '%s' compressé : %d → %d chars",
                       tool_name, len(result_str), len(compressed))
            result_str = compressed
        except Exception as e:
            logger.debug("[LVC] Compression échouée : %s", e)

    # 2. Anti-Hallucination
    try:
        from bek_core.stair.toc_builder import BekStair
        stair = BekStair()
        if hasattr(stair, "validate_result"):
            if not stair.validate_result(tool_name, result_str):
                logger.warning("[STAIR] ⚠️ Résultat '%s' non vérifié", tool_name)
                result_str += "\n\n⚠️ *Résultat non vérifié par BEK-STAIR*"
    except Exception as e:
        logger.debug("[STAIR] Validation indisponible : %s", e)

    # 3. Mémoire
    try:
        from memory import save_to_memory
        save_to_memory(f"[ACTION] {tool_name} exécuté avec succès: {result_str[:200]}")
    except Exception as e:
        logger.debug("[Memory] Enregistrement action indisponible : %s", e)

    return result_str


async def stream_chat(
    exec_messages: List[Dict[str, Any]],
    trimmed_messages: List[Dict[str, Any]],
    last_user_query: str,
    provider: str,
    model: str,
    pre_executed_tools: List[Dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    from provider_manager import provider_manager

    full_text_accumulated: List[str] = []

    _is_groq = (provider or "").strip().lower() == "groq"
    _max_per_msg = getattr(cfg, "GROQ_MAX_CHARS_PER_MESSAGE", 6000) if _is_groq else cfg.MAX_CHARS_PER_MESSAGE
    _max_total = getattr(cfg, "GROQ_MAX_TOTAL_CHARS", 18000) if _is_groq else cfg.MAX_TOTAL_CHARS

    _total_before = sum(len(m.get("content", "")) for m in exec_messages if isinstance(m, dict))
    exec_messages = _truncate_messages_for_groq(
        exec_messages,
        max_chars_per_msg=_max_per_msg,
        max_total_chars=_max_total,
    )
    _total_after = sum(len(m.get("content", "")) for m in exec_messages if isinstance(m, dict))
    logger.info(
        "[Streaming v1.6.27] Requête (%s) : %d messages | %d → %d chars (limite %d)",
        provider, len(exec_messages), _total_before, _total_after, _max_total,
    )

    _user_part = last_user_query or ""
    _instr_pos = _user_part.find("(INSTRUCTION SYSTEME")
    if _instr_pos > 0:
        _user_part = _user_part[:_instr_pos]
    _user_actions = _find_all_complete_actions(_user_part)

    _file_attached = _has_attached_file(last_user_query, exec_messages)
    _user_img_intent = _user_wants_image(last_user_query)
    _multi_intent = _has_multi_intent(last_user_query) if BEK_SKIP_BYPASS_ON_MULTI_INTENT else False

    if _file_attached:
        exec_messages = _add_file_context_guard(exec_messages)
        logger.info("[Streaming v1.6.27] Guard 'fichier joint' injecté dans le system prompt")

    _bypass_blocked_reason = None
    if _user_actions:
        _bypass_blocked_reason = "user_actions_present"
    elif _file_attached:
        _bypass_blocked_reason = "file_attached"
    elif not _user_img_intent:
        _bypass_blocked_reason = "no_image_intent"
    elif _multi_intent:
        _bypass_blocked_reason = "multi_intent_detected"

    if _bypass_blocked_reason is None:
        logger.info("[Streaming v1.6.27] 🚀 BYPASS LLM : intention image pure → generate_image direct")
        _bypass_intro = "\n\n⚙️ *Génération de l'image en cours...*\n\n"
        yield f"data: {json.dumps({'chunk': _bypass_intro})}\n\n"

        _bypass_prompt = _extract_image_subject(last_user_query)
        _bypass_t0 = time.monotonic()
        try:
            _bypass_res = act._execute_action_unified(
                "generate_image",
                {"prompt": _bypass_prompt, "provider": "pollinations", "model": "flux"},
            )
            _bypass_msg = _clean_action_result(_bypass_res)
            _bypass_chunk = "\n\n" + str(_bypass_msg) + "\n\n"
            yield f"data: {json.dumps({'chunk': _bypass_chunk}, ensure_ascii=False)}\n\n"
        except Exception as _bypass_err:
            logger.exception("[Streaming v1.6.27] BYPASS generate_image échouée")
            _err_chunk = f"\n\n⚠️ Erreur génération image : {_bypass_err}\n\n"
            yield f"data: {json.dumps({'chunk': _err_chunk})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"
        return

    if _user_img_intent:
        logger.info("[Streaming v1.6.27] ⏭️ BYPASS SKIP (raison=%s) → LLM va orchestrer", _bypass_blocked_reason)
    if _file_attached:
        logger.info("[Streaming v1.6.27] Fichier joint détecté → bypass image désactivé")

    if _user_actions:
        logger.info("[Streaming v1.6.27] %d action(s) utilisateur — exécution DIRECTE", len(_user_actions))
        _direct_msg = "\n\n⚙️ *Exécution directe...*\n\n"
        yield f"data: {json.dumps({'chunk': _direct_msg})}\n\n"
        for _idx, _ua in enumerate(_user_actions, 1):
            _ua_name = _ua["name"]
            _ua_params = _normalize_action_params(_ua["params"])
            if _ua_name not in cfg.MULTIMEDIA_ACTIONS:
                _ua_params["provider"] = provider
                _ua_params["model"] = model
            _exec_msg = f"\n\n⚙️ *Exécution {_idx}...*\n"
            yield f"data: {json.dumps({'chunk': _exec_msg})}\n\n"
            try:
                _exec_res = act._execute_action_unified(_ua_name, _ua_params)
                # ★ FIX : nettoyer AVANT formatage
                _res_msg = _clean_action_result(_exec_res)
                _res_chunk = "\n\n" + str(_res_msg) + "\n\n"
                yield f"data: {json.dumps({'chunk': _res_chunk}, ensure_ascii=False)}\n\n"
            except Exception as _err:
                logger.exception("[Streaming v1.6.27] Action %s échouée", _ua_name)
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
    _executed_tool_results: List[Dict[str, str]] = []

    if pre_executed_tools:
        for _pre in pre_executed_tools:
            _executed_tool_results.append({
                "name": _pre.get("name", "unknown"),
                "output": _pre.get("output", ""),
                "status": _pre.get("status", "success"),
            })
        logger.info(
            "[Streaming v1.6.27] 🔗 %d outil(s) pré-exécuté(s) par le brain injecté(s)",
            len(pre_executed_tools),
        )

    try:
        is_freshness_query = bool(rt._bek_rex_is_freshness_query(last_user_query))
    except Exception:
        is_freshness_query = False
    _verification_sensitive = _query_requires_verification(last_user_query, is_freshness_query)
    if is_freshness_query:
        logger.info("[Streaming v1.6.27] Requête de fraîcheur détectée")
    if _verification_sensitive:
        logger.info("[Streaming v1.6.27] Requête vérifiable : cache et mémoire non fiables désactivés")
        exec_messages = _add_verification_guard(exec_messages)

    _detected_ego = rt._bek_rex_detect_alter_ego(last_user_query)
    if _detected_ego and _detected_ego != "bek":
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
                "[Streaming v1.6.27] BEK-REX tier=%s conf=%.2f",
                _routing_result.get("tier"), _routing_result.get("confidence", 0.0),
            )
        except Exception as _rex_err:
            logger.warning("[Streaming v1.6.27] BEK-REX échec : %s", _rex_err)
            _routing_result = {"tier": "TIER_3", "confidence": 0.5}

        _tier = _routing_result.get("tier", "TIER_3")

        if BEK_ECO_CACHE_ENABLED and last_user_query and not _verification_sensitive and not _file_attached:
            try:
                _eco_result = rt._bek_eco_check_cache(last_user_query, _tier)
                if _eco_result.get("cached") and _eco_result.get("cached_value"):
                    cached_response = _eco_result["cached_value"].get("response", "")
                    if cached_response and not _llm_refused_to_generate(cached_response, _file_attached):
                        _cached_response_served = True
                        cache_badge = "⚡ *[réponse en cache]*\n\n"
                        yield f"data: {json.dumps({'chunk': cache_badge}, ensure_ascii=False)}\n\n"
                        for i in range(0, len(cached_response), 80):
                            piece = cached_response[i:i + 80]
                            yield f"data: {json.dumps({'chunk': piece}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        return
                    else:
                        logger.warning("[Streaming v1.6.27] Cache HIT mais réponse polluée → SKIP")
            except Exception as _eco_err:
                logger.warning("[Streaming v1.6.27] BEK-ECO échec : %s", _eco_err)

        for item in provider_manager.execute_chat_stream(
            messages=exec_messages,
            provider=provider,
            model=model,
            temperature=0.7,
            max_tokens=BEK_MAX_TOKENS,
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
            if not chunk:
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

            if _loop_detector is not None and not action_detected and not _file_attached:
                if _loop_detector.add(chunk):
                    yield f"data: {json.dumps({'chunk': _MSG_LOOP_DETECTED})}\n\n"
                    _success = False
                    _error_type = "loop_detected"
                    break

            if action_detected and not _has_closing_action(current_text):
                chunks_without_close += 1
                if chunks_without_close > cfg.MAX_CHUNKS_WITHOUT_CLOSE:
                    warn_incomplete = "\n\n⚠️ **Action incomplète** détectée.\n\n"
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

                    _FILE_ATTACHED_ACTIONS_BLOCKED = (
                        "web_sync",
                        "headless_scrape",
                        "headless_search",
                    )
                    if _file_attached and act_name in _FILE_ATTACHED_ACTIONS_BLOCKED:
                        logger.warning("[Streaming v1.6.27] 🚫 Action '%s' bloquée : fichier joint", act_name)
                        processed_actions.add(end_pos)
                        continue

                    logger.info("[Streaming v1.6.27] 🎯 Action %d : %s", total_actions_executed + 1, act_name)
                    if act_name == "headless_search":
                        try:
                            if rt._bek_rex_should_use_web_sync(last_user_query, _routing_result):
                                act_name = "web_sync"
                                params = {"query": params.get("query", last_user_query)}
                        except Exception:
                            pass
                    if act_name not in cfg.MULTIMEDIA_ACTIONS:
                        params["provider"] = provider
                        params["model"] = model

                    if act_name == "orchestrate":
                        _pre_goal = (
                            params.get("goal")
                            or params.get("objective")
                            or params.get("query")
                            or ""
                        )
                        _invalid, _reason = _is_orchestrate_goal_empty_or_meta(_pre_goal)
                        if _invalid:
                            logger.warning("[Streaming v1.6.27] 🛡️ orchestrate SKIP (%s) : goal=%r", _reason, _pre_goal[:120] if isinstance(_pre_goal, str) else _pre_goal)
                            _skip_user_msg = "\n\n⚠️ *L'action `orchestrate` a été ignorée (objectif vide ou trop vague). Je réponds directement.*\n\n"
                            yield f"data: {json.dumps({'chunk': _skip_user_msg}, ensure_ascii=False)}\n\n"
                            _executed_tool_results.append({
                                "name": "orchestrate",
                                "output": (
                                    f"L'action `orchestrate` a été bloquée car elle ne "
                                    f"contenait pas d'objectif valide (raison : {_reason}). "
                                    f"Aucune sous-tâche n'a été planifiée. "
                                    f"Réponds directement à l'utilisateur en texte naturel."
                                ),
                                "status": "error",
                            })
                            processed_actions.add(end_pos)
                            _last_action_end_pos = end_pos
                            continue

                    msg_imm = f'\n\n⚙️ *Exécution {total_actions_executed + 1} (`{act_name}`)...*\n'
                    yield f"data: {json.dumps({'chunk': msg_imm})}\n\n"
                    _action_start = time.monotonic()
                    try:
                        exec_res = act._execute_action_unified(act_name, params)
                        
                        # ★ v1.6.27 : NETTOYER AVANT formatage (évite JSON brut)
                        cleaned_result = _clean_action_result(exec_res)
                        
                        # Appliquer les briques sur la version nettoyée
                        final_result = _apply_post_tool_bricks(act_name, cleaned_result)
                        
                        _action_elapsed_ms = (time.monotonic() - _action_start) * 1000
                        res_chunk = "\n\n" + str(final_result) + "\n\n"
                        yield f"data: {json.dumps({'chunk': res_chunk}, ensure_ascii=False)}\n\n"
                        
                        total_actions_executed += 1
                        processed_actions.add(end_pos)
                        _last_action_end_pos = end_pos
                        _executed_tool_results.append({
                            "name": act_name,
                            "output": str(final_result),
                            "status": exec_res.get("status", "success") if isinstance(exec_res, dict) else "success",
                        })
                        logger.info("[Streaming v1.6.27] ✅ Action %s terminée (%.0fms)", act_name, _action_elapsed_ms)
                    except Exception as _act_err:
                        logger.exception("[Streaming v1.6.27] Action %s échouée", act_name)
                        err_chunk = f"\n\n⚠️ Erreur action {act_name} : {_act_err}\n\n"
                        yield f"data: {json.dumps({'chunk': err_chunk})}\n\n"
                        processed_actions.add(end_pos)
                        _last_action_end_pos = end_pos
                        _success = False
                        _error_type = f"action_{act_name}_error"
                if BEK_ANTIHALLU_ENABLED and total_actions_executed > 0:
                    _post_action_mode = True
                    _post_action_grace_chunks = 0

        _analysis_actions = getattr(cfg, "ANALYSIS_ACTIONS", (
            "read_file", "analyze_image", "analyze_zip_content",
            "search_memory", "hindsight_query", "hindsight_recall",
            "headless_scrape", "execute_command", "run_script", "neon_audit",
            "python_save_report", "analyze_architecture",
        ))
        _needs_followup = False
        for _tr in _executed_tool_results:
            if _tr["name"] in _analysis_actions:
                _needs_followup = True
                break
            if _tr["name"] == "orchestrate" and _tr["status"] == "error":
                _needs_followup = True
                break

        if BEK_FOLLOWUP_AFTER_TOOL and _needs_followup:
            logger.info(
                "[Streaming v1.6.27] 🔄 Rebond analytique post-outil activé (%d résultat(s))",
                len(_executed_tool_results),
            )
            _tool_context_parts = [
                f"[RÉSULTAT DE L'OUTIL `{tr['name']}`]\n{tr['output'][:8000]}"
                for tr in _executed_tool_results
            ]
            _followup_messages = list(exec_messages) + [
                {"role": "assistant", "content": "".join(full_text_accumulated)},
                {
                    "role": "user",
                    "content": (
                        "Voici le résultat réel retourné par l'outil :\n\n"
                        + "\n\n".join(_tool_context_parts)
                        + "\n\nRéponds maintenant directement en TEXTE NATUREL à la demande "
                        "initiale de l'utilisateur en te basant UNIQUEMENT sur ce résultat. "
                        "N'appelle AUCUNE nouvelle action `[ACTION:...]`."
                    ),
                },
            ]
            _FOLLOWUP_SEP = "\n\n---\n\n"
            yield f"data: {json.dumps({'chunk': _FOLLOWUP_SEP}, ensure_ascii=False)}\n\n"

            _followup_start = time.monotonic()
            _followup_buffer: List[str] = []
            _followup_yielded = 0
            _followup_aborted_reason: str | None = None

            try:
                for f_item in provider_manager.execute_chat_stream(
                    messages=_followup_messages,
                    provider=provider,
                    model=model,
                    temperature=0.5,
                    max_tokens=BEK_MAX_TOKENS,
                ):
                    _fu_elapsed = time.monotonic() - _followup_start
                    if MAX_STREAM_DURATION_SEC and _fu_elapsed > MAX_STREAM_DURATION_SEC:
                        logger.warning("[Streaming v1.6.27] Follow-up timeout après %.1fs", _fu_elapsed)
                        _followup_aborted_reason = "followup_timeout"
                        yield f"data: {json.dumps({'chunk': _MSG_TIMEOUT_DUR})}\n\n"
                        break

                    if "error" in f_item:
                        logger.warning(
                            "[Streaming v1.6.27] Follow-up erreur provider : %s",
                            f_item.get("error"),
                        )
                        _followup_aborted_reason = "followup_provider_error"
                        break

                    if "chunk" not in f_item:
                        continue

                    f_chunk = _sanitize_llm_output(f_item["chunk"], strip_reasoning=True)
                    if not f_chunk:
                        continue

                    _followup_buffer.append(f_chunk)
                    _combined = "".join(_followup_buffer)

                    if _ACTION_MARKER in _combined:
                        logger.warning(
                            "[Streaming v1.6.27] Follow-up : LLM a émis une action malgré la consigne → arrêt propre"
                        )
                        _followup_aborted_reason = "followup_llm_rebel"
                        _action_pos = _combined.find(_ACTION_MARKER)
                        if _action_pos > 0:
                            _safe_prefix = _combined[:_action_pos]
                            full_text_accumulated.append(_safe_prefix)
                            yield f"data: {json.dumps({'chunk': _safe_prefix}, ensure_ascii=False)}\n\n"
                            _followup_yielded += 1
                        break

                    full_text_accumulated.append(f_chunk)
                    yield f"data: {json.dumps({'chunk': f_chunk}, ensure_ascii=False)}\n\n"
                    _followup_yielded += 1

                    if len(_followup_buffer) > 4:
                        _followup_buffer = _followup_buffer[-4:]

            except Exception as _fu_err:
                logger.error(
                    "[Streaming v1.6.27] Follow-up exception : %s",
                    _fu_err, exc_info=True,
                )
                _followup_aborted_reason = f"followup_exception:{type(_fu_err).__name__}"

            if _followup_yielded == 0 and not _followup_aborted_reason:
                logger.warning(
                    "[Streaming v1.6.27] Follow-up terminé sans aucun chunk — fallback message"
                )
                _fallback_msg = (
                    "\n\n⚠️ *Le rebond analytique n'a produit aucune réponse textuelle. "
                    "Voici le résumé brut de l'outil :*\n\n"
                    + "\n\n".join(_tool_context_parts)[:2000]
                )
                full_text_accumulated.append(_fallback_msg)
                yield f"data: {json.dumps({'chunk': _fallback_msg}, ensure_ascii=False)}\n\n"

            if _followup_aborted_reason:
                logger.info(
                    "[Streaming v1.6.27] Follow-up terminé (%s) — %d chunk(s) yieldé(s)",
                    _followup_aborted_reason, _followup_yielded,
                )
            else:
                logger.info(
                    "[Streaming v1.6.27] Follow-up terminé normalement — %d chunk(s) yieldé(s)",
                    _followup_yielded,
                )

    except Exception as stream_err:
        logger.error("[Streaming v1.6.27] Erreur : %s", stream_err, exc_info=True)
        _err_text = "\n\n⚠️ Flux Error : " + str(stream_err) + "\n"
        yield f"data: {json.dumps({'chunk': _err_text})}\n\n"
        _success = False
        _error_type = type(stream_err).__name__

    finally:
        full_response = "".join(full_text_accumulated)

        _user_wants_img = _user_wants_image(last_user_query)
        _no_action_executed = (total_actions_executed == 0)
        _file_attached_final = _has_attached_file(last_user_query, exec_messages)
        _multi_intent_final = _has_multi_intent(last_user_query) if BEK_SKIP_BYPASS_ON_MULTI_INTENT else False

        _llm_refused = _llm_refused_to_generate(full_response, _file_attached_final)

        logger.info(
            "[Streaming v1.6.27] FORCE-CHECK : user_wants_image=%s | llm_refused=%s | "
            "no_action=%s | file_attached=%s | multi_intent=%s",
            _user_wants_img, _llm_refused, _no_action_executed,
            _file_attached_final, _multi_intent_final,
        )

        _q_lower_final = (last_user_query or "").lower()
        _should_force_analyze = (
            _file_attached_final
            and _no_action_executed
            and not _multi_intent_final
            and any(kw in _q_lower_final for kw in _ANALYZE_KEYWORDS_STREAM)
        )

        if _should_force_analyze:
            logger.warning("[Streaming v1.6.27] 🚨 FORÇAGE analyze_image : fichier joint + intention d'analyse")

            _m = re.search(r"\[Fichiers joints\s*:\s*([^\]]+)\]", last_user_query or "", re.IGNORECASE)
            _fname = _m.group(1).strip().split(",")[0].strip() if _m else ""

            if _fname:
                from core.paths import WORKSPACE_DIR
                from pathlib import Path as _Path
                _full_path = str(_Path(WORKSPACE_DIR) / "uploads" / _fname)

                _analyze_msg = "\n\n---\n\n⚙️ *Analyse de l'image en cours...*\n\n"
                try:
                    yield f"data: {json.dumps({'chunk': _analyze_msg}, ensure_ascii=False)}\n\n"
                except GeneratorExit:
                    logger.debug("[Streaming v1.6.27] Client a coupé (analyze_msg) — abandon")
                    raise

                try:
                    _analyze_res = act._execute_action_unified(
                        "analyze_image",
                        {"image_path": _full_path, "prompt": "Décris cette image en détail."},
                    )
                    _analyze_formatted = _clean_action_result(_analyze_res)
                    _analyze_chunk = "\n\n" + str(_analyze_formatted) + "\n\n"
                    try:
                        yield f"data: {json.dumps({'chunk': _analyze_chunk}, ensure_ascii=False)}\n\n"
                    except GeneratorExit:
                        raise
                    total_actions_executed += 1
                    action_detected = True
                    _success = True
                    _executed_tool_results.append({
                        "name": "analyze_image",
                        "output": str(_analyze_formatted),
                        "status": "success",
                    })
                    logger.info("[Streaming v1.6.27] ✅ Forçage analyze_image terminé (%s)", _fname)
                except Exception as _analyze_err:
                    logger.exception("[Streaming v1.6.27] Forçage analyze_image échoué")
                    _err_chunk = f"\n\n⚠️ Erreur analyse image : {_analyze_err}\n\n"
                    try:
                        yield f"data: {json.dumps({'chunk': _err_chunk})}\n\n"
                    except GeneratorExit:
                        raise
            else:
                logger.warning("[Streaming v1.6.27] Forçage analyze_image SKIP : nom de fichier introuvable")

        _should_force = (
            BEK_FORCE_IMAGE_ON_INTENT
            and _user_wants_img
            and _no_action_executed
            and not _file_attached_final
            and not _multi_intent_final
        )

        if _should_force:
            logger.warning("[Streaming v1.6.27] 🚨 FORÇAGE INCONDITIONNEL : utilisateur veut image + aucune action")

            _force_msg = "\n\n---\n\n⚙️ *BEK prend le relais — génération de l'image...*\n\n"
            try:
                yield f"data: {json.dumps({'chunk': _force_msg}, ensure_ascii=False)}\n\n"
            except GeneratorExit:
                logger.debug("[Streaming v1.6.27] Client a coupé (force_msg) — abandon propre")
                raise

            _forced_prompt = _extract_image_subject(last_user_query)
            _force_t0 = time.monotonic()
            try:
                _forced_res = act._execute_action_unified(
                    "generate_image",
                    {"prompt": _forced_prompt, "provider": "pollinations", "model": "flux"},
                )
                _forced_msg = _clean_action_result(_forced_res)
                _forced_chunk = "\n\n" + str(_forced_msg) + "\n\n"
                try:
                    yield f"data: {json.dumps({'chunk': _forced_chunk}, ensure_ascii=False)}\n\n"
                except GeneratorExit:
                    raise
                total_actions_executed += 1
                action_detected = True
                _success = True
            except Exception as _force_err:
                _err_chunk = f"\n\n⚠️ Erreur forçage image : {_force_err}\n\n"
                try:
                    yield f"data: {json.dumps({'chunk': _err_chunk})}\n\n"
                except GeneratorExit:
                    raise

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

            _should_have_action = _user_wants_image(last_user_query)
            _is_hallucination = _should_have_action and not action_detected
            if _is_hallucination:
                logger.warning("[Streaming v1.6.27] ⚠️ Hallucination détectée. Cache SKIP.")

            if (
                BEK_ECO_CACHE_ENABLED
                and _success
                and not _cached_response_served
                and last_user_query
                and full_text_accumulated
                and not action_detected
                and not _is_hallucination
                and not _verification_sensitive
                and not _file_attached_final
                and not _multi_intent_final
            ):
                try:
                    final_response = "".join(full_text_accumulated)
                    if (
                        final_response
                        and len(final_response) > 50
                        and not _llm_refused_to_generate(final_response, _file_attached_final)
                    ):
                        _lower = final_response.lower()
                        _error_markers = [
                            "erreur", "error", "échec", "failed",
                            "permission denied", "errno",
                            "tous les providers", "quota", "rate limit",
                        ]
                        if not any(m in _lower for m in _error_markers):
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
                and not _verification_sensitive
                and not _file_attached_final
            ):
                try:
                    final_agent_response = "".join(full_text_accumulated)
                    if final_agent_response and len(final_agent_response) > 20:
                        await hindsight_retain_conversation_async(
                            user_message=last_user_query,
                            agent_response=final_agent_response[:1000],
                            context="chat_conversation",
                        )
                except Exception:
                    pass

        except Exception as _loop_err:
            logger.debug("[Streaming v1.6.27] Erreur finally : %s", _loop_err)

        try:
            yield f"data: {json.dumps({'done': True})}\n\n"
        except GeneratorExit:
            logger.debug("[Streaming v1.6.27] Client a coupé la connexion — abandon propre")
            raise


def get_streaming_summary() -> dict:
    return {
        "version": "1.6.27",
        "features": {
            "clean_action_result": True,
            "fix_json_brut": True,
            "multi_actions": BEK_MULTI_ACTIONS_ENABLED,
            "closing_tag_tolerant": True,
            "llm_string_normalization": True,
            "whitespace_preserved_v166": True,
            "force_action_on_llm_refusal_v167": True,
            "python_3_12_safe_v168": True,
            "force_image_unconditional_v169": BEK_FORCE_IMAGE_ON_INTENT,
            "bypass_llm_for_images_v1610": True,
            "skip_image_bypass_if_file_attached_v1611": True,
            "verification_guard_and_cache_skip_v1612": True,
            "skip_image_bypass_on_multi_intent_v1613": BEK_SKIP_BYPASS_ON_MULTI_INTENT,
            "image_subject_extraction_v1613": True,
            "no_false_refusal_with_file_v1614": True,
            "preserve_system_prompt_v1615": True,
            "strict_image_intent_v1615": True,
            "analytical_tool_followup_v1615": BEK_FOLLOWUP_AFTER_TOOL,
            "generator_exit_safe_v1616": True,
            "no_return_in_finally_v1617": True,
            "file_attached_guard_v1618": True,
            "python_3_11_render_compat_v1619": True,
            "hindsight_retain_async_v1621": True,
            "orchestrate_guard_pre_execution_v1622": True,
            "analyze_image_unblocked_v1623": True,
            "force_analyze_image_on_llm_muet_v1624": True,
            "skip_loop_detector_on_file_attached_v1625": True,
            "followup_timeout_v1626": True,
            "followup_rebel_action_guard_v1626": True,
            "followup_empty_fallback_v1626": True,
            "followup_pre_executed_tools_v1626": True,
            "clean_action_result_v1627": True,
            "max_tokens": BEK_MAX_TOKENS,
        },
    }