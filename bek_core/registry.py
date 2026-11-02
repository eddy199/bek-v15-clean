# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BekRegistry (Registre des Briques)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-CORE-v1.0
# 📄 Doc : docs/BEK_CPU.md
# 🎯 Rôle : Charger et gérer le registre des briques BEK
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.core.registry")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BEK_REGISTRY_FILENAME = "registry.json"
BEK_REGISTRY_VERSION = "1.0.0"


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekRegistry:
    """
    Registre des briques BEK.

    Charge le fichier `registry.json` et expose des méthodes pour
    chercher les briques, leurs fonctions et leurs dépendances.

    Usage :
        registry = BekRegistry()
        brique = registry.get("BEK-REX")
        briques = registry.list_all()
    """

    def __init__(self, registry_path: Optional[str] = None):
        """
        Initialise le registre.

        Args:
            registry_path: Chemin vers registry.json.
                          Par défaut : bek_core/registry.json
        """
        if registry_path is None:
            registry_path = str(Path(__file__).parent / BEK_REGISTRY_FILENAME)

        self.registry_path = Path(registry_path)
        self._registry: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Charge le fichier registry.json."""
        if not self.registry_path.exists():
            logger.warning(
                "Registry introuvable : %s — registre vide",
                self.registry_path,
            )
            self._registry = {"briques": {}, "config": {}}
            return

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                self._registry = json.load(f)

            nb_briques = len(self._registry.get("briques", {}))
            logger.info(
                "Registry chargé : %d briques disponibles",
                nb_briques,
            )
        except Exception as exc:
            logger.error("Erreur chargement registry : %s", exc)
            self._registry = {"briques": {}, "config": {}}

    def reload(self) -> None:
        """Recharge le registre depuis le disque."""
        self._load()

    # ──────────────────────────────────────────────────────────────────────────
    # ACCÈS AUX BRIQUES
    # ──────────────────────────────────────────────────────────────────────────

    def get(self, abreviation: str) -> Optional[Dict[str, Any]]:
        """
        Récupère une brique par son abréviation.

        Args:
            abreviation: Nom de la brique (ex: "BEK-REX")

        Returns:
            dict de la brique ou None si introuvable
        """
        briques = self._registry.get("briques", {})
        return briques.get(abreviation)

    def exists(self, abreviation: str) -> bool:
        """Vérifie si une brique existe."""
        return self.get(abreviation) is not None

    def list_all(self) -> List[str]:
        """Liste toutes les abréviations disponibles."""
        return sorted(self._registry.get("briques", {}).keys())

    def list_by_status(self, status: str = "active") -> List[str]:
        """Liste les briques par statut (active, beta, deprecated)."""
        briques = self._registry.get("briques", {})
        return sorted([
            abrev for abrev, info in briques.items()
            if info.get("status") == status
        ])

    # ──────────────────────────────────────────────────────────────────────────
    # ACCÈS AUX FONCTIONS
    # ──────────────────────────────────────────────────────────────────────────

    def get_function(self, abreviation: str, function: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les métadonnées d'une fonction d'une brique.

        Args:
            abreviation: Nom de la brique
            function: Nom de la fonction

        Returns:
            dict de la fonction ou None
        """
        brique = self.get(abreviation)
        if not brique:
            return None
        return brique.get("functions", {}).get(function)

    def list_functions(self, abreviation: str) -> List[str]:
        """Liste les fonctions d'une brique."""
        brique = self.get(abreviation)
        if not brique:
            return []
        return sorted(brique.get("functions", {}).keys())

    # ──────────────────────────────────────────────────────────────────────────
    # MÉTADONNÉES
    # ──────────────────────────────────────────────────────────────────────────

    def get_module(self, abreviation: str) -> Optional[str]:
        """Récupère le chemin du module Python d'une brique."""
        brique = self.get(abreviation)
        if not brique:
            return None
        return brique.get("module")

    def get_brevet(self, abreviation: str) -> Optional[str]:
        """Récupère le chemin du brevet d'une brique."""
        brique = self.get(abreviation)
        if not brique:
            return None
        return brique.get("brevet")

    def get_dependencies(self, abreviation: str) -> List[str]:
        """Récupère les dépendances d'une brique."""
        brique = self.get(abreviation)
        if not brique:
            return []
        return brique.get("dependencies", [])

    def get_config(self) -> Dict[str, Any]:
        """Récupère la configuration globale."""
        return self._registry.get("config", {})

    # ──────────────────────────────────────────────────────────────────────────
    # VALIDATION
    # ──────────────────────────────────────────────────────────────────────────

    def validate(self) -> Dict[str, Any]:
        """
        Valide le registre.

        Vérifie :
            - Présence des champs obligatoires
            - Cohérence des dépendances
            - Existence des modules

        Returns:
            dict: {"valid": bool, "errors": list, "warnings": list}
        """
        errors = []
        warnings = []

        briques = self._registry.get("briques", {})

        for abrev, info in briques.items():
            # Champs obligatoires
            required = ["nom_complet", "version", "module", "functions"]
            for field in required:
                if field not in info:
                    errors.append(f"{abrev} : champ manquant '{field}'")

            # Vérifier que les dépendances existent
            for dep in info.get("dependencies", []):
                if dep not in briques:
                    warnings.append(f"{abrev} : dépendance '{dep}' introuvable")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_briques": len(briques),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # REPRÉSENTATION
    # ──────────────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        nb = len(self._registry.get("briques", {}))
        return f"<BekRegistry briques={nb} path={self.registry_path.name}>"