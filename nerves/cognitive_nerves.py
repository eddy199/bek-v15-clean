# -*- coding: utf-8 -*-
"""
==============================================================================
NERF 2 — CERVEAU COGNITIF BRANCHÉ (nerves/cognitive_nerves.py)
------------------------------------------------------------------------------
Rôle :
  Chat → Cortex → Swarm + Grounding → EventBus

Dépendances utilisées :
  - meta_cortex_swarm.py
  - meta_cortex_grounding.py
  - hermes_core.py
  - nerves.event_bus_nerves.py

RÈGLES :
  - Ne modifie aucun des modules ci-dessus.
  - Feature-flag : BEK_ENABLE_COGNITIVE_NERVES (défaut true)
  - Le pipeline cognitif ne doit jamais bloquer le flux principal.
  - Les événements passent par le EventBus unifié du Nerf 3.
==============================================================================
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.nerves.cognitive")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_COGNITIVE_NERVES", "true").lower() in ("true", "1", "yes")


def _min_length_for_critique() -> int:
    try:
        return int(os.getenv("BEK_COGNITIVE_MIN_DRAFT_LENGTH", "200"))
    except (TypeError, ValueError):
        return 200


def _min_length_for_grounding() -> int:
    try:
        return int(os.getenv("BEK_COGNITIVE_MIN_GROUNDING_LENGTH", "100"))
    except (TypeError, ValueError):
        return 100


def _degraded_confidence_threshold() -> float:
    try:
        return float(os.getenv("BEK_COGNITIVE_DEGRADED_CONFIDENCE", "0.05"))
    except (TypeError, ValueError):
        return 0.05


# ------------------------------------------------------------------------------
# PROVIDERS SWARM
# ------------------------------------------------------------------------------

_DEFAULT_SWARM_PROVIDERS = {"nvidia", "groq", "gemini", "openrouter", "mistral"}

_DEFAULT_SWARM_FALLBACK_CHAIN = ["nvidia", "groq", "gemini", "mistral", "openrouter"]

_SWARM_PROVIDER_ALIASES: Dict[str, str] = {
    "kimi": "nvidia",
    "kimi-k3-swarm": "nvidia",
    "b_ai": "nvidia",
    "kilo_anonymous": "nvidia",
    "kilo": "nvidia",
}


def _supported_swarm_providers() -> set:
    raw = os.getenv("BEK_COGNITIVE_SWARM_PROVIDERS", "").strip()
    if not raw:
        return set(_DEFAULT_SWARM_PROVIDERS)
    providers = {p.strip().lower() for p in raw.split(",") if p.strip()}
    return providers or set(_DEFAULT_SWARM_PROVIDERS)


def _swarm_fallback_chain() -> List[str]:
    raw = os.getenv("BEK_COGNITIVE_SWARM_FALLBACK", "").strip()
    if not raw:
        return list(_DEFAULT_SWARM_FALLBACK_CHAIN)
    chain = [p.strip().lower() for p in raw.split(",") if p.strip()]
    return chain or list(_DEFAULT_SWARM_FALLBACK_CHAIN)


def _resolve_swarm_provider(provider: str) -> Dict[str, Any]:
    """Résout le provider utilisé par ReflexionSwarm."""
    original = (provider or "").strip().lower()
    supported = _supported_swarm_providers()

    if not original:
        fallback = next(
            (c for c in _swarm_fallback_chain() if c in supported), "nvidia"
        )
        return {
            "provider": fallback,
            "fallback_used": True,
            "reason": "Provider vide → fallback par défaut",
            "original": "",
        }

    if original in _SWARM_PROVIDER_ALIASES:
        mapped = _SWARM_PROVIDER_ALIASES[original]
        if mapped not in supported:
            mapped = next(
                (c for c in _swarm_fallback_chain() if c in supported), "nvidia"
            )
        return {
            "provider": mapped,
            "fallback_used": True,
            "reason": f"Alias '{original}' → '{mapped}'",
            "original": original,
        }

    if original in supported:
        return {
            "provider": original,
            "fallback_used": False,
            "reason": "Provider supporté",
            "original": original,
        }

    for candidate in _swarm_fallback_chain():
        if candidate in supported:
            return {
                "provider": candidate,
                "fallback_used": True,
                "reason": f"Provider '{original}' non supporté → fallback sur '{candidate}'",
                "original": original,
            }

    return {
        "provider": "nvidia",
        "fallback_used": True,
        "reason": "Aucun provider valide → nvidia par défaut",
        "original": original,
    }


# ------------------------------------------------------------------------------
# MODÈLES SWARM
# ------------------------------------------------------------------------------

_DEFAULT_SWARM_MODELS: Dict[str, str] = {
    "nvidia": "nvidia/nemotron-3-super-120b-a12b",
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-1.5-flash",
    "openrouter": "meta-llama/llama-3.1-70b-instruct",
    "mistral": "mistral-large-latest",
}


def _default_model_for_provider(provider: str) -> str:
    provider = (provider or "").strip().lower()
    env_key = f"BEK_COGNITIVE_MODEL_{provider.upper()}"
    override = os.getenv(env_key, "").strip()
    if override:
        return override
    return _DEFAULT_SWARM_MODELS.get(provider, "")


def _is_model_valid_for_provider(model: str, provider: str) -> bool:
    """Vérification légère de compatibilité."""
    if not model:
        return True
    model_lower = model.lower()
    provider_lower = (provider or "").lower()
    incompatible_families = {
        "kimi": "kimi",
        "kimi-k3-swarm": "kimi",
        "b_ai": "b_ai",
        "kilo": "kilo",
    }
    for marker, family in incompatible_families.items():
        if marker in model_lower and family != provider_lower:
            return False
    return True


def _resolve_swarm_model(
    provider_resolved: str,
    model_received: str,
    provider_original: str,
) -> Dict[str, Any]:
    original = (model_received or "").strip()

    if not original:
        return {
            "model": _default_model_for_provider(provider_resolved),
            "fallback_used": True,
            "reason": "Modèle vide → modèle par défaut du provider",
            "original": "",
        }

    if _is_model_valid_for_provider(original, provider_resolved):
        return {
            "model": original,
            "fallback_used": False,
            "reason": "Modèle compatible",
            "original": original,
        }

    default_model = _default_model_for_provider(provider_resolved)
    return {
        "model": default_model,
        "fallback_used": True,
        "reason": (
            f"Modèle '{original}' incompatible avec provider '{provider_resolved}' "
            f"→ remplacement par '{default_model or 'défaut'}'"
        ),
        "original": original,
    }


# ------------------------------------------------------------------------------
# EVENTBUS UNIFIÉ
# ------------------------------------------------------------------------------

def _publish_cognitive_event(
    action: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Envoie les événements cognitifs au EventBus unifié du Nerf 3."""
    payload: Dict[str, Any] = {"action": action, "source": "cognitive_nerves"}
    if extra:
        payload.update(extra)
    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified("skills-index", payload)
        logger.debug("[Nerf 2] EventBus cognitive → %s", action)
    except Exception as exc:
        logger.debug("[Nerf 2] EventBus indisponible pour '%s' : %s", action, exc)


