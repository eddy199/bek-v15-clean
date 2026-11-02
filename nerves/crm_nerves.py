# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 10 — CRM → HERMES (Stub de compatibilité)
# ------------------------------------------------------------------------------
# 🏛️ Rôle : Ce fichier existe uniquement pour satisfaire le diagnostic
#            d'architecture (ArchiGen) qui vérifie la présence physique de
#            tous les fichiers nerfs.
#
# ⚠️ IMPORTANT : L'activation réelle du CRM est contrôlée par la variable
#               d'environnement `BEK_ENABLE_CRM_NERVES`. 
#               Par défaut, elle est à `false` (désactivée).
#
# 🔧 Pour activer le CRM plus tard :
#    1. Remplacer ce contenu par la vraie logique CRM.
#    2. Ajouter `BEK_ENABLE_CRM_NERVES=true` dans `env.txt`.
# ==============================================================================

from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger("bek.nerves.crm")


def _is_enabled() -> bool:
    """Vérifie si le Nerf 10 (CRM) est activé (par défaut : non)."""
    return os.getenv("BEK_ENABLE_CRM_NERVES", "false").lower() in ("true", "1", "yes")


def activate_crm_nerves() -> Dict[str, Any]:
    """
    Point d'entrée d'activation du Nerf 10.
    
    Puisque ce n'est qu'un stub, cette fonction se contente de vérifier
    le flag et de renvoyer un statut. Elle est appelée par app.py au démarrage.
    
    Returns:
        dict: Statut d'activation (toujours "disabled" pour l'instant).
    """
    if not _is_enabled():
        logger.debug("[Nerf 10] CRM désactivé (BEK_ENABLE_CRM_NERVES=false)")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_CRM_NERVES=false",
            "tool": "crm_nerves",
        }
    
    # Si un jour le flag est à true, on branchera ici les vrais outils CRM
    logger.warning(
        "[Nerf 10] ⚠️ BEK_ENABLE_CRM_NERVES=true mais le module n'est qu'un stub. "
        "Veuillez implémenter la vraie logique CRM dans nerves/crm_nerves.py."
    )
    return {
        "status": "stub_only",
        "reason": "Le flag est true mais aucune logique n'est implémentée.",
        "tool": "crm_nerves",
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEST DIRECT (optionnel)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    result = activate_crm_nerves()
    print("Résultat activation Nerf 10 (CRM) :", result)