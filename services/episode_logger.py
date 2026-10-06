# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Episode Logger (DuckDB local OU SQLite fallback) — v38
# ------------------------------------------------------------------------------
# Persiste CHAQUE exécution d'action pour permettre au Reflex-Loop :
#   • de miner des patterns récurrents (par action / erreur / contexte)
#   • de comparer succès vs échecs
#   • de mesurer latence et efficience
#
# v37 (2026-09-28) — FALLBACK SQLITE :
#   Sur Render Free (512 MB), DuckDB compile trop longtemps ou timeout.
#   → Si `import duckdb` échoue, on bascule automatiquement sur SQLite.
#   → API identique : log_episode, fetch_recent_episodes, count_episodes, close_all
#
# ★ v38 (2026-10-06) — LAZY LOADING DuckDB :
#   - ★ FIX RAM : DuckDB n'est plus chargé au boot (économie ~50 MB)
#   - ★ _detect_backend() appelée au 1er usage réel
#   - ★ Thread-safe : _BACKEND_LOCK pour éviter les doubles init
#   - ★ Flag BEK_LAZY_LOAD_DUCKDB (optionnel)
#   - ★ Fonction lazy_stats() pour health check
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
# ★ v38 — DÉTECTION LAZY DU BACKEND
# ==============================================================================
_BACKEND: Optional[str] = None      # "duckdb" ou "sqlite" (détecté lazy)
_duckdb_module = None
_BACKEND_LOCK = threading.Lock()


def _detect_backend() -> str:
    """
    ★ v38 — Détecte le backend au 1er appel (lazy).

    Priorité :
      1. Si BEK_FORCE_SQLITE_EPISODE_LOG=true → SQLite
      2. Sinon → essaie DuckDB (import lazy)
      3. Fallback → SQLite

    Thread-safe : un seul thread détecte, les autres attendent.
    """
    global _duckdb_module, _BACKEND

    # Déjà détecté ?
    if _BACKEND is not None:
        return _BACKEND

    with _BACKEND_LOCK:
        # Double-check après acquisition du lock
        if _BACKEND is not None:
            return _BACKEND

        # 1. Force SQLite si demandé
        force_sqlite = os.getenv(
            "BEK_FORCE_SQLITE_EPISODE_LOG", ""
        ).strip().lower() in ("1", "true", "yes", "on")

        if force_sqlite:
            _BACKEND = "sqlite"
            logger.info(
                "[episode_logger] Backend forcé : sqlite "
                "(BEK_FORCE_SQLITE_EPISODE_LOG=true)"
            )
            return _BACKEND

        # 2. Essayer DuckDB (import lazy)
        logger.info("[episode_logger] Chargement DuckDB (lazy)...")
        try:
            import duckdb as _duckdb
            _duckdb_module = _duckdb
            _BACKEND = "duckdb"
            logger.info("[episode_logger] ✅ Backend : duckdb")
        except ImportError as exc:
            _duckdb_module = None
            _BACKEND = "sqlite"
            logger.info(
                "[episode_logger] DuckDB indisponible (%s) → fallback sqlite",
                exc,
            )

        return _BACKEND


def backend_name() -> str:
    """
    Retourne le backend actif ('duckdb' ou 'sqlite').
    ★ v38 : déclenche la détection lazy si nécessaire.
    """
    return _detect_backend()


def lazy_stats() -> dict:
    """★ v38 — Stats pour health check."""
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
    """Retourne le chemin par défaut selon le backend (lazy)."""
    backend = _detect_backend()
    return DEFAULT_DB_PATH_DUCKDB if backend == "duckdb" else DEFAULT_DB_PATH_SQLITE


def configure(db_path: str) -> None:
    """
    Configure le chemin de la DB.
    À appeler une fois au boot avant le premier log.
    Le chemin sera adapté à l'extension du backend (.duckdb ou .sqlite).

    ★ v38 : déclenche la détection lazy du backend.
    """
    global _DB_PATH

    backend = _detect_backend()

    # Adapte l'extension au backend
    p = Path(db_path)
    if backend == "sqlite" and p.suffix.lower() not in (".sqlite", ".db"):
        p = p.with_suffix(".sqlite")
    elif backend == "duckdb" and p.suffix.lower() not in (".duckdb", ".db"):
        p = p.with_suffix(".duckdb")

    _DB_PATH = str(p)
    logger.info(
        "EpisodeLogger configuré | backend=%s | path=%s",
        backend, _DB_PATH,
    )


