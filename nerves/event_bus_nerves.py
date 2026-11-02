# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 3 — UNIFICATION EVENTBUS (v18.9) — ANTI-BOUCLE FIX
# nerves/event_bus_nerves.py
# ------------------------------------------------------------------------------
# ★ v18.9 (2026-10-06) — FIX BOUCLE INFINIE :
#   - SUPPRESSION du double publish (Kafka + Async)
#   - Utilise UNIQUEMENT l'async client (moderne)
#   - Bridge Kafka→Async désactivé (créait le cycle)
#   - Anti-boucle par correlation_id renforcé
# ==============================================================================

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import threading
import time
import uuid
from collections import deque
from typing import Any, Deque, Dict, Optional, Set

logger = logging.getLogger("bek.nerves.event_bus")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv(
        "BEK_ENABLE_EVENT_BUS_NERVES",
        "true",
    ).lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------

_MAX_ASYNC_WORKERS = 2                    # ★ v18.9 : réduit de 4 à 2
_BRIDGE_TIMEOUT_SEC = 3.0

# ★ v18.9 — Anti-boucle renforcée
_DEDUP_WINDOW_SEC = 10.0                  # Fenêtre de 10s (au lieu de 5s)
_MAX_DEDUP_ENTRIES = 5000

_DEFAULT_TOPICS: Set[str] = {
    "web-cleaned",
    "skills-index",
    "error-signals",
    "vector-context",
}


def _resolve_topics() -> Set[str]:
    try:
        from event_bus import EventBusKafka
        topics = getattr(EventBusKafka, "VALID_TOPICS", None)
        if topics:
            return set(topics)
    except Exception as exc:
        logger.debug("[Nerf 3] Impossible de lire VALID_TOPICS : %s", exc)
    return set(_DEFAULT_TOPICS)


# ------------------------------------------------------------------------------
# BRIDGE v18.9 — SIMPLIFIÉ (UN SEUL BUS)
# ------------------------------------------------------------------------------

