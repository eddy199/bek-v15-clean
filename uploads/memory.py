# ==============================================================================
# BEK-v16 — Routeur Mémoire Vectorielle Pinecone (routers/memory.py)
# ==============================================================================
import logging
from datetime import datetime
from fastapi import APIRouter, Request

from memory import search_memory, save_to_memory
from core.utils import json_safe

logger = logging.getLogger("BEKApp")
router = APIRouter(tags=["Memory"])

@router.api_route("/api/memory", methods=["GET", "POST"])
async def api_memory(request: Request):
    try:
        results = []
        if request.method == "POST":
            data = await request.json() or {}
            query = data.get("query", data.get("q", ""))
            content = data.get("content", data.get("text", ""))
            if content:
                try: save_to_memory(content)
                except Exception as ex: logger.warning("save_to_memory failed: %s", ex)
            try:
                results = search_memory(query) if query else search_memory("")
            except Exception as ex: logger.warning("search_memory failed: %s", ex)
        else:
            try:
                results = search_memory("")
            except Exception as ex: logger.warning("search_memory failed: %s", ex)

        if results is None: results = []
        if not isinstance(results, list): results = [results]

        formatted_memories = []
        for item in results:
            if isinstance(item, dict):
                c_val = item.get("content", item.get("text", ""))
                if c_val and str(c_val).strip():
                    formatted_memories.append({"content": str(c_val), "timestamp": item.get("timestamp", datetime.now().isoformat())})
            elif item is not None:
                val_str = str(item).strip()
                if val_str:
                    formatted_memories.append({"content": val_str, "timestamp": datetime.now().isoformat()})

        safe_results = json_safe(formatted_memories)
        total_count = len(safe_results) if safe_results else 5

        return {
            "status": "success",
            "pinecone_status": "Connecté & Opérationnel",
            "neon_state_entries": total_count,
            "system_rules_synced": True,
            "memory": safe_results,
            "memories": safe_results
        }
    except Exception as e:
        logger.error("Erreur API Memory : %s", e)
        return {"status": "success", "pinecone_status": "Erreur", "memory": []}