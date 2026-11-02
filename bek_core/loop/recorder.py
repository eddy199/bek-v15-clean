# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-LOOP Recorder (v2.1 — Atomic SQLite Transactions)
# ------------------------------------------------------------------------------
# v2.1 (2026-10-24) : FIX atomicité de l'INSERT et du DELETE
# ==============================================================================
from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.core.loop")

BEK_LOOP_DEFAULT_HOURS = 24
BEK_LOOP_STORAGE_DB = "data/bek_loop_episodes.db"
BEK_LOOP_MAX_EPISODES = 10000


class BekLoopRecorder:
    def __init__(self, storage_path: Optional[str] = None):
        self.db_path = Path(storage_path or BEK_LOOP_STORAGE_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS episodes (
                        episode_id TEXT PRIMARY KEY,
                        timestamp REAL,
                        query TEXT,
                        tier TEXT,
                        success INTEGER,
                        time_ms REAL,
                        result_summary TEXT,
                        error TEXT,
                        metadata TEXT
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON episodes(timestamp)")
        except Exception as exc:
            logger.error("BekLoop : Erreur d'initialisation de la DB : %s", exc)

    def record(self, episode: Dict[str, Any]) -> str:
        episode_id = f"ep_{uuid.uuid4().hex[:12]}"
        timestamp = time.time()
        
        query = episode.get("query", "")
        tier = episode.get("tier", "TIER_3")
        success = 1 if episode.get("success", False) else 0
        time_ms = float(episode.get("time_ms", 0.0))
        # ★ FIX JSON propre
        try:
            result_summary = json.dumps(episode.get("result", ""), ensure_ascii=False)[:200]
        except Exception:
            result_summary = str(episode.get("result", ""))[:200]
        error = episode.get("error", "")
        metadata = json.dumps(episode.get("metadata", {}))

        # ★ FIX v2.1 : Transaction atomique unifiée
        # On utilise 'with conn:' qui gère le commit/rollback automatiquement.
        try:
            with self._get_conn() as conn:
                # 1. Insertion
                conn.execute("""
                    INSERT INTO episodes 
                    (episode_id, timestamp, query, tier, success, time_ms, result_summary, error, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (episode_id, timestamp, query, tier, success, time_ms, result_summary, error, metadata))
                
                # 2. Nettoyage (dans la même transaction)
                conn.execute("""
                    DELETE FROM episodes 
                    WHERE episode_id IN (
                        SELECT episode_id FROM episodes 
                        ORDER BY timestamp DESC 
                        LIMIT -1 OFFSET ?
                    )
                """, (BEK_LOOP_MAX_EPISODES,))

            logger.debug("BekLoop : épisode %s enregistré | tier=%s | success=%s", episode_id, tier, bool(success))
        except Exception as exc:
            logger.error("BekLoop : Échec de l'enregistrement de l'épisode : %s", exc)

        return episode_id

    def analyze(self, hours: int = BEK_LOOP_DEFAULT_HOURS) -> Dict[str, Any]:
        cutoff = time.time() - (hours * 3600)
        recent = []

        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT * FROM episodes WHERE timestamp >= ?", (cutoff,))
                recent = [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            logger.error("BekLoop : Erreur lors de l'analyse : %s", exc)
            return {"total": 0, "success_rate": 0.0, "avg_time_ms": 0.0, "by_tier": {}, "patterns": [], "errors": []}

        if not recent:
            return {"total": 0, "success_rate": 0.0, "avg_time_ms": 0.0, "by_tier": {}, "patterns": [], "errors": []}

        total = len(recent)
        success_count = sum(1 for e in recent if e.get("success") == 1)
        total_time = sum(e.get("time_ms", 0.0) for e in recent)

        by_tier = defaultdict(lambda: {"count": 0, "success": 0, "time_ms": 0.0})
        for e in recent:
            tier = e.get("tier", "UNKNOWN")
            by_tier[tier]["count"] += 1
            if e.get("success") == 1:
                by_tier[tier]["success"] += 1
            by_tier[tier]["time_ms"] += e.get("time_ms", 0.0)

        by_tier_summary = {
            tier: {
                "count": stats["count"],
                "success_rate": round(stats["success"] / stats["count"], 3) if stats["count"] else 0.0,
                "avg_time_ms": round(stats["time_ms"] / stats["count"], 2) if stats["count"] else 0.0,
            }
            for tier, stats in by_tier.items()
        }

        failures = [e for e in recent if e.get("success") == 0]
        patterns = self._detect_failure_patterns(failures)
        errors = self._collect_errors(failures)

        return {
            "total": total,
            "success_rate": round(success_count / total, 3),
            "avg_time_ms": round(total_time / total, 2),
            "by_tier": by_tier_summary,
            "patterns": patterns,
            "errors": errors,
            "window_hours": hours,
        }

    def _detect_failure_patterns(self, failures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_tier = defaultdict(int)
        for e in failures:
            by_tier[e.get("tier", "UNKNOWN")] += 1

        patterns = []
        for tier, count in by_tier.items():
            if count >= 3:
                patterns.append({
                    "type": "repeated_failure",
                    "tier": tier,
                    "count": count,
                    "suggestion": f"Reconsidérer le routing vers {tier}",
                })
        return patterns

    def _collect_errors(self, failures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        error_count = defaultdict(int)
        for e in failures:
            err = e.get("error")
            if err:
                error_count[err[:100]] += 1

        return [
            {"error": err, "count": count}
            for err, count in sorted(error_count.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

    def count(self) -> int:
        try:
            with self._get_conn() as conn:
                return conn.execute("SELECT count(*) FROM episodes").fetchone()[0]
        except Exception:
            return 0

    def clear(self) -> int:
        try:
            with self._get_conn() as conn:
                count = conn.execute("SELECT count(*) FROM episodes").fetchone()[0]
                conn.execute("DELETE FROM episodes")
                return count
        except Exception:
            return 0


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ══════════════════════════════════════════════════════════════════════════════

def bek_loop_record(episode: Dict[str, Any]) -> str:
    recorder = BekLoopRecorder()
    return recorder.record(episode)

def bek_loop_analyze(hours: int = BEK_LOOP_DEFAULT_HOURS) -> Dict[str, Any]:
    recorder = BekLoopRecorder()
    return recorder.analyze(hours=hours)

def bek_loop_count() -> int:
    recorder = BekLoopRecorder()
    return recorder.count()