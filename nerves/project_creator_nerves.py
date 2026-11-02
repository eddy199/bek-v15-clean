# -*- coding: utf-8 -*-
# ==============================================================================
# NERF 19 — PROJECT CREATOR (BEK-v19.12)
# ------------------------------------------------------------------------------
# Permet à BEK de créer des PROJETS COMPLETS :
#   - Applications web (React/Vue/HTML+JS)
#   - Jeux 2D (Canvas, Phaser)
#   - Scripts CLI (Python, Node)
#   - APIs backend (FastAPI, Express)
#   - Landing pages
#
# Utilise la puissance de BEK v19 :
#   - Brain (routing) + ProviderManager (LLM multi-provider)
#   - Memory (contexte projets similaires passés)
#   - Vision (assets placeholder, icônes, sprites)
#   - Skills (templates réutilisables)
#   - EventBus (traçabilité A2A)
#   - codex_agent / codex_editor (si dispo, sinon fallback LLM direct)
#
# RÈGLES D'OR :
#   - Ne casse RIEN à l'existant (Nerf 18 reste intact)
#   - Feature-flag : BEK_ENABLE_PROJECT_CREATOR (défaut true)
#   - Tout dans projects/<slug>/ pour ne pas polluer le workspace
#   - Fallback LLM direct si codex indisponible
# ==============================================================================
from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.nerves.project_creator")


# ------------------------------------------------------------------------------
# FEATURE FLAG
# ------------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("BEK_ENABLE_PROJECT_CREATOR", "true").lower() in ("true", "1", "yes")


# ------------------------------------------------------------------------------
# CONSTANTES — TYPES DE PROJETS
# ------------------------------------------------------------------------------

_PROJECT_TYPES = {
    "web_app": {
        "keywords": ["application web", "app web", "site web", "dashboard",
                     "web app", "react", "vue", "angular", "frontend"],
        "files": ["index.html", "style.css", "app.js"],
        "tech": "HTML5 + CSS + JavaScript vanilla",
    },
    "game_2d": {
        "keywords": ["jeu 2d", "jeu", "game", "canvas", "phaser",
                     "platformer", "shooter", "arcade", "puzzle"],
        "files": ["index.html", "game.js", "style.css"],
        "tech": "HTML5 Canvas 2D + JavaScript",
    },
    "cli_script": {
        "keywords": ["script cli", "script python", "outil ligne de commande",
                     "script bash", "automatisation", "cli"],
        "files": ["main.py", "README.md"],
        "tech": "Python 3.11+ (stdlib uniquement)",
    },
    "api_backend": {
        "keywords": ["api", "backend", "rest", "fastapi", "express",
                     "serveur api", "endpoint"],
        "files": ["main.py", "requirements.txt", "README.md"],
        "tech": "Python FastAPI",
    },
    "landing_page": {
        "keywords": ["landing page", "page d'accueil", "page de vente",
                     "portfolio", "site vitrine"],
        "files": ["index.html", "style.css"],
        "tech": "HTML5 + CSS moderne",
    },
}


