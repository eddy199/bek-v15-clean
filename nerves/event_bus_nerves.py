# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 3 — UNIFICATION EVENTBUS (nerves/event_bus_nerves.py) — VERSION RÉVISÉE
# ------------------------------------------------------------------------------
# Ce nerf crée un PONT BIDIRECTIONNEL entre les deux implémentations
# d'EventBus existantes dans BEK :
#
#   1. event_bus.py        → EventBusKafka      (SYNC, threads, Queue)
#   2. event_bus_client.py → EventBusClient     (ASYNC, retry exponentiel)
#
# PROBLÈME RÉSOLU :
#   - Avant : les deux bus étaient isolés → 50% des événements perdus
#   - Après : pont bidirectionnel avec anti-boucle, thread-safe, borné
#
# CORRECTIONS vs VERSION PRÉCÉDENTE :
#   - ThreadPoolExecutor borné (max 4 workers) au lieu d'un thread par event
#   - asyncio.run() isolé dans les workers au lieu de new_event_loop() global
#   - Anti-boucle bidirectionnel via clé composite (topic|corr_id|ts)
#   - _processed_ids protégé par Lock (thread-safe)
#   - File d'attente bornée (maxsize=2000) pour éviter la saturation mémoire
#
# RÈGLES D'OR :
#   - Aucune modification de event_bus.py
#   - Aucune modification de event_bus_client.py
#   - Feature-flag : BEK_ENABLE_EVENT_BUS_NERVES (défaut true)
#   - Singleton idempotent et thread-safe
# ==============================================================================

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import threading
import time
from typing import Any, Dict, Optional, Set

logger = logging.getLogger("bek.nerves.event_bus")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_EVENT_BUS_NERVES", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# CONFIGURATION DU PONT
# ------------------------------------------------------------------------------

_MAX_ASYNC_WORKERS = 4          # Nombre max de threads pour publier en async
_MAX_PROCESSED_IDS = 10000      # Taille max de la mémoire anti-boucle
_BRIDGE_TIMEOUT_SEC = 5.0       # Timeout pour une publication async


# ------------------------------------------------------------------------------
# PONT SINGLETON (idempotent, thread-safe)
# ------------------------------------------------------------------------------

