# -*- coding: utf-8 -*-
# ==============================================================================
# services/memory_service.py — BEK-v18.13
# ------------------------------------------------------------------------------
# Brique de mémoire locale (LanceDB + DuckDB) conforme à l'ADR-001.
# Conçu pour tourner efficacement sur des conteneurs à ressources limitées.
#
# ★ v18.13 (2026-10-06) — LAZY LOADING :
#   - ★ FIX RAM : LanceDB + DuckDB ne sont plus chargés au boot
#   - ★ Import à la demande au 1er usage réel
#   - ★ Thread-safe : locks d'initialisation
#   - ★ Feature flags :
#       BEK_DISABLE_LANCEDB=true          → désactive LanceDB
#       BEK_DISABLE_DUCKDB_ANALYTICS=true → désactive DuckDB analytique
#   - ★ Stats exposées : is_lancedb_loaded(), is_duckdb_loaded(), lazy_stats()
# ==============================================================================
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.services.memory_service")


# ==============================================================================
# ★ v18.13 — FEATURE FLAGS
# ==============================================================================

def _env_bool(name: str, default: bool = False) -> bool:
    """Lit une variable d'env booléenne."""
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("true", "1", "yes", "on")


_DISABLE_LANCEDB = _env_bool("BEK_DISABLE_LANCEDB", False)
_DISABLE_DUCKDB_ANALYTICS = _env_bool("BEK_DISABLE_DUCKDB_ANALYTICS", False)


# ==============================================================================
# SERVICE PRINCIPAL
# ==============================================================================

