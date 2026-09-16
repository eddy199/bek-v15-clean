# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 7 — SMARTROUTER SÉMANTIQUE RÉEL (nerves/router_nerves.py)
# ------------------------------------------------------------------------------
# CORRECTIF v16 :
#   - Utilise get_routing_model() pour choisir un modèle spécifique par tâche
#     (ex : "complex" → "kimi-k3-swarm")
#   - Compatible : fallback sur _resolve_model() si pas de modèle spécifique
#   - Aucune signature modifiée
# ------------------------------------------------------------------------------
# CORRECTIF v17 (social) :
#   - Les salutations en début de message ne déclenchent plus le type "social"
#     si le message contient plus de 3 mots après retrait de la salutation.
#   - Exemple : "bjr Fais une analyse..." → complex (et non social)
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
# DÉTECTION DU TYPE DE TÂCHE
# ------------------------------------------------------------------------------

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
    r"^\s*(bonjour|salut|bjr|hello|hi|hey|coucou|bonsoir|ça va|ca va|slt)\b",
]

# Préfixe social plus large, utilisé pour retirer la salutation avant analyse
_SOCIAL_PREFIX_RE = re.compile(
    r"^\s*(bonjour|salut|bjr|hello|hi|hey|coucou|bonsoir|ça va|ca va|slt)\b[\s,!.?]*",
    re.IGNORECASE,
)


def _strip_social_prefix(text: str) -> str:
    """Retire une éventuelle salutation en début de message."""
    return _SOCIAL_PREFIX_RE.sub("", text).strip()


def detect_task_type(query: str) -> str:
    if not query:
        return "chat"

    q = query.lower().strip()

    # ------------------------------------------------------------
    # Détection sociale : uniquement si le message reste court
    # après retrait de la salutation.
    # Exemple :
    #   "bjr"                          -> social
    #   "bjr ça va ?"                  -> social
    #   "bjr Fais une analyse..."      -> PAS social (complex)
    # ------------------------------------------------------------
    q_sans_salutation = _strip_social_prefix(q)
    if len(q_sans_salutation.split()) <= 3:
        for pat in _SOCIAL_PATTERNS:
            if re.search(pat, q):
                return "social"

    # Ensuite on garde l'ordre actuel de détection
    for pat in _VISION_PATTERNS:
        if re.search(pat, q):
            return "vision"
    for pat in _CODE_PATTERNS:
        if re.search(pat, q):
            return "code"
    for pat in _COMPLEX_PATTERNS:
        if re.search(pat, q):
            return "complex"
    for pat in _LONG_PATTERNS:
        if re.search(pat, q):
            return "long"
    for pat in _CREATIVE_PATTERNS:
        if re.search(pat, q):
            return "creative"
    return "chat"


# ------------------------------------------------------------------------------
# ROUTAGE SÉMANTIQUE
# ------------------------------------------------------------------------------

def _is_provider_available(provider: str) -> bool:
    try:
        from provider_manager import provider_manager
        return provider_manager.is_provider_available(provider)
    except Exception:
        return True


def _get_default_models(provider: str) -> List[str]:
    try:
        from provider_manager import provider_manager
        models = provider_manager.PROVIDER_MODELS.get(provider, [])
        return list(models) if models else []
    except Exception:
        return []


def _resolve_model(provider: str, preferred: str = "") -> str:
    """Résout le modèle par défaut si pas de modèle spécifique fourni."""
    models = _get_default_models(provider)
    if preferred and preferred in models:
        return preferred
    if models:
        return models[0]
    return preferred or "default"


def _fallback_chain() -> List[str]:
    try:
        from bek_model_hub import get_hub_constants
        chain = get_hub_constants("fallback_chain")
        if isinstance(chain, list) and chain:
            return chain
    except Exception:
        pass
    return ["groq", "nvidia", "openrouter", "gemini"]


# Import de get_routing_model (utilisé si disponible)
try:
    from bek_routing_config import get_routing_model as _get_routing_model
    _ROUTING_MODEL_OK = True
except Exception:
    _get_routing_model = None
    _ROUTING_MODEL_OK = False


def route_semantic(
    query: str,
    context_hint: str = "",
) -> Dict[str, Any]:
    """
    Bridge public : route sémantiquement la requête vers le meilleur provider/modèle.
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

        # 3. Fallback provider par défaut
        if not preferred_provider:
            try:
                from bek_model_hub import get_hub_constants
                preferred_provider = get_hub_constants("default_provider", "groq")
            except Exception:
                preferred_provider = "groq"
            result["strategy"] = f"default:{preferred_provider}"

        # 4. Vérifier disponibilité provider
        if preferred_provider and _is_provider_available(preferred_provider):
            result["provider"] = preferred_provider
            # Tentative de modèle spécifique via get_routing_model()
            specific_model = ""
            if _ROUTING_MODEL_OK and _get_routing_model:
                try:
                    specific_model = _get_routing_model(task_type) or ""
                except Exception:
                    specific_model = ""
            # Résolution finale (spécifique ou défaut)
            result["model"] = _resolve_model(preferred_provider, specific_model)
        else:
            # 5. Fallback : parcourir la chaîne
            fallback_chain = _fallback_chain()
            result["fallback_used"] = True
            for fb_provider in fallback_chain:
                if _is_provider_available(fb_provider):
                    result["provider"] = fb_provider
                    # Fallback : pas de modèle spécifique, défaut provider
                    result["model"] = _resolve_model(fb_provider)
                    result["reasoning"] = (
                        f"Provider '{preferred_provider}' indisponible → "
                        f"fallback sur '{fb_provider}'"
                    )
                    break

        # 6. Raisonnement (debug)
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
        if not result.get("model"):
            result["model"] = "default"
        return result


# ------------------------------------------------------------------------------
# HANDLERS HERMES
# ------------------------------------------------------------------------------

def _handler_router_route(query: str = "", **kwargs: Any) -> Dict[str, Any]:
    if not query:
        return {"status": "error", "message": "query obligatoire."}
    routing = route_semantic(query)
    return {"status": "success", **routing}


def _handler_router_task_type(query: str = "", **kwargs: Any) -> Dict[str, Any]:
    if not query:
        return {"status": "error", "message": "query obligatoire."}
    return {
        "status": "success",
        "task_type": detect_task_type(query),
        "query_preview": query[:100],
    }


def _handler_router_providers(**kwargs: Any) -> Dict[str, Any]:
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


ROUTER_NERVES_TABLE: Dict[str, tuple] = {
    "router_route":      (_handler_router_route,      "L1"),
    "router_task_type":  (_handler_router_task_type,  "L1"),
    "router_providers":  (_handler_router_providers,  "L1"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_router_nerves() -> Dict[str, Any]:
    if not _is_enabled():
        logger.warning("[Nerf 7] Désactivé via BEK_ENABLE_ROUTER_NERVES=false")
        return {"status": "disabled", "reason": "Feature-flag"}

    routing_config_available = False
    model_hub_available = False
    provider_manager_available = False

    try:
        from bek_routing_config import get_routing_strategy  # noqa: F401
        routing_config_available = True
    except Exception:
        pass

    try:
        from bek_model_hub import get_hub_constants  # noqa: F401
        model_hub_available = True
    except Exception:
        pass

    try:
        from provider_manager import provider_manager  # noqa: F401
        provider_manager_available = True
    except Exception:
        pass

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(activate_router_nerves())