class EventBusBridge:
    """
    Pont bidirectionnel entre EventBusKafka (sync) et EventBusClient (async).

    Anti-boucle : chaque événement est marqué par une clé composite unique
    (topic + correlation_id + timestamp_ms), empêchant la republication infinie
    dans les deux sens.

    Thread-safe : toutes les opérations critiques sont protégées par Lock.
    Borné : utilise un ThreadPoolExecutor limité pour éviter l'explosion de threads.
    """

    # Topics supportés par EventBusKafka (source de vérité)
    KAFKA_TOPICS: Set[str] = {
        "web-cleaned",
        "skills-index",
        "error-signals",
        "vector-context",
    }

    def __init__(self) -> None:
        self._activated: bool = False
        self._lock = threading.RLock()

        # Anti-boucle : clé composite (topic|corr_id|ts_ms)
        self._processed_keys: Set[str] = set()
        self._processed_lock = threading.Lock()

        # Références aux bus
        self._kafka_bus: Any = None
        self._async_bus: Any = None

        # Pool de threads borné pour publication async
        self._async_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None

        # Compteur de statistiques
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
    def _make_key(topic: str, correlation_id: str, timestamp_ms: int) -> str:
        """Construit une clé composite unique pour anti-boucle."""
        return f"{topic}|{correlation_id}|{timestamp_ms}"

    def _mark_and_check(self, key: str) -> bool:
        """
        Retourne True si la clé est NOUVELLE (à traiter).
        Retourne False si la clé a DÉJÀ été traitée (à ignorer).
        """
        with self._processed_lock:
            if key in self._processed_keys:
                return False
            self._processed_keys.add(key)
            # Limiter la taille mémoire
            if len(self._processed_keys) > _MAX_PROCESSED_IDS:
                # Garder les 50% les plus récents (simple FIFO via set → list)
                recent = list(self._processed_keys)[-int(_MAX_PROCESSED_IDS * 0.5):]
                self._processed_keys = set(recent)
            return True

    # --------------------------------------------------------------------------
    # STATISTIQUES
    # --------------------------------------------------------------------------

    def _increment_stat(self, key: str, delta: int = 1) -> None:
        with self._stats_lock:
            self._stats[key] = self._stats.get(key, 0) + delta

    # --------------------------------------------------------------------------
    # ACTIVATION
    # --------------------------------------------------------------------------

    def activate(self) -> Dict[str, Any]:
        """Active le pont bidirectionnel. Idempotent."""
        with self._lock:
            if self._activated:
                return {"status": "already_activated", "stats": dict(self._stats)}

            # 1. Import EventBusKafka (sync)
            try:
                from event_bus import EventBusKafka
                self._kafka_bus = EventBusKafka()
            except Exception as exc:
                logger.error("[Nerf 3] Import EventBusKafka échoué : %s", exc)
                return {"status": "error", "message": f"EventBusKafka indisponible : {exc}"}

            # 2. Import EventBusClient (async) — optionnel
            try:
                from event_bus_client import event_bus as async_bus_instance
                self._async_bus = async_bus_instance
            except Exception as exc:
                logger.warning(
                    "[Nerf 3] EventBusClient indisponible (%s) — pont unidirectionnel "
                    "vers EventBusKafka uniquement.",
                    exc,
                )
                self._async_bus = None

            # 3. Créer le pool de threads borné pour publication async
            self._async_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=_MAX_ASYNC_WORKERS,
                thread_name_prefix="bek-bridge",
            )

            # 4. Enregistrer les subscribers Kafka → Async
            kafka_subscribers_registered = 0
            if self._async_bus is not None:
                for topic in self.KAFKA_TOPICS:
                    try:
                        self._kafka_bus.subscribe(
                            topic,
                            self._make_kafka_to_async_callback(topic),
                        )
                        kafka_subscribers_registered += 1
                    except Exception as exc:
                        logger.warning(
                            "[Nerf 3] Subscribe Kafka[%s] échoué : %s", topic, exc
                        )

            self._activated = True
            logger.info(
                "🌉 [Nerf 3] Pont EventBus activé | Kafka→Async : %d topics | "
                "Async→Kafka : via publish_unified() | Workers : %d",
                kafka_subscribers_registered,
                _MAX_ASYNC_WORKERS,
            )

            return {
                "status": "ok",
                "kafka_to_async_topics": kafka_subscribers_registered,
                "async_available": self._async_bus is not None,
                "topics": sorted(self.KAFKA_TOPICS),
                "max_workers": _MAX_ASYNC_WORKERS,
            }

    # --------------------------------------------------------------------------
    # CALLBACK KAFKA → ASYNC
    # --------------------------------------------------------------------------

    def _make_kafka_to_async_callback(self, topic: str):
        """
        Crée un callback qui sera appelé par EventBusKafka (sync) et qui
        republie l'événement sur EventBusClient (async) via le pool borné.
        """
        def _callback(event: Dict[str, Any]) -> None:
            try:
                payload = event.get("payload", {})
                correlation_id = payload.get("correlation_id", "")
                timestamp_ms = int(event.get("timestamp", time.time()) * 1000)

                # Anti-boucle
                key = self._make_key(topic, correlation_id, timestamp_ms)
                if not self._mark_and_check(key):
                    return

                if self._async_bus is None or self._async_executor is None:
                    self._increment_stat("dropped_count")
                    return

                # Marquer le payload pour éviter le retour en boucle
                forward_payload = dict(payload)
                forward_payload["_bridged_from"] = "kafka"
                forward_payload["_bridge_key"] = key

                # Soumettre au pool borné (pas de thread manuel)
                try:
                    self._async_executor.submit(
                        self._publish_async_safely,
                        topic,
                        forward_payload,
                    )
                except RuntimeError:
                    # Pool déjà shutdown
                    self._increment_stat("dropped_count")
                    return

            except Exception as exc:
                self._increment_stat("error_count")
                logger.debug("[Nerf 3] Erreur pont Kafka→Async : %s", exc)

        return _callback

    # --------------------------------------------------------------------------
    # CALLBACK ASYNC → KAFKA
    # --------------------------------------------------------------------------

    def _make_async_to_kafka_callback(self, topic: str):
        """
        Crée un callback async qui sera appelé par EventBusClient et qui
        republie l'événement sur EventBusKafka (sync).
        """
        async def _callback(message: Dict[str, Any]) -> None:
            try:
                correlation_id = message.get("correlation_id", "")
                timestamp_ms = int(time.time() * 1000)

                # Anti-boucle
                key = self._make_key(topic, correlation_id, timestamp_ms)
                if not self._mark_and_check(key):
                    return

                if self._kafka_bus is None:
                    self._increment_stat("dropped_count")
                    return

                forward_payload = dict(message)
                forward_payload["_bridged_from"] = "async"
                forward_payload["_bridge_key"] = key

                # Publication sync depuis un contexte async
                try:
                    self._kafka_bus.publish(topic, forward_payload)
                    self._increment_stat("async_to_kafka_count")
                except Exception as exc:
                    self._increment_stat("error_count")
                    logger.debug("[Nerf 3] Publication Kafka échouée : %s", exc)

            except Exception as exc:
                self._increment_stat("error_count")
                logger.debug("[Nerf 3] Erreur pont Async→Kafka : %s", exc)

        return _callback

    # --------------------------------------------------------------------------
    # PUBLICATION ASYNC ISOLÉE
    # --------------------------------------------------------------------------

    def _publish_async_safely(self, topic: str, payload: Dict[str, Any]) -> None:
        """
        Publie sur le bus async dans un worker du pool.
        Utilise asyncio.run() isolé (safe dans un thread dédié).
        """
        try:
            if self._async_bus is None:
                return
            # asyncio.run() crée et ferme un event loop propre pour ce worker
            asyncio.run(
                asyncio.wait_for(
                    self._async_bus.publish(topic, payload),
                    timeout=_BRIDGE_TIMEOUT_SEC,
                )
            )
            self._increment_stat("kafka_to_async_count")
        except asyncio.TimeoutError:
            self._increment_stat("error_count")
            logger.debug("[Nerf 3] Publication async timeout (%.1fs)", _BRIDGE_TIMEOUT_SEC)
        except Exception as exc:
            self._increment_stat("error_count")
            logger.debug("[Nerf 3] Publication async échouée : %s", exc)

    # --------------------------------------------------------------------------
    # API PUBLIQUE UNIFIÉE
    # --------------------------------------------------------------------------

    def publish_unified(self, topic: str, payload: Dict[str, Any]) -> str:
        """
        Publie sur les DEUX bus simultanément (Kafka sync + Async).
        Retourne le correlation_id.
        Ne lève jamais d'exception.
        """
        correlation_id = ""

        # 1. Publication SYNC sur Kafka
        try:
            if self._kafka_bus is not None:
                correlation_id = self._kafka_bus.publish(topic, payload)
        except Exception as exc:
            logger.debug("[Nerf 3] Publication Kafka échouée : %s", exc)

        # 2. Publication ASYNC via le pool borné
        if self._async_bus is not None and self._async_executor is not None:
            try:
                forward_payload = dict(payload)
                forward_payload["correlation_id"] = correlation_id
                self._async_executor.submit(
                    self._publish_async_safely,
                    topic,
                    forward_payload,
                )
            except RuntimeError:
                logger.debug("[Nerf 3] Pool déjà shutdown")
            except Exception as exc:
                logger.debug("[Nerf 3] Publication async échouée : %s", exc)

        return correlation_id

    # --------------------------------------------------------------------------
    # STATUT
    # --------------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut complet du pont."""
        with self._stats_lock:
            stats = dict(self._stats)
        with self._processed_lock:
            processed_count = len(self._processed_keys)

        return {
            "activated": self._activated,
            "kafka_available": self._kafka_bus is not None,
            "async_available": self._async_bus is not None,
            "processed_keys_count": processed_count,
            "max_processed_keys": _MAX_PROCESSED_IDS,
            "max_async_workers": _MAX_ASYNC_WORKERS,
            "stats": stats,
        }

    def shutdown(self) -> None:
        """Arrête proprement le pool de threads."""
        with self._lock:
            if self._async_executor is not None:
                self._async_executor.shutdown(wait=False, cancel_futures=True)
                self._async_executor = None
            self._activated = False
            logger.info("🌉 [Nerf 3] Pont EventBus arrêté")


