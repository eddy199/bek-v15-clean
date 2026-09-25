# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 HYBRID — SERVEUR PRINCIPAL FASTAPI (BOOTSTRAP MODULAIRE)
# ------------------------------------------------------------------------------
# v16.1 (2026-09-20) : generate_video / edit_video acceptent provider/model
# v16.2 (2026-09-21) : extend_video + extend_video_multiple
# v16.3 (2026-09-21) : route /api/config
# v16.4 (2026-09-21) : outils Whisper (generate_subtitles + burn_subtitles)
# v16.5 (2026-09-22) : ★ FIX Ctrl+C — arrêt propre sans blocage atexit
# v18.0 (2026-09-24) : ★ Régénération ARCHITECTURE.md AVANT imports routeurs
# v18.1 (2026-09-25) : ★ Route OpenAI-compatible /v1/chat/completions pour DSH
# ==============================================================================
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════
# ★ FIX CTRL+C — INSTALLÉ AVANT TOUT IMPORT LOURD
# ══════════════════════════════════════════════════════════════════════════════
import signal as _signal
import os as _os
import sys as _sys

def _bek_force_exit(signum, frame):
    try:
        _sys.stdout.write("\n\033[91m🔴 BEK — Arrêt forcé (Ctrl+C). Nettoyage immédiat.\033[0m\n")
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

# ══════════════════════════════════════════════════════════════════════════════
# FIN FIX CTRL+C
# ══════════════════════════════════════════════════════════════════════════════

# Charger env.txt dans os.environ AVANT tout autre import métier
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

try:
    from sub_crm_engine import SubCRMEngine
except ImportError:
    SubCRMEngine = None

try:
    from web_agent import web_agent_instance
except ImportError:
    web_agent_instance = None

try:
    from bek_orchestrator import bek_orchestrator
except ImportError:
    bek_orchestrator = None

try:
    from mcp_gateway import mcp_gateway
except ImportError:
    class MCPGatewayMock:
        def register_mcp_tool(self, **kwargs): pass
        def get_mcp_manifests(self): return []
    mcp_gateway = MCPGatewayMock()

# ══════════════════════════════════════════════════════════════════════════
# ★ v18 — Régénérer ARCHITECTURE.md AVANT d'importer les routeurs
# --------------------------------------------------------------------------
# Ordre critique : prompts.py charge ARCHITECTURE.md à l'import de routers.chat.
# On utilise print() car logger n'est pas encore défini à ce stade.
# ══════════════════════════════════════════════════════════════════════════
try:
    from generate_architecture_doc import update_documentation_file
    if update_documentation_file():
        print("[v18] ✅ ARCHITECTURE.md régénéré AVANT imports routeurs.")
    else:
        print("[v18] ⚠️ Régénération ARCHITECTURE.md retournée False.")
except Exception as exc:
    print(f"[v18] ⚠️ Régénération pré-imports échouée : {exc}")

# --- IMPORT DES ROUTEURS ---
from routers import admin, chat, crm, files, memory
from routers import openai_compat  # ★ v18.1 — adaptateur OpenAI-compatible

# ==========================================
# CONFIGURATION DU LOGGING
# ==========================================
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

# ==========================================
# INITIALISATION GLOBALE & HERMES HOOKS
# ==========================================
_BEK_ALREADY_BOOTSTRAPPED = os.environ.get("BEK_BOOTSTRAPPED") == "1"

