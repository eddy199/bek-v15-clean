# -*- coding: utf-8 -*-
"""event_bus_client.py

A lightweight asynchronous event‑bus wrapper that works out‑of‑the‑box with an
in‑memory mock implementation and can fall back to a real broker when the
environment variable ``USE_REAL_BUS`` is set.  It provides:

* ``publish`` – async, with up to three retries and exponential back‑off.
* ``subscribe`` – registers an async callback for a topic.
* Structured JSON logging (single‑encoding) using the project's ``core.logger``
  helper when available, otherwise a minimal fallback logger.

The module is deliberately platform‑agnostic (Windows / Linux) and enforces UTF‑8
encoding.
"""

import os
import asyncio
import json
import logging
from typing import Callable, Awaitable, Dict, Any

# ---------------------------------------------------------------------------
# Logger configuration – ensure ``logger`` is always a ``logging.Logger``
# ---------------------------------------------------------------------------
try:
    # ``setup_json_logging`` configures handlers globally and returns ``None``.
    from core.logger import setup_json_logging  # type: ignore

    # Initialise the global JSON logger (expects a log level integer).
    setup_json_logging(level=logging.INFO)
    logger = logging.getLogger(__name__)
except Exception:
    # Fallback to a simple logger that emits raw JSON strings.
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# In‑memory mock bus (fallback when no real broker is configured)
# ---------------------------------------------------------------------------
class _InMemoryBus:
    """Very simple async pub/sub bus kept in process memory.

    Topics are plain strings; each topic maps to a list of async callbacks that
    receive the published message (a ``dict``).  This implementation is sufficient
    for unit tests and local development.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, list[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """Deliver *message* to every callback registered for *topic*."""
        logger.info(
            json.dumps(
                {
                    "event": "publish",
                    "mode": "mock",
                    "topic": topic,
                    "message": message,
                }
            )
        )
        for callback in self._subscribers.get(topic, []):
            try:
                await callback(message)
            except Exception as exc:  # pragma: no cover – defensive
                logger.error(
                    json.dumps(
                        {
                            "event": "callback_error",
                            "topic": topic,
                            "error": str(exc),
                        }
                    )
                )

    def subscribe(
        self, topic: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Register *callback* for *topic*.

        ``callback`` must be an ``async def`` coroutine accepting a single ``dict``.
        """
        self._subscribers.setdefault(topic, []).append(callback)
        logger.info(
            json.dumps(
                {
                    "event": "subscribe",
                    "mode": "mock",
                    "topic": topic,
                    "callback": getattr(callback, "__name__", repr(callback)),
                }
            )
        )

# ---------------------------------------------------------------------------
# Stub for a real external broker (e.g., NATS, Kafka, RabbitMQ)
# ---------------------------------------------------------------------------
class _RealBus:
    """Placeholder for a production‑grade broker client.

    Replace the ``NotImplementedError`` sections with the actual client code.
    """

    def __init__(self) -> None:
        # Initialise the real connection here.  Raising forces the fallback.
        raise NotImplementedError("Real bus client not implemented in this stub.")

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError

    def subscribe(
        self, topic: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:  # pragma: no cover
        raise NotImplementedError

# ---------------------------------------------------------------------------
# Unified EventBus client
# ---------------------------------------------------------------------------
class EventBusClient:
    """Unified client that automatically selects the appropriate bus implementation.

    * ``publish`` – async, retries up to three times with exponential back‑off.
    * ``subscribe`` – registers an async callback for a topic.
    """

    def __init__(self) -> None:
        use_real = os.getenv("USE_REAL_BUS", "false").lower() in {"1", "true", "yes"}
        if use_real:
            try:
                self._bus = _RealBus()
                self._mode = "real"
            except Exception as exc:  # pragma: no cover – fallback path
                logger.error(
                    json.dumps({"event": "real_bus_init_failure", "error": str(exc)})
                )
                logger.info("Falling back to in‑memory mock bus.")
                self._bus = _InMemoryBus()
                self._mode = "mock"
        else:
            self._bus = _InMemoryBus()
            self._mode = "mock"

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """Publish *message* on *topic* with retry & exponential back‑off.

        Retries: max 3 attempts, initial delay 0.5 s, back‑off factor 2.
        """
        max_attempts = 3
        delay = 0.5  # seconds
        attempt = 0

        while attempt < max_attempts:
            try:
                await self._bus.publish(topic, message)
                logger.info(
                    json.dumps(
                        {
                            "event": "publish_success",
                            "mode": self._mode,
                            "topic": topic,
                            "attempt": attempt + 1,
                        }
                    )
                )
                return
            except Exception as exc:
                attempt += 1
                logger.warning(
                    json.dumps(
                        {
                            "event": "publish_failure",
                            "mode": self._mode,
                            "topic": topic,
                            "attempt": attempt,
                            "error": str(exc),
                        }
                    )
                )
                if attempt >= max_attempts:
                    logger.error(
                        json.dumps(
                            {
                                "event": "publish_giveup",
                                "mode": self._mode,
                                "topic": topic,
                                "error": str(exc),
                            }
                        )
                    )
                    raise
                await asyncio.sleep(delay)
                delay *= 2  # exponential back‑off

    def subscribe(
        self, topic: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Register *callback* for *topic* (callback must be async)."""
        self._bus.subscribe(topic, callback)
        logger.info(
            json.dumps(
                {
                    "event": "subscribe_registered",
                    "mode": self._mode,
                    "topic": topic,
                    "callback": getattr(callback, "__name__", repr(callback)),
                }
            )
        )

# ---------------------------------------------------------------------------
# Optional singleton for convenient import elsewhere in the codebase
# ---------------------------------------------------------------------------
event_bus = EventBusClient()
