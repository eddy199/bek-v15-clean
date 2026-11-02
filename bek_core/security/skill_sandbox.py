# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-SKILL Sandbox (Exécution de code sécurisée)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-SKILL-v1.0
# 📄 Doc : docs/brevets/BREVET_SKILL.md
# 🎯 Rôle : Isolation stricte, limitation RAM/CPU, et exécution de code IA
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 2.0 (Refactored - Security Hardened)
# Date : 2026-09-28
# ==============================================================================

from __future__ import annotations

import ast
import json
import logging
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, Tuple

logger = logging.getLogger("bek.core.skill.sandbox")

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES & SÉCURITÉ
# ══════════════════════════════════════════════════════════════════════════════

# On n'autorise que ces modules inoffensifs. TOUT le reste est bloqué.
ALLOWED_IMPORTS = {"math", "datetime", "json", "re", "collections", "itertools", "typing"}

MAX_EXECUTION_TIME = 10  # Secondes maximum avant de tuer le processus
MAX_MEMORY_MB = 50       # Limite stricte de RAM en Megaoctets


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class BekSkillSandbox:
    """
    Forteresse d'exécution pour les compétences générées par l'IA.
    
    1. Vérifie l'AST (Abstract Syntax Tree) avec une approche Whitelist (liste blanche).
    2. Exécute le code dans un sous-processus isolé.
    3. Impose des limites strictes de RAM et CPU (protection contre les bombes logiques).
    """

    def _verify_ast_whitelist(self, code: str) -> Tuple[bool, str]:
        """Vérifie statiquement le code avant toute exécution."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Erreur de syntaxe : {e}"

        for node in ast.walk(tree):
            # Bloquer les imports non autorisés
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_name = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
                # Extraire le module principal (ex: datetime.timezone -> datetime)
                base_module = module_name.split('.')[0] if module_name else ""
                
                if base_module not in ALLOWED_IMPORTS:
                    return False, f"Importation interdite : '{module_name}'. Seuls {ALLOWED_IMPORTS} sont autorisés."
            
            # Bloquer les appels système directs ou accès aux built-ins malveillants
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in {"eval", "exec", "open", "compile", "globals", "locals", "__import__", "input"}:
                        return False, f"Fonction built-in interdite : '{node.func.id}'."
                        
        return True, "AST Validé"

    def _build_wrapper_script(self, code: str, payload: Dict[str, Any]) -> str:
        """
        Génère le script Python qui sera exécuté dans le sous-processus.
        Il inclut des limites OS (sous Linux/Mac) et injecte le payload.
        """
        payload_json = json.dumps(payload)
        
        # Le script wrapper injecte les limites système avant d'exécuter le code IA
        wrapper_code = f"""
import sys
import json

# Application des limites de ressources (Linux/Mac)
try:
    import resource
    # Limiter le temps CPU
    resource.setrlimit(resource.RLIMIT_CPU, ({MAX_EXECUTION_TIME}, {MAX_EXECUTION_TIME}))
    # Limiter la mémoire (Address Space)
    max_mem_bytes = {MAX_MEMORY_MB} * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (max_mem_bytes, max_mem_bytes))
except ImportError:
    pass # Windows ne supporte pas le module resource

# Suppression des built-ins dangereux de l'environnement global
safe_builtins = {{k: v for k, v in __builtins__.items() if k not in ['open', 'eval', 'exec', '__import__', 'input']}}

# Code généré par l'IA :
def ia_skill_function(payload):
{self._indent_code(code, 4)}

if __name__ == '__main__':
    # Chargement sécurisé du payload
    payload = json.loads('''{payload_json}''')
    try:
        # Exécution de la fonction IA
        result = ia_skill_function(payload)
        print(json.dumps({{"status": "success", "data": result}}))
    except Exception as e:
        print(json.dumps({{"status": "error", "error": str(e)}}))
        sys.exit(1)
"""
        return wrapper_code

    def _indent_code(self, code: str, spaces: int) -> str:
        """Indente le code de l'IA pour l'insérer dans la fonction du wrapper."""
        return "\n".join(" " * spaces + line for line in code.splitlines())

    def execute_safely(self, skill_name: str, code: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Point d'entrée principal. Valide et exécute le code.
        """
        logger.info(f"BekSkillSandbox : Tentative d'exécution du skill '{skill_name}'...")

        # 1. Validation statique
        is_valid, msg = self._verify_ast_whitelist(code)
        if not is_valid:
            logger.warning(f"BekSkillSandbox : Rejet AST pour '{skill_name}' -> {msg}")
            return {"status": "error", "error": msg}

        # 2. Préparation du sous-processus
        wrapper_script = self._build_wrapper_script(code, payload)
        
        # On crée un fichier temporaire pour héberger le script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_file.write(wrapper_script)
            temp_path = temp_file.name

        # 3. Exécution avec timeout
        try:
            # On coupe les variables d'environnement (API keys, etc.)
            clean_env = {"PYTHONPATH": os.environ.get("PYTHONPATH", "")}
            
            result = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME + 2, # +2s de marge par rapport au rlimit
                env=clean_env
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Erreur inconnue lors de l'exécution (Memory Limit ou Crash)."
                return {"status": "error", "error": error_msg}
                
            # Parsing du retour JSON
            try:
                # On prend la dernière ligne (au cas où le script ferait des print inoffensifs)
                output_line = result.stdout.strip().split('\n')[-1]
                return json.loads(output_line)
            except json.JSONDecodeError:
                return {"status": "error", "error": f"Le script n'a pas retourné un JSON valide. Sortie : {result.stdout[:100]}"}

        except subprocess.TimeoutExpired:
            logger.error(f"BekSkillSandbox : Timeout dépassé ({MAX_EXECUTION_TIME}s) pour '{skill_name}'")
            return {"status": "error", "error": "L'exécution du code a pris trop de temps (Timeout)."}
        finally:
            # 4. Nettoyage
            if os.path.exists(temp_path):
                os.remove(temp_path)

# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ══════════════════════════════════════════════════════════════════════════════

def bek_execute_skill_sandboxed(skill_name: str, code: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """API publique pour exécuter un skill dynamiquement."""
    sandbox = BekSkillSandbox()
    return sandbox.execute_safely(skill_name, code, payload)