if not _BEK_ALREADY_BOOTSTRAPPED:
    try:
        init_sync_log_table()
        init_state_tables()
        if SubCRMEngine:
            SubCRMEngine.initialize_matrix_schema()
        logger.info("Tables Neon DB et schéma Matrix initialisés.")
    except Exception as exc:
        logger.warning("Initialisation DB partielle : %s", exc)

    mcp_gateway.register_mcp_tool(
        name="neon_audit",
        description="Audit des tables relationnelles Neon DB",
        parameters_schema={},
        handler=lambda: {
            "tables": [
                "companies", "contacts", "opportunities",
                "matrix_sub_crms", "bek_task_states", "sync_log",
            ]
        },
    )

    try:
        start_background_workers()
        logger.info("Workers Hermes démarrés avec succès.")
    except Exception as exc:
        logger.error("Impossible de démarrer les workers Hermes : %s", exc)


    def _bek_pre_plan_validator(objective: str, trace_id: str | None):
        return True, "Pre-Plan validé", None

    hermes.register_pre_plan_hook(_bek_pre_plan_validator)

    # ----------------------------------------
    # ENREGISTREMENT DES OUTILS DE L'AGENT
    # ----------------------------------------
    hermes.register_tool(
        "web_sync",
        lambda query="", **kwargs: web_agent_instance.run_pipeline(query) if web_agent_instance else "WebAgent indisponible",
        risk_level="L3",
    )
    hermes.register_tool(
        "orchestrate",
        lambda goal="", **kwargs: bek_orchestrator.run(goal) if bek_orchestrator else "Orchestrateur indisponible",
        risk_level="L2",
    )
    hermes.register_tool(
        "neon_audit",
        lambda **kwargs: {"status": "Neon DB audit demandé", "tables": ["companies", "contacts", "opportunities", "matrix_sub_crms", "sync_log"]},
        risk_level="L1",
    )

    # --- OUTILS MULTIMÉDIA (IMAGES) ---
    hermes.register_tool(
        "generate_image",
        lambda prompt="", query="", **kwargs: generate_image_with_provider(prompt=prompt or query) if generate_image_with_provider else {"status": "error", "message": "Module vision manquant"},
        risk_level="L1",
    )
    hermes.register_tool(
        "edit_image",
        lambda image_paths=None, prompt="", user_prompt="", query="", **kwargs: merge_and_edit_images(
            image_paths=image_paths,
            user_prompt=user_prompt or prompt or query
        ) if merge_and_edit_images else {"status": "error", "message": "Module vision manquant"},
        risk_level="L1",
    )

    # ══════════════════════════════════════════════════════════════════
    # ★ OUTILS VIDÉO v16.1
    # ══════════════════════════════════════════════════════════════════
    hermes.register_tool(
        "generate_video",
        lambda prompt="", query="",
               provider="gemini", model="veo-3.1-gene-prev",
               duration=8, aspect_ratio="16:9", auto_stitch=True,
               negative_prompt=None, person_generation="allow_all",
               **kwargs:
            generate_video_with_provider(
                prompt=prompt or query,
                provider=provider,
                model=model,
                duration=int(duration),
                aspect_ratio=aspect_ratio,
                auto_stitch=bool(auto_stitch),
                negative_prompt=negative_prompt,
                person_generation=person_generation,
            ) if generate_video_with_provider else {"status": "error", "message": "Module vidéo manquant"},
        risk_level="L1",
    )
    hermes.register_tool(
        "edit_video",
        lambda video_paths=None, prompt="", user_prompt="", query="",
               provider="gemini", model="veo-3.1-gene-prev",
               duration=8, aspect_ratio="16:9", auto_stitch=True,
               **kwargs:
            merge_and_edit_videos(
                video_paths=video_paths,
                user_prompt=user_prompt or prompt or query,
                provider=provider,
                model=model,
                duration=int(duration),
                aspect_ratio=aspect_ratio,
                auto_stitch=bool(auto_stitch),
            ) if merge_and_edit_videos else {"status": "error", "message": "Module vidéo manquant"},
        risk_level="L1",
    )

    # ══════════════════════════════════════════════════════════════════
    # ★ EXTENSION VIDÉO v28 — Agnes multi_reference
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # ★ SOUS-TITRES WHISPER (v32)
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # 🧠 ACTIVATION DU SYSTÈME NERVEUX BEK
    # ══════════════════════════════════════════════════════════════════
    try:
        from nerves import (
            event_bus_nerves, hermes_nerves, skills_nerves, headless_nerves,
            tmux_nerves, web_agent_nerves, guardian_nerves, approval_nerves,
            mcp_nerves, cognitive_nerves, router_nerves, crm_nerves,
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
        _nerve_10_result = crm_nerves.activate_crm_nerves()

        logger.info(
            "🧠 Système nerveux BEK activé | "
            "Nerf 3 : %s | Nerf 1 : %s (%d outils) | Nerf 8 : %s (%d skills) | "
            "Nerf 11-13 : %s (%d headless) | Nerf 14-17 : %s (%d tmux) | "
            "Nerf 4 : %s (%d web) | Nerf 9 : %s (%d guardian) | "
            "Nerf 5 : %s (%d approval) | Nerf 6 : %s (%d mcp) | "
            "Nerf 2 : %s (%d cognitive) | Nerf 7 : %s (%d router) | "
            "Nerf 10 : %s (%d crm)",
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
            _nerve_10_result.get("status"), _nerve_10_result.get("activated_count", 0),
        )
    except ImportError as _nerves_import_err:
        logger.warning("⚠️ Paquet nerves/ introuvable (%s). Mode legacy conservé.", _nerves_import_err)
    except Exception as _nerves_err:
        logger.error("❌ Activation des nerfs échouée : %s. Mode legacy conservé.", _nerves_err)

    os.environ["BEK_BOOTSTRAPPED"] = "1"

security_guard = hermes.security_guard
if security_guard is None:
    raise RuntimeError("SecurityGuard Hermes indisponible. Vérifiez BEK_HSM_SECRET.")

GLOBAL_SYSTEM_CONTEXT = load_project_documentation(DOCS_DIR)

# ==========================================
# GESTION DU CYCLE DE VIE (LIFESPAN)
# ==========================================
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


# ==========================================
# APPLICATION FASTAPI & MONTAGE DES ROUTES
# ==========================================
app = FastAPI(
    title="BEK v16 Hybrid FastAPI",
    description="Architecture cognitive modulaire asynchrone haute performance",
    version="18.1",
    lifespan=lifespan,
)

CORS_ORIGINS = os.environ.get(
    "BEK_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8765,http://127.0.0.1:8765,http://localhost:3001,http://127.0.0.1:3001",
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


# ══════════════════════════════════════════════════════════════════
# 🔭 OPENTELEMETRY
# ══════════════════════════════════════════════════════════════════
from core.tracing import init_tracing, shutdown_tracing  # noqa: E402

init_tracing(app)

# Inclusion des routeurs modulaires
app.include_router(admin.router)
app.include_router(files.router)
app.include_router(memory.router)
app.include_router(crm.router)
app.include_router(chat.router)
app.include_router(openai_compat.router)  # ★ v18.1 — /v1/chat/completions + /v1/models


# ══════════════════════════════════════════════════════════════════
# ★ v16.3 — ROUTE /api/config (pour l'UI)
# ══════════════════════════════════════════════════════════════════
def _provider_display_name(provider_id: str) -> str:
    """Nom affiché pour chaque provider dans l'UI."""
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


@app.get("/api/config")
async def get_config():
    """Retourne la config des providers + modèles + skills pour l'UI."""
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


# ══════════════════════════════════════════════════════════════════
# ★ v18 — ROUTE /api/refresh-architecture
# ------------------------------------------------------------------
# Régénère ARCHITECTURE.md à chaud après modification du code
# (nouveaux outils, nerfs, briques, etc.)
# ══════════════════════════════════════════════════════════════════
@app.post("/api/refresh-architecture")
async def refresh_architecture():
    """Régénère docs/ARCHITECTURE.md à chaud."""
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


# ---------- Endpoint de health check du worker headless ----------
@app.get("/health/worker")
async def health_worker():
    try:
        return {"status": "ok", "worker": "running"}
    except Exception as exc:
        logger.error("Health check du worker a échoué : %s", exc)
        return {"status": "error", "detail": str(exc)}


# Fichiers statiques et index
@app.get("/")
async def index():
    return FileResponse(os.path.join(WORKSPACE_DIR, "index.html"))


@app.get("/{filename:path}")
async def serve_static(filename: str):
    target = os.path.join(WORKSPACE_DIR, filename)
    if os.path.exists(target) and os.path.isfile(target):
        return FileResponse(target)
    raise HTTPException(status_code=404, detail="Fichier introuvable")


# --- Modèle de requête pour l'exécution des compétences ---
class SkillExecutionRequest(BaseModel):
    skill_name: str
    payload: Optional[Dict[str, Any]] = {}
    timeout: int = 30


# --- Endpoint API d'exécution ---
@app.post("/api/skills/execute")
async def execute_skill_endpoint(request: SkillExecutionRequest):
    result = await skill_runner.execute_skill_async(
        skill_name=request.skill_name,
        payload=request.payload,
        timeout_seconds=request.timeout
    )

    if result.get("status") in ["error", "timeout"]:
        raise HTTPException(status_code=500, detail=result)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# ★ FIX CTRL+C — WRAPPER UVICORN
# ══════════════════════════════════════════════════════════════════════════════
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