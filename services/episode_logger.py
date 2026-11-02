# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Episode Logger (DuckDB local OU SQLite fallback) — v39
# ------------------------------------------------------------------------------
# ★ v39 (2026-10-21) — FIX DUCKDB LOCK :
#   - Connexion UNIQUE partagée (singleton), plus de cache thread-local
#   - Toujours read_only=False (DuckDB interdit la mixité)
#   - Lectures via .cursor() (threadsafe)
#   - close_all() libère le lock au shutdown
# ★ v38 (2026-10-06) — LAZY LOADING DuckDB
# ★ v37 (2026-09-28) — FALLBACK SQLITE
# ==============================================================================
from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.episode_logger")


# ==============================================================================
# DÉTECTION LAZY DU BACKEND
# ==============================================================================
_BACKEND: Optional[str] = None
_duckdb_module = None
_BACKEND_LOCK = threading.Lock()


def _detect_backend() -> str:
    global _duckdb_module, _BACKEND
    if _BACKEND is not None:
        return _BACKEND

    with _BACKEND_LOCK:
        if _BACKEND is not None:
            return _BACKEND

        force_sqlite = os.getenv(
            "BEK_FORCE_SQLITE_EPISODE_LOG", ""
        ).strip().lower() in ("1", "true", "yes", "on")

        if force_sqlite:
            _BACKEND = "sqlite"
            logger.info("[episode_logger] Backend forcé : sqlite")
            return _BACKEND

        logger.info("[episode_logger] Chargement DuckDB (lazy)...")
        try:
            import duckdb as _duckdb
            _duckdb_module = _duckdb
            _BACKEND = "duckdb"
            logger.info("[episode_logger] ✅ Backend : duckdb")
        except ImportError as exc:
            _duckdb_module = None
            _BACKEND = "sqlite"
            logger.info("[episode_logger] DuckDB indisponible (%s) → sqlite", exc)

        return _BACKEND


def backend_name() -> str:
    return _detect_backend()


def lazy_stats() -> dict:
    return {
        "backend": _BACKEND or "not_detected",
        "duckdb_loaded": _duckdb_module is not None,
        "lazy": _BACKEND is None,
    }


# ==============================================================================
# CONFIGURATION
# ==============================================================================
DEFAULT_DB_PATH_DUCKDB = "./data/analytics.duckdb"
DEFAULT_DB_PATH_SQLITE = "./data/analytics.sqlite"
_DB_PATH: Optional[str] = None


def _default_path() -> str:
    backend = _detect_backend()
    return DEFAULT_DB_PATH_DUCKDB if backend == "duckdb" else DEFAULT_DB_PATH_SQLITE


def configure(db_path: str) -> None:
    global _DB_PATH
    backend = _detect_backend()
    p = Path(db_path)
    if backend == "sqlite" and p.suffix.lower() not in (".sqlite", ".db"):
        p = p.with_suffix(".sqlite")
    elif backend == "duckdb" and p.suffix.lower() not in (".duckdb", ".db"):
        p = p.with_suffix(".duckdb")
    _DB_PATH = str(p)
    logger.info("EpisodeLogger configuré | backend=%s | path=%s", backend, _DB_PATH)


def _get_db_path() -> str:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = _default_path()
    return _DB_PATH


# ==============================================================================
# ★ v39 — CONNEXION UNIQUE PARTAGÉE
# ==============================================================================
_WRITE_LOCK = threading.RLock()
_SHARED_CONN: Optional[Any] = None
_SHARED_CONN_BACKEND: Optional[str] = None
_SHARED_CONN_LOCK = threading.RLock()


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA
# ══════════════════════════════════════════════════════════════════════════════
_SCHEMA_DUCKDB = """
    CREATE TABLE IF NOT EXISTS episodic_log (
        episode_id      VARCHAR PRIMARY KEY,
        trace_id        VARCHAR,
        task_id         VARCHAR,
        correlation_id  VARCHAR,
        action          VARCHAR NOT NULL,
        parameters      VARCHAR,
        status          VARCHAR NOT NULL,
        message         VARCHAR,
        error_type      VARCHAR,
        latency_ms      DOUBLE,
        ts_utc          TIMESTAMP,
        source          VARCHAR,
        context_hash    VARCHAR,
        extra           VARCHAR
    );
"""

