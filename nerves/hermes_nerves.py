# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 1 — HERMES → ORGANES RÉELS (nerves/hermes_nerves.py)
# ------------------------------------------------------------------------------
# ★ AJOUT v3 : Prise en charge de save_memory (gestion des dictionnaires)
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
# HANDLERS RÉELS
# ------------------------------------------------------------------------------

def _handler_web_sync(query: str = "", **kwargs: Any) -> Dict[str, Any]:
    if not query:
        return {"status": "error", "message": "La requête web_sync est vide."}
    try:
        from services.action_executor import execute_agent_action
        return execute_agent_action("web_sync", {"query": query, **kwargs})
    except Exception as exc:
        logger.error("[Nerf web_sync] Erreur : %s", exc)
        return {"status": "error", "message": f"web_sync échoué : {exc}"}


def _handler_orchestrate(goal: str = "", **kwargs: Any) -> Dict[str, Any]:
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
    if not prompt:
        return {"status": "error", "message": "Le prompt est obligatoire."}
    try:
        from services.vision import generate_image_with_provider
        return generate_image_with_provider(prompt=prompt)
    except Exception as exc:
        logger.error("[Nerf generate_image] Erreur : %s", exc)
        return {"status": "error", "message": f"generate_image échoué : {exc}"}


def _handler_edit_image(image_paths: Any = None, prompt: str = "", user_prompt: str = "", **kwargs: Any) -> Dict[str, Any]:
    active_prompt = user_prompt or prompt
    if not active_prompt:
        return {"status": "error", "message": "Le prompt d'édition est obligatoire."}
    try:
        from services.vision import merge_and_edit_images
        return merge_and_edit_images(image_paths=image_paths, user_prompt=active_prompt)
    except Exception as exc:
        logger.error("[Nerf edit_image] Erreur : %s", exc)
        return {"status": "error", "message": f"edit_image échoué : {exc}"}


def _handler_generate_video(prompt: str = "", **kwargs: Any) -> Dict[str, Any]:
    if not prompt:
        return {"status": "error", "message": "Le prompt vidéo est obligatoire."}
    try:
        from services.vision import generate_video_with_provider
        return generate_video_with_provider(prompt=prompt)
    except Exception as exc:
        logger.error("[Nerf generate_video] Erreur : %s", exc)
        return {"status": "error", "message": f"generate_video échoué : {exc}"}


def _handler_edit_video(video_paths: Any = None, prompt: str = "", user_prompt: str = "", **kwargs: Any) -> Dict[str, Any]:
    active_prompt = user_prompt or prompt
    if not active_prompt:
        return {"status": "error", "message": "Le prompt d'édition vidéo est obligatoire."}
    try:
        from services.vision import merge_and_edit_videos
        return merge_and_edit_videos(video_paths=video_paths, user_prompt=active_prompt)
    except Exception as exc:
        logger.error("[Nerf edit_video] Erreur : %s", exc)
        return {"status": "error", "message": f"edit_video échoué : {exc}"}


def _handler_headless_scrape(url: str = "", **kwargs: Any) -> Dict[str, Any]:
    if not url:
        return {"status": "error", "message": "L'URL est obligatoire pour headless_scrape."}
    try:
        from worker_headless import HeadlessWorker
        worker = HeadlessWorker(headless=True)
        result = run_async_safely(worker.fetch_page_content(url))
        if result is None:
            return {"status": "error", "message": "headless_scrape : aucun résultat (timeout ou erreur)."}
        return result
    except Exception as exc:
        logger.error("[Nerf headless_scrape] Erreur : %s", exc)
        return {"status": "error", "message": f"headless_scrape échoué : {exc}"}


# ★ NOUVEAU : Handler de mémoire robuste (accepte strings et dictionnaires)
def _handler_save_memory(content: Any = None, text: Any = None, data: Any = None, **kwargs: Any) -> Dict[str, Any]:
    """
    Nerf : Hermes.save_memory → memory.save_to_memory.
    Gère les dictionnaires malformés du LLM en les convertissant en texte brut.
    """
    raw = content or text or data
    if not raw and kwargs:
        # Si le LLM a envoyé {"name": "Mohamed", "project": "BEK-v19"}
        raw = kwargs

    if not raw:
        return {"status": "error", "message": "Le contenu à mémoriser ne peut pas être vide."}

    # Si c'est un dictionnaire, on le convertit en texte lisible
    if isinstance(raw, dict):
        text_to_save = " ; ".join(f"{k}: {v}" for k, v in raw.items())
    elif isinstance(raw, list):
        text_to_save = ", ".join(str(item) for item in raw)
    else:
        text_to_save = str(raw).strip()

    if not text_to_save:
        return {"status": "error", "message": "Le contenu à mémoriser ne peut pas être vide."}

    try:
        from memory import save_to_memory
        save_to_memory(text_to_save)
        return {"status": "success", "message": f"✅ Mémorisé : {text_to_save}"}
    except Exception as exc:
        logger.error("[Nerf save_memory] Erreur : %s", exc)
        return {"status": "error", "message": f"save_memory échoué : {exc}"}


# ------------------------------------------------------------------------------
# TABLE DE CORRESPONDANCE
# ------------------------------------------------------------------------------

NERVES_TABLE: Dict[str, tuple] = {
    "web_sync":        (_handler_web_sync,        "L2"),
    "orchestrate":     (_handler_orchestrate,     "L2"),
    "neon_audit":      (_handler_neon_audit,      "L1"),
    "generate_image":  (_handler_generate_image,  "L1"),
    "edit_image":      (_handler_edit_image,      "L1"),
    "generate_video":  (_handler_generate_video,  "L1"),
    "edit_video":      (_handler_edit_video,      "L1"),
    "headless_scrape": (_handler_headless_scrape, "L2"),
    # ★ AJOUT : On branche save_memory ici
    "save_memory":     (_handler_save_memory,     "L1"),
}

# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

def activate_hermes_nerves() -> Dict[str, Any]:
    if not _is_enabled():
        logger.warning("[Nerf 1] Désactivé via BEK_ENABLE_HERMES_NERVES=false")
        return {"status": "disabled", "reason": "Feature-flag BEK_ENABLE_HERMES_NERVES=false"}

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

    logger.info("✅ [Nerf 1] Activation terminée : %d outils réels branchés, %d échecs.", len(activated), len(failed))

    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "async_utils_module": "nerves._async_utils",
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = activate_hermes_nerves()
    print("Résultat activation Nerf 1 :", result)