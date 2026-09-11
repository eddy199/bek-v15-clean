# ==============================================================================
# skill_generator.py — AUTO-GÉNÉRATEUR DE SKILLS DYNAMIQUES AVEC SANDBOX AST & CORRECTION HERMES
# ==============================================================================

import os
import json
import importlib.util
import sys
import logging

from core.security.skill_sandbox import validate_skill_code
from skill_registry import skill_registry

logger = logging.getLogger("SkillGenerator")
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(WORKSPACE_DIR, "skills")
os.makedirs(SKILLS_DIR, exist_ok=True)

def create_and_register_skill(skill_name: str, code_content: str, description: str = "Skill auto-généré") -> dict:
    """Valide via la Sandbox AST, crée le code Python, le manifeste JSON et injecte le skill en mémoire."""
    safe_filename = skill_name.lower().strip().replace(" ", "_")
    py_path = os.path.join(SKILLS_DIR, f"{safe_filename}.py")
    json_path = os.path.join(SKILLS_DIR, f"{safe_filename}.json")

    # 1. Validation de sécurité statique (Sandbox AST)
    security_check = validate_skill_code(code_content)
    if not security_check.get("valid", False):
        errors_str = "\n- " + "\n- ".join(security_check.get("errors", ["Code non conforme"]))
        logger.warning(f"🛡️ [SANDBOX REJET] Skill '{skill_name}' bloqué :{errors_str}")
        return {
            "status": "error",
            "message": f"🛡️ [SANDBOX REJET] Code non sécurisé ou invalide détecté :{errors_str}"
        }

    try:
        # 2. Écriture du code source Python vérifié
        with open(py_path, "w", encoding="utf-8") as f:
            f.write(code_content)

        # 3. Écriture du manifeste JSON pour BEK
        manifest = {
            "name": skill_name,
            "description": description,
            "entrypoint": f"{safe_filename}.py"
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)

        # 4. Compilation du code pour validation du bytecode
        compile(code_content, py_path, "exec")

        # 5. Chargement dynamique du module en mémoire
        spec = importlib.util.spec_from_file_location(skill_name, py_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[skill_name] = module
            spec.loader.exec_module(module)

            # Injection SÉCURISÉE pour Hermes
            run_func = getattr(module, "run", None)
            if run_func:
                if hasattr(skill_registry, "skills") and isinstance(skill_registry.skills, dict):
                    # CORRECTION HERMES : Dictionnaire structuré avec metadata au lieu d'une fonction nue
                    skill_registry.skills[skill_name] = {
                        "name": skill_name,
                        "description": description,
                        "enabled": True,
                        "func": run_func
                    }
                elif hasattr(skill_registry, "add_skill"):
                    skill_registry.add_skill(skill_name, description, run_func)

        logger.info(f"✨ [SkillGenerator] Skill '{skill_name}' validé, sécurisé et injecté.")
        return {
            "status": "success",
            "message": f"✅ Skill '{skill_name}' sécurisé et généré avec succès.\nFichiers : `{py_path}` et `{json_path}`.",
            "path": py_path
        }

    except Exception as e:
        # Nettoyage systématique des résidus en cas d'erreur
        for path in [py_path, json_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        logger.error(f"❌ [SkillGenerator] Échec d'intégration du skill '{skill_name}': {str(e)}")
        return {"status": "error", "message": f"Échec de l'auto-génération du skill : {str(e)}"}