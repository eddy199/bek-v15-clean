# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BekTranslator (Unité de Traduction)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-CORE-v1.0
# 📄 Doc : docs/BEK_CPU.md
# 🎯 Rôle : Traduire les abréviations BEK en code Python exécutable
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, Optional

from .registry import BekRegistry

logger = logging.getLogger("bek.core.translator")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BEK_TRANSLATOR_VERSION = "1.0.0"


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekTranslator:
    """
    Unité de traduction BEK.

    Traduit une abréviation (ex: "BEK-REX") en appel Python concret.

    Usage :
        translator = BekTranslator()
        result = translator.translate("BEK-REX", "route", query="test")
    """

    def __init__(self, registry: Optional[BekRegistry] = None):
        """
        Initialise le traducteur.

        Args:
            registry: Instance BekRegistry (créée si None)
        """
        self.registry = registry or BekRegistry()
        self._module_cache: Dict[str, Any] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # TRADUCTION
    # ──────────────────────────────────────────────────────────────────────────

    def translate(
        self,
        abreviation: str,
        function: str,
        **kwargs: Any,
    ) -> Any:
        """
        Traduit et exécute une abréviation BEK.

        Args:
            abreviation: Nom de la brique (ex: "BEK-REX")
            function: Nom de la fonction (ex: "route")
            **kwargs: Paramètres de la fonction

        Returns:
            Résultat de la fonction

        Raises:
            ValueError: Si la brique ou la fonction n'existe pas
            ImportError: Si le module ne peut pas être importé
        """
        # 1. Vérifier que la brique existe
        if not self.registry.exists(abreviation):
            raise ValueError(
                f"BEK-Translator : abréviation inconnue '{abreviation}'. "
                f"Disponibles : {self.registry.list_all()}"
            )

        # 2. Récupérer le module
        module_name = self.registry.get_module(abreviation)
        if not module_name:
            raise ValueError(
                f"BEK-Translator : module introuvable pour '{abreviation}'"
            )

        # 3. Importer le module (avec cache)
        module = self._import_module(module_name)

        # 4. Vérifier que la fonction existe
        if not hasattr(module, function):
            available = [n for n in dir(module) if not n.startswith("_")]
            raise ValueError(
                f"BEK-Translator : fonction '{function}' introuvable dans "
                f"'{module_name}'. Disponibles : {available[:10]}"
            )

        func = getattr(module, function)

        # 5. Vérifier les paramètres requis
        self._validate_params(abreviation, function, kwargs)

        # 6. Exécuter
        logger.debug(
            "BekTranslator : %s.%s(%s)",
            abreviation,
            function,
            ", ".join(f"{k}={v!r}" for k, v in list(kwargs.items())[:3]),
        )

        try:
            return func(**kwargs)
        except Exception as exc:
            logger.error(
                "BekTranslator : erreur exécution %s.%s : %s",
                abreviation,
                function,
                exc,
            )
            raise

    def _import_module(self, module_name: str) -> Any:
        """Importe un module Python avec cache."""
        if module_name in self._module_cache:
            return self._module_cache[module_name]

        try:
            module = importlib.import_module(module_name)
            self._module_cache[module_name] = module
            return module
        except ImportError as exc:
            raise ImportError(
                f"BEK-Translator : impossible d'importer '{module_name}' : {exc}"
            ) from exc

    def _validate_params(
        self,
        abreviation: str,
        function: str,
        kwargs: Dict[str, Any],
    ) -> None:
        """Vérifie que les paramètres requis sont présents."""
        func_meta = self.registry.get_function(abreviation, function)
        if not func_meta:
            return

        required = func_meta.get("params", [])
        for param in required:
            if param not in kwargs:
                raise ValueError(
                    f"BEK-Translator : paramètre '{param}' requis pour "
                    f"'{abreviation}.{function}'"
                )

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def can_translate(self, abreviation: str, function: str) -> bool:
        """Vérifie si une traduction est possible."""
        if not self.registry.exists(abreviation):
            return False
        module_name = self.registry.get_module(abreviation)
        if not module_name:
            return False
        try:
            module = self._import_module(module_name)
            return hasattr(module, function)
        except Exception:
            return False

    def list_translatable(self) -> Dict[str, list]:
        """Liste toutes les briques et leurs fonctions."""
        result = {}
        for abrev in self.registry.list_all():
            result[abrev] = self.registry.list_functions(abrev)
        return result

    def describe(self, abreviation: str) -> Optional[Dict[str, Any]]:
        """Retourne une description complète d'une brique."""
        brique = self.registry.get(abreviation)
        if not brique:
            return None

        return {
            "abreviation": abreviation,
            "nom_complet": brique.get("nom_complet"),
            "version": brique.get("version"),
            "module": brique.get("module"),
            "brevet": brique.get("brevet"),
            "functions": self.registry.list_functions(abreviation),
            "dependencies": self.registry.get_dependencies(abreviation),
            "status": brique.get("status"),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # REPRÉSENTATION
    # ──────────────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        nb = len(self.registry.list_all())
        return f"<BekTranslator briques={nb} cached_modules={len(self._module_cache)}>"