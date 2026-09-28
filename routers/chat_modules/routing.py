# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Routing (BEK-REX)
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Routing intelligent via BEK-REX
# 📄 Doc : docs/brevets/BREVET_REX.md
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-24
# ==============================================================================

from __future__ import annotations

import logging
from typing import Dict

from . import config as cfg

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING BEK-REX
# ══════════════════════════════════════════════════════════════════════════════

def _bek_rex_route(query: str) -> Dict:
    """
    Route une requête via BEK-REX (BEK-LVC).

    Args:
        query: La requête utilisateur

    Returns:
        dict: {
            "tier": "TIER_0..TIER_4",
            "confidence": float,
            "reasoning": str,
            "source": "bek_rex" | "fallback"
        }
    """
    if not cfg.BEK_LVC_OK or cfg.BekCPU is None:
        return {
            "tier": "TIER_3",
            "confidence": 0.5,
            "reasoning": "Fallback : BEK-LVC non chargé",
            "source": "fallback",
        }

    try:
        result = cfg.BekCPU.execute("BEK-REX", "bek_rex_route", query=query)
        result["source"] = "bek_rex"
        return result
    except Exception as exc:
        logger.warning("[BEK-REX] Échec routing : %s", exc)
        return {
            "tier": "TIER_3",
            "confidence": 0.5,
            "reasoning": f"Fallback : {exc}",
            "source": "fallback",
        }


# ══════════════════════════════════════════════════════════════════════════════
# DÉCISION D'OUTIL WEB
# ══════════════════════════════════════════════════════════════════════════════

def _bek_rex_should_use_web_sync(query: str, routing: Dict) -> bool:
    """
    Décide si on doit utiliser web_sync (WebAgent profond).

    Règles v18 :
        - TIER_0 : pas de recherche (retourne False)
        - TIER_1 : web_sync léger (5 sources) → True
        - TIER_2 : web_sync moyen (5 sources) → True
        - TIER_3 : web_sync profond (10 sources) → True
        - TIER_4 : web_sync expert (15 sources) → True

    Depuis v18 : TOUTES les recherches passent par web_sync.
    headless_search est retiré.

    Args:
        query: La requête
        routing: Le résultat de _bek_rex_route()

    Returns:
        bool: True si on doit utiliser web_sync
    """
    tier = routing.get("tier", "TIER_3")

    # TIER_0 → pas de recherche
    if tier == "TIER_0":
        return False

    # Tous les autres tiers → web_sync
    return True


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION DU TIER → SOURCES
# ══════════════════════════════════════════════════════════════════════════════

def _bek_rex_get_sources_count(tier: str) -> int:
    """
    Retourne le nombre de sources à utiliser selon le tier.

    Args:
        tier: "TIER_0" à "TIER_4"

    Returns:
        int: Nombre de sources (0 pour TIER_0)
    """
    return cfg.BEK_REX_TIER_TO_SOURCES.get(tier, 5)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DÉCISION
# ══════════════════════════════════════════════════════════════════════════════

def _bek_rex_should_answer_locally(query: str, routing: Dict) -> bool:
    """
    Décide si on peut répondre sans appel d'outil.

    Règles :
        - TIER_0 : toujours local
        - Autres : dépend du contexte (historique, fraîcheur)

    Note : cette fonction ne prend PAS en compte l'historique.
    C'est le code appelant qui décide.
    """
    tier = routing.get("tier", "TIER_3")
    return tier == "TIER_0"


def _bek_rex_is_freshness_query(query: str) -> bool:
    """
    Détecte si la requête demande des informations fraîches.

    Mots-clés : "news", "actualité", "dernières", "cherche", "actualise"
    """
    if not query:
        return False

    query_lower = query.lower()
    freshness_keywords = [
        "news", "actualité", "actualités",
        "dernières", "dernier", "récent", "récente",
        "aujourd'hui", "actuel", "actuelle",
        "cherche", "recherche", "actualise",
        "trouve", "montre-moi",
    ]

    return any(kw in query_lower for kw in freshness_keywords)


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ══════════════════════════════════════════════════════════════════════════════

