# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — UTILITAIRES ASYNC PARTAGÉS (nerves/_async_utils.py)
# ------------------------------------------------------------------------------
# Module utilitaire interne au paquet nerves/.
#
# OBJECTIF :
#   Factoriser la logique "exécuter une coroutine de manière sûre, que l'on
#   soit dans un thread OU dans un event loop déjà actif".
#
#   Cette logique était dupliquée dans :
#     - nerves/headless_nerves.py  (_run_async_safely)
#     - nerves/hermes_nerves.py    (asyncio.run brut → bug potentiel)
#
# PROBLÈME RÉSOLU :
#   - `asyncio.run()` lève RuntimeError si un event loop tourne déjà
#     (cas typique : FastAPI, uvicorn, handlers async).
#   - Chaque nerf réimplémentait sa propre version → divergence.
#
# SOLUTION :
#   - Fonction unique run_async_safely() qui :
#       1. Tente asyncio.run() si aucun loop actif (cas nominal)
#       2. Sinon délègue à un ThreadPoolExecutor isolé (thread-safe)
#       3. Applique un timeout de sécurité configurable
#
# RÈGLES D'OR :
#   - Stdlib uniquement (asyncio, concurrent.futures, logging, os, typing)
#   - Ne lève JAMAIS d'exception silencieuse : log DEBUG + retour None
#   - Utilisable depuis n'importe quel thread ou contexte async
#   - Feature-flag : BEK_ASYNC_UTILS_TIMEOUT (défaut 60 secondes)
#
# UTILISATION :
#   from nerves._async_utils import run_async_safely
#   result = run_async_safely(worker.fetch_page_content(url))
# ==============================================================================

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
from typing import Any, Awaitable, Callable, Optional, TypeVar

logger = logging.getLogger("bek.nerves.async_utils")

T = TypeVar("T")


# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------

def _default_timeout() -> float:
    """Lit le timeout par défaut depuis env.txt (BEK_ASYNC_UTILS_TIMEOUT)."""
    try:
        return float(os.getenv("BEK_ASYNC_UTILS_TIMEOUT", "60"))
    except (TypeError, ValueError):
        return 60.0


# ------------------------------------------------------------------------------
# DÉTECTION D'EVENT LOOP
# ------------------------------------------------------------------------------

def is_event_loop_running() -> bool:
    """
    Retourne True si un event loop asyncio tourne dans le thread courant.
    Ne lève jamais d'exception.
    """
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


# ------------------------------------------------------------------------------
# EXÉCUTION SÛRE D'UNE COROUTINE
# ------------------------------------------------------------------------------

def run_async_safely(
    coro: Awaitable[T],
    timeout: Optional[float] = None,
) -> Optional[T]:
    """
    Exécute une coroutine de manière sûre, que l'on soit :
      - dans un thread simple (cas nominal) → asyncio.run()
      - dans un event loop déjà actif          → ThreadPoolExecutor isolé

    Paramètres :
      - coro    : coroutine à exécuter (obligatoire)
      - timeout : timeout en secondes (défaut : BEK_ASYNC_UTILS_TIMEOUT ou 60)

    Retour :
      - Le résultat de la coroutine, ou None en cas d'échec.
      - Ne lève JAMAIS d'exception silencieuse.

    ATTENTION :
      - Si timeout est atteint, la coroutine peut continuer en arrière-plan
        (impossible d'interrompre un thread proprement en Python).
      - Préférer un timeout raisonnable (60s par défaut).
    """
    if coro is None:
        logger.debug("[async_utils] Coroutine None fournie, ignorée.")
        return None

    effective_timeout = timeout if timeout is not None else _default_timeout()

    # Cas 1 : aucun event loop actif → asyncio.run() directement (rapide)
    if not is_event_loop_running():
        try:
            return asyncio.run(
                asyncio.wait_for(coro, timeout=effective_timeout)
            )
        except asyncio.TimeoutError:
            logger.debug("[async_utils] Timeout asyncio.run (%.1fs)", effective_timeout)
            return None
        except Exception as exc:
            logger.debug("[async_utils] asyncio.run échoué : %s", exc)
            return None

    # Cas 2 : event loop actif → délégation à un thread isolé
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _run_in_isolated_loop,
                coro,
                effective_timeout,
            )
            try:
                return future.result(timeout=effective_timeout + 5.0)
            except concurrent.futures.TimeoutError:
                logger.debug(
                    "[async_utils] Timeout ThreadPoolExecutor (%.1fs)",
                    effective_timeout,
                )
                return None
    except Exception as exc:
        logger.debug("[async_utils] ThreadPoolExecutor échoué : %s", exc)
        return None


def _run_in_isolated_loop(coro: Awaitable[T], timeout: float) -> Optional[T]:
    """
    Exécute la coroutine dans un event loop isolé (thread worker).
    Utilisé en interne par run_async_safely().
    """
    try:
        return asyncio.run(
            asyncio.wait_for(coro, timeout=timeout)
        )
    except asyncio.TimeoutError:
        logger.debug("[async_utils] Timeout loop isolé (%.1fs)", timeout)
        return None
    except Exception as exc:
        logger.debug("[async_utils] Loop isolé échoué : %s", exc)
        return None


# ------------------------------------------------------------------------------
# VARIANTE : EXÉCUTION D'UNE FONCTION ASYNC PAR RÉFÉRENCE
# ------------------------------------------------------------------------------

def run_async_func_safely(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    timeout: Optional[float] = None,
    **kwargs: Any,
) -> Optional[T]:
    """
    Variante de run_async_safely() qui prend une FONCTION async + ses arguments.

    Exemple :
        result = run_async_func_safely(worker.fetch_page_content, url)

    Utile quand on ne veut pas créer la coroutine soi-même (évite les warnings
    "coroutine was never awaited" si la fonction lève avant l'exécution).
    """
    if func is None:
        logger.debug("[async_utils] Fonction async None fournie, ignorée.")
        return None
    try:
        coro = func(*args, **kwargs)
    except Exception as exc:
        logger.debug("[async_utils] Création coroutine échouée : %s", exc)
        return None
    return run_async_safely(coro, timeout=timeout)


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    async def _demo(x: int) -> int:
        await asyncio.sleep(0.1)
        return x * 2

    # Test 1 : sans event loop actif
    print("Test 1 (thread simple) :", run_async_safely(_demo(21)))
    assert run_async_safely(_demo(21)) == 42

    # Test 2 : avec event loop actif
    async def _outer():
        return run_async_safely(_demo(10))

    print("Test 2 (loop actif) :", asyncio.run(_outer()))
    assert asyncio.run(_outer()) == 20

    # Test 3 : timeout
    async def _slow():
        await asyncio.sleep(10)
        return "jamais atteint"

    print("Test 3 (timeout) :", run_async_safely(_slow(), timeout=0.5))

    # Test 4 : variante fonction
    print("Test 4 (run_async_func_safely) :", run_async_func_safely(_demo, 5))
    assert run_async_func_safely(_demo, 5) == 10

    print("✅ Tous les tests _async_utils OK")