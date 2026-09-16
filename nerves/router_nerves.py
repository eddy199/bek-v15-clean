# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 7 — SMARTROUTER SÉMANTIQUE RÉEL (nerves/router_nerves.py)
# ------------------------------------------------------------------------------
# Ce nerf transforme le SmartRouter (actuellement vide) en VRAI routeur
# sémantique qui analyse la requête et choisit le meilleur provider/modèle.
#
# PROBLÈME RÉSOLU :
#   - Actuellement : SmartRouter.route() retourne TOUJOURS "groq" sans analyse.
#   - Résultat : pas d'optimisation par type de tâche, gaspillage de tokens.
#
# SOLUTION (ce nerf) :
#   - Analyse sémantique de la requête (mots-clés + heuristiques)
#   - Détection de l'intention : code / vision / complexe / long / chat / créatif
#   - Utilisation de bek_routing_config.get_routing_strategy() (existant)
#   - Utilisation de bek_model_hub.BEK_HUB_CONSTANTS (existant)
#   - Fallback intelligent via provider_manager.is_provider_available()
#
# NOUVEAUX OUTILS HERMES (additifs) :
#   - router_route         → route une requête vers le provider idéal
#   - router_task_type     → détecte uniquement le type de tâche
#   - router_providers     → liste les providers et leur disponibilité
#
# BRIDGES EXPOSÉS :
#   - route_semantic()     → utilisable par chat.py (remplace le SmartRouter vide)
#   - detect_task_type()   → détection pure du type de tâche
#
# RÈGLES D'OR :
#   - Aucune modification de bek_intelligence.py
#   - Aucune modification de bek_routing_config.py
#   - Aucune modification de bek_model_hub.py
#   - Aucune modification de provider_manager.py
#   - Aucune modification de hermes_core.py
#   - Feature-flag : BEK_ENABLE_ROUTER_NERVES (défaut true)
#   - Ne bloque JAMAIS le flux principal
#
# CORRECTIFS v2 (robustesse) :
#   - Réécriture complète en UTF-8 propre (fin du mojibake Ã©/ð/â)
#   - Modèles correctement résolus (fallback "default" si vide)
#   - Fallback chain par défaut cohérente avec les logs prod
#   - Aucune signature modifiée : compatibilité totale avec chat.py
# ==============================================================================

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.nerves.router")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_ROUTER_NERVES", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# PUBLICATION EVENTBUS — via le pont unifié du Nerf 3
# ------------------------------------------------------------------------------

