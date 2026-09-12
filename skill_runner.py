# -*- coding: utf-8 -*-
# BEK-v16 HYBRID - Asynchronous Skill Runner
# Exécution non-bloquante des compétences avec isolation, timeout et contrôle Hermes.

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from event_bus_client import event_bus

logger = logging.getLogger("bek.skills.runner")
SKILLS_DIR = Path(__file__).resolve().parent / "skills"

async def execute_skill_async(
    skill_name: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    
    payload = payload or {}
    skill_py = SKILLS_DIR / f"{skill_name}.py"
    skill_json = SKILLS_DIR / f"{skill_name}.json"

    # Vérification de l'existence du script métier
    if not skill_py.exists():
        error_msg = f"Script Python introuvable pour la compétence : {skill_name}"
        logger.error(error_msg)
        return {"status": "error", "skill": skill_name, "error": error_msg}

    # Lecture optionnelle du manifeste JSON pour le contrôle de risque
    risk_level = "L1"
    if skill_json.exists():
        try:
            with open(skill_json, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                risk_level = manifest.get("risk_level", "L1")
        except Exception as exc:
            logger.warning(f"Impossible de lire le manifeste JSON [{skill_json.name}] : {exc}")

    logger.info(f"Lancement de la compétence [{skill_name}] | Risque: {risk_level}")

    # Exécution asynchrone en sous-processus isolé
    input_data = json.dumps(payload)
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
            proc.kill()
            await proc.communicate()
            error_msg = f"Timeout dépassé ({timeout_seconds}s) pour {skill_name}"
            logger.error(error_msg)
            return {"status": "timeout", "skill": skill_name, "error": error_msg}

        stdout_str = stdout_data.decode("utf-8", errors="replace").strip()
        stderr_str = stderr_data.decode("utf-8", errors="replace").strip()

        # Tentative de décodage du résultat JSON renvoyé par le script
        parsed_result = None
        for line in reversed(stdout_str.splitlines()):
            try:
                parsed_result = json.loads(line)
                break
            except ValueError:
                continue

        response = {
            "status": "success" if proc.returncode == 0 else "failed",
            "skill": skill_name,
            "returncode": proc.returncode,
            "result": parsed_result or stdout_str,
            "stderr": stderr_str if proc.returncode != 0 else None,
        }

        # Notification de l'exécution sur l'EventBus
        await event_bus.publish(
            f"skill.{skill_name}.executed",
            {"skill": skill_name, "status": response["status"], "risk_level": risk_level},
        )
        return response

    except Exception as exc:
        logger.error(f"Échec critique lors de l'exécution de [{skill_name}] : {exc}")
        return {"status": "error", "skill": skill_name, "error": str(exc)}