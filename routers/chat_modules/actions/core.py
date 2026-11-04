# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Actions : Core (dispatcher principal)
# ------------------------------------------------------------------------------
# ★ v1.4.11 (2026-10-17) — FIX generate_video : suppression paramètre mode
#   - generate_video_with_provider() n'accepte PAS de paramètre 'mode'
#   - Le mode est calculé automatiquement par suggest_agnes_mode_v2()
#   - Retire mode=mode de l'appel + le bloc de normalisation mode
# ★ v1.4.10 (2026-10-17) — ORCHESTRATE GUARD RENFORCÉ
# ★ v1.4.9 (2026-10-16) — FIX IMPORT : ajout `import json`
# ★ v1.4.8 (2026-10-16) — Migration : extraction dans actions/core.py
# ==============================================================================
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from .. import config as cfg
from .. import formatters as fmt

from .aliases import _resolve_action_alias
from .guards import _is_orchestrate_misused, _build_orchestrate_guard_message
from .extraction import _log_episode_safe

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION DAG INTERNE WEB_SYNC
# ══════════════════════════════════════════════════════════════════════════════

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
# NORMALISATION MODÈLE AGNES (v1.4.8)
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_agnes_model(model_val: Optional[str]) -> str:
    """Remplace automatiquement agnes-v2.0 (déprécié HTTP 503) par agnes-v2.5-flash."""
    if not model_val:
        return "agnes-v2.5-flash"
    clean = model_val.strip().lower()
    if clean in ("agnes-v2.0", "agnes-v2", "agnes-video-v2.0", "agnes-video-v2"):
        logger.info("[Actions] Modèle déprécié %r → bascule sur 'agnes-v2.5-flash'", model_val)
        return "agnes-v2.5-flash"
    return model_val