class OptimizedMemoryService:
    """
    Mémoire locale optimisée (LanceDB + DuckDB).

    ★ v18.13 : Lazy loading complet.
      - L'instance est créée instantanément (aucun import lourd).
      - LanceDB est chargé au 1er appel de fast_vector_search/upsert_vector.
      - DuckDB est chargé au 1er appel de analytical_query.
    """

    def __init__(self, base_path: str = "./data"):
        """
        Initialise les chemins (rapide, aucun import lourd).

        ★ v18.13 : LanceDB et DuckDB NE sont PAS chargés ici.
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Chemins
        self.lancedb_path = str(self.base_path / "lancedb")
        self.duckdb_path = str(self.base_path / "analytics.duckdb")

        # État interne (lazy)
        self._lancedb_conn = None
        self._lancedb_lock = threading.Lock()
        self._lancedb_loaded = False

        self._duck_conn = None
        self._duck_lock = threading.Lock()
        self._duck_loaded = False

        self._storage_initialized = False

        logger.info(
            "[MemoryService] Instance créée | base=%s | lazy_lancedb=%s | lazy_duckdb=%s",
            self.base_path,
            not _DISABLE_LANCEDB,
            not _DISABLE_DUCKDB_ANALYTICS,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # ★ v18.13 — LAZY LANCEDB
    # ══════════════════════════════════════════════════════════════════════════

    def _ensure_lancedb(self) -> Optional[Any]:
        """
        Charge LanceDB à la demande (thread-safe).

        Returns:
            La connexion LanceDB, ou None si désactivé/erreur.
        """
        if _DISABLE_LANCEDB:
            logger.debug("[MemoryService] LanceDB désactivé (BEK_DISABLE_LANCEDB=true)")
            return None

        if self._lancedb_loaded:
            return self._lancedb_conn

        with self._lancedb_lock:
            if self._lancedb_loaded:
                return self._lancedb_conn

            logger.info("[MemoryService] Chargement LanceDB (lazy)...")
            try:
                import lancedb
                self._lancedb_conn = lancedb.connect(self.lancedb_path)
                self._lancedb_loaded = True
                logger.info("[MemoryService] ✅ LanceDB chargé | path=%s", self.lancedb_path)
                return self._lancedb_conn
            except ImportError as exc:
                logger.warning("[MemoryService] LanceDB non installé : %s", exc)
                self._lancedb_loaded = True
                self._lancedb_conn = None
                return None
            except Exception as exc:
                logger.error("[MemoryService] Erreur init LanceDB : %s", exc)
                self._lancedb_loaded = True
                self._lancedb_conn = None
                return None

    def is_lancedb_loaded(self) -> bool:
        """Retourne True si LanceDB a déjà été chargé."""
        return self._lancedb_loaded

    # ══════════════════════════════════════════════════════════════════════════
    # ★ v18.13 — LAZY DUCKDB
    # ══════════════════════════════════════════════════════════════════════════

    def _ensure_duckdb(self) -> Optional[Any]:
        """
        Charge DuckDB à la demande (thread-safe).

        Returns:
            La connexion DuckDB, ou None si désactivé/erreur.
        """
        if _DISABLE_DUCKDB_ANALYTICS:
            logger.debug(
                "[MemoryService] DuckDB analytique désactivé "
                "(BEK_DISABLE_DUCKDB_ANALYTICS=true)"
            )
            return None

        if self._duck_loaded:
            return self._duck_conn

        with self._duck_lock:
            if self._duck_loaded:
                return self._duck_conn

            logger.info("[MemoryService] Chargement DuckDB (lazy)...")
            try:
                import duckdb
                self._duck_conn = duckdb.connect(self.duckdb_path)
                self._duck_loaded = True
                logger.info("[MemoryService] ✅ DuckDB chargé | path=%s", self.duckdb_path)
                return self._duck_conn
            except ImportError as exc:
                logger.warning("[MemoryService] DuckDB non installé : %s", exc)
                self._duck_loaded = True
                self._duck_conn = None
                return None
            except Exception as exc:
                logger.error("[MemoryService] Erreur init DuckDB : %s", exc)
                self._duck_loaded = True
                self._duck_conn = None
                return None

    def is_duckdb_loaded(self) -> bool:
        """Retourne True si DuckDB a déjà été chargé."""
        return self._duck_loaded

    # ══════════════════════════════════════════════════════════════════════════
    # INIT STORAGE (lazy, appelé au 1er usage)
    # ══════════════════════════════════════════════════════════════════════════

    def _init_storage(self) -> None:
        """
        Initialise la table vectorielle si elle n'existe pas.

        ★ v18.13 : appelé au 1er usage réel, pas dans __init__.
        """
        if self._storage_initialized:
            return

        db = self._ensure_lancedb()
        if db is None:
            return

        try:
            table_names = db.table_names()
            if "agent_memory" not in table_names:
                logger.info("[MemoryService] Création table 'agent_memory'...")
                initial_data = [{
                    "vector": [0.0] * 1536,
                    "text": "genesis_anchor",
                    "metadata": "{}",
                }]
                db.create_table("agent_memory", data=initial_data)
                logger.info("[MemoryService] ✅ Table 'agent_memory' créée")
            self._storage_initialized = True
        except Exception as exc:
            logger.error("[MemoryService] Erreur init storage : %s", exc)

    # ══════════════════════════════════════════════════════════════════════════
    # API PUBLIQUE — Recherche vectorielle
    # ══════════════════════════════════════════════════════════════════════════

    def fast_vector_search(
        self, query_vector: List[float], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recherche vectorielle locale instantanée.

        ★ v18.13 : Charge LanceDB au 1er appel.
        """
        # ★ v18.13 : lazy init
        self._init_storage()

        db = self._ensure_lancedb()
        if db is None:
            logger.debug("[MemoryService] fast_vector_search ignoré (LanceDB indisponible)")
            return []

        try:
            table = db.open_table("agent_memory")
            results = table.search(query_vector).limit(limit).to_pandas()
            return results.to_dict(orient="records")
        except Exception as exc:
            logger.error("[MemoryService] fast_vector_search échec : %s", exc)
            return []

    def upsert_vector(
        self, vector: List[float], text: str, metadata: Dict[str, Any]
    ) -> bool:
        """
        Ajoute une donnée vectorielle en local.

        ★ v18.13 : Charge LanceDB au 1er appel.

        Returns:
            True si succès, False sinon.
        """
        # ★ v18.13 : lazy init
        self._init_storage()

        db = self._ensure_lancedb()
        if db is None:
            logger.debug("[MemoryService] upsert_vector ignoré (LanceDB indisponible)")
            return False

        try:
            table = db.open_table("agent_memory")
            data = [{"vector": vector, "text": text, "metadata": str(metadata)}]
            table.add(data)
            return True
        except Exception as exc:
            logger.error("[MemoryService] upsert_vector échec : %s", exc)
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # API PUBLIQUE — Requête analytique
    # ══════════════════════════════════════════════════════════════════════════

    def analytical_query(self, sql_query: str) -> Optional[Any]:
        """
        Exécute une requête analytique via DuckDB.

        ★ v18.13 : Charge DuckDB au 1er appel.
        """
        conn = self._ensure_duckdb()
        if conn is None:
            logger.debug("[MemoryService] analytical_query ignoré (DuckDB indisponible)")
            return None

        try:
            return conn.execute(sql_query).fetchdf()
        except Exception as exc:
            logger.error("[MemoryService] analytical_query échec : %s", exc)
            return None

    # ══════════════════════════════════════════════════════════════════════════
    # STATS
    # ══════════════════════════════════════════════════════════════════════════

    def lazy_stats(self) -> dict:
        """★ v18.13 — Stats pour health check."""
        return {
            "lancedb_loaded": self._lancedb_loaded,
            "lancedb_disabled": _DISABLE_LANCEDB,
            "duckdb_loaded": self._duck_loaded,
            "duckdb_disabled": _DISABLE_DUCKDB_ANALYTICS,
            "storage_initialized": self._storage_initialized,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # CYCLE DE VIE
    # ══════════════════════════════════════════════════════════════════════════

    def close(self) -> None:
        """Ferme les connexions ouvertes."""
        if self._duck_conn is not None:
            try:
                self._duck_conn.close()
                logger.info("[MemoryService] DuckDB fermé")
            except Exception as exc:
                logger.debug("[MemoryService] Erreur close DuckDB : %s", exc)
            self._duck_conn = None
            self._duck_loaded = False

        # LanceDB n'a pas de méthode close() native
        self._lancedb_conn = None
        self._lancedb_loaded = False