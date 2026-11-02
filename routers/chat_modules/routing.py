# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat Module : Routing (BEK-REX, BEK-ECO & BEK-LOOP)
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Routing intelligent via BEK-REX + détection alter ego + cache + loop
# 📄 Doc : docs/brevets/BREVET_REX.md
# ------------------------------------------------------------------------------
# Version : 1.3
# Date : 2026-10-14
# ------------------------------------------------------------------------------
# ★ v1.3 (2026-10-14) — AJOUT _bek_loop_record + MATCHING ALTER EGO PRÉCIS
#   - Ajout de _bek_loop_record() appelé par streaming.py (corrige AttributeError)
#   - Détection d'alter ego par frontières de mots (\b) pour éviter les faux
#     positifs sur les mots courts ("ia", "post", "bio", "cours")
#   - ★ AUCUNE fonctionnalité supprimée (100% compatible v1.2)
# ★ v1.2 (2026-10-12) — FIX A15 : routage par tier inopérant
# ★ v1.1 (2026-10-04) — Ajout détection alter ego
# ==============================================================================

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from . import config as cfg

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING BEK-REX
# ══════════════════════════════════════════════════════════════════════════════

def _bek_rex_route(query: str) -> Dict[str, Any]:
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
        if isinstance(result, dict):
            result["source"] = "bek_rex"
            return result
        return {
            "tier": "TIER_3",
            "confidence": 0.5,
            "reasoning": "Résultat BEK-REX non-dict",
            "source": "fallback",
        }
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

def _bek_rex_should_use_web_sync(query: str, routing: Dict[str, Any]) -> bool:
    """
    ★ v1.2 — Décide si on doit utiliser web_sync (WebAgent profond).
    La décision dépend du nombre de sources configuré pour le tier
    (cfg.BEK_REX_TIER_TO_SOURCES).
    """
    tier = routing.get("tier", "TIER_3")

    if tier == "TIER_0":
        return False

    sources_count = cfg.BEK_REX_TIER_TO_SOURCES.get(tier, 0)
    return sources_count > 0


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION DU TIER → SOURCES
# ══════════════════════════════════════════════════════════════════════════════

def _bek_rex_get_sources_count(tier: str) -> int:
    """Retourne le nombre de sources à utiliser selon le tier."""
    return cfg.BEK_REX_TIER_TO_SOURCES.get(tier, 5)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DÉCISION
# ══════════════════════════════════════════════════════════════════════════════

def _bek_rex_should_answer_locally(query: str, routing: Dict[str, Any]) -> bool:
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
# ★ v1.1 / v1.3 — DÉTECTION D'ALTER EGO (SANS FAUX POSITIFS)
# ══════════════════════════════════════════════════════════════════════════════

