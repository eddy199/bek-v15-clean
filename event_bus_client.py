# -*- coding: utf-8 -*-
"""event_bus_client.py

Client EventBus async unifié BEK-v16.

Backends :
  • Redis Streams (redis-py SYNC + asyncio.to_thread) → production, persistant
  • Mock in-memory                                    → dev local sans Redis

CORRECTIF C6.1-bis (2026-09-22) :
  - Protection contre "cannot schedule new futures after interpreter shutdown"
  - Flag global _SHUTTING_DOWN : stoppe toute publication pendant l'arrêt
  - Méthode shutdown_event_bus_sync() pour scripts/CLI
  - Fermeture propre du client sync Redis

★ v18.10 (2026-10-06) — ANTI-BOUCLE GLOBALE :
  - Dédup GLOBALE par (topic, correlation_id) dans publish()
  - Empêche toute boucle infinie, quelle que soit la source
  - Fenêtre configurable via BEK_EVENTBUS_DEDUP_WINDOW_SEC (défaut: 10s)
  - Thread-safe : lock dédié + cache borné
  - Log DEBUG si skip pour ne pas spammer
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
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


# ==============================================================================
# ★ v18.10 — ANTI-BOUCLE GLOBALE (DÉDUP)
# ==============================================================================
# Toute publication avec un (topic, correlation_id) déjà vu dans les N
# dernières secondes est SILENCIEUSEMENT ignorée.
#
# Cette dédup est la DERNIÈRE LIGNE DE DÉFENSE contre les boucles infinies,
# qu'elles viennent du bridge, d'un subscriber qui re-publie, ou d'un bug.
# ==============================================================================

_GLOBAL_DEDUP_CACHE: Dict[str, float] = {}
_GLOBAL_DEDUP_LOCK = threading.Lock()

# Fenêtre de dédup (configurable)
try:
    _GLOBAL_DEDUP_WINDOW_SEC = float(
        os.getenv("BEK_EVENTBUS_DEDUP_WINDOW_SEC", "10.0")
    )
except (TypeError, ValueError):
    _GLOBAL_DEDUP_WINDOW_SEC = 10.0

# Taille maximale du cache (bornée pour éviter la fuite mémoire)
try:
    _GLOBAL_DEDUP_MAX_ENTRIES = int(
        os.getenv("BEK_EVENTBUS_DEDUP_MAX_ENTRIES", "5000")
    )
except (TypeError, ValueError):
    _GLOBAL_DEDUP_MAX_ENTRIES = 5000

# Stats de dédup (pour debug/monitoring)
_GLOBAL_DEDUP_STATS = {
    "total_checks": 0,
    "skipped_count": 0,
}


def _check_and_mark_duplicate(topic: str, correlation_id: str) -> bool:
    """
    ★ v18.10 — Vérifie si (topic, correlation_id) a déjà été publié
    dans la fenêtre de dédup.

    Returns:
        True si c'est un duplicata (à skipper)
        False si c'est une première publication (à autoriser)
    """
    if not correlation_id:
        return False

    key = f"{topic}|{correlation_id}"
    now = time.time()

    with _GLOBAL_DEDUP_LOCK:
        _GLOBAL_DEDUP_STATS["total_checks"] += 1

        last = _GLOBAL_DEDUP_CACHE.get(key, 0.0)
        if now - last < _GLOBAL_DEDUP_WINDOW_SEC:
            _GLOBAL_DEDUP_STATS["skipped_count"] += 1
            return True

        _GLOBAL_DEDUP_CACHE[key] = now

        # Nettoyage si le cache devient trop gros
        if len(_GLOBAL_DEDUP_CACHE) > _GLOBAL_DEDUP_MAX_ENTRIES:
            cutoff = now - _GLOBAL_DEDUP_WINDOW_SEC
            expired = [
                k for k, v in _GLOBAL_DEDUP_CACHE.items() if v < cutoff
            ]
            for k in expired:
                del _GLOBAL_DEDUP_CACHE[k]

        return False


def get_dedup_stats() -> Dict[str, Any]:
    """★ v18.10 — Retourne les stats de dédup (pour health check)."""
    with _GLOBAL_DEDUP_LOCK:
        return {
            "window_sec": _GLOBAL_DEDUP_WINDOW_SEC,
            "max_entries": _GLOBAL_DEDUP_MAX_ENTRIES,
            "cache_size": len(_GLOBAL_DEDUP_CACHE),
            "total_checks": _GLOBAL_DEDUP_STATS["total_checks"],
            "skipped_count": _GLOBAL_DEDUP_STATS["skipped_count"],
        }


# ==============================================================================
# ÉTAT GLOBAL SHUTDOWN (C6.1-bis)
# ==============================================================================
_SHUTTING_DOWN = False


def is_shutting_down() -> bool:
    """Indique si le client est en cours d'arrêt."""
    return _SHUTTING_DOWN


