"""Module contenant smart_truncate et clean_boilerplate."""

import re


def smart_truncate(texte: str, length: int = 100) -> str:
    """Tronque un texte intelligemment en coupant au point si possible."""
    if not texte:
        return ""
    if len(texte) <= length:
        return texte
    tronque = texte[:length]
    dernier_point = tronque.rfind(".")
    if dernier_point != -1:
        return texte[: dernier_point + 1]
    return tronque


def clean_boilerplate(texte: str) -> str:
    """Supprime les mentions de cookies et menus de navigation d'un texte."""
    if not texte:
        return ""
    result = texte
    # Supprimer les phrases contenant 'cookie' (insensible à la casse)
    result = re.sub(r"[^.]*cookie[^.]*\.?\s*", " ", result, flags=re.IGNORECASE)
    # Supprimer les phrases contenant 'menu' (insensible à la casse)
    result = re.sub(r"[^.]*menu[^.]*\.?\s*", " ", result, flags=re.IGNORECASE)
    # Supprimer les séparateurs de type ' | '
    result = re.sub(r"\s*\|\s*", " ", result)
    # Nettoyer les espaces multiples
    result = re.sub(r"\s+", " ", result).strip()
    return result