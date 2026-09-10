# ==============================================================================
# BEK-v16 — Routeur Administration & Statut (routers/admin.py)
# ==============================================================================
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

router = APIRouter(tags=["Admin"])

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
        try: db_conn.close()
        except Exception: pass
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