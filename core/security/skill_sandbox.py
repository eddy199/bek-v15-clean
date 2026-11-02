# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v16 — Sandbox Statique AST pour les Compétences Dynamiques
# ------------------------------------------------------------------------------
# Analyse le code Python AVANT exécution et refuse :
#   • modules dangereux (subprocess, ctypes, socket, ...)
#   • modules hors whitelist (requests, urllib, http, ...)
#   • fonctions partielles dangereuses (os.system, shutil.rmtree, ...)
#   • builtins dangereux (eval, exec, compile, __import__, ...)
#   • introspection (__class__, __globals__, __subclasses__, ...)
#   • getattr(...) avec attribut interdit (même indirect)
#   • imports relatifs et imports-from avec noms dangereux
#   • tailles et complexité excessives
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
    "requests", "urllib", "urllib3", "http", "httpx", "aiohttp",
    "ftplib", "smtplib", "telnetlib", "xmlrpc",
    "webbrowser", "antigravity",
    "gc", "inspect", "cProfile", "profile", "pdb",
    "resource", "sysconfig", "site", "sitecustomize",
    "builtins",
}

# Modules autorisés avec restrictions sur certaines fonctions
PARTIAL_MODULES: Dict[str, Set[str]] = {
    "os": {
        "system", "popen", "remove", "unlink", "rmdir", "removedirs",
        "rename", "renames", "replace", "truncate", "chmod", "chown",
        "kill", "terminate", "execv", "execve", "execvp", "spawnv",
        "spawnve", "spawnvp", "fork", "forkpty", "setuid", "setgid",
        "seteuid", "setegid", "chroot", "abort", "startfile",
        "putenv", "setenv", "unsetenv",
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

# Whitelist positive : ces modules sont les SEULS autorisés.
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
            # 1. Blacklist
            if alias.name in BANNED_MODULES or root in BANNED_MODULES:
                self._flag(f"Import interdit : '{alias.name}'", node)
                continue
            # 2. Whitelist (nouveau)
            if root not in ALLOWED_MODULES:
                self._flag(
                    f"Import hors whitelist : '{alias.name}' "
                    f"(autorisés: {sorted(ALLOWED_MODULES)})",
                    node,
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        # Import relatif non supporté
        if node.level and node.level > 0:
            self._flag("Import relatif non autorisé", node)
            return

        mod = node.module or ""
        root = mod.split(".")[0]

        # 1. Blacklist
        if mod in BANNED_MODULES or root in BANNED_MODULES:
            self._flag(f"Import interdit : from {mod}", node)
            return

        # 2. Whitelist (nouveau)
        if root not in ALLOWED_MODULES:
            self._flag(
                f"Import hors whitelist : from {mod} "
                f"(autorisés: {sorted(ALLOWED_MODULES)})",
                node,
            )
            return

        # 3. Vérification des noms importés : from os import system
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

        # getattr(ANY, 'attr_interdit') → détection renforcée
        # On bloque TOUT getattr dont le 2e argument est un string interdit,
        # peu importe la cible.
        if isinstance(func, ast.Name) and func.id == "getattr":
            if len(node.args) >= 2:
                attr_arg = node.args[1]
                if isinstance(attr_arg, ast.Constant) and isinstance(attr_arg.value, str):
                    if (attr_arg.value in BANNED_BUILTINS
                            or attr_arg.value in BANNED_ATTRS):
                        self._flag(
                            f"getattr avec attribut interdit : '{attr_arg.value}'",
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

    # Vérification taille AST + sécurité
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
# EXÉCUTION SÉCURISÉE (Import Broker + isolation légère)
# ==============================================================================
# Modules réellement importables à l'exécution. Doit rester un SOUS-ENSEMBLE
# strict de ALLOWED_MODULES.
SAFE_MODULES: Dict[str, Any] = {
    "math": __import__("math"),
    "random": __import__("random"),
    "json": __import__("json"),
    "re": __import__("re"),
    "datetime": __import__("datetime"),
    "time": __import__("time"),
    "collections": __import__("collections"),
    "itertools": __import__("itertools"),
    "functools": __import__("functools"),
    "statistics": __import__("statistics"),
    "hashlib": __import__("hashlib"),
    "base64": __import__("base64"),
    "uuid": __import__("uuid"),
    "string": __import__("string"),
    "textwrap": __import__("textwrap"),
    "unicodedata": __import__("unicodedata"),
    "decimal": __import__("decimal"),
    "fractions": __import__("fractions"),
    "enum": __import__("enum"),
    "dataclasses": __import__("dataclasses"),
    "typing": __import__("typing"),
    "logging": __import__("logging"),
    "warnings": __import__("warnings"),
    "traceback": __import__("traceback"),
}


def _safe_import(name: str, globals=None, locals=None, fromlist=(), level=0):
    """
    __import__ contrôlé pour l'exécution sandboxée.
    Autorise uniquement les modules de SAFE_MODULES.
    """
    root = name.split(".")[0]
    if root not in SAFE_MODULES:
        raise ImportError(
            f"Module '{name}' non autorisé en sandbox (autorisés: "
            f"{sorted(SAFE_MODULES.keys())})"
        )
    return SAFE_MODULES[root]


def execute_validated_skill(code: str, context: dict = None) -> Dict[str, Any]:
    """
    Passe le code par le validateur AST de sécurité, puis l'exécute
    de manière contrôlée si le code est validé.

    Contexte disponible dans le skill via la variable `context`.
    Le skill doit écrire son résultat dans `output`.
    """
    validation_result = validate_skill_code(code)
    if not validation_result["valid"]:
        return {
            "status": "REJECTED",
            "errors": validation_result["errors"],
        }

    # --- Builtins minimaux + import broker ---
    safe_builtins = {
        "print": print,
        "range": range,
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "dict": dict,
        "list": list,
        "tuple": tuple,
        "set": set,
        "bool": bool,
        "None": None,
        "True": True,
        "False": False,
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "round": round,
        "sorted": sorted,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "isinstance": isinstance,
        "type": type,
        "repr": repr,
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "KeyError": KeyError,
        "IndexError": IndexError,
        "__import__": _safe_import,
    }

    safe_globals = {
        "__builtins__": safe_builtins,
        "__name__": "__skill_sandbox__",
    }
    local_scope = {
        "context": context or {},
        "output": None,
    }

    try:
        exec(code, safe_globals, local_scope)
        return {
            "status": "SUCCESS",
            "result": local_scope.get("output"),
        }
    except Exception as e:
        return {
            "status": "FAILED",
            "error": str(e),
            "error_type": type(e).__name__,
        }


# ==============================================================================
# TEST DIRECT
# ==============================================================================
if __name__ == "__main__":
    tests = {
        # --- Doivent passer ---
        "ok_simple": "x = 1 + 2\nprint(x)",
        "ok_json": "import json\nprint(json.dumps({'a': 1}))",
        "ok_math": "import math\noutput = math.sqrt(16)",
        "ok_datetime": "from datetime import datetime\noutput = datetime.now().year",
        # --- Doivent être rejetés : blacklist ---
        "ko_subprocess": "import subprocess\nsubprocess.run(['ls'])",
        "ko_from_os_system": "from os import system\nsystem('ls')",
        "ko_eval": "eval('1+1')",
        "ko_dunder": "x = ().__class__.__bases__",
        "ko_getattr": "getattr(__builtins__, 'eval')('1+1')",
        "ko_shutil_rmtree": "import shutil\nshutil.rmtree('/tmp')",
        "ko_import_relatif": "from . import evil",
        # --- Doivent être rejetés : whitelist ---
        "ko_requests": "import requests\nrequests.get('http://x')",
        "ko_urllib": "from urllib import request\nrequest.urlopen('http://x')",
        "ko_http": "import http.client",
        "ko_importlib": "import importlib\nimportlib.import_module('os')",
    }

    # Tests AST
    print("=" * 78)
    print("TESTS STATIQUES (validate_skill_code)")
    print("=" * 78)
    for name, code in tests.items():
        r = validate_skill_code(code)
        status = "✅ OK " if r["valid"] else "🛡️ REJET"
        first_err = r.get("errors", [])[:1]
        print(f"{status} | {name:22s} | {first_err}")

    # Tests d'exécution
    print()
    print("=" * 78)
    print("TESTS D'EXÉCUTION (execute_validated_skill)")
    print("=" * 78)

    exec_tests = [
        ("exec_ok_math",
         "import math\noutput = math.sqrt(16)"),
        ("exec_ok_json",
         "import json\noutput = json.dumps({'a': 1})"),
        ("exec_ok_context",
         "output = context.get('x', 0) * 2"),
        ("exec_ko_requests",
         "import requests\noutput = 'fail'"),
        ("exec_ko_runtime",
         "output = 1 / 0"),
    ]
    for name, code in exec_tests:
        r = execute_validated_skill(code, context={"x": 21})
        print(f"{name:22s} | {r}")