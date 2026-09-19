# -*- coding: utf-8 -*-
# ==============================================================================
# skill_generator.py — Générateur de skills dynamiques (sandbox + EventBus)
# ------------------------------------------------------------------------------
# Sécurité :
#   • Validation stricte du nom (regex)
#   • Sandbox AST statique avant écriture
#   • Taille max du code : 200 KB
#   • Chargement du skill NE se fait PAS dans le process principal (délégué au runner)
#   • Notification EventBus (skills-index) via bus synchrone
#   • Hash SHA-256 du code écrit
# ==============================================================================

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("SkillGenerator")

# ── Dossiers ────────────────────────────────────────────────────────────────
try:
    from core.paths import WORKSPACE_DIR
    SKILLS_DIR = Path(WORKSPACE_DIR) / "skills"
except Exception:
    SKILLS_DIR = Path(__file__).resolve().parent / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)

# ── Validation du nom de skill ──────────────────────────────────────────────
_SKILL_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
_MAX_CODE_SIZE = 200 * 1024  # 200 KB

# ── Sandbox AST (importable depuis core/security OU fallback inline) ────────
try:
    from core.security.skill_sandbox import validate_skill_code  # type: ignore
    _SANDBOX_AVAILABLE = True
except ImportError:
    logger.warning("[SkillGenerator] core.security.skill_sandbox introuvable → fallback local")
    _SANDBOX_AVAILABLE = False

    # Fallback minimal intégré
    import ast

    _BANNED_MODULES = {
        "subprocess", "ctypes", "socket", "pickle",
        "multiprocessing", "importlib", "pty", "signal",
    }

    def validate_skill_code(code: str) -> Dict[str, Any]:  # type: ignore
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"valid": False, "errors": [f"SyntaxError ligne {e.lineno}: {e.msg}"]}

        errors = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif node.module:
                    names = [node.module]
                for name in names:
                    root = name.split(".")[0]
                    if root in _BANNED_MODULES:
                        errors.append(f"Import interdit : {name}")

        return {"valid": not errors, "errors": errors}