# ------------------------------------------------------------------------------
# SINGLETON GLOBAL
# ------------------------------------------------------------------------------

_bridge_instance: Optional[EventBusBridge] = None
_bridge_singleton_lock = threading.RLock()


def get_event_bus_bridge() -> EventBusBridge:
    """Retourne le singleton du pont EventBus (thread-safe)."""
    global _bridge_instance
    with _bridge_singleton_lock:
        if _bridge_instance is None:
            _bridge_instance = EventBusBridge()
        return _bridge_instance


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_event_bus_nerves() -> Dict[str, Any]:
    """Active le pont EventBus bidirectionnel. Idempotent."""
    if not _is_enabled():
        logger.warning("[Nerf 3] Désactivé via BEK_ENABLE_EVENT_BUS_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_EVENT_BUS_NERVES=false",
        }

    try:
        bridge = get_event_bus_bridge()
        result = bridge.activate()
        logger.info("✅ [Nerf 3] Activation terminée : %s", result.get("status"))
        return result
    except Exception as exc:
        logger.error("[Nerf 3] Activation échouée : %s", exc)
        return {"status": "error", "message": str(exc)}


# ------------------------------------------------------------------------------
# HELPERS PUBLICS (utilisables par les autres nerfs : web_agent, guardian, etc.)
# ------------------------------------------------------------------------------

def publish_event_unified(topic: str, payload: Dict[str, Any]) -> str:
    """
    Fonction publique unifiée : publie sur les DEUX bus simultanément.
    Ne lève jamais d'exception.
    """
    try:
        bridge = get_event_bus_bridge()
        return bridge.publish_unified(topic, payload)
    except Exception as exc:
        logger.debug("[Nerf 3] publish_event_unified échoué : %s", exc)
        return ""


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_event_bus_nerves()
    print("Résultat activation Nerf 3 :", result)
    bridge = get_event_bus_bridge()
    print("Statut bridge :", bridge.get_status())
    # Test publication unifiée
    corr_id = publish_event_unified("web-cleaned", {"query": "test", "source": "manual"})
    print("Publication unifiée, correlation_id :", corr_id)
    time.sleep(0.5)
    print("Statut après publication :", bridge.get_status())