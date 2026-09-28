# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Actions
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Exécution des actions (multimédia, web, skills, etc.)
# 📄 Doc : docs/BEK_LVC.md
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.2
# Date : 2026-09-24
# ------------------------------------------------------------------------------
# ★ v1.2 — Connecteurs + patches :
#   - Connecteur 1 : episode_logger (message tronqué à 500 chars)
#   - Connecteur 3 : hermes.dispatch_dag() avec diagnostic ✓/✗
#   - Patch A     : troncature message (évite pollution DuckDB)
#   - Patch B     : diagnostic DAG visible dans les logs
#   - Patch C     : détection DAG interne web_sync
# ==============================================================================

from __future__ import annotations

import ast
import json
import logging
import re
import time
from typing import Any, Dict, Optional

from . import config as cfg
from . import validation as val
from . import formatters as fmt

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# REGEX D'ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

ACTION_REGEX = re.compile(r"\x5bACTION:(\w+)\x5d(.*?)\x5b/ACTION\x5d", re.DOTALL)


# ══════════════════════════════════════════════════════════════════════════════
# ★ CONNECTEUR 1 — EPISODE LOGGER (Reflex-Loop)
# ------------------------------------------------------------------------------
# Trace chaque action dans DuckDB pour alimenter Reflex-Loop.
# Silencieux en cas d'échec (ne casse jamais le chat).
#
# ★ Patch A : message tronqué à 500 chars (évite pollution DuckDB).
# ==============================================================================

_LOG_EPISODE_MAX_MESSAGE_CHARS = 500


def _log_episode_safe(
    action: str,
    status: str,
    latency_ms: int,
    error_type: Optional[str] = None,
    source: str = "chat",
    extra: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
) -> None:
    """
    Log un épisode dans DuckDB (via services.episode_logger).

    Ne lève JAMAIS d'exception — silencieux en cas d'échec.

    Args:
        action: Nom de l'action (ex: "web_sync")
        status: "success" ou "error"
        latency_ms: Latence en millisecondes
        error_type: Type d'erreur si status=error
        source: Source de l'appel ("chat", "action_executor", etc.)
        extra: Métadonnées additionnelles
        message: Message de résultat (tronqué à 500 chars)
    """
    # ★ Patch A — Troncature du message
    _msg_truncated = None
    if message:
        _msg_str = str(message)
        if len(_msg_str) > _LOG_EPISODE_MAX_MESSAGE_CHARS:
            _msg_truncated = _msg_str[:_LOG_EPISODE_MAX_MESSAGE_CHARS] + "…[tronqué]"
        else:
            _msg_truncated = _msg_str

    try:
        from services.episode_logger import log_episode

        # Tentative 1 : signature complète
        try:
            log_episode(
                action=action,
                status=status,
                latency_ms=latency_ms,
                error_type=error_type,
                source=source,
                extra=extra or {},
                message=_msg_truncated,
            )
        except TypeError:
            # Tentative 2 : signature réduite (si message non supporté)
            log_episode(
                action=action,
                status=status,
                latency_ms=latency_ms,
                error_type=error_type,
                source=source,
                extra=extra or {},
            )

        logger.debug(
            "[EpisodeLogger] ✓ %s | %s | %dms | msg=%d chars",
            action, status, latency_ms,
            len(_msg_truncated) if _msg_truncated else 0,
        )
    except ImportError:
        logger.debug("[EpisodeLogger] Module non disponible — skip")
    except Exception as _e:
        logger.debug("[EpisodeLogger] Échec silencieux : %s", _e)


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION D'ACTION
# ══════════════════════════════════════════════════════════════════════════════

def _extract_first_action(text: str) -> Optional[Dict[str, Any]]:
    """
    Extrait la première action depuis le texte du LLM.

    Returns:
        {"name": "web_sync", "params": {...}} ou None
    """
    if not text:
        return None

    matches = list(ACTION_REGEX.finditer(text))
    if not matches:
        return None

    match = matches[0]
    act_name = match.group(1)
    raw_payload = match.group(2).strip()

    params: Dict[str, Any] = {}
    try:
        p_json = json.loads(raw_payload)
        if isinstance(p_json, dict):
            params = p_json
    except Exception:
        try:
            p_ast = ast.literal_eval(raw_payload)
            if isinstance(p_ast, dict):
                params = p_ast
        except Exception:
            pass

    # Filtre stérile pour headless_scrape
    if act_name == "headless_scrape":
        url = params.get("url") or ""
        if val._is_sterile_url(url):
            logger.info("[ActionFilter] Action stérile rejetée : %s", url)
            return None

    return {"name": act_name, "params": params}


