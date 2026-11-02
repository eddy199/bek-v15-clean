# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — FEEDBACK MEMORY (v1.5)
# ------------------------------------------------------------------------------
# Système d'apprentissage par feedback utilisateur.
# Stocke les corrections dans Hindsight comme faits structurés.
# ------------------------------------------------------------------------------
# v1.1 : Ajout submit_feedback_async() pour FastAPI
# v1.2 : FIX async — thread
# v1.3 : FIX async — pending + retry au boot
# v1.4 : FIX async — subprocess isolé
# v1.5 : FIX pickling — _worker au niveau module (Windows spawn-safe)
# ==============================================================================

from __future__ import annotations

# Charger env.txt en premier
try:
    from env_loader import load_env
    load_env()
except Exception:
    pass

import asyncio
import concurrent.futures
import json
import logging
import os
import queue as _queue
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.feedback")

WORKSPACE_DIR = Path(__file__).resolve().parent
FEEDBACK_LOG = WORKSPACE_DIR / "data" / "feedback_log.jsonl"
PENDING_FILE = WORKSPACE_DIR / "data" / "pending_feedback.jsonl"


# ══════════════════════════════════════════════════════════════════════════════
# WORKER AU NIVEAU MODULE (picklable sur Windows spawn)
# ══════════════════════════════════════════════════════════════════════════════

def _hindsight_worker(q, content: str, context: str) -> None:
    """
    Fonction cible du subprocess. DOIT être au niveau module
    pour être picklable sur Windows (multiprocessing spawn).
    """
    try:
        from hindsight_memory import hindsight_retain
        result = hindsight_retain(content=content, context=context)
        q.put(bool(result))
    except Exception:
        q.put(False)


def _retain_in_subprocess(content: str, context: str) -> bool:
    """
    Lance hindsight_retain() dans un subprocess isolé.
    Contourne le bug 'Timeout context manager should be used inside a task'.
    """
    import multiprocessing as mp

    try:
        ctx = mp.get_context("spawn")
    except Exception:
        ctx = mp

    q = ctx.Queue()
    p = ctx.Process(target=_hindsight_worker, args=(q, content, context))
    p.start()
    p.join(timeout=20)

    if p.is_alive():
        p.terminate()
        p.join(timeout=3)
        return False

    try:
        return bool(q.get_nowait())
    except _queue.Empty:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# VERSION SYNC
# ══════════════════════════════════════════════════════════════════════════════

def submit_feedback(
    user_query: str,
    agent_response: str,
    correction: str,
    feedback_type: str = "correction",
    rating: Optional[int] = None,
) -> Dict[str, Any]:
    """Enregistre un feedback utilisateur (VERSION SYNC)."""
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

    # 1. Journal local
    try:
        FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("[Feedback] Échec écriture locale : %s", exc)

    # 2. Hindsight via subprocess
    content = (
        f"CORRECTION UTILISATEUR : "
        f"Quand on demande '{user_query}', "
        f"la réponse correcte est : '{correction}'. "
        f"(Ancienne réponse incorrecte : '{agent_response[:200]}')"
    )

    stored_hindsight = _retain_in_subprocess(content, "feedback_correction")

    logger.info(
        "[Feedback] %s | hindsight=%s | query='%s'",
        feedback_id, stored_hindsight, user_query[:50],
    )

    return {
        "status": "ok",
        "feedback_id": feedback_id,
        "stored_in_hindsight": stored_hindsight,
        "hindsight_error": None,
        "timestamp": timestamp,
    }


# ══════════════════════════════════════════════════════════════════════════════
# VERSION ASYNC (FastAPI)
# ══════════════════════════════════════════════════════════════════════════════

