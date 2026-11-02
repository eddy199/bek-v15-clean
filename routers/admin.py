# ==============================================================================
# BEK-v16 — Routeur Administration & Statut (routers/admin.py)
# ★ v18.10.10 : Fix asyncio.to_thread sur reflex_run_cycle (Anti-Freeze)
# ==============================================================================
import logging
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from services.tasks import CURRENT_OS_NAME
from skill_registry import skill_registry
from provider_manager import provider_manager
from state_synchronizer import get_pending_or_running_tasks
from memory import get_db_connection
from sync_manager import push_to_remotes
from core.utils import json_response, json_safe
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

try:
    from nerves._health import get_nerves_summary, get_all_nerves_status
    _NERVES_HEALTH_OK = True
except Exception as _nerves_health_err:
    logger.debug("nerves._health non chargé : %s", _nerves_health_err)
    _NERVES_HEALTH_OK = False
    get_nerves_summary = None
    get_all_nerves_status = None

router = APIRouter(tags=["Admin"])

PROVIDER_DISPLAY_NAMES = {
    "agnes": "Agnes AI (Video)", "kimi": "Moonshot Kimi AI", "aisa": "AIsa (Unified)",
    "b_ai": "B.ai", "groq": "Groq", "nvidia": "NVIDIA NIM", "gemini": "Google Gemini",
    "openrouter": "OpenRouter", "mistral": "Mistral AI", "cohere": "Cohere",
    "aionlabs": "Aion Labs", "zhipu": "Zhipu AI", "siliconflow": "SiliconFlow",
    "huggingface": "Hugging Face", "ollama_cloud": "Ollama Cloud",
    "kilo_anonymous": "Kilo Code (Anonyme)", "ovh_anonymous": "OVHcloud (Anonyme)",
    "llm7_anonymous": "LLM7.io (Anonyme)",
}

PROVIDER_DISPLAY_ORDER = [
    "agnes", "kimi", "aisa", "b_ai", "groq", "nvidia", "gemini",
    "openrouter", "mistral", "cohere", "aionlabs", "zhipu",
    "siliconflow", "huggingface", "ollama_cloud",
    "kilo_anonymous", "ovh_anonymous", "llm7_anonymous",
]

def _build_providers_list():
    providers = []
    seen = set()
    for pid in PROVIDER_DISPLAY_ORDER:
        if pid not in provider_manager.PROVIDER_MODELS and pid != "agnes":
            continue
        key_name = provider_manager.PROVIDER_KEY_MAP.get(pid)
        configured = True
        if key_name:
            configured = bool(provider_manager.get_api_key(key_name))
        elif "anonymous" not in pid:
            configured = False
        providers.append({"id": pid, "name": PROVIDER_DISPLAY_NAMES.get(pid, pid.upper()), "configured": configured})
        seen.add(pid)
    for pid in provider_manager.PROVIDER_MODELS.keys():
        if pid in seen: continue
        key_name = provider_manager.PROVIDER_KEY_MAP.get(pid)
        configured = True
        if key_name: configured = bool(provider_manager.get_api_key(key_name))
        elif "anonymous" not in pid: configured = False
        providers.append({"id": pid, "name": PROVIDER_DISPLAY_NAMES.get(pid, pid.upper()), "configured": configured})
    return providers

@router.get("/api/health")
async def health():
    return {"status": "ok", "service": "BEK-v16 HYBRID FastAPI", "os": CURRENT_OS_NAME}

@router.get("/api/config")
async def get_config():
    return {
        "providers": _build_providers_list(),
        "models": provider_manager.PROVIDER_MODELS,
        "skills": skill_registry.list_all_skills(),
        "skills_count": len(skill_registry.skills),
        "mcp_tools": mcp_gateway.get_mcp_manifests(),
        "pending_tasks": get_pending_or_running_tasks(),
        "radar_status": event_bus.get_radar_status() if event_bus else {"mode": "NORMAL"},
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
        connectors.append({"name": p_id.replace("_", " ").upper(), "type": "Fournisseur LLM", "latency_ms": 80 if has_key else 0, "status": "Actif" if has_key else "Non Configuré"})
    return {"connectors": connectors}

@router.post("/api/reflexion/stream")
async def reflexion_stream(request: Request):
    data = await request.json() or {}
    swarm = ReflexionSwarm(llm_provider="b_ai", llm_model="glm-5.3-flash")
    streamer = MetaCortexSSEStreamer(swarm)
    return StreamingResponse(streamer.stream_reflection(data.get("draft", ""), data.get("query", "")), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.post("/api/sync/push")
async def api_push_remotes(request: Request):
    data = await request.json() or {}
    return json_response(push_to_remotes(data.get("message", "Auto-sync BEK-v16 agent state")))

@router.get("/health/nerves")
async def health_nerves():
    if not _NERVES_HEALTH_OK: return {"status": "unavailable", "reason": "nerves._health non chargé"}
    try: return get_nerves_summary()
    except Exception as exc: return {"status": "error", "message": str(exc)[:300]}

@router.get("/health/nerves/detail")
async def health_nerves_detail():
    if not _NERVES_HEALTH_OK: return {"status": "unavailable", "reason": "nerves._health non chargé"}
    try: return get_all_nerves_status()
    except Exception as exc: return {"status": "error", "message": str(exc)[:300]}

@router.get("/api/reflex/pending")
async def reflex_pending(limit: int = Query(50, ge=1, le=500)):
    try:
        from services.forge import list_proposals
        props = list_proposals(status="staging", limit=limit)
        for p in props:
            p["content_parsed"] = json_safe(_safe_json_load(p.get("content"))) if isinstance(p.get("content"), str) else p.get("content")
            p["extra_parsed"] = json_safe(_safe_json_load(p.get("extra"))) if isinstance(p.get("extra"), str) else (p.get("extra") or {})
        return {"status": "success", "count": len(props), "proposals": props}
    except Exception as exc: return {"status": "error", "message": str(exc)[:300], "proposals": []}

@router.get("/api/reflex/inspect/{proposal_id}")
async def reflex_inspect(proposal_id: str):
    try:
        from services.forge import list_proposals
        match = next((p for p in list_proposals(limit=500) if p.get("proposal_id") == proposal_id), None)
        if not match: raise HTTPException(status_code=404, detail=f"Proposition introuvable : {proposal_id}")
        match["content_parsed"] = json_safe(_safe_json_load(match.get("content"))) if isinstance(match.get("content"), str) else match.get("content")
        return {"status": "success", "proposal": match}
    except HTTPException: raise
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc)[:300])