def _mark_shutting_down() -> None:
    """Marque le client en arrêt (idempotent)."""
    global _SHUTTING_DOWN
    if not _SHUTTING_DOWN:
        _SHUTTING_DOWN = True
        logger.debug("[EventBusClient] Mode shutdown activé — publications bloquées")


def _log(event: str, **fields: Any) -> None:
    """Log structuré — silencieux pendant shutdown."""
    if _SHUTTING_DOWN and event in ("publish_failure", "publish_giveup"):
        return
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
        if _SHUTTING_DOWN:
            return
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

    async def connect(self) -> None:
        ok = await asyncio.to_thread(self._sync_ping)
        if not ok:
            raise RuntimeError("Ping Redis échoué")

    async def reset(self) -> None:
        self._sync_client = None

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        if _SHUTTING_DOWN:
            return
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
        while self._running and not _SHUTTING_DOWN:
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
                if _SHUTTING_DOWN:
                    break
                logger.error("[EventBusClient] boucle %s erreur : %s", topic, exc)
                try:
                    await asyncio.sleep(2)
                except asyncio.CancelledError:
                    break

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
        # Fermer le client sync Redis si possible
        try:
            if self._sync_client is not None:
                self._sync_client.close()
        except Exception:
            pass
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
        if _SHUTTING_DOWN:
            return
        try:
            await self._bus.connect()
        except Exception as exc:
            logger.debug("[EventBusClient] connect échoué : %s", exc)
            raise
        if hasattr(self._bus, "_start_pending_dispatchers"):
            await self._bus._start_pending_dispatchers()

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """
        ★ v18.10 — Publication avec dédup GLOBALE anti-boucle.

        Avant toute opération, on vérifie si (topic, correlation_id) a déjà
        été publié récemment. Si oui → skip silencieux.
        """
        # C6.1-bis : ignorer si shutdown
        if _SHUTTING_DOWN:
            return

        # ★ v18.10 — ANTI-BOUCLE : dédup globale
        correlation_id = str(message.get("correlation_id") or "")
        if _check_and_mark_duplicate(topic, correlation_id):
            logger.debug(
                "[EventBusClient] Dedup skip | topic=%s | corr=%s",
                topic, correlation_id[:20],
            )
            return

        try:
            await self._ensure_connected()
        except Exception:
            pass

        max_attempts = 3
        delay = 0.5
        attempt = 0

        while attempt < max_attempts:
            if _SHUTTING_DOWN:
                return
            try:
                await self._bus.publish(topic, message)
                return
            except Exception as exc:
                attempt += 1
                err_str = str(exc).lower()

                # Détection shutdown → on coupe immédiatement
                if "interpreter shutdown" in err_str:
                    _mark_shutting_down()
                    return

                _log("publish_failure", mode=self._mode, topic=topic,
                     attempt=attempt, error=str(exc))
                if attempt >= max_attempts:
                    _log("publish_giveup", mode=self._mode, topic=topic, error=str(exc))
                    return  # C6.1-bis : pas de raise, on abandonne silencieusement
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    return
                delay *= 2

    def subscribe(self, topic: str, callback: AsyncCallback) -> None:
        if _SHUTTING_DOWN:
            return
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
        _mark_shutting_down()
        if hasattr(self._bus, "close"):
            try:
                await self._bus.close()
            except Exception:
                pass

    @property
    def mode(self) -> str:
        return self._mode


# ==============================================================================
# Singleton
# ==============================================================================
event_bus = EventBusClient()


# ==============================================================================
# SHUTDOWN SYNCHRONE (C6.1-bis)
# ==============================================================================
def shutdown_event_bus_sync() -> None:
    """
    Arrête proprement l'EventBus depuis un contexte SYNCHRONE.

    À appeler en fin de script/test/CLI pour éviter le spam de :
        "cannot schedule new futures after interpreter shutdown"

    Ne lève JAMAIS d'exception.
    """
    _mark_shutting_down()

    # 1. Marquer le backend comme arrêté
    try:
        if hasattr(event_bus, "_bus") and hasattr(event_bus._bus, "_running"):
            event_bus._bus._running = False
    except Exception:
        pass

    # 2. Fermer le client sync Redis directement
    try:
        if hasattr(event_bus, "_bus") and hasattr(event_bus._bus, "_sync_client"):
            sync_client = event_bus._bus._sync_client
            if sync_client is not None:
                try:
                    sync_client.close()
                except Exception:
                    pass
                event_bus._bus._sync_client = None
    except Exception:
        pass

    # 3. Si un event loop est actif, tenter une fermeture async rapide
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(event_bus.close())
    except RuntimeError:
        # Pas de loop actif → rien à faire de plus
        pass
    except Exception:
        pass