_SCHEMA_SQLITE = """
    CREATE TABLE IF NOT EXISTS episodic_log (
        episode_id      TEXT PRIMARY KEY,
        trace_id        TEXT,
        task_id         TEXT,
        correlation_id  TEXT,
        action          TEXT NOT NULL,
        parameters      TEXT,
        status          TEXT NOT NULL,
        message         TEXT,
        error_type      TEXT,
        latency_ms      REAL,
        ts_utc          TEXT,
        source          TEXT,
        context_hash    TEXT,
        extra           TEXT
    );
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_episodic_action_ts ON episodic_log(action, ts_utc);",
    "CREATE INDEX IF NOT EXISTS idx_episodic_status ON episodic_log(status);",
)


def _ensure_schema(conn: Any, backend: str) -> None:
    schema = _SCHEMA_DUCKDB if backend == "duckdb" else _SCHEMA_SQLITE
    conn.execute(schema)
    for idx in _INDEXES:
        try:
            conn.execute(idx)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# ★ v39 — CONNEXION UNIQUE
# ══════════════════════════════════════════════════════════════════════════════
def _get_conn(read_only: bool = False) -> Any:
    """
    ★ v39 — Retourne LA connexion unique partagée.
    `read_only` conservé pour compat mais ignoré (DuckDB: toujours False).
    Pour lectures isolées : utiliser .cursor() sur la connexion retournée.
    """
    global _SHARED_CONN, _SHARED_CONN_BACKEND

    backend = _detect_backend()

    with _SHARED_CONN_LOCK:
        if _SHARED_CONN is not None and _SHARED_CONN_BACKEND == backend:
            return _SHARED_CONN

        if _SHARED_CONN is not None:
            try:
                _SHARED_CONN.close()
            except Exception:
                pass
            _SHARED_CONN = None

        path = _get_db_path()
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        if backend == "duckdb":
            # ★ Toujours read_only=False
            _SHARED_CONN = _duckdb_module.connect(path)
            _ensure_schema(_SHARED_CONN, backend)
        else:
            _SHARED_CONN = sqlite3.connect(
                path, timeout=10.0, check_same_thread=False
            )
            _SHARED_CONN.row_factory = sqlite3.Row
            _ensure_schema(_SHARED_CONN, backend)
            _SHARED_CONN.commit()

        _SHARED_CONN_BACKEND = backend
        logger.info(
            "EpisodeLogger : connexion partagée ouverte | backend=%s | path=%s",
            backend, path,
        )
        return _SHARED_CONN


# ══════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE — LOG
# ══════════════════════════════════════════════════════════════════════════════
def log_episode(
    action: str,
    parameters: Dict[str, Any],
    status: str,
    message: str = "",
    error_type: Optional[str] = None,
    latency_ms: float = 0.0,
    trace_id: Optional[str] = None,
    task_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    source: str = "action_executor",
    context_hash: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    episode_id = f"ep_{uuid.uuid4().hex[:16]}"

    try:
        params_json = json.dumps(parameters, default=str, ensure_ascii=False)
    except Exception:
        params_json = json.dumps({"_unserializable": True})

    try:
        extra_json = json.dumps(extra or {}, default=str, ensure_ascii=False)
    except Exception:
        extra_json = "{}"

    if message and len(message) > 2000:
        message = message[:2000] + "…"

    backend = _detect_backend()
    now_utc = datetime.now(timezone.utc)

    if backend == "duckdb":
        ts_value = now_utc
    else:
        ts_value = now_utc.isoformat()

    try:
        conn = _get_conn()
        with _WRITE_LOCK:
            sql = """
                INSERT INTO episodic_log (
                    episode_id, trace_id, task_id, correlation_id,
                    action, parameters, status, message, error_type,
                    latency_ms, ts_utc, source, context_hash, extra
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            conn.execute(sql, (
                episode_id, trace_id, task_id, correlation_id,
                action, params_json, status, message, error_type,
                float(latency_ms or 0.0), ts_value, source, context_hash, extra_json,
            ))
            if backend == "sqlite":
                conn.commit()
    except Exception:
        logger.exception("EpisodeLogger : échec d'insertion | action=%s", action)
        return ""

    return episode_id


# ══════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE — LECTURE
# ══════════════════════════════════════════════════════════════════════════════
def fetch_recent_episodes(
    hours: int = 24,
    action_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 500,
) -> List[dict]:
    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=int(hours))
    backend = _detect_backend()

    try:
        conn = _get_conn()
    except Exception as e:
        logger.error("EpisodeLogger : connexion impossible : %s", e)
        return []

    if backend == "duckdb":
        query = "SELECT * FROM episodic_log WHERE ts_utc >= ?"
        params: list = [cutoff_dt]
    else:
        query = "SELECT * FROM episodic_log WHERE ts_utc >= ?"
        params = [cutoff_dt.isoformat()]

    if action_filter:
        query += " AND action = ?"
        params.append(action_filter)
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    query += " ORDER BY ts_utc DESC LIMIT ?"
    params.append(int(limit))

    try:
        with _WRITE_LOCK:
            if backend == "duckdb":
                cursor = conn.cursor()
                try:
                    df = cursor.execute(query, params).fetchdf()
                finally:
                    cursor.close()
                records = df.to_dict(orient="records")
                for rec in records:
                    for k, v in list(rec.items()):
                        if isinstance(v, float) and math.isnan(v):
                            rec[k] = None
                        elif v is not None and not isinstance(
                            v, (str, int, float, bool, dict, list)
                        ):
                            rec[k] = str(v)
                return records
            else:
                cursor = conn.cursor()
                try:
                    rows = cursor.execute(query, params).fetchall()
                finally:
                    cursor.close()
                records = [dict(r) for r in rows]
                for rec in records:
                    for k, v in list(rec.items()):
                        if v == "":
                            rec[k] = None
                return records
    except Exception:
        logger.exception("EpisodeLogger : échec de fetch")
        return []