# ══════════════════════════════════════════════════════════════════════════════
# ★ PATCH C — DÉTECTION DAG INTERNE WEB_SYNC
# ------------------------------------------------------------------------------
# Vérifie si le module web_sync utilise un DAG ou un ThreadPoolExecutor.
# ==============================================================================

def _detect_web_sync_dag_usage() -> Dict[str, Any]:
    """
    Détecte si web_sync utilise un DAG interne.

    Returns:
        dict: {
            "uses_dag": bool,
            "uses_threadpool": bool,
            "module_found": bool,
            "method": str
        }
    """
    result = {
        "uses_dag": False,
        "uses_threadpool": False,
        "module_found": False,
        "method": "unknown",
    }

    try:
        import web_agent
        result["module_found"] = True

        # Chercher des indices dans le module
        module_source = ""
        try:
            import inspect
            module_source = inspect.getsource(web_agent)
        except Exception:
            pass

        if "dispatch_dag" in module_source or "dispatch_parallel" in module_source:
            result["uses_dag"] = True
            result["method"] = "dispatch_dag ou dispatch_parallel"
        elif "ThreadPoolExecutor" in module_source:
            result["uses_threadpool"] = True
            result["method"] = "ThreadPoolExecutor"
        elif "asyncio.gather" in module_source:
            result["method"] = "asyncio.gather"
        else:
            result["method"] = "séquentiel (aucun parallélisme détecté)"

    except ImportError:
        result["method"] = "module web_agent introuvable"

    return result


