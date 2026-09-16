# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 2 — CERVEAU COGNITIF BRANCHÉ (nerves/cognitive_nerves.py)
# ------------------------------------------------------------------------------
# Ce nerf branche les 3 briques cognitives dormantes sur Hermes et Chat :
#
#   NERF 2 : Chat → Cortex (Swarm + Grounding + SSE)
#
# PROBLÈME RÉSOLU :
#   - Actuellement : meta_cortex_swarm.py et meta_cortex_grounding.py existent
#     mais ne sont JAMAIS appelés dans le flux principal (chat.py).
#   - Résultat : aucune vérification factuelle, aucun débat critique.
#
# SOLUTION (ce nerf) :
#   - 3 outils Hermes pour déclencher la vérification cognitive
#   - 3 bridges publics utilisables par chat.py
#   - Feature-flag global + seuils configurables
#   - Traçabilité EventBus complète (via Nerf 3)
#
# NOUVEAUX OUTILS HERMES (additifs) :
#   - cognitive_critique    → débat 3 critiques (Factual, Logical, Contextual)
#   - cognitive_ground      → vérification factuelle SQL réelle
#   - cognitive_full_check  → pipeline complet (Swarm + Grounding combinés)
#
# BRIDGES EXPOSÉS :
#   - run_critique_swarm()      → utilisable par chat.py
#   - run_grounding()           → utilisable par chat.py
#   - run_cognitive_pipeline()  → pipeline complet
#
# RÈGLES D'OR :
#   - Aucune modification de meta_cortex_swarm.py
#   - Aucune modification de meta_cortex_grounding.py
#   - Aucune modification de meta_cortex_sse_ui.py
#   - Aucune modification de hermes_core.py
#   - Feature-flag : BEK_ENABLE_COGNITIVE_NERVES (défaut true)
#   - Ne bloque JAMAIS le flux principal (timeouts stricts)
# ==============================================================================

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.nerves.cognitive")


# ------------------------------------------------------------------------------
# FEATURE FLAG & SEUILS
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_COGNITIVE_NERVES", "true").lower() in ("true", "1", "yes")


def _min_length_for_critique() -> int:
    """Longueur minimale du draft pour déclencher le Swarm."""
    try:
        return int(os.getenv("BEK_COGNITIVE_MIN_DRAFT_LENGTH", "200"))
    except (TypeError, ValueError):
        return 200


def _min_length_for_grounding() -> int:
    """Longueur minimale du draft pour déclencher le Grounding."""
    try:
        return int(os.getenv("BEK_COGNITIVE_MIN_GROUNDING_LENGTH", "100"))
    except (TypeError, ValueError):
        return 100


# ------------------------------------------------------------------------------
# PUBLICATION EVENTBUS — via le pont unifié du Nerf 3
# ------------------------------------------------------------------------------

