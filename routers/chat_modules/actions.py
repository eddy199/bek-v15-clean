# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Actions (v1.4.3)
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Exécution des actions (multimédia, web, skills, etc.)
# 📄 Doc : docs/BEK_LVC.md
# ------------------------------------------------------------------------------
# ★ v1.2 — Connecteurs + patches
# ★ v1.3 — Regex tolérante aux espaces parasites (bug NVIDIA NIM)
# ★ v1.4 — Nettoyage des espaces parasites dans les params
# ★ v1.4.1 — Fix _clean_str_param ciblé (prompts préservés)
# ★ v1.4.2 — Résolution des chemins AVANT appel direct Agnes
# ★ v1.4.3 — ★ Transmet `resolution` (1080P/720P/480P) au pipeline vidéo
#             (permet des vidéos 12s en 720P, 20s en 720P, etc.)
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

ACTION_REGEX = re.compile(
    r"\[\s*ACTION\s*:\s*(\w+)\s*\]"
    r"(.*?)"
    r"\[\s*/\s*A\s*CTION\s*\]",
    re.DOTALL,
)


# ══════════════════════════════════════════════════════════════════════════════
# NETTOYAGE DES ESPACES PARASITES (ciblé)
# ==============================================================================

_FILE_EXTENSIONS = (
    "jpg|jpeg|png|gif|webp|bmp|svg|"
    "mp4|mov|webm|avi|mkv|"
    "srt|vtt|txt|json|md|csv|pdf|"
    "py|js|ts|html|css|xml|yaml|yml"
)

_EXT_SPACE_RE = re.compile(
    r"\s*\.\s*(" + _FILE_EXTENSIONS + r")\b",
    re.IGNORECASE,
)
_SLASH_SPACE_RE = re.compile(r"(/\s+)([A-Za-z0-9_\-\.])")
_BACKSLASH_SPACE_RE = re.compile(r"(\\\s+)([A-Za-z0-9_\-\.])")
_UUID_SPACE_RE = re.compile(
    r"([a-f0-9])\s+(-)\s*([a-f0-9])",
    re.IGNORECASE,
)


def _clean_str_param(s: str) -> str:
    """Nettoie UNIQUEMENT les espaces parasites dans les chemins."""
    if not isinstance(s, str):
        return s

    s = _EXT_SPACE_RE.sub(r".\1", s)
    s = _SLASH_SPACE_RE.sub(r"/\2", s)
    s = _BACKSLASH_SPACE_RE.sub(r"\\\2", s)
    s = _UUID_SPACE_RE.sub(r"\1\2\3", s)
    return s.strip()


def _clean_action_params(params: Any) -> Any:
    if isinstance(params, str):
        return _clean_str_param(params)
    if isinstance(params, list):
        return [_clean_action_params(item) for item in params]
    if isinstance(params, dict):
        return {k: _clean_action_params(v) for k, v in params.items()}
    return params


# ══════════════════════════════════════════════════════════════════════════════
# EPISODE LOGGER
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
    _msg_truncated = None
    if message:
        _msg_str = str(message)
        if len(_msg_str) > _LOG_EPISODE_MAX_MESSAGE_CHARS:
            _msg_truncated = _msg_str[:_LOG_EPISODE_MAX_MESSAGE_CHARS] + "…[tronqué]"
        else:
            _msg_truncated = _msg_str

    try:
        from services.episode_logger import log_episode
        try:
            log_episode(
                action=action, status=status, latency_ms=latency_ms,
                error_type=error_type, source=source,
                extra=extra or {}, message=_msg_truncated,
            )
        except TypeError:
            log_episode(
                action=action, status=status, latency_ms=latency_ms,
                error_type=error_type, source=source, extra=extra or {},
            )
        logger.debug(
            "[EpisodeLogger] ✓ %s | %s | %dms",
            action, status, latency_ms,
        )
    except ImportError:
        logger.debug("[EpisodeLogger] Module non disponible — skip")
    except Exception as _e:
        logger.debug("[EpisodeLogger] Échec silencieux : %s", _e)


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION D'ACTION
# ==============================================================================