# ------------------------------------------------------------------------------
# DÉTECTION DES MESSAGES SOCIAUX
# ------------------------------------------------------------------------------

_SOCIAL_KEYWORDS = {
    "bonjour", "salut", "bjr", "hello", "hi", "hey", "coucou", "bonsoir",
    "bonne nuit", "ça va", "ca va", "comment vas-tu", "merci", "thanks",
    "au revoir", "bye", "à plus", "a plus", "comment tu vas", "quoi de neuf",
    "wesh",
}


def _is_social_message(query: str) -> bool:
    if not query:
        return False
    query_lower = query.lower().strip()
    if len(query_lower) > 60:
        return False
    return any(kw in query_lower for kw in _SOCIAL_KEYWORDS)


# ------------------------------------------------------------------------------
# BRIDGE 1 — SWARM
# ------------------------------------------------------------------------------

def run_critique_swarm(
    draft: str,
    original_query: str,
    provider: str = "nvidia",
    model: str = "",
) -> Dict[str, Any]:
    """Lance le ReflexionSwarm. Le provider NVIDIA est utilisé par défaut."""
    if not draft or len(draft.strip()) < _min_length_for_critique():
        return {
            "status": "skipped",
            "reason": "Draft trop court pour critique",
            "verdict": "GOOD",
            "confidence": 0.5,
        }

    if _is_social_message(original_query):
        return {
            "status": "skipped",
            "reason": "Message social détecté",
            "verdict": "GOOD",
            "confidence": 0.9,
        }

    provider_res = _resolve_swarm_provider(provider)
    llm_provider = provider_res["provider"]
    if provider_res["fallback_used"]:
        _publish_cognitive_event(
            action="swarm_provider_fallback",
            extra={
                "original": provider_res["original"],
                "resolved": llm_provider,
                "reason": provider_res["reason"],
            },
        )

    model_res = _resolve_swarm_model(
        provider_resolved=llm_provider,
        model_received=model,
        provider_original=provider_res["original"],
    )
    llm_model = model_res["model"]
    if model_res["fallback_used"]:
        _publish_cognitive_event(
            action="swarm_model_fallback",
            extra={
                "original": model_res["original"],
                "resolved": llm_model,
                "provider": llm_provider,
                "reason": model_res["reason"],
            },
        )

    swarm = None
    try:
        from meta_cortex_swarm import ReflexionSwarm
        swarm = ReflexionSwarm(
            llm_provider=llm_provider,
            llm_model=llm_model or None,
        )
        consensus = swarm.critique(draft=draft, original_query=original_query)

        verdict = getattr(consensus, "final_verdict", None)
        verdict_str = getattr(verdict, "value", str(verdict)) if verdict else "GOOD"
        confidence = float(getattr(consensus, "confidence", 0.5))
        unanimous = bool(getattr(consensus, "unanimous", False))
        dominant_issues = getattr(consensus, "dominant_issues", []) or []

        threshold = _degraded_confidence_threshold()
        degraded = (
            verdict_str == "GOOD"
            and confidence <= threshold
            and unanimous
            and len(dominant_issues) == 0
        )
        degraded_reason = ""
        if degraded:
            degraded_reason = (
                f"Verdict GOOD avec confidence={confidence:.3f} "
                f"≤ {threshold} et consensus sans problème détecté."
            )
            _publish_cognitive_event(
                action="swarm_degraded",
                extra={
                    "reason": degraded_reason,
                    "provider_used": llm_provider,
                    "model_used": llm_model,
                    "confidence": confidence,
                },
            )

        _publish_cognitive_event(
            action="swarm_critique",
            extra={
                "verdict": verdict_str,
                "confidence": confidence,
                "unanimous": unanimous,
                "issues_count": len(dominant_issues),
                "provider_used": llm_provider,
                "provider_original": provider_res["original"],
                "model_used": llm_model,
                "model_original": model_res["original"],
                "degraded": degraded,
            },
        )

        return {
            "status": "degraded" if degraded else "success",
            "verdict": verdict_str,
            "confidence": confidence,
            "unanimous": unanimous,
            "breakdown": getattr(consensus, "breakdown", {}),
            "dominant_issues": dominant_issues,
            "reasoning": getattr(consensus, "reasoning", ""),
            "provider_used": llm_provider,
            "provider_original": provider_res["original"],
            "provider_fallback": provider_res["fallback_used"],
            "model_used": llm_model,
            "model_original": model_res["original"],
            "model_fallback": model_res["fallback_used"],
            "degraded": degraded,
            "degraded_reason": degraded_reason,
        }

    except ImportError as exc:
        logger.warning("[Nerf 2] meta_cortex_swarm indisponible : %s", exc)
        _publish_cognitive_event(
            action="swarm_unavailable",
            extra={
                "error": str(exc)[:300],
                "provider_used": llm_provider,
                "model_used": llm_model,
            },
        )
        return {
            "status": "error",
            "reason": f"meta_cortex_swarm indisponible : {exc}",
            "verdict": "GOOD",
            "confidence": 0.5,
            "provider_used": llm_provider,
            "provider_original": provider_res["original"],
            "model_used": llm_model,
            "model_original": model_res["original"],
        }

    except Exception as exc:
        logger.error("[Nerf 2] run_critique_swarm échoué : %s", exc)
        _publish_cognitive_event(
            action="swarm_error",
            extra={
                "error": str(exc)[:300],
                "provider_used": llm_provider,
                "provider_original": provider_res["original"],
                "model_used": llm_model,
                "model_original": model_res["original"],
            },
        )
        return {
            "status": "error",
            "reason": str(exc),
            "verdict": "GOOD",
            "confidence": 0.5,
            "provider_used": llm_provider,
            "provider_original": provider_res["original"],
            "model_used": llm_model,
            "model_original": model_res["original"],
        }

    finally:
        if swarm is not None:
            try:
                swarm.close()
            except Exception:
                pass


