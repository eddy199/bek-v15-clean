# -*- coding: utf-8 -*-
"""BEK code tools. NOTE: these guards are not an OS-level sandbox."""
from __future__ import annotations

import ast
import logging
import os
import re
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bek.tools.code")
BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from core.paths import CODE_WORKSPACE as _CODE_WORKSPACE  # noqa: F401
    # ★ FIX #1 : chemin en dur — ne dépend plus de core.paths
    WORKSPACE = Path("F:/workspacekimi").resolve()
except Exception:
    # Fallback sécurisé si le chemin en dur échoue
    WORKSPACE = Path(os.environ.get(
        "BEK_CODE_WORKSPACE",
        os.environ.get("BEK_WORKSPACE", BASE_DIR / "workspace")
    )).resolve()

WORKSPACE.mkdir(parents=True, exist_ok=True)

BANNED_DIRS = {
    ".git", "__pycache__", "node_modules", "venv", ".venv", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".idea",
}
SENSITIVE_NAMES = {
    ".env", "env.txt", "id_rsa", "id_ed25519", "credentials.json", "secrets.json",
    ".npmrc", ".pypirc",
}
SENSITIVE_SUFFIXES = {".pem", ".pfx", ".key"}
SECRET_MARKERS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "PRIVATE", "CREDENTIAL")

MAX_READ_CHARS = 400_000
MAX_WRITE_CHARS = 2_000_000
MAX_COMMAND_CHARS = 8_000
MAX_COMMAND_TIMEOUT = 300
MAX_OUTPUT_CHARS = 8_000
MAX_GREP_RESULTS = 500
MAX_GLOB_RESULTS = 2_000
MAX_GREP_FILE_BYTES = 2_000_000

SHELL_META = re.compile(r"[;&|<>`\n\r]")
DESTRUCTIVE_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"(?i)\bmkfs(?:\.|\s)"), re.compile(r"(?i)\bdd\s+if="),
    re.compile(r"(?i)\bformat\s+[a-z]:"), re.compile(r"(?i)\bshutdown(?:\.exe)?\b"),
    re.compile(r"(?i)\breg\s+delete\b"), re.compile(r"(?i)\bbcdedit\b"),
)
ALLOWED_EXECUTABLES = {
    "python", "python3", "python.exe", "py", "pytest", "pytest.exe",
    "node", "node.exe", "npm", "npm.cmd", "npx", "npx.cmd",
    "git", "git.exe", "ruff", "mypy", "black", "go", "cargo", "rustc",
    "dotnet", "java", "javac", "php", "ruby", "bundle", "rspec",
    "pwd", "whoami", "where", "which",
}


def _first_text(primary: Any, kwargs: Dict[str, Any], aliases: Tuple[str, ...],
                default: str = "") -> str:
    if isinstance(primary, str) and primary.strip():
        return primary
    if primary is not None and not isinstance(primary, str):
        return str(primary)
    for key in aliases:
        value = kwargs.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if value is not None and not isinstance(value, str):
            return str(value)
    return default


def _normalize_path_input(raw_path: str) -> str:
    if not isinstance(raw_path, str):
        return ""
    value = raw_path.strip().strip("\"'`").replace("\\", "/")
    value = re.sub(r"(?i)^\s*(?:mkdir|md)\s+(?:-[a-z]+\s+)*", "", value)
    value = re.sub(r"(?i)^\s*-p\s+", "", value)
    prefix = WORKSPACE.name + "/"
    if value.lower().startswith(prefix.lower()):
        value = value[len(prefix):]
    return value.strip()


def _is_sensitive_path(path: Path) -> bool:
    name = path.name.lower()
    return name in SENSITIVE_NAMES or path.suffix.lower() in SENSITIVE_SUFFIXES or name.startswith(".env.")


def _safe_resolve(path: str, *, allow_root: bool = False) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Chemin vide.")
    raw = _normalize_path_input(path)
    if not raw or "\x00" in raw:
        raise ValueError("Chemin invalide.")
    candidate = Path(raw)
    lexical = candidate if candidate.is_absolute() else WORKSPACE / candidate
    if ".." in lexical.parts:
        raise ValueError("Les segments '..' sont interdits.")
    try:
        lexical = lexical.absolute()
        lexical.relative_to(WORKSPACE)
    except ValueError as exc:
        raise ValueError(f"Chemin hors workspace refusé : {path}") from exc

    cursor = WORKSPACE
    if cursor.is_symlink():
        raise ValueError("Le workspace ne doit pas être un lien symbolique.")
    for part in lexical.relative_to(WORKSPACE).parts:
        if part in ("", "."):
            continue
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"Lien symbolique interdit : {cursor.name}")

    resolved = lexical.resolve(strict=False)
    try:
        resolved.relative_to(WORKSPACE)
    except ValueError as exc:
        raise ValueError(f"Chemin hors workspace refusé : {path}") from exc
    if resolved == WORKSPACE and not allow_root:
        raise ValueError("L'opération sur la racine du workspace n'est pas autorisée.")
    if _is_sensitive_path(resolved):
        raise ValueError(f"Accès interdit au fichier sensible : {resolved.name}")
    return resolved


