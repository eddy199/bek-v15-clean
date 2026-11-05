# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v19 HYBRID — SERVEUR PRINCIPAL FASTAPI (v19.12 — RENDER READY)
# ==============================================================================
from __future__ import annotations
import os as _os
import sys as _sys
import asyncio
import socketio

_ROUTERS_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "routers")
if _ROUTERS_DIR not in _sys.path: _sys.path.append(_ROUTERS_DIR)

try:
    import provider_manager
except ImportError:
    try:
        from core.llm import provider_manager as _pm_mod
        _sys.modules["provider_manager"] = _pm_mod
        print("[BEK v19.1] Shim provider_manager → core.llm.provider_manager")
    except ImportError:
        print("[BEK v19.1] ⚠️ provider_manager introuvable")

import signal as _signal
def _bek_force_exit(signum, frame):
    try: _sys.stdout.write("\n\033[91m🔴 BEK — Arrêt forcé (Ctrl+C).\033[0m\n"); _sys.stdout.flush()
    except Exception: pass
    _os._exit(0)
try:
    _signal.signal(_signal.SIGINT, _bek_force_exit)
    if hasattr(_signal, "SIGBREAK"): _signal.signal(_signal.SIGBREAK, _bek_force_exit)
except Exception: pass

from env_loader import load_env
load_env()

from typing import Any, Dict, Optional
from pydantic import BaseModel
import skill_runner, logging, os, sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, HTTPException, Request, Body, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from context_loader import load_project_documentation
from core.logger import setup_json_logging
from core.paths import DOCS_DIR, WORKSPACE_DIR
from hermes_core import hermes

try:
    from hermes_core import start_background_workers  # type: ignore
except ImportError:
    _fallback = getattr(hermes, "start_workers", None) or getattr(hermes, "start_background_workers", None)
    if callable(_fallback):
        start_background_workers = _fallback
        print("[BEK v19.10] ⚠️ start_background_workers absent du module → fallback hermes.start_workers()")
    else:
        start_background_workers = lambda: None
        print("[BEK v19.10] ⚠️ start_background_workers introuvable — workers désactivés")

from memory import init_sync_log_table
from state_synchronizer import init_state_tables
from core.brain import get_brain

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "services"))
try:
    from reflex_loop import ReflexLoop
    _REFLEX_AVAILABLE = True
    print("✅ [BEK] ReflexLoop chargé depuis services/reflex_loop.py")
except ImportError as _reflex_err:
    ReflexLoop = None
    _REFLEX_AVAILABLE = False
    print(f"⚠️ [BEK] ReflexLoop introuvable : {_reflex_err}")

_VISION_MODULE = None
_VISION_IMPORT_FAILED = False

def _get_vision():
    global _VISION_MODULE, _VISION_IMPORT_FAILED
    if _VISION_IMPORT_FAILED: return None
    if _VISION_MODULE is not None: return _VISION_MODULE
    try:
        from services import vision as _v
        _VISION_MODULE = _v
        print("[BEK v19.7] ✅ services.vision chargé à la demande")
        return _v
    except ImportError as e:
        _VISION_IMPORT_FAILED = True
        print(f"[BEK v19.7] ⚠️ services.vision indisponible : {e}")
        return None

async def _preload_vision_background():
    await asyncio.sleep(5)
    try:
        print("[BEK v19.7] ⏳ Pré-chargement de services.vision (torch) en arrière-plan...")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _get_vision)
        print("[BEK v19.7] ✅ services.vision pré-chargé avec succès.")
    except Exception as e:
        print(f"[BEK v19.7] ⚠️ Échec du pré-chargement vision : {e}")

def generate_image_with_provider(*args, **kwargs):
    v = _get_vision()
    return v.generate_image_with_provider(*args, **kwargs) if v else {"status": "error", "message": "vision indisponible"}
def merge_and_edit_images(*args, **kwargs):
    v = _get_vision()
    return v.merge_and_edit_images(*args, **kwargs) if v else {"status": "error", "message": "vision indisponible"}
