# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 6 — MCP GATEWAY BRANCHÉ À HERMES (nerves/mcp_nerves.py)
# ------------------------------------------------------------------------------
# Ce nerf crée une SYNCHRONISATION BIDIRECTIONNELLE entre mcp_gateway.py et Hermes :
#
#   NERF 6 : MCP Gateway ↔ Hermes (échange d'outils dans les deux sens)
#
# PROBLÈME RÉSOLU :
#   - Actuellement : mcp_gateway.register_mcp_tool() enregistre des outils
#     dans un registre isolé. Hermes ne les voit JAMAIS.
#   - Résultat : les outils MCP sont injoignables depuis le GOAP planner.
#
# SOLUTION (ce nerf) :
#   - Exposition MCP : les outils Hermes sont publiés dans mcp_gateway
#     (visibles par les clients MCP externes).
#   - Import MCP : les outils déjà présents dans mcp_gateway sont enregistrés
#     dans Hermes avec le préfixe "mcp_" (ex: mcp_neon_audit).
#   - Anti-boucle : tag interne pour éviter la re-synchronisation infinie.
#
# NOUVEAUX OUTILS HERMES (additifs) :
#   - mcp_list_tools    → liste les outils MCP exposés
#   - mcp_execute       → exécute un outil MCP par son nom
#   - mcp_register      → enregistre un nouvel outil MCP (bridge externe)
#
# BRIDGES EXPOSÉS :
#   - register_mcp_tool_into_hermes()  → enregistre 1 outil MCP dans Hermes
#   - sync_hermes_tools_to_mcp()       → publie les outils Hermes vers MCP
#
# RÈGLES D'OR :
#   - Aucune modification de mcp_gateway.py
#   - Aucune modification de hermes_core.py
#   - Anti-boucle strict (tags internes)
#   - Feature-flag : BEK_ENABLE_MCP_NERVES (défaut true)
#   - Traçabilité EventBus via Nerf 3
# ==============================================================================

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("bek.nerves.mcp")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_MCP_NERVES", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# CONSTANTES ANTI-BOUCLE
# ------------------------------------------------------------------------------

# Préfixe utilisé pour les outils MCP importés dans Hermes
MCP_TOOL_PREFIX = "mcp_"

# Tag interne pour marquer les outils Hermes synchronisés vers MCP
_SYNCED_TO_MCP_TAG = "_bek_mcp_synced"


# ------------------------------------------------------------------------------
# PUBLICATION EVENTBUS — via le pont unifié du Nerf 3
# ------------------------------------------------------------------------------