def _relative(target: Path) -> str:
    try:
        return str(target.relative_to(WORKSPACE)) or "."
    except ValueError:
        return str(target)


def _sanitized_env() -> Dict[str, str]:
    env = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if any(marker in upper for marker in SECRET_MARKERS):
            continue
        if upper in {"PYTHONSTARTUP", "PYTHONINSPECT", "BASH_ENV", "ENV", "PYTHONPATH"}:
            continue
        env[key] = value
    env["BEK_CODE_WORKSPACE"] = str(WORKSPACE)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _atomic_write(target: Path, content: str) -> None:
    _safe_resolve(str(target.relative_to(WORKSPACE)))
    target.parent.mkdir(parents=True, exist_ok=True)
    _safe_resolve(str(target.relative_to(WORKSPACE)))
    fd, tmp_name = tempfile.mkstemp(prefix=".bek-tmp-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        _safe_resolve(str(target.relative_to(WORKSPACE)))
        os.replace(tmp_name, target)
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def _iter_files(root: Path, include: str = "*"):
    if root.is_file():
        if not root.is_symlink():
            yield root
        return
    if not root.is_dir():
        return
    for current, dirs, files in os.walk(root, followlinks=False):
        here = Path(current)
        dirs[:] = [d for d in dirs if d not in BANNED_DIRS and not (here / d).is_symlink()]
        for name in files:
            candidate = here / name
            if not candidate.is_symlink() and (include == "*" or candidate.match(include)):
                yield candidate


def read_file_map(path: str = "", **kwargs: Any) -> Dict[str, Any]:
    """
    Lit un fichier et retourne sa structure (CodeMap) au lieu du texte brut.
    Si le fichier est gros, le LLM peut ensuite lire une plage de lignes précise.
    """
    try:
        raw = _first_text(path, kwargs, ("file", "filename", "target_file"))
        target = _safe_resolve(raw)
        if not target.exists():
            return {"status": "error", "message": f"Fichier introuvable : {raw}"}

        with target.open("r", encoding="utf-8", errors="replace") as stream:
            content = stream.read()

        total_lines = content.count('\n') + 1
        ext = target.suffix.lower()

        if ext == ".py":
            try:
                tree = ast.parse(content)
                map_data = []
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        name = node.name
                        type_str = "class" if isinstance(node, ast.ClassDef) else "def"
                        map_data.append({
                            "name": name,
                            "type": type_str,
                            "start_line": node.lineno,
                            "end_line": node.end_lineno if hasattr(node, 'end_lineno') else "?"
                        })

                map_lines = [f"{m['type']} {m['name']} [l.{m['start_line']}-{m['end_line']}]" for m in map_data]
                map_str = "\n".join(map_lines[:50])

                return {
                    "status": "success",
                    "path": _relative(target),
                    "total_lines": total_lines,
                    "type": "python",
                    "codemap": map_str,
                    "message": "Utilise 'read_file' avec start_line et end_line pour lire une fonction précise."
                }
            except Exception:
                pass

        preview = "\n".join(content.splitlines()[:20])
        return {
            "status": "success",
            "path": _relative(target),
            "total_lines": total_lines,
            "type": ext.replace(".", ""),
            "codemap": f"Fichier non-Python ({total_lines} lignes).\nAperçu:\n{preview}",
            "message": "Utilise 'read_file' avec start_line/end_line pour lire plus loin."
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def read_file(path: str = "", start_line: int = 1, end_line: int = 0,
              max_chars: int = MAX_READ_CHARS, **kwargs: Any) -> Dict[str, Any]:
    try:
        raw = _first_text(path, kwargs, ("file", "filename", "target_file"))
        target = _safe_resolve(raw)
        if not target.exists():
            return {"status": "error", "message": f"Fichier introuvable : {raw}"}
        if not target.is_file():
            return {"status": "error", "message": f"{raw} est un dossier, utilise ls."}
        limit = max(1, min(int(max_chars or MAX_READ_CHARS), MAX_READ_CHARS))
        start, end_req = max(1, int(start_line or 1)), int(end_line or 0)
        with target.open("r", encoding="utf-8", errors="replace") as stream:
            lines = stream.readlines()
        total = len(lines)
        end = total if end_req <= 0 else min(end_req, total)
        content = "".join(lines[start - 1:end])
        return {"status": "success", "path": _relative(target), "total_lines": total,
                "start_line": start, "end_line": end, "truncated": len(content) > limit,
                "content": content[:limit]}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def write_file(path: str = "", content: str = "", **kwargs: Any) -> Dict[str, Any]:
    try:
        raw = _first_text(path, kwargs, ("file", "filename", "target_file", "name"))
        text = _first_text(content, kwargs, ("text", "data", "code", "body", "value", "new_string"))
        if not raw:
            return {"status": "error", "message": "Clé 'path' manquante."}
        if len(text) > MAX_WRITE_CHARS:
            return {"status": "error", "message": "Contenu trop volumineux."}
        target = _safe_resolve(raw)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = _safe_resolve(raw)
        _atomic_write(target, text)
        return {"status": "success", "path": _relative(target), "chars": len(text),
                "message": f"Écrit : {_relative(target)} ({len(text)} caractères)."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def append_file(path: str = "", content: str = "", **kwargs: Any) -> Dict[str, Any]:
    try:
        raw = _first_text(path, kwargs, ("file", "filename", "target_file", "name"))
        text = _first_text(content, kwargs, ("text", "data", "code", "body", "value"))
        if not raw:
            return {"status": "error", "message": "Clé 'path' manquante."}
        if len(text) > MAX_WRITE_CHARS:
            return {"status": "error", "message": "Contenu ajouté trop volumineux."}
        target = _safe_resolve(raw)
        previous = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
        if len(previous) + len(text) > MAX_WRITE_CHARS:
            return {"status": "error", "message": "Taille finale supérieure à la limite."}
        target.parent.mkdir(parents=True, exist_ok=True)
        target = _safe_resolve(raw)
        _atomic_write(target, previous + text)
        return {"status": "success", "path": _relative(target), "appended_chars": len(text),
                "total_size": target.stat().st_size}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def edit_file(path: str = "", old_string: str = "", new_string: str = "", **kwargs: Any) -> Dict[str, Any]:
    try:
        raw = _first_text(path, kwargs, ("file", "filename", "target_file"))
        old = _first_text(old_string, kwargs, ("old_str", "search", "find", "target"))
        new = _first_text(new_string, kwargs, ("new_str", "replace", "replacement"))
        if not raw or not old:
            return {"status": "error", "message": "Clés 'path' et 'old_string' requises."}
        target = _safe_resolve(raw)
        if not target.is_file():
            return {"status": "error", "message": f"Fichier introuvable : {raw}"}
        original = target.read_text(encoding="utf-8", errors="replace")
        if old not in original:
            return {"status": "error", "message": f"old_string non trouvé dans {raw}."}

        # ★ Remplace TOUTES les occurrences (fix calculateur conservé)
        updated = original.replace(old, new)

        if len(updated) > MAX_WRITE_CHARS:
            return {"status": "error", "message": "Fichier modifié trop volumineux."}
        _atomic_write(target, updated)
        return {"status": "success", "path": _relative(target), "message": f"Modifié : {_relative(target)}."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def create_dir(path: str = "", **kwargs: Any) -> Dict[str, Any]:
    try:
        raw = _first_text(path, kwargs, ("file", "filename", "dir", "name", "target_file"))
        if not raw:
            return {"status": "error", "message": "Clé 'path' manquante."}
        target = _safe_resolve(raw)
        target.mkdir(parents=True, exist_ok=True)
        return {"status": "success", "path": _relative(target), "message": f"Dossier prêt : {_relative(target)}."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def grep(pattern: str = "", path: str = ".", max_results: int = 100,
         include: str = "*", **kwargs: Any) -> Dict[str, Any]:
    try:
        query = _first_text(pattern, kwargs, ("query", "regex", "search"))
        if not query:
            return {"status": "error", "message": "Clé 'pattern' manquante."}
        if len(query) > 1000:
            return {"status": "error", "message": "Expression trop longue."}
        root = _safe_resolve(_first_text(path, kwargs, ("file", "dir"), default=".") or ".", allow_root=True)
        regex = re.compile(query)
        limit = max(1, min(int(max_results or 100), MAX_GREP_RESULTS))
        results: List[Dict[str, Any]] = []
        for fp in _iter_files(root, include or "*"):
            if _is_sensitive_path(fp) or fp.stat().st_size > MAX_GREP_FILE_BYTES:
                continue
            try:
                with fp.open("r", encoding="utf-8", errors="replace") as stream:
                    for line_no, line in enumerate(stream, 1):
                        if regex.search(line):
                            results.append({"file": _relative(fp), "line": line_no, "text": line.strip()[:300]})
                            if len(results) >= limit:
                                return {"status": "success", "matches": results, "count": len(results), "truncated": True}
            except OSError:
                continue
        return {"status": "success", "matches": results, "count": len(results), "truncated": False}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def glob_files(pattern: str = "", **kwargs: Any) -> Dict[str, Any]:
    try:
        query = _first_text(pattern, kwargs, ("query", "glob"), default="*") or "*"
        if len(query) > 500 or query.startswith(("/", "\\")) or ".." in Path(query).parts:
            return {"status": "error", "message": "Motif invalide ou hors workspace."}
        matches = []
        for candidate in WORKSPACE.glob(query):
            if candidate.is_symlink():
                continue
            try:
                candidate.resolve().relative_to(WORKSPACE)
            except (ValueError, OSError):
                continue
            if candidate.is_file() and not _is_sensitive_path(candidate) and not any(p in BANNED_DIRS for p in candidate.parts):
                matches.append(_relative(candidate))
                if len(matches) >= MAX_GLOB_RESULTS:
                    break
        return {"status": "success", "files": matches, "count": len(matches),
                "truncated": len(matches) >= MAX_GLOB_RESULTS}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def ls(path: str = ".", **kwargs: Any) -> Dict[str, Any]:
    try:
        raw = _first_text(path, kwargs, ("file", "dir", "target_file"), default=".") or "."
        target = _safe_resolve(raw, allow_root=True)
        if not target.exists():
            return {"status": "error", "message": f"Introuvable : {raw}"}
        if target.is_file():
            return {"status": "success", "type": "file", "path": _relative(target), "size": target.stat().st_size}
        entries = []
        for item in sorted(target.iterdir()):
            if item.name in BANNED_DIRS or _is_sensitive_path(item) or item.is_symlink():
                continue
            entries.append({"name": item.name, "type": "dir" if item.is_dir() else "file",
                            "size": item.stat().st_size if item.is_file() else 0})
            if len(entries) >= 1000:
                break
        return {"status": "success", "path": _relative(target), "entries": entries, "count": len(entries)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def bash(cmd: str = "", command: str = "", timeout: int = 60, cwd: str = "", **kwargs: Any) -> Dict[str, Any]:
    actual = _first_text(cmd, kwargs, ("command", "shell", "script")) or command
    if not actual or not actual.strip():
        return {"status": "error", "message": "Aucune commande fournie (utilise 'cmd')."}
    if len(actual) > MAX_COMMAND_CHARS:
        return {"status": "error", "message": "Commande trop longue."}
    for pattern in DESTRUCTIVE_PATTERNS:
        if pattern.search(actual):
            logger.warning("[bash] commande bloquée : %s", actual[:160])
            return {"status": "error", "message": "Commande bloquée par le garde-fou BEK."}
    if SHELL_META.search(actual):
        return {"status": "error", "message": "Shell désactivé : une seule commande sans opérateurs ni redirections."}
    try:
        argv = shlex.split(actual, posix=(os.name != "nt"))
        if not argv:
            return {"status": "error", "message": "Commande vide."}
        executable = Path(argv[0]).name.lower()

        if executable in ("cd", "chdir", "pushd", "popd"):
            return {"status": "error", "message": "Utilise 'ls' pour voir un dossier, ou 'read_file' avec un chemin absolu. 'cd' n'est pas nécessaire ici."}

        if executable not in ALLOWED_EXECUTABLES:
            return {"status": "error", "message": f"Exécutable non autorisé : {executable}. Autorises : {sorted(ALLOWED_EXECUTABLES)}"}

        work_dir = _safe_resolve(cwd, allow_root=True) if cwd else WORKSPACE
        if not work_dir.is_dir():
            return {"status": "error", "message": f"Dossier de travail invalide : {cwd}"}
        timeout_s = max(1, min(int(timeout or 60), MAX_COMMAND_TIMEOUT))
        started = time.monotonic()
        result = subprocess.run(
            argv, shell=False, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout_s, cwd=str(work_dir), env=_sanitized_env(),
            stdin=subprocess.DEVNULL, close_fds=True,
        )
        return {"status": "success" if result.returncode == 0 else "error",
                "exit_code": result.returncode, "stdout": (result.stdout or "")[-MAX_OUTPUT_CHARS:],
                "stderr": (result.stderr or "")[-MAX_OUTPUT_CHARS:],
                "execution_ms": round((time.monotonic() - started) * 1000, 2), "command": argv}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"Timeout ({timeout}s).", "timed_out": True}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "error_type": type(exc).__name__}


def search_skills(query: str = "", **kwargs: Any) -> Dict[str, Any]:
    real_query = _first_text(query, kwargs, ("q", "search", "pattern"))
    registry = None
    for module_name in ("skill_registry", "bek.skill_registry"):
        try:
            module = __import__(module_name, fromlist=["skill_registry"])
            registry = getattr(module, "skill_registry", None)
            if registry is not None:
                break
        except Exception:
            continue
    if registry is None:
        return {"status": "error", "message": "skill_registry introuvable."}
    loader = getattr(registry, "load_skills", None)
    if callable(loader):
        try:
            loader()
        except Exception:
            logger.debug("Chargement des skills indisponible.", exc_info=True)
    results: Any = []
    for method_name in ("search_skills", "search"):
        method = getattr(registry, method_name, None)
        if callable(method):
            try:
                results = method(real_query) if real_query else method()
            except TypeError:
                results = method()
            except Exception as exc:
                return {"status": "error", "message": str(exc)}
            break
    if isinstance(results, dict):
        results = list(results.values())
    results = list(results or [])
    return {"status": "success", "skills": results, "count": len(results)}


# ==============================================================================
# ★ NOUVEL OUTIL : git_clone (Clone un dépôt GitHub dans le workspace)
# ==============================================================================
def git_clone(url: str = "", dest: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Clone un dépôt GitHub dans le workspace pour l'analyser ensuite."""
    actual_url = _first_text(url, kwargs, ("repo_url", "link", "uri"))
    if not actual_url or "github.com" not in actual_url.lower():
        return {"status": "error", "message": "URL GitHub invalide. Format attendu : https://github.com/user/repo"}

    # Nettoyer l'URL (retirer /tree/main, /blob/, etc.)
    clean_url = re.sub(r'/(tree|blob)/[^/]+.*$', '', actual_url).rstrip('/')
    
    # ★ FIX : Nettoyer les points résiduels AVANT d'ajouter .git
    clean_url = clean_url.rstrip('.')
    
    if not clean_url.endswith('.git'):
        clean_url += '.git'

    # ★ FIX : Extraire le nom du repo de manière robuste
    repo_name = clean_url.split('/')[-1]  # ex: bek-v15-clean.git
    repo_name = repo_name.replace('.git', '')  # ex: bek-v15-clean
    repo_name = repo_name.strip('.').strip('/')  # ★ NOUVEAU : Enlève les points résiduels

    target_dir = dest or f"external/{repo_name}"

    try:
        target = _safe_resolve(target_dir)
        if target.exists():
            return {
                "status": "success", 
                "path": _relative(target), 
                "message": f"Le dépôt {repo_name} est déjà cloné dans {_relative(target)}."
            }

        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Exécution de git clone avec timeout
        result = subprocess.run(
            ["git", "clone", "--depth", "1", clean_url, str(target)],
            capture_output=True, text=True, timeout=120,
            cwd=str(WORKSPACE), env=_sanitized_env()
        )
        
        if result.returncode != 0:
            return {
                "status": "error", 
                "message": f"Échec du clonage Git : {result.stderr or result.stdout}"
            }

        return {
            "status": "success",
            "path": _relative(target),
            "message": f"✅ Dépôt cloné avec succès dans {_relative(target)}",
            "hint": f"Utilise l'outil 'python_save_report' avec dir_path='{_relative(target)}' pour analyser ce dépôt."
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Le clonage a dépassé le temps limite (120s)."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# ==============================================================================
# ★ NOUVEL OUTIL : analyze_architecture (Génère un rapport stratégique)
# ==============================================================================
def analyze_architecture(dir_path: str = "", **kwargs: Any) -> Dict[str, Any]:
    """Analyse l'architecture d'un projet : points forts, points faibles, plan d'action."""
    raw = _first_text(dir_path, kwargs, ("path", "file", "target_file"))
    if not raw:
        return {"status": "error", "message": "Paramètre 'dir_path' requis."}

    try:
        target = _safe_resolve(raw, allow_root=True)
        if not target.is_dir():
            return {"status": "error", "message": f"Dossier introuvable : {raw}"}

        # 1. Scanner les fichiers .py
        py_files = list(target.rglob("*.py"))
        total_lines = 0
        big_files = []
        for f in py_files:
            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()
                    total_lines += len(lines)
                    if len(lines) > 300:
                        big_files.append(f"{_relative(f)} ({len(lines)} lignes)")
            except Exception:
                pass

        # 2. Chercher les doublons
        import hashlib
        file_hashes = {}
        for f in py_files:
            try:
                h = hashlib.md5(f.read_bytes()).hexdigest()
                file_hashes.setdefault(h, []).append(_relative(f))
            except Exception:
                pass
        duplicates = [files for files in file_hashes.values() if len(files) > 1]

        # 3. Chercher les TODO/FIXME
        todos = 0
        for f in py_files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                todos += content.count("TODO") + content.count("FIXME")
            except Exception:
                pass

        # 4. Chercher les tests
        test_files = list(target.rglob("test_*.py"))
        test_files.extend(target.rglob("*_test.py"))

        # 5. Synthèse
        report = f"""
# 📊 Analyse d'Architecture

## 🎯 Indicateurs
- **Fichiers Python** : {len(py_files)}
- **Lignes totales** : {total_lines}
- **Fichiers > 300 lignes** : {len(big_files)}
- **Groupes de doublons** : {len(duplicates)}
- **TODO/FIXME** : {todos}
- **Fichiers de tests** : {len(test_files)}

## ✅ Points forts (à déduire de vos métriques)
- Architecture modulaire ({len(py_files)} fichiers Python)
- Présence de tests ({len(test_files)} fichiers)
- Complexité contrôlée ({len(big_files)} fichiers volumineux)

## ⚠️ Points faibles (à corriger)
- **{len(big_files)} fichiers trop volumineux** :
"""
        for f in big_files[:10]:
            report += f"  - `{f}`\n"

        report += f"\n- **{len(duplicates)} groupes de doublons** détectés :\n"
        for dup in duplicates[:5]:
            report += f"  - {', '.join(dup)}\n"

        report += f"\n- **{todos} TODO/FIXME** en attente\n"

        report += f"""
## 🚀 Plan d'action prioritaire
1. **Refactoriser les {len(big_files)} fichiers volumineux** en modules plus petits.
2. **Éliminer les {len(duplicates)} groupes de doublons** en créant des modules partagés.
3. **Résoudre les {todos} TODO/FIXME**.
4. **Augmenter la couverture de test** ({len(test_files)} fichiers de test actuellement).
"""
        return {"status": "success", "report": report.strip()}

    except Exception as exc:
        return {"status": "error", "message": str(exc)}


CODE_TOOLS_TABLE = {
    "read_file": read_file, "read_file_map": read_file_map, "write_file": write_file, "append_file": append_file,
    "edit_file": edit_file, "create_dir": create_dir, "grep": grep,
    "glob_files": glob_files, "ls": ls, "bash": bash, "search_skills": search_skills,
    "git_clone": git_clone,  # ★ Ajouté ici
    "analyze_architecture": analyze_architecture,  # ★ Ajouté ici
}
CODE_TOOLS_RISK = {
    "read_file": "L1", "read_file_map": "L1", "write_file": "L1", "append_file": "L1", "edit_file": "L1",
    "create_dir": "L1", "grep": "L1", "glob_files": "L1", "ls": "L1",
    "bash": "L2", "search_skills": "L1",
    "git_clone": "L2",  # ★ Ajouté ici
    "analyze_architecture": "L1",  # ★ Ajouté ici
}


def register_code_tools(hermes) -> Dict[str, Any]:
    activated: List[str] = []
    failed: List[Dict[str, str]] = []
    for name, func in CODE_TOOLS_TABLE.items():
        try:
            hermes.register_tool(name, func, risk_level=CODE_TOOLS_RISK.get(name, "L1"))
            activated.append(name)
        except Exception as exc:
            failed.append({"tool": name, "error": str(exc)})
            logger.exception("Échec d'enregistrement de %s", name)
    return {"status": "ok" if not failed else "partial", "activated": activated, "failed": failed}