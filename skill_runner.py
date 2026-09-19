# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 HYBRID — Async Skill Runner (sandbox + gating L3+ + topics valides)
# ------------------------------------------------------------------------------
# Exécute une compétence Python en sous-processus isolé, avec :
#   • validation anti path-traversal
#   • timeout + kill propre
#   • gating d'approbation humaine pour L3+ (via approval_manager)
#   • émission EventBus sur le topic valide "skills-index"
#   • capture robuste stdout/stderr/JSON
# ==============================================================================

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from event_bus_client import event_bus

logger = logging.getLogger("bek.skills.runner")

# ── Dossiers autorisés ──────────────────────────────────────────────────────
try:
    from core.paths import WORKSPACE_DIR
    SKILLS_DIR = Path(WORKSPACE_DIR) / "skills"
except Exception:
    SKILLS_DIR = Path(__file__).resolve().parent / "skills"

SKILLS_DIR.mkdir(parents=True, exist_ok=True)

# ── Regex nom de skill valide ───────────────────────────────────────────────
_SKILL_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

# ── Topics EventBus valides ─────────────────────────────────────────────────
_TOPIC_SKILL_EVENTS = "skills-index"
_TOPIC_ERROR = "error-signals"


# ==============================================================================
# Helpers
# ==============================================================================
def _is_valid_skill_name(name: str) -> bool:
    return bool(name and _SKILL_NAME_RE.match(name))


def _safe_skill_path(name: str, ext: str) -> Optional[Path]:
    """Retourne le chemin absolu sécurisé du fichier skill, ou None si invalide."""
    if not _is_valid_skill_name(name):
        return None
    candidate = (SKILLS_DIR / f"{name}{ext}").resolve()
    # Doit rester DANS SKILLS_DIR
    try:
        candidate.relative_to(SKILLS_DIR.resolve())
    except ValueError:
        return None
    return candidate