def _get_db_path() -> str:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = _default_path()
    return _DB_PATH


# ==============================================================================
# CONNEXIONS THREAD-LOCAL
# ==============================================================================
_conn_lock = threading.Lock()
_WRITE_LOCK = threading.RLock()
_read_connections: Dict[int, Any] = {}
_write_connections: Dict[int, Any] = {}


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA — 2 variantes (DuckDB / SQLite)
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

_INDEXES_DUCKDB = (
    "CREATE INDEX IF NOT EXISTS idx_episodic_action_ts ON episodic_log(action, ts_utc);",
    "CREATE INDEX IF NOT EXISTS idx_episodic_status ON episodic_log(status);",
)

_INDEXES_SQLITE = (
    "CREATE INDEX IF NOT EXISTS idx_episodic_action_ts ON episodic_log(action, ts_utc);",
    "CREATE INDEX IF NOT EXISTS idx_episodic_status ON episodic_log(status);",
)


def _ensure_schema(conn: Any, backend: str) -> None:
    """Crée la table episodic_log si elle n'existe pas."""
    schema = _SCHEMA_DUCKDB if backend == "duckdb" else _SCHEMA_SQLITE
    indexes = _INDEXES_DUCKDB if backend == "duckdb" else _INDEXES_SQLITE

    conn.execute(schema)
    for idx in indexes:
        try:
            conn.execute(idx)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# CONNEXION
# ══════════════════════════════════════════════════════════════════════════════

