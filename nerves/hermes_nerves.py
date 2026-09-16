# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 1 — HERMES → ORGANES RÉELS (nerves/hermes_nerves.py)
# ------------------------------------------------------------------------------
# Ce nerf branche les outils Hermes (actuellement des stubs dans
# hermes_core._register_default_tools) sur les VRAIES briques de BEK :
#
#   - web_sync        → services.action_executor → web_agent
#   - orchestrate     → bek_orchestrator
#   - neon_audit      → services.db (requête SQL réelle)
#   - generate_image  → services.vision (utilise VOTRE prompt_optimizer)
#   - edit_image      → services.vision
#   - generate_video  → services.vision
#   - edit_video      → services.vision
#   - headless_scrape → worker_headless (Playwright)
#
# RÈGLES D'OR :
#   - Aucune modification de hermes_core.py
#   - Aucune modification de vision.py ni prompt_optimizer.py
#   - On utilise hermes.register_tool() qui ÉCRASE proprement les stubs
#   - Feature-flag : BEK_ENABLE_HERMES_NERVES (défaut true)
#   - Zéro régression garantie
#
# CORRECTIFS v2 (async robuste) :
#   - headless_scrape utilise run_async_safely (module partagé)
#     → plus de RuntimeError "event loop already running" si Hermes est
#       appelé depuis un contexte async (FastAPI, uvicorn, etc.)
#   - Aucune signature modifiée
# ==============================================================================

from __future__ import annotations

import logging
import os
from typing import Any, Dict

# ── Utilitaire async partagé (module nerves/_async_utils.py) ──
from nerves._async_utils import run_async_safely

