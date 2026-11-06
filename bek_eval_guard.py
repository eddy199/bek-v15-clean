# ==============================================================================
# bek_eval_guard.py — GARDE-FOU ET JUGE CRITIQUE AVEC AST (BEK-v15.4)
# ------------------------------------------------------------------------------
# ★ v15.4 (2026-11-06) — Ajout validate_cited_numbers
#   - Détecte les chiffres cités dans une synthèse qui ne proviennent pas
#     des chiffres officiels (audit JSON, métriques, etc.)
#   - Utilisé par core/brain.py::_validate_synthesis_numbers
# ==============================================================================

import ast
import logging
import re as _re

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


# ==============================================================================
# ★ v15.4 — Validation des chiffres cités dans une synthèse
# ==============================================================================

def validate_cited_numbers(response_content: str, official_numbers: dict) -> dict:
    """
    Vérifie que tous les entiers > 10 cités dans le texte existent dans official_numbers.

    Args:
        response_content: Texte de la synthèse à vérifier
        official_numbers: Dict {label: valeur_int} des chiffres officiels
                          ex: {"files_analyzed": 297, "total_lines": 73368, "warnings": 93}

    Returns:
        {
            "passed": bool,                 # True si aucun chiffre suspect
            "suspicious_numbers": list[int],# Chiffres cités mais absents des officiels
            "official_numbers": list[int],  # Chiffres officiels triés
        }
    """
    cited = {int(n) for n in _re.findall(r"\b(\d{2,6})\b", response_content or "")}
    official = set()
    for v in (official_numbers or {}).values():
        try:
            official.add(int(v))
        except (TypeError, ValueError):
            continue
    suspicious = sorted(n for n in cited if n not in official and n > 10)
    return {
        "passed": len(suspicious) == 0,
        "suspicious_numbers": suspicious,
        "official_numbers": sorted(official),
    }