def generate_video_with_provider(*args, **kwargs):
    v = _get_vision()
    return v.generate_video_with_provider(*args, **kwargs) if v else {"status": "error", "message": "vision indisponible"}
def merge_and_edit_videos(*args, **kwargs):
    v = _get_vision()
    return v.merge_and_edit_videos(*args, **kwargs) if v else {"status": "error", "message": "vision indisponible"}
def extend_video_with_agnes(*args, **kwargs):
    v = _get_vision()
    return v.extend_video_with_agnes(*args, **kwargs) if v else {"status": "error", "message": "vision indisponible"}
def extend_video_multiple(*args, **kwargs):
    v = _get_vision()
    return v.extend_video_multiple(*args, **kwargs) if v else {"status": "error", "message": "vision indisponible"}

_web_agent_instance = None
_web_agent_loaded = False

def _get_web_agent():
    global _web_agent_instance, _web_agent_loaded
    if _web_agent_loaded: return _web_agent_instance
    _web_agent_loaded = True
    try:
        from web_agent import web_agent_instance as wa
        _web_agent_instance = wa
        print("[BEK v19.8] ✅ web_agent chargé à la demande")
    except ImportError as e:
        print(f"[BEK v19.8] ⚠️ web_agent indisponible : {e}")
        _web_agent_instance = None
    return _web_agent_instance

_bek_orchestrator_instance = None
_bek_orch_loaded = False

def _get_orchestrator():
    global _bek_orchestrator_instance, _bek_orch_loaded
    if _bek_orch_loaded: return _bek_orchestrator_instance
    _bek_orch_loaded = True
    try:
        from bek_orchestrator import bek_orchestrator as bo
        _bek_orchestrator_instance = bo
        print("[BEK v19.8] ✅ bek_orchestrator chargé à la demande")
    except ImportError as e:
        print(f"[BEK v19.8] ⚠️ bek_orchestrator indisponible : {e}")
        _bek_orchestrator_instance = None
    return _bek_orchestrator_instance

try: from mcp_gateway import mcp_gateway
except ImportError:
    class MCPGatewayMock:
        def register_mcp_tool(self, **kwargs): pass
        def get_mcp_manifests(self): return []
    mcp_gateway = MCPGatewayMock()

try:
    from hindsight_memory import hindsight_reflect, hindsight_recall, hindsight_status as _hindsight_status
    _HINDSIGHT_AVAILABLE = True
except ImportError:
    _HINDSIGHT_AVAILABLE = False
    def hindsight_reflect(q): return ""
    def hindsight_recall(q): return []
    def _hindsight_status(): return {"enabled": False, "connected": False}

try:
    from feedback_memory import submit_feedback as _submit_feedback, list_feedbacks as _list_feedbacks, feedback_stats as _feedback_stats, process_pending_feedbacks as _process_pending_feedbacks
    _FEEDBACK_AVAILABLE = True
except ImportError: _FEEDBACK_AVAILABLE = False

try:
    from generate_architecture_doc import update_documentation_file, get_architecture_status, start_watcher as _archigen_start_watcher, stop_watcher as _archigen_stop_watcher
    _ARCHIGEN_AVAILABLE = True
except ImportError: _ARCHIGEN_AVAILABLE = False

async def _background_archi_regen():
    await asyncio.sleep(10)
    try:
        from generate_architecture_doc import update_documentation_file
        loop = asyncio.get_event_loop()
        changed = await loop.run_in_executor(None, lambda: update_documentation_file(force=False))
        if changed: print("[BEK v19.8] ✅ ARCHITECTURE.md régénéré (background)")
        else: print("[BEK v19.8] ℹ️ ARCHITECTURE.md inchangé")
    except Exception as exc: print(f"[BEK v19.8] ⚠️ Régénération ARCHITECTURE.md échouée : {exc}")

from routers import admin, chat, files, memory
from routers import openai_compat