logger = logging.getLogger("bek.nerves.hermes")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    """Vérifie si le Nerf 1 est activé (par défaut : oui)."""
    return os.getenv("BEK_ENABLE_HERMES_NERVES", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# HANDLERS RÉELS — chaque handler appelle une brique existante de BEK
# ------------------------------------------------------------------------------

def _handler_web_sync(query: str = "", **kwargs: Any) -> Dict[str, Any]:
    """
    Nerf : Hermes.web_sync → services.action_executor → web_agent.
    Remplace le stub {status: success, synced_query: query} par un VRAI scraping.
    """
    if not query:
        return {"status": "error", "message": "La requête web_sync est vide."}
    try:
        from services.action_executor import execute_agent_crm_tool
        return execute_agent_crm_tool("web_sync", {"query": query, **kwargs})
    except Exception as exc:
        logger.error("[Nerf web_sync] Erreur : %s", exc)
        return {"status": "error", "message": f"web_sync échoué : {exc}"}


def _handler_orchestrate(goal: str = "", **kwargs: Any) -> Dict[str, Any]:
    """
    Nerf : Hermes.orchestrate → bek_orchestrator (AgentMesh + Swarm critique).
    """
    if not goal:
        return {"status": "error", "message": "L'objectif d'orchestration est vide."}
    try:
        from bek_orchestrator import bek_orchestrator
        report = bek_orchestrator.run(goal)
        return {"status": "success", "report": report}
    except Exception as exc:
        logger.error("[Nerf orchestrate] Erreur : %s", exc)
        return {"status": "error", "message": f"orchestrate échoué : {exc}"}


def _handler_neon_audit(**kwargs: Any) -> Dict[str, Any]:
    """
    Nerf : Hermes.neon_audit → services.db (VRAIE requête SQL sur Neon DB).
    Remplace la liste statique par un VRAI audit de votre base.
    """
    try:
        from services.db import execute_database_sql
        result = execute_database_sql(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name;"
        )
        if result.get("status") == "success":
            tables = [row.get("table_name") for row in result.get("data", [])]
            return {
                "status": "success",
                "tables": tables,
                "count": len(tables),
                "message": f"Audit Neon DB : {len(tables)} tables détectées.",
            }
        return {"status": "error", "message": result.get("message", "Échec audit Neon DB.")}
    except Exception as exc:
        logger.error("[Nerf neon_audit] Erreur : %s", exc)
        return {"status": "error", "message": f"neon_audit échoué : {exc}"}


def _handler_generate_image(prompt: str = "", **kwargs: Any) -> Dict[str, Any]:
    """
    Nerf : Hermes.generate_image → services.vision.generate_image_with_provider.
    Utilise VOTRE prompt_optimizer.py existant (styles 3D, cinématique).
    """
    if not prompt:
        return {"status": "error", "message": "Le prompt est obligatoire."}
    try:
        from services.vision import generate_image_with_provider
        return generate_image_with_provider(prompt=prompt)
    except Exception as exc:
        logger.error("[Nerf generate_image] Erreur : %s", exc)
        return {"status": "error", "message": f"generate_image échoué : {exc}"}


def _handler_edit_image(
    image_paths: Any = None,
    prompt: str = "",
    user_prompt: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Nerf : Hermes.edit_image → services.vision.merge_and_edit_images.
    """
    active_prompt = user_prompt or prompt
    if not active_prompt:
        return {"status": "error", "message": "Le prompt d'édition est obligatoire."}
    try:
        from services.vision import merge_and_edit_images
        return merge_and_edit_images(
            image_paths=image_paths,
            user_prompt=active_prompt,
        )
    except Exception as exc:
        logger.error("[Nerf edit_image] Erreur : %s", exc)
        return {"status": "error", "message": f"edit_image échoué : {exc}"}


def _handler_generate_video(prompt: str = "", **kwargs: Any) -> Dict[str, Any]:
    """
    Nerf : Hermes.generate_video → services.vision.generate_video_with_provider.
    Utilise VOTRE prompt_optimizer.py (style cinematic_video).
    """
    if not prompt:
        return {"status": "error", "message": "Le prompt vidéo est obligatoire."}
    try:
        from services.vision import generate_video_with_provider
        return generate_video_with_provider(prompt=prompt)
    except Exception as exc:
        logger.error("[Nerf generate_video] Erreur : %s", exc)
        return {"status": "error", "message": f"generate_video échoué : {exc}"}


def _handler_edit_video(
    video_paths: Any = None,
    prompt: str = "",
    user_prompt: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Nerf : Hermes.edit_video → services.vision.merge_and_edit_videos.
    """
    active_prompt = user_prompt or prompt
    if not active_prompt:
        return {"status": "error", "message": "Le prompt d'édition vidéo est obligatoire."}
    try:
        from services.vision import merge_and_edit_videos
        return merge_and_edit_videos(
            video_paths=video_paths,
            user_prompt=active_prompt,
        )
    except Exception as exc:
        logger.error("[Nerf edit_video] Erreur : %s", exc)
        return {"status": "error", "message": f"edit_video échoué : {exc}"}


def _handler_headless_scrape(url: str = "", **kwargs: Any) -> Dict[str, Any]:
    """
    Nerf : Hermes.headless_scrape → worker_headless.HeadlessWorker (Playwright).
    Permet à Hermes de scraper n'importe quel site, y compris SPA/React/JS lourd.

    CORRECTIF v2 : utilise run_async_safely() du module partagé
    → fonctionne même si Hermes est appelé depuis un contexte async.
    """
    if not url:
        return {"status": "error", "message": "L'URL est obligatoire pour headless_scrape."}
    try:
        from worker_headless import HeadlessWorker

        worker = HeadlessWorker(headless=True)
        # ✅ run_async_safely gère automatiquement le cas "event loop déjà actif"
        result = run_async_safely(worker.fetch_page_content(url))
        if result is None:
            return {"status": "error", "message": "headless_scrape : aucun résultat (timeout ou erreur)."}
        return result
    except Exception as exc:
        logger.error("[Nerf headless_scrape] Erreur : %s", exc)
        return {"status": "error", "message": f"headless_scrape échoué : {exc}"}


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE : nom_outil → (handler_réel, niveau_de_risque)
# ------------------------------------------------------------------------------
# Ces noms correspondent EXACTEMENT aux stubs enregistrés dans hermes_core.py
# L'enregistrement suivant les ÉCRASE proprement (self.tools[name] = tool).
# ------------------------------------------------------------------------------

NERVES_TABLE: Dict[str, tuple] = {
    "web_sync":        (_handler_web_sync,        "L3"),
    "orchestrate":     (_handler_orchestrate,     "L2"),
    "neon_audit":      (_handler_neon_audit,      "L1"),
    "generate_image":  (_handler_generate_image,  "L1"),
    "edit_image":      (_handler_edit_image,      "L1"),
    "generate_video":  (_handler_generate_video,  "L1"),
    "edit_video":      (_handler_edit_video,      "L1"),
    "headless_scrape": (_handler_headless_scrape, "L2"),
}


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_hermes_nerves() -> Dict[str, Any]:
    """
    Active tous les nerfs Hermes en ré-enregistrant les outils avec de VRAIS
    handlers. Écrase silencieusement les stubs par défaut de hermes_core.py.

    Retourne un rapport d'activation structuré.
    """
    if not _is_enabled():
        logger.warning("[Nerf 1] Désactivé via BEK_ENABLE_HERMES_NERVES=false")
        return {
            "status": "disabled",
            "reason": "Feature-flag BEK_ENABLE_HERMES_NERVES=false",
        }

    try:
        from hermes_core import hermes
    except ImportError as exc:
        logger.error("[Nerf 1] Impossible d'importer hermes_core : %s", exc)
        return {"status": "error", "message": str(exc)}

    activated = []
    failed = []

    for tool_name, (handler, risk_level) in NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk_level)
            activated.append(tool_name)
            logger.info("🧠 [Nerf 1] Outil réel branché : %s (risk=%s)", tool_name, risk_level)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 1] Échec branchement %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 1] Activation terminée : %d outils réels branchés, %d échecs.",
        len(activated), len(failed),
    )

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "async_utils_module": "nerves._async_utils",
    }


# ------------------------------------------------------------------------------
# TEST DIRECT (optionnel)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_hermes_nerves()
    print("Résultat activation Nerf 1 :", result)