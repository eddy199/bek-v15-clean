# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — PathGuard : anti path-traversal renforcé
# ------------------------------------------------------------------------------
# ★ v16.1 (2026-11-06) — FIX :
#   - Bug #1 : distinction "nom invalide" vs "hors workspace" (audit log clair)
#   - Bug #2 : refus explicite des device paths \\?\ et \\.\
#   - Bug #3 : _check_symlinks teste aussi le fichier cible (pas que les parents)
#   - Bug #4 : safe_path_in vérifie que le chemin absolu est bien DANS base
#   - Docstrings en raw strings pour éviter les SyntaxWarning sur \C \? etc.
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
MAX_TOTAL_PATH_LEN = 4096

# ── Noms réservés Windows ───────────────────────────────────────────────────
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

# ── Caractères interdits (contrôle, null, etc.) ─────────────────────────────
_FORBIDDEN_CHARS_RE = re.compile(r"[\x00-\x1f<>:\"|?*]")

# ★ FIX #2 : device paths Windows à refuser explicitement
#   (strings normales, pas de raw pour éviter les confusions d'échappement)
_DEVICE_PATH_PREFIXES = (
    "\\\\?\\",   # \\?\  (4 chars)
    "\\\\.\\",   # \\.\  (4 chars)
    "//?/",      # //?/  (4 chars)
    "//./",      # //./  (4 chars)
)


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


def _is_device_path(raw: str) -> bool:
    r"""★ FIX #2 : détecte \\?\C:\... et \\.\C:\... (device paths Windows)."""
    return any(raw.startswith(p) for p in _DEVICE_PATH_PREFIXES)


def _is_absolute_windows_path(raw: str) -> bool:
    r"""Détecte un chemin absolu Windows : C:\..., D:/..., \\server\share\..."""
    if not isinstance(raw, str) or len(raw) < 2:
        return False
    # C:\... ou C:/...
    if raw[1] == ":" and raw[0].isalpha():
        return True
    # \\server\share (UNC) — mais PAS \\?\ (device path, refusé plus haut)
    if raw.startswith("\\\\") and not _is_device_path(raw):
        return True
    if raw.startswith("//") and not _is_device_path(raw):
        return True
    return False


def _resolve_absolute_safely(raw: str) -> Optional[Path]:
    r"""
    ★ FIX #1 : tente de résoudre un chemin absolu et retourne le Path
    si et seulement s'il est dans une ALLOWED_DIR. Sinon None.
    """
    if _is_device_path(raw):
        return None
    try:
        normalized = raw.replace("\\\\", "\\").replace("\\", "/")
        candidate = Path(normalized).resolve(strict=False)
    except Exception:
        return None

    for allowed in ALLOWED_DIRS:
        try:
            candidate.relative_to(allowed)
            return candidate
        except ValueError:
            continue
    return None


def _sanitize_name(raw: str) -> Optional[str]:
    r"""
    Normalise et valide un nom de fichier OU un chemin absolu.
    Retourne None si invalide.
    """
    if not isinstance(raw, str) or not raw:
        return None

    # ★ FIX #2 : device paths refusés d'emblée
    if _is_device_path(raw):
        return None

    # ★ FIX #1 : chemins absolus (Windows ou UNC) → résolution dédiée
    if _is_absolute_windows_path(raw):
        resolved = _resolve_absolute_safely(raw)
        if resolved is None:
            return None  # hors workspace
        return str(resolved)

    # ── Détection EXPLICITE du path traversal ───────────────────────────────
    normalized_sep = raw.replace("\\", "/")
    parts = normalized_sep.split("/")
    if any(p == ".." for p in parts):
        return None
    if normalized_sep.startswith("/"):
        return None
    if raw.startswith("\\\\") or raw.startswith("//"):
        return None

    # Normalisation Unicode
    try:
        name = unicodedata.normalize("NFKC", raw)
    except Exception:
        return None

    # Octets nuls et caractères interdits
    if "\x00" in name or _FORBIDDEN_CHARS_RE.search(name):
        return None

    # Dernier composant
    name = Path(name).name.strip()

    stripped_dots = name.replace(".", "").strip()
    if not stripped_dots:
        return None

    if len(name) > MAX_FILENAME_LEN:
        return None

    if _is_reserved_name(name):
        return None

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
    r"""
    ★ FIX #3 : teste le fichier cible ET tous ses parents jusqu'à la racine
    autorisée. Refuse si n'importe quel élément est un symlink.
    """
    # Test direct du path (même inexistant, is_symlink() ne lève pas)
    try:
        if path.is_symlink():
            return False
    except OSError:
        return False

    current = path.parent if path.parent != path else path
    for _ in range(64):  # profondeur max anti-boucle
        if current == current.parent:
            break
        try:
            if current.is_symlink():
                return False
        except OSError:
            return False
        # Si le parent est dans ALLOWED_DIRS, on s'arrête (les parents
        # au-dessus sont déjà de confiance)
        if _is_inside_allowed(current):
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

    if len(filename) > MAX_TOTAL_PATH_LEN:
        _audit("path_too_long", filename[:80])
        raise ValueError("Chemin trop long.")

    # ★ FIX #2 (renforcé) : check device path AVANT tout, quel que soit le format
    if _is_device_path(filename):
        _audit("device_path_forbidden", filename)
        raise ValueError(f"Device path refusé : {filename}")

    # ★ FIX #1 : on distingue "invalide" de "hors workspace"
    if _is_absolute_windows_path(filename):
        candidate = _resolve_absolute_safely(filename)
        if candidate is None:
            _audit("outside_allowed_dirs", filename)
            raise ValueError(f"Accès refusé hors workspace : {filename}")
    else:
        name = _sanitize_name(filename)
        if name is None:
            _audit("invalid_name", filename)
            raise ValueError(f"Nom de fichier invalide : {filename!r}")
        candidate = (WORKSPACE / name).resolve(strict=False)

    if not _is_inside_allowed(candidate):
        _audit("outside_allowed_dirs", filename, f"candidat={candidate}")
        raise ValueError(f"Accès refusé hors workspace : {filename}")

    if not _check_symlinks(candidate):
        _audit("symlink_detected", filename)
        raise ValueError(f"Symlink refusé : {filename}")

    if candidate.exists() and candidate.is_dir():
        _audit("path_is_directory", filename, f"candidat={candidate}")
        raise ValueError(f"Le chemin pointe vers un dossier : {filename}")

    return candidate