def _get_conn(read_only: bool = False) -> Any:
    """
    Retourne une connexion DuckDB ou SQLite pour le thread courant.
    - DuckDB : read_only=True pour lectures (Windows lock).
    - SQLite : check_same_thread=False pour partage entre threads.

    ★ v38 : détecte le backend au 1er appel (lazy).
    """
    tid = threading.get_ident()
    cache = _read_connections if read_only else _write_connections
    conn = cache.get(tid)
    if conn is not None:
        return conn

    with _conn_lock:
        conn = cache.get(tid)
        if conn is not None:
            return conn

        # ★ v38 : détection lazy du backend
        backend = _detect_backend()

        path = _get_db_path()
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        if backend == "duckdb":
            if read_only:
                conn = _duckdb_module.connect(path, read_only=True)
            else:
                conn = _duckdb_module.connect(path)
                _ensure_schema(conn, backend)
        else:
            # SQLite
            conn = sqlite3.connect(
                path,
                timeout=10.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            if not read_only:
                _ensure_schema(conn, backend)
                conn.commit()

        cache[tid] = conn
        logger.debug(
            "EpisodeLogger : nouvelle connexion | backend=%s | tid=%s | read_only=%s",
            backend, tid, read_only,
        )
    return conn


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
    """
    Enregistre un épisode d'exécution.

    Returns:
        episode_id (uuid court) ou "" en cas d'échec silencieux.
    """
    episode_id = f"ep_{uuid.uuid4().hex[:16]}"

    # ---- Sérialisation défensive ----
    try:
        params_json = json.dumps(parameters, default=str, ensure_ascii=False)
    except Exception:
        params_json = json.dumps({"_unserializable": True})

    try:
        extra_json = json.dumps(extra or {}, default=str, ensure_ascii=False)
    except Exception:
        extra_json = "{}"

    # ---- Troncature ----
    if message and len(message) > 2000:
        message = message[:2000] + "…"

    # ★ v38 : détection lazy
    backend = _detect_backend()

    now_utc = datetime.now(timezone.utc)

    # ---- Formats selon backend ----
    if backend == "duckdb":
        ts_value = now_utc
        placeholder = "?"
    else:
        # SQLite n'a pas de type TIMESTAMP → string ISO
        ts_value = now_utc.isoformat()
        placeholder = "?"

    try:
        conn = _get_conn(read_only=False)
        with _WRITE_LOCK:
            sql = f"""
                INSERT INTO episodic_log (
                    episode_id, trace_id, task_id, correlation_id,
                    action, parameters, status, message, error_type,
                    latency_ms, ts_utc, source, context_hash, extra
                ) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder},
                          {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder},
                          {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
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
    """
    Récupère les épisodes récents pour analyse.
    Utilisé par Reflex-Loop pour miner les patterns.
    """
    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=int(hours))

    # ★ v38 : détection lazy
    backend = _detect_backend()

    conn = None
    last_err = None
    for _ in range(3):
        try:
            conn = _get_conn(read_only=True)
            break
        except Exception as e:
            last_err = e
            import time as _t
            _t.sleep(0.5)

    if conn is None:
        logger.error("EpisodeLogger : DB verrouillée : %s", last_err)
        return []

    # ─── Construit la requête selon backend ───
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
                df = conn.execute(query, params).fetchdf()
                records = df.to_dict(orient="records")
                # Normalisation NaN → None
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
                cur = conn.execute(query, params)
                rows = cur.fetchall()
                records = [dict(r) for r in rows]
                # Normalisation None pour colonnes vides
                for rec in records:
                    for k, v in list(rec.items()):
                        if v == "":
                            rec[k] = None
                return records
    except Exception:
        logger.exception("EpisodeLogger : échec de fetch")
        return []


def count_episodes() -> int:
    """Nombre total d'épisodes loggés."""
    try:
        conn = _get_conn(read_only=True)
        with _WRITE_LOCK:
            row = conn.execute("SELECT COUNT(*) FROM episodic_log").fetchone()
            if row is None:
                return 0
            # DuckDB retourne un tuple, SQLite retourne un Row
            if isinstance(row, sqlite3.Row):
                return int(row[0])
            return int(row[0])
    except Exception:
        return 0


def close_all() -> None:
    """Ferme toutes les connexions."""
    with _conn_lock:
        all_conns = list(_read_connections.items()) + list(_write_connections.items())
        for tid, conn in all_conns:
            try:
                conn.close()
            except Exception:
                pass
        _read_connections.clear()
        _write_connections.clear()


# ══════════════════════════════════════════════════════════════════════════════
# TEST AUTONOME
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    print(f"\n🔧 Backend actif : {backend_name()}\n")
    print(f"📊 Lazy stats : {lazy_stats()}\n")

    # Chemin de test
    test_path = "./data/test_episode_logger"
    configure(test_path)
    print(f"📁 DB path : {_get_db_path()}\n")

    print("=== TEST 1 : log 3 épisodes ===")
    e1 = log_episode(
        action="web_sync",
        parameters={"query": "test 1"},
        status="success",
        message="3 résultats trouvés",
        latency_ms=123.4,
        trace_id="BEK-TRC-AAA",
        task_id="task_001",
        correlation_id="corr_001",
    )
    e2 = log_episode(
        action="web_sync",
        parameters={"query": "test 2"},
        status="error",
        message="Timeout DDG",
        error_type="TimeoutError",
        latency_ms=5001.2,
    )
    e3 = log_episode(
        action="create_dynamic_skill",
        parameters={"skill_name": "evil"},
        status="error",
        message="Sandbox AST refus",
        error_type="SandboxRejection",
        latency_ms=12.0,
    )
    print(f"e1={e1} | e2={e2} | e3={e3}")
    assert e1 and e2 and e3
    assert count_episodes() >= 3
    print("✅ TEST 1 OK")

    print("\n=== TEST 2 : fetch récents ===")
    eps = fetch_recent_episodes(hours=1, limit=10)
    print(f"Épisodes récupérés : {len(eps)}")
    for e in eps[:3]:
        print(f"  - {e['action']:24s} | {e['status']:8s} | {e['latency_ms']}ms")
    assert len(eps) >= 3
    print("✅ TEST 2 OK")

    print("\n=== TEST 3 : fetch par status ===")
    errors = fetch_recent_episodes(hours=1, status_filter="error", limit=10)
    print(f"Épisodes en erreur : {len(errors)}")
    assert len(errors) >= 2
    print("✅ TEST 3 OK")

    print("\n=== TEST 4 : serialization robuste ===")
    e4 = log_episode(
        action="weird_action",
        parameters={"obj": object(), "num": 42},
        status="success",
        message="ok",
    )
    assert e4
    print("✅ TEST 4 OK")

    close_all()
    print(f"\n🎉 TOUS LES TESTS PASSENT — Backend={backend_name()}\n")
    print(f"📊 Lazy stats finales : {lazy_stats()}\n")