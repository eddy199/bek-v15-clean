# ==============================================================================
# BEK-v16 — Routeur Administration & Statut (routers/admin.py)
# ------------------------------------------------------------------------------
# AJOUT v16 (Chantier 8) :
#   - /health/nerves          → résumé condensé du système nerveux (monitoring)
#   - /health/nerves/detail   → rapport détaillé des 12 nerfs (debug)
#
# TOUS LES ENDPOINTS EXISTANTS SONT PRÉSERVÉS :
#   - /api/health
#   - /api/config
#   - /api/connectors
#   - /api/reflexion/stream
#   - /api/sync/push
# ==============================================================================
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from services.tasks import CURRENT_OS_NAME
from skill_registry import skill_registry
from provider_manager import provider_manager
from state_synchronizer import get_pending_or_running_tasks
from memory import get_db_connection
from sync_manager import push_to_remotes
from core.utils import json_response
from meta_cortex_swarm import ReflexionSwarm
from meta_cortex_sse_ui import MetaCortexSSEStreamer

logger = logging.getLogger("BEKApp")

try:
    from mcp_gateway import mcp_gateway
except ImportError:
    class MCPGatewayMock:
        def register_mcp_tool(self, **kwargs): pass
        def get_mcp_manifests(self): return []
    mcp_gateway = MCPGatewayMock()

try:
    from event_bus import EventBusKafka
    event_bus = EventBusKafka()
except Exception:
    event_bus = None

# ── Health check du système nerveux (Nerf 3 + 12 modules nerves/) ──
try:
    from nerves._health import get_nerves_summary, get_all_nerves_status
    _NERVES_HEALTH_OK = True
except Exception as _nerves_health_err:
    logger.debug("nerves._health non chargé : %s", _nerves_health_err)
    _NERVES_HEALTH_OK = False
    get_nerves_summary = None
    get_all_nerves_status = None


router = APIRouter(tags=["Admin"])


# ══════════════════════════════════════════════════════════════════
# ENDPOINTS EXISTANTS (préservés à l'identique)
# ══════════════════════════════════════════════════════════════════

@router.get("/api/health")
async def health():
    return {"status": "ok", "service": "BEK-v16 HYBRID FastAPI", "os": CURRENT_OS_NAME}


@router.get("/api/config")
async def get_config():
    providers_list = [
        {"id": "b_ai", "name": "B.ai", "configured": True},
        {"id": "kilo_anonymous", "name": "Kilo Code (Anonyme)", "configured": True},
        {"id": "ovh_anonymous", "name": "OVHcloud (Anonyme)", "configured": True},
        {"id": "llm7_anonymous", "name": "LLM7.io (Anonyme)", "configured": True},
        {"id": "groq", "name": "Groq", "configured": True},
        {"id": "nvidia", "name": "NVIDIA NIM", "configured": True},
        {"id": "gemini", "name": "Google Gemini", "configured": True},
        {"id": "openrouter", "name": "OpenRouter", "configured": True},
        {"id": "mistral", "name": "Mistral AI", "configured": True},
        {"id": "cohere", "name": "Cohere", "configured": True},
        {"id": "aionlabs", "name": "Aion Labs", "configured": True},
        {"id": "zhipu", "name": "Zhipu AI", "configured": True},
        {"id": "siliconflow", "name": "SiliconFlow", "configured": True},
    ]
    return {
        "providers": providers_list,
        "models": provider_manager.PROVIDER_MODELS,
        "skills": skill_registry.list_all_skills(),
        "skills_count": len(skill_registry.skills),
        "mcp_tools": mcp_gateway.get_mcp_manifests(),
        "pending_tasks": get_pending_or_running_tasks(),
        "radar_status": event_bus.get_radar_status() if event_bus else {"mode": "NORMAL"}
    }


@router.get("/api/connectors")
async def get_connectors():
    connectors = []
    db_conn = get_db_connection()
    db_status = "Actif" if db_conn else "Erreur de connexion"
    if db_conn:
        try:
            db_conn.close()
        except Exception:
            pass
    connectors.append({"name": "Neon DB (PostgreSQL)", "type": "Database Principale", "latency_ms": 12, "status": db_status})
    connectors.append({"name": "Vision Multimodal Engine", "type": "Analyse d'Images", "latency_ms": 15, "status": "Actif"})
    connectors.append({"name": "ZIP Archive Manager", "type": "Extraction / Compression", "latency_ms": 4, "status": "Actif"})
    connectors.append({"name": "Model Context Protocol (MCP)", "type": "Passerelle Interopérabilité", "latency_ms": 2, "status": "Actif"})
    connectors.append({"name": "EventBus Kafka Mock", "type": "Pipeline Ingestion A2A", "latency_ms": 1, "status": "Actif"})

    for p_id in provider_manager.FALLBACK_ORDER:
        has_key = bool(provider_manager.get_api_key(f"{p_id.upper()}_API_KEY")) or ("anonymous" in p_id)
        connectors.append({
            "name": p_id.replace("_", " ").upper(),
            "type": "Fournisseur LLM",
            "latency_ms": 80 if has_key else 0,
            "status": "Actif" if has_key else "Non Configuré"
        })
    return {"connectors": connectors}


@router.post("/api/reflexion/stream")
async def reflexion_stream(request: Request):
    data = await request.json() or {}
    draft = data.get("draft", "")
    query = data.get("query", "")

    swarm = ReflexionSwarm(llm_provider="b_ai", llm_model="glm-5.3-flash")
    streamer = MetaCortexSSEStreamer(swarm)

    return StreamingResponse(
        streamer.stream_reflection(draft, query),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.post("/api/sync/push")
async def api_push_remotes(request: Request):
    data = await request.json() or {}
    msg = data.get("message", "Auto-sync BEK-v16 agent state")
    res = push_to_remotes(msg)
    return json_response(res)


# ══════════════════════════════════════════════════════════════════
# NOUVEAU (Chantier 8) : Health check du système nerveux
# ══════════════════════════════════════════════════════════════════

@router.get("/health/nerves")
async def health_nerves():
    """
    Résumé condensé du système nerveux (12 nerfs + pont EventBus).

    Format : {status, ok, disabled, error, inactive, unknown,
              event_bus_bridge_active, duration_ms}

    Utilisable par un monitoring externe (Render, UptimeRobot, etc.).
    """
    if not _NERVES_HEALTH_OK:
        return {
            "status": "unavailable",
            "reason": "nerves._health non chargé (paquet nerves/ absent ?)",
        }
    try:
        return get_nerves_summary()
    except Exception as exc:
        logger.error("[health/nerves] Échec : %s", exc)
        return {"status": "error", "message": str(exc)[:300]}


@router.get("/health/nerves/detail")
async def health_nerves_detail():
    """
    Rapport détaillé du système nerveux (12 nerfs + pont EventBus + durées).

    Utilisable pour du debug humain après un redéploiement.
    """
    if not _NERVES_HEALTH_OK:
        return {
            "status": "unavailable",
            "reason": "nerves._health non chargé (paquet nerves/ absent ?)",
        }
    try:
        return get_all_nerves_status()
    except Exception as exc:
        logger.error("[health/nerves/detail] Échec : %s", exc)
        return {"status": "error", "message": str(exc)[:300]}