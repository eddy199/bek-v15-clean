# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 HYBRID — SERVEUR PRINCIPAL FASTAPI (BOOTSTRAP MODULAIRE)
# ------------------------------------------------------------------------------
# v16.5 (2026-09-22) : FIX Ctrl+C
# v18.0 (2026-09-24) : Régénération ARCHITECTURE.md AVANT imports routeurs
# v18.1 (2026-09-25) : Route OpenAI-compatible /v1/chat/completions
# v18.2 (2026-09-29) : Intégration HINDSIGHT (outils + routes API)
# v18.5 (2026-09-29) : Feedback utilisateur (routes /api/feedback)
# v18.6 (2026-09-29) : Pending feedbacks traités au boot + route async
# v18.10 (2026-09-29) : ★ Route admin /api/admin/flush-redis
# v18.11 (2026-09-29) : ★ Tool generate_video avec support images
# v18.12 (2026-10-06) : ★ CRM DÉSACTIVÉ (Nerf 10 + router retirés)
# v18.13 (2026-10-06) : ★ LAZY LOADING (Playwright, ChromaDB, DuckDB, LanceDB)
#                       + Route /health/memory
# ==============================================================================
from __future__ import annotations

import signal as _signal
import os as _os
import sys as _sys


def _bek_force_exit(signum, frame):
    try:
        _sys.stdout.write(
            "\n\033[91m🔴 BEK — Arrêt forcé (Ctrl+C). Nettoyage immédiat.\033[0m\n"
        )
        _sys.stdout.flush()
        _sys.stderr.flush()
    except Exception:
        pass
    _os._exit(0)


try:
    _signal.signal(_signal.SIGINT, _bek_force_exit)
    if hasattr(_signal, "SIGBREAK"):
        _signal.signal(_signal.SIGBREAK, _bek_force_exit)
except Exception as _sig_err:
    print(f"[BEK] Impossible d'installer le handler SIGINT : {_sig_err}")

from env_loader import load_env
load_env()

from typing import Any, Dict, Optional
from pydantic import BaseModel
import skill_runner

import logging
import os
import sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# --- IMPORTS NOYAU & PATHS ---
from context_loader import load_project_documentation
from core.logger import setup_json_logging
from core.paths import DOCS_DIR, WORKSPACE_DIR
from hermes_core import hermes, start_background_workers
from memory import init_sync_log_table
from state_synchronizer import init_state_tables

# ─── VISION (image + vidéo) ───
try:
    from services.vision import (
        generate_image_with_provider,
        merge_and_edit_images,
        generate_video_with_provider,
        merge_and_edit_videos,
        extend_video_with_agnes,
        extend_video_multiple,
    )
except ImportError:
    generate_image_with_provider = None
    merge_and_edit_images = None
    generate_video_with_provider = None
    merge_and_edit_videos = None
    extend_video_with_agnes = None
    extend_video_multiple = None

# ─── ★ v18.12 : SubCRMEngine n'est PLUS chargé (CRM désactivé) ───
SubCRMEngine = None  # ★ Désactivé

# ─── WEB AGENT ───
try:
    from web_agent import web_agent_instance
except ImportError:
    web_agent_instance = None

# ─── ORCHESTRATEUR ───
try:
    from bek_orchestrator import bek_orchestrator
except ImportError:
    bek_orchestrator = None

# ─── MCP GATEWAY ───
try:
    from mcp_gateway import mcp_gateway
except ImportError:
    class MCPGatewayMock:
        def register_mcp_tool(self, **kwargs): pass
        def get_mcp_manifests(self): return []
    mcp_gateway = MCPGatewayMock()

# ─── ★ v18.2 — HINDSIGHT ───
try:
    from hindsight_memory import (
        hindsight_reflect,
        hindsight_recall,
        hindsight_status as _hindsight_status,
    )
    _HINDSIGHT_AVAILABLE = True
except ImportError:
    _HINDSIGHT_AVAILABLE = False

    def hindsight_reflect(q): return ""
    def hindsight_recall(q): return []
    def _hindsight_status(): return {"enabled": False, "connected": False}

