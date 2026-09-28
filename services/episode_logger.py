# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Episode Logger (DuckDB local, ADR-001) — FIX v36 Windows
# ------------------------------------------------------------------------------
# Persiste CHAQUE exécution d'action pour permettre au Reflex-Loop :
#   • de miner des patterns récurrents (par action / erreur / contexte)
#   • de comparer succès vs échecs
#   • de mesurer latence et efficience
#
# Stockage : DuckDB local (data/analytics.duckdb)
#   - Zéro round-trip réseau
#   - Connexion thread-local (DuckDB n'est pas thread-safe)
#   - Schéma créé automatiquement au premier appel
# ==============================================================================
from __future__ import annotations

import json
import logging
import math
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import duckdb

logger = logging.getLogger("bek.episode_logger")


# ==============================================================================
# CONFIGURATION
# ==============================================================================
DEFAULT_DB_PATH = "./data/analytics.duckdb"


# ==============================================================================
# CONNEXIONS THREAD-LOCAL
# ==============================================================================
_conn_lock = threading.Lock()
_WRITE_LOCK = threading.RLock()  # FIX v36 Windows: 1 seul ecrivain DuckDB a la fois
_connections: Dict[int, duckdb.DuckDBPyConnection] = {}
_db_path: Optional[str] = None


def _get_db_path() -> str:
    global _db_path
    if _db_path is None:
        _db_path = DEFAULT_DB_PATH
    return _db_path


def configure(db_path: str) -> None:
    """
    Configure le chemin de la DB.
    À appeler une fois au boot avant le premier log.
    """
    global _db_path
    _db_path = db_path
    logger.info("EpisodeLogger configuré | path=%s", db_path)


_read_connections: Dict[int, duckdb.DuckDBPyConnection] = {}

def _get_conn(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """
    Retourne une connexion DuckDB pour le thread courant.
    FIX v36 Windows: lectures en read_only=True.
    """
    tid = threading.get_ident()
    cache = _read_connections if read_only else _connections
    conn = cache.get(tid)
    if conn is not None:
        return conn

    with _conn_lock:
        conn = cache.get(tid)
        if conn is not None:
            return conn
        path = _get_db_path()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if read_only:
            conn = duckdb.connect(path, read_only=True)
        else:
            conn = duckdb.connect(path)
            _ensure_schema(conn)
        cache[tid] = conn
        logger.debug(
            "EpisodeLogger : nouvelle connexion | tid=%s read_only=%s",
            tid, read_only,
        )
    return conn


def _ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Crée la table episodic_log si elle n'existe pas."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS episodic_log (
            episode_id      VARCHAR PRIMARY KEY,
            trace_id        VARCHAR,
            task_id         VARCHAR,
            correlation_id  VARCHAR,
            action          VARCHAR NOT NULL,
            parameters      VARCHAR,      -- JSON stringifié
            status          VARCHAR NOT NULL,  -- success | error | exception
            message         VARCHAR,
            error_type      VARCHAR,
            latency_ms      DOUBLE,
            ts_utc          TIMESTAMP,
            source          VARCHAR,      -- action_executor | hermes | manual
            context_hash    VARCHAR,
            extra           VARCHAR       -- JSON pour extensions
        );
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_episodic_action_ts
        ON episodic_log(action, ts_utc);
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_episodic_status
        ON episodic_log(status);
    """)


# ==============================================================================
# API PUBLIQUE
# ==============================================================================
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

    ts_utc = datetime.now(timezone.utc)

    try:
        conn = _get_conn()
        with _WRITE_LOCK:  # FIX v36 Windows: evite 'database locked' avec 10 workers Hermes
            conn.execute(
                """
                INSERT INTO episodic_log (
                    episode_id, trace_id, task_id, correlation_id,
                    action, parameters, status, message, error_type,
                    latency_ms, ts_utc, source, context_hash, extra
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    trace_id,
                    task_id,
                    correlation_id,
                    action,
                    params_json,
                    status,
                    message,
                    error_type,
                    float(latency_ms or 0.0),
                    ts_utc,
                    source,
                    context_hash,
                    extra_json,
                ),
            )
    except Exception as exc:
        logger.exception("EpisodeLogger : échec d'insertion | action=%s", action)
        return ""

    return episode_id


