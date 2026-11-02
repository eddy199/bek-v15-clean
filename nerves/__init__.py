# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 HYBRID — SYSTÈME NERVEUX (nerves/__init__.py)
# ------------------------------------------------------------------------------
# Ce paquet contient les "nerfs" qui relient les briques existantes de BEK.
#
# Chaque nerf est un module indépendant, additif, qui active une connexion
# entre deux briques existantes SANS les modifier.
#
# RÈGLES D'OR DE CE PAQUET :
#   - Aucune brique existante n'est supprimée
#   - Aucune brique existante n'est modifiée en profondeur
#   - Chaque nerf est activable/désactivable via feature-flag (env.txt)
#   - Zéro régression garantie
#
# Chantier 1 : Nerf 1 (Hermes réel) + Nerf 8 (Skills chargés au boot)
# Chantier 2 : Nerf 11-13 (Headless relié à Hermes + WebAgent + EventBus)
# Chantier 3 : Nerf 14-17 (Tmux relié à Hermes + EventBus + Guardian + Sub-CRM)
# Chantier 4 : Nerf 3 (EventBus unifié) + Nerf 4 (WebAgent tracé) + Nerf 9 (Guardian tracé)
# Chantier 5 : Nerf 5 (Approval Manager) + Nerf 6 (MCP Gateway ↔ Hermes)
# Chantier 6 : Nerf 2 (Cortex cognitif) + Nerf 7 (SmartRouter) + Nerf 10 (Sub-CRM → Hermes)
# ==============================================================================

__version__ = "16.0-nerves"
__author__ = "BEK Architecture"

__all__ = [
    # Chantier 1 — Fondations
    "hermes_nerves",
    "skills_nerves",
    # Chantier 2 — Headless
    "headless_nerves",
    # Chantier 3 — Tmux / Tâches de fond
    "tmux_nerves",
    # Chantier 4 — EventBus unifié & Traçabilité A2A
    "event_bus_nerves",
    "web_agent_nerves",
    "guardian_nerves",
    # Chantier 5 — Gouvernance & Interopérabilité
    "approval_nerves",
    "mcp_nerves",
    # Chantier 6 — Couche AGI cognitive
    "cognitive_nerves",
    "router_nerves",
    "crm_nerves",
]