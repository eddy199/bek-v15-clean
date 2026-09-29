# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 3 — UNIFICATION EVENTBUS (v18.7)
# nerves/event_bus_nerves.py
# ------------------------------------------------------------------------------
# Pont EventBusKafka (sync) <-> EventBusClient (async)
#
# Corrections :
#   - Anti-boucle robuste par bridge_id persistant.
#   - ★ v18.7 : Pont Async→Kafka DÉSACTIVÉ (cause de boucle infinie).
#   - FIFO borné pour les événements traités.
#   - Topics dérivés de EventBusKafka.VALID_TOPICS.
#   - Propagation correcte de correlation_id.
#   - Activation idempotente et thread-safe.
#   - Publication non bloquante.
# ==============================================================================

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
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

_MAX_ASYNC_WORKERS = 4
_MAX_PROCESSED_IDS = 10000
_BRIDGE_TIMEOUT_SEC = 5.0

_DEFAULT_KAFKA_TOPICS: Set[str] = {
    "web-cleaned",
    "skills-index",
    "error-signals",
    "vector-context",
}


def _resolve_kafka_topics() -> Set[str]:
    try:
        from event_bus import EventBusKafka
        topics = getattr(EventBusKafka, "VALID_TOPICS", None)
        if topics:
            return set(topics)
    except Exception as exc:
        logger.debug("[Nerf 3] Impossible de lire VALID_TOPICS : %s", exc)
    return set(_DEFAULT_KAFKA_TOPICS)


# ------------------------------------------------------------------------------
# BRIDGE
# ------------------------------------------------------------------------------

