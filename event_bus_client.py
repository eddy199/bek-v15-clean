# -*- coding: utf-8 -*-
"""event_bus_client.py

Client EventBus async unifié BEK-v16.

Backends :
  • Redis Streams (redis-py SYNC + asyncio.to_thread) → production, persistant
  • Mock in-memory                                    → dev local sans Redis

Approche :
    Le client Redis est SYNCHRONE (redis-py classique). Toutes les opérations
    bloquantes (XADD, XREAD, PING) sont exécutées dans un thread via
    ``asyncio.to_thread``. Cela évite TOUT problème de event loop
    (« bound to a different event loop », « Event loop is closed »).

API publique :
    await client.publish(topic, message) -> None
    client.subscribe(topic, async_callback) -> None
    client.unsubscribe(topic, async_callback) -> bool

Variables d'environnement :
    REDIS_URL           : redis://localhost:6379/0
    USE_REAL_BUS        : true | false  (auto via REDIS_URL)
    BEK_EVENTBUS_MAXLEN : 10000
    BEK_EVENTBUS_OFFSETS: .eventbus_client_offsets.json
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

# ─── Logger ────────────────────────────────────────────────────────────────
try:
    from core.logger import setup_json_logging  # type: ignore
    setup_json_logging(level=logging.INFO)
    logger = logging.getLogger(__name__)
except Exception:
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        _h = logging.StreamHandler()
        _h.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# ─── Charger env.txt ───────────────────────────────────────────────────────
try:
    from env_loader import load_env
    load_env()
except Exception:
    pass

# ─── Backend Redis sync (optionnel) ────────────────────────────────────────
try:
    import redis as _sync_redis  # type: ignore
    _REDIS_SYNC_AVAILABLE = True
except ImportError:
    _sync_redis = None  # type: ignore
    _REDIS_SYNC_AVAILABLE = False

# ─── Topics valides ────────────────────────────────────────────────────────
VALID_TOPICS = {"web-cleaned", "skills-index", "error-signals", "vector-context"}

AsyncCallback = Callable[[Dict[str, Any]], Awaitable[None]]


def _log(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    try:
        logger.info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        logger.info("%s %s", event, fields)


def _has_running_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


# ==============================================================================
# Backend 1 — Mock in-memory
# ==============================================================================
class _InMemoryBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[AsyncCallback]] = {}

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        _log("publish", mode="mock", topic=topic)
        for cb in list(self._subscribers.get(topic, [])):
            try:
                await cb(message)
            except Exception as exc:
                _log("callback_error", topic=topic, error=str(exc))

    def subscribe(self, topic: str, callback: AsyncCallback) -> None:
        self._subscribers.setdefault(topic, []).append(callback)
        _log("subscribe", mode="mock", topic=topic,
             callback=getattr(callback, "__name__", repr(callback)))

    def unsubscribe(self, topic: str, callback: AsyncCallback) -> bool:
        try:
            self._subscribers.get(topic, []).remove(callback)
            return True
        except (KeyError, ValueError):
            return False

    async def reset(self) -> None:
        pass

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        self._subscribers.clear()


# ==============================================================================
# Backend 2 — Redis Streams (SYNC + to_thread)
# ==============================================================================
class _RedisBus:
    """
    Backend Redis basé sur le client SYNC (redis-py).
    Les appels bloquants sont exécutés dans un thread via asyncio.to_thread,
    ce qui évite tout conflit avec l'event loop FastAPI.
    """

    def __init__(self, url: str, maxlen: int = 10000) -> None:
        self._url = url
        self._maxlen = maxlen
        self._sync_client: Any = None
        self._subscribers: Dict[str, List[AsyncCallback]] = {t: [] for t in VALID_TOPICS}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = True
        self._offsets_file = Path(
            os.getenv("BEK_EVENTBUS_OFFSETS", ".eventbus_client_offsets.json")
        )
        self._offsets: Dict[str, str] = self._load_offsets()

    # ------------------------------------------------------------------
    # Offsets
    # ------------------------------------------------------------------
    def _load_offsets(self) -> Dict[str, str]:
        try:
            if self._offsets_file.exists():
                return json.loads(self._offsets_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {t: "0" for t in VALID_TOPICS}

    def _save_offsets(self) -> None:
        try:
            self._offsets_file.write_text(
                json.dumps(self._offsets, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Client sync
    # ------------------------------------------------------------------
    def _get_sync_client(self) -> Any:
        if self._sync_client is None:
            if not _REDIS_SYNC_AVAILABLE:
                raise RuntimeError("redis-py (sync) non installé")
            self._sync_client = _sync_redis.Redis.from_url(
                self._url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=3,
            )
        return self._sync_client

    def _sync_ping(self) -> bool:
        return bool(self._get_sync_client().ping())

    def _sync_publish(self, topic: str, event: Dict[str, Any]) -> None:
        client = self._get_sync_client()
        client.xadd(
            topic,
            {"data": json.dumps(event, ensure_ascii=False)},
            maxlen=self._maxlen,
            approximate=True,
        )

    def _sync_xread(self, topic: str, last_id: str) -> Any:
        client = self._get_sync_client()
        return client.xread({topic: last_id}, count=100, block=2000)

    # ------------------------------------------------------------------
    # API async (to_thread pour ne pas bloquer l'event loop)
    # ------------------------------------------------------------------
    async def connect(self) -> None:
        ok = await asyncio.to_thread(self._sync_ping)
        if not ok:
            raise RuntimeError("Ping Redis échoué")

    async def reset(self) -> None:
        # On abandonne le client sync : il sera recréé au prochain appel.
        self._sync_client = None

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        if topic not in VALID_TOPICS:
            raise ValueError(f"Topic inconnu : {topic}")

        correlation_id = message.get("correlation_id") or f"corr_{os.urandom(6).hex()}"
        message["correlation_id"] = correlation_id

        event = {
            "topic": topic,
            "timestamp": time.time(),
            "correlation_id": correlation_id,
            "payload": message,
        }

        await asyncio.to_thread(self._sync_publish, topic, event)
        _log("publish_success", mode="redis", topic=topic, correlation_id=correlation_id)

    def subscribe(self, topic: str, callback: AsyncCallback) -> None:
        if topic not in VALID_TOPICS:
            logger.warning("[EventBusClient] topic inconnu : %s", topic)
            return
        self._subscribers[topic].append(callback)

        if topic not in self._tasks:
            if _has_running_loop():
                loop = asyncio.get_running_loop()
                self._tasks[topic] = loop.create_task(self._dispatch_loop(topic))
            else:
                logger.debug(
                    "[EventBusClient] subscribe sans loop — dispatch différé (%s)",
                    topic,
                )

        _log("subscribe", mode="redis", topic=topic,
             callback=getattr(callback, "__name__", repr(callback)))

    def unsubscribe(self, topic: str, callback: AsyncCallback) -> bool:
        try:
            self._subscribers.get(topic, []).remove(callback)
            return True
        except (KeyError, ValueError):
            return False

    async def _start_pending_dispatchers(self) -> None:
        if not _has_running_loop():
            return
        loop = asyncio.get_running_loop()
        for topic in list(self._subscribers.keys()):
            if topic not in self._tasks and self._subscribers[topic]:
                self._tasks[topic] = loop.create_task(self._dispatch_loop(topic))
                logger.debug(
                    "[EventBusClient] dispatcher différé démarré : %s", topic
                )

    async def _dispatch_loop(self, topic: str) -> None:
        last_id = self._offsets.get(topic, "0")
        while self._running:
            try:
                result = await asyncio.to_thread(self._sync_xread, topic, last_id)
                if not result:
                    continue
                for _stream, entries in result:
                    for entry_id, fields in entries:
                        last_id = entry_id
                        self._offsets[topic] = entry_id
                        raw = fields.get("data")
                        if not raw:
                            continue
                        try:
                            event = json.loads(raw)
                        except Exception as exc:
                            logger.warning(
                                "[EventBusClient] JSON invalide %s : %s", topic, exc
                            )
                            continue
                        payload = event.get("payload", {})
                        for cb in list(self._subscribers.get(topic, [])):
                            try:
                                await cb(payload)
                            except Exception as exc:
                                _log("callback_error", topic=topic, error=str(exc))
                self._save_offsets()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("[EventBusClient] boucle %s erreur : %s", topic, exc)
                await asyncio.sleep(2)

    async def close(self) -> None:
        self._running = False
        for task in self._tasks.values():
            try:
                task.cancel()
            except Exception:
                pass
        if self._tasks:
            try:
                await asyncio.gather(*self._tasks.values(), return_exceptions=True)
            except Exception:
                pass
        self._tasks.clear()
        self._sync_client = None


# ==============================================================================
# Client unifié
# ==============================================================================
class EventBusClient:
    def __init__(self) -> None:
        use_real_env = os.getenv("USE_REAL_BUS", "").lower() in {"1", "true", "yes"}
        redis_url = os.getenv("REDIS_URL", "").strip()
        self._redis_url = redis_url or "redis://localhost:6379/0"
        want_real = use_real_env or bool(redis_url)

        self._mode = "mock"
        self._bus: Any = None

        if want_real and _REDIS_SYNC_AVAILABLE and redis_url:
            try:
                self._bus = _RedisBus(
                    redis_url,
                    maxlen=int(os.getenv("BEK_EVENTBUS_MAXLEN", "10000")),
                )
                # Ping synchrone au démarrage (avant toute loop)
                _sync_redis.Redis.from_url(
                    redis_url, socket_timeout=3, socket_connect_timeout=3
                ).ping()
                self._mode = "redis"
                _log("bus_init", mode="redis", url=redis_url)
            except Exception as exc:
                _log("bus_init_failure", target="redis", error=str(exc))
                self._bus = _InMemoryBus()
                self._mode = "mock"
                _log("bus_init", mode="mock")
        else:
            self._bus = _InMemoryBus()
            self._mode = "mock"
            _log("bus_init", mode="mock")

    async def _ensure_connected(self) -> None:
        if self._mode != "redis":
            return
        # Ping dans un thread pour valider la connexion
        try:
            await self._bus.connect()
        except Exception as exc:
            logger.debug("[EventBusClient] connect échoué : %s", exc)
            raise
        if hasattr(self._bus, "_start_pending_dispatchers"):
            await self._bus._start_pending_dispatchers()

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        try:
            await self._ensure_connected()
        except Exception:
            pass  # On tente quand même le publish (reconnect interne)

        max_attempts = 3
        delay = 0.5
        attempt = 0

        while attempt < max_attempts:
            try:
                await self._bus.publish(topic, message)
                return
            except Exception as exc:
                attempt += 1
                _log("publish_failure", mode=self._mode, topic=topic,
                     attempt=attempt, error=str(exc))
                if attempt >= max_attempts:
                    _log("publish_giveup", mode=self._mode, topic=topic, error=str(exc))
                    raise
                await asyncio.sleep(delay)
                delay *= 2

    def subscribe(self, topic: str, callback: AsyncCallback) -> None:
        if self._mode == "redis" and _has_running_loop():
            if getattr(self._bus, "_sync_client", None) is None:
                try:
                    asyncio.get_running_loop().create_task(self._bus.connect())
                except Exception:
                    pass
        elif self._mode == "redis":
            logger.debug(
                "[EventBusClient] subscribe hors event loop — connexion différée (%s)",
                topic,
            )

        self._bus.subscribe(topic, callback)
        _log("subscribe_registered", mode=self._mode, topic=topic,
             callback=getattr(callback, "__name__", repr(callback)))

    def unsubscribe(self, topic: str, callback: AsyncCallback) -> bool:
        if hasattr(self._bus, "unsubscribe"):
            return self._bus.unsubscribe(topic, callback)
        return False

    async def close(self) -> None:
        if hasattr(self._bus, "close"):
            await self._bus.close()

    @property
    def mode(self) -> str:
        return self._mode


# ==============================================================================
# Singleton
# ==============================================================================
event_bus = EventBusClient()