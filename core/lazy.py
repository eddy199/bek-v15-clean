# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Lazy Loader Générique
# ------------------------------------------------------------------------------
# ★ v18.13 (2026-10-06) — Créé pour économiser la RAM sur Render Free.
#
# Utilisation :
#     from core.lazy import lazy_import, lazy_singleton
#
#     # Lazy import (module chargé au 1er accès)
#     playwright = lazy_import("playwright.async_api")
#
#     # Lazy singleton (instance créée au 1er appel)
#     def _create_headless():
#         from worker_headless import HeadlessWorker
#         return HeadlessWorker()
#     get_headless = lazy_singleton(_create_headless)
#     # Puis : worker = get_headless()
# ==============================================================================

from __future__ import annotations

import importlib
import logging
import os
import threading
from typing import Any, Callable, Optional

logger = logging.getLogger("bek.lazy")


# ------------------------------------------------------------------------------
# FEATURE FLAG GLOBAL
# ------------------------------------------------------------------------------

def is_lazy_enabled() -> bool:
    """Active le lazy loading (défaut: true)."""
    return os.getenv("BEK_LAZY_LOAD", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# LAZY IMPORT (module)
# ------------------------------------------------------------------------------

_import_cache: dict = {}
_import_lock = threading.Lock()


def lazy_import(module_name: str) -> Any:
    """Import différé d'un module Python."""
    if not is_lazy_enabled():
        return importlib.import_module(module_name)

    with _import_lock:
        if module_name in _import_cache:
            return _import_cache[module_name]

        try:
            module = importlib.import_module(module_name)
            _import_cache[module_name] = module
            logger.debug("[Lazy] Module chargé : %s", module_name)
            return module
        except ImportError as exc:
            logger.warning("[Lazy] Import échoué pour %s : %s", module_name, exc)
            _import_cache[module_name] = None
            return None


# ------------------------------------------------------------------------------
# LAZY SINGLETON (instance)
# ------------------------------------------------------------------------------

class LazySingleton:
    """Singleton thread-safe créé au premier accès."""

    def __init__(self, factory: Callable[[], Any], name: str = "unnamed"):
        self._factory = factory
        self._name = name
        self._instance: Optional[Any] = None
        self._lock = threading.Lock()
        self._created = False

    def __call__(self) -> Any:
        if self._created:
            return self._instance

        with self._lock:
            if self._created:
                return self._instance

            try:
                logger.info("[Lazy] Création instance '%s'", self._name)
                self._instance = self._factory()
                self._created = True
                logger.info("[Lazy] ✅ Instance '%s' prête", self._name)
            except Exception as exc:
                logger.error("[Lazy] Échec création '%s' : %s", self._name, exc)
                raise

        return self._instance

    @property
    def is_loaded(self) -> bool:
        return self._created

    def reset(self) -> None:
        with self._lock:
            self._instance = None
            self._created = False
            logger.info("[Lazy] Instance '%s' reset", self._name)


def lazy_singleton(factory: Callable[[], Any], name: str = "unnamed") -> LazySingleton:
    """Raccourci pour créer un LazySingleton."""
    return LazySingleton(factory, name=name)


# ------------------------------------------------------------------------------
# STATS
# ------------------------------------------------------------------------------

def lazy_stats() -> dict:
    """Retourne les statistiques du lazy loader."""
    return {
        "enabled": is_lazy_enabled(),
        "imports_loaded": list(_import_cache.keys()),
        "imports_count": len(_import_cache),
    }