def find_existing(filename: str) -> Optional[Path]:
    """
    Cherche un fichier existant dans WORKSPACE / uploads / generated.
    Ne retourne JAMAIS un chemin hors des dossiers autorisés.
    """
    if not isinstance(filename, str) or not filename:
        return None

    # ★ FIX #2 : device paths refusés
    if _is_device_path(filename):
        _audit("find_existing_device_path", filename)
        return None

    # ★ FIX #1 : chemins absolus
    if _is_absolute_windows_path(filename):
        resolved = _resolve_absolute_safely(filename)
        if resolved is None:
            _audit("find_existing_outside", filename)
            return None
        if not _check_symlinks(resolved):
            return None
        try:
            if resolved.is_file():
                return resolved
        except OSError:
            pass
        return None

    # Noms relatifs : on cherche dans les ALLOWED_DIRS
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
    r"""
    Variante : autorise un fichier DANS un dossier spécifique (ex. uploads/, generated/).
    Utile pour forcer l'écriture dans un sous-dossier précis.

    ★ FIX #4 : si `filename` est absolu, il DOIT être contenu dans `base_dir`.
    """
    base = Path(base_dir).resolve()
    if base not in ALLOWED_DIRS:
        _audit("base_dir_not_allowed", filename, f"base={base}")
        raise ValueError(f"Dossier de base non autorisé : {base}")

    # ★ FIX #2 : device paths
    if _is_device_path(filename):
        _audit("safe_path_in_device_path", filename)
        raise ValueError(f"Device path refusé : {filename}")

    # ★ FIX #4 : chemins absolus → doivent être DANS base
    if _is_absolute_windows_path(filename):
        candidate = _resolve_absolute_safely(filename)
        if candidate is None:
            _audit("safe_path_in_outside_allowed", filename)
            raise ValueError(f"Accès refusé hors workspace : {filename}")
        try:
            candidate.relative_to(base)
        except ValueError:
            _audit(
                "safe_path_in_not_in_base", filename,
                f"candidat={candidate} base={base}",
            )
            raise ValueError(
                f"Le chemin absolu doit être dans {base} : {filename}"
            )
    else:
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
        str(GENERATED_DIR / "audit_bek-v15-clean.md"),
        str(FILES_DIR / "rapport.md"),
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
        "C:\\Windows\\System32\\config\\SAM",
        "\\\\?\\C:\\Windows\\System32\\config\\SAM",
        "\\\\.\\PhysicalDrive0",
    ]

    print("=== Tests OK (doivent passer) ===")
    for t in tests_ok:
        try:
            p = safe_path(t)
            print(f"✅ {t!r:60s} → {p}")
        except ValueError as e:
            print(f"❌ {t!r:60s} → {e}")

    print("\n=== Tests KO (doivent être refusés) ===")
    for t in tests_ko:
        try:
            p = safe_path(t)
            print(f"⚠️  {t!r:60s} → ACCEPTÉ (BAD) {p}")
        except ValueError as e:
            print(f"🛡️ {t!r:60s} → refusé : {str(e)[:60]}")

    print("\n=== find_existing ===")
    print("find_existing('mon_fichier.txt')  =", find_existing("mon_fichier.txt"))
    print("find_existing('../../etc/passwd') =", find_existing("../../etc/passwd"))
    print(f"find_existing('{GENERATED_DIR / 'audit_bek-v15-clean.md'}')  =", find_existing(str(GENERATED_DIR / "audit_bek-v15-clean.md")))
    print("find_existing('\\\\?\\C:\\Windows\\x')  =", find_existing("\\\\?\\C:\\Windows\\x"))