# ── EventBus (bus synchrone prioritaire pour éviter le problème de loop fermée) ─
def _publish_event(action: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """
    Publie un événement sur 'skills-index'.
    Utilise le bus SYNCHRONE (EventBusKafka) car create_and_register_skill
    est une fonction synchrone → évite les problèmes d'event loop fermée.
    """
    payload = {"action": action, "source": "skill_generator"}
    if extra:
        payload.update(extra)

    # Bus synchrone (Redis Streams ou mock) — pas de loop asyncio requise
    try:
        from event_bus import EventBusKafka  # type: ignore
        bus = EventBusKafka()
        bus.publish("skills-index", payload)
        bus.stop()
        return
    except Exception as exc:
        logger.debug("[SkillGenerator] bus sync indisponible : %s", exc)

    # Fallback : bus async si on est déjà dans une loop qui tourne
    try:
        import asyncio
        from event_bus_client import event_bus  # type: ignore
        loop = asyncio.get_running_loop()
        loop.create_task(event_bus.publish("skills-index", payload))
    except RuntimeError:
        logger.debug("[SkillGenerator] aucun bus disponible, event ignoré")
    except Exception as exc:
        logger.debug("[SkillGenerator] publish async échoué : %s", exc)


# ── Helpers ─────────────────────────────────────────────────────────────────
def _valid_name(skill_name: str) -> Optional[str]:
    """Retourne un nom normalisé valide ou None."""
    if not isinstance(skill_name, str):
        return None
    candidate = skill_name.strip().lower().replace(" ", "_")
    if not _SKILL_NAME_RE.match(candidate):
        return None
    return candidate


def _safe_paths(name: str) -> tuple[Path, Path]:
    py_path = (SKILLS_DIR / f"{name}.py").resolve()
    json_path = (SKILLS_DIR / f"{name}.json").resolve()
    for p in (py_path, json_path):
        try:
            p.relative_to(SKILLS_DIR.resolve())
        except ValueError:
            raise ValueError(f"Chemin invalide pour {name}")
    return py_path, json_path


# ==============================================================================
# API PUBLIQUE
# ==============================================================================
def create_and_register_skill(
    skill_name: str,
    code_content: str,
    description: str = "Skill auto-généré",
) -> Dict[str, Any]:
    """
    Valide le nom, vérifie le code via sandbox, écrit les fichiers puis
    notifie le SkillRegistry et l'EventBus.

    IMPORTANT : le code n'est PAS exécuté dans le process principal.
                L'exécution se fait via skill_runner (sous-processus isolé).
    """
    # 1. Validation du nom
    name = _valid_name(skill_name)
    if not name:
        msg = f"❌ Nom de skill invalide : {skill_name!r} (autorisé: A-Z a-z 0-9 _ -)"
        logger.warning(msg)
        _publish_event("skill_rejected", {"skill": skill_name, "reason": "invalid_name"})
        return {"status": "error", "message": msg}

    # 2. Validation taille
    if not isinstance(code_content, str) or not code_content.strip():
        return {"status": "error", "message": "Code vide."}
    if len(code_content.encode("utf-8")) > _MAX_CODE_SIZE:
        msg = f"❌ Code trop volumineux (> {_MAX_CODE_SIZE // 1024} KB)"
        logger.warning("[SkillGenerator] %s pour '%s'", msg, name)
        _publish_event("skill_rejected", {"skill": name, "reason": "size_limit"})
        return {"status": "error", "message": msg}

    # 3. Sandbox AST
    check = validate_skill_code(code_content)
    if not check.get("valid", False):
        errors = check.get("errors", ["Code non conforme"])
        logger.warning("🛡️ [SANDBOX REJET] '%s' : %s", name, errors)
        _publish_event(
            "skill_rejected",
            {"skill": name, "reason": "sandbox", "errors": errors[:5]},
        )
        return {
            "status": "error",
            "message": "🛡️ [SANDBOX REJET] Code refusé :\n- " + "\n- ".join(errors),
            "errors": errors,
        }

    # 4. Chemins sécurisés
    try:
        py_path, json_path = _safe_paths(name)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    # 5. Compilation (détecte erreurs restantes)
    try:
        compile(code_content, str(py_path), "exec")
    except SyntaxError as exc:
        return {"status": "error", "message": f"SyntaxError ligne {exc.lineno}: {exc.msg}"}

    # 6. Écriture
    try:
        code_hash = hashlib.sha256(code_content.encode("utf-8")).hexdigest()
        py_path.write_text(code_content, encoding="utf-8")

        manifest = {
            "name": name,
            "description": description,
            "entrypoint": f"{name}.py",
            "risk_level": "L2",  # skills générés = L2 par défaut
            "hash_sha256": code_hash,
        }
        json_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    except Exception as exc:
        # Rollback
        for p in (py_path, json_path):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        logger.error("[SkillGenerator] Écriture échouée pour '%s' : %s", name, exc)
        return {"status": "error", "message": f"Échec écriture : {exc}"}

    # 7. Injection dans SkillRegistry (métadonnées seulement, PAS le code)
    try:
        from skill_registry import skill_registry  # type: ignore
        if hasattr(skill_registry, "skills") and isinstance(skill_registry.skills, dict):
            skill_registry.skills[name] = {
                "name": name,
                "description": description,
                "enabled": True,
                "path": str(py_path),
                "manifest": manifest,
            }
        elif hasattr(skill_registry, "add_skill"):
            skill_registry.add_skill(name, description, None)
    except Exception as exc:
        logger.warning("[SkillGenerator] SkillRegistry non mis à jour : %s", exc)

    logger.info("✨ [SkillGenerator] Skill '%s' créé (hash=%s…)", name, code_hash[:12])

    # 8. Notification EventBus
    _publish_event(
        "skill_created",
        {
            "skill": name,
            "description": description,
            "hash": code_hash,
            "path": str(py_path),
        },
    )

    return {
        "status": "success",
        "message": (
            f"✅ Skill '{name}' sécurisé et généré.\n"
            f"Fichiers : `{py_path}` et `{json_path}`."
        ),
        "path": str(py_path),
        "hash": code_hash,
    }