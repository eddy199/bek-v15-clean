# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Routing (BEK-REX)
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Routing intelligent via BEK-REX + détection alter ego
# 📄 Doc : docs/brevets/BREVET_REX.md
# ------------------------------------------------------------------------------
# Version : 1.1
# Date : 2026-10-04
# ------------------------------------------------------------------------------
# ★ v1.1 — Ajout détection alter ego (suntzu, nova, atlas, belfort, mentor, oracle)
# ==============================================================================

from __future__ import annotations

import logging
from typing import Dict, List

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
    """
    tier = routing.get("tier", "TIER_3")

    if tier == "TIER_0":
        return False

    return True


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION DU TIER → SOURCES
# ══════════════════════════════════════════════════════════════════════════════

def _bek_rex_get_sources_count(tier: str) -> int:
    """Retourne le nombre de sources à utiliser selon le tier."""
    return cfg.BEK_REX_TIER_TO_SOURCES.get(tier, 5)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DÉCISION
# ══════════════════════════════════════════════════════════════════════════════

def _bek_rex_should_answer_locally(query: str, routing: Dict) -> bool:
    """Décide si on peut répondre sans appel d'outil."""
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
# ★ v1.1 — DÉTECTION D'ALTER EGO
# ══════════════════════════════════════════════════════════════════════════════

# Mots-clés par alter ego (utilisés pour le routage automatique)
_ALTER_EGO_KEYWORDS = {
    "suntzu": [
        "stratégie", "concurrence", "battre", "sun tzu", "blue ocean",
        "bcg", "marché", "positionnement", "swot", "roadmap",
        "concurrent", "avantage compétitif", "niche", "compétition",
        "rival", "domination", "art de la guerre",
    ],
    "nova": [
        "rédige", "écris", "email", "mail", "linkedin", "seo", "article",
        "post", "communication", "message", "slogan", "bio", "rédaction",
        "copywriting", "newsletter", "blog", "texte", "contenu",
        "reformule", "corrige", "adapte",
    ],
    "atlas": [
        "productivité", "organise", "priorise", "planifie", "routine",
        "tâches", "budget", "vie perso", "objectifs", "planning",
        "agenda", "to-do", "todo", "organisation", "planifier",
        "gérer", "structurer", "habitudes", "focus",
    ],
    "belfort": [
        "vente", "closing", "client", "prospect", "support", "chatbot",
        "conversion", "pitch", "prospection", "objection", "négociation",
        "closer", "convaincre", "persuader", "argumentaire",
    ],
    "mentor": [
        "apprendre", "formation", "pédagogie", "exercice", "quiz",
        "expliquer", "cours", "tutor", "enseigner", "élève", "étudiant",
        "vulgariser", "leçon", "comprendre", "apprentissage", "tutoriel",
    ],
    "oracle": [
        "prompt", "ia", "technique", "avancé", "erreurs", "bonnes pratiques",
        "llm", "chatgpt", "modèle", "optimisation prompt", "prompt engineering",
        "few-shot", "zero-shot", "chain of thought",
    ],
}


def _bek_rex_detect_alter_ego(query: str) -> str:
    """
    ★ v1.1 — Détecte le domaine de la requête et retourne l'alter ego approprié.

    Args:
        query: La requête utilisateur

    Returns:
        str: Nom de l'alter ego ("suntzu", "nova", "atlas", "belfort",
             "mentor", "oracle") ou "bek" si aucun domaine détecté.
    """
    if not query:
        return "bek"

    query_lower = query.lower()
    scores: Dict[str, int] = {}

    for ego, keywords in _ALTER_EGO_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in query_lower)
        if matches > 0:
            scores[ego] = matches

    if not scores:
        logger.info("[BEK-REX] Aucun alter ego spécifique → BEK maître")
        return "bek"

    best_ego = max(scores, key=scores.get)
    logger.info(
        "[BEK-REX] 🎭 Alter ego détecté : %s (score=%d)",
        best_ego, scores[best_ego]
    )
    return best_ego


def _bek_rex_get_alter_ego_prompt(ego: str) -> str:
    """
    ★ v1.1 — Retourne le prompt complet de l'alter ego demandé.

    Charge depuis skills/alter-egos/{ego}/SKILL.md si disponible.
    Sinon retourne une chaîne vide.
    """
    if not ego or ego == "bek":
        return ""

    try:
        from pathlib import Path
        skills_dir = Path(__file__).resolve().parent.parent.parent / "skills"
        alter_ego_file = skills_dir / "alter-egos" / ego / "SKILL.md"

        if alter_ego_file.exists() and alter_ego_file.is_file():
            with alter_ego_file.open("r", encoding="utf-8") as fh:
                content = fh.read()
            logger.info(
                "[BEK-REX] Alter ego '%s' chargé (%d chars)",
                ego, len(content)
            )
            return content

        logger.debug(
            "[BEK-REX] Alter ego '%s' non trouvé dans %s",
            ego, alter_ego_file
        )
    except Exception as exc:
        logger.warning("[BEK-REX] Erreur chargement alter ego '%s' : %s", ego, exc)

    return ""


def _bek_rex_get_alter_ego_names() -> List[str]:
    """Retourne la liste des alter egos disponibles."""
    return list(_ALTER_EGO_KEYWORDS.keys())


# ══════════════════════════════════════════════════════════════════════════════
# ★ BEK-ECO — CACHE ÉCONOMIQUE (levier d'accélération)
# ══════════════════════════════════════════════════════════════════════════════

def _bek_eco_check_cache(query: str, tier: str) -> Dict:
    """
    Vérifie si une réponse similaire est déjà en cache via BEK-ECO.
    """
    if not cfg.BEK_LVC_OK or cfg.BekCPU is None:
        return {"cached": False, "decision": "proceed", "score": 1.0,
                "cost_estimate": 0.0, "query_hash": ""}

    try:
        import hashlib
        query_hash = hashlib.md5(
            f"{tier}:{query.lower().strip()}".encode("utf-8")
        ).hexdigest()[:16]

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
    """Stocke une réponse dans le cache BEK-ECO."""
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


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ══════════════════════════════════════════════════════════════════════════════

def get_routing_summary() -> dict:
    """Résumé du module routing."""
    return {
        "version": "1.1",
        "functions": [
            "_bek_rex_route",
            "_bek_rex_should_use_web_sync",
            "_bek_rex_get_sources_count",
            "_bek_rex_should_answer_locally",
            "_bek_rex_is_freshness_query",
            "_bek_rex_detect_alter_ego",
            "_bek_rex_get_alter_ego_prompt",
            "_bek_rex_get_alter_ego_names",
        ],
        "bek_lvc_ok": cfg.BEK_LVC_OK,
        "tier_to_sources": cfg.BEK_REX_TIER_TO_SOURCES,
        "web_sync_all_tiers": True,
        "headless_search_status": "retiré",
        "alter_egos": _bek_rex_get_alter_ego_names(),
    }