# ══════════════════════════════════════════════════════════════════════════════
# DISPATCHER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def _execute_action_unified(act_name: str, params: dict) -> dict:
    _t0 = time.time()
    _original_action = act_name

    # ★ v1.4.5 — Résoudre l'alias ICI aussi
    act_name = _resolve_action_alias(act_name)

    if act_name == "headless_search":
        logger.warning("[ActionFilter] headless_search → web_sync")
        act_name = "web_sync"

    # ══════════════════════════════════════════════════════════════════════════
    # ★ v1.4.10 — GARDE-FOU ANTI-ORCHESTRATE (défense en profondeur)
    # ══════════════════════════════════════════════════════════════════════════
    if act_name == "orchestrate":
        _goal = params.get("goal") or params.get("objective") or params.get("query") or ""
        _goal_clean = _goal.strip() if isinstance(_goal, str) else ""

        # ★ v1.4.10 — Check EXPLICITE du goal vide (ne dépend pas de guards.py)
        if not _goal_clean:
            logger.warning(
                "[OrchestrateGuard] ❌ orchestrate avec goal VIDE (défense v1.4.10)"
            )
            _guard_msg = _build_orchestrate_guard_message(_goal)
            _log_episode_safe(
                action=_original_action, status="error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type="orchestrate_empty_goal",
                message=_guard_msg[:500],
            )
            return {
                "status": "error",
                "message": _guard_msg,
                "guard": "orchestrate_empty_goal",
                "suggestion": "Réponds en TEXTE naturel, sans action.",
            }

        # Guard classique (via guards.py)
        if _is_orchestrate_misused(_goal):
            logger.warning(
                "[OrchestrateGuard] ❌ orchestrate invalide (goal vide ou meta) : %r",
                _goal[:120] if isinstance(_goal, str) else _goal,
            )
            _guard_msg = _build_orchestrate_guard_message(_goal)
            _log_episode_safe(
                action=_original_action, status="error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type="orchestrate_misused_or_empty",
                message=_guard_msg[:500],
            )
            return {
                "status": "error",
                "message": _guard_msg,
                "guard": "orchestrate_misused_or_empty",
                "suggestion": "Réponds en TEXTE NATUREL, sans action.",
            }
        else:
            logger.info(
                "[OrchestrateGuard] ✅ orchestrate légitime : %r",
                _goal[:120] if isinstance(_goal, str) else _goal,
            )

    # ══════════════════════════════════════════════════════════════════════════
    # MULTIMÉDIA
    # ══════════════════════════════════════════════════════════════════════════
    try:
        if act_name == "generate_image":
            from services.vision import generate_image_with_provider
            prompt = params.get("prompt") or params.get("query") or ""
            provider_v = params.get("provider", "pollinations")
            model_v = params.get("model", "flux")
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
            if isinstance(paths, str):
                paths = [paths]
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

        elif act_name == "generate_video":
            # ══════════════════════════════════════════════════════════════════
            # ★ v1.4.11 — FIX : generate_video_with_provider n'accepte PAS 'mode'
            # Le mode est calculé automatiquement par suggest_agnes_mode_v2()
            # ══════════════════════════════════════════════════════════════════
            from services.vision import generate_video_with_provider
            prompt = params.get("prompt") or params.get("query") or ""
            provider_v = params.get("provider", "agnes")
            model_v = _normalize_agnes_model(params.get("model", "agnes-v2.5-flash"))
            duration_v = params.get("duration", 5)
            aspect_ratio_v = params.get("aspect_ratio", "16:9")
            with_audio_v = params.get("with_audio", True)
            audio_style_v = params.get("audio_style", "children")
            resolution_v = params.get("resolution", "1080P")

            image_paths = params.get("image_paths") or params.get("reference_images")
            reference_images = None

            if image_paths:
                if isinstance(image_paths, str):
                    image_paths = [image_paths]
                reference_images = image_paths

            if reference_images:
                try:
                    from services.vision.video_generation import _resolve_existing_media_paths
                    resolved_refs = _resolve_existing_media_paths(
                        reference_images, (".png", ".jpg", ".jpeg", ".webp")
                    )
                    if resolved_refs:
                        reference_images = resolved_refs
                    else:
                        logger.warning(
                            "[generate_video] Aucune image de référence résolue → fallback texte pur"
                        )
                        reference_images = None
                except Exception as _res_err:
                    logger.warning(
                        "[generate_video] Résolution refs échouée : %s", _res_err
                    )

            # ★ v1.4.11 — SUPPRESSION de mode=mode dans l'appel
            _r = generate_video_with_provider(
                prompt=prompt,
                provider=provider_v,
                model=model_v,
                duration=duration_v,
                aspect_ratio=aspect_ratio_v,
                with_audio=with_audio_v,
                audio_style=audio_style_v,
                resolution=resolution_v,
                reference_images=reference_images,
            )
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type=_r.get("message", "")[:100] if _r.get("status") != "success" else None,
                message=_r.get("message", ""),
            )
            return _r

        elif act_name in ("edit_video", "extend_video", "extend_video_multiple", "generate_subtitles", "burn_subtitles", "analyze_image"):
            from services.action_executor import execute_agent_tool
            norm_params = dict(params)
            if act_name == "edit_video":
                if "video_paths" not in norm_params and ("video_path" in norm_params or "path" in norm_params):
                    vp = norm_params.get("video_path") or norm_params.get("path")
                    norm_params["video_paths"] = [vp] if isinstance(vp, str) else vp
                norm_params["model"] = _normalize_agnes_model(norm_params.get("model", "agnes-v2.5-flash"))
            elif act_name in ("extend_video", "extend_video_multiple"):
                if "video_path" not in norm_params and "path" in norm_params:
                    norm_params["video_path"] = norm_params["path"]
                norm_params["model"] = _normalize_agnes_model(norm_params.get("model", "agnes-v2.5-flash"))
            elif act_name in ("generate_subtitles", "burn_subtitles"):
                if "video_path" not in norm_params and "path" in norm_params:
                    norm_params["video_path"] = norm_params["path"]
            elif act_name == "analyze_image":
                if "image_path" not in norm_params and "path" in norm_params:
                    norm_params["image_path"] = norm_params["path"]
                if "prompt" not in norm_params and "query" in norm_params:
                    norm_params["prompt"] = norm_params["query"]

            _r = execute_agent_crm_tool(act_name, norm_params)
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                message=_r.get("message", "")[:500] if _r.get("message") else None,
            )
            return _r

        # ══════════════════════════════════════════════════════════════════════
        # WEB & HEADLESS
        # ══════════════════════════════════════════════════════════════════════
        elif act_name == "web_sync":
            from web_agent import web_sync
            query = params.get("query") or params.get("prompt") or ""
            _r = web_sync(query=query)
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                message=_r.get("message", "")[:500] if _r.get("message") else None,
            )
            return _r

        elif act_name in ("headless_scrape", "headless_extract_leads", "headless_render"):
            url = params.get("url") or params.get("query") or ""
            _r = None
            try:
                from hermes_core import hermes
                tool_obj = hermes._get_tool(act_name)
                if tool_obj is not None:
                    arg_key = "query" if act_name == "headless_extract_leads" else "url"
                    _r = tool_obj.func(**{arg_key: url})
            except Exception as _he:
                logger.debug("[Actions] Hermes %s fallback : %s", act_name, _he)

            if _r is None:
                try:
                    from nerves.hermes_nerves import _handler_headless_scrape
                    from nerves.headless_nerves import _handler_headless_extract_leads, _handler_headless_render
                    if act_name == "headless_scrape":
                        _r = _handler_headless_scrape(url=url)
                    elif act_name == "headless_extract_leads":
                        _r = _handler_headless_extract_leads(query=url)
                    else:
                        _r = _handler_headless_render(url=url)
                except Exception as _ne:
                    _r = {"status": "error", "message": f"Erreur {act_name} : {_ne}"}

            if not isinstance(_r, dict):
                _r = {"status": "success", "message": str(_r)}

            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                message=_r.get("message", "")[:500] if _r.get("message") else None,
            )
            return _r

        # ══════════════════════════════════════════════════════════════════════
        # HINDSIGHT
        # ══════════════════════════════════════════════════════════════════════
        elif act_name in ("hindsight_query", "hindsight_recall"):
            query = params.get("query") or params.get("prompt") or ""
            try:
                import hindsight_memory as _hm
                if act_name == "hindsight_query" and hasattr(_hm, "hindsight_query"):
                    raw_res = _hm.hindsight_query(query=query)
                elif act_name == "hindsight_query" and hasattr(_hm, "hindsight_reflect"):
                    ans = _hm.hindsight_reflect(query)
                    raw_res = ans if ans else _hm.hindsight_recall(query)
                else:
                    raw_res = _hm.hindsight_recall(query)

                if isinstance(raw_res, dict):
                    _r = raw_res
                    _r.setdefault("status", "success")
                    if "message" not in _r:
                        _r["message"] = str(_r.get("answer") or _r.get("results") or _r)
                else:
                    _r = {"status": "success", "message": str(raw_res) if raw_res else "Aucun souvenir trouvé dans Hindsight."}
            except Exception as _h_err:
                _r = {"status": "error", "message": f"Hindsight indisponible : {_h_err}"}

            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
            )
            return _r

        # ══════════════════════════════════════════════════════════════════════
        # NEON AUDIT & MCP
        # ══════════════════════════════════════════════════════════════════════
        elif act_name == "neon_audit":
            try:
                from nerves.hermes_nerves import _handler_neon_audit
                _r = _handler_neon_audit()
            except Exception as _na_err:
                _r = {"status": "error", "message": f"Erreur neon_audit : {_na_err}"}
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
            )
            return _r

        elif act_name == "mcp_execute":
            from mcp_gateway import mcp_gateway
            tool_name = params.get("tool") or params.get("tool_name") or params.get("name") or ""
            arguments = params.get("arguments") or params.get("params") or {}
            _r = mcp_gateway.execute_tool(tool_name, arguments)
            if not isinstance(_r, dict):
                _r = {"status": "success", "message": str(_r)}
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
            )
            return _r

        # ══════════════════════════════════════════════════════════════════════
        # PONT UNIFIÉ VERS services/action_executor.py (v36+)
        # ══════════════════════════════════════════════════════════════════════
        elif act_name in (
            "save_memory", "search_memory", "delete_memory",
            "write_file", "read_file", "delete_file",
            "create_zip", "extract_zip", "analyze_zip_content",
            "execute_command", "run_script", "run_tests",
            "orchestrate", "create_dynamic_skill",
            "start_background_task", "stop_background_task",
        ):
            from services.action_executor import execute_agent_crm_tool
            norm_params = dict(params)

            if act_name in ("write_file", "read_file", "delete_file"):
                if not norm_params.get("filename"):
                    norm_params["filename"] = (
                        norm_params.get("path")
                        or norm_params.get("file_path")
                        or norm_params.get("file")
                        or ""
                    )
            elif act_name == "create_zip":
                if not norm_params.get("folder_path") and norm_params.get("paths"):
                    p_list = norm_params["paths"]
                    norm_params["folder_path"] = p_list[0] if isinstance(p_list, list) and p_list else str(p_list)
                if not norm_params.get("output_zip"):
                    norm_params["output_zip"] = norm_params.get("output_path") or norm_params.get("zip_path") or "generated/export_projet.zip"
            elif act_name == "extract_zip":
                if not norm_params.get("zip_path") and norm_params.get("path"):
                    norm_params["zip_path"] = norm_params["path"]
                if not norm_params.get("extract_to") and norm_params.get("output_path"):
                    norm_params["extract_to"] = norm_params["output_path"]
            elif act_name in ("execute_command", "run_script"):
                if not norm_params.get("command"):
                    script_p = norm_params.get("path") or norm_params.get("script_path")
                    if script_p and act_name == "run_script":
                        norm_params["command"] = f"python {script_p}"
                    else:
                        norm_params["command"] = norm_params.get("cmd") or ""
            elif act_name == "save_memory":
                if not norm_params.get("content") and norm_params.get("query"):
                    norm_params["content"] = norm_params["query"]
            elif act_name == "delete_memory":
                if not norm_params.get("record_id") and norm_params.get("id"):
                    norm_params["record_id"] = norm_params["id"]

            _r = execute_agent_crm_tool(act_name, norm_params)
            _log_episode_safe(
                action=_original_action,
                status="success" if _r.get("status") == "success" else "error",
                latency_ms=int((time.time() - _t0) * 1000),
                message=_r.get("message", "")[:500] if _r.get("message") else None,
            )
            return _r

        # ══════════════════════════════════════════════════════════════════════
        # FALLBACK SUR LES OUTILS HERMES ENREGISTRÉS
        # ══════════════════════════════════════════════════════════════════════
        else:
            try:
                from hermes_core import hermes
                tool_obj = hermes._get_tool(act_name)
                if tool_obj is not None:
                    raw_res = tool_obj.func(**params)
                    _r = raw_res if isinstance(raw_res, dict) else {"status": "success", "message": str(raw_res)}
                    _r.setdefault("status", "success")
                    if "message" not in _r:
                        _r["message"] = json.dumps(_r, ensure_ascii=False)
                    _log_episode_safe(
                        action=_original_action, status="success",
                        latency_ms=int((time.time() - _t0) * 1000),
                    )
                    return _r
            except Exception:
                pass

            logger.warning("[ActionUnified] Action inconnue : %s", act_name)
            _log_episode_safe(
                action=_original_action, status="error",
                latency_ms=int((time.time() - _t0) * 1000),
                error_type="unknown_action",
                message=f"Action inconnue : {act_name}",
            )
            return {
                "status": "error",
                "message": f"⚠️ Action inconnue : `{act_name}`. Aucun exécuteur disponible.",
                "suggestion": "Réponds en texte naturel sans action.",
            }

    except Exception as _exc:
        logger.exception("[ActionUnified] Exception %s : %s", act_name, _exc)
        _log_episode_safe(
            action=_original_action, status="error",
            latency_ms=int((time.time() - _t0) * 1000),
            error_type=type(_exc).__name__,
            message=str(_exc)[:500],
        )
        return {
            "status": "error",
            "message": f"⚠️ Erreur exécution `{act_name}` : {_exc}",
            "error_type": type(_exc).__name__,
        }