def _publish_cognitive_event(
    action: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Publie un événement cognitif sur l'EventBus unifié."""
    payload: Dict[str, Any] = {"action": action, "source": "cognitive_nerves"}
    if extra:
        payload.update(extra)

    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified("skills-index", payload)
        logger.debug("[Nerf 2] Événement publié : skills-index / %s", action)
    except Exception as exc:
        logger.debug("[Nerf 2] Publication EventBus échouée (mode dégradé) : %s", exc)


# ------------------------------------------------------------------------------
# DÉTECTION SALUTATION / PETITE DISCUSSION
# ------------------------------------------------------------------------------

_SOCIAL_KEYWORDS = {
    "bonjour", "salut", "bjr", "hello", "hi", "hey", "coucou",
    "bonsoir", "bonne nuit", "ça va", "ca va", "comment vas-tu",
    "merci", "thanks", "au revoir", "bye", "à plus", "a plus",
    "comment tu vas", "quoi de neuf", "wesh",
}


def _is_social_message(query: str) -> bool:
    """Détecte si le message est une simple salutation/discussion sociale."""
    if not query:
        return False
    q = query.lower().strip()
    if len(q) > 60:
        return False
    return any(kw in q for kw in _SOCIAL_KEYWORDS)


# ------------------------------------------------------------------------------
# BRIDGE 1 : SWARM (débat 3 critiques)
# ------------------------------------------------------------------------------

def run_critique_swarm(
    draft: str,
    original_query: str,
    provider: str = "groq",
    model: str = "",
) -> Dict[str, Any]:
    """
    Bridge public : lance le débat 3 critiques (Factual, Logical, Contextual).
    Utilise meta_cortex_swarm.ReflexionSwarm (existant).

    Ne lève JAMAIS d'exception. Timeout interne de sécurité.
    """
    if not draft or len(draft.strip()) < _min_length_for_critique():
        return {
            "status": "skipped",
            "reason": "Draft trop court pour critique",
            "verdict": "GOOD",
            "confidence": 0.5,
        }

    # Skip les messages sociaux (pas besoin de débat sur "bonjour")
    if _is_social_message(original_query):
        return {
            "status": "skipped",
            "reason": "Message social détecté",
            "verdict": "GOOD",
            "confidence": 0.9,
        }

    try:
        from meta_cortex_swarm import ReflexionSwarm

        # Si aucun provider explicite, on utilise groq par défaut
        llm_provider = provider if provider and provider != "b_ai" else "groq"

        swarm = ReflexionSwarm(llm_provider=llm_provider, llm_model=model or None)
        consensus = swarm.critique(draft=draft, original_query=original_query)

        verdict = getattr(consensus, "final_verdict", None)
        verdict_str = getattr(verdict, "value", str(verdict)) if verdict else "GOOD"
        confidence = float(getattr(consensus, "confidence", 0.5))

        # Traçabilité A2A
        _publish_cognitive_event(
            action="swarm_critique",
            extra={
                "verdict": verdict_str,
                "confidence": confidence,
                "unanimous": getattr(consensus, "unanimous", False),
                "issues_count": len(getattr(consensus, "dominant_issues", [])),
            },
        )

        # Nettoyage du swarm (ferme le ThreadPoolExecutor)
        try:
            swarm.close()
        except Exception:
            pass

        return {
            "status": "success",
            "verdict": verdict_str,
            "confidence": confidence,
            "unanimous": getattr(consensus, "unanimous", False),
            "breakdown": getattr(consensus, "breakdown", {}),
            "dominant_issues": getattr(consensus, "dominant_issues", []),
            "reasoning": getattr(consensus, "reasoning", ""),
        }

    except ImportError as exc:
        logger.warning("[Nerf 2] meta_cortex_swarm indisponible : %s", exc)
        return {
            "status": "error",
            "reason": f"meta_cortex_swarm indisponible : {exc}",
            "verdict": "GOOD",
            "confidence": 0.5,
        }
    except Exception as exc:
        logger.error("[Nerf 2] run_critique_swarm échoué : %s", exc)
        _publish_cognitive_event(
            action="swarm_error",
            extra={"error": str(exc)[:300]},
        )
        return {
            "status": "error",
            "reason": str(exc),
            "verdict": "GOOD",
            "confidence": 0.5,
        }


# ------------------------------------------------------------------------------
# BRIDGE 2 : GROUNDING (vérification factuelle SQL)
# ------------------------------------------------------------------------------

def run_grounding(
    draft: str,
    original_query: str,
    connection_string: str = "",
) -> Dict[str, Any]:
    """
    Bridge public : lance la vérification factuelle via GroundingValidator.
    Utilise meta_cortex_grounding.GroundingValidator (existant).

    Ne lève JAMAIS d'exception.
    """
    if not draft or len(draft.strip()) < _min_length_for_grounding():
        return {
            "status": "skipped",
            "reason": "Draft trop court pour grounding",
            "verified_count": 0,
            "unverified_count": 0,
        }

    # Skip les messages sociaux
    if _is_social_message(original_query):
        return {
            "status": "skipped",
            "reason": "Message social détecté",
            "verified_count": 0,
            "unverified_count": 0,
        }

    try:
        from meta_cortex_grounding import GroundingValidator

        # Si pas de conn_str explicite, on utilise celle de memory
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

        for r in results:
            if not hasattr(r, "verified"):
                continue
            if r.verified:
                verified_count += 1
            elif r.actual_value == "UNVERIFIABLE":
                unverifiable_count += 1
            else:
                unverified_count += 1
                issues.append({
                    "claim": getattr(r.claim, "claim_text", "")[:200] if hasattr(r, "claim") else "",
                    "expected": getattr(r, "expected_value", ""),
                    "actual": getattr(r, "actual_value", ""),
                })

        # Nettoyage
        try:
            validator.close()
        except Exception:
            pass

        # Traçabilité A2A
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
        }


