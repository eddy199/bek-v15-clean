# ==============================================================================
# skill_generator.py — AUTO-GÉNÉRATEUR DE SKILLS DYNAMIQUES (CORRIGÉ)
# ==============================================================================

import os
import json
import importlib.util
import sys
import logging
from skill_registry import skill_registry

logger = logging.getLogger("SkillGenerator")
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(WORKSPACE_DIR, "skills")
os.makedirs(SKILLS_DIR, exist_ok=True)

def create_and_register_skill(skill_name: str, code_content: str, description: str) -> dict:
    """Crée le code Python, le manifeste JSON et injecte le skill en mémoire."""
    safe_filename = skill_name.lower().strip().replace(' ', '_')
    py_path = os.path.join(SKILLS_DIR, f"{safe_filename}.py")
    json_path = os.path.join(SKILLS_DIR, f"{safe_filename}.json")
    
    try:
        # 1. Écriture du code source Python
        with open(py_path, "w", encoding="utf-8") as f:
            f.write(code_content)
            
        # 2. Écriture du manifeste JSON (Format attendu par BEK)
        manifest = {
            "name": skill_name,
            "description": description,
            "entrypoint": f"{safe_filename}.py"
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)
        
        # 3. Test de compilation (détection précoce des erreurs syntaxiques)
        compile(code_content, py_path, 'exec')
        
        # 4. Chargement dynamique en mémoire
        spec = importlib.util.spec_from_file_location(skill_name, py_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[skill_name] = module
            spec.loader.exec_module(module)
            
            # Injection de force dans le dictionnaire interne si possible
            if hasattr(skill_registry, "skills") and isinstance(skill_registry.skills, dict):
                skill_registry.skills[skill_name] = module.run
            elif hasattr(skill_registry, "add_skill"):
                skill_registry.add_skill(skill_name, description, module.run)
                
        logger.info(f"✨ [SkillGenerator] Skill '{skill_name}' généré (.py + .json).")
        return {
            "status": "success", 
            "message": f"✅ Skill '{skill_name}' auto-généré avec succès.\nFichiers créés : `{py_path}` et `{json_path}`.", 
            "path": py_path
        }
            
    except Exception as e:
        # Nettoyage en cas d'erreur
        for path in [py_path, json_path]:
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
        return {"status": "error", "message": f"Échec de l'auto-génération du skill : {str(e)}"}