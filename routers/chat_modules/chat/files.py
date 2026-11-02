# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — Chat : Files (injection fichiers joints)
# ------------------------------------------------------------------------------
# ★ v19.23 (2026-10-24) — FIX _smart_truncate_file (budgets proportionnels)
#   - Avant : head=30 lignes fixes, tail=15 lignes fixes, struct=100 lignes fixes
#     → sur un fichier de 33K avec budget 20K, on ne gardait que 3.9K chars
#   - Après : budgets en CARACTÈRES proportionnels au max_chars
#     (head=35%, struct=45%, tail=20%)
#     → sur un fichier de 33K avec budget 20K, on garde ~20K chars
#   - Ajout de 2-3 lignes de contexte après chaque ligne structurelle
#   - AUCUNE fonctionnalité supprimée (100% rétrocompatible)
# ★ v18.10.3 — Ajout de _smart_truncate_file() (troncature structurelle)
# ★ v18.10.5 (2026-10-16) — Migration : extraction dans chat/files.py
# ==============================================================================
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import (
    MAX_FILE_CHARS,
    MAX_TOTAL_FILE_CHARS,
    _AUDIO_EXTENSIONS,
    _FILES_ATTACHED_RE,
    _IMAGE_EXTENSIONS,
    _STRUCTURAL_LINE_RE,
    _TEXT_EXTENSIONS,
    _UPLOAD_DIRS,
    _VIDEO_EXTENSIONS,
)

logger = logging.getLogger("BEKApp")


# ══════════════════════════════════════════════════════════════════════════════
# ★ v19.23 — TRONCATURE STRUCTURELLE AVEC BUDGETS PROPORTIONNELS
# ══════════════════════════════════════════════════════════════════════════════

def _smart_truncate_file(
    content: str,
    max_chars: int,
    filename: str = "",
) -> str:
    """
    ★ v19.23 — Troncature STRUCTURELLE d'un fichier trop long.

    Corrige le bug où les limites étaient en lignes fixes (30/15/100),
    ce qui sur-tronquait massivement les gros fichiers.

    Nouveau comportement : budgets en CARACTÈRES proportionnels à max_chars :
      - Tête   : 35% du budget (imports, docstrings, début de classe)
      - Queue  : 20% du budget (conclusion, fin du fichier)
      - Struct : 45% du budget (signatures de fonctions/classes + 2-3 lignes de contexte)

    Args:
        content  : Contenu complet du fichier
        max_chars: Limite de caractères à respecter
        filename : Nom du fichier (pour les logs)

    Returns:
        Contenu tronqué intelligemment, avec marqueurs explicites.
    """
    if not content or len(content) <= max_chars:
        return content

    original_len = len(content)
    lines = content.split("\n")
    total_lines = len(lines)

    # Cas simple : fichier avec très peu de lignes → coupe classique
    if total_lines <= 50:
        truncated = content[:max_chars]
        return (
            truncated
            + f"\n\n[...{original_len - max_chars} chars omis "
            + f"(fichier trop long : {original_len} chars, "
            + f"limite {max_chars})...]"
        )

    # ─── Budgets en caractères (proportionnels au max_chars) ───
    budget_head = int(max_chars * 0.35)
    budget_tail = int(max_chars * 0.20)
    budget_struct = max_chars - budget_head - budget_tail  # 45%

    # ─── 1. Tête : lignes du début jusqu'à épuisement du budget_head ───
    head_lines: List[str] = []
    head_chars = 0
    for line in lines:
        if head_chars + len(line) + 1 > budget_head:
            break
        head_lines.append(line)
        head_chars += len(line) + 1
    head = "\n".join(head_lines)

    # ─── 2. Queue : lignes de la fin jusqu'à épuisement du budget_tail ───
    tail_lines: List[str] = []
    tail_chars = 0
    for line in reversed(lines):
        if tail_chars + len(line) + 1 > budget_tail:
            break
        tail_lines.insert(0, line)
        tail_chars += len(line) + 1
    tail = "\n".join(tail_lines)

    # ─── 3. Milieu structurel : lignes importantes + contexte ───
    middle_start = len(head_lines)
    middle_end = total_lines - len(tail_lines)

    structural_lines: List[str] = []
    structural_chars = 0

    if middle_start < middle_end:
        i = middle_start
        while i < middle_end:
            line = lines[i]
            if _STRUCTURAL_LINE_RE.match(line):
                # Ajouter la ligne structurelle
                if structural_chars + len(line) + 1 > budget_struct:
                    break
                structural_lines.append(line)
                structural_chars += len(line) + 1

                # Ajouter 2-3 lignes de contexte après (utile pour les signatures)
                for j in range(1, 4):
                    idx = i + j
                    if idx >= middle_end:
                        break
                    next_line = lines[idx]
                    if _STRUCTURAL_LINE_RE.match(next_line):
                        # Si la ligne suivante est aussi structurelle,
                        # on la traitera à la prochaine itération de la boucle
                        break
                    if structural_chars + len(next_line) + 1 > budget_struct:
                        break
                    structural_lines.append(next_line)
                    structural_chars += len(next_line) + 1
                i += 3  # Sauter les lignes de contexte déjà ajoutées
            else:
                i += 1

    # ─── 4. Reconstruction ───
    parts: List[str] = [head]

    if structural_lines:
        structural_block = (
            f"\n\n[... STRUCTURE DU FICHIER ({len(structural_lines)} lignes clés) ...]\n"
            + "\n".join(structural_lines)
            + "\n[... FIN DE LA STRUCTURE ...]"
        )
        parts.append(structural_block)

    parts.append(
        f"\n\n[... FIN DU FICHIER ...]\n{tail}"
    )

    result = "".join(parts)

    # ─── 5. Sécurité finale : si on a encore dépassé (arrondis), coupe propre ───
    if len(result) > max_chars:
        result = result[:max_chars] + (
            f"\n\n[...{original_len - max_chars} chars omis "
            f"(troncature finale)...]"
        )

    # ─── 6. Log ───
    if filename:
        logger.info(
            "[Chat/Files] Troncature intelligente '%s' : %d → %d chars "
            "(head=%d, structure=%d, tail=%d)",
            filename,
            original_len,
            len(result),
            len(head),
            structural_chars,
            len(tail),
        )

    return result


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS FICHIERS (INCHANGÉS)
# ══════════════════════════════════════════════════════════════════════════════