class EventBusBridge:
    KAFKA_TOPICS: Set[str] = set(_DEFAULT_KAFKA_TOPICS)

    def __init__(self) -> None:
        self._activated = False
        self._lock = threading.RLock()

        self._processed_keys_set: Set[str] = set()
        self._processed_keys_order: Deque[str] = deque()
        self._processed_lock = threading.Lock()

        self._kafka_bus: Any = None
        self._async_bus: Any = None

        self._active_topics: Set[str] = set()
        self._mode = "unknown"

        self._async_executor: Optional[
            concurrent.futures.ThreadPoolExecutor
        ] = None

        self._bridge_id = f"bridge_{uuid.uuid4().hex}"

        self._stats = {
            "kafka_to_async_count": 0,
            "async_to_kafka_count": 0,
            "dropped_count": 0,
            "error_count": 0,
        }
        self._stats_lock = threading.Lock()

    # --------------------------------------------------------------------------
    # ANTI-BOUCLE
    # --------------------------------------------------------------------------

    @staticmethod
    def _make_key(
        topic: str,
        correlation_id: str,
        timestamp_ms: int,
        bridge_id: str = "",
    ) -> str:
        return (
            f"{topic}|"
            f"{bridge_id}|"
            f"{correlation_id}|"
            f"{timestamp_ms}"
        )

    def _mark_and_check(self, key: str) -> bool:
        with self._processed_lock:
            if key in self._processed_keys_set:
                return False

            if len(self._processed_keys_order) >= _MAX_PROCESSED_IDS:
                oldest = self._processed_keys_order.popleft()
                self._processed_keys_set.discard(oldest)

            self._processed_keys_order.append(key)
            self._processed_keys_set.add(key)
            return True

    # --------------------------------------------------------------------------
    # STATS
    # --------------------------------------------------------------------------

    def _increment_stat(self, key: str, delta: int = 1) -> None:
        with self._stats_lock:
            self._stats[key] = self._stats.get(key, 0) + delta

    # --------------------------------------------------------------------------
    # EXTRACTION ÉVÉNEMENT
    # --------------------------------------------------------------------------

    @staticmethod
    def _extract_payload(event: Any) -> Dict[str, Any]:
        if not isinstance(event, dict):
            return {}
        payload = event.get("payload")
        if isinstance(payload, dict):
            return dict(payload)
        return dict(event)

    @staticmethod
    def _extract_correlation_id(
        event: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> str:
        return str(
            payload.get("correlation_id")
            or event.get("correlation_id")
            or ""
        )

    @staticmethod
    def _extract_timestamp_ms(
        event: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> int:
        raw_timestamp = (
            event.get("timestamp")
            or payload.get("timestamp")
            or time.time()
        )
        try:
            value = float(raw_timestamp)
            if value > 10_000_000_000:
                return int(value)
            return int(value * 1000)
        except (TypeError, ValueError):
            return int(time.time() * 1000)

    # --------------------------------------------------------------------------
    # ACTIVATION
    # --------------------------------------------------------------------------

    def activate(self) -> Dict[str, Any]:
        with self._lock:
            if self._activated:
                return {
                    "status": "already_activated",
                    "mode": self._mode,
                    "stats": dict(self._stats),
                    "topics": sorted(self._active_topics),
                    "bridge_id": self._bridge_id,
                }

            # Kafka
            try:
                from event_bus import EventBusKafka
                self._kafka_bus = EventBusKafka()
            except Exception as exc:
                logger.error("[Nerf 3] EventBusKafka indisponible : %s", exc)
                return {
                    "status": "error",
                    "message": f"EventBusKafka indisponible : {exc}",
                }

            # Topics
            source_topics = _resolve_kafka_topics()
            EventBusBridge.KAFKA_TOPICS = set(source_topics)
            self._active_topics = set(source_topics)

            # Async bus
            try:
                from event_bus_client import event_bus
                self._async_bus = event_bus
            except Exception as exc:
                logger.warning("[Nerf 3] EventBusClient indisponible : %s", exc)
                self._async_bus = None

            # Executor
            self._async_executor = (
                concurrent.futures.ThreadPoolExecutor(
                    max_workers=_MAX_ASYNC_WORKERS,
                    thread_name_prefix="bek-bridge",
                )
            )

            # Kafka -> Async
            kafka_subscribers_registered = 0
            if self._async_bus is not None:
                for topic in sorted(self._active_topics):
                    try:
                        self._kafka_bus.subscribe(
                            topic,
                            self._make_kafka_to_async_callback(topic),
                        )
                        kafka_subscribers_registered += 1
                    except Exception as exc:
                        logger.warning(
                            "[Nerf 3] Subscribe Kafka[%s] échoué : %s",
                            topic, exc,
                        )

            # ★ v18.7 — Async -> Kafka DÉSACTIVÉ (boucle infinie)
            # Le pont Async→Kafka provoquait une boucle infinie sur
            # 'skills-index' car asyncio.run() dans _publish_async_safely
            # crée une nouvelle event loop qui perd le bridge_id.
            async_subscribers_registered = 0
            logger.info(
                "🔇 [Nerf 3] Pont Async→Kafka DÉSACTIVÉ (anti-boucle v18.7)"
            )

            # MODE
            if async_subscribers_registered > 0:
                self._mode = "bidirectional"
            else:
                self._mode = "unidirectional"

            self._activated = True

            logger.info(
                "🌉 [Nerf 3] EventBus activé | mode=%s | "
                "Kafka→Async=%d | Async→Kafka=%d",
                self._mode,
                kafka_subscribers_registered,
                async_subscribers_registered,
            )

            return {
                "status": "ok",
                "mode": self._mode,
                "kafka_to_async_topics": kafka_subscribers_registered,
                "async_to_kafka_topics": async_subscribers_registered,
                "async_available": self._async_bus is not None,
                "topics": sorted(self._active_topics),
                "max_workers": _MAX_ASYNC_WORKERS,
                "bridge_id": self._bridge_id,
                "note": "Async→Kafka disabled (anti-loop v18.7)",
            }

    # --------------------------------------------------------------------------
    # SCHEDULING COROUTINE
    # --------------------------------------------------------------------------

    @staticmethod
    def _schedule_awaitable(awaitable: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(awaitable)
            return
        except RuntimeError:
            pass

        def _runner() -> None:
            try:
                asyncio.run(awaitable)
            except Exception as exc:
                logger.debug(
                    "[Nerf 3] Coroutine subscribe échouée : %s", exc,
                )

        thread = threading.Thread(
            target=_runner,
            name="bek-eventbus-async-subscribe",
            daemon=True,
        )
        thread.start()

    # --------------------------------------------------------------------------
    # KAFKA -> ASYNC
    # --------------------------------------------------------------------------

    def _make_kafka_to_async_callback(self, topic: str):
        def _callback(event: Dict[str, Any]) -> None:
            try:
                payload = self._extract_payload(event)
                correlation_id = self._extract_correlation_id(event, payload)
                timestamp_ms = self._extract_timestamp_ms(event, payload)

                source_bridge_id = str(
                    payload.get("_bridge_id")
                    or event.get("_bridge_id")
                    or ""
                )

                if source_bridge_id == self._bridge_id:
                    return

                key = self._make_key(
                    topic, correlation_id, timestamp_ms, source_bridge_id,
                )

                if not self._mark_and_check(key):
                    return

                if self._async_bus is None or self._async_executor is None:
                    self._increment_stat("dropped_count")
                    return

                forward_payload = dict(payload)
                forward_payload.setdefault("correlation_id", correlation_id)
                forward_payload["_bridge_id"] = self._bridge_id
                forward_payload["_bridged_from"] = "kafka"
                forward_payload["_bridge_key"] = key

                try:
                    self._async_executor.submit(
                        self._publish_async_safely,
                        topic,
                        forward_payload,
                    )
                except RuntimeError:
                    self._increment_stat("dropped_count")

            except Exception as exc:
                self._increment_stat("error_count")
                logger.debug("[Nerf 3] Kafka→Async erreur : %s", exc)

        return _callback

    # --------------------------------------------------------------------------
    # ASYNC -> KAFKA (désactivé en v18.7, gardé pour compat)
    # --------------------------------------------------------------------------

    def _make_async_to_kafka_callback(self, topic: str):
        async def _callback(message: Dict[str, Any]) -> None:
            # ★ v18.7 : callback désactivé pour éviter la boucle infinie
            return
        return _callback

    # --------------------------------------------------------------------------
    # PUBLICATION ASYNC
    # --------------------------------------------------------------------------

    def _publish_async_safely(
        self,
        topic: str,
        payload: Dict[str, Any],
    ) -> None:
        try:
            if self._async_bus is None:
                return

            coroutine = self._async_bus.publish(topic, payload)

            asyncio.run(
                asyncio.wait_for(
                    coroutine,
                    timeout=_BRIDGE_TIMEOUT_SEC,
                )
            )
            self._increment_stat("kafka_to_async_count")

        except asyncio.TimeoutError:
            self._increment_stat("error_count")
            logger.debug(
                "[Nerf 3] Async publish timeout : %.1fs",
                _BRIDGE_TIMEOUT_SEC,
            )
        except Exception as exc:
            self._increment_stat("error_count")
            logger.debug("[Nerf 3] Async publish échoué : %s", exc)

    # --------------------------------------------------------------------------
    # API UNIFIÉE
    # --------------------------------------------------------------------------

    def publish_unified(
        self,
        topic: str,
        payload: Dict[str, Any],
    ) -> str:
        if not isinstance(payload, dict):
            payload = {}

        correlation_id = str(payload.get("correlation_id") or "")

        # Kafka
        try:
            if self._kafka_bus is not None:
                result = self._kafka_bus.publish(topic, payload)
                if result:
                    correlation_id = str(result)
        except Exception as exc:
            self._increment_stat("error_count")
            logger.debug("[Nerf 3] Kafka publish échoué : %s", exc)

        # Async
        if (
            self._async_bus is not None
            and self._async_executor is not None
        ):
            try:
                forward_payload = dict(payload)
                if correlation_id:
                    forward_payload["correlation_id"] = correlation_id

                forward_payload["_bridge_id"] = self._bridge_id
                forward_payload["_bridged_from"] = "unified"

                self._async_executor.submit(
                    self._publish_async_safely,
                    topic,
                    forward_payload,
                )
            except RuntimeError:
                self._increment_stat("dropped_count")
            except Exception as exc:
                self._increment_stat("error_count")
                logger.debug(
                    "[Nerf 3] Async unified publish échoué : %s", exc,
                )

        return correlation_id

    # --------------------------------------------------------------------------
    # STATUS
    # --------------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._stats_lock:
            stats = dict(self._stats)

        with self._processed_lock:
            processed_count = len(self._processed_keys_set)

        return {
            "activated": self._activated,
            "mode": self._mode,
            "kafka_available": self._kafka_bus is not None,
            "async_available": self._async_bus is not None,
            "active_topics": sorted(self._active_topics),
            "processed_keys_count": processed_count,
            "max_processed_keys": _MAX_PROCESSED_IDS,
            "max_async_workers": _MAX_ASYNC_WORKERS,
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
                    self._async_executor.shutdown(
                        wait=False,
                        cancel_futures=True,
                    )
                except Exception:
                    pass
                self._async_executor = None

            self._activated = False
            logger.info("🌉 [Nerf 3] EventBus bridge arrêté")


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
        logger.warning(
            "[Nerf 3] Désactivé via BEK_ENABLE_EVENT_BUS_NERVES=false"
        )
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_EVENT_BUS_NERVES=false",
        }

    try:
        bridge = get_event_bus_bridge()
        result = bridge.activate()
        logger.info("✅ [Nerf 3] Activation : %s", result.get("status"))
        return result
    except Exception as exc:
        logger.error("[Nerf 3] Activation échouée : %s", exc)
        return {"status": "error", "message": str(exc)}


# ------------------------------------------------------------------------------
# HELPER PUBLIC
# ------------------------------------------------------------------------------

def publish_event_unified(
    topic: str,
    payload: Dict[str, Any],
) -> str:
    try:
        bridge = get_event_bus_bridge()
        if not bridge._activated:
            bridge.activate()
        return bridge.publish_unified(topic, payload)
    except Exception as exc:
        logger.debug(
            "[Nerf 3] publish_event_unified échoué : %s", exc,
        )
        return ""


# ------------------------------------------------------------------------------
# TEST DIRECT
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    result = activate_event_bus_nerves()
    print("Résultat activation Nerf 3 :", result)

    bridge = get_event_bus_bridge()
    print("Statut bridge :", bridge.get_status())

    corr_id = publish_event_unified(
        "web-cleaned",
        {"query": "test", "source": "manual"},
    )
    print("Publication unifiée, correlation_id :", corr_id)

    time.sleep(0.5)
    print("Statut après publication :", bridge.get_status())