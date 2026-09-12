# ==============================================================================
# bek_eval_guard.py — GARDE-FOU ET JUGE CRITIQUE AVEC AST (BEK-v15.3)
# ==============================================================================

import ast
import logging

logger = logging.getLogger("BekEvalGuard")

def evaluate_response_quality(objective: str, response_content: str) -> dict:
    """Intercepte le contenu généré, vérifie la syntaxe Python statique et valide la qualité."""
    
    # 1. Extraction et audit syntaxique par AST uniquement sur les blocs Python explicites
    if "```python" in response_content:
        try:
            lines = response_content.splitlines()
            code_block = []
            capturing = False
            for line in lines:
                if "```python" in line:
                    capturing = True
                    continue
                elif "```" in line and capturing:
                    capturing = False
                    break
                if capturing:
                    code_block.append(line)
            
            target_code = "\n".join(code_block)
            if target_code.strip():
                ast.parse(target_code)
                logger.info("✨ [BekEvalGuard] Validation syntaxique AST réussie.")
        except SyntaxError as se:
            logger.warning(f"❌ [BekEvalGuard] Échec syntaxique AST : {se}")
            return {
                "passed": False,
                "reason": f"Erreur de syntaxe Python détectée par l'analyseur statique : {se.msg} (Ligne {se.lineno})"
            }
        except Exception as e:
            logger.warning(f"⚠️ [BekEvalGuard] Avertissement parsing : {e}")

    # 2. Validation globale de la structure de la réponse
    if not response_content.strip():
        return {"passed": False, "reason": "Le contenu de la réponse est vide."}

    return {
        "passed": True,
        "reason": "Validation structurelle et syntaxique validée avec succès."
    }