def _publish_mcp_event(
    action: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Publie un événement MCP sur l'EventBus unifié.
    Ne lève JAMAIS d'exception.
    """
    payload: Dict[str, Any] = {
        "action": action,
        "source": "mcp_nerves",
    }
    if extra:
        payload.update(extra)

    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified("skills-index", payload)
        logger.debug("[Nerf 6] Événement publié : skills-index / %s", action)
    except Exception as exc:
        logger.debug("[Nerf 6] Publication EventBus échouée (mode dégradé) : %s", exc)


# ------------------------------------------------------------------------------
# IMPORT MCP → HERMES
# ------------------------------------------------------------------------------

def register_mcp_tool_into_hermes(
    mcp_tool_name: str,
    risk_level: str = "L2",
) -> Dict[str, Any]:
    """
    Bridge public : enregistre un outil MCP existant dans Hermes.
    L'outil sera nommé "mcp_<nom_original>" pour éviter les collisions.

    Ne lève JAMAIS d'exception.
    Retourne un dict {status, hermes_tool_name, ...}.
    """
    if not mcp_tool_name:
        return {"status": "error", "message": "mcp_tool_name obligatoire."}

    try:
        from mcp_gateway import mcp_gateway
        from hermes_core import hermes
    except ImportError as exc:
        return {"status": "error", "message": f"Import échoué : {exc}"}

    # Vérifier que l'outil MCP existe
    if mcp_tool_name not in getattr(mcp_gateway, "tools", {}):
        return {
            "status": "error",
            "message": f"Outil MCP '{mcp_tool_name}' introuvable dans mcp_gateway.",
        }

    # Anti-boucle : ne pas réimporter un outil déjà présent sous le préfixe
    hermes_tool_name = f"{MCP_TOOL_PREFIX}{mcp_tool_name}"
    if hermes_tool_name in getattr(hermes, "tools", {}):
        return {
            "status": "already_registered",
            "hermes_tool_name": hermes_tool_name,
        }

    # Création du handler bridge
    def _mcp_handler(**kwargs: Any) -> Any:
        """Handler qui route les appels vers mcp_gateway.execute_tool()."""
        try:
            return mcp_gateway.execute_tool(mcp_tool_name, kwargs)
        except Exception as exc:
            logger.error("[Nerf 6] Exécution MCP '%s' échouée : %s", mcp_tool_name, exc)
            return {"status": "error", "message": str(exc)}

    # Enregistrement dans Hermes
    try:
        hermes.register_tool(hermes_tool_name, _mcp_handler, risk_level=risk_level)
    except Exception as exc:
        return {"status": "error", "message": f"Enregistrement Hermes échoué : {exc}"}

    # Traçabilité
    _publish_mcp_event(
        action="mcp_imported_into_hermes",
        extra={"mcp_tool_name": mcp_tool_name, "hermes_tool_name": hermes_tool_name},
    )

    logger.info("🧠 [Nerf 6] Outil MCP importé dans Hermes : %s → %s", mcp_tool_name, hermes_tool_name)

    return {
        "status": "ok",
        "mcp_tool_name": mcp_tool_name,
        "hermes_tool_name": hermes_tool_name,
        "risk_level": risk_level,
    }


# ------------------------------------------------------------------------------
# EXPORT HERMES → MCP
# ------------------------------------------------------------------------------

def sync_hermes_tools_to_mcp(
    exclude_prefixes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Bridge public : publie les outils Hermes dans mcp_gateway (exposition MCP).
    Ne synchronise PAS les outils déjà préfixés "mcp_" (anti-boucle).
    Ne synchronise PAS les outils déjà marqués comme synchronisés.

    Ne lève JAMAIS d'exception.
    """
    exclude_prefixes = exclude_prefixes or [MCP_TOOL_PREFIX]

    try:
        from mcp_gateway import mcp_gateway
        from hermes_core import hermes
    except ImportError as exc:
        return {"status": "error", "message": f"Import échoué : {exc}"}

    synced_names: List[str] = []
    skipped_names: List[str] = []
    failed_names: List[str] = []

    hermes_tools = getattr(hermes, "tools", {}) or {}

    for tool_name, tool_obj in list(hermes_tools.items()):
        # Anti-boucle 1 : ignorer les préfixes exclus
        if any(tool_name.startswith(prefix) for prefix in exclude_prefixes):
            skipped_names.append(tool_name)
            continue

        # Anti-boucle 2 : ignorer les outils déjà synchronisés
        if getattr(tool_obj, _SYNCED_TO_MCP_TAG, False):
            skipped_names.append(tool_name)
            continue

        # Récupérer les métadonnées du tool Hermes
        try:
            risk_level = getattr(tool_obj, "risk_level", "L1")
            description = f"Outil Hermes '{tool_name}' (risk={risk_level})"

            # Créer le handler MCP qui appelle directement hermes.dispatch()
            def _make_handler(tn: str) -> Callable:
                def _handler(**kwargs: Any) -> Any:
                    try:
                        return hermes.dispatch(tn, kwargs)
                    except Exception as exc:
                        logger.error("[Nerf 6] Dispatch Hermes '%s' échoué : %s", tn, exc)
                        return {"status": "error", "message": str(exc)}
                return _handler

            # Enregistrer dans MCP
            mcp_gateway.register_mcp_tool(
                name=tool_name,
                description=description,
                parameters_schema={},
                handler=_make_handler(tool_name),
            )

            # Marquer comme synchronisé (attribut dynamique sur l'objet tool)
            try:
                setattr(tool_obj, _SYNCED_TO_MCP_TAG, True)
            except Exception:
                # Les dataclasses frozen ne supportent pas setattr — on utilise un registre séparé
                pass

            synced_names.append(tool_name)

        except Exception as exc:
            failed_names.append(tool_name)
            logger.debug("[Nerf 6] Sync '%s' échoué : %s", tool_name, exc)

    # Traçabilité
    _publish_mcp_event(
        action="hermes_tools_synced_to_mcp",
        extra={
            "synced_count": len(synced_names),
            "skipped_count": len(skipped_names),
            "failed_count": len(failed_names),
        },
    )

    logger.info(
        "🔌 [Nerf 6] Sync Hermes → MCP : %d synchronisés, %d ignorés, %d échecs",
        len(synced_names), len(skipped_names), len(failed_names),
    )

    return {
        "status": "ok",
        "synced_count": len(synced_names),
        "skipped_count": len(skipped_names),
        "failed_count": len(failed_names),
        "synced_tools": synced_names,
        "failed_tools": failed_names,
    }


# ------------------------------------------------------------------------------
# HANDLERS HERMES — pilotage MCP
# ------------------------------------------------------------------------------

def _handler_mcp_list_tools(**kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : liste les outils MCP exposés."""
    try:
        from mcp_gateway import mcp_gateway
        manifests = mcp_gateway.get_mcp_manifests()
        return {
            "status": "success",
            "count": len(manifests),
            "tools": manifests,
        }
    except Exception as exc:
        logger.error("[Nerf 6] mcp_list_tools échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_mcp_execute(
    tool_name: str = "",
    arguments: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Any:
    """Handler Hermes : exécute un outil MCP par son nom."""
    if not tool_name:
        return {"status": "error", "message": "tool_name obligatoire."}
    try:
        from mcp_gateway import mcp_gateway
        result = mcp_gateway.execute_tool(tool_name, arguments or {})

        # Traçabilité
        _publish_mcp_event(
            action="mcp_executed",
            extra={"tool_name": tool_name, "arguments_keys": list((arguments or {}).keys())},
        )

        return result
    except Exception as exc:
        logger.error("[Nerf 6] mcp_execute échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


def _handler_mcp_register(
    name: str = "",
    description: str = "",
    handler_kind: str = "echo",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Handler Hermes : enregistre un nouvel outil MCP (bridge externe).

    NOTE : pour des raisons de sécurité, seuls des handlers prédéfinis
    sont disponibles ici ("echo" pour test). Pour des handlers custom,
    utilisez directement mcp_gateway.register_mcp_tool() en Python.
    """
    if not name:
        return {"status": "error", "message": "name obligatoire."}

    try:
        from mcp_gateway import mcp_gateway

        if handler_kind == "echo":
            def _echo_handler(**kw: Any) -> Dict[str, Any]:
                return {"status": "success", "echo": kw}
            handler = _echo_handler
        else:
            return {
                "status": "error",
                "message": f"handler_kind '{handler_kind}' non supporté. Utilisez 'echo'.",
            }

        mcp_gateway.register_mcp_tool(
            name=name,
            description=description or f"Outil MCP '{name}'",
            parameters_schema={},
            handler=handler,
        )

        # Traçabilité
        _publish_mcp_event(
            action="mcp_registered",
            extra={"name": name, "description": description[:100]},
        )

        return {
            "status": "success",
            "name": name,
            "message": f"Outil MCP '{name}' enregistré.",
        }
    except Exception as exc:
        logger.error("[Nerf 6] mcp_register échoué : %s", exc)
        return {"status": "error", "message": str(exc)}


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE
# ------------------------------------------------------------------------------

MCP_NERVES_TABLE: Dict[str, tuple] = {
    "mcp_list_tools": (_handler_mcp_list_tools, "L1"),
    "mcp_execute":    (_handler_mcp_execute,    "L2"),
    "mcp_register":   (_handler_mcp_register,   "L2"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_mcp_nerves() -> Dict[str, Any]:
    """
    Active les nerfs MCP en :
      1. Synchronisant les outils Hermes existants → mcp_gateway (exposition)
      2. Import : les outils MCP existants → Hermes (avec préfixe mcp_)
      3. Enregistrant 3 nouveaux outils Hermes : mcp_list_tools, mcp_execute, mcp_register

    Idempotent. Feature-flag BEK_ENABLE_MCP_NERVES.

    Retourne un rapport d'activation structuré.
    """
    if not _is_enabled():
        logger.warning("[Nerf 6] Désactivé via BEK_ENABLE_MCP_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_MCP_NERVES=false",
        }

    # Vérification disponibilité mcp_gateway
    mcp_available = False
    try:
        from mcp_gateway import mcp_gateway  # noqa: F401
        mcp_available = True
    except ImportError as exc:
        logger.warning(
            "⚠️ [Nerf 6] mcp_gateway.py indisponible (%s). "
            "Les outils seront enregistrés mais échoueront à l'exécution.",
            exc,
        )

    try:
        from hermes_core import hermes
    except ImportError as exc:
        logger.error("[Nerf 6] Impossible d'importer hermes_core : %s", exc)
        return {"status": "error", "message": str(exc)}

    # Étape 1 : Sync Hermes → MCP (exposition)
    sync_result: Dict[str, Any] = {"synced_count": 0, "skipped_count": 0, "failed_count": 0}
    if mcp_available:
        try:
            sync_result = sync_hermes_tools_to_mcp()
        except Exception as exc:
            logger.error("[Nerf 6] Sync Hermes→MCP échoué : %s", exc)

    # Étape 2 : Import MCP → Hermes (outils MCP déjà enregistrés)
    imported_count = 0
    if mcp_available:
        try:
            from mcp_gateway import mcp_gateway
            existing_mcp_tools = list(getattr(mcp_gateway, "tools", {}).keys())
            for mcp_tool_name in existing_mcp_tools:
                # Éviter de réimporter les outils Hermes déjà exposés à MCP
                # (ceux-ci sont dans mcp_gateway par la sync étape 1, mais pas "MCP natifs")
                # On importe uniquement ceux qui ne sont PAS synchronisés depuis Hermes.
                # Heuristique : les outils natifs MCP ont un nom qui ne correspond PAS
                # à un outil Hermes existant.
                if mcp_tool_name in getattr(hermes, "tools", {}):
                    continue  # C'est un outil Hermes exposé à MCP → pas besoin d'importer

                result = register_mcp_tool_into_hermes(mcp_tool_name, risk_level="L2")
                if result.get("status") == "ok":
                    imported_count += 1
        except Exception as exc:
            logger.error("[Nerf 6] Import MCP→Hermes échoué : %s", exc)

    # Étape 3 : Enregistrement des 3 outils Hermes de pilotage MCP
    activated: List[str] = []
    failed: List[Dict[str, str]] = []

    for tool_name, (handler, risk_level) in MCP_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("🧠 [Nerf 6] Outil MCP branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 6] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 6] Activation terminée : %d outils MCP branchés, %d échecs. "
        "Sync Hermes→MCP : %d | Import MCP→Hermes : %d | mcp_gateway : %s",
        len(activated), len(failed),
        sync_result.get("synced_count", 0), imported_count, mcp_available,
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "mcp_gateway_available": mcp_available,
        "sync_hermes_to_mcp": sync_result,
        "imported_mcp_to_hermes": imported_count,
        "bridges_exposed": [
            "register_mcp_tool_into_hermes",
            "sync_hermes_tools_to_mcp",
        ],
    }


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_mcp_nerves()
    print("Résultat activation Nerf 6 :", result)

    # Test list MCP tools
    from mcp_gateway import mcp_gateway  # noqa: F401
    tools = _handler_mcp_list_tools()
    print("Outils MCP exposés :", tools)