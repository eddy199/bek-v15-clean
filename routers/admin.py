# ==============================================================================
# BEK-v16 — Routeur Administration & Statut (routers/admin.py)
# ------------------------------------------------------------------------------
# AJOUT v16 (Chantier 8) :
#   - /health/nerves          → résumé condensé du système nerveux (monitoring)
#   - /health/nerves/detail   → rapport détaillé des 12 nerfs (debug)
#
# AJOUT v16.1 (2026-09-20) :
#   - Agnes AI ajouté à /api/config (vidéo gratuite, provider indépendant)
#   - Liste providers désormais DYNAMIQUE depuis provider_manager.PROVIDER_MODELS
#   - Le nom court UI reste accessible pour chaque provider
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


# ==============================================================================
# MÉTADONNÉES DES PROVIDERS (nom d'affichage + icône + ordre UI)
# ------------------------------------------------------------------------------
# Cette table associe chaque identifiant provider interne à son nom UI.
# v16.1 : Agnes AI ajouté en tête de liste (vidéo gratuite).
# ==============================================================================
PROVIDER_DISPLAY_NAMES = {
    # ── Vidéo ──
    "agnes":         "Agnes AI (Video)",
    # ── Chat / texte ──
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
    # ── Anonymes ──
    "kilo_anonymous": "Kilo Code (Anonyme)",
    "ovh_anonymous":  "OVHcloud (Anonyme)",
    "llm7_anonymous": "LLM7.io (Anonyme)",
}

# Ordre d'affichage dans le sélecteur UI (Agnes en premier)
PROVIDER_DISPLAY_ORDER = [
    "agnes",
    "kimi",
    "aisa",
    "b_ai",
    "groq",
    "nvidia",
    "gemini",
    "openrouter",
    "mistral",
    "cohere",
    "aionlabs",
    "zhipu",
    "siliconflow",
    "huggingface",
    "ollama_cloud",
    "kilo_anonymous",
    "ovh_anonymous",
    "llm7_anonymous",
]


def _build_providers_list():
    """
    Construit la liste des providers à afficher dans l'UI.

    - Utilise PROVIDER_DISPLAY_ORDER pour l'ordre.
    - Détecte automatiquement si la clé API est configurée.
    - Inclut les providers anonymes qui n'ont pas besoin de clé.
    - Ajoute tout provider présent dans PROVIDER_MODELS mais pas dans
      PROVIDER_DISPLAY_ORDER (fallback automatique).
    """
    providers = []
    seen = set()

    for pid in PROVIDER_DISPLAY_ORDER:
        # Le provider existe-t-il dans le provider_manager ?
        if pid not in provider_manager.PROVIDER_MODELS and pid != "agnes":
            continue

        # Vérifier si la clé API est présente
        key_name = provider_manager.PROVIDER_KEY_MAP.get(pid)
        configured = True
        if key_name:
            configured = bool(provider_manager.get_api_key(key_name))
        elif "anonymous" not in pid:
            configured = False  # Provider non-anonyme sans clé déclarée

        providers.append({
            "id": pid,
            "name": PROVIDER_DISPLAY_NAMES.get(pid, pid.upper()),
            "configured": configured,
        })
        seen.add(pid)

    # Fallback : ajouter les providers présents dans PROVIDER_MODELS
    # mais non listés dans PROVIDER_DISPLAY_ORDER
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
    """
    Configuration de l'UI BEK.

    v16.1 : La liste des providers est construite dynamiquement depuis
    provider_manager. Agnes AI y figure en premier (vidéo gratuite).
    """
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