# ══════════════════════════════════════════════════════════════════════════════
# DISPATCHER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def _execute_action_unified(act_name: str, params: dict) -> dict:
    """
    Exécute une action unifiée.

    Gère :
        - Multimédia (image, vidéo, sous-titres)
        - headless_scrape
        - web_sync (via Hermes + DAG Engine)
        - Autres (via Hermes + CRM)

    ★ v1.2 : log automatique dans DuckDB (episode_logger) + diagnostic DAG.
    """
    _t0 = time.time()
    _original_action = act_name

    # ══════════════════════════════════════════════════════════════════════════
    # ★ DÉCISION ARCHITECTURALE — headless_search RETIRÉ
    # ==========================================================================
    if act_name == "headless_search":
        logger.warning(
            "[ActionFilter] headless_search détecté — redirection forcée vers web_sync"
        )
        act_name = "web_sync"

    # ══════════════════════════════════════════════════════════════════════════
    # MULTIMÉDIA — IMAGES
    # ══════════════════════════════════════════════════════════════════════════
    try:
        if act_name == "generate_image":
            from services.vision import generate_image_with_provider
            prompt = params.get("prompt") or params.get("query") or ""
            provider_v = params.get("provider", "pollinations")
            model_v = params.get("model", "flux-3d")
            _r = generate_image_with_provider(
                prompt=prompt, provider=provider_v, model=model_v,
            )
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type=_r.get("message", "")[:100] if _r.get("status") != "success" else None,
                message=_r.get("message", ""),
            )
            return _r

        elif act_name == "edit_image":
            from services.vision import merge_and_edit_images
            paths = params.get("image_paths") or params.get("image_path") or []
            prompt = params.get("prompt") or params.get("user_prompt") or params.get("query") or ""
            _r = merge_and_edit_images(image_paths=paths, user_prompt=prompt)
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type=_r.get("message", "")[:100] if _r.get("status") != "success" else None,
                message=_r.get("message", ""),
            )
            return _r

        # ══════════════════════════════════════════════════════════════════════
        # MULTIMÉDIA — VIDÉO
        # ══════════════════════════════════════════════════════════════════════
        elif act_name == "generate_video":
            from services.vision import generate_video_with_provider
            prompt = params.get("prompt") or params.get("query") or ""
            provider_v = params.get("provider", "agnes")
            model_v = params.get("model", "agnes-v2.0")
            duration_v = params.get("duration", 5)
            aspect_ratio_v = params.get("aspect_ratio", "16:9")
            with_audio_v = params.get("with_audio", True)
            audio_style_v = params.get("audio_style", "children")
            logger.info(
                "[generate_video] prompt=%r provider=%s model=%s duration=%s",
                prompt[:80], provider_v, model_v, duration_v,
            )
            _r = generate_video_with_provider(
                prompt=prompt, provider=provider_v, model=model_v,
                duration=int(duration_v), aspect_ratio=aspect_ratio_v,
                with_audio=bool(with_audio_v), audio_style=audio_style_v,
            )
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type=_r.get("message", "")[:100] if _r.get("status") != "success" else None,
                message=_r.get("message", ""),
            )
            return _r

        elif act_name == "edit_video":
            from services.vision import merge_and_edit_videos
            paths = params.get("video_paths") or params.get("video_path") or []
            prompt = params.get("prompt") or params.get("user_prompt") or params.get("query") or ""
            provider_v = params.get("provider", "agnes")
            model_v = params.get("model", "agnes-v2.0")
            duration_v = params.get("duration", 5)
            _r = merge_and_edit_videos(
                video_paths=paths, prompt=prompt,
                provider=provider_v, model=model_v, duration=int(duration_v),
            )
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type=_r.get("message", "")[:100] if _r.get("status") != "success" else None,
                message=_r.get("message", ""),
            )
            return _r

        elif act_name == "extend_video":
            from services.vision import extend_video_with_agnes
            video_path = params.get("video_path") or params.get("video_paths") or "LAST"
            if isinstance(video_path, list):
                video_path = video_path[0] if video_path else "LAST"
            prompt = params.get("prompt") or params.get("user_prompt") or params.get("query") or ""
            model_v = params.get("model", "agnes-v2.0")
            duration_v = params.get("duration", 9)
            with_audio_v = params.get("with_audio", True)
            audio_style_v = params.get("audio_style", "nature")
            _r = extend_video_with_agnes(
                video_path=video_path, new_prompt=prompt, model=model_v,
                duration=int(duration_v), with_audio=bool(with_audio_v),
                audio_style=audio_style_v,
            )
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type=_r.get("message", "")[:100] if _r.get("status") != "success" else None,
                message=_r.get("message", ""),
            )
            return _r

        elif act_name == "extend_video_multiple":
            from services.vision import extend_video_multiple
            video_path = params.get("video_path") or "LAST"
            prompts_list = params.get("prompts", [])
            model_v = params.get("model", "agnes-v2.0")
            duration_v = params.get("duration", 9)
            with_audio_v = params.get("with_audio", True)
            audio_style_v = params.get("audio_style", "nature")
            _r = extend_video_multiple(
                video_path=video_path, prompts=prompts_list, model=model_v,
                duration_per_clip=int(duration_v), with_audio=bool(with_audio_v),
                audio_style=audio_style_v,
            )
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type=_r.get("message", "")[:100] if _r.get("status") != "success" else None,
                message=_r.get("message", ""),
            )
            return _r

        elif act_name == "generate_subtitles":
            from services.vision.whisper_client import generate_subtitles_from_video
            video_path = params.get("video_path") or "LAST"
            language = params.get("language")
            model_name = params.get("model", "base")
            _r = generate_subtitles_from_video(
                video_path=video_path, language=language, model_name=model_name,
            )
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type=_r.get("message", "")[:100] if _r.get("status") != "success" else None,
                message=_r.get("message", ""),
            )
            return _r

        elif act_name == "burn_subtitles":
            from services.vision.whisper_client import (
                generate_subtitles_from_video, burn_subtitles_into_video,
            )
            video_path = params.get("video_path") or "LAST"
            language = params.get("language")
            model_name = params.get("model", "base")
            srt_path = params.get("srt_path")
            if not srt_path:
                srt_result = generate_subtitles_from_video(
                    video_path=video_path, language=language, model_name=model_name,
                )
                if srt_result.get("status") == "error":
                    _r = {"status": "error", "message": f"Échec .srt : {srt_result.get('message')}"}
                    _log_episode_safe(
                        action=_original_action,
                        status="error",
                        latency_ms=int((time.time() - _t0) * 1000),
                        error_type=_r["message"][:100],
                        message=_r["message"],
                    )
                    return _r
                srt_path = srt_result.get("srt_path")
            _r = burn_subtitles_into_video(video_path=video_path, srt_path=srt_path)
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type=_r.get("message", "")[:100] if _r.get("status") != "success" else None,
                message=_r.get("message", ""),
            )
            return _r

    except Exception as exc:
        logger.error("Erreur Vision (%s) : %s", act_name, exc, exc_info=True)
        _err = {"status": "error", "message": f"Erreur multimédia : {exc}"}
        _log_episode_safe(
            action=_original_action,
            status="error",
            latency_ms=int((time.time() - _t0) * 1000),
            error_type=f"vision_exception: {exc}"[:100],
            message=_err["message"],
        )
        return _err

    # ══════════════════════════════════════════════════════════════════════════
    # HEADLESS_SCRAPE (unique URL)
    # ══════════════════════════════════════════════════════════════════════════
    if act_name == "headless_scrape":
        url = params.get("url") or params.get("query") or ""
        if not url:
            _err = {"status": "error", "message": "URL manquante pour headless_scrape"}
            _log_episode_safe(
                action=_original_action,
                status="error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type="url_missing",
                message=_err["message"],
            )
            return _err

        if val._is_sterile_url(url):
            logger.warning("[headless_scrape] URL stérile rejetée : %s", url)
            _err = {
                "status": "error",
                "message": (
                    f"URL stérile rejetée (page de recherche, home ou login). "
                    f"Utilise une URL DIRECTE de contenu."
                ),
            }
            _log_episode_safe(
                action=_original_action,
                status="error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type="sterile_url",
                message=_err["message"],
            )
            return _err

        try:
            from worker_headless import HeadlessWorker
            from nerves._async_utils import run_async_safely
            logger.info("[headless_scrape] Démarrage : %s", url)
            worker = HeadlessWorker(headless=True)
            result = run_async_safely(worker.fetch_page_content(url))
            if result is None:
                _err = {"status": "error", "message": f"headless_scrape : impossible de charger {url}."}
                _log_episode_safe(
                    action=_original_action,
                    status="error",
                    latency_ms=int((time.time() - _t0) * 1000),
                    error_type="fetch_none",
                    message=_err["message"],
                )
                return _err
            preview = str(result)[:200] if result else ""
            logger.info(
                "[headless_scrape] OK %s (%d chars) | preview=%s",
                url, len(str(result)), preview,
            )
            _log_episode_safe(
                action=_original_action,
                status="success",
                latency_ms=int((time.time() - _t0) * 1000),
                message=f"Scraped {url} ({len(str(result))} chars)",
            )
            return result
        except Exception as exc:
            logger.error("Erreur headless_scrape : %s", exc, exc_info=True)
            _err = {"status": "error", "message": f"headless_scrape échoué : {exc}"}
            _log_episode_safe(
                action=_original_action,
                status="error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type=f"scrape_exception: {exc}"[:100],
                message=_err["message"],
            )
            return _err

    # ══════════════════════════════════════════════════════════════════════════
    # ★ CONNECTEUR 3 + PATCH B — HERMES DISPATCHER + DAG ENGINE + DIAGNOSTIC
    # --------------------------------------------------------------------------
    # Pour web_sync et orchestrate → utilise dispatch_dag() (parallélisation).
    # Pour les autres → dispatch() standard.
    #
    # ★ Patch B : log explicite ✓/✗ pour savoir si le DAG est utilisé.
    # ==========================================================================
    try:
        from hermes_core import hermes

        if act_name in hermes.tools:
            _use_dag = (
                act_name in ("web_sync", "orchestrate")
                and hasattr(hermes, "dispatch_dag")
            )

            # ★ Patch B — Diagnostic DAG
            if _use_dag:
                logger.info(
                    "[DAG Engine] ✓ Dispatch parallèle pour '%s' (DAG utilisé)",
                    act_name,
                )
                try:
                    h_disp = hermes.dispatch_dag([
                        {"tool": act_name, "params": params},
                    ])
                except Exception as _dag_err:
                    logger.warning(
                        "[DAG Engine] ✗ Échec dispatch_dag : %s — fallback dispatch()",
                        _dag_err,
                    )
                    h_disp = hermes.dispatch(act_name, params)
            else:
                logger.info(
                    "[DAG Engine] ✗ Non utilisé pour '%s' (act_name pas dans web_sync/orchestrate)",
                    act_name,
                )
                h_disp = hermes.dispatch(act_name, params)

            if h_disp.get("status") == "SUCCESS" and h_disp.get("results"):
                task_res = list(h_disp["results"].values())[0]
                if task_res.get("success"):
                    data = task_res.get("data")
                    _r = data if isinstance(data, dict) else {"status": "success", "message": str(data)}

                    # ★ Patch C — Diagnostic DAG interne web_sync
                    _dag_internal_info = None
                    if act_name == "web_sync":
                        _dag_internal_info = _detect_web_sync_dag_usage()
                        logger.info(
                            "[DAG Interne web_sync] %s (méthode: %s)",
                            "✓ DAG détecté" if _dag_internal_info.get("uses_dag") else
                            ("⚠ ThreadPool détecté" if _dag_internal_info.get("uses_threadpool") else
                             "✗ Séquentiel"),
                            _dag_internal_info.get("method"),
                        )

                    _log_episode_safe(
                        action=_original_action,
                        status="success",
                        latency_ms=int((time.time() - _t0) * 1000),
                        message=_r.get("message", "") or str(data)[:500],
                        extra={
                            "dag_used": _use_dag,
                            "dag_internal": _dag_internal_info,
                        },
                    )
                    return _r
    except Exception as exc:
        logger.debug("[Hermes] Dispatch échec : %s", exc)

    # ══════════════════════════════════════════════════════════════════════════
    # FALLBACK — CRM / Autres
    # ══════════════════════════════════════════════════════════════════════════
    try:
        from services.action_executor import execute_agent_crm_tool
        exec_res = execute_agent_crm_tool(act_name, params)
        _r = exec_res or {"status": "error", "message": "Aucune réponse d'exécution"}
        _log_episode_safe(
            action=_original_action,
            status="success" if _r.get("status") == "success" else "error",
            latency_ms=int((time.time() - _t0) * 1000),
            error_type=_r.get("message", "")[:100] if _r.get("status") != "success" else None,
            message=_r.get("message", ""),
            extra={"fallback": "crm"},
        )
        return _r
    except Exception as exc:
        logger.error("[Action] Fallback CRM échec : %s", exc)
        _err = {"status": "error", "message": f"Erreur critique : {exc}"}
        _log_episode_safe(
            action=_original_action,
            status="error",
            latency_ms=int((time.time() - _t0) * 1000),
            error_type=f"crm_exception: {exc}"[:100],
            message=_err["message"],
        )
        return _err


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ══════════════════════════════════════════════════════════════════════════════