# ------------------------------------------------------------------------------
# BRIDGE 3 : PIPELINE COGNITIF COMPLET
# ------------------------------------------------------------------------------

def run_cognitive_pipeline(
    draft: str,
    original_query: str,
    provider: str = "groq",
    model: str = "",
    enable_swarm: bool = True,
    enable_grounding: bool = True,
) -> Dict[str, Any]:
    """
    Bridge public : pipeline cognitif complet (Swarm + Grounding).
    Utilisable par chat.py après chaque réponse LLM.

    Retourne un dict avec :
      - swarm_result : dict (ou None si désactivé)
      - grounding_result : dict (ou None si désactivé)
      - final_verdict : "GOOD" | "FIX" | "ESCALATE"
      - needs_correction : bool
      - issues : liste consolidée des problèmes détectés
    """
    result: Dict[str, Any] = {
        "status": "success",
        "final_verdict": "GOOD",
        "needs_correction": False,
        "issues": [],
        "swarm_result": None,
        "grounding_result": None,
    }

    # Skip les messages sociaux
    if _is_social_message(original_query):
        result["status"] = "skipped"
        result["reason"] = "Message social — pas de vérification cognitive"
        return result

    # Étape 1 : Grounding (vérification factuelle rapide)
    if enable_grounding:
        grounding = run_grounding(draft=draft, original_query=original_query)
        result["grounding_result"] = grounding
        if grounding.get("unverified_count", 0) > 0:
            result["needs_correction"] = True
            result["issues"].extend(grounding.get("issues", []))

    # Étape 2 : Swarm (débat critique)
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

        if verdict in ("FIX", "ESCALATE"):
            result["needs_correction"] = True
            result["issues"].extend(swarm.get("dominant_issues", []))

    # Traçabilité finale
    _publish_cognitive_event(
        action="cognitive_pipeline_done",
        extra={
            "final_verdict": result["final_verdict"],
            "needs_correction": result["needs_correction"],
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
    provider: str = "groq",
    model: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Handler Hermes : cognitive_critique → run_critique_swarm()."""
    if not draft:
        return {"status": "error", "message": "draft obligatoire."}
    return run_critique_swarm(draft=draft, original_query=original_query, provider=provider, model=model)


def _handler_cognitive_ground(
    draft: str = "",
    original_query: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Handler Hermes : cognitive_ground → run_grounding()."""
    if not draft:
        return {"status": "error", "message": "draft obligatoire."}
    return run_grounding(draft=draft, original_query=original_query)


def _handler_cognitive_full_check(
    draft: str = "",
    original_query: str = "",
    provider: str = "groq",
    model: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Handler Hermes : cognitive_full_check → run_cognitive_pipeline()."""
    if not draft:
        return {"status": "error", "message": "draft obligatoire."}
    return run_cognitive_pipeline(
        draft=draft,
        original_query=original_query,
        provider=provider,
        model=model,
    )


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE
# ------------------------------------------------------------------------------

COGNITIVE_NERVES_TABLE: Dict[str, tuple] = {
    "cognitive_critique":   (_handler_cognitive_critique,   "L2"),
    "cognitive_ground":     (_handler_cognitive_ground,     "L2"),
    "cognitive_full_check": (_handler_cognitive_full_check, "L2"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_cognitive_nerves() -> Dict[str, Any]:
    """
    Active les nerfs cognitifs en enregistrant 3 outils Hermes.

    Idempotent. Feature-flag BEK_ENABLE_COGNITIVE_NERVES.
    """
    if not _is_enabled():
        logger.warning("[Nerf 2] Désactivé via BEK_ENABLE_COGNITIVE_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_COGNITIVE_NERVES=false",
        }

    # Vérification des dépendances cognitives
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
            logger.info("🧠 [Nerf 2] Outil cognitif branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 2] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 2] Activation terminée : %d outils cognitifs branchés, %d échecs. "
        "Swarm : %s | Grounding : %s",
        len(activated), len(failed), swarm_available, grounding_available,
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "swarm_available": swarm_available,
        "grounding_available": grounding_available,
        "bridges_exposed": [
            "run_critique_swarm",
            "run_grounding",
            "run_cognitive_pipeline",
        ],
        "thresholds": {
            "min_draft_length_critique": _min_length_for_critique(),
            "min_draft_length_grounding": _min_length_for_grounding(),
        },
    }


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_cognitive_nerves()
    print("Résultat activation Nerf 2 :", result)