class EventBusBridge:
    """
    ★ v18.9 — Bridge SIMPLIFIÉ.

    Au lieu d'utiliser 2 bus (Kafka sync + Async client) qui créent des doublons,
    on utilise UNIQUEMENT l'async client (event_bus_client.py).
    """

    TOPICS: Set[str] = set(_DEFAULT_TOPICS)

    def __init__(self) -> None:
        self._activated = False
        self._lock = threading.RLock()

        # ★ v18.9 — Cache de dédup renforcé
        self._recent_publishes: Dict[str, float] = {}
        self._dedup_lock = threading.Lock()
        self._stats_lock = threading.Lock()

        # Client async (le SEUL bus utilisé)
        self._async_bus: Any = None
        self._async_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None

        self._active_topics: Set[str] = set()
        self._bridge_id = f"bridge_{uuid.uuid4().hex[:8]}"

        self._stats = {
            "publish_count": 0,
            "dedup_skipped_count": 0,
            "error_count": 0,
            "timeout_count": 0,
        }

    # --------------------------------------------------------------------------
    # ★ v18.9 — DÉDUP RENFORCÉE
    # --------------------------------------------------------------------------

    def _is_duplicate(self, correlation_id: str, topic: str) -> bool:
        """
        Retourne True si le même (correlation_id, topic) a été publié
        dans les _DEDUP_WINDOW_SEC dernières secondes.
        """
        if not correlation_id:
            return False

        key = f"{topic}|{correlation_id}"
        now = time.time()

        with self._dedup_lock:
            last = self._recent_publishes.get(key, 0.0)
            if now - last < _DEDUP_WINDOW_SEC:
                self._increment_stat("dedup_skipped_count")
                return True

            self._recent_publishes[key] = now

            # Nettoyage périodique
            if len(self._recent_publishes) > _MAX_DEDUP_ENTRIES:
                cutoff = now - _DEDUP_WINDOW_SEC
                self._recent_publishes = {
                    k: v for k, v in self._recent_publishes.items()
                    if v > cutoff
                }

        return False

    # --------------------------------------------------------------------------
    # STATS
    # --------------------------------------------------------------------------

    def _increment_stat(self, key: str, delta: int = 1) -> None:
        with self._stats_lock:
            self._stats[key] = self._stats.get(key, 0) + delta

    # --------------------------------------------------------------------------
    # ACTIVATION
    # --------------------------------------------------------------------------

    def activate(self) -> Dict[str, Any]:
        with self._lock:
            if self._activated:
                return {
                    "status": "already_activated",
                    "mode": "async_only",
                    "stats": dict(self._stats),
                    "bridge_id": self._bridge_id,
                }

            # Récupérer l'async client (LE SEUL BUS)
            try:
                from event_bus_client import event_bus
                self._async_bus = event_bus
            except Exception as exc:
                logger.error("[Nerf 3] EventBusClient indisponible : %s", exc)
                return {
                    "status": "error",
                    "message": f"EventBusClient indisponible : {exc}",
                }

            # Executor
            self._async_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=_MAX_ASYNC_WORKERS,
                thread_name_prefix="bek-bridge",
            )

            self._active_topics = _resolve_topics()
            EventBusBridge.TOPICS = set(self._active_topics)

            self._activated = True

            logger.info(
                "[Nerf 3] EventBus active | mode=async_only | "
                "topics=%d | dedup_window=%.1fs | bridge_id=%s",
                len(self._active_topics),
                _DEDUP_WINDOW_SEC,
                self._bridge_id,
            )

            return {
                "status": "ok",
                "mode": "async_only",
                "topics": sorted(self._active_topics),
                "dedup_window_sec": _DEDUP_WINDOW_SEC,
                "bridge_id": self._bridge_id,
                "note": "v18.9 — Anti-boucle : un seul bus + dédup renforcée",
            }

    # --------------------------------------------------------------------------
    # PUBLICATION ASYNC (UNE SEULE FOIS)
    # --------------------------------------------------------------------------

    def _publish_async(self, topic: str, payload: Dict[str, Any]) -> None:
        """Publie sur l'async client (une seule fois, via un nouveau loop)."""
        try:
            if self._async_bus is None:
                return

            coroutine = self._async_bus.publish(topic, payload)

            try:
                asyncio.run(
                    asyncio.wait_for(coroutine, timeout=_BRIDGE_TIMEOUT_SEC)
                )
                self._increment_stat("publish_count")
            except asyncio.TimeoutError:
                self._increment_stat("timeout_count")

        except Exception as exc:
            self._increment_stat("error_count")
            logger.debug("[Nerf 3] async publish échoué : %s", exc)

    # --------------------------------------------------------------------------
    # ★ v18.9 — API UNIFIÉE (UN SEUL BUS, DÉDUP RENFORCÉE)
    # --------------------------------------------------------------------------

    def publish_unified(self, topic: str, payload: Dict[str, Any]) -> str:
        """
        ★ v18.9 — Publie sur l'async client UNIQUEMENT.

        - Pas de Kafka (évite le doublon)
        - Pas de bridge (évite la boucle)
        - Dédup par (topic, correlation_id) renforcée
        """
        if not isinstance(payload, dict):
            payload = {}

        # Récupérer ou générer le correlation_id
        correlation_id = str(payload.get("correlation_id") or "")

        # ★ DÉDUP : skip si (topic, correlation_id) déjà publié récemment
        if self._is_duplicate(correlation_id, topic):
            logger.debug(
                "[Nerf 3] Dedup skip | topic=%s | corr=%s",
                topic, correlation_id[:20],
            )
            return correlation_id

        # Publier sur l'async client (une seule fois)
        if self._async_bus is not None and self._async_executor is not None:
            try:
                forward_payload = dict(payload)
                if correlation_id:
                    forward_payload["correlation_id"] = correlation_id
                forward_payload["_bridge_id"] = self._bridge_id

                self._async_executor.submit(
                    self._publish_async, topic, forward_payload
                )
            except RuntimeError:
                self._increment_stat("error_count")

        return correlation_id

    # --------------------------------------------------------------------------
    # STATUS
    # --------------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._stats_lock:
            stats = dict(self._stats)

        with self._dedup_lock:
            dedup_entries = len(self._recent_publishes)

        return {
            "activated": self._activated,
            "mode": "async_only",
            "async_available": self._async_bus is not None,
            "active_topics": sorted(self._active_topics),
            "dedup_window_sec": _DEDUP_WINDOW_SEC,
            "dedup_entries": dedup_entries,
            "max_dedup_entries": _MAX_DEDUP_ENTRIES,
            "bridge_id": self._bridge_id,
            "stats": stats,
        }

    # --------------------------------------------------------------------------
    # SHUTDOWN
    # --------------------------------------------------------------------------

    def shutdown(self) -> None:
        with self._lock:
            if self._async_executor is not None:
                try:
                    self._async_executor.shutdown(wait=False, cancel_futures=True)
                except Exception:
                    pass
                self._async_executor = None

            self._activated = False
            logger.info("[Nerf 3] EventBus bridge arrêté")


# ------------------------------------------------------------------------------
# SINGLETON
# ------------------------------------------------------------------------------

_bridge_instance: Optional[EventBusBridge] = None
_bridge_singleton_lock = threading.RLock()


def get_event_bus_bridge() -> EventBusBridge:
    global _bridge_instance
    with _bridge_singleton_lock:
        if _bridge_instance is None:
            _bridge_instance = EventBusBridge()
        return _bridge_instance


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_event_bus_nerves() -> Dict[str, Any]:
    if not _is_enabled():
        logger.warning("[Nerf 3] Désactivé via BEK_ENABLE_EVENT_BUS_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_EVENT_BUS_NERVES=false",
        }

    try:
        bridge = get_event_bus_bridge()
        result = bridge.activate()
        logger.info("[Nerf 3] Activation : %s", result.get("status"))
        return result
    except Exception as exc:
        logger.error("[Nerf 3] Activation échouée : %s", exc)
        return {"status": "error", "message": str(exc)}


# ------------------------------------------------------------------------------
# HELPER PUBLIC
# ------------------------------------------------------------------------------

def publish_event_unified(topic: str, payload: Dict[str, Any]) -> str:
    try:
        bridge = get_event_bus_bridge()
        if not bridge._activated:
            bridge.activate()
        return bridge.publish_unified(topic, payload)
    except Exception as exc:
        logger.debug("[Nerf 3] publish_event_unified échoué : %s", exc)
        return ""