# ------------------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convertit un texte en slug de nom de dossier."""
    text = text.lower().strip()
    text = re.sub(r"[àâä]", "a", text)
    text = re.sub(r"[éèêë]", "e", text)
    text = re.sub(r"[îï]", "i", text)
    text = re.sub(r"[ôö]", "o", text)
    text = re.sub(r"[ùûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:40] or "project"


def _detect_project_type(brief: str) -> str:
    """Détecte le type de projet depuis le brief utilisateur."""
    brief_lower = brief.lower()
    scores = {}
    for ptype, config in _PROJECT_TYPES.items():
        score = sum(1 for kw in config["keywords"] if kw in brief_lower)
        if score > 0:
            scores[ptype] = score
    if not scores:
        return "web_app"  # défaut
    return max(scores, key=scores.get)


def _get_projects_root() -> Path:
    """Retourne le dossier racine des projets."""
    from core.paths import WORKSPACE_DIR
    root = Path(WORKSPACE_DIR) / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


# ------------------------------------------------------------------------------
# APPEL LLM (via provider_manager — le même que le chat)
# ------------------------------------------------------------------------------

def _call_llm(prompt: str, system: str = "", max_tokens: int = 4000) -> str:
    """Appel LLM générique via provider_manager."""
    try:
        from provider_manager import provider_manager
    except ImportError:
        try:
            from core.llm.provider_manager import provider_manager
        except ImportError:
            raise RuntimeError("provider_manager introuvable")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    chunks = []
    for item in provider_manager.execute_chat_stream(
        messages=messages,
        provider="nvidia",
        model="deepseek-v4.1-flash-free",
        temperature=0.3,
        max_tokens=max_tokens,
    ):
        if "chunk" in item:
            chunks.append(item["chunk"])
        elif "error" in item:
            raise RuntimeError(f"LLM error: {item['error']}")

    return "".join(chunks).strip()


# ------------------------------------------------------------------------------
# PLANIFICATION DU PROJET
# ------------------------------------------------------------------------------

def _generate_project_plan(brief: str, project_type: str, project_name: str) -> Dict[str, Any]:
    """
    Utilise le LLM pour planifier l'arborescence complète du projet.
    Retourne {files: [{path, content, description}], readme, tech_notes}
    """
    type_config = _PROJECT_TYPES.get(project_type, _PROJECT_TYPES["web_app"])

    system_prompt = (
        "Tu es un architecte logiciel expert. Tu génères des projets COMPLETS "
        "et FONCTIONNELS. Réponds UNIQUEMENT en JSON valide, sans markdown, "
        "sans explication. Format attendu :\n"
        '{"files": [{"path": "index.html", "content": "<!DOCTYPE html>...", '
        '"description": "page principale"}], '
        '"readme": "# Nom\\n\\nDescription...", '
        '"tech_notes": "..."}'
    )

    user_prompt = f"""Génère le projet complet suivant :

**Nom** : {project_name}
**Type** : {project_type}
**Stack imposée** : {type_config['tech']}
**Brief** : {brief}

Fichiers minimum attendus : {', '.join(type_config['files'])}

Contraintes :
- Code COMPLET, fonctionnel, prêt à lancer.
- Aucune dépendance npm si possible (vanilla HTML/JS/CSS ou Python stdlib).
- Tous les fichiers doivent être cohérents entre eux (chemins, imports, IDs).
- Pour les jeux : boucle requestAnimationFrame, contrôles clavier, collision AABB.
- Pour les apps web : UI responsive, au moins 1 interaction fonctionnelle.
- Pour les scripts : CLI avec argparse ou sys.argv.
- Inclure un README.md clair.
- Commentaires en français.

Génère au minimum 3 fichiers et au maximum 8 fichiers."""

    raw = _call_llm(user_prompt, system=system_prompt, max_tokens=6000)

    # Nettoyer les blocs markdown résiduels
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("[project_creator] LLM n'a pas renvoyé du JSON pur : %s", e)
        # Fallback : chercher le JSON dans le texte
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            plan = json.loads(json_match.group(0))
        else:
            raise RuntimeError(f"Impossible de parser le plan LLM : {raw[:300]}")

    if not isinstance(plan.get("files"), list):
        raise RuntimeError("Plan LLM invalide : 'files' manquant")

    return plan


# ------------------------------------------------------------------------------
# ÉCRITURE DES FICHIERS
# ------------------------------------------------------------------------------

def _write_project_files(project_dir: Path, plan: Dict[str, Any]) -> List[str]:
    """Écrit tous les fichiers du projet sur le disque."""
    written = []
    for file_spec in plan.get("files", []):
        path = file_spec.get("path", "").strip()
        content = file_spec.get("content", "")
        if not path or not content:
            continue
        # Sécurité : pas de path traversal
        if ".." in path or path.startswith("/"):
            logger.warning("[project_creator] Chemin refusé : %s", path)
            continue
        target = project_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(path)
        logger.info("[project_creator] ✍️  %s (%d chars)", path, len(content))

    # README séparé si présent
    if plan.get("readme") and "README.md" not in written:
        readme = project_dir / "README.md"
        readme.write_text(plan["readme"], encoding="utf-8")
        written.append("README.md")

    return written


# ------------------------------------------------------------------------------
# HANDLERS HERMES
# ------------------------------------------------------------------------------

def _handler_create_project(
    brief: str = "",
    project_name: str = "",
    project_type: str = "",
    dry_run: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Handler Hermes : crée un projet complet à partir d'un brief.
    """
    if not brief or not brief.strip():
        return {"status": "error", "message": "brief obligatoire"}

    t0 = time.monotonic()

    # 1. Détection automatique du type
    if not project_type or project_type == "auto":
        project_type = _detect_project_type(brief)
    if project_type not in _PROJECT_TYPES:
        return {
            "status": "error",
            "message": f"Type de projet inconnu : {project_type}. "
                       f"Types valides : {list(_PROJECT_TYPES.keys())}",
        }

    # 2. Nom du projet
    if not project_name:
        project_name = _slugify(brief[:50])
    slug = _slugify(project_name)
    if not slug:
        slug = f"project_{uuid.uuid4().hex[:6]}"

    project_dir = _get_projects_root() / slug
    if project_dir.exists() and not dry_run:
        return {
            "status": "error",
            "message": f"Le projet '{slug}' existe déjà dans projects/. "
                       f"Choisis un autre nom.",
        }

    logger.info(
        "[project_creator] 🚀 Création projet : name=%s type=%s dry_run=%s",
        slug, project_type, dry_run,
    )

    # 3. Génération du plan via LLM
    try:
        plan = _generate_project_plan(brief, project_type, project_name)
    except Exception as e:
        logger.exception("[project_creator] Plan LLM échoué")
        return {"status": "error", "message": f"Génération du plan échouée : {e}"}

    # 4. Dry run : on renvoie juste le plan
    if dry_run:
        return {
            "status": "success",
            "mode": "dry_run",
            "project_name": slug,
            "project_type": project_type,
            "files_planned": [f.get("path") for f in plan.get("files", [])],
            "readme_preview": (plan.get("readme") or "")[:500],
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 2),
        }

    # 5. Écriture sur disque
    try:
        project_dir.mkdir(parents=True, exist_ok=True)
        written = _write_project_files(project_dir, plan)
    except Exception as e:
        logger.exception("[project_creator] Écriture échouée")
        return {"status": "error", "message": f"Écriture projet échouée : {e}"}

    # 6. Trace EventBus (si dispo)
    try:
        from nerves.event_bus_nerves import publish_event_unified
        publish_event_unified("vector-context", {
            "action": "project_created",
            "project": slug,
            "type": project_type,
            "files": written,
            "timestamp_ms": int(time.time() * 1000),
        })
    except Exception:
        pass

    elapsed = round((time.monotonic() - t0) * 1000, 2)
    logger.info(
        "[project_creator] ✅ Projet '%s' créé (%d fichiers, %.0fms)",
        slug, len(written), elapsed,
    )

    return {
        "status": "success",
        "project_name": slug,
        "project_type": project_type,
        "project_path": str(project_dir),
        "files_created": written,
        "files_count": len(written),
        "readme_preview": (plan.get("readme") or "")[:500],
        "elapsed_ms": elapsed,
        "open_with": str(project_dir / "index.html") if (project_dir / "index.html").exists() else str(project_dir),
    }


def _handler_list_projects(**kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : liste les projets existants."""
    root = _get_projects_root()
    projects = []
    for p in sorted(root.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_dir():
            continue
        files = [f.name for f in p.rglob("*") if f.is_file()]
        projects.append({
            "name": p.name,
            "path": str(p),
            "files_count": len(files),
            "modified": p.stat().st_mtime,
        })
    return {"status": "success", "count": len(projects), "projects": projects}


def _handler_project_status(project_name: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Handler Hermes : status d'un projet spécifique."""
    if not project_name:
        return {"status": "error", "message": "project_name obligatoire"}
    slug = _slugify(project_name)
    project_dir = _get_projects_root() / slug
    if not project_dir.exists():
        return {"status": "error", "message": f"Projet '{slug}' introuvable"}

    files = []
    for f in sorted(project_dir.rglob("*")):
        if f.is_file():
            files.append({
                "path": str(f.relative_to(project_dir)),
                "size": f.stat().st_size,
            })
    return {
        "status": "success",
        "project_name": slug,
        "path": str(project_dir),
        "files": files,
        "files_count": len(files),
    }


# ------------------------------------------------------------------------------
# ACTIVATION
# ------------------------------------------------------------------------------

PROJECT_CREATOR_NERVES_TABLE: Dict[str, tuple] = {
    "create_project":   (_handler_create_project,  "L2"),
    "list_projects":    (_handler_list_projects,   "L1"),
    "project_status":   (_handler_project_status,  "L1"),
}


def activate_project_creator_nerves() -> Dict[str, Any]:
    """
    Enregistre les outils de création de projets dans Hermes.
    Idempotent. Feature-flag BEK_ENABLE_PROJECT_CREATOR.
    """
    if not _is_enabled():
        logger.warning("[Nerf 19] Désactivé via BEK_ENABLE_PROJECT_CREATOR=false")
        return {"status": "disabled", "reason": "feature-flag"}

    try:
        from hermes_core import hermes
    except ImportError as exc:
        logger.error("[Nerf 19] hermes_core introuvable : %s", exc)
        return {"status": "error", "message": str(exc)}

    activated = []
    failed = []
    for tool_name, (handler, risk) in PROJECT_CREATOR_NERVES_TABLE.items():
        try:
            hermes.register_tool(tool_name, handler, risk_level=risk)
            activated.append(tool_name)
            logger.info("🧠 [Nerf 19] Outil branché : %s (risk=%s)", tool_name, risk)
        except Exception as exc:
            failed.append({"tool": tool_name, "error": str(exc)})
            logger.error("[Nerf 19] Échec %s : %s", tool_name, exc)

    logger.info(
        "✅ [Nerf 19] Activation terminée : %d outils, %d échecs",
        len(activated), len(failed),
    )
    return {
        "status": "ok",
        "activated_count": len(activated),
        "activated_tools": activated,
        "failed": failed,
        "project_types": list(_PROJECT_TYPES.keys()),
    }