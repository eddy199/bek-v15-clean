# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — FEEDBACK MEMORY (v1.0)
# ------------------------------------------------------------------------------
# Système d'apprentissage par feedback utilisateur.
# Stocke les corrections dans Hindsight comme faits structurés.
# ==============================================================================

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.feedback")

WORKSPACE_DIR = Path(__file__).resolve().parent
FEEDBACK_LOG = WORKSPACE_DIR / "data" / "feedback_log.jsonl"


# ══════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE
# ══════════════════════════════════════════════════════════════════════════════

def submit_feedback(
    user_query: str,
    agent_response: str,
    correction: str,
    feedback_type: str = "correction",
    rating: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Enregistre un feedback utilisateur.

    Args:
        user_query: La question posée à l'agent
        agent_response: La réponse incorrecte de l'agent
        correction: La bonne réponse (ou précision)
        feedback_type: "correction" | "rating" | "note"
        rating: 1-5 (optionnel)

    Returns:
        {"status": "ok", "stored_in_hindsight": bool, "feedback_id": str}
    """
    if not user_query or not correction:
        return {"status": "error", "message": "user_query et correction obligatoires"}

    feedback_id = f"fb_{int(time.time())}_{os.urandom(3).hex()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    feedback_entry = {
        "feedback_id": feedback_id,
        "timestamp": timestamp,
        "type": feedback_type,
        "rating": rating,
        "user_query": user_query[:500],
        "agent_response": agent_response[:500] if agent_response else "",
        "correction": correction[:1000],
    }

    # 1. Journal local (JSONL — append-only)
    try:
        FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("[Feedback] Échec écriture locale : %s", exc)

    # 2. Stockage dans Hindsight (async ou sync)
    stored_hindsight = False
    try:
        from hindsight_memory import hindsight_retain

        # Formule un fait structuré pour Hindsight
        content = (
            f"CORRECTION UTILISATEUR : "
            f"Quand on demande '{user_query}', "
            f"la réponse correcte est : '{correction}'. "
            f"(Ancienne réponse incorrecte : '{agent_response[:200]}')"
        )

        stored_hindsight = hindsight_retain(
            content=content,
            context="feedback_correction",
        )
    except Exception as exc:
        logger.warning("[Feedback] Échec Hindsight : %s", exc)

    logger.info(
        "[Feedback] %s | hindsight=%s | query='%s'",
        feedback_id, stored_hindsight, user_query[:50],
    )

    return {
        "status": "ok",
        "feedback_id": feedback_id,
        "stored_in_hindsight": stored_hindsight,
        "timestamp": timestamp,
    }


def list_feedbacks(limit: int = 50) -> List[Dict[str, Any]]:
    """Liste les derniers feedbacks (local)."""
    if not FEEDBACK_LOG.exists():
        return []

    entries: List[Dict[str, Any]] = []
    try:
        with open(FEEDBACK_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        logger.warning("[Feedback] Échec lecture : %s", exc)

    # Derniers en premier
    return list(reversed(entries[-limit:]))


def feedback_stats() -> Dict[str, Any]:
    """Statistiques sur les feedbacks."""
    all_fb = list_feedbacks(limit=10000)
    if not all_fb:
        return {"total": 0, "by_type": {}, "avg_rating": None}

    by_type: Dict[str, int] = {}
    ratings: List[int] = []

    for fb in all_fb:
        t = fb.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
        if isinstance(fb.get("rating"), int):
            ratings.append(fb["rating"])

    return {
        "total": len(all_fb),
        "by_type": by_type,
        "avg_rating": sum(ratings) / len(ratings) if ratings else None,
        "last_feedback": all_fb[0]["timestamp"] if all_fb else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEST AUTONOME
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    print("\n=== TEST Feedback Memory ===\n")

    # Test 1 : correction
    res = submit_feedback(
        user_query="Quel est mon langage préféré ?",
        agent_response="JavaScript",
        correction="Python",
        feedback_type="correction",
    )
    print(f"Test 1 (correction) : {res}")

    # Test 2 : rating
    res2 = submit_feedback(
        user_query="Bonjour",
        agent_response="Bonjour !",
        correction="Excellente réponse",
        feedback_type="rating",
        rating=5,
    )
    print(f"Test 2 (rating) : {res2}")

    # Test 3 : stats
    stats = feedback_stats()
    print(f"\nStats : {stats}")

    # Test 4 : liste
    fb_list = list_feedbacks(limit=5)
    print(f"\nDerniers feedbacks ({len(fb_list)}) :")
    for fb in fb_list:
        print(f"  - [{fb['type']}] {fb['user_query'][:50]}")

    print("\n✅ Tests terminés.\n")