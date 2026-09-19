# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Sandbox Statique AST pour les Compétences Dynamiques
# ------------------------------------------------------------------------------
# Analyse le code Python AVANT exécution et refuse :
#   • modules dangereux (subprocess, ctypes, socket, ...)
#   • fonctions partielles dangereuses (os.system, shutil.rmtree, ...)
#   • builtins dangereux (eval, exec, compile, __import__, ...)
#   • introspection (__class__, __globals__, __subclasses__, ...)
#   • imports relatifs et imports-from avec noms dangereux
#   • tailles excessives
# ==============================================================================

from __future__ import annotations

import ast
from typing import Any, Dict, List, Set

# ── Configuration ───────────────────────────────────────────────────────────
MAX_CODE_BYTES = 200 * 1024   # 200 KB
MAX_AST_NODES = 20_000         # anti-bombes

BANNED_MODULES: Set[str] = {
    "subprocess", "ctypes", "socket", "pickle",
    "multiprocessing", "importlib", "pty", "signal",
    "asyncio",      # l'exécution async est gérée par le runner
    "threading",    # idem
    "concurrent",   # idem
}

# Modules autorisés avec restrictions sur certaines fonctions
PARTIAL_MODULES: Dict[str, Set[str]] = {
    "os": {
        "system", "popen", "remove", "unlink", "rmdir", "removedirs",
        "rename", "renames", "replace", "truncate", "chmod", "chown",
        "kill", "terminate", "execv", "execve", "execvp", "spawnv",
        "spawnve", "spawnvp", "fork", "forkpty", "setuid", "setgid",
        "seteuid", "setegid", "chroot", "abort", "startfile",
    },
    "sys": {"exit", "settrace", "setprofile", "setrecursionlimit"},
    "shutil": {"rmtree", "move", "chown", "copy2"},
    "pathlib": set(),  # tout autorisé pour Path
    "glob": set(),
}

BANNED_BUILTINS: Set[str] = {
    "eval", "exec", "compile", "__import__", "breakpoint",
    "input", "globals", "locals", "vars", "open",
    "memoryview", "reload",
}

BANNED_ATTRS: Set[str] = {
    "__class__", "__subclasses__", "__bases__", "__mro__",
    "__globals__", "__builtins__", "__import__", "__code__",
    "__closure__", "__reduce__", "__reduce_ex__",
    "__getattribute__", "__setattr__", "__delattr__",
    "__dict__", "__weakref__", "__func__", "__self__",
}

# Whitelist positive : ces modules sont toujours OK
ALLOWED_MODULES: Set[str] = {
    "math", "random", "json", "re", "datetime", "time",
    "collections", "itertools", "functools", "typing",
    "dataclasses", "enum", "decimal", "fractions", "statistics",
    "hashlib", "base64", "binascii", "hmac", "secrets",
    "uuid", "string", "textwrap", "unicodedata",
    "pathlib", "os", "sys", "shutil", "glob",  # gated par PARTIAL_MODULES
    "io", "tempfile", "zipfile", "tarfile", "csv", "sqlite3",
    "logging", "warnings", "traceback",
    "core", "skills",  # modules internes BEK
}


