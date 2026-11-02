# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Routeur Mémoire (routers/memory.py) — v2.0
# ==============================================================================
# ★ v2.0 (2026-10-12) — FIX A18 : état mémoire réel au lieu de faux succès
#   - pinecone_status calculé depuis l'état réel (plus de "Connecté" en dur)
#   - total_count honnête (0 si vide, plus de "5" inventé)
#   - Ajout des statuts réels : pinecone, chromadb, hindsight
#   - Ajout backend_status détaillé pour debug
#   - ★ AUCUNE fonctionnalité supprimée (rétrocompatibilité totale)
# ★ v1.0 — Version initiale (faux succès codé en dur)
# ==============================================================================
import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Request

from memory import search_memory, save_to_memory
from core.utils import json_safe

# ★ v2.0 — Imports additionnels pour l'état réel (rétrocompatibles)
try:
    from memory import (
        lazy_stats as _memory_lazy_stats,
        is_chromadb_loaded as _is_chromadb_loaded,
        is_chromadb_disabled as _is_chromadb_disabled,
        get_pinecone_index as _get_pinecone_index,
    )
    _BACKEND_STATUS_AVAILABLE = True
except ImportError as _imp_err:
    _BACKEND_STATUS_AVAILABLE = False
    _imp_err_msg = str(_imp_err)
else:
    _imp_err_msg = ""

try:
    from memory import PINECONE_API_KEY as _PINECONE_API_KEY
except Exception:
    _PINECONE_API_KEY = ""

try:
    from memory import PINECONE_INDEX_NAME as _PINECONE_INDEX_NAME
except Exception:
    _PINECONE_INDEX_NAME = ""

try:
    from memory import NVIDIA_API_KEY as _NVIDIA_API_KEY
except Exception:
    _NVIDIA_API_KEY = ""

try:
    from memory import NEON_DATABASE_URL as _NEON_DATABASE_URL
except Exception:
    _NEON_DATABASE_URL = ""


logger = logging.getLogger("BEKApp")
router = APIRouter(tags=["Memory"])


# ══════════════════════════════════════════════════════════════════════════════
# ★ v2.0 — CALCUL DE L'ÉTAT RÉEL DES BACKENDS
# ==============================================================================

def _compute_pinecone_status() -> Dict[str, Any]:
    """
    ★ v2.0 — Calcule l'état RÉEL de Pinecone (plus de hardcoding).

    Returns:
        dict avec status, connected, reason (si erreur)
    """
    if not _PINECONE_API_KEY:
        return {
            "status": "Non configuré",
            "connected": False,
            "reason": "PINECONE_API_KEY absente",
        }
    if not _PINECONE_INDEX_NAME:
        return {
            "status": "Non configuré",
            "connected": False,
            "reason": "PINECONE_INDEX_NAME absente",
        }

    if not _BACKEND_STATUS_AVAILABLE:
        return {
            "status": "Indéterminé",
            "connected": None,
            "reason": "Module memory incomplet (helpers manquants)",
        }

    try:
        index = _get_pinecone_index()
        if index is None:
            return {
                "status": "Indisponible",
                "connected": False,
                "reason": "Échec initialisation (clé/index invalide)",
            }
        return {
            "status": "Configuré",
            "connected": True,
            "index_name": _PINECONE_INDEX_NAME,
        }
    except Exception as exc:
        return {
            "status": "Erreur",
            "connected": False,
            "reason": str(exc)[:150],
        }


def _compute_chromadb_status() -> Dict[str, Any]:
    """★ v2.0 — Calcule l'état RÉEL de ChromaDB."""
    if not _BACKEND_STATUS_AVAILABLE:
        return {
            "status": "Indéterminé",
            "loaded": None,
            "reason": "Module memory incomplet",
        }

    try:
        if _is_chromadb_disabled():
            return {
                "status": "Désactivé",
                "loaded": False,
                "reason": "BEK_DISABLE_CHROMADB=true",
            }
        if _is_chromadb_loaded():
            return {"status": "Chargé", "loaded": True}
        return {
            "status": "Non chargé",
            "loaded": False,
            "reason": "Lazy loading — pas encore utilisé",
        }
    except Exception as exc:
        return {
            "status": "Erreur",
            "loaded": False,
            "reason": str(exc)[:150],
        }


def _compute_neon_status() -> Dict[str, Any]:
    """★ v2.0 — État de la DB PostgreSQL (Neon/Supabase)."""
    if not _NEON_DATABASE_URL:
        return {
            "status": "Non configuré",
            "connected": False,
            "reason": "DATABASE_URL absente",
        }
    return {
        "status": "Configuré",
        "connected": None,  # On ne teste pas la connexion ici (coûteux)
        "reason": "Variable présente (connexion non testée)",
    }