# ------------------------------------------------------------------------------
# BRIDGE 2 — GROUNDING
# ------------------------------------------------------------------------------

def run_grounding(
    draft: str,
    original_query: str,
    connection_string: str = "",
) -> Dict[str, Any]:
    """Vérifie les affirmations du draft avec GroundingValidator."""
    if not draft or len(draft.strip()) < _min_length_for_grounding():
        return {
            "status": "skipped",
            "reason": "Draft trop court pour grounding",
            "verified_count": 0,
            "unverified_count": 0,
            "unverifiable_count": 0,
        }

    if _is_social_message(original_query):
        return {
            "status": "skipped",
            "reason": "Message social détecté",
            "verified_count": 0,
            "unverified_count": 0,
            "unverifiable_count": 0,
        }

    validator = None
    try:
        from meta_cortex_grounding import GroundingValidator

        if not connection_string:
            try:
                from memory import NEON_DATABASE_URL
                connection_string = NEON_DATABASE_URL or ""
            except Exception:
                connection_string = ""

        validator = GroundingValidator(conn_str=connection_string)
        results = validator.validate(draft=draft, query=original_query)

        verified_count = 0
        unverified_count = 0
        unverifiable_count = 0
        issues: List[Dict[str, Any]] = []

        for result in results:
            if not hasattr(result, "verified"):
                continue
            if result.verified:
                verified_count += 1
            elif result.actual_value == "UNVERIFIABLE":
                unverifiable_count += 1
            else:
                unverified_count += 1
                issues.append(
                    {
                        "claim": getattr(
                            getattr(result, "claim", None), "claim_text", ""
                        )[:200],
                        "expected": getattr(result, "expected_value", ""),
                        "actual": getattr(result, "actual_value", ""),
                    }
                )

        _publish_cognitive_event(
            action="grounding_check",
            extra={
                "verified_count": verified_count,
                "unverified_count": unverified_count,
                "unverifiable_count": unverifiable_count,
                "total_claims": len(results),
            },
        )

        return {
            "status": "success",
            "total_claims": len(results),
            "verified_count": verified_count,
            "unverified_count": unverified_count,
            "unverifiable_count": unverifiable_count,
            "issues": issues,
            "all_verified": unverified_count == 0,
        }

    except ImportError as exc:
        logger.warning("[Nerf 2] meta_cortex_grounding indisponible : %s", exc)
        return {
            "status": "error",
            "reason": f"meta_cortex_grounding indisponible : {exc}",
            "verified_count": 0,
            "unverified_count": 0,
            "unverifiable_count": 0,
        }

    except Exception as exc:
        logger.error("[Nerf 2] run_grounding échoué : %s", exc)
        _publish_cognitive_event(
            action="grounding_error",
            extra={"error": str(exc)[:300]},
        )
        return {
            "status": "error",
            "reason": str(exc),
            "verified_count": 0,
            "unverified_count": 0,
            "unverifiable_count": 0,
        }

    finally:
        if validator is not None:
            try:
                validator.close()
            except Exception:
                pass