async def submit_feedback_async(
    user_query: str,
    agent_response: str,
    correction: str,
    feedback_type: str = "correction",
    rating: Optional[int] = None,
) -> Dict[str, Any]:
    """VERSION ASYNC POUR FASTAPI."""
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

    # 1. Journal local
    try:
        FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("[Feedback ASYNC] Échec écriture locale : %s", exc)

    # 2. Hindsight via subprocess dans un thread
    content = (
        f"CORRECTION UTILISATEUR : "
        f"Quand on demande '{user_query}', "
        f"la réponse correcte est : '{correction}'. "
        f"(Ancienne réponse incorrecte : '{agent_response[:200]}')"
    )

    stored_hindsight = False
    hindsight_error = None
    try:
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            stored_hindsight = await loop.run_in_executor(
                executor,
                _retain_in_subprocess,
                content,
                "feedback_correction",
            )
    except Exception as exc:
        hindsight_error = str(exc)
        logger.debug("[Feedback ASYNC] Subprocess échec : %s", exc)

    # 3. Fallback pending
    pending_retry = False
    if not stored_hindsight:
        try:
            PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PENDING_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(feedback_entry, ensure_ascii=False) + "\n")
            pending_retry = True
        except Exception as exc:
            logger.warning("[Feedback ASYNC] Échec pending : %s", exc)

    logger.info(
        "[Feedback ASYNC] %s | hindsight=%s | pending=%s | query='%s'",
        feedback_id, stored_hindsight, pending_retry, user_query[:50],
    )

    return {
        "status": "ok",
        "feedback_id": feedback_id,
        "stored_in_hindsight": stored_hindsight,
        "pending_retry": pending_retry,
        "hindsight_error": hindsight_error,
        "timestamp": timestamp,
    }


# ══════════════════════════════════════════════════════════════════════════════
# TRAITEMENT DES PENDING
# ══════════════════════════════════════════════════════════════════════════════

def process_pending_feedbacks() -> int:
    """Traite les feedbacks pending via subprocess isolé."""
    if not PENDING_FILE.exists():
        return 0

    entries: List[Dict[str, Any]] = []
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        logger.warning("[Pending] Échec lecture : %s", exc)
        return 0

    if not entries:
        try:
            PENDING_FILE.unlink()
        except Exception:
            pass
        return 0

    processed = 0
    failed: List[Dict[str, Any]] = []
    for entry in entries:
        try:
            content = (
                f"CORRECTION UTILISATEUR : "
                f"Quand on demande '{entry.get('user_query', '')}', "
                f"la réponse correcte est : '{entry.get('correction', '')}'."
            )
            ok = _retain_in_subprocess(content, "feedback_correction")
            if ok:
                processed += 1
            else:
                failed.append(entry)
        except Exception as exc:
            logger.warning("[Pending] Échec : %s", exc)
            failed.append(entry)

    try:
        if failed:
            with open(PENDING_FILE, "w", encoding="utf-8") as f:
                for entry in failed:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        else:
            PENDING_FILE.unlink()
    except Exception:
        pass

    logger.info("[Pending] %d/%d feedbacks traités", processed, len(entries))
    return processed


def pending_count() -> int:
    """Retourne le nombre de feedbacks pending."""
    if not PENDING_FILE.exists():
        return 0
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# LECTURE / STATS
# ══════════════════════════════════════════════════════════════════════════════

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

    return list(reversed(entries[-limit:]))


def feedback_stats() -> Dict[str, Any]:
    """Statistiques sur les feedbacks."""
    all_fb = list_feedbacks(limit=10000)
    if not all_fb:
        return {"total": 0, "by_type": {}, "avg_rating": None, "pending": pending_count()}

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
        "pending": pending_count(),
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

    print("\n=== TEST Feedback Memory v1.5 ===\n")

    # Test 1 : sync
    res = submit_feedback(
        user_query="Quel est mon langage préféré ?",
        agent_response="JavaScript",
        correction="Python",
        feedback_type="correction",
    )
    print(f"Test 1 (sync) : {res}")

    # Test 2 : async
    async def _test_async():
        res2 = await submit_feedback_async(
            user_query="Quelle est ma couleur préférée ?",
            agent_response="Rouge",
            correction="Bleu",
            feedback_type="correction",
        )
        print(f"Test 2 (async) : {res2}")

    asyncio.run(_test_async())

    # Test 3 : stats
    stats = feedback_stats()
    print(f"\nStats : {stats}")

    # Test 4 : pending
    print(f"\nPending count : {pending_count()}")

    # Test 5 : traiter pending
    processed = process_pending_feedbacks()
    print(f"Processed : {processed}")
    print(f"Pending après traitement : {pending_count()}")

    # Nettoyage
    try:
        from hindsight_memory import hindsight_close
        hindsight_close()
    except Exception:
        pass

    print("\n✅ Tests terminés.\n")