_ALTER_EGO_KEYWORDS: Dict[str, List[str]] = {
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


def _kw_matches_query(kw: str, query_lower: str) -> bool:
    """Vérifie la présence d'un mot-clé avec frontières de mots pour les mots courts."""
    if len(kw) <= 5 and " " not in kw:
        return bool(re.search(rf"\b{re.escape(kw)}\b", query_lower))
    return kw in query_lower


def _bek_rex_detect_alter_ego(query: str) -> str:
    """
    ★ v1.3 — Détecte le domaine de la requête et retourne l'alter ego approprié.
    """
    if not query:
        return "bek"

    query_lower = query.lower()
    scores: Dict[str, int] = {}

    for ego, keywords in _ALTER_EGO_KEYWORDS.items():
        matches = sum(1 for kw in keywords if _kw_matches_query(kw, query_lower))
        if matches > 0:
            scores[ego] = matches

    if not scores:
        logger.info("[BEK-REX] Aucun alter ego spécifique → BEK maître")
        return "bek"

    best_ego = max(scores, key=scores.get)
    logger.info(
        "[BEK-REX] 🎭 Alter ego détecté : %s (score=%d)",
        best_ego, scores[best_ego],
    )
    return best_ego


def _bek_rex_get_alter_ego_prompt(ego: str) -> str:
    """
    ★ v1.1 — Retourne le prompt complet de l'alter ego demandé.
    Charge depuis skills/alter-egos/{ego}/SKILL.md si disponible.
    """
    if not ego or ego == "bek":
        return ""

    try:
        skills_dir = Path(__file__).resolve().parent.parent.parent / "skills"
        alter_ego_file = skills_dir / "alter-egos" / ego / "SKILL.md"

        if alter_ego_file.exists() and alter_ego_file.is_file():
            with alter_ego_file.open("r", encoding="utf-8") as fh:
                content = fh.read()
            logger.info(
                "[BEK-REX] Alter ego '%s' chargé (%d chars)",
                ego, len(content),
            )
            return content

        logger.debug(
            "[BEK-REX] Alter ego '%s' non trouvé dans %s",
            ego, alter_ego_file,
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

def _bek_eco_check_cache(query: str, tier: str) -> Dict[str, Any]:
    """
    Vérifie si une réponse similaire est déjà en cache via BEK-ECO.
    """
    if not cfg.BEK_LVC_OK or cfg.BekCPU is None:
        return {
            "cached": False, "decision": "proceed", "score": 1.0,
            "cost_estimate": 0.0, "query_hash": "",
        }

    try:
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
        if not isinstance(decision, dict):
            decision = {"decision": "proceed", "score": 1.0, "cost_estimate": 0.0}
        decision["cached"] = False
        decision["query_hash"] = query_hash
        return decision

    except Exception as exc:
        logger.warning("[BEK-ECO] Échec check cache : %s", exc)
        return {
            "cached": False, "decision": "proceed", "score": 1.0,
            "cost_estimate": 0.0, "query_hash": "",
        }


def _bek_eco_store_cache(query: str, tier: str, response: str) -> bool:
    """Stocke une réponse dans le cache BEK-ECO."""
    if not cfg.BEK_LVC_OK or cfg.BekCPU is None:
        return False

    try:
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
# ★ v1.3 — BEK-LOOP (APPRENTISSAGE CONTINU DEPUIS STREAMING.PY)
# ══════════════════════════════════════════════════════════════════════════════

def _bek_loop_record(
    query: str,
    tier: str = "TIER_3",
    provider: str = "",
    model: str = "",
    success: bool = True,
    time_ms: float = 0.0,
    error_type: str = "",
) -> bool:
    """
    ★ v1.3 — Enregistre un épisode d'interaction dans BEK-LOOP via BekCPU.
    Appelé à la fin de chaque requête dans `streaming.py`.
    """
    if not cfg.BEK_LVC_OK or cfg.BekCPU is None:
        return False

    episode = {
        "query": (query or "")[:200],
        "tier": tier,
        "provider": provider,
        "model": model,
        "success": bool(success),
        "time_ms": round(float(time_ms or 0.0), 1),
        "error_type": error_type or None,
    }

    try:
        cfg.BekCPU.execute("BEK-LOOP", "bek_loop_record", episode=episode)
        logger.debug("[BEK-LOOP] Épisode enregistré (tier=%s, success=%s)", tier, success)
        return True
    except Exception as exc:
        logger.debug("[BEK-LOOP] Échec enregistrement épisode : %s", exc)
        return False


# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ POUR DEBUG
# ══════════════════════════════════════════════════════════════════════════════

def get_routing_summary() -> dict:
    """
    ★ v1.3 — Résumé du module routing.
    """
    tier_to_sources = cfg.BEK_REX_TIER_TO_SOURCES

    non_zero_tiers = [
        t for t in ("TIER_1", "TIER_2", "TIER_3", "TIER_4")
        if tier_to_sources.get(t, 0) > 0
    ]
    web_sync_all_tiers = len(non_zero_tiers) == 4

    return {
        "version": "1.3",
        "functions": [
            "_bek_rex_route",
            "_bek_rex_should_use_web_sync",
            "_bek_rex_get_sources_count",
            "_bek_rex_should_answer_locally",
            "_bek_rex_is_freshness_query",
            "_bek_rex_detect_alter_ego",
            "_bek_rex_get_alter_ego_prompt",
            "_bek_rex_get_alter_ego_names",
            "_bek_eco_check_cache",
            "_bek_eco_store_cache",
            "_bek_loop_record",
        ],
        "bek_lvc_ok": cfg.BEK_LVC_OK,
        "tier_to_sources": tier_to_sources,
        "web_sync_all_tiers": web_sync_all_tiers,
        "web_sync_active_tiers": non_zero_tiers,
        "headless_search_status": "retiré",
        "alter_egos": _bek_rex_get_alter_ego_names(),
        "fix_web_sync_tier_v12": True,
        "★ bek_loop_record_v13": True,
    }