# ------------------------------------------------------------------------------
# BRIDGE 3 — PIPELINE COGNITIF COMPLET
# ------------------------------------------------------------------------------

def run_cognitive_pipeline(
    draft: str,
    original_query: str,
    provider: str = "nvidia",
    model: str = "",
    enable_swarm: bool = True,
    enable_grounding: bool = True,
) -> Dict[str, Any]:
    """Pipeline complet : Draft → Grounding → Swarm → Verdict → EventBus."""
    result: Dict[str, Any] = {
        "status": "success",
        "final_verdict": "GOOD",
        "needs_correction": False,
        "degraded": False,
        "issues": [],
        "swarm_result": None,
        "grounding_result": None,
    }

    if not _is_enabled():
        return {
            "status": "disabled",
            "reason": "BEK_ENABLE_COGNITIVE_NERVES=false",
            "final_verdict": "GOOD",
            "needs_correction": False,
            "degraded": True,
            "issues": [],
            "swarm_result": None,
            "grounding_result": None,
        }

    if _is_social_message(original_query):
        result["status"] = "skipped"
        result["reason"] = "Message social — pas de vérification cognitive"
        return result

    # GROUNDING
    if enable_grounding:
        grounding = run_grounding(draft=draft, original_query=original_query)
        result["grounding_result"] = grounding
        if grounding.get("unverified_count", 0) > 0:
            result["needs_correction"] = True
            result["issues"].extend(grounding.get("issues", []))
        if grounding.get("status") == "error":
            result["degraded"] = True

    # SWARM
    if enable_swarm:
        swarm = run_critique_swarm(
            draft=draft,
            original_query=original_query,
            provider=provider,
            model=model,
        )
        result["swarm_result"] = swarm
        verdict = swarm.get("verdict", "GOOD")
        result["final_verdict"] = verdict
        if swarm.get("degraded"):
            result["degraded"] = True
            result["status"] = "degraded"
        if swarm.get("status") == "error":
            result["degraded"] = True
        if verdict in ("FIX", "ESCALATE"):
            result["needs_correction"] = True
            result["issues"].extend(swarm.get("dominant_issues", []))

    if result["degraded"] and result["status"] == "success":
        result["status"] = "degraded"

    _publish_cognitive_event(
        action="cognitive_pipeline_done",
        extra={
            "final_verdict": result["final_verdict"],
            "needs_correction": result["needs_correction"],
            "degraded": result["degraded"],
            "issues_count": len(result["issues"]),
        },
    )

    return result