# ─── ★ v18.5 — FEEDBACK ───
try:
    from feedback_memory import (
        submit_feedback as _submit_feedback,
        list_feedbacks as _list_feedbacks,
        feedback_stats as _feedback_stats,
        process_pending_feedbacks as _process_pending_feedbacks,
    )
    _FEEDBACK_AVAILABLE = True
except ImportError:
    _FEEDBACK_AVAILABLE = False

    def _submit_feedback(**kwargs):
        return {"status": "error", "message": "feedback_memory indisponible"}
    def _list_feedbacks(limit=50): return []
    def _feedback_stats(): return {"total": 0}
    def _process_pending_feedbacks(): return 0

# ─── ★ v18 — Régénérer ARCHITECTURE.md AVANT les routeurs ───
try:
    from generate_architecture_doc import update_documentation_file
    if update_documentation_file():
        print("[v18] ✅ ARCHITECTURE.md régénéré AVANT imports routeurs.")
    else:
        print("[v18] ⚠️ Régénération ARCHITECTURE.md retournée False.")
except Exception as exc:
    print(f"[v18] ⚠️ Régénération pré-imports échouée : {exc}")

# ─── ROUTERS ───
# ★ v18.12 : "crm" retiré de l'import et de l'inclusion
from routers import admin, chat, files, memory
from routers import openai_compat