def get_routing_summary() -> dict:
    """Résumé du module routing."""
    return {
        "functions": [
            "_bek_rex_route",
            "_bek_rex_should_use_web_sync",
            "_bek_rex_get_sources_count",
            "_bek_rex_should_answer_locally",
            "_bek_rex_is_freshness_query",
        ],
        "bek_lvc_ok": cfg.BEK_LVC_OK,
        "tier_to_sources": cfg.BEK_REX_TIER_TO_SOURCES,
        "web_sync_all_tiers": True,
        "headless_search_status": "retiré",
    }

# ══════════════════════════════════════════════════════════════════════════════
# ★ BEK-ECO — CACHE ÉCONOMIQUE (levier d'accélération)
# ══════════════════════════════════════════════════════════════════════════════

def _bek_eco_check_cache(query: str, tier: str) -> Dict:
    """
    Vérifie si une réponse similaire est déjà en cache via BEK-ECO.
    
    Args:
        query: La requête utilisateur
        tier: Le tier BEK-REX (TIER_0..TIER_4)
    
    Returns:
        dict: {
            "cached": bool,
            "decision": str,       # "proceed" | "reject"
            "score": float,
            "cost_estimate": float,
            "query_hash": str
        }
    """
    if not cfg.BEK_LVC_OK or cfg.BekCPU is None:
        return {"cached": False, "decision": "proceed", "score": 1.0,
                "cost_estimate": 0.0, "query_hash": ""}

    try:
        # 1. Générer un hash de la requête pour le cache
        import hashlib
        query_hash = hashlib.md5(
            f"{tier}:{query.lower().strip()}".encode("utf-8")
        ).hexdigest()[:16]

        # 2. Vérifier le cache
        cached_result = cfg.BekCPU.execute(
            "BEK-ECO", "bek_eco_cache_get", key=query_hash
        )

        if cached_result and cached_result.get("value"):
            logger.info("[BEK-ECO] Cache HIT pour query_hash=%s", query_hash)
            return {
                "cached": True,
                "decision": "proceed",
                "score": 1.0,
                "cost_estimate": 0.0,
                "query_hash": query_hash,
                "cached_value": cached_result.get("value"),
            }

        # 3. Pas en cache → vérifier la décision économique
        decision = cfg.BekCPU.execute(
            "BEK-ECO", "bek_eco_optimize", tier=tier, query=query
        )
        decision["cached"] = False
        decision["query_hash"] = query_hash
        return decision

    except Exception as exc:
        logger.warning("[BEK-ECO] Échec check cache : %s", exc)
        return {"cached": False, "decision": "proceed", "score": 1.0,
                "cost_estimate": 0.0, "query_hash": ""}


def _bek_eco_store_cache(query: str, tier: str, response: str) -> bool:
    """
    Stocke une réponse dans le cache BEK-ECO.
    
    Args:
        query: La requête utilisateur
        tier: Le tier BEK-REX
        response: La réponse LLM à mettre en cache
    
    Returns:
        bool: True si stocké
    """
    if not cfg.BEK_LVC_OK or cfg.BekCPU is None:
        return False

    try:
        import hashlib
        query_hash = hashlib.md5(
            f"{tier}:{query.lower().strip()}".encode("utf-8")
        ).hexdigest()[:16]

        cfg.BekCPU.execute(
            "BEK-ECO", "bek_eco_cache_set",
            key=query_hash,
            value={"response": response, "tier": tier, "query": query},
        )
        logger.info("[BEK-ECO] Cache STORE pour query_hash=%s", query_hash)
        return True

    except Exception as exc:
        logger.warning("[BEK-ECO] Échec store cache : %s", exc)
        return False