logger = logging.getLogger("BEKApp")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = RotatingFileHandler(os.path.join(WORKSPACE_DIR, "bek_app.log"), maxBytes=10_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(ch)

_BEK_ALREADY_BOOTSTRAPPED = os.environ.get("BEK_BOOTSTRAPPED") == "1"

if not _BEK_ALREADY_BOOTSTRAPPED:
    try: init_sync_log_table(); init_state_tables(); logger.info("Tables PostgreSQL initialisées.")
    except Exception as exc: logger.warning("Initialisation DB partielle : %s", exc)

    mcp_gateway.register_mcp_tool(name="neon_audit", description="Audit des tables", parameters_schema={}, handler=lambda: {"tables": ["companies", "contacts", "opportunities", "bek_task_states", "sync_log"]})
    try: start_background_workers()
    except Exception as exc: logger.error("Impossible de démarrer les workers Hermes : %s", exc)

    try:
        n = _process_pending_feedbacks()
        if n > 0: logger.info("✓ %d feedbacks traités.", n)
    except Exception: pass

    hermes.register_tool("web_sync", lambda query="", **kwargs: (_get_web_agent().run_pipeline(query) if _get_web_agent() else "WebAgent indisponible"), risk_level="L3")
    hermes.register_tool("orchestrate", lambda goal="", **kwargs: (_get_orchestrator().run(goal) if _get_orchestrator() else "Orchestrateur indisponible"), risk_level="L2")
    hermes.register_tool("save_memory", lambda content="", text="", **kwargs: {"status": "success", "message": "Mémorisé"}, risk_level="L1")
    hermes.register_tool("neon_audit", lambda **kwargs: {"status": "Audit DB", "tables": ["companies", "contacts", "opportunities", "sync_log"]}, risk_level="L1")
    hermes.register_tool("generate_image", lambda prompt="", query="", **kwargs: generate_image_with_provider(prompt=prompt or query), risk_level="L1")
    hermes.register_tool("edit_image", lambda image_paths=None, prompt="", user_prompt="", query="", **kwargs: merge_and_edit_images(image_paths=image_paths, user_prompt=user_prompt or prompt or query), risk_level="L1")

    def _generate_video_handler(prompt="", query="", image_paths=None, reference_images=None, video_paths=None, provider="agnes", model="agnes-v2.0", duration=8, aspect_ratio="16:9", auto_stitch=True, with_audio=True, audio_style="children", negative_prompt=None, person_generation="allow_all", mode=None, **kwargs):
        refs = reference_images or image_paths
        if refs and mode is None: mode = "multi_reference" if isinstance(refs, list) and len(refs) > 1 else "keyframes"
        call_kwargs = {"prompt": prompt or query, "provider": provider, "model": model, "duration": int(duration), "aspect_ratio": aspect_ratio, "auto_stitch": bool(auto_stitch), "with_audio": bool(with_audio), "audio_style": audio_style, "negative_prompt": negative_prompt, "person_generation": person_generation}
        try: return generate_video_with_provider(**call_kwargs)
        except Exception as exc: return {"status": "error", "message": str(exc)}

    hermes.register_tool("generate_video", _generate_video_handler, risk_level="L1")
    hermes.register_tool("edit_video", lambda video_paths=None, prompt="", user_prompt="", query="", provider="gemini", model="veo-3.1-gene-prev", duration=8, aspect_ratio="16:9", auto_stitch=True, **kwargs: merge_and_edit_videos(video_paths=video_paths, user_prompt=user_prompt or prompt or query, provider=provider, model=model, duration=int(duration), aspect_ratio=aspect_ratio, auto_stitch=bool(auto_stitch)), risk_level="L1")

    def _extend_video_handler(video_path="LAST", prompt="", new_prompt="", duration=9, with_audio=True, audio_style="nature", **kwargs):
        try: return extend_video_with_agnes(video_path=video_path, new_prompt=new_prompt or prompt, duration=int(duration), with_audio=bool(with_audio), audio_style=audio_style)
        except Exception as e: return {"status": "error", "message": str(e)}
    hermes.register_tool("extend_video", _extend_video_handler, risk_level="L1")

    def _extend_video_multiple_handler(video_path="LAST", prompts=None, duration=9, with_audio=True, audio_style="nature", max_clips=5, **kwargs):
        try: return extend_video_multiple(video_path=video_path, prompts=prompts or [], duration_per_clip=int(duration), with_audio=bool(with_audio), audio_style=audio_style, max_clips=int(max_clips))
        except Exception as e: return {"status": "error", "message": str(e)}
    hermes.register_tool("extend_video_multiple", _extend_video_multiple_handler, risk_level="L1")

    def _generate_subtitles_handler(video_path="LAST", language=None, model="base", **kwargs):
        try:
            from services.vision.whisper_client import generate_subtitles_from_video
            return generate_subtitles_from_video(video_path=video_path, language=language, model_name=model)
        except Exception as e: return {"status": "error", "message": str(e)}
    hermes.register_tool("generate_subtitles", _generate_subtitles_handler, risk_level="L1")

    def _burn_subtitles_handler(video_path="LAST", srt_path=None, language=None, model="base", **kwargs):
        try:
            from services.vision.whisper_client import generate_subtitles_from_video, burn_subtitles_into_video
            if not srt_path:
                res = generate_subtitles_from_video(video_path=video_path, language=language, model_name=model)
                if res.get("status") == "error": return res
                srt_path = res.get("srt_path")
            return burn_subtitles_into_video(video_path=video_path, srt_path=srt_path)
        except Exception as e: return {"status": "error", "message": str(e)}
    hermes.register_tool("burn_subtitles", _burn_subtitles_handler, risk_level="L1")

    def _hindsight_query_handler(query: str = "", **kwargs):
        if not query: return {"status": "error", "message": "query obligatoire"}
        try:
            answer = hindsight_reflect(query)
            return {"status": "success", "answer": answer} if answer else {"status": "success", "results": hindsight_recall(query), "answer": ""}
        except Exception as e: return {"status": "error", "message": str(e)}
    hermes.register_tool("hindsight_query", _hindsight_query_handler, risk_level="L1")

    def _hindsight_recall_handler(query: str = "", **kwargs):
        if not query: return {"status": "error"}
        try: return {"status": "success", "results": hindsight_recall(query)}
        except Exception as e: return {"status": "error", "message": str(e)}
    hermes.register_tool("hindsight_recall", _hindsight_recall_handler, risk_level="L1")

    def _submit_feedback_handler(user_query: str = "", agent_response: str = "", correction: str = "", feedback_type: str = "correction", **kwargs):
        if not user_query or not correction: return {"status": "error"}
        try: return _submit_feedback(user_query=user_query, agent_response=agent_response, correction=correction, feedback_type=feedback_type)
        except Exception as e: return {"status": "error", "message": str(e)}
    hermes.register_tool("submit_feedback", _submit_feedback_handler, risk_level="L1")

    try:
        from nerves import event_bus_nerves, hermes_nerves, skills_nerves, headless_nerves, tmux_nerves, web_agent_nerves, guardian_nerves, approval_nerves, mcp_nerves, cognitive_nerves, router_nerves, coder_nerves, project_creator_nerves
        event_bus_nerves.activate_event_bus_nerves()
        hermes_nerves.activate_hermes_nerves()
        skills_nerves.activate_skills_nerves()
        headless_nerves.activate_headless_nerves()
        tmux_nerves.activate_tmux_nerves()
        web_agent_nerves.activate_web_agent_nerves()
        guardian_nerves.activate_guardian_nerves()
        approval_nerves.activate_approval_nerves()
        mcp_nerves.activate_mcp_nerves()
        cognitive_nerves.activate_cognitive_nerves()
        router_nerves.activate_router_nerves()
        coder_nerves.activate_coder_nerves()
        # ★ NERF 20 — BEK-GA (Moteur Génétique)
        from nerves.ga_nerves import activate_ga_nerves
        activate_ga_nerves()
        
        # ★ v19.1 : Initialiser les clients mémoire au boot
        try:
            from memory import get_pinecone_index, _init_pg_pool
            _ = get_pinecone_index()
            _ = _init_pg_pool()
            # ★ AJOUT : Pré-initialisation de Hindsight
            from hindsight_memory import _get_client as _get_hindsight_client
            _ = _get_hindsight_client()
            # ★ AJOUT : Pré-initialisation de ChromaDB (évite 1.6s de lazy load au 1er chat)
            try:
                from memory import _get_chroma_collection
                _ = _get_chroma_collection()
                logger.info("✅ [Boot] ChromaDB pré-initialisé")
            except ImportError:
                logger.info("ℹ️ [Boot] ChromaDB lazy (module optionnel)")
            logger.info("✅ [Boot] Clients mémoire pré-initialisés (Pinecone + PostgreSQL + Hindsight + ChromaDB)")
        except Exception as exc:
            logger.warning("⚠️ [Boot] Pré-init mémoire partielle : %s", exc)
        project_creator_nerves.activate_project_creator_nerves()
    except Exception as _nerves_err: logger.error("❌ Activation des nerfs échouée : %s", _nerves_err)

    # ★ AJOUT 2 : Connecteur REA-Agents (Reverse Engineering)
    try:
        from mcp_gateway import mcp_gateway
        from rea_agents_bridge import sync_call_rea_agents_tool
        from nerves.mcp_nerves import register_mcp_tool_into_hermes

        # Outil 1 : Analyse de binaires natifs
        mcp_gateway.register_mcp_tool(
            name="rea_analyze_binary",
            description="Analyse un fichier binaire local (exe, dll, so, elf) avec REA.",
            parameters_schema={"file_path": "str"},
            handler=lambda file_path=None, path=None, **kwargs: sync_call_rea_agents_tool(
                "inspect_native_binary",
                {"path": file_path or path or ""}
            )
        )

        # Outil 2 : Analyse JavaScript/Electron
        mcp_gateway.register_mcp_tool(
            name="rea_analyze_javascript",
            description="Analyse une application JavaScript/Electron locale avec REA. Paramètre obligatoire : input_path (chemin absolu vers le fichier ou dossier).",
            parameters_schema={"input_path": "str"},
            handler=lambda input_path=None, path=None, app_path=None, file_path=None, **kwargs: sync_call_rea_agents_tool(
                "analyze_javascript_application",
                {"input_path": input_path or path or app_path or file_path or ""}
            )
        )

        register_mcp_tool_into_hermes("rea_analyze_binary", risk_level="L2")
        register_mcp_tool_into_hermes("rea_analyze_javascript", risk_level="L2")

        logger.info("✅ [REA-Agents] Connecteur Reverse Engineering branché sur Hermes.")
    except Exception as _rea_agents_err:
        logger.warning("⚠️ [REA-Agents] Connecteur indisponible : %s", _rea_agents_err)

    # ★ AJOUT 3 : Connecteur Python (analyse de code source)
    try:
        from mcp_gateway import mcp_gateway
        from python_bridge import sync_call_python_tool
        from nerves.mcp_nerves import register_mcp_tool_into_hermes

        mcp_gateway.register_mcp_tool(
            name="python_analyze_file",
            description="Analyse un fichier Python (classes, fonctions, imports). Paramètre : file_path.",
            parameters_schema={"file_path": "str"},
            handler=lambda file_path=None, path=None, **kwargs: sync_call_python_tool(
                "analyze_python_file",
                {"file_path": file_path or path or ""}
            )
        )

        mcp_gateway.register_mcp_tool(
            name="python_analyze_directory",
            description="Analyse tous les fichiers .py d'un dossier et détecte les anomalies. Paramètre : dir_path.",
            parameters_schema={"dir_path": "str"},
            handler=lambda dir_path=None, path=None, **kwargs: sync_call_python_tool(
                "analyze_python_directory",
                {"dir_path": dir_path or path or ""}
            )
        )

        def _python_save_report_handler(dir_path=None, path=None, output_name=None, **kwargs):
            """Génère le rapport ET force l'analyse par le LLM."""
            from python_bridge import sync_call_python_tool
            result = sync_call_python_tool(
                "save_python_analysis_report",
                {"dir_path": dir_path or path or "", "output_name": output_name or ""}
            )
            
            # Ajoute une instruction pour forcer l'interprétation
            try:
                import json
                res_data = json.loads(result)
                if res_data.get("status") == "success":
                    md_path = res_data.get("markdown")
                    if md_path:
                        # On ajoute une directive explicite
                        return f"{result}\n\nINSTRUCTION: Tu DOIS maintenant lire le fichier '{md_path}' avec l'outil 'read_file' et ensuite m'expliquer les problèmes de structure détectés (fichiers trop gros, classes trop longues, etc.) et proposer des solutions."
            except Exception:
                pass
            
            return result
        
        mcp_gateway.register_mcp_tool(
            name="python_save_report",
            description="Analyse un dossier Python et sauvegarde le rapport (Markdown + JSON) dans generated/. Paramètre : dir_path, output_name (optionnel).",
            parameters_schema={"dir_path": "str", "output_name": "str"},
            handler=_python_save_report_handler
        )

        register_mcp_tool_into_hermes("python_analyze_file", risk_level="L1")
        register_mcp_tool_into_hermes("python_analyze_directory", risk_level="L1")
        register_mcp_tool_into_hermes("python_save_report", risk_level="L1")
        logger.info("✅ [Python] Connecteur d'analyse Python branché sur Hermes.")
    except Exception as _py_err:
        logger.warning("⚠️ [Python] Connecteur indisponible : %s", _py_err)

    try: _archigen_start_watcher(interval_sec=60)
    except Exception: pass

    os.environ["BEK_BOOTSTRAPPED"] = "1"

security_guard = hermes.security_guard
if security_guard is None: raise RuntimeError("SecurityGuard Hermes indisponible.")
GLOBAL_SYSTEM_CONTEXT = load_project_documentation(DOCS_DIR)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*", logger=False, engineio_logger=False)
_reflex_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _reflex_instance
    setup_json_logging()
    try:
        await get_brain().boot()
        logger.info("🧠 [BEK Brain] Cerveau initialisé")
    except Exception as exc: logger.warning("⚠️ [BEK Brain] Boot partiel : %s", exc)

    asyncio.create_task(_preload_vision_background())
    asyncio.create_task(_background_archi_regen())

    autonomous_task = None
    if _REFLEX_AVAILABLE and ReflexLoop is not None:
        try:
            _reflex_instance = ReflexLoop(sio=sio)
            autonomous_task = asyncio.create_task(_reflex_instance.start_autonomous(interval_sec=120, auto_fix=True))
            logger.info("🔁 [ReflexLoop] Mode autonome démarré")
        except Exception as exc:
            logger.warning("⚠️ [ReflexLoop] Démarrage autonome échoué : %s", exc)
            _reflex_instance = None
            autonomous_task = None
    else:
        logger.warning("⚠️ [ReflexLoop] Module indisponible → autonome désactivé")

    yield

    if _reflex_instance is not None:
        try: _reflex_instance.stop_autonomous()
        except Exception as exc: logger.debug("[ReflexLoop] stop_autonomous : %s", exc)
    if autonomous_task is not None:
        autonomous_task.cancel()
        try: await autonomous_task
        except asyncio.CancelledError: pass
        except Exception as exc: logger.debug("[ReflexLoop] task shutdown : %s", exc)
    logger.info("🔁 [ReflexLoop] Arrêté proprement")
    _reflex_instance = None

    try:
        from bek.episode_logger import close_all as _close_episode_db
        _close_episode_db()
    except Exception: pass
    try: await get_brain().shutdown()
    except Exception: pass
    try: _archigen_stop_watcher()
    except Exception: pass
    try:
        from core.tracing import shutdown_tracing
        shutdown_tracing()
    except Exception: pass
    try:
        from event_bus import shutdown_event_bus_sync
        shutdown_event_bus_sync()
    except Exception: pass
    try:
        from hindsight_memory import hindsight_close
        hindsight_close()
    except Exception: pass


app = FastAPI(title="BEK Hybrid Agent v19", description="Créé par BEKKARA Mohamed — Oran, DZ", version="19.11", lifespan=lifespan)

CORS_ORIGINS = os.environ.get("BEK_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8765,http://127.0.0.1:8765,http://localhost:3001,http://127.0.0.1:3001,http://localhost:5173,http://127.0.0.1:5173")
cors_origins = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def add_anti_cache_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"; response.headers["Expires"] = "0"
    return response

from core.tracing import init_tracing
init_tracing(app)

@app.post("/api/audio/duck")
async def audio_duck(data: dict = Body(...)):
    vol = float(data.get("volume", 0.15))
    try:
        from core.audio.manager import audio_manager
        await audio_manager.duck(vol)
    except Exception as e: logger.error("[Audio Duck] %s", e)
    return {"status": "ducked", "volume": vol, "chat_boot": "ALIVE"}

@app.post("/api/audio/unduck")
async def audio_unduck():
    try:
        from core.audio.manager import audio_manager
        await audio_manager.unduck()
    except Exception as e: logger.error("[Audio Unduck] %s", e)
    return {"status": "unducked", "volume": 1.0}

@app.get("/api/branding")
async def branding():
    return {"title": "BEK Hybrid Agent v19", "version": "19.11", "creator": "BEKKARA Mohamed", "location": "Oran, DZ", "date": "Oct 2026", "workspace": "workspacekimi"}

@app.post("/api/brain/chat")
async def brain_chat(data: dict = Body(...)):
    try:
        brain = get_brain()
        session_id = data.get("conv_id") or data.get("session_id") or "default"

        return await brain.process(
            query=data.get("query", data.get("message", "")),
            provider=data.get("provider"),
            model=data.get("model"),
            files=data.get("files", []),
            session_id=session_id
        )
    except Exception as exc:
        logger.error("[brain/chat] %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))

@app.get("/api/brain/status")
async def brain_status():
    try: return get_brain().status()
    except Exception as exc: return {"status": "error", "message": str(exc)}

@app.get("/api/brain/provider-health")
async def brain_provider_health():
    try:
        from provider_manager import provider_manager
        return {
            "status": "ok",
            "health": provider_manager.get_provider_health(),
            "configured": {
                p: provider_manager.is_provider_available(p)
                for p in provider_manager.PROVIDER_MODELS
            },
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

class ReflexTrigger(BaseModel):
    hours: int = 24
    auto_fix: bool = True

@app.post("/api/reflex/run")
async def api_reflex_run(trigger: ReflexTrigger):
    if not _REFLEX_AVAILABLE or ReflexLoop is None:
        raise HTTPException(503, "ReflexLoop indisponible")
    try:
        reflex = _reflex_instance or ReflexLoop(sio=sio)
        result = await reflex.run_cycle(hours=trigger.hours, auto_fix=trigger.auto_fix)
        return {"status": "success", "report": result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/reflex/stats")
async def api_reflex_stats():
    return {"status": "ok", "reports": [], "autonomous": _reflex_instance is not None}

app.include_router(admin.router)
app.include_router(files.router)
app.include_router(memory.router)
app.include_router(chat.router)
app.include_router(openai_compat.router)

def _provider_display_name(provider_id: str) -> str:
    names = {"agnes": "Agnes AI", "kimi": "Kimi AI", "b_ai": "B.ai", "groq": "Groq", "nvidia": "NVIDIA NIM", "gemini": "Google Gemini", "openrouter": "OpenRouter", "mistral": "Mistral AI", "cohere": "Cohere", "huggingface": "Hugging Face", "beatapi": "BeatAPI.io"}
    return names.get(provider_id, provider_id.replace("_", " ").title())

@app.get("/api/config")
async def get_config():
    try:
        from provider_manager import provider_manager
    except ImportError:
        try:
            from core.llm.provider_manager import provider_manager
        except ImportError:
            raise HTTPException(503, "provider_manager introuvable")

    providers = [{"id": p_id, "name": _provider_display_name(p_id), "configured": provider_manager.is_provider_available(p_id)} for p_id in provider_manager.PROVIDER_MODELS]

    skills_data = []
    try:
        from skill_runner import list_skills as _list_skills
        skills_data = _list_skills()
        print(f"[DEBUG API CONFIG] {len(skills_data)} compétences envoyées : {[s['name'] for s in skills_data]}")
    except Exception as e:
        logger.error(f"[API Config] Erreur chargement skills: {e}")

    return {
        "models": provider_manager.PROVIDER_MODELS,
        "providers": providers,
        "provider_health": provider_manager.get_provider_health(),
        "skills": skills_data,
        "tools": skills_data
    }

@app.get("/api/files")
async def api_files_fallback():
    try:
        from core.storage.file_manager import file_manager
        files_list = await file_manager.list_workspace_files()
        return {"files": files_list, "count": len(files_list)}
    except Exception as exc: return {"files": [], "count": 0, "error": str(exc)}

@app.post("/api/files/upload")
async def api_files_upload_fallback(file: UploadFile = File(...)):
    try:
        from core.storage.file_manager import file_manager
        content = await file.read()
        meta = await file_manager.save_upload(content, file.filename or "upload.bin")
        return {"status": "ok", **meta}
    except Exception as exc: raise HTTPException(500, str(exc))

@app.get("/")
@app.head("/")
async def index(): return FileResponse(os.path.join(WORKSPACE_DIR, "index.html"))

@app.get("/{filename:path}")
async def serve_static(filename: str):
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        raise HTTPException(status_code=403, detail="Accès interdit.")

    basename = os.path.basename(filename).lower()
    blocked_names = {".env", "env.txt", ".env.local", ".env.production", "credentials.json", "id_rsa", "id_ed25519"}
    blocked_ext = {".txt", ".py", ".log", ".db", ".sqlite", ".bak", ".key", ".pem", ".env"}
    ext = os.path.splitext(basename)[1].lower()
    if basename in blocked_names or ext in blocked_ext:
        raise HTTPException(status_code=403, detail="Accès interdit aux fichiers de configuration.")

    try:
        from security_guard import SecurityGuard
        if basename in SecurityGuard.BLOCKED_SENSITIVE_FILES:
            raise HTTPException(status_code=403, detail="Fichier sensible bloqué.")
    except ImportError:
        pass

    target = os.path.join(WORKSPACE_DIR, filename)
    if os.path.exists(target) and os.path.isfile(target):
        return FileResponse(target)

    raise HTTPException(status_code=404, detail="Fichier introuvable")

@sio.event
async def connect(sid, environ): logger.info("[Socket.io] ✅ client connecté : %s", sid)

@sio.event
async def disconnect(sid): logger.info("[Socket.io] client déconnecté : %s", sid)

@sio.event
async def audio_duck(sid, data): await sio.emit("audio:duck", data or {}, skip_sid=sid)

@sio.event
async def audio_unduck(sid): await sio.emit("audio:unduck", {}, skip_sid=sid)

@sio.event
async def tool_start(sid, data): await sio.emit("tool:start", data or {}, skip_sid=sid)

@sio.event
async def tool_end(sid): await sio.emit("tool:end", {}, skip_sid=sid)

@sio.event
async def dag_node(sid, data): await sio.emit("dag:node", data or {}, skip_sid=sid)

@sio.event
async def dag_update(sid, data): await sio.emit("dag:update", data or {}, skip_sid=sid)

app = socketio.ASGIApp(sio, app)
logger.info("[Socket.io] ✅ monté sur /socket.io (ASGIApp)")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "3001"))
    host = os.environ.get("HOST", "0.0.0.0")
    try:
        logger.info("🚀 Démarrage de BEK sur %s:%s", host, port)
        uvicorn.run(app, host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        try:
            _sys.stdout.write("\n🔴 BEK — Arrêt forcé.\n")
            _sys.stdout.flush()
        except Exception:
            pass
        _os._exit(0)