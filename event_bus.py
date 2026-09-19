# ==============================================================================
# event_bus.py — PIPELINE D'INGESTION & TRAÇABILITÉ A2A (BEK-v16 + Redis Streams)
# ==============================================================================
"""
Bus événementiel durable, avec deux backends interchangeables :

  1. Redis Streams   → persistance, reprise après crash, multi-process ready
  2. Mock in-memory  → fallback automatique si Redis indisponible

API publique inchangée (zéro régression) :
    bus.publish(topic, payload) -> correlation_id
    bus.subscribe(topic, callback)
    bus.get_radar_status() -> dict
    bus.reset_radar()
    bus.stop()

Variables d'environnement :
    REDIS_URL             : ex. redis://localhost:6379/0
    BEK_EVENTBUS_MODE     : auto | redis | mock   (défaut: auto)
    BEK_EVENTBUS_MAXLEN   : taille max par stream (défaut: 10000)
    BEK_EVENTBUS_OFFSETS  : fichier d'offset persistant (défaut: .eventbus_offsets.json)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional

# --- Charger env.txt dans os.environ (REDIS_URL, BEK_EVENTBUS_MODE) --------
try:
    from env_loader import load_env
    load_env()
except Exception:
    pass

# --- Logger ----------------------------------------------------------------
logger = logging.getLogger("bek.event_bus")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)

# --- Backend optionnel : redis-py ------------------------------------------
try:
    import redis as _redis  # type: ignore
    _REDIS_LIB_AVAILABLE = True
except ImportError:
    _redis = None  # type: ignore
    _REDIS_LIB_AVAILABLE = False


# ==============================================================================
# CLASSE PRINCIPALE (nom conservé pour compatibilité descendante)
# ==============================================================================
class EventBusKafka:
    """
    Bus événementiel durable. Le nom "Kafka" est conservé pour compatibilité,
    mais le backend réel est Redis Streams (ou mock en fallback).
    """

    VALID_TOPICS = {"web-cleaned", "skills-index", "error-signals", "vector-context"}

    def __init__(self, mode: Optional[str] = None) -> None:
        self._mode: str = "mock"                    # 'redis' ou 'mock'
        self._redis_client: Any = None
        self._maxlen: int = int(os.getenv("BEK_EVENTBUS_MAXLEN", "10000"))
        self._offsets_file = Path(os.getenv("BEK_EVENTBUS_OFFSETS", ".eventbus_offsets.json"))
        self._offsets: Dict[str, str] = self._load_offsets()

        # État partagé
        self._lock = threading.RLock()
        self._running = True
        self._event_counter = 0
        self._radar_red_active = False

        # Subscribers : topic -> list[callback]
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {
            t: [] for t in self.VALID_TOPICS
        }

        # Dispatch local (mock) : queue par topic
        self._queues: Dict[str, Queue] = {t: Queue() for t in self.VALID_TOPICS}

        # Threads
        self._threads: List[threading.Thread] = []

        # Sélection du backend
        requested_mode = (mode or os.getenv("BEK_EVENTBUS_MODE", "auto")).lower().strip()
        self._init_backend(requested_mode)

    # ------------------------------------------------------------------
    # Backend
    # ------------------------------------------------------------------
    def _init_backend(self, requested: str) -> None:
        use_redis = False

        if requested == "mock":
            use_redis = False
        elif requested == "redis":
            use_redis = True
        else:  # 'auto'
            use_redis = _REDIS_LIB_AVAILABLE and bool(os.getenv("REDIS_URL", "").strip())

        if use_redis and _REDIS_LIB_AVAILABLE:
            try:
                url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                self._redis_client = _redis.Redis.from_url(
                    url, decode_responses=True, socket_timeout=5, socket_connect_timeout=3,
                )
                # Ping de démarrage
                self._redis_client.ping()
                self._mode = "redis"
                logger.info("🌐 [EventBus] Backend Redis Streams actif (%s)", url)
            except Exception as exc:
                logger.warning("⚠️ [EventBus] Redis indisponible (%s) → fallback mock", exc)
                self._redis_client = None
                self._mode = "mock"
        else:
            self._mode = "mock"
            logger.info("🧪 [EventBus] Backend mock in-memory actif")

        # Lancer les boucles de dispatch
        if self._mode == "redis":
            for topic in self.VALID_TOPICS:
                t = threading.Thread(
                    target=self._redis_dispatch_loop,
                    args=(topic,),
                    daemon=True,
                    name=f"bek-eventbus-redis-{topic}",
                )
                t.start()
                self._threads.append(t)
        else:
            t = threading.Thread(
                target=self._mock_dispatch_loop,
                daemon=True,
                name="bek-eventbus-mock",
            )
            t.start()
            self._threads.append(t)

    # ------------------------------------------------------------------
    # Offsets (persistance de la position de lecture Redis)
    # ------------------------------------------------------------------
    def _load_offsets(self) -> Dict[str, str]:
        try:
            if self._offsets_file.exists():
                return json.loads(self._offsets_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.debug("[EventBus] Lecture offsets impossible : %s", exc)
        return {t: "0" for t in self.VALID_TOPICS}

    def _save_offsets(self) -> None:
        try:
            self._offsets_file.write_text(
                json.dumps(self._offsets, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.debug("[EventBus] Écriture offsets impossible : %s", exc)

    # ------------------------------------------------------------------
    # PUBLISH
    # ------------------------------------------------------------------
    def publish(self, topic: str, payload: Dict[str, Any]) -> str:
        if topic not in self.VALID_TOPICS:
            raise ValueError(
                f"Topic inconnu : {topic}. Valides : {self.VALID_TOPICS}"
            )

        correlation_id = payload.get("correlation_id") or f"corr_{uuid.uuid4().hex[:12]}"
        payload["correlation_id"] = correlation_id

        with self._lock:
            self._event_counter += 1
            current_id = self._event_counter
            if topic == "error-signals":
                self._radar_red_active = True

        event = {
            "id": current_id,
            "topic": topic,
            "timestamp": time.time(),
            "correlation_id": correlation_id,
            "payload": payload,
            "alert_level": "RED" if topic == "error-signals" else None,
        }

        if self._mode == "redis" and self._redis_client is not None:
            try:
                self._redis_client.xadd(
                    topic,
                    {"data": json.dumps(event, ensure_ascii=False)},
                    maxlen=self._maxlen,
                    approximate=True,
                )
            except Exception as exc:
                logger.error("[EventBus] XADD échec (%s) → fallback local", exc)
                self._queues[topic].put(event)
        else:
            self._queues[topic].put(event)

        return correlation_id

    # ------------------------------------------------------------------
    # SUBSCRIBE / UNSUBSCRIBE
    # ------------------------------------------------------------------
    def subscribe(
        self,
        topic: str,
        callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        if topic not in self.VALID_TOPICS:
            logger.warning("[EventBus] subscribe topic inconnu : %s", topic)
            return
        with self._lock:
            self._subscribers[topic].append(callback)

    def unsubscribe(
        self,
        topic: str,
        callback: Callable[[Dict[str, Any]], None],
    ) -> bool:
        with self._lock:
            try:
                self._subscribers[topic].remove(callback)
                return True
            except (KeyError, ValueError):
                return False

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    def _dispatch_to_subscribers(self, topic: str, event: Dict[str, Any]) -> None:
        with self._lock:
            callbacks = list(self._subscribers.get(topic, []))

        for cb in callbacks:
            try:
                cb(event)
            except Exception as exc:
                logger.error("[EventBus] subscriber %s erreur : %s", topic, exc)

    def _mock_dispatch_loop(self) -> None:
        while self._running:
            any_event = False
            for topic, q in self._queues.items():
                try:
                    event = q.get_nowait()
                except Empty:
                    continue
                any_event = True
                self._dispatch_to_subscribers(topic, event)
                q.task_done()
            if not any_event:
                time.sleep(0.05)

    def _redis_dispatch_loop(self, topic: str) -> None:
        last_id = self._offsets.get(topic, "0")
        while self._running:
            try:
                result = self._redis_client.xread(
                    {topic: last_id},
                    count=100,
                    block=2000,  # ms
                )
                if not result:
                    continue
                for _stream_name, entries in result:
                    for entry_id, fields in entries:
                        last_id = entry_id
                        self._offsets[topic] = entry_id
                        raw = fields.get("data")
                        if not raw:
                            continue
                        try:
                            event = json.loads(raw)
                        except Exception as exc:
                            logger.warning("[EventBus] JSON invalide (%s) : %s", topic, exc)
                            continue
                        self._dispatch_to_subscribers(topic, event)
                self._save_offsets()
            except Exception as exc:
                logger.error("[EventBus] boucle Redis %s erreur : %s", topic, exc)
                time.sleep(2)

    # ------------------------------------------------------------------
    # Radar / status
    # ------------------------------------------------------------------
    def get_radar_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "radar_red": self._radar_red_active,
                "mode": "POLICE_ISOLATION" if self._radar_red_active else "NORMAL",
                "total_events_processed": self._event_counter,
                "backend": self._mode,
            }

    def reset_radar(self) -> None:
        with self._lock:
            self._radar_red_active = False

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------
    def stop(self) -> None:
        self._running = False
        for t in self._threads:
            t.join(timeout=3)
        logger.info("[EventBus] Arrêté proprement.")


# ==============================================================================
# TEST DIRECT
# ==============================================================================
if __name__ == "__main__":
    print("--- TEST EVENTBUS (Redis Streams / Mock) BEK-v16 A2A ---")
    bus = EventBusKafka()

    received = []
    bus.subscribe("skills-index", lambda e: received.append((e["payload"].get("name"), e["correlation_id"])))
    bus.subscribe("error-signals", lambda e: print(f"🚨 RADAR ROUGE [Corr:{e['correlation_id']}] : {e['payload'].get('msg')}"))

    corr = bus.publish("skills-index", {"name": "skill_crm_lead_v1", "version": "1.0"})
    time.sleep(0.4)
    print(f"skills-index reçu : {received} | corr={corr}")
    print(f"Statut nominal    : {bus.get_radar_status()}")

    bus.publish("error-signals", {"msg": "Tentative d'accès non certifié", "code": 500})
    time.sleep(0.4)
    print(f"Statut après alerte : {bus.get_radar_status()}")

    bus.stop()