# ------------------------------------------------------------------------------
# HANDLERS HERMES
# ------------------------------------------------------------------------------

def _handler_cognitive_critique(
    draft: str = "",
    original_query: str = "",
    provider: str = "nvidia",
    model: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    if not draft:
        return {"status": "error", "message": "draft obligatoire."}
    return run_critique_swarm(
        draft=draft, original_query=original_query, provider=provider, model=model
    )


def _handler_cognitive_ground(
    draft: str = "",
    original_query: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    if not draft:
        return {"status": "error", "message": "draft obligatoire."}
    return run_grounding(draft=draft, original_query=original_query)


def _handler_cognitive_full_check(
    draft: str = "",
    original_query: str = "",
    provider: str = "nvidia",
    model: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    if not draft:
        return {"status": "error", "message": "draft obligatoire."}
    return run_cognitive_pipeline(
        draft=draft,
        original_query=original_query,
        provider=provider,
        model=model,
    )


# ------------------------------------------------------------------------------
# TABLE HERMES
# ------------------------------------------------------------------------------

COGNITIVE_NERVES_TABLE: Dict[str, tuple] = {
    "cognitive_critique": (_handler_cognitive_critique, "L2"),
    "cognitive_ground": (_handler_cognitive_ground, "L2"),
    "cognitive_full_check": (_handler_cognitive_full_check, "L2"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_cognitive_nerves() -> Dict[str, Any]:
    """Active les trois outils cognitifs Hermes."""
    if not _is_enabled():
        logger.warning("[Nerf 2] Désactivé via BEK_ENABLE_COGNITIVE_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_COGNITIVE_NERVES=false",
        }

    swarm_available = False
    grounding_available = False

    try:
        from meta_cortex_swarm import ReflexionSwarm  # noqa: F401
        swarm_available = True
    except Exception as exc:
        logger.warning("[Nerf 2] meta_cortex_swarm indisponible : %s", exc)

    try:
        from meta_cortex_grounding import GroundingValidator  # noqa: F401
        grounding_available = True
    except Exception as exc:
        logger.warning("[Nerf 2] meta_cortex_grounding indisponible : %s", exc)

    try:
        from hermes_core import hermes
    except ImportError as exc:
        logger.error("[Nerf 2] Impossible d'importer hermes_core : %s", exc)
        return {"status": "error", "message": str(exc)}

    activated: List[str] = []
    failed: List[Dict[str, str]] = []

    for tool_name, (handler, risk_level) in COGNITIVE_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("[Nerf 2] Outil cognitif branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 2] Échec branchement %s : %s", tool_name, exc)

    eventbus_available = False
    try:
        from nerves.event_bus_nerves import get_event_bus_bridge
        bridge = get_event_bus_bridge()
        eventbus_available = bridge.get_status().get("activated", False)
    except Exception as exc:
        logger.debug(
            "[Nerf 2] EventBus unifié non disponible au moment de l'activation : %s",
            exc,
        )

    logger.info(
        "[Nerf 2] Activation terminée : %d outils branchés, %d échecs | "
        "Swarm=%s | Grounding=%s | EventBus=%s",
        len(activated), len(failed),
        swarm_available, grounding_available, eventbus_available,
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "swarm_available": swarm_available,
        "grounding_available": grounding_available,
        "eventbus_available": eventbus_available,
        "bridges_exposed": [
            "run_critique_swarm",
            "run_grounding",
            "run_cognitive_pipeline",
        ],
        "thresholds": {
            "min_draft_length_critique": _min_length_for_critique(),
            "min_draft_length_grounding": _min_length_for_grounding(),
            "degraded_confidence": _degraded_confidence_threshold(),
        },
        "swarm_providers": {
            "supported": sorted(_supported_swarm_providers()),
            "fallback_chain": _swarm_fallback_chain(),
            "aliases": dict(_SWARM_PROVIDER_ALIASES),
        },
        "swarm_models": {
            "defaults": dict(_DEFAULT_SWARM_MODELS),
        },
    }


# ------------------------------------------------------------------------------
# TEST DIRECT
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    result = activate_cognitive_nerves()
    print("Résultat activation Nerf 2 :", result)
    print()

    for provider in ["kimi", "b_ai", "groq", "nvidia", "inconnu", "", "gemini"]:
        print(f"resolve_provider({provider!r}) →", _resolve_swarm_provider(provider))
    print()

    for provider, model in [
        ("nvidia", "kimi-k3-swarm"),
        ("nvidia", ""),
        ("groq", "llama-3.3-70b-versatile"),
    ]:
        print(
            f"resolve_model({provider!r}, {model!r}) →",
            _resolve_swarm_model(provider, model, provider),
        )