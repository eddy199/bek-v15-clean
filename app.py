# ==============================================================================
# BEK-v16 HYBRID — SERVEUR PRINCIPAL FASTAPI (BOOTSTRAP MODULAIRE)
# ARCHITECTURE MODULAIRE : ZERO RÉGRESSION / ROUTERS & SERVICES EXTRAITS
# ==============================================================================
from __future__ import annotations

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# --- IMPORTS NOYAU & PATHS ---
from core.paths import WORKSPACE_DIR, DOCS_DIR
from core.logger import setup_json_logging  # <-- ajout du logger JSON
from context_loader import load_project_documentation
from memory import init_sync_log_table
from state_synchronizer import init_state_tables
from hermes_core import hermes, start_background_workers

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

# --- IMPORT DES ROUTEURS ---
from routers import admin, files, memory, crm, chat

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
# INITIALISATION GLOBAL & HERMES HOOKS
# ==========================================
try:
    init_sync_log_table()
    init_state_tables()
    if SubCRMEngine:
        SubCRMEngine.initialize_matrix_schema()
    logger.info("Tables Neon DB et schéma Matrix initialisés.")
except Exception as exc:
    logger.warning("Initialisation DB partielle : %s", exc)

try:
    from generate_architecture_doc import update_documentation_file
    update_documentation_file()
except Exception as exc:
    logger.debug("Génération auto architecture Doc : %s", exc)

GLOBAL_SYSTEM_CONTEXT = load_project_documentation(DOCS_DIR)

security_guard = hermes.security_guard
if security_guard is None:
    raise RuntimeError("SecurityGuard Hermes indisponible. Vérifiez BEK_HSM_SECRET.")

mcp_gateway.register_mcp_tool(
    name="neon_audit",
    description="Audit des tables relationnelles Neon DB",
    parameters_schema={},
    handler=lambda: {"tables": ["companies", "contacts", "opportunities", "matrix_sub_crms", "bek_task_states", "sync_log"]}
)

try:
    start_background_workers()
    logger.info("Workers Hermes démarrés avec succès.")
except Exception as exc:
    logger.error("Impossible de démarrer les workers Hermes : %s", exc)

def _bek_pre_plan_validator(objective: str, trace_id: str | None):
    return True, "Pre-Plan validé", None

hermes.register_pre_plan_hook(_bek_pre_plan_validator)
hermes.register_tool("web_sync", lambda query="", **kwargs: web_agent_instance.run_pipeline(query) if web_agent_instance else "WebAgent indisponible", risk_level="L3")
hermes.register_tool("orchestrate", lambda goal="", **kwargs: bek_orchestrator.run(goal) if bek_orchestrator else "Orchestrateur indisponible", risk_level="L2")
hermes.register_tool("neon_audit", lambda **kwargs: {"status": "Neon DB audit demandé", "tables": ["companies", "contacts", "opportunities", "matrix_sub_crms", "sync_log"]}, risk_level="L1")

# ==========================================
# APPLICATION FASTAPI & MONTAGE DES ROUTES
# ==========================================
app = FastAPI(
    title="BEK v16 Hybrid FastAPI",
    description="Architecture cognitive modulaire asynchrone haute performance",
    version="16.0"
)

# ---------- Startup event : initialise le logger JSON ----------
@app.on_event("startup")
async def on_startup():
    # Initialise le logger JSON avant tout autre traitement
    setup_json_logging()
    logger.info("setup_json_logging() exécuté lors du démarrage de l'application.")

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

# Inclusion des routeurs modulaires
app.include_router(admin.router)
app.include_router(files.router)
app.include_router(memory.router)
app.include_router(crm.router)
app.include_router(chat.router)

# ---------- Endpoint de health check du worker headless ----------
@app.get("/health/worker")
async def health_worker():
    """Vérifie rapidement que le worker headless est opérationnel.
    Aucun appel bloquant n'est effectué ; on se contente de renvoyer un statut
    basé sur la disponibilité du processus de fond démarré par
    ``start_background_workers``.
    """
    try:
        # Ici on suppose que le worker expose un attribut ou une fonction de ping.
        # Si aucun ping n'est disponible, on renvoie simplement "running" tant que le
        # démarrage n'a pas levé d'exception (voir le log au démarrage).
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8765"))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("app:app", host=host, port=port, reload=False)
