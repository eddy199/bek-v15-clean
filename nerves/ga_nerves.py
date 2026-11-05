# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 20 — BEK-GA : Moteur génétique auto-évolutif (CPU only, 0 VRAM)
# ------------------------------------------------------------------------------
# Ce nerf branche le moteur génétique BEK-GA sur Hermes.
# Il expose 3 outils :
#   - ga_get_best        : récupère le meilleur gène (prompt/config) actuel
#   - ga_record_result   : enregistre le résultat d'une exécution (fitness)
#   - ga_evolve          : déclenche une nouvelle génération (mutation)
# ==============================================================================

from __future__ import annotations

import logging
from typing import Any, Dict

from bek_ga_light import BEKGeneticEngineCPU

logger = logging.getLogger("bek.nerves.ga")

# Instance unique (singleton) du moteur génétique
_engine = None


def get_ga_engine() -> BEKGeneticEngineCPU:
    """Retourne l'instance unique du moteur génétique (lazy init)."""
    global _engine
    if _engine is None:
        _engine = BEKGeneticEngineCPU(population_size=4, mutation_rate=0.2)
        logger.info("[Nerf 20] Moteur génétique BEK-GA initialisé.")
    return _engine


# ------------------------------------------------------------------------------
# HANDLERS HERMES
# ------------------------------------------------------------------------------

def _handler_ga_get_best(**kwargs: Any) -> Dict[str, Any]:
    """Récupère le meilleur neurone (prompt/config) actuel."""
    try:
        engine = get_ga_engine()
        best = engine.select_best_gene()
        return {
            "status": "success",
            "gene_id": best.gene_id,
            "prompt_template": best.prompt_template,
            "max_tokens": best.max_tokens,
            "temperature": best.temperature,
            "fitness": best.fitness,
        }
    except Exception as exc:
        logger.error("[Nerf 20] ga_get_best échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_ga_record_result(
    gene_id: str = "",
    success: bool = False,
    execution_time_ms: float = 0.0,
    tokens_used: int = 0,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Enregistre le résultat d'une exécution pour calculer la fitness."""
    if not gene_id:
        return {"status": "error", "message": "gene_id obligatoire."}
    try:
        engine = get_ga_engine()
        gene = next((g for g in engine.population if g.gene_id == gene_id), None)
        if not gene:
            return {"status": "error", "message": f"Gène introuvable : {gene_id}"}

        fitness = engine.calculate_fitness(
            gene=gene,
            success=success,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
        )
        return {
            "status": "success",
            "gene_id": gene_id,
            "fitness": fitness,
            "success": success,
        }
    except Exception as exc:
        logger.error("[Nerf 20] ga_record_result échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_ga_evolve(**kwargs: Any) -> Dict[str, Any]:
    """Déclenche une nouvelle génération (croisement + mutation)."""
    try:
        engine = get_ga_engine()
        engine.evolve()
        best = engine.select_best_gene()
        return {
            "status": "success",
            "message": "Nouvelle génération évoluée.",
            "best_gene_id": best.gene_id,
            "best_fitness": best.fitness,
        }
    except Exception as exc:
        logger.error("[Nerf 20] ga_evolve échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE
# ------------------------------------------------------------------------------

GA_NERVES_TABLE: Dict[str, tuple] = {
    "ga_get_best":      (_handler_ga_get_best,      "L1"),
    "ga_record_result": (_handler_ga_record_result, "L2"),
    "ga_evolve":        (_handler_ga_evolve,        "L2"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_ga_nerves() -> Dict[str, Any]:
    """Active le nerf BEK-GA en enregistrant ses outils dans Hermes."""
    try:
        from hermes_core import hermes
    except ImportError as exc:
        logger.error("[Nerf 20] hermes_core introuvable : %s", exc)
        return {"status": "error", "message": str(exc)}

    activated = []
    failed = []

    for tool_name, (handler, risk_level) in GA_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("🧬 [Nerf 20] Outil GA branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 20] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 20] Activation terminée : %d outils GA branchés, %d échecs.",
        len(activated), len(failed),
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_ga_nerves()
    print("Résultat activation Nerf 20 :", result)