@router.post("/api/reflex/approve/{proposal_id}")
async def reflex_approve(proposal_id: str):
    try: return _set_proposal_status(proposal_id, "approved", "approve")
    except HTTPException: raise
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc)[:300])

@router.post("/api/reflex/reject/{proposal_id}")
async def reflex_reject(proposal_id: str):
    try: return _set_proposal_status(proposal_id, "rejected", "reject")
    except HTTPException: raise
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc)[:300])

@router.get("/api/reflex/stats")
async def reflex_stats():
    try:
        from services.forge import forge_stats
        return {"status": "success", **forge_stats()}
    except Exception as exc: return {"status": "error", "message": str(exc)[:300], "total": 0, "staging": 0, "approved": 0, "rejected": 0, "expired": 0}

@router.get("/api/reflex/history")
async def reflex_history(limit: int = Query(100, ge=1, le=1000), status: Optional[str] = Query(None)):
    try:
        from services.forge import list_proposals
        props = list_proposals(status=status, limit=limit)
        for p in props: p["content_parsed"] = json_safe(_safe_json_load(p.get("content"))) if isinstance(p.get("content"), str) else p.get("content")
        return {"status": "success", "count": len(props), "proposals": props}
    except Exception as exc: return {"status": "error", "message": str(exc)[:300], "proposals": []}

def _safe_json_load(raw: str):
    import json as _json
    try: return _json.loads(raw)
    except Exception: return None

def _set_proposal_status(proposal_id: str, new_status: str, action_label: str):
    from services.episode_logger import _get_conn
    from datetime import datetime, timezone
    conn = _get_conn()
    try:
        row = conn.execute("SELECT proposal_id, status FROM forge_proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
    except Exception as exc: raise HTTPException(status_code=500, detail=f"Lecture impossible : {exc}")
    if row is None: raise HTTPException(status_code=404, detail=f"Introuvable : {proposal_id}")
    if row[1] != "staging": raise HTTPException(status_code=409, detail=f"Déjà traitée (status = '{row[1]}').")
    try: conn.execute("UPDATE forge_proposals SET status = ? WHERE proposal_id = ?", (new_status, proposal_id))
    except Exception as exc: raise HTTPException(status_code=500, detail=f"Update impossible : {exc}")
    try:
        from services.forge import _publish_event
        _publish_event(action=f"forge_proposal_{action_label}", extra={"proposal_id": proposal_id, "new_status": new_status, "decided_at": datetime.now(timezone.utc).isoformat()})
    except Exception: pass
    return {"status": "success", "proposal_id": proposal_id, "new_status": new_status, "action": action_label}

# ★ FIX : Utilisation de asyncio.to_thread
@router.post("/api/reflex/run-cycle")
async def reflex_run_cycle(
    hours: int = Query(24, ge=1, le=168),
    with_critic: bool = Query(False),
    with_forge: bool = Query(True),
    forge_dry_run: bool = Query(True),
):
    try:
        from services.reflex_loop import ReflexLoop
        loop = ReflexLoop()
        report = await asyncio.to_thread(loop.run_cycle, hours=hours, with_critic=with_critic, with_forge=with_forge, forge_dry_run=forge_dry_run)
        return {"status": "success", "report_id": report.get("report_id"), "summary": report.get("summary"), "forge": report.get("forge")}
    except Exception as exc:
        logger.exception("[reflex/run-cycle] Échec")
        raise HTTPException(status_code=500, detail=str(exc)[:300])

@router.get("/api/debug/episodes")
async def debug_episodes():
    try:
        from services.episode_logger import count_episodes
        return {"status": "success", "episodes_count": count_episodes()}
    except Exception as exc: return {"status": "error", "message": str(exc)[:300]}