def _publish_router_event(action: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """Publie un événement de routage sur l'EventBus unifié."""
    payload: Dict[str, Any] = {"action": action, "source": "router_nerves"}
    if extra:
        payload.update(extra)

    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified("skills-index", payload)
        logger.debug("[Nerf 7] Événement publié : skills-index / %s", action)
    except Exception as exc:
        logger.debug("[Nerf 7] Publication EventBus échouée (mode dégradé) : %s", exc)


# ------------------------------------------------------------------------------
# DÉTECTION DU TYPE DE TÂCHE (heuristique sémantique)
# ------------------------------------------------------------------------------

# Patterns de détection par catégorie
_CODE_PATTERNS = [
    r"\b(code|script|fonction|class|débug|debug|refactor|algorithme|regex|sql|bash|python|javascript|react|fastapi|flask)\b",
    r"\b(compil|exécute|exécution|lance le|test unitaire|unittest|pytest)\b",
    r"```",
]
_VISION_PATTERNS = [
    r"\b(image|photo|dessin|illustration|portrait|paysage|caricature|génère une image|génère une photo)\b",
    r"\b(vidéo|video|animation|film|clip|mouvement|cinématique|scène)\b",
    r"\b(voir|regarde|analyse cette image|regarde cette photo)\b",
]
_COMPLEX_PATTERNS = [
    r"\b(architecture|planifie|stratégie|analyse profonde|raisonnement|réfléchis|réflexion|complexe)\b",
    r"\b(compare|évalue|critique|débat|contradiction|argumente)\b",
]
_LONG_PATTERNS = [
    r"\b(document|rapport|synthèse|résume|long texte|mémoire|thèse|article)\b",
    r"\b(développe|détaillé|approfondi|extensif)\b",
]
_CREATIVE_PATTERNS = [
    r"\b(histoire|poème|chanson|scénario|conte|créatif|imagination|invente)\b",
]
_SOCIAL_PATTERNS = [
    r"^\s*(bonjour|salut|bjr|hello|hi|hey|coucou|bonsoir|ça va|ca va)\b",
]


def detect_task_type(query: str) -> str:
    """
    Détecte le type de tâche à partir de la requête utilisateur.
    Retourne l'un des types : chat, code, vision, complex, long, creative, social.
    """
    if not query:
        return "chat"

    q = query.lower().strip()

    # Social : priorité maximale (évite de mobiliser un LLM puissant pour "bonjour")
    for pat in _SOCIAL_PATTERNS:
        if re.search(pat, q):
            return "social"

    # Vision
    for pat in _VISION_PATTERNS:
        if re.search(pat, q):
            return "vision"

    # Code
    for pat in _CODE_PATTERNS:
        if re.search(pat, q):
            return "code"

    # Complexe
    for pat in _COMPLEX_PATTERNS:
        if re.search(pat, q):
            return "complex"

    # Long
    for pat in _LONG_PATTERNS:
        if re.search(pat, q):
            return "long"

    # Créatif
    for pat in _CREATIVE_PATTERNS:
        if re.search(pat, q):
            return "creative"

    # Par défaut : chat
    return "chat"


# ------------------------------------------------------------------------------
# ROUTAGE SÉMANTIQUE
# ------------------------------------------------------------------------------

def _is_provider_available(provider: str) -> bool:
    """Vérifie si un provider est disponible via provider_manager."""
    try:
        from provider_manager import provider_manager
        return provider_manager.is_provider_available(provider)
    except Exception:
        return True  # Ne bloque pas en cas d'erreur


def _get_default_models(provider: str) -> List[str]:
    """Récupère la liste des modèles disponibles pour un provider."""
    try:
        from provider_manager import provider_manager
        models = provider_manager.PROVIDER_MODELS.get(provider, [])
        return list(models) if models else []
    except Exception:
        return []


def _resolve_model(provider: str, preferred: str = "") -> str:
    """Résout le modèle à utiliser pour un provider (jamais vide)."""
    models = _get_default_models(provider)
    if preferred and preferred in models:
        return preferred
    if models:
        return models[0]
    # Fallback : jamais de chaîne vide (évite les erreurs côté providers)
    return preferred or "default"


def _fallback_chain() -> List[str]:
    """Récupère la chaîne de fallback depuis bek_model_hub."""
    try:
        from bek_model_hub import get_hub_constants
        chain = get_hub_constants("fallback_chain")
        if isinstance(chain, list) and chain:
            return chain
    except Exception:
        pass
    # Fallback de secours (aligné avec les providers actifs dans tes logs)
    return ["groq", "nvidia", "openrouter", "gemini"]


def route_semantic(
    query: str,
    context_hint: str = "",
) -> Dict[str, Any]:
    """
    Bridge public : route sémantiquement la requête vers le meilleur provider/modèle.

    Retourne un dict :
      {
        "provider": str,
        "model": str,
        "task_type": str,
        "strategy": str,
        "fallback_used": bool,
        "reasoning": str,
        "correlation_id": str
      }

    Ne lève JAMAIS d'exception.
    """
    result: Dict[str, Any] = {
        "provider": "groq",
        "model": "",
        "task_type": "chat",
        "strategy": "default",
        "fallback_used": False,
        "reasoning": "",
        "correlation_id": "",
    }

    try:
        # 1. Détecter le type de tâche
        task_type = detect_task_type(query or context_hint)
        result["task_type"] = task_type

        # 2. Utiliser bek_routing_config.get_routing_strategy() si disponible
        preferred_provider = ""
        try:
            from bek_routing_config import get_routing_strategy
            preferred_provider = get_routing_strategy(task_type)
            result["strategy"] = f"bek_routing_config:{task_type}→{preferred_provider}"
        except Exception as exc:
            logger.debug("[Nerf 7] bek_routing_config indisponible : %s", exc)

        # 3. Si pas de préférence, on utilise le provider par défaut
        if not preferred_provider:
            try:
                from bek_model_hub import get_hub_constants
                preferred_provider = get_hub_constants("default_provider", "groq")
            except Exception:
                preferred_provider = "groq"
            result["strategy"] = f"default:{preferred_provider}"

        # 4. Vérifier la disponibilité du provider préféré
        if preferred_provider and _is_provider_available(preferred_provider):
            result["provider"] = preferred_provider
            result["model"] = _resolve_model(preferred_provider)
        else:
            # 5. Fallback : parcourir la chaîne de fallback
            fallback_chain = _fallback_chain()
            result["fallback_used"] = True
            for fb_provider in fallback_chain:
                if _is_provider_available(fb_provider):
                    result["provider"] = fb_provider
                    result["model"] = _resolve_model(fb_provider)
                    result["reasoning"] = (
                        f"Provider '{preferred_provider}' indisponible → "
                        f"fallback sur '{fb_provider}'"
                    )
                    break

        # 6. Raisonnement (pour debug/logs)
        if not result["reasoning"]:
            result["reasoning"] = (
                f"Type '{task_type}' → provider '{result['provider']}' "
                f"(stratégie: {result['strategy']})"
            )

        # 7. Garde-fou : jamais de modèle vide
        if not result["model"]:
            result["model"] = "default"

        # 8. Traçabilité A2A
        _publish_router_event(
            action="route_decision",
            extra={
                "task_type": task_type,
                "provider": result["provider"],
                "model": result["model"],
                "fallback_used": result["fallback_used"],
            },
        )

        return result

    except Exception as exc:
        logger.error("[Nerf 7] route_semantic échoué : %s", exc)
        _publish_router_event(action="route_error", extra={"error": str(exc)[:300]})
        # Garantir une valeur de modèle non vide même en cas d'erreur
        if not result.get("model"):
            result["model"] = "default"
        return result


# ------------------------------------------------------------------------------
# HANDLERS HERMES
# ------------------------------------------------------------------------------

def _handler_router_route(query: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : router_route → route_semantic()."""
    if not query:
        return {"status": "error", "message": "query obligatoire."}
    routing = route_semantic(query)
    return {"status": "success", **routing}


def _handler_router_task_type(query: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : router_task_type → detect_task_type()."""
    if not query:
        return {"status": "error", "message": "query obligatoire."}
    return {
        "status": "success",
        "task_type": detect_task_type(query),
        "query_preview": query[:100],
    }


def _handler_router_providers(**kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : router_providers → liste des providers disponibles."""
    try:
        from provider_manager import provider_manager
        providers_info: List[Dict[str, Any]] = []
        for provider_id in provider_manager.PROVIDER_MODELS.keys():
            available = provider_manager.is_provider_available(provider_id)
            models_count = len(provider_manager.PROVIDER_MODELS.get(provider_id, []))
            providers_info.append({
                "provider": provider_id,
                "available": available,
                "models_count": models_count,
            })
        return {
            "status": "success",
            "count": len(providers_info),
            "providers": providers_info,
            "fallback_chain": _fallback_chain(),
        }
    except Exception as exc:
        logger.error("[Nerf 7] router_providers échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE
# ------------------------------------------------------------------------------

ROUTER_NERVES_TABLE: Dict[str, tuple] = {
    "router_route":      (_handler_router_route,      "L1"),
    "router_task_type":  (_handler_router_task_type,  "L1"),
    "router_providers":  (_handler_router_providers,  "L1"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_router_nerves() -> Dict[str, Any]:
    """
    Active les nerfs Router en enregistrant 3 outils Hermes.

    Idempotent. Feature-flag BEK_ENABLE_ROUTER_NERVES.
    """
    if not _is_enabled():
        logger.warning("[Nerf 7] Désactivé via BEK_ENABLE_ROUTER_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_ROUTER_NERVES=false",
        }

    # Vérification des dépendances
    routing_config_available = False
    model_hub_available = False
    provider_manager_available = False

    try:
        from bek_routing_config import get_routing_strategy  # noqa: F401
        routing_config_available = True
    except Exception as exc:
        logger.debug("[Nerf 7] bek_routing_config indisponible : %s", exc)

    try:
        from bek_model_hub import get_hub_constants  # noqa: F401
        model_hub_available = True
    except Exception as exc:
        logger.debug("[Nerf 7] bek_model_hub indisponible : %s", exc)

    try:
        from provider_manager import provider_manager  # noqa: F401
        provider_manager_available = True
    except Exception as exc:
        logger.debug("[Nerf 7] provider_manager indisponible : %s", exc)

    try:
        from hermes_core import hermes
    except ImportError as exc:
        logger.error("[Nerf 7] Impossible d'importer hermes_core : %s", exc)
        return {"status": "error", "message": str(exc)}

    activated: List[str] = []
    failed: List[Dict[str, str]] = []

    for tool_name, (handler, risk_level) in ROUTER_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("🧠 [Nerf 7] Outil Router branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 7] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 7] Activation terminée : %d outils Router branchés, %d échecs. "
        "bek_routing_config : %s | bek_model_hub : %s | provider_manager : %s",
        len(activated), len(failed),
        routing_config_available, model_hub_available, provider_manager_available,
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "bek_routing_config_available": routing_config_available,
        "bek_model_hub_available": model_hub_available,
        "provider_manager_available": provider_manager_available,
        "bridges_exposed": ["route_semantic", "detect_task_type"],
        "task_types_supported": ["social", "vision", "code", "complex", "long", "creative", "chat"],
    }


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_router_nerves()
    print("Résultat activation Nerf 7 :", result)

    # Tests de détection
    print()
    print("Test route_semantic :")
    for query in [
        "Bonjour, comment vas-tu ?",
        "Écris une fonction Python qui trie une liste",
        "Génère une image d'un chat en 3D",
        "Analyse complexe de l'architecture micro-services",
        "Rédige un rapport détaillé sur l'IA",
        "Écris-moi un poème sur l'automne",
    ]:
        routing = route_semantic(query)
        print(f"  '{query[:40]}...' → {routing['task_type']} → {routing['provider']}/{routing['model']}")