def _find_uploaded_file(filename: str) -> Optional[Path]:
    """
    ★ v18.10.2 — Cherche un fichier uploadé dans les répertoires connus.
    Sécurisé contre la traversée de chemin (../).
    """
    if not filename:
        return None

    filename = filename.strip().strip('"').strip("'")
    if not filename:
        return None

    # Sécurité : refuse les traversées de chemin
    if ".." in filename:
        logger.warning("[Chat/Files] Nom suspect rejeté : %r", filename)
        return None

    # Nettoie : garde seulement le nom de base si chemin absolu
    safe_name = Path(filename).name
    if not safe_name:
        return None

    # 1. Recherche directe dans les répertoires connus
    for base in _UPLOAD_DIRS:
        try:
            candidate = base / safe_name
            if candidate.exists() and candidate.is_file():
                return candidate
        except Exception:
            continue

    # 2. Fallback : recherche récursive (limitée)
    for base in _UPLOAD_DIRS:
        if not base.exists() or not base.is_dir():
            continue
        try:
            for found in base.rglob(safe_name):
                if found.is_file():
                    return found
        except Exception:
            continue

    return None


def _read_text_file_safe(path: Path, max_chars: int = MAX_FILE_CHARS) -> str:
    """
    Lit un fichier texte avec fallback d'encodage.
    ★ v18.10.3 : conserve le contenu brut (pas de troncature ici).
    La troncature intelligente se fait via `_smart_truncate_file()`.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = path.read_text(encoding="latin-1")
        except Exception as exc:
            return f"[Impossible de lire {path.name} : {type(exc).__name__}]"
    except Exception as exc:
        return f"[Erreur lecture {path.name} : {type(exc).__name__}]"

    return content


def _extract_attached_files(content: str) -> List[str]:
    """Extrait la liste des noms de fichiers depuis [Fichiers joints : a.md, b.png]."""
    if not isinstance(content, str):
        return []

    files: List[str] = []
    seen = set()
    for match in _FILES_ATTACHED_RE.findall(content):
        for name in re.split(r"[,;]", match):
            name = name.strip()
            if name and name not in seen:
                files.append(name)
                seen.add(name)
    return files


def _inject_file_contents(messages: List[Dict[str, Any]]) -> None:
    """
    ★ v18.10.3 — Détecte [Fichiers joints : ...] dans le dernier message user,
    lit le contenu des fichiers, et l'injecte. Modifie `messages` en place.

    - Fichiers texte → contenu injecté avec TRONCATURE STRUCTURELLE (v19.23)
    - Images → instruction d'appel à analyze_image
    - Vidéos → instruction d'appel aux outils vidéo
    - Fichiers introuvables → message explicite au LLM
    """
    if not messages:
        return

    # Trouve le dernier message user
    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], dict) and messages[i].get("role") == "user":
            last_user_idx = i
            break

    if last_user_idx is None:
        return

    msg = messages[last_user_idx]
    content = msg.get("content", "")
    if not isinstance(content, str):
        return

    attached = _extract_attached_files(content)
    if not attached:
        return

    logger.info(
        "[Chat/Files] %d fichier(s) joint(s) détecté(s) : %s",
        len(attached), attached,
    )

    total_chars = 0
    text_blocks: List[str] = []
    visual_instructions: List[str] = []
    not_found: List[str] = []

    for filename in attached:
        path = _find_uploaded_file(filename)

        if path is None:
            logger.warning("[Chat/Files] Fichier introuvable : %s", filename)
            not_found.append(filename)
            continue

        ext = path.suffix.lower()
        logger.info("[Chat/Files] Fichier trouvé : %s (ext=%s)", path, ext)

        # ─── Fichier texte : lecture directe ───
        if ext in _TEXT_EXTENSIONS or ext == "":
            remaining = MAX_TOTAL_FILE_CHARS - total_chars
            if remaining <= 0:
                text_blocks.append(
                    f"\n[{filename} ignoré : limite globale de contexte atteinte]"
                )
                continue

            raw_content = _read_text_file_safe(path, max_chars=10_000_000)
            file_content = _smart_truncate_file(
                raw_content,
                max_chars=min(MAX_FILE_CHARS, remaining),
                filename=filename,
            )
            total_chars += len(file_content)
            text_blocks.append(
                f"\n=== CONTENU DU FICHIER : {filename} ===\n"
                f"{file_content}\n"
                f"=== FIN DU FICHIER : {filename} ===\n"
            )

        # ─── Image : instruction d'analyse ───
        elif ext in _IMAGE_EXTENSIONS:
            visual_instructions.append(
                f"⚠️ L'utilisateur a joint une IMAGE : `{filename}`\n"
                f"   Chemin : `{path}`\n"
                f"   Pour l'analyser, appelle : "
                f"[ACTION:analyze_image]{{\"image_path\": \"{path}\"}}[/ACTION]"
            )

        # ─── Vidéo ───
        elif ext in _VIDEO_EXTENSIONS:
            visual_instructions.append(
                f"⚠️ L'utilisateur a joint une VIDÉO : `{filename}`\n"
                f"   Chemin : `{path}`\n"
                f"   Utilise les outils vidéo (generate_subtitles, analyze_video...) si demandé."
            )

        # ─── Audio ───
        elif ext in _AUDIO_EXTENSIONS:
            visual_instructions.append(
                f"⚠️ L'utilisateur a joint un AUDIO : `{filename}`\n"
                f"   Chemin : `{path}`"
            )

        # ─── Type inconnu : tentative de lecture texte ───
        else:
            remaining = MAX_TOTAL_FILE_CHARS - total_chars
            if remaining > 0:
                raw_content = _read_text_file_safe(path, max_chars=10_000_000)
                if "\x00" in raw_content[:200]:
                    text_blocks.append(
                        f"\n[{filename} : fichier binaire non lisible, ignoré]"
                    )
                else:
                    file_content = _smart_truncate_file(
                        raw_content,
                        max_chars=min(MAX_FILE_CHARS, remaining),
                        filename=filename,
                    )
                    total_chars += len(file_content)
                    text_blocks.append(
                        f"\n=== CONTENU DU FICHIER : {filename} (type {ext}) ===\n"
                        f"{file_content}\n"
                        f"=== FIN DU FICHIER : {filename} ===\n"
                    )

    # Construction du bloc final à injecter
    extra_parts: List[str] = []

    if text_blocks:
        extra_parts.append(
            "\n\n--- CONTENU DES FICHIERS JOINTS ---"
            + "".join(text_blocks)
            + "\n--- FIN DU CONTENU DES FICHIERS JOINTS ---"
        )

    if visual_instructions:
        extra_parts.append(
            "\n\n--- INSTRUCTIONS FICHIERS VISUELS ---\n"
            + "\n\n".join(visual_instructions)
            + "\n--- FIN DES INSTRUCTIONS FICHIERS VISUELS ---"
        )

    if not_found:
        extra_parts.append(
            "\n\n--- FICHIERS INTROUVABLES ---\n"
            + "\n".join(
                f"⚠️ `{name}` : fichier introuvable dans les répertoires d'upload. "
                f"Dis à l'utilisateur qu'il doit le ré-uploader."
                for name in not_found
            )
            + "\n--- FIN DES FICHIERS INTROUVABLES ---"
        )

    if extra_parts:
        msg["content"] = content + "".join(extra_parts)
        logger.info(
            "[Chat/Files] ✅ Injection : %d chars (texte) | %d instructions visuelles | %d introuvables",
            total_chars, len(visual_instructions), len(not_found),
        )
    else:
        logger.warning("[Chat/Files] Aucun contenu à injecter (fichiers vides ou non trouvés)")