# ==============================================================================
# LECTURE (pour Reflex-Loop)
# ==============================================================================
def fetch_recent_episodes(
    hours: int = 24,
    action_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """
    Récupère les épisodes récents pour analyse.
    Utilisé par Reflex-Loop pour miner les patterns.

    Note : les valeurs NULL/vides des colonnes VARCHAR sont retournées
    comme None (et non NaN), pour cohérence avec le reste du code.
    """
    # FIX v36 Windows: cutoff calcule en Python (l'ancien INTERVAL (? || ' hours') plante sur DuckDB)
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=int(hours))
    import time as _time
    conn = None
    last_err = None
    for _ in range(3):
        try:
            conn = _get_conn(read_only=True)
            break
        except Exception as e:
            last_err = e
            _time.sleep(0.5)
    if conn is None:
        logger.error("EpisodeLogger : DB verrouillee, ferme l'autre python : %s", last_err)
        return []
    query = """
        SELECT * FROM episodic_log
        WHERE ts_utc >= ?
    """
    params: list = [cutoff]

    if action_filter:
        query += " AND action = ?"
        params.append(action_filter)
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    query += " ORDER BY ts_utc DESC LIMIT ?"
    params.append(int(limit))

    try:
        with _WRITE_LOCK:  # FIX v36 Windows: lecture protegee pendant ecritures
            result = conn.execute(query, params).fetchdf()
        records = result.to_dict(orient="records")

        # --- Normalisation : pandas met NaN (float) pour les colonnes
        #     VARCHAR vides. On les convertit en None pour cohérence.
        for rec in records:
            for k, v in list(rec.items()):
                if isinstance(v, float) and math.isnan(v):
                    rec[k] = None
                # pandas met aussi pd.NaT pour les TIMESTAMP NULL
                elif v is not None and not isinstance(
                    v, (str, int, float, bool, dict, list)
                ):
                    rec[k] = str(v)
        return records
    except Exception as exc:
        logger.exception("EpisodeLogger : échec de fetch")
        return []


def count_episodes() -> int:
    """Nombre total d'épisodes loggés. Utile pour tests/diagnostic."""
    try:
        conn = _get_conn(read_only=True)
        row = conn.execute("SELECT COUNT(*) FROM episodic_log").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def close_all() -> None:
    """Ferme toutes les connexions. Utile pour tests/shutdown propre."""
    with _conn_lock:
        _all = list(_connections.items()) + list(_read_connections.items())
        for tid, conn in _all:
            try:
                conn.close()
            except Exception:
                pass
        _connections.clear()
        _read_connections.clear()


# ==============================================================================
# TEST AUTONOME
# ==============================================================================
if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    configure("./data/test_episode_logger.duckdb")

    print("\n=== TEST 1 : log 3 épisodes ===")
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
        trace_id="BEK-TRC-BBB",
        task_id="task_002",
        correlation_id="corr_002",
    )
    e3 = log_episode(
        action="create_dynamic_skill",
        parameters={"skill_name": "evil", "code_content": "import subprocess"},
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

    print("\n=== TEST 5 : NaN normalisé en None ===")
    # Un épisode avec error_type vide → doit revenir None, pas NaN
    log_episode(
        action="no_error_test",
        parameters={},
        status="success",
        message="ok",
        error_type=None,
    )
    eps = fetch_recent_episodes(hours=1, action_filter="no_error_test", limit=5)
    assert len(eps) >= 1
    et = eps[0].get("error_type")
    assert et is None, f"Attendu None, reçu {et!r} ({type(et)})"
    print("✅ TEST 5 OK")

    close_all()
    print("\n🎉 TOUS LES TESTS PASSENT — EPISODE LOGGER VALIDÉ.\n")