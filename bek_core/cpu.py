# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BekCPU (CPU Logique Virtuel)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-CPU-v1.0
# 📄 Doc : docs/BEK_CPU.md
# 🎯 Rôle : Point d'entrée unique pour exécuter les briques BEK
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .registry import BekRegistry
from .translator import BekTranslator

logger = logging.getLogger("bek.core.cpu")


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekCPU:
    """
    CPU Logique Virtuel BEK.

    Point d'entrée unique pour exécuter les briques BEK.

    Usage :
        BekCPU.execute("BEK-REX", "route", query="Analyse Bitcoin")
        BekCPU.list()
        BekCPU.doc("BEK-REX")
    """

    _registry: Optional[BekRegistry] = None
    _translator: Optional[BekTranslator] = None

    # ──────────────────────────────────────────────────────────────────────────
    # INITIALISATION (SINGLETON)
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def _get_translator(cls) -> BekTranslator:
        """Retourne le translator (créé à la demande)."""
        if cls._translator is None:
            cls._registry = BekRegistry()
            cls._translator = BekTranslator(cls._registry)
        return cls._translator

    @classmethod
    def reload(cls) -> None:
        """Recharge le registre depuis le disque."""
        cls._registry = None
        cls._translator = None
        cls._get_translator()
        logger.info("BekCPU rechargé")

    # ──────────────────────────────────────────────────────────────────────────
    # API PUBLIQUE
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def execute(
        cls,
        abreviation: str,
        function: str,
        **kwargs: Any,
    ) -> Any:
        """
        Exécute une instruction BEK.

        Args:
            abreviation: Nom de la brique (ex: "BEK-REX")
            function: Nom de la fonction (ex: "route")
            **kwargs: Paramètres

        Returns:
            Résultat de la fonction

        Raises:
            ValueError: Si la brique ou la fonction n'existe pas
        """
        translator = cls._get_translator()
        t0 = time.monotonic()

        logger.debug(
            "BekCPU.execute : %s.%s",
            abreviation,
            function,
        )

        try:
            result = translator.translate(abreviation, function, **kwargs)
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.debug(
                "BekCPU.execute : %s.%s OK (%.1f ms)",
                abreviation,
                function,
                elapsed_ms,
            )
            return result
        except Exception as exc:
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.error(
                "BekCPU.execute : %s.%s ÉCHEC (%.1f ms) : %s",
                abreviation,
                function,
                elapsed_ms,
                exc,
            )
            raise

    @classmethod
    def list(cls) -> List[str]:
        """Liste toutes les briques disponibles."""
        return cls._get_translator().registry.list_all()

    @classmethod
    def list_functions(cls, abreviation: str) -> List[str]:
        """Liste les fonctions d'une brique."""
        return cls._get_translator().registry.list_functions(abreviation)

    @classmethod
    def doc(cls, abreviation: str) -> Optional[str]:
        """Retourne le chemin du brevet associé à une brique."""
        return cls._get_translator().registry.get_brevet(abreviation)

    @classmethod
    def describe(cls, abreviation: str) -> Optional[Dict[str, Any]]:
        """Retourne une description complète d'une brique."""
        return cls._get_translator().describe(abreviation)

    @classmethod
    def exists(cls, abreviation: str) -> bool:
        """Vérifie si une brique existe."""
        return cls._get_translator().registry.exists(abreviation)

    @classmethod
    def can_execute(cls, abreviation: str, function: str) -> bool:
        """Vérifie si une instruction peut être exécutée."""
        return cls._get_translator().can_translate(abreviation, function)

    @classmethod
    def validate(cls) -> Dict[str, Any]:
        """Valide le registre (cohérence, dépendances)."""
        return cls._get_translator().registry.validate()

    @classmethod
    def config(cls) -> Dict[str, Any]:
        """Retourne la configuration globale."""
        return cls._get_translator().registry.get_config()

    # ──────────────────────────────────────────────────────────────────────────
    # REPRÉSENTATION
    # ──────────────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        try:
            nb = len(cls.list()) if False else 0  # noqa
        except Exception:
            nb = 0
        return f"<BekCPU briques={nb}>"