logger = logging.getLogger("BEKApp")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = RotatingFileHandler(
        os.path.join(WORKSPACE_DIR, "bek_app.log"),
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

_BEK_ALREADY_BOOTSTRAPPED = os.environ.get("BEK_BOOTSTRAPPED") == "1"

if not _BEK_ALREADY_BOOTSTRAPPED:
    # ─── INIT DB ───
    try:
        init_sync_log_table()
        init_state_tables()
        logger.info("Tables PostgreSQL (Supabase) initialisées.")
    except Exception as exc:
        logger.warning("Initialisation DB partielle : %s", exc)

    # ─── MCP : neon_audit ───
    mcp_gateway.register_mcp_tool(
        name="neon_audit",
        description="Audit des tables relationnelles PostgreSQL",
        parameters_schema={},
        handler=lambda: {
            "tables": [
                "companies", "contacts", "opportunities",
                "bek_task_states", "sync_log",
            ]
        },
    )

    # ─── WORKERS HERMES ───
    try:
        start_background_workers()
        logger.info("Workers Hermes démarrés avec succès.")
    except Exception as exc:
        logger.error("Impossible de démarrer les workers Hermes : %s", exc)

    # ─── PENDING FEEDBACKS ───
    try:
        n_pending = _process_pending_feedbacks()
        if n_pending > 0:
            logger.info("✓ %d feedbacks pending traités au boot", n_pending)
    except Exception as exc:
        logger.warning("Pending feedbacks : %s", exc)

    # ─── PRE-PLAN HOOK ───
    def _bek_pre_plan_validator(objective: str, trace_id: str | None):
        return True, "Pre-Plan validé", None

    hermes.register_pre_plan_hook(_bek_pre_plan_validator)

    # ══════════════════════════════════════════════════════════════════════
    # ENREGISTREMENT DES OUTILS HERMES
    # ══════════════════════════════════════════════════════════════════════

    # ─── web_sync ───
    hermes.register_tool(
        "web_sync",
        lambda query="", **kwargs: (
            web_agent_instance.run_pipeline(query)
            if web_agent_instance else "WebAgent indisponible"
        ),
        risk_level="L3",
    )

    # ─── orchestrate ───
    hermes.register_tool(
        "orchestrate",
        lambda goal="", **kwargs: (
            bek_orchestrator.run(goal)
            if bek_orchestrator else "Orchestrateur indisponible"
        ),
        risk_level="L2",
    )

    # ─── neon_audit ───
    hermes.register_tool(
        "neon_audit",
        lambda **kwargs: {
            "status": "Audit DB demandé",
            "tables": ["companies", "contacts", "opportunities", "sync_log"],
        },
        risk_level="L1",
    )

    # ─── generate_image ───
    hermes.register_tool(
        "generate_image",
        lambda prompt="", query="", **kwargs: (
            generate_image_with_provider(prompt=prompt or query)
            if generate_image_with_provider
            else {"status": "error", "message": "Module vision manquant"}
        ),
        risk_level="L1",
    )

    # ─── edit_image ───
    hermes.register_tool(
        "edit_image",
        lambda image_paths=None, prompt="", user_prompt="", query="", **kwargs: (
            merge_and_edit_images(
                image_paths=image_paths,
                user_prompt=user_prompt or prompt or query
            )
            if merge_and_edit_images
            else {"status": "error", "message": "Module vision manquant"}
        ),
        risk_level="L1",
    )

    # ─── generate_video (handler complexe) ───
    def _generate_video_handler(
        prompt="", query="",
        image_paths=None,
        reference_images=None,
        video_paths=None,
        provider="agnes",
        model="agnes-v2.0",
        duration=8,
        aspect_ratio="16:9",
        auto_stitch=True,
        with_audio=True,
        audio_style="children",
        negative_prompt=None,
        person_generation="allow_all",
        mode=None,
        **kwargs
    ):
        """Génère une vidéo (★ v18.11 : support images de référence)."""
        if generate_video_with_provider is None:
            return {"status": "error", "message": "Module vidéo manquant"}

        refs = reference_images or image_paths

        if refs and mode is None:
            if isinstance(refs, list) and len(refs) > 1:
                mode = "multi_reference"
            else:
                mode = "keyframes"

        call_kwargs = {
            "prompt": prompt or query,
            "provider": provider,
            "model": model,
            "duration": int(duration),
            "aspect_ratio": aspect_ratio,
            "auto_stitch": bool(auto_stitch),
            "with_audio": bool(with_audio),
            "audio_style": audio_style,
            "negative_prompt": negative_prompt,
            "person_generation": person_generation,
        }

        if refs:
            try:
                from services.vision.agnes_client import _agnes_generate_single_clip
                from provider_manager import provider_manager as _pm
                model_id = _pm.resolve_agnes_model_id(model)
                logger.info(
                    "[generate_video] Mode %s avec %d image(s) de référence",
                    mode, len(refs) if isinstance(refs, list) else 1,
                )
                clip = _agnes_generate_single_clip(
                    prompt=prompt or query,
                    model_id=model_id,
                    duration=int(duration),
                    aspect_ratio=aspect_ratio,
                    mode=mode,
                    reference_images=refs if isinstance(refs, list) else [refs],
                )
                from core.paths import GENERATED_DIR as _GD
                import uuid as _uuid
                out_name = f"gen_video_{_uuid.uuid4().hex[:8]}.mp4"
                out_path = _os.path.join(_GD, out_name)
                with open(out_path, "wb") as _f:
                    _f.write(clip["bytes"])
                return {
                    "status": "success",
                    "filepath": out_path,
                    "filename": out_name,
                    "duration": int(duration),
                    "provider": "agnes",
                    "model_id": model_id,
                    "with_audio": bool(with_audio),
                    "mode_used": mode,
                    "reference_images_count": len(refs) if isinstance(refs, list) else 1,
                }
            except Exception as exc:
                logger.warning(
                    "[generate_video] Échec mode %s avec refs : %s — fallback",
                    mode, exc,
                )
                try:
                    return generate_video_with_provider(**call_kwargs)
                except Exception as exc2:
                    return {
                        "status": "error",
                        "message": f"Échec génération avec refs : {exc} | fallback : {exc2}",
                    }

        try:
            return generate_video_with_provider(**call_kwargs)
        except TypeError:
            call_kwargs.pop("with_audio", None)
            call_kwargs.pop("audio_style", None)
            try:
                return generate_video_with_provider(**call_kwargs)
            except Exception as exc:
                return {"status": "error", "message": f"Erreur generate_video : {exc}"}
        except Exception as exc:
            return {"status": "error", "message": f"Erreur generate_video : {exc}"}

    hermes.register_tool("generate_video", _generate_video_handler, risk_level="L1")

    # ─── edit_video ───
    hermes.register_tool(
        "edit_video",
        lambda video_paths=None, prompt="", user_prompt="", query="",
               provider="gemini", model="veo-3.1-gene-prev",
               duration=8, aspect_ratio="16:9", auto_stitch=True,
               **kwargs: (
            merge_and_edit_videos(
                video_paths=video_paths,
                user_prompt=user_prompt or prompt or query,
                provider=provider,
                model=model,
                duration=int(duration),
                aspect_ratio=aspect_ratio,
                auto_stitch=bool(auto_stitch),
            )
            if merge_and_edit_videos
            else {"status": "error", "message": "Module vidéo manquant"}
        ),
        risk_level="L1",
    )

    # ─── extend_video ───
    def _extend_video_handler(
        video_path="LAST", prompt="", new_prompt="",
        duration=9, with_audio=True, audio_style="nature", **kwargs
    ):
        try:
            if extend_video_with_agnes is None:
                return {"status": "error", "message": "Module extend_video indisponible"}
            return extend_video_with_agnes(
                video_path=video_path,
                new_prompt=new_prompt or prompt,
                duration=int(duration),
                with_audio=bool(with_audio),
                audio_style=audio_style,
            )
        except Exception as e:
            return {"status": "error", "message": f"extend_video échec : {e}"}

    # ─── extend_video_multiple ───
    def _extend_video_multiple_handler(
        video_path="LAST", prompts=None,
        duration=9, with_audio=True, audio_style="nature", max_clips=5, **kwargs
    ):
        try:
            if extend_video_multiple is None:
                return {"status": "error", "message": "Module extend_video_multiple indisponible"}
            return extend_video_multiple(
                video_path=video_path,
                prompts=prompts or [],
                duration_per_clip=int(duration),
                with_audio=bool(with_audio),
                audio_style=audio_style,
                max_clips=int(max_clips),
            )
        except Exception as e:
            return {"status": "error", "message": f"extend_video_multiple échec : {e}"}

    hermes.register_tool("extend_video", _extend_video_handler, risk_level="L1")
    hermes.register_tool("extend_video_multiple", _extend_video_multiple_handler, risk_level="L1")

    # ─── generate_subtitles ───
    def _generate_subtitles_handler(
        video_path="LAST", language=None, model="base", **kwargs
    ):
        try:
            from services.vision.whisper_client import generate_subtitles_from_video
            return generate_subtitles_from_video(
                video_path=video_path,
                language=language,
                model_name=model,
            )
        except Exception as e:
            return {"status": "error", "message": f"Whisper échec : {e}"}

    # ─── burn_subtitles ───
    def _burn_subtitles_handler(
        video_path="LAST", srt_path=None, language=None,
        model="base", **kwargs
    ):
        try:
            from services.vision.whisper_client import (
                generate_subtitles_from_video,
                burn_subtitles_into_video,
            )
            if not srt_path:
                srt_result = generate_subtitles_from_video(
                    video_path=video_path,
                    language=language,
                    model_name=model,
                )
                if srt_result.get("status") == "error":
                    return srt_result
                srt_path = srt_result.get("srt_path")
            return burn_subtitles_into_video(
                video_path=video_path,
                srt_path=srt_path,
            )
        except Exception as e:
            return {"status": "error", "message": f"Burn subs échec : {e}"}

    hermes.register_tool("generate_subtitles", _generate_subtitles_handler, risk_level="L1")
    hermes.register_tool("burn_subtitles", _burn_subtitles_handler, risk_level="L1")

    # ─── hindsight_query ───
    def _hindsight_query_handler(query: str = "", **kwargs):
        if not query:
            return {"status": "error", "message": "query obligatoire"}
        try:
            answer = hindsight_reflect(query)
            if answer:
                return {"status": "success", "answer": answer}
            results = hindsight_recall(query)
            return {"status": "success", "results": results, "answer": ""}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ─── hindsight_recall ───
    def _hindsight_recall_handler(query: str = "", **kwargs):
        if not query:
            return {"status": "error", "message": "query obligatoire"}
        try:
            return {"status": "success", "results": hindsight_recall(query)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    hermes.register_tool("hindsight_query", _hindsight_query_handler, risk_level="L1")
    hermes.register_tool("hindsight_recall", _hindsight_recall_handler, risk_level="L1")
    logger.info("🧠 Outils Hindsight enregistrés : hindsight_query + hindsight_recall")

    # ─── submit_feedback ───
    def _submit_feedback_handler(
        user_query: str = "", agent_response: str = "",
        correction: str = "", feedback_type: str = "correction",
        **kwargs
    ):
        if not user_query or not correction:
            return {"status": "error", "message": "user_query et correction obligatoires"}
        try:
            return _submit_feedback(
                user_query=user_query,
                agent_response=agent_response,
                correction=correction,
                feedback_type=feedback_type,
            )
        except Exception as e:
            return {"status": "error", "message": str(e)}

    hermes.register_tool("submit_feedback", _submit_feedback_handler, risk_level="L1")
    logger.info("🧠 Outil Feedback enregistré : submit_feedback")

    # ══════════════════════════════════════════════════════════════════════
    # ACTIVATION DES NERFS
    # ══════════════════════════════════════════════════════════════════════
    try:
        from nerves import (
            event_bus_nerves, hermes_nerves, skills_nerves, headless_nerves,
            tmux_nerves, web_agent_nerves, guardian_nerves, approval_nerves,
            mcp_nerves, cognitive_nerves, router_nerves,
        )

        _nerve_3_result = event_bus_nerves.activate_event_bus_nerves()
        _nerve_1_result = hermes_nerves.activate_hermes_nerves()
        _nerve_8_result = skills_nerves.activate_skills_nerves()
        _nerve_11_result = headless_nerves.activate_headless_nerves()
        _nerve_14_result = tmux_nerves.activate_tmux_nerves()
        _nerve_4_result = web_agent_nerves.activate_web_agent_nerves()
        _nerve_9_result = guardian_nerves.activate_guardian_nerves()
        _nerve_5_result = approval_nerves.activate_approval_nerves()
        _nerve_6_result = mcp_nerves.activate_mcp_nerves()
        _nerve_2_result = cognitive_nerves.activate_cognitive_nerves()
        _nerve_7_result = router_nerves.activate_router_nerves()

        _nerve_10_result = {
            "status": "disabled",
            "reason": "CRM désactivé (inutile dans BEK-v18)",
        }

        logger.info(
            "🧠 Système nerveux BEK activé | "
            "Nerf 3 : %s | Nerf 1 : %s (%d outils) | Nerf 8 : %s (%d skills) | "
            "Nerf 11-13 : %s (%d headless) | Nerf 14-17 : %s (%d tmux) | "
            "Nerf 4 : %s (%d web) | Nerf 9 : %s (%d guardian) | "
            "Nerf 5 : %s (%d approval) | Nerf 6 : %s (%d mcp) | "
            "Nerf 2 : %s (%d cognitive) | Nerf 7 : %s (%d router) | "
            "Nerf 10 : %s (CRM désactivé)",
            _nerve_3_result.get("status"),
            _nerve_1_result.get("status"), _nerve_1_result.get("activated_count", 0),
            _nerve_8_result.get("status"), _nerve_8_result.get("skills_loaded", 0),
            _nerve_11_result.get("status"), _nerve_11_result.get("activated_count", 0),
            _nerve_14_result.get("status"), _nerve_14_result.get("activated_count", 0),
            _nerve_4_result.get("status"), _nerve_4_result.get("activated_count", 0),
            _nerve_9_result.get("status"), _nerve_9_result.get("activated_count", 0),
            _nerve_5_result.get("status"), _nerve_5_result.get("activated_count", 0),
            _nerve_6_result.get("status"), _nerve_6_result.get("activated_count", 0),
            _nerve_2_result.get("status"), _nerve_2_result.get("activated_count", 0),
            _nerve_7_result.get("status"), _nerve_7_result.get("activated_count", 0),
            _nerve_10_result.get("status"),
        )
    except ImportError as _nerves_import_err:
        logger.warning(
            "⚠️ Paquet nerves/ introuvable (%s). Mode legacy conservé.",
            _nerves_import_err,
        )
    except Exception as _nerves_err:
        logger.error(
            "❌ Activation des nerfs échouée : %s. Mode legacy conservé.",
            _nerves_err,
        )

    os.environ["BEK_BOOTSTRAPPED"] = "1"


# ══════════════════════════════════════════════════════════════════════
# SECURITY GUARD
# ══════════════════════════════════════════════════════════════════════
security_guard = hermes.security_guard
if security_guard is None:
    raise RuntimeError("SecurityGuard Hermes indisponible. Vérifiez BEK_HSM_SECRET.")

GLOBAL_SYSTEM_CONTEXT = load_project_documentation(DOCS_DIR)


# ══════════════════════════════════════════════════════════════════════
# LIFESPAN
# ══════════════════════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_json_logging()
    logger.info("setup_json_logging() exécuté lors du démarrage de l'application.")
    yield

    logger.info("🛑 Arrêt de BEK — nettoyage explicite des services...")
    try:
        from core.tracing import shutdown_tracing
        shutdown_tracing()
        logger.info("✓ OpenTelemetry arrêté proprement.")
    except Exception as exc:
        logger.debug("shutdown_tracing : %s", exc)

    try:
        from event_bus import shutdown_event_bus_sync
        shutdown_event_bus_sync()
        logger.info("✓ EventBus arrêté proprement.")
    except Exception as exc:
        logger.debug("shutdown_event_bus_sync : %s", exc)

    try:
        from hindsight_memory import hindsight_close
        hindsight_close()
        logger.info("✓ Hindsight fermé proprement.")
    except Exception as exc:
        logger.debug("hindsight_close : %s", exc)


# ══════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ══════════════════════════════════════════════════════════════════════
app = FastAPI(
    title="BEK v16 Hybrid FastAPI",
    description="Architecture cognitive modulaire asynchrone haute performance",
    version="18.13",
    lifespan=lifespan,
)

CORS_ORIGINS = os.environ.get(
    "BEK_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:8765,http://127.0.0.1:8765,"
    "http://localhost:3001,http://127.0.0.1:3001",
)
cors_origins = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.onrender\.com|https://.*\.workers\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_anti_cache_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


from core.tracing import init_tracing  # noqa: E402

init_tracing(app)

# ─── ROUTERS ───
app.include_router(admin.router)
app.include_router(files.router)
app.include_router(memory.router)
# app.include_router(crm.router)  # ★ Désactivé v18.12
app.include_router(chat.router)
app.include_router(openai_compat.router)


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════
def _provider_display_name(provider_id: str) -> str:
    names = {
        "agnes":          "Agnes AI (Video)",
        "kimi":           "Moonshot Kimi AI",
        "aisa":           "AIsa (Unified)",
        "b_ai":           "B.ai",
        "groq":           "Groq",
        "nvidia":         "NVIDIA NIM",
        "gemini":         "Google Gemini",
        "openrouter":     "OpenRouter",
        "mistral":        "Mistral AI",
        "cohere":         "Cohere",
        "aionlabs":       "Aion Labs",
        "zhipu":          "Zhipu AI",
        "siliconflow":    "SiliconFlow",
        "ovh_anonymous":  "OVHcloud (Anonyme)",
        "kilo_anonymous": "Kilo Code (Anonyme)",
        "llm7_anonymous": "LLM7.io (Anonyme)",
        "huggingface":    "Hugging Face",
        "ollama_cloud":   "Ollama Cloud",
    }
    return names.get(provider_id, provider_id.replace("_", " ").title())


# ══════════════════════════════════════════════════════════════════════
# ROUTES API
# ══════════════════════════════════════════════════════════════════════
@app.get("/api/config")
async def get_config():
    from provider_manager import provider_manager

    providers = []
    for provider_id, models in provider_manager.PROVIDER_MODELS.items():
        try:
            configured = provider_manager.is_provider_available(provider_id)
        except Exception:
            configured = False
        providers.append({
            "id": provider_id,
            "name": _provider_display_name(provider_id),
            "configured": configured,
        })

    skills_list = []
    try:
        from skills import list_skills as _list_skills
        raw_skills = _list_skills() or []
        for s in raw_skills:
            if not isinstance(s, dict):
                continue
            name = s.get("name") or s.get("command") or "skill"
            skills_list.append({
                "name": name,
                "description": s.get("description", ""),
                "command": s.get("command") or ("/" + name if not name.startswith("/") else name),
            })
    except Exception as exc:
        logger.warning("[api/config] Impossible de charger les skills : %s", exc)

    logger.info(
        "[api/config] %d providers | %d skills retournés",
        len(providers), len(skills_list),
    )

    return {
        "models": provider_manager.PROVIDER_MODELS,
        "providers": providers,
        "skills": skills_list,
        "skills_count": len(skills_list),
    }


@app.post("/api/refresh-architecture")
async def refresh_architecture():
    try:
        from generate_architecture_doc import update_documentation_file
        success = update_documentation_file()
        return {
            "status": "ok" if success else "error",
            "message": "Architecture régénérée avec succès" if success else "Échec de la génération",
        }
    except Exception as exc:
        logger.error("[refresh-architecture] %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════
# HINDSIGHT ROUTES
# ══════════════════════════════════════════════════════════════════════
@app.get("/api/hindsight/status")
async def api_hindsight_status():
    return _hindsight_status()


@app.get("/api/hindsight/query")
async def api_hindsight_query(q: str = ""):
    if not q:
        raise HTTPException(status_code=400, detail="Paramètre 'q' obligatoire")
    if not _HINDSIGHT_AVAILABLE:
        return {"status": "error", "message": "Hindsight non disponible"}
    try:
        answer = hindsight_reflect(q)
        results = hindsight_recall(q)
        return {
            "status": "ok",
            "query": q,
            "answer": answer,
            "results_count": len(results),
            "results": results,
        }
    except Exception as exc:
        logger.error("[hindsight/query] %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════
# FEEDBACK ROUTES
# ══════════════════════════════════════════════════════════════════════
class FeedbackRequest(BaseModel):
    user_query: str
    agent_response: str = ""
    correction: str
    feedback_type: str = "correction"
    rating: Optional[int] = None


@app.post("/api/feedback")
async def api_submit_feedback(req: FeedbackRequest):
    """Enregistre un feedback utilisateur dans Hindsight (ASYNC)."""
    try:
        from feedback_memory import submit_feedback_async
        result = await submit_feedback_async(
            user_query=req.user_query,
            agent_response=req.agent_response,
            correction=req.correction,
            feedback_type=req.feedback_type,
            rating=req.rating,
        )
        return result
    except Exception as exc:
        logger.error("[feedback] %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/feedback")
async def api_list_feedback(limit: int = 50):
    """Liste les derniers feedbacks + statistiques."""
    try:
        return {
            "status": "ok",
            "available": _FEEDBACK_AVAILABLE,
            "stats": _feedback_stats(),
            "feedbacks": _list_feedbacks(limit=limit),
        }
    except Exception as exc:
        logger.error("[feedback/list] %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════
# ADMIN : FLUSH REDIS
# ══════════════════════════════════════════════════════════════════════
@app.post("/api/admin/flush-redis")
async def api_flush_redis():
    """Vide tous les streams Redis."""
    try:
        import redis as _redis_lib
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="redis-py non installé. pip install redis",
        )

    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        raise HTTPException(
            status_code=400,
            detail="REDIS_URL non configuré dans l'environnement",
        )

    try:
        client = _redis_lib.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=10,
            socket_connect_timeout=5,
        )
        client.ping()

        keys_before = client.keys("*")
        count_before = len(keys_before)

        client.flushall()

        keys_after = client.keys("*")
        count_after = len(keys_after)

        logger.warning(
            "[FLUSH-REDIS] %d clés supprimées (%d → %d) | URL=%s",
            count_before - count_after,
            count_before,
            count_after,
            redis_url.split("@")[-1] if "@" in redis_url else redis_url,
        )

        return {
            "status": "ok",
            "redis_url_host": redis_url.split("@")[-1] if "@" in redis_url else redis_url,
            "keys_before": count_before,
            "keys_after": count_after,
            "keys_deleted": count_before - count_after,
            "message": f"Redis vidé : {count_before - count_after} clés supprimées",
        }

    except Exception as exc:
        logger.error("[FLUSH-REDIS] %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ══════════════════════════════════════════════════════════════════════
# ★ v18.13 — HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════
@app.get("/health/worker")
async def health_worker():
    try:
        return {"status": "ok", "worker": "running"}
    except Exception as exc:
        logger.error("Health check du worker a échoué : %s", exc)
        return {"status": "error", "detail": str(exc)}


@app.get("/health/memory")
async def health_memory():
    """
    ★ v18.13 — Health check granulaire de la mémoire + lazy loading.

    Permet de voir :
      - RAM utilisée (si psutil installé)
      - Composants lazy chargés (Playwright, ChromaDB, DuckDB, LanceDB)
      - Stats globales du lazy loader
    """
    # ─── Stats lazy globales ───
    try:
        from core.lazy import lazy_stats as core_lazy_stats
        lazy_stats_data = core_lazy_stats()
    except Exception:
        lazy_stats_data = {"enabled": None, "imports_loaded": [], "imports_count": 0}

    # ─── RAM utilisée (optionnel) ───
    memory_mb = -1
    try:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        memory_mb = round(mem_info.rss / 1024 / 1024, 1)
    except ImportError:
        pass
    except Exception:
        pass

    # ─── Statut des composants ───
    components: Dict[str, Any] = {}

    # Playwright
    try:
        from worker_headless import _playwright_loaded
        components["playwright"] = "loaded" if _playwright_loaded else "lazy"
    except Exception:
        components["playwright"] = "unavailable"

    # ChromaDB
    try:
        from memory import is_chromadb_loaded, is_chromadb_disabled
        if is_chromadb_disabled():
            components["chromadb"] = "disabled"
        elif is_chromadb_loaded():
            components["chromadb"] = "loaded"
        else:
            components["chromadb"] = "lazy"
    except Exception:
        components["chromadb"] = "unavailable"

    # DuckDB (episode_logger)
    try:
        from services.episode_logger import lazy_stats as _el_stats
        el_stats = _el_stats()
        components["duckdb_episode"] = el_stats.get("backend", "unknown")
    except Exception:
        components["duckdb_episode"] = "unavailable"

    # LanceDB + DuckDB analytics (memory_service)
    try:
        from services.memory_service import OptimizedMemoryService
        # On ne crée pas d'instance, on vérifie juste que le module est importable
        components["memory_service"] = "available"
    except Exception:
        components["memory_service"] = "unavailable"

    return {
        "status": "ok",
        "version": "18.13",
        "memory_mb": memory_mb,
        "lazy_global": lazy_stats_data,
        "components": components,
    }


# ══════════════════════════════════════════════════════════════════════
# STATIC FILES
# ══════════════════════════════════════════════════════════════════════
@app.get("/")
async def index():
    return FileResponse(os.path.join(WORKSPACE_DIR, "index.html"))


@app.get("/{filename:path}")
async def serve_static(filename: str):
    target = os.path.join(WORKSPACE_DIR, filename)
    if os.path.exists(target) and os.path.isfile(target):
        return FileResponse(target)
    raise HTTPException(status_code=404, detail="Fichier introuvable")


# ══════════════════════════════════════════════════════════════════════
# SKILLS
# ══════════════════════════════════════════════════════════════════════
class SkillExecutionRequest(BaseModel):
    skill_name: str
    payload: Optional[Dict[str, Any]] = {}
    timeout: int = 30


@app.post("/api/skills/execute")
async def execute_skill_endpoint(request: SkillExecutionRequest):
    result = await skill_runner.execute_skill_async(
        skill_name=request.skill_name,
        payload=request.payload,
        timeout_seconds=request.timeout,
    )
    if result.get("status") in ["error", "timeout"]:
        raise HTTPException(status_code=500, detail=result)
    return result


# ══════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8765"))
    host = os.environ.get("HOST", "0.0.0.0")

    try:
        uvicorn.run("app:app", host=host, port=port, reload=False)
    except KeyboardInterrupt:
        try:
            _sys.stdout.write("\n🔴 BEK — Arrêt forcé. Au revoir.\n")
            _sys.stdout.flush()
        except Exception:
            pass
        _os._exit(0)