def get_actions_summary() -> dict:
    """Résumé des actions disponibles."""
    return {
        "version": "1.2",
        "functions": [
            "_extract_first_action",
            "_execute_action_unified",
            "_log_episode_safe",
            "_detect_web_sync_dag_usage",
        ],
        "connecteurs": {
            "episode_logger": "✅ branché (message tronqué 500 chars)",
            "dag_engine": "✅ branché (web_sync + orchestrate)",
            "dag_diagnostic": "✅ actif (✓/✗ dans les logs)",
        },
        "patches": {
            "patch_a_troncature": "✅ message limité à 500 chars",
            "patch_b_diagnostic_dag": "✅ logs explicites ✓/✗",
            "patch_c_detection_dag_interne": "✅ détection auto web_sync",
        },
        "handled_actions": [
            "generate_image", "edit_image",
            "generate_video", "edit_video",
            "extend_video", "extend_video_multiple",
            "generate_subtitles", "burn_subtitles",
            "headless_scrape",
            "web_sync",
            "headless_search → web_sync (redirection automatique)",
            "orchestrate", "create_dynamic_skill",
            "run_script", "execute_command",
            "save_memory", "search_memory",
            "write_file", "read_file",
        ],
        "headless_search_status": "déprécié — redirigé vers web_sync",
    }