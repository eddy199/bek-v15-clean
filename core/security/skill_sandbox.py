# ==============================================================================
# BEK-v16 — Sandbox Statique AST pour les Compétences Dynamiques
# ==============================================================================
import ast
from typing import Dict, Any

BANNED_MODULES = {
    "subprocess", "ctypes", "socket", "pickle",
    "multiprocessing", "importlib", "gc", "pty", "signal",
}

PARTIAL_MODULES = {
    "os": {
        "system", "popen", "remove", "unlink", "rmdir", "removedirs",
        "rename", "renames", "replace", "truncate", "chmod", "chown",
        "kill", "terminate", "execv", "execve", "execvp", "spawnv",
        "fork", "setuid", "setgid",
    },
    "sys": {"exit", "settrace", "setprofile", "modules"},
    "shutil": {"rmtree", "move"},
}

BANNED_BUILTINS = {
    "eval", "exec", "compile", "__import__", "breakpoint",
    "input", "globals", "locals", "vars",
}

BANNED_ATTRS = {
    "__class__", "__subclasses__", "__bases__", "__mro__",
    "__globals__", "__builtins__", "__import__", "__code__",
    "__closure__", "__reduce__", "__reduce_ex__",
}


class SecurityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []

    def _flag(self, msg: str, node: ast.AST):
        lineno = getattr(node, "lineno", "?")
        self.violations.append(f"Ligne {lineno} : {msg}")

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            root = alias.name.split(".")[0]
            if alias.name in BANNED_MODULES or root in BANNED_MODULES:
                self._flag(f"Import interdit : '{alias.name}'", node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        root = mod.split(".")[0]
        if mod in BANNED_MODULES or root in BANNED_MODULES:
            self._flag(f"Import interdit : from {mod}", node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in BANNED_BUILTINS:
            self._flag(f"Appel de fonction interdit : '{func.id}()'", node)
        elif isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):
                mod_name = func.value.id
                if mod_name in PARTIAL_MODULES and func.attr in PARTIAL_MODULES[mod_name]:
                    self._flag(f"Appel interdit : '{mod_name}.{func.attr}()'", node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr in BANNED_ATTRS:
            self._flag(f"Accès d'introspection interdit : '.{node.attr}'", node)
        self.generic_visit(node)


def validate_skill_code(code: str) -> Dict[str, Any]:
    """Valide la syntaxe et la sécurité du code Python avant exécution/sauvegarde."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"valid": False, "errors": [f"Erreur de syntaxe Python (Ligne {e.lineno}) : {e.msg}"]}

    visitor = SecurityVisitor()
    visitor.visit(tree)
    if visitor.violations:
        return {"valid": False, "errors": visitor.violations}

    return {"valid": True, "errors": []}