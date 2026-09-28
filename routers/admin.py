# ==============================================================================
# BEK-v16 — Routeur Administration & Statut (routers/admin.py)
# ------------------------------------------------------------------------------
# AJOUT v16 (Chantier 8) :
#   - /health/nerves          → résumé condensé du système nerveux
#   - /health/nerves/detail   → rapport détaillé des 12 nerfs
#
# AJOUT v16.1 (2026-09-20) : Agnes AI + providers dynamiques
#
# AJOUT v16.2 (2026-09-22) — C6.3 : Admin UI Reflex
#   - GET  /api/reflex/pending         → propositions en staging
#   - GET  /api/reflex/inspect/{id}    → détail d'une proposition
#   - POST /api/reflex/approve/{id}    → approuve (status=approved)
#   - POST /api/reflex/reject/{id}     → rejette (status=rejected)
#   - GET  /api/reflex/stats           → stats globales
#   - GET  /api/reflex/history         → historique complet
# ==============================================================================
import logging
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

# ── Health check du système nerveux ──
try:
    from nerves._health import get_nerves_summary, get_all_nerves_status
    _NERVES_HEALTH_OK = True
except Exception as _nerves_health_err:
    logger.debug("nerves._health non chargé : %s", _nerves_health_err)
    _NERVES_HEALTH_OK = False
    get_nerves_summary = None
    get_all_nerves_status = None


router = APIRouter(tags=["Admin"])


# ==============================================================================
# MÉTADONNÉES DES PROVIDERS (nom d'affichage + ordre UI)
# ==============================================================================
PROVIDER_DISPLAY_NAMES = {
    "agnes":         "Agnes AI (Video)",
    "kimi":          "Moonshot Kimi AI",
    "aisa":          "AIsa (Unified)",
    "b_ai":          "B.ai",
    "groq":          "Groq",
    "nvidia":        "NVIDIA NIM",
    "gemini":        "Google Gemini",
    "openrouter":    "OpenRouter",
    "mistral":       "Mistral AI",
    "cohere":        "Cohere",
    "aionlabs":      "Aion Labs",
    "zhipu":         "Zhipu AI",
    "siliconflow":   "SiliconFlow",
    "huggingface":   "Hugging Face",
    "ollama_cloud":  "Ollama Cloud",
    "kilo_anonymous": "Kilo Code (Anonyme)",
    "ovh_anonymous":  "OVHcloud (Anonyme)",
    "llm7_anonymous": "LLM7.io (Anonyme)",
}

PROVIDER_DISPLAY_ORDER = [
    "agnes", "kimi", "aisa", "b_ai", "groq", "nvidia", "gemini",
    "openrouter", "mistral", "cohere", "aionlabs", "zhipu",
    "siliconflow", "huggingface", "ollama_cloud",
    "kilo_anonymous", "ovh_anonymous", "llm7_anonymous",
]


def _build_providers_list():
    """Construit la liste des providers à afficher dans l'UI."""
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

        providers.append({
            "id": pid,
            "name": PROVIDER_DISPLAY_NAMES.get(pid, pid.upper()),
            "configured": configured,
        })
        seen.add(pid)

    for pid in provider_manager.PROVIDER_MODELS.keys():
        if pid in seen:
            continue
        key_name = provider_manager.PROVIDER_KEY_MAP.get(pid)
        configured = True
        if key_name:
            configured = bool(provider_manager.get_api_key(key_name))
        elif "anonymous" not in pid:
            configured = False
        providers.append({
            "id": pid,
            "name": PROVIDER_DISPLAY_NAMES.get(pid, pid.upper()),
            "configured": configured,
        })

    return providers


# ══════════════════════════════════════════════════════════════════
# ENDPOINTS EXISTANTS (préservés à l'identique)
# ══════════════════════════════════════════════════════════════════

@router.get("/api/health")
async def health():
    return {"status": "ok", "service": "BEK-v16 HYBRID FastAPI", "os": CURRENT_OS_NAME}


