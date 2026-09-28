# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-ECO Optimizer
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-ECO-v1.0
# 📄 Doc : docs/brevets/BREVET_ECO.md
# 🎯 Rôle : Optimisation économique + cache + limites
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-23
# ==============================================================================

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("bek.core.eco")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

# Pondération des 7 facteurs (somme = 1.0)
BEK_ECO_WEIGHTS = {
    "conformite":   0.25,
    "securite":     0.20,
    "precision":    0.20,
    "efficience":   0.15,
    "rentabilite":  0.10,
    "productivite": 0.05,
    "technologie":  0.05,
}

BEK_ECO_DEFAULT_TTL = 3600              # 1 heure
BEK_ECO_DEFAULT_DAILY_LIMIT = 50
BEK_ECO_CACHE_FILE = "data/bek_eco_cache.json"
BEK_ECO_LIMITS_FILE = "data/bek_eco_limits.json"


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekEcoOptimizer:
    """
    Optimiseur BEK-ECO.

    Prend des décisions économiques selon 7 facteurs pondérés.
    Gère le cache multi-niveaux et les limites quotidiennes.

    Usage :
        optimizer = BekEcoOptimizer()
        decision = optimizer.optimize(tier="TIER_2", query="Cherche Bitcoin")
    """

    def __init__(
        self,
        cache_file: Optional[str] = None,
        limits_file: Optional[str] = None,
    ):
        self.cache_path = Path(cache_file or BEK_ECO_CACHE_FILE)
        self.limits_path = Path(limits_file or BEK_ECO_LIMITS_FILE)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._limits: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._load()

    # ──────────────────────────────────────────────────────────────────────────
    # CHARGEMENT / SAUVEGARDE
    # ──────────────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Charge le cache et les limites depuis le disque."""
        # Cache
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f).get("cache", {})
            except Exception as exc:
                logger.warning("BekEco : cache load error : %s", exc)
                self._cache = {}

        # Limites
        if self.limits_path.exists():
            try:
                with open(self.limits_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._limits = defaultdict(
                        lambda: defaultdict(int),
                        {k: defaultdict(int, v) for k, v in data.get("limits", {}).items()},
                    )
            except Exception as exc:
                logger.warning("BekEco : limits load error : %s", exc)

    def _save_cache(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump({"cache": self._cache}, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error("BekEco : cache save error : %s", exc)

    def _save_limits(self) -> None:
        try:
            self.limits_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.limits_path, "w", encoding="utf-8") as f:
                json.dump({"limits": dict(self._limits)}, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error("BekEco : limits save error : %s", exc)

    # ──────────────────────────────────────────────────────────────────────────
    # OPTIMISATION
    # ──────────────────────────────────────────────────────────────────────────

    def optimize(
        self,
        tier: str,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Optimise une décision.

        Args:
            tier: Le tier demandé (TIER_0 à TIER_4)
            query: La requête utilisateur
            context: Contexte additionnel

        Returns:
            dict: {
                "decision": "proceed" | "cached" | "reject",
                "cached": bool,
                "cached_value": Any,
                "score": float,
                "cost_estimate": float,
                "limits": {...}
            }
        """
        context = context or {}

        # 1. Cache check
        cache_key = self._cache_key(query)
        cached = self.cache_get(cache_key)
        if cached:
            return {
                "decision": "cached",
                "cached": True,
                "cached_value": cached.get("value"),
                "score": 1.0,
                "cost_estimate": 0.0,
                "limits": self.check_limits(),
            }

        # 2. Vérification des limites
        limits = self.check_limits()
        if tier in ("TIER_2", "TIER_3", "TIER_4"):
            if limits.get("daily_remaining", 0) <= 0:
                return {
                    "decision": "reject",
                    "cached": False,
                    "reason": "Limite quotidienne atteinte",
                    "score": 0.0,
                    "cost_estimate": 0.0,
                    "limits": limits,
                }

        # 3. Scoring des 7 facteurs
        factors = self._score_factors(tier, query, context)
        score = self._weighted_score(factors)

        # 4. Estimation du coût
        cost = self._estimate_cost(tier)

        # 5. Décision
        decision = "proceed" if score >= 0.5 else "reject"

        return {
            "decision": decision,
            "cached": False,
            "score": round(score, 3),
            "factors": factors,
            "cost_estimate": cost,
            "limits": limits,
        }

    def _score_factors(
        self,
        tier: str,
        query: str,
        context: Dict[str, Any],
    ) -> Dict[str, float]:
        """Score les 7 facteurs."""
        # Facteurs simples (0.0 à 1.0)
        return {
            "conformite":   1.0,   # Par défaut : OK
            "securite":     1.0,   # Par défaut : OK
            "precision":    0.9 if tier in ("TIER_2", "TIER_3", "TIER_4") else 0.7,
            "efficience":   0.5,   # Valeur moyenne
            "rentabilite":  0.7 if tier in ("TIER_0", "TIER_1") else 0.5,
            "productivite": 0.5,
            "technologie":  0.5,
        }

    def _weighted_score(self, factors: Dict[str, float]) -> float:
        """Score pondéré des 7 facteurs."""
        total = 0.0
        for factor, weight in BEK_ECO_WEIGHTS.items():
            total += factors.get(factor, 0.0) * weight
        return total

    def _estimate_cost(self, tier: str) -> float:
        """Estime le coût d'un tier."""
        costs = {
            "TIER_0": 0.0,
            "TIER_1": 0.001,
            "TIER_2": 0.01,
            "TIER_3": 0.05,
            "TIER_4": 0.08,
        }
        return costs.get(tier, 0.01)

    # ──────────────────────────────────────────────────────────────────────────
    # CACHE
    # ──────────────────────────────────────────────────────────────────────────

    def _cache_key(self, query: str) -> str:
        """Génère une clé de cache."""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    def cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        """Récupère une entrée du cache."""
        entry = self._cache.get(key)
        if not entry:
            return None

        # Vérifier TTL
        ttl = entry.get("ttl", BEK_ECO_DEFAULT_TTL)
        if time.time() - entry.get("timestamp", 0) > ttl:
            del self._cache[key]
            self._save_cache()
            return None

        return entry

    def cache_set(
        self,
        key: str,
        value: Any,
        ttl: int = BEK_ECO_DEFAULT_TTL,
    ) -> bool:
        """Stocke dans le cache."""
        self._cache[key] = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl,
        }
        self._save_cache()
        return True

    def cache_clear(self) -> int:
        """Efface le cache."""
        count = len(self._cache)
        self._cache = {}
        self._save_cache()
        return count

    # ──────────────────────────────────────────────────────────────────────────
    # LIMITES
    # ──────────────────────────────────────────────────────────────────────────

    def check_limits(self, scope: str = "global") -> Dict[str, Any]:
        """
        Vérifie les limites quotidiennes.

        Args:
            scope: Périmètre (global, user, etc.)

        Returns:
            dict: {daily_limit, daily_used, daily_remaining}
        """
        today = time.strftime("%Y-%m-%d")
        used = self._limits[scope].get(today, 0)
        limit = BEK_ECO_DEFAULT_DAILY_LIMIT

        return {
            "scope": scope,
            "daily_limit": limit,
            "daily_used": used,
            "daily_remaining": max(0, limit - used),
        }

    def increment_limit(self, scope: str = "global") -> None:
        """Incrémente le compteur d'utilisation."""
        today = time.strftime("%Y-%m-%d")
        self._limits[scope][today] += 1
        self._save_limits()


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ══════════════════════════════════════════════════════════════════════════════

def bek_eco_optimize(
    tier: str,
    query: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fonction principale BEK-ECO : optimisation."""
    optimizer = BekEcoOptimizer()
    return optimizer.optimize(tier, query, context)


def bek_eco_cache_get(key: str) -> Optional[Dict[str, Any]]:
    """Récupère une entrée du cache."""
    optimizer = BekEcoOptimizer()
    return optimizer.cache_get(key)


def bek_eco_cache_set(key: str, value: Any, ttl: int = BEK_ECO_DEFAULT_TTL) -> bool:
    """Stocke dans le cache."""
    optimizer = BekEcoOptimizer()
    return optimizer.cache_set(key, value, ttl)


def bek_eco_check_limits(scope: str = "global") -> Dict[str, Any]:
    """Vérifie les limites."""
    optimizer = BekEcoOptimizer()
    return optimizer.check_limits(scope)