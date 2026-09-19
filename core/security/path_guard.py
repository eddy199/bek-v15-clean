# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — PathGuard : anti path-traversal renforcé
# ------------------------------------------------------------------------------
# Protections :
#   • resolve() + is_relative_to() double vérification
#   • Détection symlinks
#   • Détection octets nuls (\x00)
#   • Détection noms réservés Windows (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
#   • Limite de longueur (255 caractères)
#   • Normalisation Unicode (NFKC)
#   • Détection EXPLICITE du path traversal (../, ..\, absolu)
#   • Refus si le chemin pointe vers un dossier
#   • Audit log de chaque tentative d'accès refusée
#   • Whitelist stricte : uploads/, generated/, workspace/ (racine seulement)
# ==============================================================================

from __future__ import annotations

import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Iterable, List, Optional

from core.paths import WORKSPACE_DIR, FILES_DIR, GENERATED_DIR

logger = logging.getLogger("bek.security.path_guard")

# ── Dossiers autorisés (résolus absolus) ────────────────────────────────────
WORKSPACE = Path(WORKSPACE_DIR).resolve()
ALLOWED_DIRS: List[Path] = [
    WORKSPACE,
    Path(FILES_DIR).resolve(),
    Path(GENERATED_DIR).resolve(),
]

# ── Limites ─────────────────────────────────────────────────────────────────
MAX_FILENAME_LEN = 255
MAX_TOTAL_PATH_LEN = 4096  # limite Windows

# ── Noms réservés Windows (insensibles à la casse) ──────────────────────────
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

# ── Caractères interdits (contrôle, null, etc.) ─────────────────────────────
_FORBIDDEN_CHARS_RE = re.compile(r"[\x00-\x1f<>:\"|?*]")


# ==============================================================================
# HELPERS
# ==============================================================================
def _audit(reason: str, filename: str, extra: str = "") -> None:
    """Log d'audit pour toute tentative suspecte."""
    logger.warning(
        "🛡️ [PathGuard] REFUS | raison=%s | fichier=%r | %s",
        reason, filename, extra,
    )


def _is_reserved_name(name: str) -> bool:
    """Vérifie si le nom (sans extension) est un nom réservé Windows."""
    stem = name.split(".")[0].lower().strip()
    return stem in _WINDOWS_RESERVED


def _sanitize_name(raw: str) -> Optional[str]:
    """
    Normalise et valide un nom de fichier.
    Retourne None si invalide.
    """
    if not isinstance(raw, str) or not raw:
        return None

    # ── Détection EXPLICITE du path traversal AVANT toute normalisation ────
    normalized_sep = raw.replace("\\", "/")
    parts = normalized_sep.split("/")
    if any(p == ".." for p in parts):
        return None
    # Refuse tout chemin absolu (C:\..., /etc/..., \\server\share)
    if normalized_sep.startswith("/") or (len(raw) >= 2 and raw[1] == ":"):
        return None
    if raw.startswith("\\\\") or raw.startswith("//"):
        return None

    # Normalisation Unicode (NFKC élimine ligatures & co)
    try:
        name = unicodedata.normalize("NFKC", raw)
    except Exception:
        return None

    # Octets nuls et caractères de contrôle
    if "\x00" in name or _FORBIDDEN_CHARS_RE.search(name):
        return None

    # Récupère le dernier composant (après filtrage strict ci-dessus)
    name = Path(name).name

    # Strip des espaces (Windows les retire silencieusement)
    name = name.strip()

    # Refus si vide, ou si composé uniquement de points et espaces
    stripped_dots = name.replace(".", "").strip()
    if not stripped_dots:
        return None

    # Longueur
    if len(name) > MAX_FILENAME_LEN:
        return None

    # Noms réservés Windows
    if _is_reserved_name(name):
        return None

    # Refus des noms vides ou uniquement des points
    if name in {"", ".", ".."}:
        return None

    return name


def _is_inside_allowed(path: Path) -> bool:
    """Vérifie que le path résolu est dans une des ALLOWED_DIRS."""
    try:
        resolved = path.resolve(strict=False)
    except Exception:
        return False

    for allowed in ALLOWED_DIRS:
        try:
            resolved.relative_to(allowed)
            return True
        except ValueError:
            continue
    return False


def _check_symlinks(path: Path) -> bool:
    """
    Refuse si un des parents (jusqu'à la racine autorisée) est un symlink.
    """
    current = path
    for _ in range(32):  # profondeur max anti-boucle
        if current == current.parent:
            break
        try:
            if current.is_symlink():
                return False
        except OSError:
            return False
        if _is_inside_allowed(current.parent):
            break
        current = current.parent
    return True