def _extract_first_action(text: str) -> Optional[Dict[str, Any]]:
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

    params = _clean_action_params(params)

    if act_name == "headless_scrape":
        url = params.get("url") or ""
        if val._is_sterile_url(url):
            logger.info("[ActionFilter] Action stérile rejetée : %s", url)
            return None

    return {"name": act_name, "params": params}


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION DAG INTERNE WEB_SYNC
# ==============================================================================

def _detect_web_sync_dag_usage() -> Dict[str, Any]:
    result = {
        "uses_dag": False, "uses_threadpool": False,
        "module_found": False, "method": "unknown",
    }
    try:
        import web_agent
        result["module_found"] = True
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
            result["method"] = "séquentiel"
    except ImportError:
        result["method"] = "module web_agent introuvable"
    return result


# ══════════════════════════════════════════════════════════════════════════════
# DISPATCHER PRINCIPAL
# ==============================================================================

def _execute_action_unified(act_name: str, params: dict) -> dict:
    _t0 = time.time()
    _original_action = act_name

    if act_name == "headless_search":
        logger.warning("[ActionFilter] headless_search → web_sync")
        act_name = "web_sync"

    # ══════════════════════════════════════════════════════════════════════════
    # MULTIMÉDIA
    # ==========================================================================
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
        # ★ v1.4.3 — VIDÉO AVEC IMAGES DE RÉFÉRENCE + RESOLUTION
        # ==========================================================================
        elif act_name == "generate_video":
            from services.vision import generate_video_with_provider
            prompt = params.get("prompt") or params.get("query") or ""
            provider_v = params.get("provider", "agnes")
            model_v = params.get("model", "agnes-v2.0")
            duration_v = params.get("duration", 8)
            aspect_ratio_v = params.get("aspect_ratio", "16:9")
            with_audio_v = params.get("with_audio", True)
            audio_style_v = params.get("audio_style", "children")
            # ★ v1.4.3 — Nouvelle option resolution
            resolution_v = params.get("resolution", "1080P")

            image_paths = params.get("image_paths") or params.get("reference_images")
            reference_images = None
            mode = params.get("mode")

            if image_paths:
                if isinstance(image_paths, str):
                    image_paths = [image_paths]
                if not mode:
                    if len(image_paths) > 1:
                        mode = "multi_reference"
                    else:
                        mode = "keyframes"
                reference_images = image_paths
                logger.info(
                    "[generate_video] %d image(s) de référence | mode=%s | resolution=%s",
                    len(image_paths), mode, resolution_v,
                )

            logger.info(
                "[generate_video] prompt=%r provider=%s model=%s duration=%s mode=%s resolution=%s",
                prompt[:80], provider_v, model_v, duration_v, mode, resolution_v,
            )

            if reference_images:
                # ★ v1.4.2 — Résoudre les chemins AVANT d'envoyer à Agnes
                try:
                    from services.vision.video_generation import _resolve_existing_media_paths
                    resolved_refs = _resolve_existing_media_paths(
                        reference_images, (".png", ".jpg", ".jpeg", ".webp")
                    )
                except Exception as _res_err:
                    logger.warning(
                        "[generate_video] Résolution chemins échouée : %s — on garde les bruts",
                        _res_err,
                    )
                    resolved_refs = reference_images

                import os as _os
                logger.info(
                    "[generate_video] Chemins résolus : %d/%d | %s",
                    len(resolved_refs), len(reference_images),
                    [_os.path.basename(p) for p in resolved_refs],
                )

                if not resolved_refs:
                    logger.error(
                        "[generate_video] Aucun fichier trouvé ! Bruts=%s",
                        reference_images,
                    )
                    _r = {
                        "status": "error",
                        "message": f"Images introuvables : {reference_images}",
                    }
                    _log_episode_safe(
                        action=_original_action, status="error",
                        latency_ms=int((time.time() - _t0) * 1000),
                        error_type="images_not_found",
                        message=_r["message"],
                    )
                    return _r

                try:
                    from services.vision.agnes_client import _agnes_generate_single_clip
                    from provider_manager import provider_manager as _pm
                    model_id = _pm.resolve_agnes_model_id(model_v)
                    clip = _agnes_generate_single_clip(
                        prompt=prompt,
                        model_id=model_id,
                        duration=int(duration_v),
                        aspect_ratio=aspect_ratio_v,
                        mode=mode,
                        reference_images=resolved_refs,
                        # ★ v1.4.3 — resolution transmise
                        resolution=resolution_v,
                    )
                    import os as _os2
                    from core.paths import GENERATED_DIR as _GD
                    import uuid as _uuid
                    out_name = f"gen_video_{_uuid.uuid4().hex[:8]}.mp4"
                    out_path = _os2.path.join(_GD, out_name)
                    with open(out_path, "wb") as _f:
                        _f.write(clip["bytes"])
                    _r = {
                        "status": "success",
                        "filepath": out_path,
                        "filename": out_name,
                        "duration": int(duration_v),
                        "provider": "agnes",
                        "model_id": model_id,
                        "with_audio": bool(with_audio_v),
                        "mode_used": mode,
                        "resolution_used": resolution_v,
                        "reference_images_count": len(resolved_refs),
                    }
                except Exception as _exc:
                    logger.warning(
                        "[generate_video] Échec mode %s avec refs : %s — fallback sans refs",
                        mode, _exc,
                    )
                    refs = params.get("image_paths") or params.get("reference_images")
                    if isinstance(refs, str):
                        refs = [refs]
                    _r = generate_video_with_provider(
                        prompt=prompt,
                        provider=provider_v,
                        model=model_v,
                        duration=int(duration_v),
                        aspect_ratio=aspect_ratio_v,
                        with_audio=bool(with_audio_v),
                        audio_style=audio_style_v,
                        image_paths=refs,
                        style_preset=params.get("style_preset", "auto"),
                        resolution=resolution_v,
                    )
            else:
                _r = generate_video_with_provider(
                    prompt=prompt, provider=provider_v, model=model_v,
                    duration=int(duration_v), aspect_ratio=aspect_ratio_v,
                    with_audio=bool(with_audio_v), audio_style=audio_style_v,
                    resolution=resolution_v,
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
                        action=_original_action, status="error",
                        latency_ms=int((time.time() - _t0) * 1000),
                        error_type=_r["message"][:100], message=_r["message"],
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
            action=_original_action, status="error",
            latency_ms=int((time.time() - _t0) * 1000),
            error_type=f"vision_exception: {exc}"[:100],
            message=_err["message"],
        )
        return _err

    # HEADLESS_SCRAPE
    if act_name == "headless_scrape":
        url = params.get("url") or params.get("query") or ""
        if not url:
            _err = {"status": "error", "message": "URL manquante pour headless_scrape"}
            _log_episode_safe(
                action=_original_action, status="error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type="url_missing", message=_err["message"],
            )
            return _err

        if val._is_sterile_url(url):
            logger.warning("[headless_scrape] URL stérile rejetée : %s", url)
            _err = {
                "status": "error",
                "message": "URL stérile rejetée (page de recherche, home ou login).",
            }
            _log_episode_safe(
                action=_original_action, status="error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type="sterile_url", message=_err["message"],
            )
            return _err

        try:
            from worker_headless import HeadlessWorker
            from nerves._async_utils import run_async_safely
            logger.info("[headless_scrape] Démarrage : %s", url)
            worker = HeadlessWorker(headless=True)
            result = run_async_safely(worker.fetch_page_content(url))
            if result is None:
                _err = {"status": "error", "message": f"Impossible de charger {url}."}
                _log_episode_safe(
                    action=_original_action, status="error",
                    latency_ms=int((time.time() - _t0) * 1000),
                    error_type="fetch_none", message=_err["message"],
                )
                return _err
            preview = str(result)[:200] if result else ""
            logger.info(
                "[headless_scrape] OK %s (%d chars) | preview=%s",
                url, len(str(result)), preview,
            )
            _log_episode_safe(
                action=_original_action, status="success",
                latency_ms=int((time.time() - _t0) * 1000),
                message=f"Scraped {url} ({len(str(result))} chars)",
            )
            return result
        except Exception as exc:
            logger.error("Erreur headless_scrape : %s", exc, exc_info=True)
            _err = {"status": "error", "message": f"headless_scrape échoué : {exc}"}
            _log_episode_safe(
                action=_original_action, status="error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type=f"scrape_exception: {exc}"[:100],
                message=_err["message"],
            )
            return _err

    # HERMES DISPATCHER
    try:
        from hermes_core import hermes
        if act_name in hermes.tools:
            _use_dag = (
                act_name in ("web_sync", "orchestrate")
                and hasattr(hermes, "dispatch_dag")
            )
            if _use_dag:
                logger.info("[DAG Engine] ✓ Dispatch parallèle pour '%s'", act_name)
                try:
                    h_disp = hermes.dispatch_dag([{"tool": act_name, "params": params}])
                except Exception as _dag_err:
                    logger.warning("[DAG Engine] ✗ Échec : %s — fallback", _dag_err)
                    h_disp = hermes.dispatch(act_name, params)
            else:
                logger.info("[DAG Engine] ✗ Non utilisé pour '%s'", act_name)
                h_disp = hermes.dispatch(act_name, params)

            if h_disp.get("status") == "SUCCESS" and h_disp.get("results"):
                task_res = list(h_disp["results"].values())[0]
                if task_res.get("success"):
                    data = task_res.get("data")
                    _r = data if isinstance(data, dict) else {"status": "success", "message": str(data)}
                    _dag_internal_info = None
                    if act_name == "web_sync":
                        _dag_internal_info = _detect_web_sync_dag_usage()
                        logger.info(
                            "[DAG Interne web_sync] %s (méthode: %s)",
                            "✓ DAG détecté" if _dag_internal_info.get("uses_dag") else
                            ("⚠ ThreadPool" if _dag_internal_info.get("uses_threadpool") else "✗ Séquentiel"),
                            _dag_internal_info.get("method"),
                        )
                    _log_episode_safe(
                        action=_original_action, status="success",
                        latency_ms=int((time.time() - _t0) * 1000),
                        message=_r.get("message", "") or str(data)[:500],
                        extra={"dag_used": _use_dag, "dag_internal": _dag_internal_info},
                    )
                    return _r
    except Exception as exc:
        logger.debug("[Hermes] Dispatch échec : %s", exc)

    # FALLBACK CRM
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
            action=_original_action, status="error",
            latency_ms=int((time.time() - _t0) * 1000),
            error_type=f"crm_exception: {exc}"[:100],
            message=_err["message"],
        )
        return _err


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ==============================================================================

def get_actions_summary() -> dict:
    return {
        "version": "1.4.3",
        "functions": [
            "_extract_first_action", "_execute_action_unified",
            "_log_episode_safe", "_detect_web_sync_dag_usage",
            "_clean_str_param", "_clean_action_params",
        ],
        "patches": {
            "v1.4.0_clean_spaces": "✅ 'x. jpg' → 'x.jpg'",
            "v1.4.1_targeted_clean": "✅ Nettoie UNIQUEMENT chemins",
            "v1.4.1_uuid_fix": "✅ '1c8a -4333' → '1c8a-4333'",
            "v1.4.2_resolve_before_agnes": "✅ Résout uploads/ AVANT appel direct Agnes",
            "v1.4.3_resolution_passthrough": "✅ Transmet resolution (1080P/720P/480P)",
        },
        "handled_actions": [
            "generate_image", "edit_image",
            "generate_video (avec image_paths + resolution)", "edit_video",
            "extend_video", "extend_video_multiple",
            "generate_subtitles", "burn_subtitles",
            "headless_scrape", "web_sync",
            "orchestrate", "create_dynamic_skill",
            "run_script", "execute_command",
            "save_memory", "search_memory",
            "write_file", "read_file",
        ],
    }