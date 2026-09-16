# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 8 — SKILLS CHARGÉS AU BOOT (nerves/skills_nerves.py)
# ------------------------------------------------------------------------------
# Sans ce nerf :
#   - skill_registry.skills reste vide {}
#   - hermes.goap_planner() → skill_registry.search_skills() → retourne []
#   - Hermes ne peut JAMAIS router vers un skill
#
# Avec ce nerf :
#   - skill_registry.load_skills() est appelé au démarrage
#   - Tous les skills des dossiers SKILLS_DIR et FALLBACK_SKILLS_DIR sont chargés
#   - Hermes peut router intelligemment vers les skills adaptés
#
# RÈGLES D'OR :
#   - Aucune modification de skill_registry.py
#   - Aucune modification de hermes_core.py
#   - On utilise UNIQUEMENT l'API publique existante (load_skills, _initialized)
#   - Feature-flag : BEK_ENABLE_SKILLS_NERVES (défaut true)
#   - Idempotent : appelable plusieurs fois sans effet de bord
# ==============================================================================

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger("bek.nerves.skills")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    """Vérifie si le Nerf 8 est activé (par défaut : oui)."""
    return os.getenv("BEK_ENABLE_SKILLS_NERVES", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_skills_nerves() -> Dict[str, Any]:
    """
    Charge le SkillRegistry au démarrage pour que Hermes GOAP puisse
    utiliser les compétences disponibles.

    Idempotent : peut être appelé plusieurs fois sans effet de bord
    (le registre vérifie son propre flag _initialized).

    Retourne un rapport structuré.
    """
    if not _is_enabled():
        logger.warning("[Nerf 8] Désactivé via BEK_ENABLE_SKILLS_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_SKILLS_NERVES=false",
        }

    try:
        from skill_registry import skill_registry
    except ImportError as exc:
        logger.error("[Nerf 8] Impossible d'importer skill_registry : %s", exc)
        return {"status": "error", "message": str(exc)}

    # Vérification de l'état AVANT chargement
    already_loaded = getattr(skill_registry, "_initialized", False)
    skills_before = len(getattr(skill_registry, "skills", {}) or {})

    try:
        # load_skills() est idempotent et thread-safe (RLock dans le registry)
        count = skill_registry.load_skills()
    except Exception as exc:
        logger.error("[Nerf 8] Erreur chargement skills : %s", exc)
        return {"status": "error", "message": str(exc)}

    skills_after = len(getattr(skill_registry, "skills", {}) or {})
    directories: List[str] = []
    try:
        directories = [str(d) for d in getattr(skill_registry, "directories", [])]
    except Exception:
        pass

    if already_loaded:
        logger.info(
            "🧠 [Nerf 8] Skill Registry déjà chargé (idempotent). %d skills actifs.",
            skills_after,
        )
    else:
        logger.info(
            "🧠 [Nerf 8] Skill Registry chargé au boot : %d skills actifs.",
            skills_after,
        )

    # Compteur optionnel : combien de skills réellement utilisables (enabled=True)
    enabled_count = 0
    try:
        for skill in (skill_registry.skills or {}).values():
            if getattr(skill, "enabled", False):
                enabled_count += 1
    except Exception:
        enabled_count = count

    return {
        "status": "ok",
        "skills_loaded": count,
        "skills_enabled": enabled_count,
        "skills_before": skills_before,
        "skills_after": skills_after,
        "was_already_initialized": already_loaded,
        "directories": directories,
    }


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_skills_nerves()
    print("Résultat activation Nerf 8 :", result)