# ==============================================================================
# API PUBLIQUE
# ==============================================================================
def safe_path(filename: str) -> Path:
    """
    Renvoie un chemin garanti DANS le workspace.
    Lève ValueError avec message d'audit en cas de tentative dangereuse.
    """
    if not isinstance(filename, str) or not filename.strip():
        _audit("empty_filename", filename)
        raise ValueError("Nom de fichier vide ou invalide.")

    # Longueur totale
    if len(filename) > MAX_TOTAL_PATH_LEN:
        _audit("path_too_long", filename[:80])
        raise ValueError("Chemin trop long.")

    # Normalisation + validation
    name = _sanitize_name(filename)
    if name is None:
        _audit("invalid_name", filename)
        raise ValueError(f"Nom de fichier invalide : {filename!r}")

    # Construit le chemin candidat à la racine du workspace
    candidate = (WORKSPACE / name).resolve(strict=False)

    # Doit être dans une ALLOWED_DIR
    if not _is_inside_allowed(candidate):
        _audit("outside_allowed_dirs", filename, f"candidat={candidate}")
        raise ValueError(f"Accès refusé hors workspace : {filename}")

    # Symlink check
    if not _check_symlinks(candidate):
        _audit("symlink_detected", filename)
        raise ValueError(f"Symlink refusé : {filename}")

    # Refus si le chemin pointe vers un dossier existant
    if candidate.exists() and candidate.is_dir():
        _audit("path_is_directory", filename, f"candidat={candidate}")
        raise ValueError(f"Le chemin pointe vers un dossier : {filename}")

    return candidate


def find_existing(filename: str) -> Optional[Path]:
    """
    Cherche un fichier existant dans WORKSPACE / uploads / generated.
    Ne retourne JAMAIS un chemin hors des dossiers autorisés.
    """
    name = _sanitize_name(filename)
    if name is None:
        _audit("find_existing_invalid_name", filename)
        return None

    for directory in ALLOWED_DIRS:
        try:
            p = (directory / name).resolve(strict=False)
        except Exception:
            continue

        if not _is_inside_allowed(p):
            continue
        if not _check_symlinks(p):
            continue

        try:
            if p.is_file():
                return p
        except OSError:
            continue

    return None


def safe_path_in(filename: str, base_dir: Path | str) -> Path:
    """
    Variante : autorise un fichier DANS un dossier spécifique (ex. uploads/, generated/).
    Utile pour forcer l'écriture dans un sous-dossier précis.
    """
    base = Path(base_dir).resolve()
    if base not in ALLOWED_DIRS:
        _audit("base_dir_not_allowed", filename, f"base={base}")
        raise ValueError(f"Dossier de base non autorisé : {base}")

    name = _sanitize_name(filename)
    if name is None:
        _audit("safe_path_in_invalid_name", filename)
        raise ValueError(f"Nom de fichier invalide : {filename!r}")

    candidate = (base / name).resolve(strict=False)

    if not _is_inside_allowed(candidate):
        _audit("safe_path_in_outside", filename, f"candidat={candidate}")
        raise ValueError(f"Accès refusé : {filename}")

    if not _check_symlinks(candidate):
        _audit("safe_path_in_symlink", filename)
        raise ValueError(f"Symlink refusé : {filename}")

    if candidate.exists() and candidate.is_dir():
        _audit("safe_path_in_directory", filename, f"candidat={candidate}")
        raise ValueError(f"Le chemin pointe vers un dossier : {filename}")

    return candidate


def list_allowed_dirs() -> Iterable[str]:
    """Retourne les dossiers autorisés (utile pour debug/UI)."""
    return [str(d) for d in ALLOWED_DIRS]


# ==============================================================================
# TEST DIRECT
# ==============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    tests_ok = [
        "mon_fichier.txt",
        "subdir/mon_fichier.txt",
        "image_2025.png",
    ]
    tests_ko = [
        "../../../etc/passwd",
        "..\\..\\Windows\\System32\\config\\SAM",
        "file\x00name.txt",
        "CON",
        "NUL.txt",
        "LPT1",
        "a" * 300,
        "",
        ". . .",
    ]

    print("=== Tests OK (doivent passer) ===")
    for t in tests_ok:
        try:
            p = safe_path(t)
            print(f"✅ {t!r:40s} → {p}")
        except ValueError as e:
            print(f"❌ {t!r:40s} → {e}")

    print("\n=== Tests KO (doivent être refusés) ===")
    for t in tests_ko:
        try:
            p = safe_path(t)
            print(f"⚠️  {t!r:40s} → ACCEPTÉ (BAD) {p}")
        except ValueError as e:
            print(f"🛡️ {t!r:40s} → refusé : {str(e)[:60]}")

    print("\n=== find_existing ===")
    print("find_existing('mon_fichier.txt')  =", find_existing("mon_fichier.txt"))
    print("find_existing('../../etc/passwd') =", find_existing("../../etc/passwd"))