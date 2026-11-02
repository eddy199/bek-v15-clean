# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-ECO Optimizer
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-ECO-v1.0
# 📄 Doc : docs/brevets/BREVET_ECO.md
# 🎯 Rôle : Optimisation économique + cache + limites
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.1
# Date : 2026-10-04
# ------------------------------------------------------------------------------
# ★ v1.1 — FIX cache intelligent :
#   - Ne cache plus les questions de clarification
#   - Ne cache plus les échecs
#   - Ne cache plus les réponses trop courtes
#   - TTL différencié selon le type de réponse
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
BEK_ECO_CONVERSATIONAL_TTL = 300        # 5 minutes (réponses conversationnelles)
BEK_ECO_FACTUAL_TTL = 7200              # 2 heures (réponses factuelles stables)
BEK_ECO_DEFAULT_DAILY_LIMIT = 50
BEK_ECO_CACHE_FILE = "data/bek_eco_cache.json"
BEK_ECO_LIMITS_FILE = "data/bek_eco_limits.json"

# ★ v1.1 — Marqueurs à ne PAS cacher
_CLARIFICATION_STARTERS = (
    "avant", "peux-tu", "peux tu", "quel", "quelle", "quels", "quelles",
    "comment", "pourquoi", "où", "quand", "qui", "combien",
    "j'ai besoin", "jai besoin", "précise", "precise",
    "dis-moi", "dis moi", "pourrais-tu", "pourrais tu",
)

_FAILURE_MARKERS = (
    "sans résultat", "sans resultat", "erreur", "échec", "echec",
    "impossible", "pas pu", "aucune source", "non trouvé", "non trouve",
    "je n'ai pas", "je nai pas", "je ne peux pas",
    "aucun résultat", "aucun resultat",
)

_MIN_CACHEABLE_LENGTH = 200


# ══════════════════════════════════════════════════════════════════════════════
# ★ v1.1 — FONCTIONS DE FILTRAGE CACHE
# ══════════════════════════════════════════════════════════════════════════════

def _is_clarification(response: str) -> bool:
    """Détecte si la réponse est une question de clarification."""
    if not response:
        return False
    r = response.lower().strip()
    # Retirer les préfixes de cache éventuels
    r = r.replace("⚡ *[réponse en cache]*", "").strip()
    for starter in _CLARIFICATION_STARTERS:
        if r.startswith(starter):
            return True
    return False


def _is_failure(response: str) -> bool:
    """Détecte si la réponse est un échec."""
    if not response:
        return True
    r = response.lower()
    for marker in _FAILURE_MARKERS:
        if marker in r:
            return True
    return False


def _should_cache_response(response: str, query: str) -> bool:
    """
    ★ v1.1 — Détermine si une réponse doit être mise en cache.

    Ne pas cacher :
    - Les questions de clarification (commencent par "Avant", "Peux-tu", etc.)
    - Les échecs (contiennent "sans résultat", "erreur", "échec")
    - Les réponses trop courtes (< 200 chars)
    - Les réponses qui sont juste un placeholder

    Returns:
        True si la réponse peut être cachée, False sinon.
    """
    if not response:
        return False

    response_clean = response.strip()

    # 1. Trop courte → ne pas cacher
    if len(response_clean) < _MIN_CACHEABLE_LENGTH:
        logger.debug(
            "[BEK-ECO] Cache SKIP : réponse trop courte (%d chars < %d)",
            len(response_clean), _MIN_CACHEABLE_LENGTH,
        )
        return False

    # 2. Question de clarification → ne pas cacher
    if _is_clarification(response_clean):
        logger.info(
            "[BEK-ECO] Cache SKIP : question de clarification détectée"
        )
        return False

    # 3. Échec → ne pas cacher
    if _is_failure(response_clean):
        logger.info(
            "[BEK-ECO] Cache SKIP : échec détecté"
        )
        return False

    return True


def _compute_ttl(response: str, query: str) -> int:
    """
    ★ v1.1 — Calcule le TTL approprié selon le type de réponse.

    - Réponse factuelle (contient des URLs, dates) → TTL long
    - Réponse conversationnelle → TTL court
    """
    if not response:
        return BEK_ECO_DEFAULT_TTL

    r = response.lower()

    # Réponse factuelle : contient des sources/URLs
    if "http://" in r or "https://" in r:
        return BEK_ECO_FACTUAL_TTL

    # Réponse conversationnelle : commence par une question
    if _is_clarification(response):
        return BEK_ECO_CONVERSATIONAL_TTL

    return BEK_ECO_DEFAULT_TTL


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
            # ★ v1.1 — Vérifier que la valeur cachée est toujours valide
            cached_value = cached.get("value")
            if cached_value and _should_cache_response(
                str(cached_value), query
            ):
                return {
                    "decision": "cached",
                    "cached": True,
                    "cached_value": cached_value,
                    "score": 1.0,
                    "cost_estimate": 0.0,
                    "limits": self.check_limits(),
                }
            else:
                # ★ v1.1 — Entrée cache invalide → supprimer et continuer
                logger.info(
                    "[BEK-ECO] Cache INVALIDÉ pour query_hash=%s "
                    "(réponse non cacheable)",
                    cache_key[:12],
                )
                del self._cache[cache_key]
                self._save_cache()

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
        return {
            "conformite":   1.0,
            "securite":     1.0,
            "precision":    0.9 if tier in ("TIER_2", "TIER_3", "TIER_4") else 0.7,
            "efficience":   0.5,
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
        ttl: Optional[int] = None,
        query: str = "",
    ) -> bool:
        """
        ★ v1.1 — Stocke dans le cache AVEC filtrage intelligent.

        Args:
            key: Clé de cache
            value: Valeur à cacher
            ttl: TTL optionnel (calculé automatiquement si None)
            query: Requête originale (pour le calcul du TTL)

        Returns:
            True si caché, False si rejeté par le filtre.
        """
        # ★ v1.1 — Vérifier si la réponse peut être cachée
        value_str = str(value) if value else ""
        if not _should_cache_response(value_str, query):
            logger.info(
                "[BEK-ECO] Cache SKIP pour key=%s (réponse non cacheable)",
                key[:12],
            )
            return False

        # ★ v1.1 — Calculer le TTL si non fourni
        if ttl is None:
            ttl = _compute_ttl(value_str, query)

        self._cache[key] = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl,
        }
        self._save_cache()
        logger.info(
            "[BEK-ECO] Cache STORE pour key=%s (ttl=%ds)",
            key[:12], ttl,
        )
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
        """Vérifie les limites quotidiennes."""
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


def bek_eco_cache_set(
    key: str,
    value: Any,
    ttl: Optional[int] = None,
    query: str = "",
) -> bool:
    """
    ★ v1.1 — Stocke dans le cache avec filtrage intelligent.
    """
    optimizer = BekEcoOptimizer()
    return optimizer.cache_set(key, value, ttl, query)


def bek_eco_check_limits(scope: str = "global") -> Dict[str, Any]:
    """Vérifie les limites."""
    optimizer = BekEcoOptimizer()
    return optimizer.check_limits(scope)