# ==============================================================================
# VISITEUR AST
# ==============================================================================
class SecurityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: List[str] = []
        self.node_count = 0

    def _flag(self, msg: str, node: ast.AST) -> None:
        lineno = getattr(node, "lineno", "?")
        self.violations.append(f"Ligne {lineno} : {msg}")

    # ── Imports ─────────────────────────────────────────────────────────────
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if alias.name in BANNED_MODULES or root in BANNED_MODULES:
                self._flag(f"Import interdit : '{alias.name}'", node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        # Import relatif non supporté
        if node.level and node.level > 0:
            self._flag("Import relatif non autorisé", node)
            return

        mod = node.module or ""
        root = mod.split(".")[0]

        if mod in BANNED_MODULES or root in BANNED_MODULES:
            self._flag(f"Import interdit : from {mod}", node)
            return

        # Vérification des noms importés : from os import system
        if mod in PARTIAL_MODULES:
            for alias in node.names:
                if alias.name in PARTIAL_MODULES[mod]:
                    self._flag(
                        f"Import interdit : from {mod} import {alias.name}",
                        node,
                    )
        self.generic_visit(node)

    # ── Appels ──────────────────────────────────────────────────────────────
    def visit_Call(self, node: ast.Call) -> None:
        func = node.func

        # eval(...), exec(...), __import__(...)
        if isinstance(func, ast.Name) and func.id in BANNED_BUILTINS:
            self._flag(f"Appel interdit : '{func.id}()'", node)

        # os.system(...), shutil.rmtree(...)
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            mod_name = func.value.id
            if mod_name in PARTIAL_MODULES and func.attr in PARTIAL_MODULES[mod_name]:
                self._flag(f"Appel interdit : '{mod_name}.{func.attr}()'", node)

            # getattr(obj, 'eval')(...) → détection
            if func.attr == "getattr":
                for arg in node.args[1:2]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value in BANNED_BUILTINS or arg.value in BANNED_ATTRS:
                            self._flag(
                                f"getattr avec attribut interdit : '{arg.value}'",
                                node,
                            )

        self.generic_visit(node)

    # ── Attributs ───────────────────────────────────────────────────────────
    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in BANNED_ATTRS:
            self._flag(f"Accès d'introspection interdit : '.{node.attr}'", node)
        self.generic_visit(node)

    # ── Comptage global ─────────────────────────────────────────────────────
    def generic_visit(self, node: ast.AST) -> None:
        self.node_count += 1
        super().generic_visit(node)


# ==============================================================================
# API PUBLIQUE
# ==============================================================================
def validate_skill_code(code: str) -> Dict[str, Any]:
    """
    Valide la syntaxe et la sécurité du code Python avant exécution/sauvegarde.

    Retourne :
        {"valid": bool, "errors": List[str]}
    """
    # Taille
    try:
        size = len(code.encode("utf-8"))
    except Exception:
        return {"valid": False, "errors": ["Code non encodable en UTF-8"]}

    if size > MAX_CODE_BYTES:
        return {
            "valid": False,
            "errors": [f"Code trop volumineux ({size} > {MAX_CODE_BYTES} octets)"],
        }

    # Parsing
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {
            "valid": False,
            "errors": [f"Erreur de syntaxe Python (Ligne {e.lineno}) : {e.msg}"],
        }
    except Exception as e:
        return {"valid": False, "errors": [f"Parse error : {e}"]}

    # Vérification taille AST
    visitor = SecurityVisitor()
    visitor.visit(tree)

    if visitor.node_count > MAX_AST_NODES:
        return {
            "valid": False,
            "errors": [
                f"AST trop complexe ({visitor.node_count} > {MAX_AST_NODES} nœuds)"
            ],
        }

    if visitor.violations:
        return {"valid": False, "errors": visitor.violations}

    return {"valid": True, "errors": []}


# ==============================================================================
# TEST DIRECT
# ==============================================================================
if __name__ == "__main__":
    tests = {
        "ok_simple": "x = 1 + 2\nprint(x)",
        "ok_json": "import json\nprint(json.dumps({'a': 1}))",
        "ko_subprocess": "import subprocess\nsubprocess.run(['ls'])",
        "ko_from_os_system": "from os import system\nsystem('ls')",
        "ko_eval": "eval('1+1')",
        "ko_dunder": "x = ().__class__.__bases__",
        "ko_getattr": "getattr(__builtins__, 'eval')('1+1')",
        "ko_shutil_rmtree": "import shutil\nshutil.rmtree('/tmp')",
        "ko_import_relatif": "from . import evil",
    }

    for name, code in tests.items():
        r = validate_skill_code(code)
        status = "✅ OK " if r["valid"] else "🛡️ REJET"
        print(f"{status} | {name:22s} | {r.get('errors', [])[:1]}")