@router.get("/api/config")
async def get_config():
    providers_list = _build_providers_list()
    return {
        "providers": providers_list,
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
# HEALTH CHECK DU SYSTÈME NERVEUX
# ══════════════════════════════════════════════════════════════════

@router.get("/health/nerves")
async def health_nerves():
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


# ══════════════════════════════════════════════════════════════════
# REFLEX LOOP ADMIN (C6.3 — 2026-09-22)
# ══════════════════════════════════════════════════════════════════
# Toutes les opérations passent par services.forge + services.episode_logger.
# Aucune modification des tables hormis forge_proposals.status.
# ══════════════════════════════════════════════════════════════════

@router.get("/api/reflex/pending")
async def reflex_pending(limit: int = Query(50, ge=1, le=500)):
    """
    Liste les propositions de la Forge en staging.
    Retourne aussi les métadonnées agrégées de la critique source.
    """
    try:
        from services.forge import list_proposals
        props = list_proposals(status="staging", limit=limit)
        # Décoder le contenu JSON pour le rendre exploitable côté UI
        for p in props:
            try:
                raw = p.get("content")
                if isinstance(raw, str):
                    p["content_parsed"] = json_safe(_safe_json_load(raw))
                else:
                    p["content_parsed"] = raw
            except Exception:
                p["content_parsed"] = None
            try:
                raw_extra = p.get("extra")
                if isinstance(raw_extra, str):
                    p["extra_parsed"] = json_safe(_safe_json_load(raw_extra))
                else:
                    p["extra_parsed"] = raw_extra or {}
            except Exception:
                p["extra_parsed"] = {}

        return {
            "status": "success",
            "count": len(props),
            "proposals": props,
        }
    except Exception as exc:
        logger.exception("[reflex/pending] Échec")
        return {"status": "error", "message": str(exc)[:300], "proposals": []}


@router.get("/api/reflex/inspect/{proposal_id}")
async def reflex_inspect(proposal_id: str):
    """Détail complet d'une proposition."""
    try:
        from services.forge import list_proposals
        all_props = list_proposals(limit=500)
        match = next(
            (p for p in all_props if p.get("proposal_id") == proposal_id),
            None,
        )
        if not match:
            raise HTTPException(
                status_code=404,
                detail=f"Proposition introuvable : {proposal_id}",
            )

        try:
            raw = match.get("content")
            match["content_parsed"] = (
                json_safe(_safe_json_load(raw))
                if isinstance(raw, str)
                else raw
            )
        except Exception:
            match["content_parsed"] = None

        return {"status": "success", "proposal": match}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[reflex/inspect] Échec")
        raise HTTPException(status_code=500, detail=str(exc)[:300])


@router.post("/api/reflex/approve/{proposal_id}")
async def reflex_approve(proposal_id: str):
    """
    Approuve une proposition.
    Option A : status='approved' + publish EventBus. Pas d'envoi à approval_manager.
    """
    try:
        return _set_proposal_status(
            proposal_id=proposal_id,
            new_status="approved",
            action_label="approve",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[reflex/approve] Échec")
        raise HTTPException(status_code=500, detail=str(exc)[:300])


@router.post("/api/reflex/reject/{proposal_id}")
async def reflex_reject(proposal_id: str):
    """Rejette une proposition."""
    try:
        return _set_proposal_status(
            proposal_id=proposal_id,
            new_status="rejected",
            action_label="reject",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[reflex/reject] Échec")
        raise HTTPException(status_code=500, detail=str(exc)[:300])


@router.get("/api/reflex/stats")
async def reflex_stats():
    """Statistiques globales sur les propositions."""
    try:
        from services.forge import forge_stats
        stats = forge_stats()
        return {"status": "success", **stats}
    except Exception as exc:
        logger.exception("[reflex/stats] Échec")
        return {
            "status": "error",
            "message": str(exc)[:300],
            "total": 0, "staging": 0, "approved": 0, "rejected": 0, "expired": 0,
        }


@router.get("/api/reflex/history")
async def reflex_history(
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
):
    """Historique des propositions (toutes ou filtrées par status)."""
    try:
        from services.forge import list_proposals
        props = list_proposals(status=status, limit=limit)
        for p in props:
            try:
                raw = p.get("content")
                if isinstance(raw, str):
                    p["content_parsed"] = json_safe(_safe_json_load(raw))
                else:
                    p["content_parsed"] = raw
            except Exception:
                p["content_parsed"] = None
        return {"status": "success", "count": len(props), "proposals": props}
    except Exception as exc:
        logger.exception("[reflex/history] Échec")
        return {"status": "error", "message": str(exc)[:300], "proposals": []}


# ────────────────────────────────────────────────────────────────
# HELPERS INTERNES REFLEX
# ────────────────────────────────────────────────────────────────
def _safe_json_load(raw: str):
    """Parse un JSON stringifié, retourne None en cas d'échec."""
    import json as _json
    try:
        return _json.loads(raw)
    except Exception:
        return None


def _set_proposal_status(
    proposal_id: str,
    new_status: str,
    action_label: str,
):
    """
    Change le status d'une proposition dans forge_proposals.
    Publie un event EventBus (best-effort).
    Ne touche PAS à approval_manager (Option A).
    """
    from services.episode_logger import _get_conn
    from datetime import datetime, timezone

    conn = _get_conn()

    # Vérifier existence + status actuel
    try:
        row = conn.execute(
            "SELECT proposal_id, status FROM forge_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Lecture forge_proposals impossible : {exc}",
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Proposition introuvable : {proposal_id}",
        )

    current_status = row[1]
    if current_status != "staging":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Proposition {proposal_id} déjà traitée "
                f"(status actuel = '{current_status}')."
            ),
        )

    # Mise à jour
    try:
        conn.execute(
            "UPDATE forge_proposals SET status = ? WHERE proposal_id = ?",
            (new_status, proposal_id),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Mise à jour forge_proposals impossible : {exc}",
        )

    # Publication EventBus (best-effort)
    try:
        from services.forge import _publish_event
        _publish_event(
            action=f"forge_proposal_{action_label}",
            extra={
                "proposal_id": proposal_id,
                "new_status": new_status,
                "decided_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as exc:
        logger.debug("[reflex/%s] EventBus indisponible : %s", action_label, exc)

    logger.info(
        "🔥 [Admin/Reflex] Proposition %s → %s (action=%s)",
        proposal_id, new_status, action_label,
    )

    return {
        "status": "success",
        "proposal_id": proposal_id,
        "new_status": new_status,
        "action": action_label,
    }
@router.post("/api/reflex/run-cycle")
async def reflex_run_cycle(
    hours: int = Query(24, ge=1, le=168),
    with_critic: bool = Query(False),
    with_forge: bool = Query(True),
    forge_dry_run: bool = Query(True),
):
    """
    Déclenche manuellement un cycle Reflex-Loop depuis l'UI.
    Retourne le rapport complet.
    """
    try:
        from services.reflex_loop import ReflexLoop
        loop = ReflexLoop()
        report = loop.run_cycle(
            hours=hours,
            with_critic=with_critic,
            with_forge=with_forge,
            forge_dry_run=forge_dry_run,
        )
        return {
            "status": "success",
            "report_id": report.get("report_id"),
            "summary": report.get("summary"),
            "forge": report.get("forge"),
        }
    except Exception as exc:
        logger.exception("[reflex/run-cycle] Échec")
        raise HTTPException(status_code=500, detail=str(exc)[:300])
@router.get("/api/debug/episodes")
async def debug_episodes():
    """Debug : compte les épisodes dans episodic_log."""
    try:
        from services.episode_logger import count_episodes
        return {
            "status": "success",
            "episodes_count": count_episodes(),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)[:300]}