def count_episodes() -> int:
    try:
        conn = _get_conn()
        with _WRITE_LOCK:
            cursor = conn.cursor()
            try:
                row = cursor.execute(
                    "SELECT COUNT(*) FROM episodic_log"
                ).fetchone()
            finally:
                cursor.close()
            if row is None:
                return 0
            return int(row[0])
    except Exception:
        return 0


def close_all() -> None:
    """★ v39 — Ferme la connexion unique partagée."""
    global _SHARED_CONN, _SHARED_CONN_BACKEND
    with _SHARED_CONN_LOCK:
        if _SHARED_CONN is not None:
            try:
                _SHARED_CONN.close()
                logger.info("EpisodeLogger : connexion partagée fermée")
            except Exception:
                pass
            _SHARED_CONN = None
        _SHARED_CONN_BACKEND = None


# ══════════════════════════════════════════════════════════════════════════════
# TEST AUTONOME
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    print(f"\n🔧 Backend : {backend_name()}")
    print(f"📊 Lazy stats : {lazy_stats()}\n")

    configure("./data/test_episode_logger")
    print(f"📁 DB path : {_get_db_path()}\n")

    e1 = log_episode("web_sync", {"q": "t1"}, "success", "ok", latency_ms=100)
    e2 = log_episode("web_sync", {"q": "t2"}, "error", "timeout",
                     error_type="TimeoutError", latency_ms=5000)
    e3 = log_episode("create_dynamic_skill", {"n": "x"}, "error", "refus",
                     error_type="SandboxRejection")
    assert e1 and e2 and e3
    assert count_episodes() >= 3
    print("✅ log_episode OK")

    eps = fetch_recent_episodes(hours=1, limit=10)
    assert len(eps) >= 3
    print(f"✅ fetch_recent_episodes OK ({len(eps)} épisodes)")

    errors = fetch_recent_episodes(hours=1, status_filter="error", limit=10)
    assert len(errors) >= 2
    print(f"✅ filtre status OK ({len(errors)} erreurs)")

    # Test concurrence (simule ReflexLoop + chat simultanés)
    import threading as _t
    errs = []
    def _worker(i):
        try:
            log_episode("concurrent_test", {"i": i}, "success")
            fetch_recent_episodes(hours=1, limit=5)
        except Exception as ex:
            errs.append(str(ex))
    threads = [_t.Thread(target=_worker, args=(i,)) for i in range(5)]
    for th in threads: th.start()
    for th in threads: th.join()
    assert not errs, f"Erreurs concurrence: {errs}"
    print("✅ concurrence 5 threads OK (plus de DB verrouillée)")

    close_all()
    print(f"\n🎉 TOUS LES TESTS PASSENT | backend={backend_name()}\n")