async def _maybe_require_approval(skill_name: str, risk_level: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Si le skill est L3+, on demande approbation via approval_manager.
    Retourne {"allowed": bool, "approval_id": str, "reason": str}.
    """
    if risk_level not in ("L3", "L4", "L5"):
        return {"allowed": True, "approval_id": "", "reason": "risque < L3"}

    try:
        from approval_manager import approval_manager  # type: ignore

        request = approval_manager.submit_request(
            task_id=f"skill_{skill_name}_{os.urandom(4).hex()}",
            trace_id=f"trace_{os.urandom(4).hex()}",
            tool=f"skill.{skill_name}",
            args=payload,
            risk_level=risk_level,
            reason=f"Exécution du skill '{skill_name}' ({risk_level}) requiert validation humaine.",
        )
        approval_id = str(getattr(request, "approval_id", "") or "")
        logger.info(
            "🛡️ [SkillRunner] Skill L3+ soumis à approbation | skill=%s | id=%s",
            skill_name, approval_id,
        )
        return {
            "allowed": False,   # bloqué tant que non approuvé
            "approval_id": approval_id,
            "reason": "En attente d'approbation humaine",
        }
    except ImportError:
        logger.warning("[SkillRunner] approval_manager indisponible → L3+ NON gaté")
        return {"allowed": True, "approval_id": "", "reason": "approval_manager absent"}
    except Exception as exc:
        logger.error("[SkillRunner] Erreur approval_manager : %s", exc)
        return {"allowed": False, "approval_id": "", "reason": f"approval error: {exc}"}


async def _kill_process(proc: asyncio.subprocess.Process) -> None:
    """Tue le sous-processus proprement (SIGTERM puis SIGKILL)."""
    if proc.returncode is not None:
        return
    try:
        if sys.platform == "win32":
            proc.kill()
        else:
            proc.send_signal(signal.SIGTERM)
            await asyncio.sleep(0.5)
            if proc.returncode is None:
                proc.kill()
    except ProcessLookupError:
        pass
    except Exception as exc:
        logger.debug("[SkillRunner] kill error : %s", exc)
    finally:
        try:
            await proc.communicate()
        except Exception:
            pass


# ==============================================================================
# API publique
# ==============================================================================
async def execute_skill_async(
    skill_name: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    """
    Exécute un skill en sous-processus isolé.
    Retour :
        {"status": "success"|"error"|"timeout"|"blocked", "skill": ..., ...}
    """
    payload = payload or {}

    # ── Validation nom ──────────────────────────────────────────────────────
    if not _is_valid_skill_name(skill_name):
        error_msg = f"Nom de skill invalide : {skill_name!r}"
        logger.error(error_msg)
        await _publish_error(skill_name, error_msg)
        return {"status": "error", "skill": skill_name, "error": error_msg}

    skill_py = _safe_skill_path(skill_name, ".py")
    skill_json = _safe_skill_path(skill_name, ".json")

    if skill_py is None or not skill_py.exists():
        error_msg = f"Script Python introuvable : {skill_name}"
        logger.error(error_msg)
        await _publish_error(skill_name, error_msg)
        return {"status": "error", "skill": skill_name, "error": error_msg}

    # ── Lecture manifeste (risk_level + metadata) ───────────────────────────
    risk_level = "L1"
    manifest_meta: Dict[str, Any] = {}
    if skill_json is not None and skill_json.exists():
        try:
            manifest = json.loads(skill_json.read_text(encoding="utf-8"))
            risk_level = str(manifest.get("risk_level", "L1")).upper()
            manifest_meta = manifest
        except Exception as exc:
            logger.warning("[SkillRunner] Manifeste illisible (%s) : %s", skill_json.name, exc)

    logger.info("🚀 [SkillRunner] Lancement %s | risque=%s", skill_name, risk_level)

    # ── Gating L3+ ──────────────────────────────────────────────────────────
    approval = await _maybe_require_approval(skill_name, risk_level, payload)
    if not approval["allowed"]:
        await event_bus.publish(
            _TOPIC_SKILL_EVENTS,
            {
                "action": "skill_blocked_for_approval",
                "skill": skill_name,
                "risk_level": risk_level,
                "approval_id": approval["approval_id"],
                "reason": approval["reason"],
            },
        )
        return {
            "status": "blocked",
            "skill": skill_name,
            "risk_level": risk_level,
            "approval_id": approval["approval_id"],
            "reason": approval["reason"],
        }

    # ── Exécution sous-processus ────────────────────────────────────────────
    input_data = json.dumps(payload, ensure_ascii=False)
    proc: Optional[asyncio.subprocess.Process] = None

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(skill_py),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                proc.communicate(input=input_data.encode("utf-8")),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            await _kill_process(proc)
            error_msg = f"Timeout dépassé ({timeout_seconds}s)"
            logger.error("[SkillRunner] %s pour %s", error_msg, skill_name)
            await event_bus.publish(
                _TOPIC_ERROR,
                {
                    "action": "skill_timeout",
                    "skill": skill_name,
                    "risk_level": risk_level,
                    "timeout": timeout_seconds,
                },
            )
            return {
                "status": "timeout",
                "skill": skill_name,
                "risk_level": risk_level,
                "error": error_msg,
            }

        stdout_str = stdout_data.decode("utf-8", errors="replace").strip()
        stderr_str = stderr_data.decode("utf-8", errors="replace").strip()

        # Décodage JSON depuis la dernière ligne valide
        parsed_result: Any = None
        for line in reversed(stdout_str.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                parsed_result = json.loads(line)
                break
            except ValueError:
                continue
        if parsed_result is None:
            parsed_result = stdout_str

        success = proc.returncode == 0
        status = "success" if success else "failed"

        response = {
            "status": status,
            "skill": skill_name,
            "risk_level": risk_level,
            "returncode": proc.returncode,
            "result": parsed_result,
            "stderr": stderr_str if not success else None,
        }

        # ── Publication EventBus (topic valide) ─────────────────────────────
        await event_bus.publish(
            _TOPIC_SKILL_EVENTS,
            {
                "action": "skill_executed",
                "skill": skill_name,
                "status": status,
                "risk_level": risk_level,
                "returncode": proc.returncode,
                "manifest": manifest_meta.get("description", "")[:200],
            },
        )

        return response

    except Exception as exc:
        logger.exception("[SkillRunner] Échec critique pour %s : %s", skill_name, exc)
        if proc is not None:
            await _kill_process(proc)
        await _publish_error(skill_name, str(exc))
        return {
            "status": "error",
            "skill": skill_name,
            "risk_level": risk_level,
            "error": str(exc),
        }


async def _publish_error(skill_name: str, message: str) -> None:
    try:
        await event_bus.publish(
            _TOPIC_ERROR,
            {
                "action": "skill_error",
                "skill": skill_name,
                "message": message[:500],
            },
        )
    except Exception as exc:
        logger.debug("[SkillRunner] publish_error ignoré : %s", exc)