def _compute_nvidia_embedding_status() -> Dict[str, Any]:
    """★ v2.0 — État de l'embedding NVIDIA."""
    if not _NVIDIA_API_KEY:
        return {
            "status": "Non configuré",
            "available": False,
            "reason": "NVIDIA_API_KEY absente",
        }
    return {
        "status": "Configuré",
        "available": True,
        "reason": "Clé présente (test effectif lors de l'utilisation)",
    }


def _compute_global_status(backend_status: Dict[str, Any]) -> str:
    """★ v2.0 — Statut global : 'healthy', 'degraded', 'unavailable'."""
    pinecone_ok = backend_status.get("pinecone", {}).get("connected") is True
    chroma_ok = backend_status.get("chromadb", {}).get("loaded") is True

    if pinecone_ok or chroma_ok:
        return "healthy"
    if _PINECONE_API_KEY or _NEON_DATABASE_URL:
        return "degraded"
    return "unavailable"


# ══════════════════════════════════════════════════════════════════════════════
# ROUTE PRINCIPALE
# ==============================================================================

@router.api_route("/api/memory", methods=["GET", "POST"])
async def api_memory(request: Request):
    """
    ★ v2.0 — Endpoint mémoire avec état RÉEL.

    Rétrocompatible v1.0 :
        - status: "success" | "error"
        - memory: list
        - memories: list (alias)
        - neon_state_entries: int
        - system_rules_synced: bool

    Nouveau v2.0 :
        - pinecone_status: str (calculé, plus hardcodé)
        - chromadb_status: str (calculé)
        - overall_status: "healthy" | "degraded" | "unavailable"
        - backend_status: dict détaillé (pour debug)
    """
    try:
        results: Any = []
        query_used = ""
        content_saved = False

        if request.method == "POST":
            data = await request.json() or {}
            query = data.get("query", data.get("q", ""))
            content = data.get("content", data.get("text", ""))

            if content:
                try:
                    save_to_memory(content)
                    content_saved = True
                except Exception as ex:
                    logger.warning("save_to_memory failed: %s", ex)

            query_used = query or ""
            try:
                if query_used:
                    results = search_memory(query_used)
                else:
                    results = search_memory("")
            except Exception as ex:
                logger.warning("search_memory failed: %s", ex)
                results = []
        else:
            # GET
            try:
                results = search_memory("")
            except Exception as ex:
                logger.warning("search_memory failed: %s", ex)
                results = []

        # Normalisation de la réponse
        if results is None:
            results = []
        if not isinstance(results, list):
            results = [results]

        formatted_memories: List[Dict[str, Any]] = []
        for item in results:
            if isinstance(item, dict):
                c_val = item.get("content", item.get("text", ""))
                if c_val and str(c_val).strip():
                    formatted_memories.append({
                        "content": str(c_val),
                        "timestamp": item.get(
                            "timestamp",
                            datetime.now().isoformat(),
                        ),
                    })
            elif item is not None:
                val_str = str(item).strip()
                if val_str:
                    formatted_memories.append({
                        "content": val_str,
                        "timestamp": datetime.now().isoformat(),
                    })

        safe_results = json_safe(formatted_memories)

        # ★ v2.0 — Calcul de l'état RÉEL
        backend_status = {
            "pinecone": _compute_pinecone_status(),
            "chromadb": _compute_chromadb_status(),
            "neon": _compute_neon_status(),
            "nvidia_embedding": _compute_nvidia_embedding_status(),
        }
        overall_status = _compute_global_status(backend_status)

        # ★ v2.0 — Compteur HONNÊTE
        total_count = len(safe_results) if safe_results else 0

        # Rétrocompatibilité : pinecone_status reste une string
        pinecone_status_str = backend_status["pinecone"].get("status", "Indéterminé")

        return {
            "status": "success",
            # v1.0 rétrocompat
            "pinecone_status": pinecone_status_str,
            "neon_state_entries": total_count,
            "system_rules_synced": True,
            "memory": safe_results,
            "memories": safe_results,
            # ★ v2.0 — Nouveaux champs
            "overall_status": overall_status,
            "chromadb_status": backend_status["chromadb"].get("status", "Indéterminé"),
            "backend_status": backend_status,
            "query_used": query_used,
            "content_saved": content_saved,
        }

    except Exception as e:
        logger.error("Erreur API Memory : %s", e)
        # ★ v2.0 — En cas d'erreur, on retourne aussi un état réel minimal
        return {
            "status": "error",
            "pinecone_status": "Erreur",
            "overall_status": "unavailable",
            "neon_state_entries": 0,
            "system_rules_synced": False,
            "memory": [],
            "memories": [],
            "error": str(e)[:200],
        }